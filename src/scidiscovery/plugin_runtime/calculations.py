"""Scientific calculation values and narrow capabilities for domain algorithms."""
from __future__ import annotations
from typing import Annotated, Protocol
from pydantic import Field
from ..artifact_agent.schema.common import ContractDiagnostic
from ..artifact_agent.schema.layered_diagnosis import CalculationRecord
from ..operation_contract import declared_violation

__all__ = ["CalculationResult", "CalculationTools", "CalculationEvidence",
    "analysis_source_claims", "analysis_evidence_aliases"]

class CalculationResult(CalculationRecord):
    """Algorithm result with exact input hashes; contains no receipt or attempts."""
    input_digests: Annotated[dict[str, str], Field(max_length=40)]
    diagnostics: tuple[ContractDiagnostic, ...] = Field(default=(), max_length=8)

class CalculationTools(Protocol):
    def complete_calculation(self, record: CalculationResult, *, diagnostics=(), summary=False) -> dict: ...
    def publish_analysis_file(self, raw: bytes, *, media_type, kind, sources, suffix, metadata=None) -> dict: ...

    def publish_calculation_checkpoint(self, raw: bytes, *, algorithm_version: str, record_key: str, sources: tuple[str, ...], numerical_identity: list) -> dict: ...
    def read_calculation_checkpoint(self, alias: str, *, algorithm_version: str, tool_names: tuple[str, ...], sources: tuple[str, ...], max_bytes: int) -> tuple[bytes, list]: ...

class CalculationEvidence(Protocol):
    def verified_calculations(self, report) -> tuple[CalculationResult, ...]: ...

def analysis_source_claims(source_key, locator, input_alias, sources, calculation_aliases=None):
    """Use the same source identities for validation and mechanical completion."""
    claims = {source_key} if source_key in sources else set()
    if input_alias is not None:
        claims.add(input_alias)
    if locator.split(":", 1)[0] in sources:
        claims.add(locator.split(":", 1)[0])
    aliases = calculation_aliases or {}
    return {aliases.get(claim, claim) for claim in claims}

def analysis_evidence_aliases(evidence, references, sources, calculation_aliases=None):
    """Resolve optional citations without letting a generated mapping hide a conflict."""
    resolved = {}
    for index, reference in enumerate(references):
        claims = analysis_source_claims(reference.source_key, "", reference.input_alias, sources, calculation_aliases)
        claims.update(resolved.get(reference.source_key, ()))
        if len(claims) != 1:
            raise declared_violation("analysis source key has conflicting source mappings",
                path=f"$.source_references[{index}].source_key")
        resolved[reference.source_key] = claims
    for index, item in enumerate(evidence):
        claims = analysis_source_claims(item.source_key, item.locator, None, sources, calculation_aliases)
        claims.update(resolved.get(item.source_key, ()))
        if len(claims) > 1:
            raise declared_violation("analysis source key has conflicting source mappings",
                path=f"$.evidence[{index}].source_key")
        resolved[item.source_key] = claims
    return {key: next(iter(claims)) if claims else key for key, claims in resolved.items()}
