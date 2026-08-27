"""Bounded, identity-free JSON revisions for immutable scientific objects."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .common import SchemaModel, canonical_json


RevisionTargetSchema = Literal[
    "scidiscovery.scientific-intake.v1",
    "scidiscovery.scientific-foundation.v1",
    "scidiscovery.hypothesis-proposal.v1",
    "scidiscovery.hypothesis-portfolio.v1",
    "scidiscovery.experiment-portfolio.v1",
]
JsonPointer = Annotated[str, Field(min_length=2, max_length=1024)]


class StructuredRevisionOperation(SchemaModel):
    operation: Literal["add", "replace", "remove"]
    path: JsonPointer
    value: Any | None = None

    @model_validator(mode="after")
    def _operation_is_bounded(self) -> StructuredRevisionOperation:
        validate_json_pointer(self.path)
        has_value = "value" in self.model_fields_set
        if self.operation == "remove" and has_value:
            raise ValueError("remove operation must not declare value")
        if self.operation != "remove" and not has_value:
            raise ValueError("add and replace operations require value")
        return self


class StructuredRevision(SchemaModel):
    operations: Annotated[
        tuple[StructuredRevisionOperation, ...], Field(min_length=1, max_length=64)
    ]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _paths_are_unique(self) -> StructuredRevision:
        paths = tuple(item.path for item in self.operations)
        if len(paths) != len(set(paths)):
            raise ValueError("structured revision paths must be unique")
        return self


class StructuredRevisionDiff(SchemaModel):
    target_schema: RevisionTargetSchema
    changed_paths: Annotated[tuple[JsonPointer, ...], Field(min_length=1, max_length=64)]
    operations: Annotated[
        tuple[Literal["add", "replace", "remove"], ...],
        Field(min_length=1, max_length=64),
    ]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


def validate_structured_revision(value: dict[str, object]) -> dict[str, object]:
    return StructuredRevision.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def apply_structured_revision(
    base: dict[str, Any], revision: StructuredRevision
) -> dict[str, Any]:
    """Apply the bounded RFC-6902 subset to a detached JSON object."""

    value = _json_copy(base)
    for operation in revision.operations:
        tokens = _pointer_tokens(operation.path)
        parent: Any = value
        for token in tokens[:-1]:
            if isinstance(parent, dict):
                if token not in parent:
                    raise ValueError(f"revision path does not exist: {operation.path}")
                parent = parent[token]
            elif isinstance(parent, list):
                index = _list_index(token, len(parent), allow_end=False)
                parent = parent[index]
            else:
                raise ValueError(f"revision path has a scalar parent: {operation.path}")
        leaf = tokens[-1]
        if isinstance(parent, dict):
            if operation.operation in {"replace", "remove"} and leaf not in parent:
                raise ValueError(f"revision path does not exist: {operation.path}")
            if operation.operation == "remove":
                del parent[leaf]
            else:
                parent[leaf] = _json_copy(operation.value)
        elif isinstance(parent, list):
            if operation.operation == "add":
                index = _list_index(leaf, len(parent), allow_end=True)
                parent.insert(index, _json_copy(operation.value))
            else:
                index = _list_index(leaf, len(parent), allow_end=False)
                if operation.operation == "remove":
                    del parent[index]
                else:
                    parent[index] = _json_copy(operation.value)
        else:
            raise ValueError(f"revision path has a scalar parent: {operation.path}")
    return value


def operation_is_within_scope(path: str, allowed_paths: tuple[str, ...]) -> bool:
    return any(path == allowed or path.startswith(allowed + "/") for allowed in allowed_paths)


def validate_json_pointer(value: str) -> None:
    if not value.startswith("/") or value == "/":
        raise ValueError("revision path must be a non-root JSON Pointer")
    _pointer_tokens(value)
    if value == "/schema_version" or value.startswith("/schema_version/"):
        raise ValueError("schema_version cannot be revised")


def _pointer_tokens(value: str) -> tuple[str, ...]:
    tokens = []
    for raw in value[1:].split("/"):
        index = 0
        decoded = []
        while index < len(raw):
            if raw[index] != "~":
                decoded.append(raw[index])
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                raise ValueError("revision path contains an invalid JSON Pointer escape")
            decoded.append("~" if raw[index + 1] == "0" else "/")
            index += 2
        tokens.append("".join(decoded))
    return tuple(tokens)


def _list_index(token: str, length: int, *, allow_end: bool) -> int:
    if token == "-" and allow_end:
        return length
    if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
        raise ValueError("revision list index is invalid")
    index = int(token)
    upper = length if allow_end else length - 1
    if index > upper:
        raise ValueError("revision list index is out of range")
    return index


def _json_copy(value: Any) -> Any:
    import json

    return json.loads(canonical_json(value))


__all__ = [
    "JsonPointer",
    "RevisionTargetSchema",
    "StructuredRevision",
    "StructuredRevisionDiff",
    "StructuredRevisionOperation",
    "apply_structured_revision",
    "operation_is_within_scope",
    "validate_json_pointer",
    "validate_structured_revision",
]
