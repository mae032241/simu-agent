from __future__ import annotations

import json
import os
import sqlite3

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolError,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.execution_context import ExecutionContext
from tcad_artifact.device_parameters import (
    DeviceParameterCoverageReport,
    DeviceParameterRequirementSet,
    DeviceParameterSet,
    project_parameter_uncertainty,
)
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
from scidiscovery.builtin_plugin import CORE_PLUGIN as BUILTIN_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.general_science_control_operations import INTAKE_SPLIT_OPERATION
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.execution_control import SolverCapabilitySnapshot
from tcad_artifact.operation_transforms import EXECUTION_CONTEXT_OPERATION
from tcad_artifact.parameter_operations import (
    COVERAGE_OPERATION as PARAMETER_COVERAGE_OPERATION,
    UNCERTAINTY_OPERATION as PARAMETER_UNCERTAINTY_OPERATION,
)
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
from scidiscovery.operations.invoke import (
    InvocationArtifact,
    OperationInvocationError,
    execute_compiled_transform,
    preflight_operation,
)


EXPERIMENT_MATERIALIZE_OPERATION = "science.experiment.materialize.v1"
OBJECTIVE_PROJECT_OPERATION = "science.objective.project.v1"
GENERAL_TRANSFORM_OPERATION_IDS = {
    INTAKE_SPLIT_OPERATION,
    EXPERIMENT_MATERIALIZE_OPERATION,
    OBJECTIVE_PROJECT_OPERATION,
}


def test_materialize_maximum_legal_goals_and_current_selection_without_expansion() -> None:
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    from tests.operations.m3_transform_equivalence_runner import _engineering_intent

    intent = json.loads(_engineering_intent())
    goals = ["原样目标 " + "x" * (8192 - 5), *[f"Bounded goal {index}" for index in range(15)]]
    assert len(goals[0]) == 8192
    proposal = intent["proposals"][0]
    proposal.update(objectives=goals, current_objectives=goals)
    raw, _ = materialize_experiment_plan({"experiment_design_intent": canonical_json(intent)})
    plan = ExperimentPortfolio.model_validate_json(raw, strict=True)
    assert plan.proposals[0].objectives == (intent["engineering_objective"], *goals)
    assert plan.proposals[0].current_objectives == tuple(goals)
    assert len(plan.proposals[0].objectives) == 17
    assert len(plan.proposals[0].cases) == 1
    assert plan.proposals[0].resource_estimate.case_count == 1
    assert plan.proposals[0].value_assessment.rationale == proposal["value_assessment"]["rationale"]
    assert plan.priority_rationale == intent["priority_rationale"]


def _intake() -> ScientificIntake:
    objective = "Reproduce one bounded target curve."
    return ScientificIntake.model_validate_json(
        canonical_json({
            "problem_frame": {
                "title": "Minimal frame",
                "scientific_question": "Can the target curve be reproduced?",
                "objective": objective,
                "current_contradiction": "The baseline misses the target.",
                "scope": "One frozen curve.",
                "foundation_item_keys": ["target"],
                "observables": [
                    {
                        "observable_key": "profile",
                        "description": "Concentration versus depth.",
                        "role": "target",
                        "foundation_item_keys": ["target"],
                        "acceptance_relevance": "It is the frozen comparison target.",
                    }
                ],
                "claim_boundary": {
                    "allowed_claim": "Only the scoped curve may be compared.",
                    "required_conditions": ["All declared gates pass."],
                },
                "stop_conditions": ["Stop after the deterministic split."],
            },
            "scientific_foundation": {
                "title": "Minimal foundation",
                "objective": objective,
                "summary": "One target is frozen.",
                "evidence": [
                    {
                        "source_key": "paper",
                        "source_type": "frozen_input",
                        "title": "Paper fixture",
                        "locator": "paper.pdf#figure",
                    }
                ],
                "items": [
                    {
                        "item_key": "target",
                        "item_type": "target_data",
                        "epistemic_status": "paper_fact",
                        "statement": "The target is the supplied curve.",
                        "scope": "The frozen fixture only.",
                        "evidence_keys": ["paper"],
                    }
                ],
            },
        }),
        strict=True,
    )


