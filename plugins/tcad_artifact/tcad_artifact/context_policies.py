"""TCAD-specific task-context policies."""

from scidiscovery.artifact_agent.context_policy import (
    ContextInputRule,
    RoleContextPolicies,
    TaskContextPolicy,
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
                ),
                ContextInputRule(
                    "experiment_plan",
                    "full",
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=1024 * 1024,
                ),
                ContextInputRule(
                    "scientific_foundation",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.scientific-foundation.v1",),
                    max_bytes=1024 * 1024,
                ),
            ),
            allow_additional=False,
            max_inputs=3,
            max_readable_bytes=3 * 1024 * 1024,
        ),
        "tcad.deck-review.revision.v2": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "revised_project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                ),
                ContextInputRule(
                    "project_diff",
                    "full",
                    schemas=("tcad.deck-project-diff.v1",),
                    max_bytes=128 * 1024,
                ),
                ContextInputRule(
                    "prior_review",
                    "on_demand",
                    required=False,
                    schemas=("tcad.deck-review-report.v1",),
                    max_bytes=256 * 1024,
                ),
                ContextInputRule(
                    "experiment_plan",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=1024 * 1024,
                ),
            ),
            allow_additional=False,
            max_inputs=4,
            max_readable_bytes=2 * 1024 * 1024,
        ),
        "tcad.deck-review.provenance.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "project",
                    "full",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=1024 * 1024,
                ),
                ContextInputRule(
                    "diagnosis",
                    "full",
                    schemas=("scidiscovery.layered-diagnosis.v1",),
                    max_bytes=256 * 1024,
                ),
                ContextInputRule(
                    "metric_report",
                    "full",
                    max_bytes=512 * 1024,
                ),
                ContextInputRule(
                    "evidence_audit",
                    "on_demand",
                    required=False,
                    max_bytes=512 * 1024,
                ),
            ),
            allow_additional=False,
            max_inputs=4,
            max_readable_bytes=2 * 1024 * 1024,
        ),
    },
    default_profile=None,
)


__all__ = ["DECK_REVIEW_CONTEXT_POLICIES"]
