from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentDesignIntent
from scidiscovery.artifact_agent.service.local_workspace import SealedFile, SealedWorkspace
from scidiscovery.artifact_agent.service.run_outputs import (
    RunCheckerError,
    RunOutputError,
    validate_run_output,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_experiment_components import _experiment_context
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations import catalog as catalog_module
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    InvocationArtifact,
    operation_port_json_schema,
    operation_primary_output,
    preflight_operation,
)
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.parameter_operations import ParameterEvidencePackage


def _catalog():
    return compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )


def test_every_public_agent_exposes_one_compiled_output_contract() -> None:
    catalog = _catalog()
    agents = tuple(
        catalog.operation(operation_id)
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.catalog_scope == "public"
        and catalog.operation(operation_id).spec.executor.kind == "agent"
    )
    assert agents
    for compiled in agents:
        port = operation_primary_output(compiled)
        schema = operation_port_json_schema(compiled, port)
        semantic = schema["x-scidiscovery-semantic-constraints"]
        validation = schema["x-scidiscovery-validation-contract"]
        assert semantic["schema_version"] == 1
        assert semantic["rules"]
        assert len({item["rule_id"] for item in semantic["rules"]}) == len(
            semantic["rules"]
        )
        assert validation["operation_id"] == compiled.spec.operation_id
        assert validation["operation_digest"] == compiled.digest
        assert validation["output_port"] == port.name
        assert "runtime.schema" in {
            item["rule_id"] for item in validation["rules"]
        }
        checkers = {item["phase"]: item["rule_id"] for item in validation["checkers"]}
        assert "payload" in checkers
        assert set(checkers.values()) <= {
            item["rule_id"] for item in semantic["rules"]
        }


def test_experiment_revision_has_only_its_true_behavioral_inputs() -> None:
    operation = _catalog().operation("science.experiment.revise.v1").spec
    assert tuple(port.name for port in operation.inputs) == (
        "prior_draft",
        "change_request",
    )
    assert operation.input_admission is None
    assert operation.guards == ()
    assert operation.outputs[0].context_sources == (
        "prior_draft",
        "change_request",
    )


def test_experiment_design_exposes_the_exact_critic_review() -> None:
    operation = _catalog().operation("science.experiment.design.v1").spec
    critic_review = next(
        port for port in operation.inputs if port.name == "critic_review"
    )
    assert critic_review.exposure == "full"


