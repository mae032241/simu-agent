"""TCAD-specific task-context policies."""

from scidiscovery.artifact_agent.context_policy import (
    ContextInputRule,
    RoleContextPolicies,
    TaskContextPolicy,
)


DECK_AUTHOR_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "tcad.deck-author.capability-bound.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "execution_capability",
                    "full",
                    schemas=("tcad.solver-capability.v2",),
                    max_bytes=64 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=True,
            additional_usages=("claim_evidence",),
            max_inputs=32,
            max_readable_bytes=64 * 1024 * 1024,
        ),
        "tcad.deck-author.capability-bound.revision.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "prior_project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                    usage="revision_base",
                ),
                ContextInputRule(
                    "change_request",
                    "full",
                    schemas=("tcad.deck-review-report.v1",),
                    max_bytes=256 * 1024,
                    usage="change_request",
                ),
                ContextInputRule(
                    "execution_capability",
                    "full",
                    schemas=("tcad.solver-capability.v2",),
                    max_bytes=64 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "experiment_plan",
                    "full",
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "reviewed_hypotheses",
                    "full",
                    schemas=("scidiscovery.hypothesis-proposal.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "candidate_review",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.critic-review.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "hypothesis_evidence_audit",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.evidence-audit.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "scientific_foundation",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.scientific-foundation.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "foundation_evidence_audit",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.evidence-audit.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=False,
            max_inputs=9,
            max_readable_bytes=(
                4 * 1024 * 1024 + 3 * 512 * 1024 + 320 * 1024
            ),
        ),
        "tcad.deck-author.runtime-failure-revision.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "prior_project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                    usage="revision_base",
                ),
                ContextInputRule(
                    "runtime_attestation",
                    "full",
                    schemas=("tcad.runtime-attestation.v1",),
                    max_bytes=256 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "solver_log",
                    "full",
                    schemas=("opaque",),
                    max_bytes=16 * 1024 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "execution_capability",
                    "full",
                    schemas=("tcad.solver-capability.v2",),
                    max_bytes=64 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "experiment_plan",
                    "full",
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=False,
            max_inputs=5,
            max_readable_bytes=19 * 1024 * 1024,
        ),
    },
    default_profile="tcad.deck-author.capability-bound.v1",
)


DECK_REVIEW_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "tcad.deck-review.initial.v2": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "experiment_plan",
                    "full",
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "execution_capability",
                    "full",
                    schemas=("tcad.solver-capability.v2",),
                    max_bytes=64 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "scientific_foundation",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.scientific-foundation.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "parameter_requirements",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.device-parameter-requirements.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "device_parameters",
                    "full",
                    required=False,
                    schemas=("scidiscovery.device-parameter-set.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "source_catalog",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.evidence-source-catalog.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "parameter_coverage",
                    "full",
                    required=False,
                    schemas=("scidiscovery.device-parameter-coverage.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "parameter_audit",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.evidence-audit.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=False,
            max_inputs=9,
            max_readable_bytes=12 * 1024 * 1024,
        ),
        "tcad.deck-review.revision.v2": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "revised_project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "project_diff",
                    "full",
                    schemas=("tcad.deck-project-diff.v1",),
                    max_bytes=128 * 1024,
                    usage="change_request",
                ),
                ContextInputRule(
                    "execution_capability",
                    "full",
                    schemas=("tcad.solver-capability.v2",),
                    max_bytes=64 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "prior_review",
                    "on_demand",
                    required=False,
                    schemas=("tcad.deck-review-report.v1",),
                    max_bytes=256 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "experiment_plan",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=False,
            max_inputs=5,
            max_readable_bytes=3 * 1024 * 1024,
        ),
        "tcad.deck-review.provenance.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "diagnosis",
                    "full",
                    schemas=("scidiscovery.layered-diagnosis.v1",),
                    max_bytes=256 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "metric_report",
                    "full",
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "execution_capability",
                    "full",
                    schemas=("tcad.solver-capability.v2",),
                    max_bytes=64 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "evidence_audit",
                    "on_demand",
                    required=False,
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=False,
            max_inputs=5,
            max_readable_bytes=3 * 1024 * 1024,
        ),
    },
    default_profile=None,
)


__all__ = [
    "DECK_AUTHOR_CONTEXT_POLICIES",
    "DECK_REVIEW_CONTEXT_POLICIES",
]
