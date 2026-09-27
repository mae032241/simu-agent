"""Domain-neutral Agent Operation declarations; no registration side effects."""

from __future__ import annotations

from .operation_declaration import scientific_agent_operation
from .operations.spec import CollectionSpec, ComponentRef, NetworkPolicy, InputAdmissionSpec, InputValidationSpec, InputDerivationSpec, InputPortSpec, OperationSpec, OutputPortSpec, ReviewSpec

JSON_CODEC = ComponentRef("json_codec")
OPAQUE_CODEC = ComponentRef("opaque_codec")
WORKSPACE_REF = ComponentRef("workspace")
BUILTIN = "builtin"
_EVIDENCE_APPROVAL_PROVIDER = ("science.evidence.qualify.v1",)
_FOUNDATION_ADMISSION = InputAdmissionSpec(
    cohort_id="qualified_foundation",
    member_ports=("scientific_foundation",),
    approval_subject_ports=("scientific_foundation",),
    approval_kind="scientific_foundation",
    accepted_options=("approve",),
    accepted_provider_operations=_EVIDENCE_APPROVAL_PROVIDER,
)


def _ref(component_id: str) -> ComponentRef:
    if component_id in {
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
        "file_apply_patch_tool",
    }:
        return ComponentRef(component_id, plugin_id=BUILTIN)
    return ComponentRef(component_id)


BASE_TOOLS = tuple(
    _ref(name)
    for name in (
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
        "file_apply_patch_tool",
    )
)


def _input(
    name: str,
    description: str,
    schema: str,
    *,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
    max_items: int = 1,
    max_item_bytes: int = 1024 * 1024,
    exposure: str = "full",
    usage: str = "claim_evidence",
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=OPAQUE_CODEC if schema in {"opaque", "*"} else JSON_CODEC,
        schema_resource=ComponentRef(_schema_component(schema)),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        exposure=exposure,
        usage=usage,
    )


def _output(
    name: str,
    description: str,
    kind: str,
    schema: str,
    validator: str,
    *,
    max_item_bytes: int,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
    max_items: int = 1,
    collection: CollectionSpec | None = None,
    context_validator: str | None = None,
    context_sources: tuple[str, ...] = (),
    semantic_contract: str | None = None,
    evidence_paths: tuple[str, ...] | None = None,
) -> OutputPortSpec:
    payload_rule, context_rule = _checker_rule_ids(schema)
    return OutputPortSpec(
        name=name,
        description=description,
        kind=kind,
        schema=schema,
        media_types=media_types,
        codec=OPAQUE_CODEC if schema == "opaque" else JSON_CODEC,
        schema_resource=ComponentRef(_schema_component(schema)),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        validator=ComponentRef(validator),
        validator_rule_id=payload_rule,
        semantic_contract=ComponentRef(
            semantic_contract or _semantic_component(schema)
        ),
        collection=collection,
        context_validator=(
            ComponentRef(context_validator) if context_validator is not None else None
        ),
        context_rule_id=(
            context_rule
            if context_validator is not None
            else None
        ),
        context_sources=context_sources,
        evidence_paths=(
            _EVIDENCE_PATHS_BY_SCHEMA.get(schema, ())
            if evidence_paths is None
            else evidence_paths
        ),
    )


_EVIDENCE_PATHS_BY_SCHEMA = {
    "scidiscovery.scientific-intake.v1": ("/scientific_foundation/evidence",),
    "scidiscovery.scientific-foundation.v1": ("/evidence",),
    "scidiscovery.hypothesis-proposal.v2": ("/evidence",),
    "scidiscovery.critic-review.v2": ("/evidence",),
    "scidiscovery.evidence-audit.v1": ("/evidence",),
    "scidiscovery.scientific-review.v1": ("/evidence",),
}


