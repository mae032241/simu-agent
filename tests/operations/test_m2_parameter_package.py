"""Scientific parameter fixture and invariant retained after task consolidation."""
import pytest
from pydantic import ValidationError
from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.parameter_operations import ParameterEvidencePackage

def _package(source_key: str = "source_a") -> ParameterEvidencePackage:
    objective = "Validate one bounded TCAD parameter."
    return ParameterEvidencePackage.model_validate_json(
        canonical_json(
            {
                "scientific_intake": {
                    "problem_frame": {
                        "title": "Parameter frame",
                        "scientific_question": "Is the declared scale source-bound?",
                        "objective": objective,
                        "current_contradiction": "The scale is not yet frozen.",
                        "scope": "One dimensionless fixture parameter.",
                        "foundation_item_keys": ["parameter_fact"],
                        "observables": [
                            {
                                "observable_key": "scale",
                                "description": "The declared fixture scale.",
                                "role": "target",
                                "foundation_item_keys": ["parameter_fact"],
                                "acceptance_relevance": "It fixes the bounded input.",
                            }
                        ],
                        "claim_boundary": {
                            "allowed_claim": "Only the frozen scale is supported.",
                            "required_conditions": ["The exact source remains bound."],
                        },
                        "stop_conditions": ["Stop after deterministic expansion."],
                    },
                    "scientific_foundation": {
                        "title": "Parameter foundation",
                        "objective": objective,
                        "summary": "One user source declares the scale.",
                        "evidence": [
                            {
                                "source_key": source_key,
                                "source_type": "frozen_input",
                                "title": "Frozen source A",
                                "locator": f"{source_key}:line-1",
                            }
                        ],
                        "items": [
                            {
                                "item_key": "parameter_fact",
                                "item_type": "parameter",
                                "epistemic_status": "user_defined",
                                "statement": "The fixture scale is one.",
                                "value": "1e+0",
                                "unit": "1",
                                "scope": "The bounded fixture only.",
                                "evidence_keys": [source_key],
                            }
                        ],
                    },
                },
                "parameter_requirements": {
                    "requirement_set_key": "fixture_requirements",
                    "title": "Fixture requirements",
                    "device_key": "fixture_device",
                    "objective": objective,
                    "parameters": [
                        {
                            "parameter_key": "scale",
                            "display_name": "Scale",
                            "category": "geometry",
                            "device_scope": "Fixture",
                            "canonical_unit": "1",
                            "criticality": "required",
                            "minimum_independent_sources": 1,
                            "allow_authoritative_single": True,
                            "assumption_policy": "forbidden",
                            "agreement_rule": {"kind": "exact"},
                            "required_condition_names": [],
                        }
                    ],
                },
                "device_parameters": {
                    "parameter_set_key": "fixture_parameters",
                    "requirement_set_key": "fixture_requirements",
                    "title": "Fixture parameters",
                    "objective": objective,
                    "claims": [
                        {
                            "parameter_key": "scale",
                            "selected_value": "1e+0",
                            "unit": "1",
                            "conditions": [],
                            "epistemic_status": "user_defined",
                            "observations": [
                                {
                                    "source_key": source_key,
                                    "reported_value": "1e+0",
                                    "reported_unit": "1",
                                    "conditions": [],
                                    "locator": f"{source_key}:line-1",
                                    "evidence_mode": "direct_report",
                                }
                            ],
                            "selection_rationale": "Use the exact frozen declaration.",
                        }
                    ],
                },
                "source_catalog": {
                    "catalog_key": "fixture_sources",
                    "sources": [
                        {
                            "source_key": source_key,
                            "source_type": "frozen_input",
                            "title": "Frozen source A",
                            "source_class": "user_source",
                            "work_key": f"user:{source_key}",
                        }
                    ],
                },
            }
        ),
        strict=True,
    )

def test_parameter_package_rejects_cross_object_objective_drift() -> None:
    raw = _package().model_dump(mode="json")
    raw["device_parameters"]["objective"] = "A different objective."

    with pytest.raises(ValidationError, match="one exact objective"):
        ParameterEvidencePackage.model_validate_json(canonical_json(raw), strict=True)
