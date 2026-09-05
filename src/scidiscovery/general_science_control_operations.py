"""Domain-neutral Transform and Approval Operation declarations."""

from __future__ import annotations

from .operations.spec import (
    ApprovalContract,
    ApprovalOption,
    ComponentRef,
    ExecutorRef,
    InputAdmissionSpec,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    ReviewSpec,
)

JSON_CODEC = ComponentRef("json_codec")
OPAQUE_CODEC = ComponentRef("opaque_codec")
INTAKE_SPLIT_OPERATION = "science.intake.split.v1"
EVIDENCE_APPROVAL_PROVIDER = ("science.evidence.qualify.v1",)

_SCHEMA_RESOURCES = {
    "*": "wildcard_schema",
    "scidiscovery.scientific-intake.v1": "scientific_intake_schema",
    "scidiscovery.scientific-foundation.v1": "scientific_foundation_schema",
    "scidiscovery.problem-frame.v1": "problem_frame_schema",
    "scidiscovery.hypothesis-proposal.v2": "hypothesis_schema",
    "scidiscovery.critic-review.v2": "critic_review_schema",
    "scidiscovery.evidence-audit.v1": "evidence_audit_schema",
    "scidiscovery.research-objective.v1": "research_objective_schema",
    "scidiscovery.experiment-design-intent.v1": "experiment_intent_schema",
    "scidiscovery.experiment-portfolio.v1": "experiment_portfolio_schema",
    "scidiscovery.experiment-plan-materialization.v1": "materialization_report_schema",
}


def _input(
    name: str,
    description: str,
    schema: str,
    *,
    media_types: tuple[str, ...] | None = None,
    min_items: int = 1,
    max_items: int = 1,
    max_item_bytes: int = 8 * 1024 * 1024,
    usage: str = "claim_evidence",
    exposure: str = "full",
    required_non_null_fields: tuple[str, ...] = (),
) -> InputPortSpec:
    wildcard = schema == "*"
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=(
            media_types
            if media_types is not None
            else ("*/*",) if wildcard else ("application/json",)
        ),
        codec=OPAQUE_CODEC if wildcard else JSON_CODEC,
        schema_resource=ComponentRef(_SCHEMA_RESOURCES[schema]),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        usage=usage,
        exposure=exposure,
        required_non_null_fields=required_non_null_fields,
    )


def _output(
    name: str,
    description: str,
    kind: str,
    schema: str,
    validator: str,
    *,
    max_item_bytes: int = 8 * 1024 * 1024,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=description,
        kind=kind,
        schema=schema,
        media_types=("application/json",),
        codec=JSON_CODEC,
        schema_resource=ComponentRef(_SCHEMA_RESOURCES[schema]),
        max_item_bytes=max_item_bytes,
        validator=ComponentRef(validator),
    )


def _transform(
    operation_id: str,
    purpose: str,
    applies_when: str,
    not_for: str,
    *,
    component: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    input_admission: InputAdmissionSpec | None = None,
    review: ReviewSpec | None = None,
    guards: tuple[str, ...] = (),
    max_input_bytes: int = 32 * 1024 * 1024,
    max_output_bytes: int = 16 * 1024 * 1024,
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="support",
        description=OperationDescription(purpose, applies_when, not_for),
        executor=ExecutorRef(kind="transform", component=ComponentRef(component)),
        inputs=inputs,
        outputs=outputs,
        consequence="scientific",
        input_admission=input_admission,
        review=review,
        guards=tuple(ComponentRef(item) for item in guards),
        limits=LimitsSpec(
            timeout_seconds=60,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_files=len(outputs),
        ),
    )