def _schema_component(schema: str) -> str:
    return {
        "opaque": "opaque_schema",
        "scidiscovery.scientific-intake.v1": "scientific_intake_schema",
        "scidiscovery.tool-evidence-manifest.v1": "tool_evidence_schema",
        "scidiscovery.scientific-foundation.v1": "scientific_foundation_schema",
        "scidiscovery.problem-frame.v1": "problem_frame_schema",
        "scidiscovery.hypothesis-proposal.v2": "hypothesis_schema",
        "scidiscovery.critic-review.v2": "critic_review_schema",
        "scidiscovery.evidence-audit.v1": "evidence_audit_schema",
        "scidiscovery.research-objective.v1": "research_objective_schema",
        "scidiscovery.execution-context.v1": "execution_context_schema",
        "scidiscovery.experiment-scientific-skeleton.v1": "experiment_skeleton_schema",
        "scidiscovery.experiment-design-intent.v1": "experiment_intent_schema",
        "scidiscovery.experiment-portfolio.v1": "experiment_portfolio_schema",
        "scidiscovery.scientific-review.v1": "scientific_review_schema",
        "*": "wildcard_schema",
    }[schema]


def _semantic_component(schema: str) -> str:
    return {
        "opaque": "intake_semantic_contract",
        "scidiscovery.scientific-intake.v1": "intake_semantic_contract",
        "scidiscovery.hypothesis-proposal.v2": "hypothesis_semantic_contract",
        "scidiscovery.critic-review.v2": "critic_semantic_contract",
        "scidiscovery.evidence-audit.v1": "evidence_audit_semantic_contract",
        "scidiscovery.experiment-scientific-skeleton.v1": "experiment_skeleton_semantic_contract",
        "scidiscovery.experiment-design-intent.v1": "experiment_design_semantic_contract",
        "scidiscovery.experiment-portfolio.v1": "experiment_revision_semantic_contract",
        "scidiscovery.scientific-review.v1": "scientific_review_semantic_contract",
    }[schema]


def _checker_rule_ids(schema: str) -> tuple[str, str]:
    return {
        "opaque": ("intake.internal_closure", "intake.source_binding"),
        "scidiscovery.scientific-intake.v1": (
            "intake.internal_closure", "intake.source_binding"
        ),
        "scidiscovery.hypothesis-proposal.v2": (
            "hypothesis.portfolio_closure", "hypothesis.objective_binding"
        ),
        "scidiscovery.critic-review.v2": (
            "critic.review_consistency", "critic.portfolio_binding"
        ),
        "scidiscovery.evidence-audit.v1": (
            "evidence.audit.check_consistency", "evidence.audit.source_binding"
        ),
        "scidiscovery.experiment-scientific-skeleton.v1": ("experiment.skeleton.structure", "experiment.skeleton.binding"),
        "scidiscovery.experiment-design-intent.v1": (
            "experiment.design.intent_closure",
            "experiment.design.objective_and_hypothesis_binding",
        ),
        "scidiscovery.experiment-portfolio.v1": (
            "experiment.revision.case_and_validation_closure",
            "experiment.revision.review_target",
        ),
        "scidiscovery.scientific-review.v1": (
            "experiment.review.structure",
            "experiment.review.subject_binding",
        ),
    }[schema]


def _agent(
    operation_id: str,
    purpose: str,
    applies_when: str,
    not_for: str,
    *,
    agent: str,
    prompt: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    timeout: int,
    max_input_bytes: int,
    max_output_bytes: int,
    max_files: int,
    tools: tuple[ComponentRef, ...] = BASE_TOOLS,
    native_view_image: bool = False,
    native_web_search: str = "disabled",
    network: NetworkPolicy = NetworkPolicy(),
    input_admission: InputAdmissionSpec | None = None,
    input_validation: InputValidationSpec | None = None,
    review: ReviewSpec | None = None,
    guards: tuple[str, ...] = (),
    consequence: str = "scientific",
    decision_fields: tuple[str, ...] = ("summary", "conclusion", "limitations", "remaining_question", "remaining_contradiction"),
) -> OperationSpec:
    return scientific_agent_operation(
        operation_id,
        purpose,
        applies_when,
        not_for,
        agent=ComponentRef(agent),
        workspace=WORKSPACE_REF,
        prompt=ComponentRef(prompt),
        tools=tools,
        inputs=inputs,
        outputs=outputs,
        timeout=timeout,
        max_input_bytes=max_input_bytes,
        max_output_bytes=max_output_bytes,
        max_files=max_files,
        native_view_image=native_view_image,
        native_web_search=native_web_search,
        network=network,
        input_admission=input_admission,
        input_validation=input_validation,
        review=review,
        guards=tuple(ComponentRef(item) for item in guards),
        consequence=consequence,
        decision_fields=decision_fields,
    )


