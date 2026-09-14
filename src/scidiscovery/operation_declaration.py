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
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    ReviewSpec,
    SemanticRuleSpec,
    ExecutorRef,
)


RESEARCH_WORK_CONTEXT = """Research context and responsibilities:
Evidence establishes source-bound facts; hypotheses propose falsifiable explanations;
design selects a feasible current objective and retains later objectives and conditions.
Independent review checks scientific validity and whether the task is deliverable from
its declared inputs. Authors implement the exact plan within available capabilities;
execution requires its own authorization; analysis interprets actual results and may
return limited or inconclusive findings for the next design. These are composable
responsibilities, not a mandatory stage sequence. Only the scheduler selects Operations.

Read the bound overall objective, current plan/task, and relevant progress before
judging or implementing. Read large evidence on demand through declared input tools.
Background and past verdicts do not override the current exact subject or grant claim
or execution qualification. A producer's handoff is not automatically part of its payload.
Never assume shared chat, unbound files, or another role's tools are available.
Report unavailable context precisely without inventing facts or replacement inputs.
Read any bound user_context originals before judging the task. These are user
requirements, suggestions or factual claims relayed by the scheduler; assess their
meaning and evidential weight within your role. They are not independent review,
verified evidence or execution approval. Report a scope or input gap when needed;
no acknowledgment form or proof of adopting every suggestion is required.

Distinguish missing implementation inputs, responsibility/capability mismatch, and
conditions affecting only later analysis. Do not turn all later conditions into authoring
prerequisites. Redesign may defer work, change a supported method, narrow the current
objective, or explain infeasibility; it need not perform every missing task itself.
Do not repeat an unchanged impossible assignment or create placeholder success.
Independent reviewers assess the exact subject themselves, not the author's hidden
reasoning. Global awareness grants no extra access, scientific authority, or tools.

"""


OPERATION_AGENT_PREAMBLE = RESEARCH_WORK_CONTEXT + """This is one bounded compiled scientific Operation.
Read only the exact assignment, declared inputs, and output contract returned by
the selected runtime backend. Do not search the project repository, installed
package, framework source, historical runs, or sibling workspaces. Treat missing
task-local evidence as a bounded gap rather than permission to find substitutes.

The runtime appends the authoritative backend-specific lifecycle, filesystem,
and tool instructions. A tool being visible is not authorization to use it. If
output validation fails, correct the reported rule_id and field paths against
the compiled Schema and its two contract pointers declared in assignment.json;
never inspect framework implementation to reverse engineer a validator.
The output Schema describes the sealed result. Existing workspace finalizers fill
mechanical copies before validation: proposal resource case_count from cases, the
portfolio objective in proposal objectives, and Intake objective text from its formal
objective_contract.statement (or foundation objective when no contract exists).
Write the authoritative scientific field once; its generated copies may be omitted.
For ScientificReview, the finalizer projects handoff verdict and a short reference
to the formal payload.summary; these transport fields or the whole handoff may be
omitted in the draft. Explicit handoff notes remain. CriticReview and EvidenceAudit
only project verdict: their handoff summary and any needed next actions remain authored.
Scientific choices, findings, current/later goals and evidence are never generated.
Scientific content must be delivered through the backend's declared submit
action, not through chat.

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
    input_admission: InputAdmissionSpec | None = None,
    input_validation: InputValidationSpec | None = None,
    complete_transform_family: CompleteTransformFamilySpec | None = None,
    review: ReviewSpec | None = None,
    guards: tuple[ComponentRef, ...] = (),
    consequence: str = "scientific",
    accepts_actions: tuple[str, ...] = (),
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
            model="gpt-5.6-sol",
            native_tools=NativeToolPolicy(
                shell=native_shell, view_image=native_view_image
            ),
        ),
        inputs=inputs,
        outputs=outputs,
        consequence=consequence,
        input_admission=input_admission,
        input_validation=input_validation,
        complete_transform_family=complete_transform_family,
        review=review,
        guards=guards,
        accepts_actions=accepts_actions,
        limits=LimitsSpec(
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
