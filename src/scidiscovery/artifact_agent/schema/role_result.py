"""Uniform worker result envelope shared by every scientific role."""

from __future__ import annotations

from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .common import canonical_json


class FormModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
    )


class RoleHandoff(FormModel):
    verdict: Literal["pass", "revise", "blocked", "inconclusive"]
    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    assumptions: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    next_actions: Annotated[tuple[str, ...], Field(max_length=32)] = ()


PayloadT = TypeVar("PayloadT")


class RoleResultEnvelope(FormModel, Generic[PayloadT]):
    schema_version: Literal[1]
    handoff: RoleHandoff
    payload: PayloadT

    def canonical_json(self) -> bytes:
        return canonical_json(self.model_dump(mode="json"))


def parse_role_result(value: Any) -> RoleResultEnvelope[Any]:
    return RoleResultEnvelope[Any].model_validate_json(
        canonical_json(value), strict=True
    )


def role_result_json_schema(payload_model: type[BaseModel]) -> dict[str, Any]:
    return RoleResultEnvelope[payload_model].model_json_schema(mode="validation")


__all__ = [
    "FormModel",
    "RoleHandoff",
    "RoleResultEnvelope",
    "parse_role_result",
    "role_result_json_schema",
]