RETRIEVED_SOURCE_OUTPUT = OutputPortSpec(
    name="tool_evidence", description="Tool-preserved original public sources, with provenance in the manifest.",
    kind="retrieved_source", schema="opaque",
    media_types=("application/pdf", "text/html", "text/plain", "text/csv", "application/json"),
    codec=OPAQUE_CODEC, schema_resource=ComponentRef("opaque_schema"),
    min_items=0, max_items=8, max_item_bytes=16 * 1024 * 1024,
    collection=CollectionSpec(max_total_bytes=128 * 1024 * 1024),
)
SOURCE_MANIFEST_OUTPUT = OutputPortSpec(
    name="recovery_manifest_output", description="Control-owned source provenance and retrieval attempts.",
    kind="tool_evidence_manifest", schema="scidiscovery.tool-evidence-manifest.v1",
    media_types=("application/json",), codec=JSON_CODEC, schema_resource=ComponentRef("tool_evidence_schema"),
    min_items=0, max_items=1, max_item_bytes=1024 * 1024,
    collection=CollectionSpec(max_total_bytes=1024 * 1024),
)

INTAKE_OUTPUT = _output(
    "scientific_intake",
    "Concise problem frame and source-bound scientific foundation.",
    "scientific_intake",
    "scidiscovery.scientific-intake.v1",
    "intake_validator",
    max_item_bytes=64 * 1024,
    context_validator="intake_source_context",
    context_sources=("source_material",),
)
def _hypothesis_output(*context_sources: str) -> OutputPortSpec:
    return _output(
        "hypothesis_portfolio",
        "Distinct falsifiable hypothesis proposal bound to one global objective.",
        "hypothesis_portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        "hypothesis_validator",
        max_item_bytes=64 * 1024,
        context_validator="hypothesis_objective_context",
        context_sources=context_sources,
        evidence_paths=(),
    )
def _audit_output(*context_sources: str) -> OutputPortSpec:
    return _output(
        "evidence_audit",
        "Independent evidence and provenance audit.",
        "evidence_audit",
        "scidiscovery.evidence-audit.v1",
        "audit_validator",
        max_item_bytes=32 * 1024,
        context_validator="evidence_audit_context",
        context_sources=context_sources,
    )


_HYPOTHESIS_FEEDBACK = tuple(
    _input(name, description, "*", media_types=("*/*",), min_items=0,
           max_items=4, max_item_bytes=bound, exposure="on_demand", usage="evidence_inventory")
    for name, description, bound in (
        ("experiment_results", "Exact observations, original outputs or failed executions; not automatic mechanism evidence.", 8*1024*1024),
        ("result_analysis", "Sealed interpretations with their validity limits; negative and inconclusive reports remain readable.", 128*1024),
        ("current_progress", "Relevant exact plans, prior reviews and bounded history, read only when needed.", 2*1024*1024),
    )
)
_PREVIOUS_HYPOTHESES = _input("previous_hypotheses",
    "Optional earlier portfolio for evidence-driven comparison, not a revision base or inherited review.",
    "scidiscovery.hypothesis-proposal.v2", min_items=0, max_item_bytes=128*1024,
    exposure="on_demand", usage="evidence_inventory")
_HYPOTHESIS_FEEDBACK_NAMES = tuple(port.name for port in _HYPOTHESIS_FEEDBACK)

