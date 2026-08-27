"""Core role context policies that close scientific handoff contracts."""

from .context_policy import ContextInputRule, RoleContextPolicies, TaskContextPolicy


_REVISION_TARGET_SCHEMAS = (
    "scidiscovery.scientific-intake.v1",
    "scidiscovery.scientific-foundation.v1",
    "scidiscovery.hypothesis-proposal.v1",
    "scidiscovery.hypothesis-portfolio.v1",
    "scidiscovery.experiment-portfolio.v1",
)


_STRUCTURED_REVISION_POLICY = TaskContextPolicy(
    rules=(
        ContextInputRule(
            "prior_draft",
            "full",
            schemas=_REVISION_TARGET_SCHEMAS,
            max_bytes=8 * 1024 * 1024,
            usage="revision_base",
        ),
        ContextInputRule(
            "change_request",
            "full",
            required=False,
            max_bytes=512 * 1024,
            usage="change_request",
        ),
        ContextInputRule(
            "prior_signal",
            "on_demand",
            required=False,
            max_bytes=512 * 1024,
            usage="prior_signal",
        ),
    ),
    allow_additional=True,
    additional_usages=("cached_excerpt",),
    max_inputs=6,
    max_readable_bytes=12 * 1024 * 1024,
)


_EXPERIMENT_DESIGN_EVIDENCE_REVISION_POLICY = TaskContextPolicy(
    rules=(
        ContextInputRule(
            "prior_draft",
            "full",
            schemas=("scidiscovery.experiment-portfolio.v1",),
            max_bytes=8 * 1024 * 1024,
            usage="revision_base",
        ),
        ContextInputRule(
            "change_request",
            "full",
            required=False,
            max_bytes=512 * 1024,
            usage="change_request",
        ),
        ContextInputRule(
            "figure_manifest",
            "full",
            schemas=("scidiscovery.figure-evidence-manifest.v1",),
            max_bytes=1024 * 1024,
            usage="evidence_inventory",
        ),
        ContextInputRule(
            "evidence_validation_report",
            "full",
            schemas=("scidiscovery.figure-evidence-validation-report.v1",),
            max_bytes=1024 * 1024,
            usage="evidence_inventory",
        ),
    ),
    allow_additional=False,
    max_inputs=4,
    max_readable_bytes=10 * 1024 * 1024,
)


SCIENTIFIC_REVISION_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "default": TaskContextPolicy(),
        "scidiscovery.scientific-revision.v1": _STRUCTURED_REVISION_POLICY,
        "scidiscovery.scientific-revision.figure-extraction.v1": (
            TaskContextPolicy(
                rules=(
                    ContextInputRule(
                        "prior_draft",
                        "full",
                        schemas=("scidiscovery.scientific-intake.v1",),
                        max_bytes=8 * 1024 * 1024,
                        usage="revision_base",
                    ),
                    ContextInputRule(
                        "paper_source",
                        "full",
                        max_bytes=32 * 1024 * 1024,
                        usage="claim_evidence",
                    ),
                    ContextInputRule(
                        "figure_manifest",
                        "full",
                        schemas=("scidiscovery.figure-evidence-manifest.v1",),
                        max_bytes=1024 * 1024,
                        usage="evidence_inventory",
                    ),
                    ContextInputRule(
                        "evidence_validation_report",
                        "full",
                        schemas=(
                            "scidiscovery.figure-evidence-validation-report.v1",
                        ),
                        max_bytes=1024 * 1024,
                        usage="evidence_inventory",
                    ),
                ),
                allow_additional=True,
                additional_usages=("evidence_inventory",),
                max_inputs=32,
                max_readable_bytes=64 * 1024 * 1024,
            )
        ),
        "scidiscovery.evidence-intake.device-parameters.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "parameter_requirements",
                    "full",
                    required=False,
                    schemas=(
                        "scidiscovery.device-parameter-requirements.v1",
                    ),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=True,
            max_inputs=32,
            max_readable_bytes=64 * 1024 * 1024,
        ),
    },
    default_profile="default",
)


