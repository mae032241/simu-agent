"""Authoring and materialization share the current validation-intent contract."""
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment_intent import (
    ExperimentDesignIntent,
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


@pytest.mark.parametrize("defect", ["legacy_only", "both", "missing", "different_experiment"])
def test_current_reader_rejects_legacy_validation_plan(experiment_case, defect):
    current, legacy = engineering_pair(experiment_case)
    proposal = legacy["proposals"][0]
    if defect == "both":
        proposal["validation_intent"] = current["proposals"][0]["validation_intent"]
    elif defect == "missing":
        proposal.pop("validation_plan")
    elif defect == "different_experiment":
        proposal["validation_plan"]["experiment_key"] = "different_experiment"
    with pytest.raises(ValidationError):
        ExperimentDesignIntent.model_validate_json(canonical_json(legacy), strict=True)