def test_intake_source_context_accepts_only_exact_bound_source_names() -> None:
    from scidiscovery.general_science_components import _intake_source_context
    from scidiscovery.operation_contract import SemanticRuleViolation

    payload = _intake().model_dump(mode="json")
    payload["scientific_foundation"]["evidence"][0]["source_key"] = (
        "source_material"
    )
    payload["scientific_foundation"]["items"][0]["evidence_keys"] = [
        "source_material"
    ]

    _intake_source_context(
        payload,
        {"source_material": b"bounded source"},
        {},
    )

    payload["scientific_foundation"]["evidence"][0]["source_key"] = (
        "invented_source"
    )
    payload["scientific_foundation"]["items"][0]["evidence_keys"] = [
        "invented_source"
    ]
    with pytest.raises(SemanticRuleViolation, match="outside the bound inputs"):
        _intake_source_context(
            payload,
            {"source_material": b"bounded source"},
            {},
        )


def test_general_intake_operations_execute_the_declared_source_binding_rule() -> None:
    catalog = compile_catalog((BUILTIN_PLUGIN, GENERAL_PLUGIN))
    for operation_id in (
        "science.evidence.extract.v1",
        "science.intake.revise.v1",
        "science.evidence.revise-from-critic.v1",
    ):
        output = catalog.operation(operation_id).spec.outputs[0]
        assert output.context_validator is not None
        assert output.context_validator.component_id == "intake_source_context"
        assert output.context_rule_id == "intake.source_binding"
        assert output.context_sources == ("source_material",)


def _catalog():
    return compile_catalog(
        (BUILTIN_PLUGIN, GENERAL_PLUGIN, TCAD_PLUGIN, CURVE_PLUGIN)
    )


def _invocation_artifact(
    name: str,
    schema: str,
    *,
    parent_refs: tuple[ArtifactRef, ...] = (),
    media_type: str = "application/json",
) -> InvocationArtifact:
    ref = ArtifactRef(
        artifact_id=f"art_{name.replace('-', '_')}",
        sha256=(name.encode().hex() + "0" * 64)[:64],
        kind=name.replace("-", "_"),
        schema_id=schema,
    )
    return InvocationArtifact(
        artifact_name=name,
        ref=ref,
        schema_id=schema,
        media_type=media_type,
        size_bytes=32,
        parent_refs=parent_refs,
    )


def _root(tmp_path, *, catalog=None):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="r3_transform",
        title="R3 deterministic transform operations",
        objective="Verify catalog-owned deterministic transforms.",
    )
    facade = RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog or _catalog(),
    )
    return runtime, instance, RootMCPRouter(facade)


def _register(
    runtime,
    instance,
    *,
    name: str,
    raw: bytes,
    kind: str,
    schema: str,
    media_type: str = "application/json",
    parents: tuple[ArtifactRef, ...] = (),
    provisional: bool = False,
):
    envelope = runtime.artifacts.register(
        raw,
        ArtifactRegistration(
            kind=kind,
            schema_id=schema,
            payload_schema_version=1,
            media_type=media_type,
            creator=runtime.actor,
            parent_refs=parents,
            labels=(
                {"scientific_claim_admissible": "false"}
                if provisional
                else {}
            ),
        ),
        idempotency_key=f"r3-transform:{name}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=name,
        object_id=envelope.artifact_id,
    )
    return envelope


def test_general_plugin_compiles_only_its_domain_neutral_transform_set() -> None:
    catalog = compile_catalog((BUILTIN_PLUGIN, GENERAL_PLUGIN))
    actual = {
        operation_id
        for operation_id in catalog.operation_ids()
        if operation_id != "builtin.test.transform"
        and catalog.operation(operation_id).spec.executor.kind == "transform"
    }
    assert actual == GENERAL_TRANSFORM_OPERATION_IDS
    assert all(catalog.operation(item).plugin_id == "general_science" for item in actual)
    assert not any("foundation" in item or "hypothesis-portfolio" in item for item in actual)


