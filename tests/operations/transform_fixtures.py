"""Inputs for deterministic components without a Run or installed environment."""

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract
from scidiscovery.artifact_agent.schema.scientific_foundation import ScientificFoundation
from tests.operations.test_general_transform_operations import _intake


def _project_research_objective(raw: bytes) -> bytes:
    foundation = ScientificFoundation.model_validate_json(raw, strict=True)
    if foundation.objective_contract is None:
        raise ValueError("objective fixture requires an explicit objective contract")
    return foundation.objective_contract.canonical_json()


def _objective_fixture() -> tuple[ScientificIntake, bytes, bytes]:
    intake: ScientificIntake = _intake()
    objective_contract = ResearchObjectiveContract.model_validate_json(
        canonical_json(
            {
                "objective_key": "bounded_curve_reproduction",
                "intent": "external_reproduction",
                "statement": "Reproduce one bounded target curve.",
                "mandatory_targets": [
                    {
                        "target_key": "target_curve",
                        "observable": "profile",
                        "support_requirement": "complete_observation",
                        "evidence_item_keys": ["target"],
                        "rationale": "The supplied curve is the only target.",
                    }
                ],
                "closure_requirements": [
                    {
                        "requirement_key": "target_coverage",
                        "description": "Cover the frozen target.",
                        "requirement_type": "target_coverage",
                        "target_keys": ["target_curve"],
                    }
                ],
            }
        ),
        strict=True,
    )
    foundation = intake.scientific_foundation.model_copy(
        update={"objective_contract": objective_contract}
    ).canonical_json()
    objective = _project_research_objective(foundation)
    return intake, foundation, objective