@pytest.fixture
def experiment_case():
    critic = canonical_json(
        {"disposition": "ready_for_experiment", "schema_version": 2}
    )
    objective = canonical_json(
        {
            "objective_key": "objective_expected",
            "intent": "mechanism_discrimination",
            "statement": "Distinguish one bounded mechanism.",
            "closure_requirements": [
                {
                    "requirement_key": "comparison_required",
                    "description": "Compare the bounded candidates.",
                    "requirement_type": "comparison_present",
                    "comparison_purposes": ["mechanism_separation"],
                }
            ],
        }
    )
    hypotheses = canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective_expected",
            "stage_objective": "Separate one bounded mechanism.",
            "contradiction": "The supplied evidence does not distinguish it.",
            "hypotheses": [
                {
                    "hypothesis_key": "hypothesis_a",
                    "statement": "A bounded mechanism changes the response.",
                    "mechanism": "The mechanism has one finite intervention.",
                    "scope": "Only the supplied system.",
                    "predictions": [
                        {
                            "prediction_key": "prediction_a",
                            "observable": "response",
                            "expected_outcome": "The response changes.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "falsifier_a",
                            "observable": "response",
                            "rejection_condition": "The response does not change.",
                        }
                    ],
                }
            ],
        }
    )
    intent = {
        "study_kind": "scientific",
        "objective_key": "objective_wrong",
        "selected_hypothesis_keys": ["hypothesis_a"],
        "proposals": [
            {
                "experiment_key": "experiment_a",
                "hypothesis_keys": ["hypothesis_a"],
                "frozen_invariants": ["Use the same bounded system."],
                "cases": [
                    {
                        "case_key": "baseline",
                        "scientific_role": "baseline",
                        "purpose": "Establish the baseline.",
                    },
                    {
                        "case_key": "perturbation",
                        "scientific_role": "perturbation",
                        "purpose": "Apply the bounded intervention.",
                    },
                ],
                "baseline_case_key": "baseline",
                "variables": [
                    {
                        "variable_key": "intervention",
                        "scientific_path": "model.intervention",
                        "factor_type": "physical",
                        "comparison_role": "intended_change",
                        "unit": "1",
                        "baseline_value": 0,
                        "case_overrides": [
                            {"case_key": "perturbation", "value": 1}
                        ],
                        "equivalence_rule": "exact",
                        "rationale": "The intervention distinguishes the candidates.",
                    }
                ],
                "required_observables": ["response"],
                "identifiability_claims": [
                    {
                        "hypothesis_key": "hypothesis_a",
                        "observable": "response",
                        "distinguishing_outcome": "The response changes.",
                        "decision_rule": "Compare the two bounded cases.",
                        "ambiguity_conditions": ["A case cannot complete."],
                        "smallest_resolving_control": "Repeat the failed case.",
                    }
                ],
                "prediction_tests": [
                    {
                        "hypothesis_key": "hypothesis_a",
                        "prediction_key": "prediction_a",
                        "observable": "response",
                        "expected_result": "The response changes.",
                        "falsifying_result": "The response does not change.",
                    }
                ],
                "validation_intent": {
                    "numerical": {"rationale": "Check numerical completion."},
                    "physical": {"rationale": "Check the bounded response."},
                    "experimental": {"rationale": "No additional observation."},
                },
                "resource_estimate": {
                    "relative_cost": "low",
                    "runtime_basis": "Two bounded cases.",
                },
                "stop_conditions": ["Stop after both cases."],
                "value_assessment": {
                    "evidence_support": "medium",
                    "discrimination_power": "medium",
                    "information_gain": "medium",
                    "cost": "low",
                    "added_free_parameters": 1,
                    "rationale": "One bounded comparison tests the mechanism.",
                },
            }
        ],
        "priority_order": ["experiment_a"],
        "priority_rationale": "Only one bounded experiment is required.",
    }
    return intent, {
        "critic_review": critic,
        "research_objective": objective,
        "hypothesis_portfolio": hypotheses,
    }


def test_experiment_context_reports_validation_as_a_correctable_rule(experiment_case) -> None:
    intent, sources = experiment_case
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    with pytest.raises(SemanticRuleViolation, match="objective_key differs"):
        _experiment_context(intent, sources, {})


def test_experiment_materialized_constraints_are_correctable(experiment_case) -> None:
    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    variable = intent["proposals"][0]["variables"][0]
    variable["baseline_value"] = False
    variable["case_overrides"][0]["value"] = 0
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    with pytest.raises(SemanticRuleViolation, match="intended_change variable must vary"):
        _experiment_context(intent, sources, {})


@pytest.fixture
def engineering_case(experiment_case):
    intent, sources = experiment_case
    intent.update(study_kind="engineering", objective_key=None,
                  engineering_objective="Check one bounded numerical case.",
                  selected_hypothesis_keys=[])
    proposal = intent["proposals"][0]
    proposal.update(hypothesis_keys=[], cases=proposal["cases"][:1],
                    baseline_case_key=None, variables=[],
                    identifiability_claims=[], prediction_tests=[])
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    return intent, sources


