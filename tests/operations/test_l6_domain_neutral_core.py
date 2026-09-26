from __future__ import annotations

import json

from pydantic import TypeAdapter

from scidiscovery.artifact_agent.schema.comparison import (
    RealizationSnapshot,
    RealizedValue,
    evaluate_control_equivalence,
)
from scidiscovery.artifact_agent.schema.experiment import (
    CaseExpectation,
    ComparisonContract,
    ComparisonVariable,
    IdentifiabilityClaim,
)
from scidiscovery.artifact_agent.schema.research_cycle import (
    ArtifactKind,
)
def test_core_scientific_kinds_accept_plugin_identifiers() -> None:
    assert TypeAdapter(ArtifactKind).validate_python(
        "protein_sequence_review", strict=True
    ) == "protein_sequence_review"
    schemas = json.dumps(
        {
            "artifact_kind": TypeAdapter(ArtifactKind).json_schema(),
        },
        sort_keys=True,
    ).lower()
    assert "deck" not in schemas
    assert "tcad" not in schemas


def test_reviewed_equivalence_is_domain_neutral() -> None:
    variable = ComparisonVariable(
        variable_key="sample_identity",
        scientific_path="/sample/identity",
        factor_type="physical",
        comparison_role="frozen",
        unit="dimensionless",
        expectations=(
            CaseExpectation(case_key="baseline", value="same sample"),
            CaseExpectation(case_key="comparison", value="same sample"),
        ),
        equivalence_rule="reviewed",
        rationale="Identity is established by an independent domain review.",
    )
    contract = ComparisonContract(
        baseline_case_key="baseline",
        comparison_case_keys=("comparison",),
        variables=(variable,),
        required_observables=("response",),
        identifiability_claims=(
            IdentifiabilityClaim(
                hypothesis_key="hypothesis_a",
                observable="response",
                distinguishing_outcome="The response differs between cases.",
                decision_rule="Compare the registered response.",
                ambiguity_conditions=("The sample identity is not established.",),
                smallest_resolving_control="Independently review sample identity.",
            ),
        ),
    )
    snapshots = tuple(
        RealizationSnapshot(
            case_key=case_key,
            values=(
                RealizedValue(
                    variable_key="sample_identity",
                    scientific_path="/sample/identity",
                    value=value,
                    unit="dimensionless",
                    source_locator=f"record:{case_key}",
                ),
            ),
            source_description=f"Registered {case_key} sample.",
            materialization_kind="historical_qualified",
            source_artifact_sha256s=(digest * 64,),
            capability_sha256="c" * 64,
        )
        for case_key, value, digest in (
            ("baseline", "sample A", "a"),
            ("comparison", "sample B", "b"),
        )
    )
    report = evaluate_control_equivalence(
        contract,
        snapshots,
        reviewed_variable_keys=frozenset({"sample_identity"}),
    )
    rationale = report.differences[0].rationale.lower()
    assert report.status == "pass"
    assert "independent review" in rationale
    assert "deck" not in rationale
    assert "tcad" not in rationale
