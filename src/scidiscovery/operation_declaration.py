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


RESEARCH_WORK_CONTEXT = """Research responsibilities (composable, not a mandatory sequence):
Evidence establishes source-bound facts; hypotheses propose falsifiable explanations;
design selects feasible current objectives and retains later goals and conditions.
Independent review checks validity and deliverability from declared inputs. Authors
implement the exact plan within available capabilities. Execution requires separate
authorization; analysis interprets actual results, including limited or inconclusive
findings. Only the scheduler selects Operations.

Read the bound overall objective, exact task and relevant progress. Background and
past verdicts grant no current claim or execution qualification; a producer's handoff
is not automatically in its payload. Never assume shared chat, unbound files or
another role's tools. Report missing context without inventing replacements.
Read bound user_context originals and judge their meaning and evidential weight:
requirements, suggestions and claims are not verified evidence, independent review
or execution approval. Report scope/input gaps; no acknowledgment form is needed.

Distinguish missing implementation inputs, capability/responsibility mismatch and
later analysis conditions. Later conditions need not block authoring. Redesign may
defer work, narrow objectives, change a supported method or explain infeasibility;
it need not do every missing task. Do not repeat impossible assignments unchanged
or create placeholder success. Independent reviewers assess the exact subject,
not hidden author reasoning. Global awareness grants no extra authority or access.

Keep local detail proportional to the current research decision. Pursue additional
checks only when they can materially change the conclusion, next action or execution
validity; judge precision against evidence uncertainty and the intended claim.
Once evidence supports a scoped conclusion, deliver it with limitations instead of
refining indefinitely. Reviewers distinguish material defects from optional polish;
do not turn the latter into blockers. Use existing evidence and tools before adding
experiments. Never silently relax a frozen requirement: explain disproportionate
requirements through the existing redesign path. Preserve required review and approval.

"""


OPERATION_AGENT_PREAMBLE = RESEARCH_WORK_CONTEXT + """This is one bounded compiled scientific Operation.
Read its exact assignment, declared inputs, registered tool evidence and output contract.
External discovery requires explicit current-Operation permission; preserve new factual
support with its declared source tool before citing it. Do not search
the project repository, framework source, installed packages, historical runs or
sibling workspaces. Missing task-local evidence is a bounded gap.
The runtime appends authoritative backend lifecycle, filesystem and tool rules;
visibility is not authorization. Correct output rejections using rule_id, field
paths, the compiled Schema and its two contract pointers in assignment.json;
never reverse engineer the validator from framework source.

Read for a concrete task question: use the compact entry and input index first,
then needed original sections, JSON paths, curves or images. Do not print entire
assignments, tool maps, directories or logs just to discover their contents.
Retain already-read contracts within this assignment; refresh after a new assignment
or contract loss/change. Do not truncate a contract or required scientific evidence.

Write scientific fields once; workspace finalizers supply the mechanical copies
specified by the role and output contract, never scientific choices, findings,
goals or evidence. Deliver scientific content through the declared submit action,
not chat.

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
    """Declare the common read-only capability, never an executor or input port."""
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
