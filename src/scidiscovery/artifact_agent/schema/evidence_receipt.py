"""Identity-free receipt for an unchanged, control-bound evidence set."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .structured_revision import RevisionTargetSchema, validate_json_pointer


class UnchangedEvidenceReceipt(SchemaModel):
    target_schema: RevisionTargetSchema
    evidence_source_labels: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=128)
    ]
    changed_paths: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    declarations_unchanged: Literal[True] = True

    @model_validator(mode="after")
    def _receipt_is_bounded(self) -> UnchangedEvidenceReceipt:
        if len(self.evidence_source_labels) != len(set(self.evidence_source_labels)):
            raise ValueError("evidence receipt source labels must be unique")
        if len(self.changed_paths) != len(set(self.changed_paths)):
            raise ValueError("evidence receipt changed paths must be unique")
        for path in self.changed_paths:
            validate_json_pointer(path)
        return self


def validate_unchanged_evidence_receipt(
    value: dict[str, object],
) -> dict[str, object]:
    return UnchangedEvidenceReceipt.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "UnchangedEvidenceReceipt",
    "validate_unchanged_evidence_receipt",
]