def _solver_capability_snapshot() -> SolverCapabilitySnapshot:
    return SolverCapabilitySnapshot(
        profile_id="sprocess_r2020_09",
        solver_kind="sprocess",
        launch_name="sprocess",
        public_arguments=("-i",),
        public_release_label="R-2020.09",
        private_fixed_argument_count=1,
        private_fixed_arguments_sha256="a" * 64,
        private_release_evidence_bytes=16,
        private_release_evidence_sha256="b" * 64,
        capability_sha256="c" * 64,
    )


def test_tcad_execution_context_projection_is_narrow_and_composes_with_design() -> None:
    catalog = _catalog()
    operation = catalog.operation(EXECUTION_CONTEXT_OPERATION)
    assert operation.spec.catalog_scope == "support"
    assert operation.spec.executor.kind == "transform"
    assert tuple(port.name for port in operation.spec.inputs) == ("capability",)
    assert tuple(port.name for port in operation.spec.outputs) == (
        "execution_context",
    )
    assert operation.spec.outputs[0].schema_id == "scidiscovery.execution-context.v1"

    snapshot = _solver_capability_snapshot()
    payload = snapshot.model_dump(mode="json")
    raw = json.dumps(payload, indent=2).encode("utf-8")
    capability = _invocation_artifact("capability", "tcad.solver-capability.v2")
    bound = preflight_operation(
        operation,
        name="execution_context",
        artifacts_by_port={"capability": (capability,)},
        instruction=None,
    )
    output = execute_compiled_transform(bound, {"capability": raw})[0]
    context = ExecutionContext.model_validate_json(output.content, strict=True)
    assert context == ExecutionContext(
        domain="tcad",
        implementation_backend="sprocess",
        implementation_kind="sprocess",
        release_label="R-2020.09",
        public_arguments=("-i",),
        capability_statements=None,
        limitations=None,
    )
    assert "private_" not in output.content.decode("utf-8")
    reordered = json.dumps(
        dict(reversed(tuple(payload.items()))), separators=(",", ":")
    ).encode("utf-8")
    assert execute_compiled_transform(bound, {"capability": reordered})[0].content == (
        output.content
    )

    foundation = _invocation_artifact(
        "foundation", "scidiscovery.scientific-foundation.v1"
    )
    objective = _invocation_artifact(
        "objective",
        "scidiscovery.research-objective.v1",
        parent_refs=(foundation.ref,),
    )
    portfolio = _invocation_artifact(
        "portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        parent_refs=(foundation.ref,),
    )
    critic = _invocation_artifact(
        "critic",
        "scidiscovery.critic-review.v2",
        parent_refs=(foundation.ref, portfolio.ref),
    )
    projected = InvocationArtifact(
        artifact_name="execution_context",
        ref=ArtifactRef(
            artifact_id="art_execution_context",
            sha256="d" * 64,
            kind="execution_context",
            schema_id="scidiscovery.execution-context.v1",
        ),
        schema_id="scidiscovery.execution-context.v1",
        media_type="application/json",
        size_bytes=len(output.content),
        parent_refs=(capability.ref,),
    )
    design = preflight_operation(
        catalog.operation("science.experiment.design.v1"),
        name="design",
        artifacts_by_port={
            "scientific_foundation": (foundation,),
            "research_objective": (objective,),
            "hypothesis_portfolio": (portfolio,),
            "critic_review": (critic,),
            "execution_context": (projected,),
            "current_progress": (),
            "experiment_results": (),
            "result_analysis": (),
        },
        instruction="Design one bounded experiment.",
    )
    assert next(
        item for item in design.inputs if item.port_name == "execution_context"
    ).artifact.ref == projected.ref


