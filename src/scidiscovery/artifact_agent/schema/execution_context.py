"""Domain-neutral, declared execution context for experiment design."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import SchemaModel


Label = Annotated[str, Field(min_length=1, max_length=256)]
Statement = Annotated[str, Field(min_length=1, max_length=1024)]
Statements = Annotated[tuple[Statement, ...], Field(max_length=32)]


class ExecutionContext(SchemaModel):
    """Public declarations about one implementation environment."""

    schema_version: Literal[1] = 1
    domain: Label = Field(description="Domain that supplied this execution context.")
    implementation_backend: Label | None = Field(
        default=None,
        description="Declared backend name; null means the source did not declare one.",
    )
    implementation_kind: Label | None = Field(
        default=None,
        description="Declared implementation kind; null means it is unknown.",
    )
    release_label: Label | None = Field(
        default=None,
        description="Public release label; null means no release was declared.",
    )
    public_arguments: Annotated[tuple[str, ...], Field(max_length=256)] | None = Field(
        default=None,
        description=(
            "Declared public arguments; null means undeclared and an empty tuple means "
            "the source explicitly declared none."
        ),
    )
    capability_statements: Statements | None = Field(
        default=None,
        description="Declared capabilities; null means the source supplied none.",
    )
    limitations: Statements | None = Field(
        default=None,
        description="Declared limitations; null means the source supplied none.",
    )


__all__ = ["ExecutionContext"]