CRITIC_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "default": TaskContextPolicy(),
        "scidiscovery.critic.revision.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "revised_object",
                    "full",
                    schemas=_REVISION_TARGET_SCHEMAS,
                    max_bytes=8 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "revision_diff",
                    "full",
                    schemas=("scidiscovery.structured-revision-diff.v1",),
                    max_bytes=512 * 1024,
                    usage="change_request",
                ),
                ContextInputRule(
                    "prior_review",
                    "on_demand",
                    schemas=("scidiscovery.critic-review.v1",),
                    max_bytes=512 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "evidence_receipt",
                    "full",
                    schemas=("scidiscovery.unchanged-evidence-receipt.v1",),
                    max_bytes=512 * 1024,
                    usage="unchanged_set_receipt",
                ),
                ContextInputRule(
                    "revision_request",
                    "full",
                    required=False,
                    max_bytes=512 * 1024,
                    usage="change_request",
                ),
            ),
            allow_additional=True,
            additional_usages=("cached_excerpt",),
            max_inputs=9,
            max_readable_bytes=12 * 1024 * 1024,
        ),
    },
    default_profile="default",
)

EVIDENCE_AUDITOR_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "default": TaskContextPolicy(),
        "scidiscovery.evidence-audit.device-parameters.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "scientific_foundation",
                    "full",
                    schemas=("scidiscovery.scientific-foundation.v1",),
                    max_bytes=8 * 1024 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "parameter_requirements",
                    "full",
                    schemas=(
                        "scidiscovery.device-parameter-requirements.v1",
                    ),
                    max_bytes=2 * 1024 * 1024,
                    usage="evidence_inventory",
                ),
                ContextInputRule(
                    "device_parameters",
                    "full",
                    schemas=("scidiscovery.device-parameter-set.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="evidence_inventory",
                ),
                ContextInputRule(
                    "source_catalog",
                    "full",
                    schemas=("scidiscovery.evidence-source-catalog.v1",),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
                ContextInputRule(
                    "parameter_coverage",
                    "full",
                    schemas=("scidiscovery.device-parameter-coverage.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="evidence_inventory",
                ),
            ),
            allow_additional=True,
            additional_usages=("evidence_inventory",),
            max_inputs=37,
            max_readable_bytes=80 * 1024 * 1024,
        ),
        "scidiscovery.evidence-audit.figure-extraction.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "extraction_primary",
                    "full",
                    schemas=("scidiscovery.scientific-intake.v1",),
                    max_bytes=8 * 1024 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "paper_source",
                    "full",
                    required=False,
                    max_bytes=32 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "figure_manifest",
                    "full",
                    schemas=("scidiscovery.figure-evidence-manifest.v1",),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
                ContextInputRule(
                    "evidence_validation_report",
                    "full",
                    schemas=(
                        "scidiscovery.figure-evidence-validation-report.v1",
                    ),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
            ),
            allow_additional=True,
            additional_usages=("evidence_inventory",),
            max_inputs=32,
            max_readable_bytes=64 * 1024 * 1024,
        ),
        "scidiscovery.evidence-audit.revision.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "revised_object",
                    "full",
                    schemas=(
                        "scidiscovery.scientific-intake.v1",
                        "scidiscovery.scientific-foundation.v1",
                        "scidiscovery.hypothesis-proposal.v1",
                        "scidiscovery.hypothesis-portfolio.v1",
                        "scidiscovery.experiment-portfolio.v1",
                    ),
                    max_bytes=8 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "revision_diff",
                    "full",
                    schemas=("scidiscovery.structured-revision-diff.v1",),
                    max_bytes=512 * 1024,
                    usage="change_request",
                ),
                ContextInputRule(
                    "prior_audit",
                    "on_demand",
                    schemas=("scidiscovery.evidence-audit.v1",),
                    max_bytes=512 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "evidence_receipt",
                    "full",
                    schemas=("scidiscovery.unchanged-evidence-receipt.v1",),
                    max_bytes=512 * 1024,
                    usage="unchanged_set_receipt",
                ),
                ContextInputRule(
                    "revision_request",
                    "full",
                    required=False,
                    max_bytes=512 * 1024,
                    usage="change_request",
                ),
            ),
            allow_additional=True,
            additional_usages=("cached_excerpt",),
            max_inputs=9,
            max_readable_bytes=12 * 1024 * 1024,
        ),
    },
    default_profile="default",
)


