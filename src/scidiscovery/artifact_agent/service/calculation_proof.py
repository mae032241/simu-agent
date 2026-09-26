"""Private calculation receipts. Never a scientific schema or workspace artifact."""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import Field
from ..schema.common import SchemaModel, Identifier, ContractDiagnostic, canonical_json
from ..schema.layered_diagnosis import CalculationRecord

class CalculationAttemptReference(SchemaModel):
    manifest_alias: Identifier
    attempt_key: Identifier
    proof_kind: Literal["current", "recovery"] = "current"

class ControlledCalculationRecord(CalculationRecord):
    input_digests: Annotated[dict[str, str], Field(max_length=40)]
    attempt: CalculationAttemptReference | None = None
    diagnostics: tuple[ContractDiagnostic, ...] = Field(default=(), max_length=8)


def scientific_calculation(record):
    """Project this declared record; user science dictionaries are not filtered."""
    value = record.model_dump(mode="json", exclude={"input_digests", "attempt", "diagnostics"})
    result = value.get("result")
    if isinstance(result, dict):
        # These keys belong to the registered curve algorithms' identity envelope.
        if record.algorithm_version.startswith(("analysis-curve-", "tcad-")):
            for target in (result, result.get("metric_report"), result.get("localization")):
                if isinstance(target, dict):
                    for key in ("curve_bundle_sha256", "comparison_spec_sha256", "validation_plan_sha256"):
                        target.pop(key, None)
    return value


def controlled_calculation(raw, receipt):
    """Restore only the exact service-sealed receipt of these scientific bytes."""
    proof = receipt.get("metadata", {}).get("calculation_proof")
    if proof is None:
        raise ValueError("calculation has no sealed control proof")
    record = ControlledCalculationRecord.model_validate_json(canonical_json(proof))
    import json
    if canonical_json(scientific_calculation(record)) != canonical_json(json.loads(raw)):
        raise ValueError("calculation scientific material differs from its sealed proof")
    return record
