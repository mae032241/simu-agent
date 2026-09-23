"""Domain-neutral experiment Operation declarations."""

from __future__ import annotations

from .general_science_agent_operations import (
    _EVIDENCE_APPROVAL_PROVIDER,
    _FOUNDATION_ADMISSION,
    _agent,
    _input as _agent_input,
    _output as _agent_output,
)
from .general_science_control_operations import (
    _input as _transform_input,
    _output as _transform_output,
    _transform,
)
from .operations.spec import ComponentRef, InputAdmissionSpec, InputValidationSpec, ReviewSpec


_OPTIONAL_SCIENCE_CONTEXT_ADMISSION = InputAdmissionSpec(
    cohort_id="qualified_science_context",
    member_ports=(
        "scientific_foundation",
        "research_objective",
        "hypothesis_portfolio",
        "critic_review",
    ),
    approval_subject_ports=("scientific_foundation",),
    approval_kind="scientific_foundation",
    accepted_options=("approve",),
    accepted_provider_operations=_EVIDENCE_APPROVAL_PROVIDER,
)


_FEEDBACK_INPUTS = tuple(
    _agent_input(
        name,
        description,
        "*",
        media_types=("*/*",),
        min_items=0,
        max_items=4,
        max_item_bytes=8 * 1024 * 1024,
        exposure="on_demand",
        usage="evidence_inventory",
    )
    for name, description in (
        ("current_progress", "Optional exact prior plans, reviews, and bounded progress records."),
        ("experiment_results", "Optional exact experiment outputs, failures, and deterministic metrics."),
        ("result_analysis", "Optional exact analyses supporting the current objective selection."),
    )
)