def test_tcad_execution_context_projection_rejects_non_snapshot_content() -> None:
    operation = _catalog().operation(EXECUTION_CONTEXT_OPERATION)
    capability = _invocation_artifact("capability", "tcad.solver-capability.v2")
    wrong_schema = _invocation_artifact("capability", "opaque")
    with pytest.raises(OperationInvocationError) as mismatch:
        preflight_operation(
            operation,
            name="execution_context",
            artifacts_by_port={"capability": (wrong_schema,)},
            instruction=None,
        )
    assert mismatch.value.reason_code == "input_schema_mismatch"
    bound = preflight_operation(
        operation,
        name="execution_context",
        artifacts_by_port={"capability": (capability,)},
        instruction=None,
    )
    invalid = {
        **_solver_capability_snapshot().model_dump(mode="json"),
        "undeclared": True,
    }
    with pytest.raises(OperationInvocationError) as error:
        execute_compiled_transform(
            bound, {"capability": json.dumps(invalid).encode("utf-8")}
        )
    assert error.value.reason_code == "executor_component_failed"


def test_root_projects_execution_context_idempotently_with_exact_parent(
    tmp_path, monkeypatch
) -> None:
    runtime, instance, root = _root(tmp_path)
    snapshot = _solver_capability_snapshot()
    raw = json.dumps(snapshot.model_dump(mode="json"), indent=2).encode("utf-8")
    capability = _register(
        runtime,
        instance,
        name="solver_capability",
        raw=raw,
        kind="solver_capability",
        schema="tcad.solver-capability.v2",
    )
    request = {
        "name": "execution_context",
        "operation_id": EXECUTION_CONTEXT_OPERATION,
        "inputs": [
            {"port": "capability", "artifact_names": ["solver_capability"]}
        ],
    }
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    first = root.call_tool("operation_invoke", request)
    assert root.call_tool("operation_invoke", request) == first
    output_name = first["result"]["outputs"][0]["artifact_name"]
    artifact_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=output_name,
    )
    envelope = runtime.artifacts.get_by_id(artifact_id)
    assert envelope.parent_refs == (capability.ref,)
    assert envelope.schema_id == "scidiscovery.execution-context.v1"
    context = ExecutionContext.model_validate_json(
        runtime.artifacts.read(envelope.ref), strict=True
    )
    assert context.domain == "tcad"
    assert context.implementation_backend == "sprocess"

    reordered_raw = json.dumps(
        dict(reversed(tuple(snapshot.model_dump(mode="json").items()))),
        separators=(",", ":"),
    ).encode("utf-8")
    reordered_capability = _register(
        runtime,
        instance,
        name="solver_capability_reordered",
        raw=reordered_raw,
        kind="solver_capability",
        schema="tcad.solver-capability.v2",
    )
    reordered_request = {
        "name": "execution_context_reordered",
        "operation_id": EXECUTION_CONTEXT_OPERATION,
        "inputs": [
            {
                "port": "capability",
                "artifact_names": ["solver_capability_reordered"],
            }
        ],
    }
    reordered_result = root.call_tool("operation_invoke", reordered_request)
    reordered_name = reordered_result["result"]["outputs"][0]["artifact_name"]
    reordered_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=reordered_name,
    )
    reordered_envelope = runtime.artifacts.get_by_id(reordered_id)
    assert reordered_envelope.parent_refs == (reordered_capability.ref,)
    assert reordered_envelope.ref != envelope.ref
    assert runtime.artifacts.read(reordered_envelope.ref) == runtime.artifacts.read(
        envelope.ref
    )

    foundation = _register(
        runtime,
        instance,
        name="design_foundation",
        raw=b"{}",
        kind="scientific_foundation",
        schema="scidiscovery.scientific-foundation.v1",
    )
    objective = _register(
        runtime,
        instance,
        name="design_objective",
        raw=b"{}",
        kind="research_objective",
        schema="scidiscovery.research-objective.v1",
        parents=(foundation.ref,),
    )
    portfolio = _register(
        runtime,
        instance,
        name="design_portfolio",
        raw=b"{}",
        kind="hypothesis_portfolio",
        schema="scidiscovery.hypothesis-proposal.v2",
        parents=(foundation.ref,),
    )
    critic = _register(
        runtime,
        instance,
        name="design_critic",
        raw=b"{}",
        kind="critic_review",
        schema="scidiscovery.critic-review.v2",
        parents=(foundation.ref, portfolio.ref),
    )
    monkeypatch.setattr(
        runtime.approvals,
        "are_subjects_approved_by_provider",
        lambda *args, **kwargs: True,
    )
    design_request = {
        "name": "design_with_execution_context",
        "operation_id": "science.experiment.design.v1",
        "inputs": [
            {
                "port": "scientific_foundation",
                "artifact_names": ["design_foundation"],
            },
            {
                "port": "research_objective",
                "artifact_names": ["design_objective"],
            },
            {
                "port": "hypothesis_portfolio",
                "artifact_names": ["design_portfolio"],
            },
            {
                "port": "critic_review",
                "artifact_names": ["design_critic"],
            },
            {
                "port": "execution_context",
                "artifact_names": [output_name],
            },
        ],
        "instruction": "Design one bounded experiment using the declared context.",
    }
    assert root.call_tool("operation_preflight", design_request)[
        "admissible"
    ] is True
    invoked = root.call_tool("operation_invoke", design_request)
    assert invoked["result"]["state"] == "queued"
    run_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="run",
        name="design_with_execution_context",
    )
    status = runtime.runs.status(run_id)
    bound_context = next(
        item for item in status.inputs if item.port_name == "execution_context"
    )
    assert bound_context.artifact_name == output_name