def test_engineering_run_submission_is_correctable_then_completes(tmp_path, engineering_case) -> None:
    intent, sources = engineering_case
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    state, diagnostics = runtime.runs.submit(run_id)
    assert state == "rejected"
    assert runtime.runs.status(run_id).state == "running"
    assert {item["rule_id"] for item in diagnostics} == {
        "experiment.design.objective_and_hypothesis_binding"
    }
    assert any("engineering experiment requires numerical validation only" in item["message"]
               for item in diagnostics)
    intent["proposals"][0]["validation_intent"]["numerical"]["reviewed_checks"] = [{
        "observable": "completion", "metric": "bounded numerical completion",
        "acceptance_condition": "The single case completes.",
        "failure_action": "Stop and inspect the numerical failure.",
        "basis": "This engineering check has one numerical case.",
    }]
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ("completed", ())
    assert runtime.runs.status(run_id).state == "completed"


@pytest.mark.parametrize("fault", ("critic_review", "value_error", "runtime_error"))
def test_engineering_run_submission_keeps_system_failures_terminal(
    tmp_path, monkeypatch, engineering_case, fault,
) -> None:
    from scidiscovery.artifact_agent.schema import experiment_intent

    intent, sources = engineering_case
    if fault == "critic_review":
        sources["critic_review"] = b"{}"
    else:
        error_type = ValueError if fault == "value_error" else RuntimeError

        def broken_materializer(*_args):
            raise error_type("materializer programming defect")

        monkeypatch.setattr(experiment_intent, "materialize_experiment_design_intent", broken_materializer)
    runtime, run_id, output = _experiment_run(tmp_path, sources)
    output.write_bytes(_experiment_envelope(intent))
    assert runtime.runs.submit(run_id) == ("failed", ())
    assert runtime.runs.status(run_id).state == "failed"


def _experiment_run(tmp_path, sources):
    from tests.operations.test_general_transform_operations import _intake, _register, _root

    catalog = _catalog()
    compiled = catalog.operation("science.experiment.design.v1")
    runtime, instance, _ = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    content = {"scientific_foundation": _intake().scientific_foundation.canonical_json(), **sources}
    envelopes = {}
    artifacts = {}
    for port in compiled.spec.inputs:
        parents = (() if port.name == "scientific_foundation" else
                   (envelopes["scientific_foundation"].ref,))
        if port.name == "critic_review":
            parents += (envelopes["hypothesis_portfolio"].ref,)
        envelope = _register(runtime, instance, name=port.name, raw=content[port.name],
                             kind=port.name, schema=port.schema_id, parents=parents)
        envelopes[port.name] = envelope
        artifacts[port.name] = (InvocationArtifact(
            artifact_name=port.name, ref=envelope.ref, schema_id=envelope.schema_id,
            media_type=envelope.media_type, size_bytes=envelope.size_bytes,
            parent_refs=envelope.parent_refs,
        ),)
    bound = preflight_operation(compiled, name="experiment", artifacts_by_port=artifacts,
                                instruction="Check the exact experiment output contract.")
    # Exercise the real Run submission lifecycle independently of UI admission.
    run_id = runtime.runs.schedule(
        bound, instance_id=instance.instance_id, output_binding_name="experiment",
        output_logical_name="experiment", output_revision=1,
        output_binding_fingerprint="a" * 64,
    )
    _, workspace = runtime.runs.open(operation_id=compiled.spec.operation_id,
                                     operation_digest=compiled.digest)
    return runtime, run_id, workspace.output_directory / "result.json"


@pytest.mark.parametrize("broken_input", ("critic_review", "research_objective", "hypothesis_portfolio"))
def test_experiment_submission_rejects_corrupt_immutable_inputs_as_system_failures(
    tmp_path, experiment_case, broken_input,
) -> None:
    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    sources[broken_input] = b"{}"
    with pytest.raises(RunCheckerError, match="context checker failed"):
        _validate_experiment_submission(tmp_path, intent, sources)


