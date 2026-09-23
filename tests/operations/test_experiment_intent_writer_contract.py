"""New authoring contracts exclude legacy input-only validation plans."""
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment_intent import (
    ExperimentDesignIntent,
    HistoricalExperimentDesignIntent,
    materialize_experiment_design_intent,
)
from scidiscovery.operations.spec import json_projection
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _catalog, _experiment_envelope, _experiment_run, _partial_experiment,
)
from tests.operations.test_general_transform_operations import _register, _root


def engineering_pair(experiment_case):
    current, _ = deepcopy(experiment_case)
    current.update(study_kind="engineering", objective_key=None,
                   engineering_objective="Check the bounded fixture.", selected_hypothesis_keys=[])
    for proposal in current["proposals"]:
        proposal["hypothesis_keys"] = []
        proposal["prediction_tests"] = []
        proposal["identifiability_claims"] = []
    portfolio = materialize_experiment_design_intent(
        ExperimentDesignIntent.model_validate_json(canonical_json(current), strict=True), None)
    historical = deepcopy(current)
    for proposal, validation in zip(historical["proposals"], portfolio.validation_plans, strict=True):
        proposal.pop("validation_intent")
        proposal["validation_plan"] = validation.model_dump(mode="json")
    return current, historical


def test_worker_schema_shows_only_submit_ready_validation_and_repair_stays_in_run(tmp_path, experiment_case):
    current, sources = _partial_experiment(experiment_case)
    compiled = _catalog().operation("science.experiment.design.v1")
    schema = json_projection(compiled.output_contracts["experiment_design_intent"])
    proposal = schema["$defs"]["ExperimentProposalIntent"]
    assert "validation_plan" not in proposal["properties"]
    assert "validation_intent" in proposal["required"]
    assert "ValidationPlan" not in schema["$defs"]
    assert not any(name.startswith("Historical") for name in schema["$defs"])
    validator = Draft202012Validator(schema)
    validator.validate(current)
    _, legacy = engineering_pair(experiment_case)
    assert list(validator.iter_errors(legacy))

    runtime, run_id, output = _experiment_run(tmp_path, sources)
    invalid = deepcopy(current)
    invalid["proposals"][0].pop("validation_intent")
    invalid["proposals"][0]["validation_plan"] = legacy["proposals"][0]["validation_plan"]
    output.write_bytes(_experiment_envelope(invalid))
    state, diagnostics = runtime.runs.submit(run_id)
    assert state == "rejected" and runtime.runs.status(run_id).state == "running"
    assert any("validation_intent" in item["path"] or "validation_plan" in item["path"] for item in diagnostics)
    output.write_bytes(_experiment_envelope(current))
    assert runtime.runs.submit(run_id) == ("completed", ())


def test_historical_input_contract_and_root_materialization_preserve_old_record(tmp_path, experiment_case):
    current, legacy = engineering_pair(experiment_case)
    compiled = _catalog().operation("science.experiment.materialize.v1")
    port = next(p for p in compiled.spec.inputs if p.name == "experiment_design_intent")
    resource = compiled.implementations[f"{port.schema_resource.plugin_id or compiled.plugin_id}:{port.schema_resource.component_id}"]
    validator = Draft202012Validator(json.loads(resource))
    validator.validate(legacy)
    validator.validate(current)
    old_model = HistoricalExperimentDesignIntent.model_validate_json(canonical_json(legacy), strict=True)
    new_model = ExperimentDesignIntent.model_validate_json(canonical_json(current), strict=True)
    assert materialize_experiment_design_intent(old_model, None) == materialize_experiment_design_intent(new_model, None)

    runtime, instance, root = _root(tmp_path)
    original = canonical_json(legacy)
    record = _register(runtime, instance, name="historical_intent", raw=original,
                       kind="experiment_design_intent", schema="scidiscovery.experiment-design-intent.v1")
    request = {"operation_id": compiled.spec.operation_id, "name": "materialized_history",
               "inputs": [{"port": "experiment_design_intent", "artifact_names": ["historical_intent"]}]}
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    result = root.call_tool("operation_invoke", request)
    assert result["executor_kind"] == "transform"
    assert root.call_tool("operation_invoke", request) == result
    assert runtime.artifacts.read(record.ref) == original


@pytest.mark.parametrize("defect", ["both", "missing", "different_experiment"])
def test_historical_reader_does_not_weaken_existing_validation(experiment_case, defect):
    current, legacy = engineering_pair(experiment_case)
    proposal = legacy["proposals"][0]
    if defect == "both":
        proposal["validation_intent"] = current["proposals"][0]["validation_intent"]
    elif defect == "missing":
        proposal.pop("validation_plan")
    else:
        proposal["validation_plan"]["experiment_key"] = "different_experiment"
    with pytest.raises(ValidationError):
        HistoricalExperimentDesignIntent.model_validate_json(canonical_json(legacy), strict=True)


def test_scientific_skeleton_is_separate_from_concrete_plan(experiment_case):
    from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentScientificSkeleton
    from scidiscovery.general_science_experiment_components import _skeleton_context, _object_review_inputs
    from scidiscovery.operations.input_validation import OperationInvocationError
    skeleton = {name: ["A bounded scientific condition with its evidence basis."] for name in (
        "current_objectives", "competing_explanations_and_controls", "changed_conditions",
        "held_conditions", "observables", "discrimination_criteria_and_basis",
        "immutable_conditions", "stop_conditions")}
    skeleton["selected_hypothesis_keys"] = ["hypothesis_a"]
    raw = canonical_json(skeleton)
    ExperimentScientificSkeleton.model_validate_json(raw, strict=True)
    _, sources = experiment_case
    _skeleton_context(skeleton, sources, {})
    _object_review_inputs({"scientific_skeleton": raw})
    with pytest.raises(OperationInvocationError, match="input_review_subject_exact_one"):
        _object_review_inputs({"scientific_skeleton": raw, "experiment_plan": b"{}"})
    with pytest.raises(OperationInvocationError, match="input_review_subject_exact_one"):
        _object_review_inputs({})
    compiled = _catalog().operation("science.experiment.skeleton.v1")
    assert compiled.spec.review is None
    assert len([p for p in compiled.spec.outputs if p.collection is None]) == 1
    contract = json_projection(compiled.output_contracts["scientific_skeleton"])
    assert not {"cases", "validation_plan", "raw_outputs"} & set(contract["properties"])
    assert "experiment_plan" not in {p.name for p in compiled.spec.inputs}
    with pytest.raises(ValidationError):
        ExperimentScientificSkeleton.model_validate_json(canonical_json({**skeleton, "cases": []}), strict=True)
