from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentDesignIntent
from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
from scidiscovery.artifact_agent.schema.research_objective import (
    ObjectiveClosureRequirement,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_experiment_components import _experiment_context
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.general_science_resources import Resources
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import operation_port_json_schema, operation_primary_output
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.parameter_operations import ParameterEvidencePackage
from curve_figure_evidence.figure_science_operations import AUDIT_PROMPT as FIGURE_AUDIT_PROMPT


def _catalog():
    return compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )


def test_declared_output_relationship_reports_the_visible_rule_and_missing_field():
    from scidiscovery.artifact_agent.schema.layered_diagnosis import AnalysisSourceReference, CalculationRecord
    from scidiscovery.operation_contract import validation_diagnostics
    for model, raw, field in (
        (AnalysisSourceReference, dict(source_key='source', input_alias='raw', experiment_key='experiment'), 'case_key'),
        (CalculationRecord, dict(record_key='calculation', request={}, algorithm_version='v1', status='computed'), 'result'),
    ):
        schema = model.model_json_schema()
        with pytest.raises(ValidationError) as caught:
            model.model_validate_json(canonical_json(raw))
        details = validation_diagnostics(caught.value, schema=schema, phase='output_payload', action='submit')
        assert details[0]['path'] == '$.' + field
        assert details[0]['message'] in json.dumps(schema)


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


def test_audit_contracts_distinguish_fidelity_from_evidence_sufficiency() -> None:
    general = Resources.auditor_prompt
    semantic = Resources.evidence_audit_semantic_contract
    for text in (general, semantic, FIGURE_AUDIT_PROMPT):
        assert "忠实" in text or "faithful" in text
        assert "pass" in text
        assert "fail" in text
        assert "unknown" in text
        assert "not_applicable" in text
        assert "充分" in text or "sufficient" in text


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
                "objectives": ["Distinguish one bounded mechanism."],
                "current_objectives": ["Distinguish one bounded mechanism."],
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


@pytest.mark.parametrize('key', [None, 'legacy_display_key'])
def test_experiment_context_does_not_require_copying_global_key(experiment_case, key) -> None:
    intent, sources = experiment_case
    intent['objective_key'] = key
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    _experiment_context(intent, sources, {})
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    raw, _ = materialize_experiment_plan({
        'experiment_design_intent': canonical_json(intent),
        'research_objective': sources['research_objective'],
        'hypothesis_portfolio': sources['hypothesis_portfolio'],
    })
    assert json.loads(raw)['objective_key'] == json.loads(sources['research_objective'])['objective_key']


@pytest.mark.parametrize("model_kind,limit", (("intent", 16), ("proposal", 17)))
@pytest.mark.parametrize("field", ("objectives", "current_objectives"))
@pytest.mark.parametrize("defect", ("missing", "empty", "blank", "long", "too_many"))
def test_experiment_goal_lists_enforce_exact_bounds(
    experiment_case, model_kind, limit, field, defect,
) -> None:
    from scidiscovery.artifact_agent.schema.experiment import ExperimentProposal
    from scidiscovery.artifact_agent.schema.experiment_intent import (
        ExperimentProposalIntent, materialize_experiment_design_intent,
    )
    from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract

    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    if model_kind == "intent":
        model, proposal = ExperimentProposalIntent, intent["proposals"][0]
    else:
        plan = materialize_experiment_design_intent(
            ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True),
            ResearchObjectiveContract.model_validate_json(sources["research_objective"], strict=True),
        )
        model, proposal = ExperimentProposal, plan.proposals[0].model_dump(mode="json")
    if defect == "missing":
        proposal.pop(field)
    else:
        proposal[field] = {
            "empty": [], "blank": [""], "long": ["x" * 8193],
            "too_many": [f"goal {index}" for index in range((limit if field == "objectives" else 16) + 1)],
        }[defect]
    with pytest.raises(ValidationError):
        model.model_validate_json(canonical_json(proposal), strict=True)