def test_experiment_submission_preserves_declared_rule_id(tmp_path, experiment_case) -> None:
    intent, sources = experiment_case
    with pytest.raises(RunOutputError) as error:
        _validate_experiment_submission(tmp_path, intent, sources)
    assert {item["rule_id"] for item in error.value.details} == {
        "experiment.design.objective_and_hypothesis_binding"
    }
    assert any("objective_key differs" in item["message"] for item in error.value.details)


@pytest.mark.parametrize("error_type", (ValueError, RuntimeError))
def test_experiment_materializer_program_errors_remain_system_failures(
    tmp_path, monkeypatch, experiment_case, error_type,
) -> None:
    from scidiscovery.artifact_agent.schema import experiment_intent

    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"

    def broken_materializer(*_args):
        raise error_type("materializer programming defect")

    monkeypatch.setattr(experiment_intent, "materialize_experiment_design_intent", broken_materializer)
    with pytest.raises(RunCheckerError, match="context checker failed") as error:
        _validate_experiment_submission(tmp_path, intent, sources)
    assert type(error.value.__cause__) is error_type


def test_context_sources_do_not_include_a_different_port_with_the_same_prefix(
    tmp_path, experiment_case,
) -> None:
    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    sources["critic_review_aux"] = b"private lineage content"
    compiled = _catalog().operation("science.experiment.design.v1")
    extra = compiled.spec.inputs[0].model_copy(update={"name": "critic_review_aux", "min_items": 0})
    implementations = dict(compiled.implementations)
    observed = []

    def check(payload, context, handoff):
        observed.append(set(context))
        _experiment_context(payload, context, handoff)

    implementations["general_science:experiment_context"] = check
    compiled = replace(
        compiled, implementations=implementations,
        spec=compiled.spec.model_copy(update={"inputs": (*compiled.spec.inputs, extra)}),
    )
    _validate_experiment_submission(tmp_path, intent, sources, compiled=compiled)
    assert observed == [{"critic_review", "research_objective", "hypothesis_portfolio"}]


def test_schema_projection_program_errors_remain_system_failures(
    tmp_path, monkeypatch, experiment_case,
) -> None:
    from scidiscovery.artifact_agent.service import run_outputs

    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"

    def broken_projection(*_args, **_kwargs):
        raise ValueError("projection programming defect")

    monkeypatch.setattr(run_outputs, "operation_port_json_schema", broken_projection)
    with pytest.raises(
        RunCheckerError, match="compiled output schema projection failed"
    ) as error:
        _validate_experiment_submission(tmp_path, intent, sources)
    assert type(error.value.__cause__) is ValueError


def _experiment_envelope(intent):
    return canonical_json({
        "schema_version": 1,
        "payload": intent,
        "handoff": {"verdict": "pass", "summary": "One bounded design."},
    })


def _validate_experiment_submission(tmp_path, intent, sources, *, compiled=None):
    content = _experiment_envelope(intent)
    (tmp_path / "result.json").write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    sealed = SealedWorkspace(
        backend="test", backend_version="1", run_id="experiment-contract",
        digest=digest, root=tmp_path,
        files=(SealedFile(relative_path="result.json", media_type="application/json",
                          size_bytes=len(content), sha256=digest),),
    )
    return validate_run_output(
        compiled or _catalog().operation("science.experiment.design.v1"), sealed,
        input_source_ports={name: name for name in sources}, input_bytes=sources,
    )


def test_experiment_context_does_not_reclassify_invalid_inputs() -> None:
    with pytest.raises(ValueError) as error:
        _experiment_context({}, {"critic_review": b"{}"}, {})
    assert not isinstance(error.value, SemanticRuleViolation)