OPERATIONS = (
    _agent(
        "science.evidence.audit.v1",
        "Audit one scientific foundation against its exact supplied sources.",
        "A foundation exists and its source support must be checked independently.",
        "Extracting evidence, generating mechanisms, or granting qualification.",
        agent="auditor_agent",
        prompt="auditor_prompt",
        inputs=(
            _input(
                "scientific_foundation",
                "Scientific foundation under independent audit.",
                "scidiscovery.scientific-foundation.v1",
                usage="prior_signal",
            ),
            _input(
                "source_material",
                "Exact frozen source material cited by the foundation.",
                "*",
                media_types=("*/*",),
                min_items=0,
                max_items=14,
                max_item_bytes=2**63-1,
                exposure="material",
                usage="evidence_inventory",
            ),
        ),
        decision_fields=("checks",),
        outputs=(_audit_output("scientific_foundation", "source_material"),),
        timeout=600,
        max_input_bytes=225 * 1024 * 1024,
        max_output_bytes=32 * 1024,
        max_files=1,
        tools=BASE_TOOLS + (_ref("pdf_extract_tool"),),
        native_view_image=True,
    ),
    _agent(
        "science.evidence.audit.intake.v1",
        "Audit one extracted ScientificIntake against its exact supplied sources.",
        "A provisional intake must be checked before its claims are qualified.",
        "Creating the intake or approving it.",
        agent="auditor_agent",
        prompt="auditor_prompt",
        inputs=(
            _input(
                "scientific_intake",
                "Provisional scientific intake under review.",
                "scidiscovery.scientific-intake.v1",
                usage="prior_signal",
            ),
            _input(
                "source_material",
                "Exact frozen source material used by the intake.",
                "*",
                media_types=("*/*",),
                min_items=1,
                max_items=14,
                max_item_bytes=2**63-1,
                exposure="material",
                usage="evidence_inventory",
            ),

        ),
        decision_fields=("checks",),
        outputs=(_audit_output("scientific_intake", "source_material"),),
        timeout=600,
        max_input_bytes=225 * 1024 * 1024,
        max_output_bytes=32 * 1024,
        max_files=1,
        tools=BASE_TOOLS + (_ref("pdf_extract_tool"),),
        native_view_image=True,
    ),
    _agent(
        "science.evidence.extract.v1",
        "Extract or revise one complete ScientificIntake using sources and optional prior evidence or feedback.",
        "The objective needs a source-backed problem frame and foundation.",
        "Granting qualification. Use a domain evidence task when quantitative extraction tools are needed.",
        decision_fields=("/scientific_foundation/summary", "/scientific_foundation/missing_inputs", "/scientific_foundation/open_questions", "/problem_frame/current_contradiction"),
        agent="evidence_agent",
        prompt="evidence_prompt",
        inputs=(
            _input(
                "source_material",
                "Immutable paper, text, table, or user-supplied source.",
                "*",
                media_types=("*/*",),
                max_items=6,
                max_item_bytes=2**63-1,
                exposure="material", usage="evidence_inventory",
            ),
            _input("prior_draft", "Optional exact previous intake to reconsider.", "scidiscovery.scientific-intake.v1", min_items=0, exposure="on_demand", usage="evidence_inventory"),
            _input("feedback", "Optional review, scientific feedback or remaining evidence question.", "*", media_types=("*/*",), min_items=0, max_items=4, exposure="on_demand", usage="evidence_inventory"),
        ),
        outputs=(INTAKE_OUTPUT.model_copy(update={"context_sources": ("source_material", "prior_draft", "feedback", "tool_evidence")}),
                 RETRIEVED_SOURCE_OUTPUT, SOURCE_MANIFEST_OUTPUT),
        timeout=900,
        max_input_bytes=96 * 1024 * 1024,
        max_output_bytes=129 * 1024 * 1024 + 64 * 1024,
        max_files=10,
        tools=BASE_TOOLS + (_ref("pdf_extract_tool"), _ref("source_capture_tool")),
        native_view_image=True,
        native_web_search="live",
        network=NetworkPolicy(mode="public_web", max_requests=24),
        review=ReviewSpec(
            reviewer_operation="science.evidence.audit.intake.v1",
            reviewer_input_port="scientific_intake",
            subject_outputs=("scientific_intake",),
        ),
    ).model_copy(update={"version": "2"}),
    _agent(
        "science.hypothesis.criticize.v1",
        "Adversarially review every proposed hypothesis.",
        "A hypothesis portfolio and its scientific foundation are available.",
        "Generating hypotheses or deciding qualification.",
        input_validation=InputValidationSpec(ComponentRef("critic_inputs"), "science.hypothesis.criticize.v1.inputs", "The exact hypothesis portfolio must contain hypotheses."),
        decision_fields=("disposition", "global_issues", "reviews"),
        agent="critic_agent",
        prompt="critic_prompt",
        inputs=(
            _input(
                "hypothesis_portfolio",
                "Exact hypothesis proposal under review.",
                "scidiscovery.hypothesis-proposal.v2",
                usage="prior_signal",
            ),
            _input(
                "scientific_foundation",
                "Exact scientific foundation used to challenge the proposal.",
                "scidiscovery.scientific-foundation.v1",
            ).model_copy(update={"derivation": InputDerivationSpec(anchor_port="hypothesis_portfolio", producer_input_path=("scientific_foundation",))}),
            *_HYPOTHESIS_FEEDBACK,
            _PREVIOUS_HYPOTHESES,
        ),
        outputs=(
            _output(
                "scientific_review",
                "Independent hypothesis critic review.",
                "scientific_review",
                "scidiscovery.critic-review.v2",
                "critic_validator",
                max_item_bytes=32 * 1024,
                context_validator="critic_portfolio_context",
                context_sources=("hypothesis_portfolio", "scientific_foundation", "previous_hypotheses", *_HYPOTHESIS_FEEDBACK_NAMES),
                evidence_paths=(),
            ),
        ),
        timeout=600,
        max_input_bytes=48 * 1024 * 1024,
        max_output_bytes=32 * 1024,
        max_files=1,
        input_admission=_FOUNDATION_ADMISSION,
    ),
    _agent(
        "science.hypothesis.propose.v1",
        "Propose or evolve a bounded hypothesis portfolio using the current contradiction and any bound experiment feedback.",
        "A problem frame and scientific foundation, optionally with prior hypotheses and results, expose an unresolved question.",
        "Reviewing, selecting, or qualifying hypotheses.",
        input_validation=InputValidationSpec(ComponentRef("hypothesis_inputs"), "science.hypothesis.propose.v1.inputs", "The scientific foundation must contain its explicit original objective."),
        decision_fields=("stage_objective", "contradiction", "hypotheses"),
        agent="ideator_agent",
        prompt="ideator_prompt",
        inputs=(
            _input(
                "problem_frame",
                "Exact bounded problem frame.",
                "scidiscovery.problem-frame.v1",
                max_item_bytes=512 * 1024,
                usage="prior_signal",
            ),
            _input(
                "scientific_foundation",
                "Exact evidence-bearing scientific foundation.",
                "scidiscovery.scientific-foundation.v1",
            ),
            *_HYPOTHESIS_FEEDBACK,
            _PREVIOUS_HYPOTHESES,
        ),
        outputs=(_hypothesis_output("problem_frame", "scientific_foundation", "previous_hypotheses", *_HYPOTHESIS_FEEDBACK_NAMES),),
        timeout=900,
        max_input_bytes=48 * 1024 * 1024,
        max_output_bytes=64 * 1024,
        max_files=1,
        input_admission=_FOUNDATION_ADMISSION,
        review=ReviewSpec(
            reviewer_operation="science.hypothesis.criticize.v1",
            reviewer_input_port="hypothesis_portfolio",
            subject_outputs=("hypothesis_portfolio",),
        ),
    ),
)


AGENT_OPERATIONS = OPERATIONS

__all__ = ["AGENT_OPERATIONS"]