@pytest.mark.parametrize("raw, reason", (
    (b'{"objective_contract":null}', "input_required_field_missing"),
    (b'{}', "input_required_field_missing"),
    (b'[]', "input_content_invalid"),
    (b'{', "input_content_invalid"),
))
def test_declared_input_presence_fails_during_pure_preflight(raw, reason) -> None:
    operation = _catalog().operation(OBJECTIVE_PROJECT_OPERATION)
    artifact = _invocation_artifact("foundation", "scidiscovery.scientific-foundation.v1")
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(
            operation, name="objective", artifacts_by_port={"scientific_foundation": (artifact,)},
            instruction=None, read_artifact=lambda ref: raw,
        )
    assert error.value.reason_code == reason
    assert error.value.port == "scientific_foundation"


def test_objective_projection_preflight_and_invoke_reject_null_at_root(tmp_path) -> None:
    runtime, instance, root = _root(tmp_path)
    catalog = root.call_tool("operation_catalog", {"scope": "support"})
    operation = next(item for item in catalog["operations"] if item["operation_id"] == OBJECTIVE_PROJECT_OPERATION)
    assert operation["inputs"][0]["required_non_null_fields"] == ["objective_contract"]
    foundation = _intake().scientific_foundation
    assert foundation.objective_contract is None
    _register(runtime, instance, name="foundation", raw=foundation.canonical_json(),
              kind="scientific_foundation", schema="scidiscovery.scientific-foundation.v1")
    request = {
        "name": "objective", "operation_id": OBJECTIVE_PROJECT_OPERATION,
        "inputs": [{"port": "scientific_foundation", "artifact_names": ["foundation"]}],
    }
    def snapshot():
        values = {}
        for path in (runtime.state_root / "database").glob("*.sqlite3"):
            with sqlite3.connect(path) as connection:
                values[path.name] = tuple(connection.iterdump())
        return values

    before = snapshot()
    result = root.call_tool("operation_preflight", request)
    assert result["admissible"] is False
    assert result["reason_code"] == "input_required_field_missing"
    assert result["port"] == "scientific_foundation"
    with pytest.raises(RootToolError, match="input_required_field_missing"):
        root.call_tool("operation_invoke", request)
    assert snapshot() == before