def test_experiment_goal_subset_is_verbatim_and_python_uses_tuples(experiment_case) -> None:
    from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentProposalIntent

    intent, _ = experiment_case
    proposal = intent["proposals"][0]
    proposal.update(objectives=["  Exact goal\n"], current_objectives=["Exact goal"])
    with pytest.raises(ValidationError, match="exact subset"):
        ExperimentProposalIntent.model_validate_json(canonical_json(proposal), strict=True)
    proposal["current_objectives"] = list(proposal["objectives"])
    value = ExperimentProposalIntent.model_validate_json(canonical_json(proposal), strict=True)
    assert value.objectives == value.current_objectives == ("  Exact goal\n",)
    with pytest.raises(ValidationError, match="tuple"):
        ExperimentProposalIntent.model_validate(proposal, strict=True)


def _partial_experiment(experiment_case):
    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    objective = json.loads(sources["research_objective"])
    objective["mandatory_targets"] = [
        {"target_key": key, "observable": observable,
         "support_requirement": "complete_observation", "evidence_item_keys": [key],
         "rationale": "The original objective retains this obligation."}
        for key, observable in (("current_response", "response"), ("future_response", "future observable"))
    ]
    objective["closure_requirements"].append({
        "requirement_key": "all_targets", "requirement_type": "target_coverage",
        "description": "Overall closure still requires both targets.",
        "target_keys": ["current_response", "future_response"],
    })
    sources["research_objective"] = canonical_json(objective)
    proposal = intent["proposals"][0]
    proposal.update(objectives=["Test the response now.", "Test the future observable after evidence is available."],
                    current_objectives=["Test the response now."])
    proposal["value_assessment"]["rationale"] = (
        "The response comparison is sufficient for this bounded inference. "
        "Defer the future observable until its evidence is available; overall closure remains open."
    )
    return intent, sources


@pytest.mark.parametrize("global_already_present", (False, True))
def test_materialization_and_revision_preserve_goal_text_and_rationales(
    experiment_case, global_already_present,
) -> None:
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    from scidiscovery.general_science_experiment_components import _experiment_revision_context

    intent, inputs = _partial_experiment(experiment_case)
    global_objective = json.loads(inputs["research_objective"])["statement"]
    proposal = intent["proposals"][0]
    local_goals = ["  Current response\n", "Future response; requires additional evidence."]
    proposal["objectives"] = [local_goals[0], global_objective, local_goals[1]] if global_already_present else local_goals
    proposal["current_objectives"] = [local_goals[0]]
    proposal["value_assessment"]["rationale"] += "\n  Keep exact scientific wording."
    intent["priority_rationale"] = "  First resolve the response.\nThen reassess the evidence condition."
    args = {"experiment_design_intent": canonical_json(intent),
            "research_objective": inputs["research_objective"],
            "hypothesis_portfolio": inputs["hypothesis_portfolio"]}
    raw, report = materialize_experiment_plan(args)
    assert materialize_experiment_plan(args) == (raw, report)
    plan = ExperimentPortfolio.model_validate_json(raw, strict=True)
    assert plan.proposals[0].objectives == (global_objective, *local_goals)
    assert plan.proposals[0].current_objectives == (local_goals[0],)
    assert plan.proposals[0].value_assessment.rationale == proposal["value_assessment"]["rationale"]
    assert plan.priority_rationale == intent["priority_rationale"]
    assert len(plan.proposals[0].cases) == 2
    assert plan.proposals[0].required_observables == ("response",)
    assert ExperimentPortfolio.model_validate_json(plan.canonical_json(), strict=True) == plan
    revised = plan.model_dump(mode="json")
    revised["proposals"][0]["objectives"].append("Reassess a bounded follow-up after review.")
    sources = {"prior_draft": raw, "change_request": canonical_json({
        "review_target": "experiment_portfolio", "verdict": "revise",
        "summary": "Retain the condition for one later follow-up.",
    })}
    _experiment_revision_context(revised, sources, {})
    assert revised["proposals"][0]["value_assessment"]["rationale"] == proposal["value_assessment"]["rationale"]
    assert revised["priority_rationale"] == intent["priority_rationale"]
    revised["proposals"][0]["objectives"].remove(global_objective)
    ExperimentPortfolio.model_validate_json(canonical_json(revised), strict=True)
    _experiment_revision_context(revised, sources, {})


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
    proposal.update(objectives=[intent["engineering_objective"]],
                    current_objectives=[intent["engineering_objective"]],
                    hypothesis_keys=[], cases=proposal["cases"][:1],
                    baseline_case_key=None, variables=[],
                    identifiability_claims=[], prediction_tests=[])
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    return intent, sources


