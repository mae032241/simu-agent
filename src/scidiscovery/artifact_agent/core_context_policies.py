"""Core role context policies that close scientific handoff contracts."""

from .context_policy import ContextInputRule, RoleContextPolicies, TaskContextPolicy


EXPERIMENT_DESIGN_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "scidiscovery.experiment-design.reviewed.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "hypothesis_portfolio",
                    "full",
                    schemas=("scidiscovery.hypothesis-proposal.v1",),
                    max_bytes=1024 * 1024,
                ),
                ContextInputRule(
                    "candidate_eligibility",
                    "full",
                    schemas=("scidiscovery.candidate-eligibility.v1",),
                    max_bytes=256 * 1024,
                ),
                ContextInputRule(
                    "problem_frame",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.problem-frame.v1",),
                    max_bytes=512 * 1024,
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
            max_inputs=4,
            max_readable_bytes=3 * 1024 * 1024,
        ),
        "scidiscovery.experiment-design.engineering.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "diagnosis",
                    "full",
                    schemas=("scidiscovery.layered-diagnosis.v1",),
                    max_bytes=512 * 1024,
                ),
                ContextInputRule(
                    "project_review",
                    "full",
                    schemas=("tcad.deck-review-report.v1",),
                    max_bytes=512 * 1024,
                ),
                ContextInputRule(
                    "project",
                    "on_demand",
                    required=False,
                    schemas=("tcad.deck-project.v1",),
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
            max_inputs=4,
            max_readable_bytes=3 * 1024 * 1024,
        ),
    },
    default_profile=None,
)


__all__ = ["EXPERIMENT_DESIGN_CONTEXT_POLICIES"]
