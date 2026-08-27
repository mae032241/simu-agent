"""Small advisory topologies for the interactive research scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scidiscovery.artifact_agent.schema.research_cycle import (
    ArtifactKind,
    ScientificReadiness,
)


TaskMode = Literal[
    "evidence_intake",
    "baseline_replay",
    "baseline_provenance",
    "deck_revision",
    "new_mechanism",
    "result_diagnosis",
]


@dataclass(frozen=True)
class TopologyAdvice:
    task_mode: TaskMode
    stages: tuple[tuple[str, ...], ...]
    human_reviews: tuple[str, ...]
    deterministic_steps: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class RoleRuntimeProfile:
    latency_class: Literal["fast", "standard", "creative"]
    timeout_seconds: int
    max_output_bytes: int


CapabilityKind = Literal["role", "deterministic_transform", "execution"]


@dataclass(frozen=True)
class CapabilitySpec:
    """Minimum data readiness for one action; this is not an ordered workflow."""

    name: str
    kind: CapabilityKind
    requires_all: tuple[ArtifactKind, ...]
    produces: tuple[ArtifactKind, ...]
    transform_profile: str | None = None


_ADVICE = {
    "evidence_intake": TopologyAdvice(
        task_mode="evidence_intake",
        stages=(("evidence_extractor",),),
        human_reviews=("scientific_foundation",),
        deterministic_steps=(),
        rationale="Freeze and review source-backed facts before scientific proposal work.",
    ),
    "baseline_replay": TopologyAdvice(
        task_mode="baseline_replay",
        stages=(
            ("tcad_deck_author",),
            ("tcad_deck_reviewer",),
            ("diagnostician",),
        ),
        human_reviews=("execution_authorization",),
        deterministic_steps=(
            "validate_deck_review",
            "package_deck_project",
            "attest_runtime",
        ),
        rationale="A frozen implementation replay does not require new hypothesis generation.",
    ),
    "baseline_provenance": TopologyAdvice(
        task_mode="baseline_provenance",
        stages=(("evidence_auditor",), ("diagnostician",)),
        human_reviews=(),
        deterministic_steps=("profile_inputs", "score_curves"),
        rationale="Audit provenance and deterministically rescore before proposing new physics.",
    ),
    "deck_revision": TopologyAdvice(
        task_mode="deck_revision",
        stages=(("tcad_deck_author",), ("tcad_deck_reviewer",)),
        human_reviews=(),
        deterministic_steps=(
            "diff_deck_project",
            "validate_deck_review",
        ),
        rationale=(
            "A reviewed implementation correction edits the prior project directly in "
            "a task-private deck sandbox, then receives an independent code review."
        ),
    ),
    "new_mechanism": TopologyAdvice(
        task_mode="new_mechanism",
        stages=(
            ("ideator", "evidence_auditor"),
            ("critic",),
            ("experiment_designer",),
            ("tcad_deck_author",),
            ("tcad_deck_reviewer",),
            ("diagnostician",),
        ),
        human_reviews=("scientific_foundation", "execution_authorization"),
        deterministic_steps=(
            "profile_inputs",
            "derive_candidate_eligibility",
            "materialize_experiment_plan",
            "validate_deck_review",
            "package_deck_project",
            "attest_runtime",
            "evaluate_control_equivalence",
            "score_curves",
            "derive_knowledge_update",
            "project_knowledge_state",
        ),
        rationale=(
            "A new mechanism needs independent creativity and criticism, then one "
            "author/reviewer implementation pair before execution and diagnosis."
        ),
    ),
    "result_diagnosis": TopologyAdvice(
        task_mode="result_diagnosis",
        stages=(("diagnostician",),),
        human_reviews=(),
        deterministic_steps=(
            "profile_inputs",
            "attest_runtime",
            "score_curves",
            "derive_knowledge_update",
            "project_knowledge_state",
        ),
        rationale="Diagnose supplied results first; create a new idea task only if the diagnosis calls for one.",
    ),
}


def advise_topology(task_mode: TaskMode) -> TopologyAdvice:
    """Return advisory stages; the scheduler may deviate with a stated reason."""

    try:
        return _ADVICE[task_mode]
    except KeyError as error:
        raise ValueError("unknown task mode") from error


_CAPABILITIES = (
    CapabilitySpec(
        "evidence_extractor",
        "role",
        (),
        ("scientific_intake",),
    ),
    CapabilitySpec(
        "split_scientific_intake",
        "deterministic_transform",
        ("scientific_intake",),
        ("problem_frame", "scientific_foundation"),
    ),
    CapabilitySpec(
        "project_research_objective",
        "deterministic_transform",
        ("scientific_foundation",),
        ("research_objective",),
        "scidiscovery.research-objective-project.v1",
    ),
    CapabilitySpec(
        "ideator",
        "role",
        ("problem_frame", "scientific_foundation"),
        ("hypothesis_portfolio",),
    ),
    CapabilitySpec(
        "evidence_auditor",
        "role",
        ("scientific_foundation",),
        ("evidence_audit",),
    ),
    CapabilitySpec(
        "critic",
        "role",
        ("hypothesis_portfolio", "scientific_foundation"),
        ("scientific_review",),
    ),
    CapabilitySpec(
        "derive_candidate_eligibility",
        "deterministic_transform",
        ("hypothesis_portfolio", "scientific_review", "evidence_audit"),
        ("candidate_eligibility",),
    ),
    CapabilitySpec(
        "experiment_designer",
        "role",
        ("research_objective", "hypothesis_portfolio", "candidate_eligibility"),
        ("experiment_design_intent",),
    ),
    CapabilitySpec(
        "materialize_experiment_plan",
        "deterministic_transform",
        (
            "experiment_design_intent",
            "research_objective",
            "hypothesis_portfolio",
            "candidate_eligibility",
        ),
        ("experiment_portfolio",),
        "scidiscovery.experiment-plan-materialize.v1",
    ),
    CapabilitySpec(
        "tcad_deck_author",
        "role",
        ("scientific_foundation", "experiment_portfolio"),
        ("tcad_project",),
    ),
    CapabilitySpec(
        "tcad_deck_reviewer",
        "role",
        ("tcad_project", "experiment_portfolio"),
        ("deck_review",),
    ),
    CapabilitySpec(
        "package_deck_project",
        "deterministic_transform",
        ("tcad_project", "deck_review", "experiment_portfolio"),
        ("packaged_project",),
    ),
    CapabilitySpec(
        "execute_project",
        "execution",
        ("packaged_project",),
        ("execution_result",),
    ),
    CapabilitySpec(
        "attest_runtime",
        "deterministic_transform",
        ("packaged_project", "execution_result"),
        ("runtime_attestation",),
    ),
    CapabilitySpec(
        "evaluate_control_equivalence",
        "deterministic_transform",
        ("experiment_portfolio", "packaged_project"),
        ("control_equivalence_report",),
        "tcad.control-equivalence.v1",
    ),
    CapabilitySpec(
        "score_curves",
        "deterministic_transform",
        ("experiment_portfolio", "execution_result", "runtime_attestation"),
        ("metric_report",),
        "scidiscovery.curve-score.v1",
    ),
    CapabilitySpec(
        "diagnostician",
        "role",
        (
            "experiment_portfolio",
            "execution_result",
            "runtime_attestation",
            "control_equivalence_report",
            "metric_report",
        ),
        ("layered_diagnosis",),
    ),
    CapabilitySpec(
        "diagnose_baseline_provenance",
        "role",
        ("evidence_audit", "metric_report"),
        ("layered_diagnosis",),
    ),
    CapabilitySpec(
        "derive_knowledge_update",
        "deterministic_transform",
        ("hypothesis_portfolio", "layered_diagnosis"),
        ("knowledge_state",),
    ),
)


def ready_capabilities(readiness: ScientificReadiness) -> tuple[CapabilitySpec, ...]:
    """Return all data-ready actions; the scheduler still chooses scientific order."""

    available = set(readiness.available_artifacts)
    candidates = tuple(
        item for item in _CAPABILITIES if set(item.requires_all).issubset(available)
    )
    if "experiment_design_intent" in available:
        candidates = tuple(
            item for item in candidates if item.name != "experiment_designer"
        )
    if "experiment_portfolio" in available:
        candidates = tuple(
            item
            for item in candidates
            if item.name not in {"experiment_designer", "materialize_experiment_plan"}
        )
    if readiness.execution_readiness not in {"ready", "authorized"}:
        candidates = tuple(item for item in candidates if item.kind != "execution")
    if readiness.objective_status == "blocked":
        blocked_actions = {
            "experiment_designer",
            "materialize_experiment_plan",
            "tcad_deck_author",
            "tcad_deck_reviewer",
            "package_deck_project",
            "execute_project",
        }
        candidates = tuple(
            item for item in candidates if item.name not in blocked_actions
        )
    return candidates


_ROLE_PROFILES = {
    "ideator": RoleRuntimeProfile("creative", 900, 65536),
    "experiment_designer": RoleRuntimeProfile("creative", 900, 65536),
    "tcad_deck_author": RoleRuntimeProfile("creative", 1200, 524288),
    "diagnostician": RoleRuntimeProfile("standard", 900, 131072),
    "critic": RoleRuntimeProfile("standard", 600, 32768),
    "evidence_auditor": RoleRuntimeProfile("standard", 600, 32768),
    "tcad_deck_reviewer": RoleRuntimeProfile("standard", 600, 65536),
}


def role_runtime_profile(role: str) -> RoleRuntimeProfile:
    return _ROLE_PROFILES.get(role, RoleRuntimeProfile("standard", 900, 65536))


__all__ = [
    "RoleRuntimeProfile",
    "CapabilityKind",
    "CapabilitySpec",
    "TaskMode",
    "TopologyAdvice",
    "advise_topology",
    "role_runtime_profile",
    "ready_capabilities",
]
