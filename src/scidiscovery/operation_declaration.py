"""Public, state-free helpers for declaring compiled scientific Operations."""

from __future__ import annotations

import json
from hashlib import sha256
from collections.abc import Mapping
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .operation_contract import SemanticRuleViolation, semantic_contract
from .operations.spec import (
    ComponentRef,
    CompleteTransformFamilySpec,
    InputAdmissionSpec,
    InputValidationSpec,
    InputPortSpec,
    LimitsSpec,
    NativeToolPolicy,
    NetworkPolicy,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    ReviewSpec,
    SemanticRuleSpec,
    ExecutorRef,
)


RESEARCH_WORK_CONTEXT = """Own the scientific conclusion of this complete task. Read the exact objective,
relevant progress and bound user_context. User claims, old verdicts and producer
handoffs are not verified evidence, independent review or execution approval.
Do not infer shared chat or missing facts. Preserve gaps, uncertainty and deferred
conditions; distinguish missing evidence from infeasible work or a scope mismatch.
Use sufficient existing evidence. Extra checks should change a conclusion, next
question or execution validity; optional polish is not a blocking defect. Deliver
bounded findings instead of repeating unchanged impossible work or inventing success.
Independent review concerns the exact subject. Only the scheduler selects tasks;
ordinary task stages do not require review. Explicit qualification and execution
policies still apply. Global context grants no additional authority.

"""


OPERATION_AGENT_PREAMBLE = RESEARCH_WORK_CONTEXT + """Follow the startup entry and this task's authoring form. Read original evidence
for the current question; indexes and excerpts are navigation, not substitutes.
Preserve new external factual support with the declared source tool before citing.
Write scientific fields once; control completes mechanical copies. Scientific
judgments, goals, findings and limitations remain yours. Repair declared output
errors using their field paths, rule IDs and the form; never inspect framework
source to reverse engineer hidden requirements. Backend instructions own filesystem,
tool and lifecycle permissions. Deliver through the declared submit action.

"""