AGENT_OPERATIONS = (
    _agent(
        "science.experiment.design.v1",
        "Design a legacy detailed-plan intent that discriminates reviewed hypotheses.",
        "A research objective, hypothesis portfolio, and independent critic review are available.",
        "Expanding the complete execution plan or implementing domain code.",
        input_validation=InputValidationSpec(ComponentRef("experiment_inputs"), "science.experiment.design.v1.inputs", "The hypothesis portfolio must match the exact research objective; critic disposition must support design; optional execution context must be structurally valid."),
        agent="experiment_agent",
        prompt="experiment_design_prompt",
        inputs=(
            _agent_input(
                "scientific_foundation",
                "Exact approved foundation shared by the objective, portfolio, and critic.",
                "scidiscovery.scientific-foundation.v1",
                max_item_bytes=1024 * 1024,
                exposure="handoff_only",
                usage="prior_signal",
            ),
            _agent_input(
                "research_objective",
                "Exact immutable research objective.",
                "scidiscovery.research-objective.v1",
                max_item_bytes=512 * 1024,
                usage="prior_signal",
            ),
            _agent_input(
                "hypothesis_portfolio",
                "Exact reviewed hypothesis portfolio.",
                "scidiscovery.hypothesis-proposal.v2",
                usage="prior_signal",
            ),
            _agent_input(
                "critic_review",
                "Exact independent critic review.",
                "scidiscovery.critic-review.v2",
                max_item_bytes=64 * 1024,
                usage="prior_signal",
            ),
            _agent_input(
                "execution_context",
                "Optional immutable execution capabilities, model coverage, and implementation limits.",
                "scidiscovery.execution-context.v1",
                min_items=0,
                max_item_bytes=64 * 1024,
                usage="prior_signal",
            ),
            *_FEEDBACK_INPUTS,
        ),
        outputs=(
            _agent_output(
                "experiment_design_intent",
                "Compact experiment-design intent.",
                "experiment_design_intent",
                "scidiscovery.experiment-design-intent.v1",
                "experiment_validator",
                max_item_bytes=64 * 1024,
                context_validator="experiment_context",
                context_sources=(
                    "research_objective",
                    "hypothesis_portfolio",
                    "critic_review",
                    "execution_context",
                    "current_progress",
                    "experiment_results",
                    "result_analysis",
                ),
            ),
        ),
        timeout=900,
        max_input_bytes=32 * 1024 * 1024,
        max_output_bytes=64 * 1024,
        max_files=1,
        input_admission=_FOUNDATION_ADMISSION,
        guards=("experiment_science_cohort",),
        accepts_actions=(
            "science.experiment.design",
            "science.model-counterfactual.design",
        ),
    ),
    _agent(
        "science.object.review.v1",
        "Independently review exactly one legacy plan or scientific skeleton without changing it.",
        "A complete legacy portfolio or scientific skeleton needs independent scientific review.",
        "Reviewing an unmaterialized intent or granting human approval.",
        input_validation=InputValidationSpec(ComponentRef("object_review_inputs"), "science.object.review.v1.inputs", "Bind exactly one experiment_plan or scientific_skeleton; validate that subject and optional research objective/execution context structures. The reviewer judges the plan's relation to the original goal; stage objectives need not repeat its key or statement."),
        agent="critic_agent",
        prompt="object_review_prompt",
        inputs=(
            _agent_input("scientific_skeleton", "Optional scientific skeleton under review; exactly one subject is required.", "scidiscovery.experiment-scientific-skeleton.v1", min_items=0, usage="prior_signal", max_item_bytes=64 * 1024),
            _agent_input(
                "experiment_plan",
                "Complete experiment portfolio under review (legacy branch).",
                "scidiscovery.experiment-portfolio.v1",
                min_items=0,
                max_item_bytes=2 * 1024 * 1024,
                usage="prior_signal",
            ),
            _agent_input(
                "research_objective",
                "Optional exact original research objective for independent coverage review.",
                "scidiscovery.research-objective.v1",
                min_items=0,
                max_item_bytes=512 * 1024,
                usage="prior_signal",
            ),
            _agent_input(
                "execution_context",
                "Optional immutable execution capabilities and implementation limits.",
                "scidiscovery.execution-context.v1",
                min_items=0,
                max_item_bytes=64 * 1024,
                usage="prior_signal",
            ),
            *_FEEDBACK_INPUTS,
        ),
        outputs=(
            _agent_output(
                "scientific_review",
                "Independent structured review.",
                "scientific_review",
                "scidiscovery.scientific-review.v1",
                "review_validator",
                max_item_bytes=64 * 1024,
                context_validator="object_review_context",
                context_sources=(
                    "experiment_plan", "scientific_skeleton", "research_objective", "execution_context",
                    "current_progress", "experiment_results", "result_analysis",
                ),
                evidence_paths=(),
            ),
        ),
        timeout=600,
        max_input_bytes=32 * 1024 * 1024,
        max_output_bytes=64 * 1024,
        max_files=1,
    ),
    _agent(
        "science.experiment.revise.v1",
        "Revise one complete immutable legacy experiment plan.",
        "An exact prior experiment and independent review are available.",
        "Producing a patch, inheriting review qualification, or changing unsupported science.",
        input_validation=InputValidationSpec(ComponentRef("experiment_revision_inputs"), "science.experiment.revise.v1.inputs", "The change request must review the experiment portfolio."),
        agent="experiment_agent",
        prompt="experiment_prompt",
        inputs=(
            _agent_input(
                "prior_draft",
                "Exact immutable experiment.",
                "scidiscovery.experiment-portfolio.v1",
                max_item_bytes=8 * 1024 * 1024,
                usage="revision_base",
            ),
            _agent_input(
                "change_request",
                "Exact independent review.",
                "scidiscovery.scientific-review.v1",
                max_item_bytes=512 * 1024,
                usage="change_request",
            ),
            _FEEDBACK_INPUTS[0].model_copy(update={"max_item_bytes": 2 * 1024 * 1024}),
        ),
        outputs=(
            _agent_output(
                "experiment_plan",
                "Complete revised experiment portfolio.",
                "experiment_portfolio",
                "scidiscovery.experiment-portfolio.v1",
                "experiment_portfolio_validator",
                max_item_bytes=2 * 1024 * 1024,
                context_validator="experiment_revision_context",
                context_sources=("prior_draft", "change_request", "current_progress"),
            ),
        ),
        timeout=900,
        max_input_bytes=16 * 1024 * 1024,
        max_output_bytes=2 * 1024 * 1024,
        max_files=1,
        review=ReviewSpec(
            reviewer_operation="science.object.review.v1",
            reviewer_input_port="experiment_plan",
            subject_outputs=("experiment_plan",),
        ),
    ).model_copy(update={"version": "2"}),
)


