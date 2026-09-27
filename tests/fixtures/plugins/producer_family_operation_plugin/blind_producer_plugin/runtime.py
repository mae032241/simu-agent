"""State-free implementations for the blind producer-family fixture."""

from __future__ import annotations

import json
from typing import Any, Mapping

from scidiscovery.artifact_agent.schema.approval import (
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.operation_declaration import semantic_contract
from scidiscovery.operations.invoke import ApprovalProjectorContext
from scidiscovery.operations.spec import (
    CallableComponent,
    SemanticRuleSpec,
    WorkspaceContract,
)


def _schema(schema_id: str) -> str:
    return json.dumps(
        {"$id": schema_id, "additionalProperties": True, "type": "object"},
        separators=(",", ":"),
        sort_keys=True,
    )


SOURCE_SCHEMA = _schema("blind.source.v1")
OBJECT_SCHEMA = _schema("blind.object.v1")
REVIEW_SCHEMA = _schema("blind.review.v1")
SEMANTIC_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="producer.output",
        description="Every output is validated by its compiled port contract.",
    )
)
PROMPT = (
    "Produce the complete bounded blind object or independent review assigned by "
    "this Operation. Never emit a patch or inherit an earlier verdict."
)
WORKSPACE = WorkspaceContract()


def _json_codec(raw: bytes) -> bytes:
    value = json.loads(raw)
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _object_validator(raw: bytes) -> None:
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("value"), str):
        raise ValueError("blind object requires one string value")


def _review_validator(raw: bytes) -> None:
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("verdict") not in {"pass", "revise"}:
        raise ValueError("blind review requires a pass or revise verdict")
    if not isinstance(value.get("request"), str) or not value["request"].strip():
        raise ValueError("blind review requires a non-empty request")


def _producer(values: Mapping[str, tuple[bytes, ...]]) -> dict[str, tuple[bytes, ...]]:
    source = json.loads(values["seed"][0])
    value = str(source.get("value", "seed"))
    return {
        "specimen": (
            json.dumps({"value": value}, separators=(",", ":"), sort_keys=True).encode(),
        ),
        "notes": tuple(
            json.dumps({"value": value}, separators=(",", ":"), sort_keys=True).encode()
            for value in ("alpha", "beta")
        ),
    }


def _agent_marker() -> None:
    return None


def _approval_projector(context: ApprovalProjectorContext) -> ReviewDocument:
    candidates = tuple(item for item in context.subjects if item.port_name == "candidate")
    if len(candidates) != 1:
        raise ValueError("blind approval requires one candidate")
    candidate = candidates[0]
    families = tuple(
        item for item in context.producer_families if item.primary_ref == candidate.ref
    )
    if len(families) != 1:
        raise ValueError("blind approval requires one complete producer family")
    family = families[0]
    expected_siblings = tuple(
        member.ref for member in family.members if member.ref != family.primary_ref
    )
    actual_siblings = tuple(
        item.ref for item in context.subjects if item.port_name == "companions"
    )
    if actual_siblings != expected_siblings:
        raise ValueError("blind approval omitted or added a producer sibling")
    reviews = tuple(item for item in context.subjects if item.port_name == "review")
    if len(reviews) != 1:
        raise ValueError("blind approval requires one independent review")
    return ReviewDocument(
        title="盲插件生产者族审批",
        description="展示插件声明的完整对象族。",
        sections=(
            ReviewDocumentSection(
                title="主对象",
                items=(
                    ReviewDocumentItem(
                        kind="json_tree",
                        label="候选对象",
                        subject_index=candidate.subject_index,
                        json_pointer="",
                    ),
                ),
            ),
        ),
    )


JSON_CODEC = CallableComponent("codec", _json_codec)
OBJECT_VALIDATOR = CallableComponent("validator", _object_validator)
REVIEW_VALIDATOR = CallableComponent("validator", _review_validator)
PRODUCER = CallableComponent("transform", _producer)
REVISION_AGENT = CallableComponent("agent", _agent_marker)
REVIEW_AGENT = CallableComponent("agent", _agent_marker)
APPROVAL_PROJECTOR = CallableComponent("projector", _approval_projector)
