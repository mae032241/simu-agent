"""Blind CSV data models, deterministic analysis, and contextual checks."""

from __future__ import annotations

import csv
import hashlib
import io
import math
from typing import Annotated, Any, Literal

from pydantic import Field

from scidiscovery.artifact_agent.schema.common import SchemaModel, canonical_json
from scidiscovery.operation_declaration import payload_validator, schema_resource
from scidiscovery.operation_contract import SemanticRuleViolation


CSV_SCHEMA_PROBE = "schema-read-only:7d1c6e51d08f4b32"


class CsvStructure(SchemaModel):
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    row_count: Annotated[int, Field(ge=1, le=10_000)]
    columns: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    numeric_means: dict[str, float]


class CsvObservation(SchemaModel):
    schema_probe: Literal["schema-read-only:7d1c6e51d08f4b32"]
    structure: CsvStructure
    interpretation: Annotated[str, Field(min_length=1, max_length=4096)]
    limitations: Annotated[tuple[str, ...], Field(max_length=16)] = ()


class CsvReview(SchemaModel):
    subject_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    verdict: Literal["pass", "revise", "inconclusive"]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


def summarize_csv(raw: bytes) -> CsvStructure:
    if not raw or len(raw) > 2 * 1024 * 1024:
        raise ValueError("CSV input is empty or too large")
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("CSV input must be valid UTF-8") from error
    if len(rows) < 2 or len(rows) > 10_001:
        raise ValueError("CSV requires a header and 1..10000 rows")
    columns = tuple(item.strip() for item in rows[0])
    if not columns or len(columns) > 64 or any(not item for item in columns):
        raise ValueError("CSV header is invalid")
    if len(columns) != len(set(columns)):
        raise ValueError("CSV columns must be unique")
    body = rows[1:]
    if any(len(row) != len(columns) for row in body):
        raise ValueError("CSV row width differs from the header")
    means: dict[str, float] = {}
    for index, column in enumerate(columns):
        try:
            values = [float(row[index]) for row in body if row[index].strip()]
        except ValueError:
            continue
        if values and all(math.isfinite(value) for value in values):
            means[column] = sum(values) / len(values)
    return CsvStructure(
        source_sha256=hashlib.sha256(raw).hexdigest(),
        row_count=len(body),
        columns=columns,
        numeric_means=means,
    )


def validate_observation_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    observation = CsvObservation.model_validate_json(canonical_json(payload), strict=True)
    if observation.structure != summarize_csv(sources["source_table"]):
        raise SemanticRuleViolation("observation structure differs from the exact CSV")
    if handoff.get("verdict") not in {"pass", "inconclusive"}:
        raise SemanticRuleViolation("observation handoff is inconsistent")


def validate_review_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    review = CsvReview.model_validate_json(canonical_json(payload), strict=True)
    subject = sources["csv_observation"]
    observation = CsvObservation.model_validate_json(subject, strict=True)
    if observation.structure != summarize_csv(sources["source_table"]):
        raise SemanticRuleViolation("review subject differs from the exact CSV")
    if review.subject_sha256 != hashlib.sha256(subject).hexdigest():
        raise SemanticRuleViolation("review does not bind the exact observation")
    expected = "blocked" if review.verdict == "revise" else review.verdict
    if handoff.get("verdict") != expected:
        raise SemanticRuleViolation("review handoff differs from the review verdict")


OBSERVATION_SCHEMA = schema_resource(CsvObservation, "blind.csv-observation.v1")
REVIEW_SCHEMA = schema_resource(CsvReview, "blind.csv-review.v1")
OBSERVATION_VALIDATOR = payload_validator(
    lambda value: CsvObservation.model_validate_json(canonical_json(value), strict=True)
)
REVIEW_VALIDATOR = payload_validator(
    lambda value: CsvReview.model_validate_json(canonical_json(value), strict=True)
)


__all__ = [
    "CSV_SCHEMA_PROBE",
    "CsvObservation",
    "CsvReview",
    "OBSERVATION_SCHEMA",
    "OBSERVATION_VALIDATOR",
    "REVIEW_SCHEMA",
    "REVIEW_VALIDATOR",
    "summarize_csv",
    "validate_observation_context",
    "validate_review_context",
]