BASE_OPERATIONS = (
    _transform(
        INTAKE_SPLIT_OPERATION,
        "Split one validated scientific intake into its immutable frame and foundation.",
        "A scientific intake exists and its provisional status must be preserved.",
        "Extracting new evidence or changing scientific content.",
        component="intake_split",
        inputs=(
            _input(
                "scientific_intake",
                "Exact validated scientific intake.",
                "scidiscovery.scientific-intake.v1",
                usage="prior_signal",
            ),
            _input(
                "evidence_audit",
                "Exact passing independent audit of this scientific intake.",
                "scidiscovery.evidence-audit.v1",
                usage="prior_signal",
                exposure="handoff_only",
            ),
        ),
        outputs=(
            _output(
                "problem_frame",
                "Problem frame projected from the intake.",
                "problem_frame",
                "scidiscovery.problem-frame.v1",
                "problem_frame_validator",
            ),
            _output(
                "scientific_foundation",
                "Scientific foundation projected from the intake.",
                "scientific_foundation",
                "scidiscovery.scientific-foundation.v1",
                "foundation_validator",
            ),
        ),
    ),
)


TRANSFORM_OPERATIONS = BASE_OPERATIONS

def _approval_operation(
    operation_id: str,
    description: OperationDescription,
    *,
    projector: str,
    inputs: tuple[InputPortSpec, ...],
    question: str,
    options: tuple[ApprovalOption, ...],
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="public",
        description=description,
        executor=ExecutorRef(kind="approval", component=ComponentRef(projector)),
        inputs=inputs,
        outputs=(),
        consequence="scientific",
        review=ReviewSpec(
            approval=ApprovalContract(
                subject_ports=tuple(port.name for port in inputs),
                question=question,
                options=options,
                projector=ComponentRef(projector),
                kind="scientific_foundation",
            )
        ),
        limits=LimitsSpec(
            timeout_seconds=60,
            max_input_bytes=512 * 1024 * 1024,
            max_output_bytes=512 * 1024,
            max_files=1,
        ),
    )


EVIDENCE_APPROVAL_INPUTS = (
    _input(
        "scientific_foundation",
        "Exact foundation split from the final extraction primary.",
        "scidiscovery.scientific-foundation.v1",
        usage="prior_signal",
    ),
    _input(
        "extraction_primary",
        "Exact final ScientificIntake primary under qualification.",
        "scidiscovery.scientific-intake.v1",
        usage="prior_signal",
    ),
    _input(
        "producer_outputs",
        "Complete non-validation sibling output family.",
        "*",
        media_types=("*/*",),
        min_items=0,
        max_items=177,
        max_item_bytes=32 * 1024 * 1024,
        exposure="handoff_only",
        usage="evidence_inventory",
    ),
    _input(
        "validation_results",
        "Complete deterministic validation result set when applicable.",
        "*",
        media_types=("*/*",),
        min_items=0,
        max_items=16,
        max_item_bytes=32 * 1024 * 1024,
        exposure="handoff_only",
        usage="evidence_inventory",
    ),
    _input(
        "frozen_sources",
        "Complete frozen producer evidence-source set.",
        "*",
        media_types=("*/*",),
        min_items=0,
        max_items=32,
        max_item_bytes=32 * 1024 * 1024,
        exposure="handoff_only",
        usage="evidence_inventory",
    ),
    _input(
        "evidence_audit",
        "Independent audit of the exact final evidence family.",
        "scidiscovery.evidence-audit.v1",
        usage="prior_signal",
    ),
)


APPROVAL_OPERATIONS = (
    _approval_operation(
        "science.evidence.qualify.v1",
        OperationDescription(
            purpose="Create one human qualification review for a complete evidence family.",
            applies_when="Extraction, deterministic validation, and an independent audit are complete.",
            not_for="Extracting evidence, repairing a provisional bundle, or granting execution authority.",
        ),
        projector="evidence_qualification_projector",
        inputs=EVIDENCE_APPROVAL_INPUTS,
        question="是否批准这组完整、已独立审核的科学证据作为后续研究基础？",
        options=(
            ApprovalOption("批准", "accept"),
            ApprovalOption("要求修订", "revise", requires_reason=True),
        ),
    ),
)

CONTROL_OPERATIONS = TRANSFORM_OPERATIONS + APPROVAL_OPERATIONS

__all__ = [
    "CONTROL_OPERATIONS",
    "EVIDENCE_APPROVAL_PROVIDER",
    "INTAKE_SPLIT_OPERATION",
    "REVISION_TARGETS",
]
