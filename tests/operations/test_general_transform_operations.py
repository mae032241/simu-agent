from __future__ import annotations

import json

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
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
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    InvocationArtifact,
    OperationEngineeringError,
    OperationInvocationError,
    execute_compiled_transform,
    preflight_operation,
)


OBJECTIVE_PROJECT_OPERATION = "science.objective.project.v1"
GENERAL_TRANSFORM_OPERATION_IDS = {
    INTAKE_SPLIT_OPERATION,
    OBJECTIVE_PROJECT_OPERATION,
}


def test_materialize_maximum_legal_goals_and_current_selection_without_expansion() -> None:
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    from tests.operations.science_fixtures import _engineering_intent

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
    with pytest.raises(SemanticRuleViolation, match="source bound to this task"):
        _intake_source_context(
            payload,
            {"source_material": b"bounded source"},
            {},
        )


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
    with pytest.raises(OperationEngineeringError) as error:
        execute_compiled_transform(
            bound, {"capability": json.dumps(invalid).encode("utf-8")}
        )
    assert error.value.reason_code == "executor_component_failed"


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
        port.exposure in {"handoff_only", "on_demand", "material", "file_reference"}
        and port.usage == "evidence_inventory"
        for port in wildcard_ports
    )