_DEVICE_PARAMETER_DOWNSTREAM_RULES = (
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
)


EXPERIMENT_DESIGN_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "scidiscovery.experiment-design.revision.v1": _STRUCTURED_REVISION_POLICY,
        "scidiscovery.experiment-design.evidence-alignment-revision.v1": (
            _EXPERIMENT_DESIGN_EVIDENCE_REVISION_POLICY
        ),
        "scidiscovery.experiment-design.reviewed.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "research_objective",
                    "full",
                    schemas=("scidiscovery.research-objective.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
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
                ContextInputRule(
                    "figure_manifest",
                    "full",
                    required=False,
                    schemas=("scidiscovery.figure-evidence-manifest.v1",),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
                ContextInputRule(
                    "evidence_validation_report",
                    "full",
                    required=False,
                    schemas=("scidiscovery.figure-evidence-validation-report.v1",),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
            ) + _DEVICE_PARAMETER_DOWNSTREAM_RULES,
            allow_additional=False,
            max_inputs=12,
            max_readable_bytes=13 * 1024 * 1024,
        ),
        "scidiscovery.experiment-design.objective-bound.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "research_objective",
                    "full",
                    schemas=("scidiscovery.research-objective.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
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
                ContextInputRule(
                    "figure_manifest",
                    "full",
                    required=False,
                    schemas=("scidiscovery.figure-evidence-manifest.v1",),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
                ContextInputRule(
                    "evidence_validation_report",
                    "full",
                    required=False,
                    schemas=("scidiscovery.figure-evidence-validation-report.v1",),
                    max_bytes=1024 * 1024,
                    usage="evidence_inventory",
                ),
            ) + _DEVICE_PARAMETER_DOWNSTREAM_RULES,
            allow_additional=False,
            max_inputs=12,
            max_readable_bytes=13 * 1024 * 1024,
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


DIAGNOSTICIAN_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={
        "default": TaskContextPolicy(),
        "scidiscovery.diagnosis.tcad-result.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "experiment_plan",
                    "full",
                    schemas=("scidiscovery.experiment-portfolio.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "runtime_attestation",
                    "full",
                    schemas=("tcad.runtime-attestation.v1",),
                    max_bytes=512 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "control_equivalence_report",
                    "full",
                    schemas=("tcad.study-control-equivalence.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "metric_report",
                    "full",
                    schemas=("scidiscovery.curve-consistency-report.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "curve_bundle",
                    "full",
                    required=False,
                    schemas=("scidiscovery.curve-bundle.v1",),
                    max_bytes=8 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "curve_plot",
                    "full",
                    required=False,
                    schemas=("scidiscovery.curve-comparison-plot.v1",),
                    max_bytes=8 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "hypothesis_portfolio",
                    "on_demand",
                    required=False,
                    schemas=(
                        "scidiscovery.hypothesis-proposal.v1",
                        "scidiscovery.hypothesis-portfolio.v1",
                    ),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "scientific_foundation",
                    "on_demand",
                    required=False,
                    schemas=("scidiscovery.scientific-foundation.v1",),
                    max_bytes=2 * 1024 * 1024,
                    usage="claim_evidence",
                ),
            ),
            allow_additional=False,
            max_inputs=8,
            max_readable_bytes=26 * 1024 * 1024,
        ),
        "scidiscovery.diagnosis.revision.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "revised_object",
                    "full",
                    schemas=_REVISION_TARGET_SCHEMAS,
                    max_bytes=8 * 1024 * 1024,
                    usage="claim_evidence",
                ),
                ContextInputRule(
                    "revision_diff",
                    "full",
                    schemas=("scidiscovery.structured-revision-diff.v1",),
                    max_bytes=512 * 1024,
                    usage="change_request",
                ),
                ContextInputRule(
                    "prior_diagnosis",
                    "on_demand",
                    schemas=("scidiscovery.layered-diagnosis.v1",),
                    max_bytes=1024 * 1024,
                    usage="prior_signal",
                ),
                ContextInputRule(
                    "evidence_receipt",
                    "full",
                    schemas=("scidiscovery.unchanged-evidence-receipt.v1",),
                    max_bytes=512 * 1024,
                    usage="unchanged_set_receipt",
                ),
                ContextInputRule(
                    "revision_request",
                    "full",
                    required=False,
                    max_bytes=512 * 1024,
                    usage="change_request",
                ),
            ),
            allow_additional=True,
            additional_usages=("cached_excerpt",),
            max_inputs=9,
            max_readable_bytes=12 * 1024 * 1024,
        ),
        "scidiscovery.diagnosis.fig4-baseline-provenance.v1": TaskContextPolicy(
            rules=(
                ContextInputRule(
                    "target_curve_bundle",
                    "full",
                    schemas=("opaque",),
                    max_bytes=256 * 1024,
                ),
                ContextInputRule(
                    "target_metrics",
                    "full",
                    schemas=("opaque",),
                    max_bytes=64 * 1024,
                ),
                ContextInputRule(
                    "historical_profile",
                    "full",
                    schemas=("opaque",),
                    max_bytes=2 * 1024 * 1024,
                ),
                ContextInputRule(
                    "candidate_profile",
                    "full",
                    schemas=("opaque",),
                    max_bytes=2 * 1024 * 1024,
                ),
                ContextInputRule(
                    "historical_log",
                    "on_demand",
                    schemas=("opaque",),
                    max_bytes=1024 * 1024,
                ),
                ContextInputRule(
                    "candidate_log",
                    "on_demand",
                    schemas=("opaque",),
                    max_bytes=1024 * 1024,
                ),
                ContextInputRule(
                    "historical_manifest",
                    "full",
                    schemas=("opaque",),
                    max_bytes=128 * 1024,
                ),
                ContextInputRule(
                    "candidate_manifest",
                    "full",
                    schemas=("opaque",),
                    max_bytes=128 * 1024,
                ),
                ContextInputRule(
                    "historical_deck",
                    "on_demand",
                    schemas=("opaque",),
                    max_bytes=256 * 1024,
                ),
                ContextInputRule(
                    "candidate_project",
                    "on_demand",
                    schemas=("tcad.deck-project.v1",),
                    max_bytes=2 * 1024 * 1024,
                ),
                ContextInputRule(
                    "candidate_review",
                    "on_demand",
                    schemas=(
                        "scidiscovery.role-output.tcad-project-review.v1",
                    ),
                    max_bytes=512 * 1024,
                ),
                ContextInputRule(
                    "metric_report",
                    "full",
                    schemas=("opaque",),
                    max_bytes=512 * 1024,
                ),
                ContextInputRule(
                    "residual_report",
                    "full",
                    schemas=("opaque",),
                    max_bytes=2 * 1024 * 1024,
                ),
                ContextInputRule(
                    "project_diff",
                    "full",
                    schemas=("opaque",),
                    max_bytes=512 * 1024,
                ),
                ContextInputRule(
                    "evidence_audit",
                    "full",
                    schemas=("scidiscovery.decision-packet.v1",),
                    max_bytes=512 * 1024,
                ),
            ),
            allow_additional=False,
            max_inputs=15,
            max_readable_bytes=8 * 1024 * 1024,
        ),
    },
    default_profile="default",
)


__all__ = [
    "CRITIC_CONTEXT_POLICIES",
    "DIAGNOSTICIAN_CONTEXT_POLICIES",
    "EVIDENCE_AUDITOR_CONTEXT_POLICIES",
    "EXPERIMENT_DESIGN_CONTEXT_POLICIES",
    "SCIENTIFIC_REVISION_CONTEXT_POLICIES",
]
