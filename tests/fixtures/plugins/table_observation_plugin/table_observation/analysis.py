"""Bounded deterministic CSV structure and numeric summaries."""

from __future__ import annotations

import csv
import hashlib
import io
import math
from typing import Annotated

from pydantic import Field, model_validator

from scidiscovery.artifact_agent.schema.common import Identifier, SchemaModel


class NumericColumnSummary(SchemaModel):
    column: Annotated[str, Field(min_length=1, max_length=256)]
    count: Annotated[int, Field(ge=1, le=100_000)]
    minimum: float
    maximum: float
    mean: float


class TableStructureSummary(SchemaModel):
    table_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    rows: Annotated[int, Field(ge=1, le=100_000)]
    columns: Annotated[tuple[str, ...], Field(min_length=1, max_length=128)]
    numeric_columns: Annotated[
        tuple[NumericColumnSummary, ...], Field(max_length=128)
    ] = ()


class TableObservation(SchemaModel):
    experiment_key: Identifier
    structure: TableStructureSummary
    finding: Annotated[str, Field(min_length=1, max_length=8192)]
    limitations: Annotated[tuple[str, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _limitations_are_unique(self) -> TableObservation:
        if len(self.limitations) != len(set(self.limitations)):
            raise ValueError("table observation limitations must be unique")
        return self


def summarize_csv(raw: bytes) -> TableStructureSummary:
    if not raw or len(raw) > 16 * 1024 * 1024:
        raise ValueError("table input is empty or exceeds 16 MiB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("table input must be UTF-8 CSV") from error
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration as error:
        raise ValueError("table input requires a header") from error
    columns = tuple(item.strip() for item in header)
    if not columns or len(columns) > 128 or any(not item for item in columns):
        raise ValueError("table header is empty or invalid")
    if len(columns) != len(set(columns)):
        raise ValueError("table columns must be unique")
    rows: list[tuple[str, ...]] = []
    for row in reader:
        if len(row) != len(columns):
            raise ValueError("table rows must match the header width")
        rows.append(tuple(item.strip() for item in row))
        if len(rows) > 100_000:
            raise ValueError("table exceeds 100000 rows")
    if not rows:
        raise ValueError("table requires at least one data row")
    numeric: list[NumericColumnSummary] = []
    for index, column in enumerate(columns):
        values: list[float] = []
        for row in rows:
            if row[index] == "":
                continue
            try:
                value = float(row[index])
            except ValueError:
                values = []
                break
            if not math.isfinite(value):
                raise ValueError("numeric table values must be finite")
            values.append(value)
        if values:
            numeric.append(
                NumericColumnSummary(
                    column=column,
                    count=len(values),
                    minimum=min(values),
                    maximum=max(values),
                    mean=sum(values) / len(values),
                )
            )
    return TableStructureSummary(
        table_sha256=hashlib.sha256(raw).hexdigest(),
        rows=len(rows),
        columns=columns,
        numeric_columns=tuple(numeric),
    )


__all__ = [
    "NumericColumnSummary",
    "TableObservation",
    "TableStructureSummary",
    "summarize_csv",
]