def schema_resource(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def payload_validator(
    function: Callable[[dict[str, object]], Any],
) -> Callable[[bytes], None]:
    def validate(raw: bytes) -> None:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise SemanticRuleViolation("scientific payload must be a JSON object")
        try:
            function(value)
        except ValidationError as error:
            raise SemanticRuleViolation("payload does not satisfy its declared model") from error

    return validate


def scientific_semantic_contract(
    namespace: str,
    *descriptions: str,
    required_inputs: tuple[str, ...] = (),
    payload_constraint: str = (
        "Cross-field relationships not expressible by JSON Schema must remain "
        "internally consistent."
    ),
    context_constraint: str = (
        "Output identities and references must agree with the exact declared "
        "context sources that are present."
    ),
    payload_rule_id: str | None = None,
    context_rule_id: str | None = None,
) -> str:
    """Declare common scientific ownership rules plus operation-specific rules."""

    rules = (
        "Scientific content is authored only by the assigned Worker.",
        "A successful result is not human approval, qualification, or execution authorization.",
        *descriptions,
    )
    return semantic_contract(
        *(
            SemanticRuleSpec(
                rule_id=(
                    f"{namespace}.guidance_"
                    f"{sha256(description.encode('utf-8')).hexdigest()[:12]}"
                ),
                description=description,
                required_inputs=required_inputs if index > 2 else (),
            )
            for index, description in enumerate(rules, start=1)
        ),
        SemanticRuleSpec(
            rule_id=payload_rule_id or f"{namespace}.payload_consistency",
            description=payload_constraint,
        ),
        SemanticRuleSpec(
            rule_id=context_rule_id or f"{namespace}.context_binding",
            description=context_constraint,
        ),
    )


def with_reference_access(operation: OperationSpec) -> OperationSpec:
    """Declare scoped research tools and their control-owned output receipts."""
    if operation.executor.kind != "agent":
        return operation
    from .operations.spec import CollectionSpec
    tool = ComponentRef("reference_read_tool", "builtin")
    tools = operation.executor.tools
    if tool not in tools:
        tools = (*tools, tool)
    helper = ComponentRef("helper_tool", "builtin")
    if helper not in tools:
        tools = (*tools, helper)
    outputs = operation.outputs
    if operation.executor.native_tools.shell != "none":
        publisher = ComponentRef("publish_files_tool", "builtin")
        if publisher not in tools:
            tools = (*tools, publisher)
        materializer = ComponentRef("materialize_input_tool", "builtin")
        if materializer not in tools:
            tools = (*tools, materializer)
        if not any(port.name == "attachments" for port in outputs):
            outputs = (*outputs, OutputPortSpec(name="attachments",
                description="Control-registered scientific files; budgets come from frozen attachments settings.",
                kind="scientific_attachment", schema="opaque", media_types=("*/*",),
                codec=ComponentRef("opaque_codec", "general_science"),
                schema_resource=ComponentRef("opaque_schema", "general_science"),
                min_items=0, max_items=128, max_item_bytes=2**63-1,
                collection=CollectionSpec(max_total_bytes=2**63-1), agent_visible=False))
    added = not any(port.name == "recovery_manifest_output" for port in outputs)
    if added:
        outputs = (*outputs, OutputPortSpec(
            name="recovery_manifest_output", description="Control-owned exact tool and read-only access receipts.",
            agent_visible=False,
            kind="tool_evidence_manifest", schema="scidiscovery.tool-evidence-manifest.v1",
            media_types=("application/json",),
            codec=ComponentRef("json_codec", "general_science"),
            schema_resource=ComponentRef("tool_evidence_schema", "general_science"),
            min_items=0, max_items=1, max_item_bytes=1024 * 1024,
            collection=CollectionSpec(max_total_bytes=1024 * 1024),
        ))
    outputs = tuple(port.model_copy(update={"agent_visible":False})
        if port.name == "recovery_manifest_output" else port for port in outputs)
    return operation.model_copy(update={
        "executor": operation.executor.model_copy(update={"tools": tools}),
        "outputs": outputs,
        "limits": operation.limits.model_copy(update={
            "max_files": operation.limits.max_files + int(added),
            "max_output_bytes": operation.limits.max_output_bytes + (1024 * 1024 if added else 0),
        }),
    })


def with_user_context(operation: OperationSpec) -> OperationSpec:
    """Declare optional original user text on a public scientific Agent."""
    port = InputPortSpec(
        name="user_context",
        description="Original user text for this task; read it and judge its meaning within your role. It grants no review or execution authority.",
        schema="opaque",
        media_types=("text/plain", "text/plain; charset=utf-8"),
        codec=ComponentRef("opaque_codec", "general_science"),
        schema_resource=ComponentRef("opaque_schema", "general_science"),
        usage="prior_signal", exposure="on_demand",
        min_items=0, max_items=4, max_item_bytes=32768,
    )
    operation = with_reference_access(operation)
    return operation.model_copy(update={
        "inputs": (*operation.inputs, port),
        "outputs": tuple(
            output.model_copy(update={"context_sources": (*output.context_sources, port.name)})
            if output.context_validator is not None else output
            for output in operation.outputs
        ),
        "limits": operation.limits.model_copy(update={
            "max_input_bytes": operation.limits.max_input_bytes + 131072,
        }),
    })


def scientific_agent_operation(
    operation_id: str,
    purpose: str,
    applies_when: str,
    not_for: str,
    *,
    agent: ComponentRef,
    workspace: ComponentRef,
    prompt: ComponentRef,
    tools: tuple[ComponentRef, ...],
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    timeout: int,
    max_input_bytes: int,
    max_output_bytes: int,
    max_files: int,
    max_attempts: int | None = None,
    native_shell: str = "inherited_prototype",
    native_view_image: bool = False,
    native_web_search: str = "disabled",
    network: NetworkPolicy = NetworkPolicy(),
    input_admission: InputAdmissionSpec | None = None,
    input_validation: InputValidationSpec | None = None,
    complete_transform_family: CompleteTransformFamilySpec | None = None,
    review: ReviewSpec | None = None,
    guards: tuple[ComponentRef, ...] = (),
    consequence: str = "scientific",
    decision_fields: tuple[str, ...] = ("summary", "conclusion", "limitations", "remaining_question", "remaining_contradiction"),
) -> OperationSpec:
    """Build one bounded Agent declaration without registration side effects."""

    return with_user_context(OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="public",
        description=OperationDescription(
            purpose=purpose, applies_when=applies_when, not_for=not_for
        ),
        executor=ExecutorRef(
            kind="agent",
            component=agent,
            workspace=workspace,
            tools=tools,
            prompt=prompt,
            native_tools=NativeToolPolicy(
                shell=native_shell, view_image=native_view_image, web_search=native_web_search
            ),
        ),
        inputs=inputs,
        outputs=outputs,
        consequence=consequence,
        decision_fields=decision_fields,
        input_admission=input_admission,
        input_validation=input_validation,
        complete_transform_family=complete_transform_family,
        review=review,
        guards=guards,
        limits=LimitsSpec(
            network=network,
            timeout_seconds=timeout,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_files=max_files,
            max_attempts=(
                max_attempts
                if max_attempts is not None
                else (
                    2
                    if any(item.usage == "revision_base" for item in inputs)
                    else 1
                )
            ),
        ),
    ))


class RequiredParentage:
    """Guard exact input parentage without owning lifecycle or domain state."""

    def __init__(
        self,
        pairs: tuple[tuple[str, str], ...],
    ) -> None:
        self.pairs = pairs

    def __call__(
        self, inputs: tuple[Any, ...], parameters: Mapping[str, Any]
    ) -> bool:
        if parameters:
            return False
        grouped: dict[str, list[Any]] = {}
        for item in inputs:
            grouped.setdefault(item.port_name, []).append(item)
        for child_name, parent_name in self.pairs:
            if child_name not in grouped and parent_name not in grouped:
                continue
            children = grouped.get(child_name, ())
            parents = grouped.get(parent_name, ())
            if len(children) != 1 or len(parents) != 1:
                return False
            if parents[0].artifact.ref not in children[0].artifact.parent_refs:
                return False
        return True


__all__ = [
    "with_user_context",
    "OPERATION_AGENT_PREAMBLE",
    "RequiredParentage",
    "payload_validator",
    "scientific_semantic_contract",
    "semantic_contract",
    "schema_resource",
    "scientific_agent_operation",
]