TRANSFORM_OPERATIONS = (
    _transform(
        "science.objective.project.v1",
        "Project the exact research objective declared by a foundation.",
        "A qualified foundation declares an explicit objective contract.",
        "Inferring a new objective or changing scientific content.",
        component="objective_project",
        inputs=(
            _transform_input(
                "scientific_foundation",
                "Qualified foundation containing the objective contract.",
                "scidiscovery.scientific-foundation.v1",
                usage="prior_signal",
                required_non_null_fields=("objective_contract",),
            ),
        ),
        outputs=(
            _transform_output(
                "research_objective",
                "Exact research objective contract.",
                "research_objective",
                "scidiscovery.research-objective.v1",
                "objective_validator",
            ),
        ),
        input_admission=_FOUNDATION_ADMISSION,
    ),
    _transform(
        "science.experiment.materialize.v1",
        "Materialize one compact experiment intent into a complete plan.",
        "A validated compact intent and its optional exact scientific context are bound.",
        "Adding scientific choices absent from the compact intent.",
        component="experiment_materialize",
        inputs=(
            _transform_input(
                "experiment_design_intent",
                "Compact intent.",
                "scidiscovery.experiment-design-intent.v1",
                usage="prior_signal",
            ),
            _transform_input(
                "scientific_foundation",
                "Optional exact approved foundation cohort witness.",
                "scidiscovery.scientific-foundation.v1",
                min_items=0,
                usage="prior_signal",
                exposure="handoff_only",
            ),
            _transform_input(
                "research_objective",
                "Optional exact objective.",
                "scidiscovery.research-objective.v1",
                min_items=0,
                usage="prior_signal",
            ),
            _transform_input(
                "hypothesis_portfolio",
                "Optional exact hypothesis proposal.",
                "scidiscovery.hypothesis-proposal.v2",
                min_items=0,
                usage="prior_signal",
            ),
            _transform_input(
                "critic_review",
                "Optional exact critic review.",
                "scidiscovery.critic-review.v2",
                min_items=0,
                usage="prior_signal",
                exposure="handoff_only",
            ),
        ),
        outputs=(
            _transform_output(
                "experiment_plan",
                "Complete experiment portfolio.",
                "experiment_portfolio",
                "scidiscovery.experiment-portfolio.v1",
                "experiment_portfolio_validator",
            ),
            _transform_output(
                "materialization_report",
                "Deterministic materialization report.",
                "experiment_plan_materialization_report",
                "scidiscovery.experiment-plan-materialization.v1",
                "materialization_report_validator",
            ),
        ),
        input_admission=_OPTIONAL_SCIENCE_CONTEXT_ADMISSION,
        guards=("experiment_lineage",),
        review=ReviewSpec(
            reviewer_operation="science.object.review.v1",
            reviewer_input_port="experiment_plan",
            subject_outputs=("experiment_plan",),
        ),
    ),
)



__all__ = ["AGENT_OPERATIONS", "OPERATIONS", "TRANSFORM_OPERATIONS"]


# A new design, including intentional revisions, uses normal foundation admission.
# It has one primary output and intentionally no mandatory review edge.
AGENT_OPERATIONS += (
    _agent(
        "science.experiment.skeleton.v1",
        "Design the scientific skeleton; the TCAD author owns its concrete implementation plan.",
        "Reviewed hypotheses and an approved foundation support a bounded scientific decision.",
        "Enumerating implementation cases, writing code or granting execution permission.",
        input_validation=InputValidationSpec(ComponentRef("skeleton_inputs"), "science.experiment.skeleton.v1.inputs", "Normal design inputs and paired optional exact prior skeleton/change basis are required."),
        agent="experiment_agent", prompt="experiment_skeleton_prompt",
        inputs=(*(p for p in AGENT_OPERATIONS[0].inputs if p.name != "user_context"),
            _agent_input("prior_skeleton", "Exact prior skeleton for an intentional new design.", "scidiscovery.experiment-scientific-skeleton.v1", min_items=0, usage="prior_signal", max_item_bytes=64 * 1024),
            _agent_input("skeleton_change_basis", "Exact formal change evidence; pair with prior_skeleton.", "*", media_types=("*/*",), min_items=0, exposure="on_demand", usage="evidence_inventory", max_item_bytes=2 * 1024 * 1024)),
        outputs=(_agent_output("scientific_skeleton", "Scientific choices without compulsory engineering cases.", "experiment_scientific_skeleton", "scidiscovery.experiment-scientific-skeleton.v1", "skeleton_validator", max_item_bytes=64 * 1024, context_validator="skeleton_context", context_sources=tuple(p.name for p in AGENT_OPERATIONS[0].inputs if p.exposure != "handoff_only" and p.name != "user_context") + ("prior_skeleton", "skeleton_change_basis")),),
        timeout=900, max_input_bytes=32 * 1024 * 1024, max_output_bytes=64 * 1024,
        max_files=1, input_admission=_FOUNDATION_ADMISSION, guards=("experiment_science_cohort",),
    ),
)

OPERATIONS = AGENT_OPERATIONS + TRANSFORM_OPERATIONS
