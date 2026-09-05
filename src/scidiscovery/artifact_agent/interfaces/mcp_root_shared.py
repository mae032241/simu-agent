"""State-free values shared by the Root MCP route modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...operations.invoke import BoundOperationCall


NONQUALIFYING_HANDOFF_VERDICTS = frozenset({"blocked", "revise"})
APPROVAL_OPTION_IDS = {
    "accept": "approve",
    "accept_with_exception": "approve_with_exception",
    "reject": "reject",
    "revise": "revise",
}


class RootToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreationTarget:
    name: str
    logical_name: str
    revision: int
    existing_object_id: str | None


def derived_name(base: str, *parts: str) -> str:
    value = ".".join((base, *parts))
    if len(value) > 256:
        raise RootToolError("derived semantic name is too long")
    return value


def claim_admissible(
    labels: dict[str, str] | Any, handoff_verdict: str | None
) -> bool:
    return (
        labels.get("scientific_claim_admissible") != "false"
        and handoff_verdict not in NONQUALIFYING_HANDOFF_VERDICTS
    )


def operation_artifact_labels(
    bound: BoundOperationCall | None,
) -> dict[str, str]:
    if bound is None:
        return {}
    labels = {
        "operation_id": bound.compiled.spec.operation_id,
        "operation_version": bound.compiled.spec.version,
        "operation_digest": bound.compiled.digest,
    }
    if (
        bound.compiled.spec.consequence == "explore"
        or bound.compiled.spec.catalog_scope == "internal"
    ):
        labels["scientific_claim_admissible"] = "false"
    identity = bound.compiled.approval_identity
    if identity is not None:
        labels["approval_contract_digest"] = identity.approval_contract_digest
    return labels


def identity_word(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in ("_id", "hash", "token", "ref"))


__all__ = [
    "APPROVAL_OPTION_IDS",
    "CreationTarget",
    "NONQUALIFYING_HANDOFF_VERDICTS",
    "RootToolError",
    "claim_admissible",
    "derived_name",
    "identity_word",
    "operation_artifact_labels",
]