def test_objective_projection_reads_exact_bound_content_and_preserves_objective() -> None:
    operation = _catalog().operation(OBJECTIVE_PROJECT_OPERATION)
    artifact = _invocation_artifact("foundation", "scidiscovery.scientific-foundation.v1")
    objective = {
        "objective_key": "bounded_objective", "intent": "mechanism_discrimination",
        "statement": "Separate the bounded mechanisms.",
        "closure_requirements": [{"requirement_key": "comparison", "description": "Compare the cases.",
                                  "requirement_type": "comparison_present", "comparison_purposes": ["mechanism_separation"]}],
    }
    payload = _intake().scientific_foundation.model_dump(mode="json")
    payload["objective"] = objective["statement"]
    payload["objective_contract"] = objective
    raw = canonical_json(payload)
    seen = []

    def read(ref):
        seen.append(ref)
        return raw

    with pytest.raises(OperationInvocationError, match="input_content_reader_missing"):
        preflight_operation(operation, name="objective", artifacts_by_port={"scientific_foundation": (artifact,)}, instruction=None)
    bound = preflight_operation(operation, name="objective", artifacts_by_port={"scientific_foundation": (artifact,)}, instruction=None, read_artifact=read)
    assert seen == [artifact.ref]
    outputs = execute_compiled_transform(bound, {"scientific_foundation": raw})
    assert json.loads(outputs[0].content)["objective_key"] == objective["objective_key"]
    assert json.loads(outputs[0].content)["statement"] == objective["statement"]


def test_parameter_uncertainty_projection_blocks_unbounded_and_preserves_bounded_tuning() -> None:
    requirement_payload = {
        "requirement_set_key": "projection_requirements",
        "title": "Projection requirements",
        "device_key": "projection_device",
        "objective": "Classify one exact parameter.",
        "parameters": [
            {
                "parameter_key": "control",
                "display_name": "Control",
                "category": "physics_model",
                "device_scope": "Fixture",
                "canonical_unit": "1",
                "criticality": "required",
                "minimum_independent_sources": 1,
                "allow_authoritative_single": True,
                "assumption_policy": "review_only_bounded_tuning",
                "agreement_rule": {"kind": "exact", "tolerance": None},
                "required_condition_names": [],
            }
        ],
    }
    requirements = DeviceParameterRequirementSet.model_validate_json(
        canonical_json(requirement_payload), strict=True
    )
    missing = DeviceParameterSet.model_validate_json(
        canonical_json(
            {
                "parameter_set_key": "missing_parameters",
                "requirement_set_key": "projection_requirements",
                "title": "Missing",
                "objective": "Show a blocking required parameter.",
                "claims": [],
            }
        ),
        strict=True,
    )
    missing_coverage = DeviceParameterCoverageReport.model_validate_json(
        canonical_json(
            {
                "requirement_set_key": "projection_requirements",
                "parameter_set_key": "missing_parameters",
                "source_catalog_key": "projection_sources",
                "status": "fail",
                "items": [
                    {
                        "parameter_key": "control",
                        "status": "missing",
                        "selected_value": None,
                        "canonical_unit": "1",
                        "independent_source_count": 0,
                        "comparisons": [],
                        "summary": "Required value is missing.",
                    }
                ],
                "confirmed_count": 0,
                "review_count": 0,
                "blocking_count": 1,
            }
        ),
        strict=True,
    )
    blocked = project_parameter_uncertainty(
        requirements, missing, missing_coverage
    )
    assert blocked.status == "blocking_unbounded"
    assert blocked.items[0].classification == "blocking_unbounded"

    tuned = DeviceParameterSet.model_validate_json(
        canonical_json(
            {
                "parameter_set_key": "bounded_parameters",
                "requirement_set_key": "projection_requirements",
                "title": "Bounded",
                "objective": "Retain an exact reviewed discrete set.",
                "claims": [
                    {
                        "parameter_key": "control",
                        "selected_value": "1e+0",
                        "unit": "1",
                        "conditions": [],
                        "epistemic_status": "assumption",
                        "observations": [],
                        "selection_rationale": "Reviewed bounded fixture.",
                        "tuning": {
                            "purpose": "calibration",
                            "basis": "engineering_prior",
                            "candidate_values": ["1e+0", "2e+0"],
                            "rationale": "Only these reviewed values are admissible.",
                        },
                    }
                ],
            }
        ),
        strict=True,
    )
    tuned_coverage = DeviceParameterCoverageReport.model_validate_json(
        canonical_json(
            {
                "requirement_set_key": "projection_requirements",
                "parameter_set_key": "bounded_parameters",
                "source_catalog_key": "projection_sources",
                "status": "review_required",
                "items": [
                    {
                        "parameter_key": "control",
                        "status": "assumed",
                        "selected_value": "1e+0",
                        "canonical_unit": "1",
                        "independent_source_count": 0,
                        "comparisons": [],
                        "summary": "Reviewed bounded assumption.",
                    }
                ],
                "confirmed_count": 0,
                "review_count": 1,
                "blocking_count": 0,
            }
        ),
        strict=True,
    )
    bounded = project_parameter_uncertainty(
        requirements, tuned, tuned_coverage
    )
    assert bounded.status == "ready"
    assert bounded.items[0].classification == "bounded_tunable"
    assert bounded.items[0].candidate_values == ("1e+0", "2e+0")