def test_scientific_curve_contracts_declare_the_objective_as_required() -> None:
    catalog = _catalog()
    for operation_id in (
        "science.curve.contract.design.v1",
        "science.curve.contract.review.v1",
    ):
        operation = catalog.operation(operation_id)
        objective = next(
            port for port in operation.spec.inputs if port.name == "research_objective"
        )
        assert objective.min_items == 1
        contract = operation_port_json_schema(
            operation, operation_primary_output(operation)
        )["x-scidiscovery-validation-contract"]
        context_checker = next(
            item for item in contract["checkers"] if item["phase"] == "context"
        )
        assert context_checker["rule_id"] in {
            "curve.contract.objective_binding",
            "curve.review.subject_binding",
        }
        source_contract = {
            item["port"]: item["required"] for item in contract["context_sources"]
        }
        assert source_contract["research_objective"] is True


def test_threshold_unit_vocabulary_is_visible_in_the_json_schema() -> None:
    schema = ExperimentPortfolio.model_json_schema(mode="validation")
    unit_schema = schema["$defs"]["MetricThreshold"]["properties"]["unit"]
    assert "1" in unit_schema["enum"]
    assert "dimensionless" in unit_schema["enum"]
    assert "probability" not in unit_schema["enum"]

    parameter_schema = ParameterEvidencePackage.model_json_schema(mode="validation")
    requirement_unit = parameter_schema["$defs"]["DeviceParameterRequirement"][
        "properties"
    ]["canonical_unit"]
    claim_unit = parameter_schema["$defs"]["DeviceParameterClaim"]["properties"][
        "unit"
    ]
    assert requirement_unit["enum"] == claim_unit["enum"]
    assert "1" in requirement_unit["enum"]
    assert "probability" not in requirement_unit["enum"]


def test_evidence_source_projection_uses_only_exact_bound_inventory_aliases() -> None:
    compiled = _catalog().operation("tcad.parameter.evidence.extract.v1")
    port = operation_primary_output(compiled)
    schema = operation_port_json_schema(
        compiled,
        port,
        input_source_ports={
            "required_parameter_checklist": "required_parameter_checklist",
            "source_material_001": "source_material",
            "source_material_002": "source_material",
        },
    )
    evidence = schema["properties"]["scientific_intake"]["$ref"]
    intake = schema["$defs"][evidence.removeprefix("#/$defs/")]
    foundation_ref = intake["properties"]["scientific_foundation"]["$ref"]
    foundation = schema["$defs"][foundation_ref.removeprefix("#/$defs/")]
    item_projection = foundation["properties"]["evidence"]["items"]["allOf"][-1]
    assert item_projection["properties"]["source_key"]["enum"] == [
        "source_material_001",
        "source_material_002",
    ]
    validation = schema["x-scidiscovery-validation-contract"]
    usages = {
        item["port"]: item["usage"] for item in validation["context_sources"]
    }
    assert usages == {
        "required_parameter_checklist": "prior_signal",
        "source_material": "evidence_inventory",
    }


def test_empty_optional_evidence_inventory_forbids_nonempty_evidence() -> None:
    compiled = _catalog().operation("science.evidence.audit.v1")
    port = operation_primary_output(compiled)
    static_schema = operation_port_json_schema(compiled, port)
    assert static_schema["properties"]["evidence"].get("maxItems") == 32

    bound_schema = operation_port_json_schema(
        compiled,
        port,
        input_source_ports={"scientific_foundation": "scientific_foundation"},
    )
    assert bound_schema["properties"]["evidence"]["maxItems"] == 0


def test_evidence_source_projection_version_changes_only_applicable_digest(
    monkeypatch,
) -> None:
    first = _catalog()
    selector = catalog_module._evidence_source_projection_version

    def next_projection(spec, port):
        return "evidence-source-enum.test-next" if selector(spec, port) else None

    monkeypatch.setattr(
        catalog_module, "_evidence_source_projection_version", next_projection
    )
    second = _catalog()
    assert (
        first.operation("tcad.parameter.evidence.extract.v1").digest
        != second.operation("tcad.parameter.evidence.extract.v1").digest
    )
    assert (
        first.operation("science.experiment.design.v1").digest
        == second.operation("science.experiment.design.v1").digest
    )