def test_experiment_context_does_not_reclassify_invalid_inputs() -> None:
    with pytest.raises(ValueError) as error:
        _experiment_context({}, {"critic_review": b"{}"}, {})
    assert not isinstance(error.value, SemanticRuleViolation)


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


@pytest.mark.parametrize(
    ("requirement_type", "fields", "accepted"),
    (
        (None, {"target_keys": ["target_a"]}, True),
        ("target_coverage", {"target_keys": ["target_a"]}, True),
        ("target_coverage", {}, False),
        (
            "target_coverage",
            {"target_keys": ["target_a"], "comparison_purposes": ["target_fit"]},
            False,
        ),
        ("comparison_present", {"comparison_purposes": ["target_fit"]}, True),
        (
            "comparison_present",
            {
                "target_keys": ["target_a"],
                "comparison_purposes": ["target_fit"],
            },
            True,
        ),
        ("comparison_present", {}, False),
        (
            "comparison_present",
            {
                "comparison_purposes": ["target_fit"],
                "validation_check_keys": ["check_a"],
            },
            False,
        ),
        (
            "validation_check_present",
            {"validation_check_keys": ["check_a"]},
            True,
        ),
        ("validation_check_present", {}, False),
        (
            "validation_check_present",
            {
                "validation_check_keys": ["check_a"],
                "target_keys": ["target_a"],
            },
            False,
        ),
        ("target_coverage", {"target_keys": ["target_a", "target_a"]}, True),
        (
            "comparison_present",
            {"comparison_purposes": ["target_fit", "target_fit"]},
            True,
        ),
        (
            "validation_check_present",
            {"validation_check_keys": ["check_a", "check_a"]},
            True,
        ),
    ),
)
def test_objective_closure_schema_matches_strict_model_acceptance(
    requirement_type, fields, accepted,
) -> None:
    from jsonschema.validators import validator_for

    payload = {
        "requirement_key": "closure_a",
        "description": "Close one bounded objective condition.",
        **fields,
    }
    if requirement_type is not None:
        payload["requirement_type"] = requirement_type

    try:
        ObjectiveClosureRequirement.model_validate_json(
            canonical_json(payload), strict=True
        )
        model_accepts = True
    except Exception:
        model_accepts = False

    direct_schema = ObjectiveClosureRequirement.model_json_schema(mode="validation")
    nested_schema = ScientificIntake.model_json_schema(mode="validation")["$defs"][
        "ObjectiveClosureRequirement"
    ]
    for schema in (direct_schema, nested_schema):
        validator_type = validator_for(schema)
        validator_type.check_schema(schema)
        schema_accepts = not tuple(validator_type(schema).iter_errors(payload))
        assert schema_accepts is accepted
    assert model_accepts is accepted


def test_evidence_source_projection_uses_exact_bound_context_aliases() -> None:
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
        "required_parameter_checklist",
        "source_material_001",
        "source_material_002",
    ]
    validation = schema["x-scidiscovery-validation-contract"]
    usages = {
        item["port"]: item["usage"] for item in validation["context_sources"]
    }
    assert usages == {
        "required_parameter_checklist": "evidence_inventory",
        "previous_evidence": "evidence_inventory",
        "source_material": "evidence_inventory",
        "user_context": "prior_signal",
    }


def test_empty_optional_inventory_still_allows_citing_the_bound_review_subject() -> None:
    compiled = _catalog().operation("science.evidence.audit.v1")
    port = operation_primary_output(compiled)
    static_schema = operation_port_json_schema(compiled, port)
    assert static_schema["properties"]["evidence"].get("maxItems") == 32

    bound_schema = operation_port_json_schema(
        compiled,
        port,
        input_source_ports={"scientific_foundation": "scientific_foundation"},
    )
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(bound_schema)
    payload = {"evidence": [{"source_key": "scientific_foundation", "source_type": "frozen_input", "locator": "/items/0"}]}
    validator.validate(payload)
    payload["evidence"][0]["source_key"] = "unbound_source"
    assert list(validator.iter_errors(payload))