def test_optional_experiment_inputs_fail_closed_as_two_explicit_shapes() -> None:
    operation = _catalog().operation(EXPERIMENT_MATERIALIZE_OPERATION)
    assert operation.spec.input_admission is not None
    assert operation.spec.input_admission.member_ports == (
        "scientific_foundation",
        "research_objective",
        "hypothesis_portfolio",
        "critic_review",
    )
    intent = _invocation_artifact(
        "intent", "scidiscovery.experiment-design-intent.v1"
    )
    engineering = {
        "experiment_design_intent": (intent,),
        "scientific_foundation": (),
        "research_objective": (),
        "hypothesis_portfolio": (),
        "critic_review": (),
    }
    assert preflight_operation(
        operation,
        name="engineering",
        artifacts_by_port=engineering,
        instruction=None,
    ).compiled is operation
    objective = _invocation_artifact(
        "objective", "scidiscovery.research-objective.v1"
    )
    with pytest.raises(OperationInvocationError) as partial:
        preflight_operation(
            operation,
            name="partial_science",
            artifacts_by_port={**engineering, "research_objective": (objective,)},
            instruction=None,
        )
    assert partial.value.reason_code == "input_cohort_incomplete"
    assert partial.value.port == "scientific_foundation"

    portfolio = _invocation_artifact(
        "portfolio", "scidiscovery.hypothesis-proposal.v2"
    )
    foundation = _invocation_artifact(
        "foundation", "scidiscovery.scientific-foundation.v1"
    )
    objective = _invocation_artifact(
        "cohort_objective",
        "scidiscovery.research-objective.v1",
        parent_refs=(foundation.ref,),
    )
    portfolio = _invocation_artifact(
        "cohort_portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        parent_refs=(foundation.ref,),
    )
    critic = _invocation_artifact(
        "critic",
        "scidiscovery.critic-review.v2",
        parent_refs=(portfolio.ref, foundation.ref),
    )
    reviewed_intent = _invocation_artifact(
        "reviewed_intent",
        "scidiscovery.experiment-design-intent.v1",
        parent_refs=(foundation.ref, objective.ref, portfolio.ref, critic.ref),
    )
    scientific = {
        "experiment_design_intent": (reviewed_intent,),
        "scientific_foundation": (foundation,),
        "research_objective": (objective,),
        "hypothesis_portfolio": (portfolio,),
        "critic_review": (critic,),
    }
    assert preflight_operation(
        operation,
        name="reviewed_science",
        artifacts_by_port=scientific,
        instruction=None,
    ).compiled is operation

    unrelated_critic = _invocation_artifact(
        "unrelated_critic", "scidiscovery.critic-review.v2"
    )
    with pytest.raises(OperationInvocationError, match="guard_rejected"):
        preflight_operation(
            operation,
            name="unreviewed_science",
            artifacts_by_port={**scientific, "critic_review": (unrelated_critic,)},
            instruction=None,
        )


