"""Uniform worker result envelope shared by every scientific role."""

from __future__ import annotations

import re

from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import Identifier, canonical_json


class FormModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
    )


class SourceReference(FormModel):
    source_key: Identifier
    source_type: Literal["frozen_input", "web_snapshot", "user_statement", "runtime_output", "inference"]
    locator: Annotated[str, Field(min_length=1, max_length=2048,
        description="Exact input locator. Boundary citations use 'text' for full text or a heading/section hint for plain text; hints remain unlocated even when the quote matches elsewhere. An explicit / JSON Pointer selects only that value and never falls back to whole-source search.")]


class BoundaryReference(FormModel):
    source_key: Identifier | None = Field(default=None,
        description="Exact frozen input source_name; omit for a declaration in this result. Never supply an Artifact ID or hash.")
    boundary_key: Identifier


class BoundaryCitation(FormModel):
    source: SourceReference
    quote: Annotated[str, Field(min_length=1, max_length=2048)] | None = Field(default=None,
        description="Exact necessary source text, when useful. Without a quote no quoted-byte match is established. Matching proves bytes in the reported search scope only, never interpretation or user authorization, nor a unique location unless multiplicity is checked.")


class BoundaryDeclaration(FormModel):
    boundary_key: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=2048)]
    evidence: Annotated[tuple[BoundaryCitation, ...], Field(max_length=8)] = ()
    interpretation: Annotated[str, Field(min_length=1, max_length=2048)]
    hypothesis_key: Identifier | None = None
    parameter_name: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    revises: Annotated[tuple[BoundaryReference, ...], Field(max_length=8)] = ()


class RoleHandoff(FormModel):
    verdict: Literal["pass", "revise", "blocked", "inconclusive"]
    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    assumptions: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    next_actions: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    boundary_references: Annotated[tuple[BoundaryReference, ...], Field(max_length=32)] = ()


PayloadT = TypeVar("PayloadT")


class RoleResultEnvelope(FormModel, Generic[PayloadT]):
    schema_version: Literal[1]
    handoff: RoleHandoff
    payload: PayloadT
    boundary_declarations: Annotated[tuple[BoundaryDeclaration, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _unique_boundary_keys(self):
        keys = [item.boundary_key for item in self.boundary_declarations]
        if len(keys) != len(set(keys)):
            raise ValueError("boundary_key values must be unique within this result")
        return self

    def canonical_json(self) -> bytes:
        return canonical_json(self.model_dump(mode="json"))


def parse_role_result(value: Any) -> RoleResultEnvelope[Any]:
    return RoleResultEnvelope[Any].model_validate_json(
        canonical_json(value), strict=True
    )


def role_result_json_schema(payload_model: type[BaseModel]) -> dict[str, Any]:
    return RoleResultEnvelope[payload_model].model_json_schema(mode="validation")


BOUNDARY_GUIDANCE = """
Boundary declarations separate claim origin from applicability. Use optional
boundary_declarations for your statement, exact SourceReference with a necessary
quote, and your interpretation; associate existing hypothesis_key/parameter.name
when relevant. A verbatim original excerpt may be the statement; put inferred
meaning and applicability in interpretation. Even statement == quote can repeat
an example or a reported view rather than a hard constraint: read the original context.
Use handoff.boundary_references to cite declaration keys in this
result or an exact frozen input source_name, without repeating the declaration list.
Control supplies producer identity, exact frozen references and location checks.
Source-location and quoted-byte checks are separate. An absent quote is not matched;
a short or complete matched quote proves only those bytes in the reported search scope, never the interpretation's
truth or user authorization. A stronger interpretation remains the owner's claim,
including when the source is original user text. Scientific material repeating user
words does not become original user text. Unverified citations or unresolved
references cannot weaken existing assigned H boundaries or grant permissions.
For frozen plain/Markdown text, a heading is only a hint: its location may remain
unverified while the exact quote matches the full source_text. quote_match_scope
describes the searched text or selected JSON value; quote_match_multiplicity marks
unique/multiple occurrences within that space, not semantic authority or a new locator.
An explicit / JSON Pointer never falls back to full-text search. Read relevant
original context for an ambiguous quote; a matched quote alone does not prove coverage.
Read complete sealed declarations through input scientific_view or
worker_reference_read(view="boundaries"); follow returned continuation. This is
separate from original payload pointers. Keep assumptions/missing_inputs as strings.
Unassociated or omitted original scope/basis stays attributed to its producer and source-unverified; this directory does not exhaust all boundary prose.
"""

# A compiled role prompt may carry its complete detailed rules after this
# marker. The frozen assignment keeps every byte; a current startup delivers
# the core checklist and serves each named section on demand, once.
REFERENCE_MARKER = "\n[[on-demand reference]]\n"
_SECTION = re.compile(r"^## ([a-z][a-z0-9_]*)\n", re.MULTILINE)


def reference_sections(text: str, anchors: tuple[tuple[str, str], ...], *, remove: tuple[str, ...] = ()) -> dict[str, str]:
    """Split one existing prompt at exact anchor phrases; every byte is assigned once."""
    for sentence in remove:
        if text.count(sentence) != 1:
            raise ValueError(f"reference removal is not unique: {sentence[:40]!r}")
        text = text.replace(sentence, "")
    positions = []
    for name, anchor in anchors:
        if text.count(anchor) != 1:
            raise ValueError(f"reference anchor is not unique: {name}")
        positions.append(text.index(anchor))
    if positions != sorted(positions) or text[:positions[0]].strip():
        raise ValueError("reference anchors must cover the text in order")
    bounds = positions + [len(text)]
    return {name: text[bounds[i]:bounds[i + 1]].strip() for i, (name, _) in enumerate(anchors)}


def with_reference(core: str, sections: dict[str, str]) -> str:
    return core.rstrip() + "\n" + REFERENCE_MARKER + "".join(
        f"## {name}\n{body.strip()}\n\n" for name, body in sections.items())


def split_reference(text: str) -> tuple[str, dict[str, str] | None]:
    if text.count(REFERENCE_MARKER) != 1:
        return text, None
    core, reference = text.split(REFERENCE_MARKER)
    parts = _SECTION.split(reference)
    if parts[0].strip() or len(parts) < 3:
        return text, None
    sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
    return core.rstrip() + "\n", sections


__all__ = [
    "FormModel",
    "RoleHandoff",
    "RoleResultEnvelope",
    "parse_role_result",
    "role_result_json_schema",
]