def test_experiment_design_rejects_mixed_foundation_cohorts() -> None:
    operation = _catalog().operation("science.experiment.design.v1")
    old_foundation = _invocation_artifact(
        "old_foundation", "scidiscovery.scientific-foundation.v1"
    )
    current_foundation = _invocation_artifact(
        "current_foundation", "scidiscovery.scientific-foundation.v1"
    )
    objective = _invocation_artifact(
        "current_objective",
        "scidiscovery.research-objective.v1",
        parent_refs=(current_foundation.ref,),
    )
    portfolio = _invocation_artifact(
        "old_portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        parent_refs=(old_foundation.ref,),
    )
    critic = _invocation_artifact(
        "mixed_critic",
        "scidiscovery.critic-review.v2",
        parent_refs=(portfolio.ref, current_foundation.ref),
    )
    bindings = {
        "scientific_foundation": (current_foundation,),
        "research_objective": (objective,),
        "hypothesis_portfolio": (portfolio,),
        "critic_review": (critic,),
        "execution_context": (),
        "current_progress": (),
        "experiment_results": (),
        "result_analysis": (),
    }
    with pytest.raises(OperationInvocationError, match="guard_rejected"):
        preflight_operation(
            operation,
            name="mixed_foundation_design",
            artifacts_by_port=bindings,
            instruction="Design one bounded discriminating experiment.",
        )

    exact_portfolio = _invocation_artifact(
        "current_portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        parent_refs=(current_foundation.ref,),
    )
    exact_critic = _invocation_artifact(
        "current_critic",
        "scidiscovery.critic-review.v2",
        parent_refs=(exact_portfolio.ref, current_foundation.ref),
    )
    accepted = preflight_operation(
        operation,
        name="exact_foundation_design",
        artifacts_by_port={
            **bindings,
            "hypothesis_portfolio": (exact_portfolio,),
            "critic_review": (exact_critic,),
        },
        instruction="Design one bounded discriminating experiment.",
    )
    assert accepted.compiled is operation


def test_wildcard_schema_is_limited_to_read_only_evidence_ports() -> None:
    catalog = _catalog()
    wildcard_ports = tuple(
        port
        for operation_id in catalog.operation_ids()
        for port in catalog.operation(operation_id).spec.inputs
        if port.schema_id == "*" or port.media_types == ("*/*",)
    )
    assert wildcard_ports
    assert all(
        port.exposure in {"handoff_only", "on_demand"}
        and port.usage == "evidence_inventory"
        for port in wildcard_ports
    )


def test_catalog_transform_split_is_idempotent_and_preserves_provisional_state(
    tmp_path,
) -> None:
    runtime, instance, root = _root(tmp_path)
    intake = _register(
        runtime,
        instance,
        name="scientific_intake",
        raw=_intake().canonical_json(),
        kind="scientific_intake",
        schema="scidiscovery.scientific-intake.v1",
        provisional=True,
    )
    audit = _register(
        runtime,
        instance,
        name="evidence_audit",
        raw=b"{}",
        kind="evidence_audit",
        schema="scidiscovery.evidence-audit.v1",
    )
    request = {
        "name": "problem_frame",
        "operation_id": INTAKE_SPLIT_OPERATION,
        "inputs": [
            {"port": "scientific_intake", "artifact_names": ["scientific_intake"]},
            {"port": "evidence_audit", "artifact_names": ["evidence_audit"]},
        ],
    }
    first = root.call_tool("operation_invoke", request)
    assert root.call_tool("operation_invoke", request) == first
    assert [item["output_label"] for item in first["result"]["outputs"]] == [
        "primary",
        "scientific_foundation",
    ]
    assert [item["artifact_name"] for item in first["result"]["outputs"]] == [
        "problem_frame",
        "problem_frame.scientific_foundation",
    ]
    for name in ("problem_frame", "problem_frame.scientific_foundation"):
        artifact_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id, namespace="artifact", name=name
        )
        envelope = runtime.artifacts.get_by_id(artifact_id)
        assert envelope.parent_refs == (intake.ref, audit.ref)
        assert envelope.labels["operation_id"] == INTAKE_SPLIT_OPERATION
        assert envelope.labels["scientific_claim_admissible"] == "false"
    with pytest.raises(RootToolError, match="unknown root tool"):
        root.call_tool(
            "artifact_transform",
            {
                "name": "legacy_split",
                "profile": "scidiscovery.scientific-intake-split.v1",
                "inputs": [
                    {
                        "source_name": "scientific_intake",
                        "artifact_name": "scientific_intake",
                    }
                ],
            },
        )
