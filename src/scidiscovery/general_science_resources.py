"""Immutable schemas, prompts, and semantic contracts for general science."""

from __future__ import annotations

import json

from .artifact_agent.schema.cognitive import CriticReview, EvidenceAudit, HypothesisProposal
from .artifact_agent.schema.research_cycle import ProblemFrame, ScientificFoundation, ScientificIntake
from .operation_declaration import (
    OPERATION_AGENT_PREAMBLE,
    schema_resource,
    scientific_semantic_contract,
)

EVIDENCE_PROMPT = """Return exactly one RoleResultEnvelope whose payload is the
ScientificIntake required by output.schema.json. Build a bounded ProblemFrame
and ScientificFoundation for only the assigned question. They must use the same
objective, and every problem-frame foundation reference must close over an item
in that foundation.

Use the exact assignment source_name as FoundationEvidence.source_key and in
every factual item's evidence_keys; do not invent aliases from filenames or the
local instruction. Preserve scope, conditions, units, uncertainty, conflicts,
assumptions, and open questions when supported. Paper facts, user definitions,
and runtime observations require exact supplied evidence; inference,
assumption, and speculation require an explicit rationale. Do not generalize
beyond the immutable inputs and do not copy whole source documents.

When the assignment includes a prior_draft and change_request, output/result.json
is a copy-on-write draft of that intake. Read it first, edit only the fields
required by the exact request, and complete the new handoff. Submit the entire
revised ScientificIntake, not a patch object; preserve unchallenged support and
do not inherit qualification.
"""


IDEATOR_PROMPT = """Return exactly one RoleResultEnvelope whose payload is the
HypothesisProposal required by output.schema.json. Propose a small ordered
portfolio of distinct, testable mechanisms for the supplied contradiction.
Copy the immutable global objective key into research_objective_key. Write only
the bounded goal of this hypothesis stage in stage_objective; never copy,
paraphrase, or replace the global research objective as if it were role-owned.
Each hypothesis must state its mechanism, bounded parameters, observable
predictions, explicit falsifiers, competitors, scope, and only the exact source
keys that support it. Creative hypotheses are allowed but are not established
facts. Prefer whole-response tests and few degrees of freedom; never select or
qualify a candidate.

When the assignment includes a prior_draft and change_request, output/result.json
is a copy-on-write draft of that portfolio. Read it first, edit only the fields
required by the exact critic request, and complete the new handoff. Submit the
entire revised HypothesisProposal, not a patch object; preserve the exact
hypothesis_key set and sound hypotheses, and do not inherit the critic verdict.
"""


CRITIC_PROMPT = """Return exactly one RoleResultEnvelope whose payload is the
CriticReview required by output.schema.json. Independently review every exact
hypothesis only for physical plausibility, logical falsifiability, and whether
at least one finite discriminating observation or computation can exist in
principle. Do not require numerical thresholds, extraction algorithms,
interpolation rules, or uncertainty propagation here; those belong to
experiment design. Record an issue once and give the smallest resolving action
only for an unresolved dimension. Also enforce the boundary of the qualified
scientific foundation: factual premises must be present there, inferences must
be labelled as inference, and missing inputs or historical observations must
not be restated as established mechanisms. Choose exactly one disposition. Use
ready_for_experiment when the mechanisms are sound and a finite discriminator
exists even though no discriminating result exists yet; revise_hypothesis only
for a defect in the mechanism statement; revise_evidence for a missing factual
premise; design_model_counterfactual when a bounded model computation is the
needed discriminator; inconclusive when no bounded resolving action is
currently available; and reject only for an irreparable failed mechanism.
Challenge mechanisms; do not design the
measurement algorithm, repeat source intake, grant qualification, select a
candidate, or demand that uncertainty be hidden by further prose.
"""


AUDITOR_PROMPT = """Return exactly one RoleResultEnvelope whose payload is the
EvidenceAudit required by output.schema.json. Audit whether the exact supplied
object's factual claims, values, conditions, structures, and conclusions are
supported by the immutable sources. Declare each source once, use one compact
check per material question, preserve conflicts and missing support, and cite
only exact task-local source aliases. Do not grant qualification or inherit a
prior verdict.

Judge the object's fidelity to the supplied sources, not whether those sources
are sufficient for a broader research objective. Use pass when a statement is
supported or faithfully preserves a source limitation, local gap, detection
limit, shared dependency, or unresolved identity. Use fail when the object
overstates support, hides a limitation, binds an identity incorrectly, or makes
an unsupported affirmative claim. Use unknown only when required material is
missing, unreadable, or cannot be compared. Use not_applicable only when the
declared check does not apply. A faithful statement that evidence is limited can
pass this audit without becoming qualified or scientifically sufficient.
"""


class Resources:
    opaque_schema = '{"$id":"opaque","type":["object","array","string","number","boolean","null"]}'
    intake_semantic_contract = scientific_semantic_contract(
        "intake",
        "Every factual foundation item must cite an exact supplied source key.",
        "Problem-frame references must close over the exact foundation item keys in this payload.",
        "A parameter item requires both a value and a unit; use dimensionless when applicable.",
        "A unit cannot exist without a value, and numeric uncertainty requires a unit.",
        "Paper facts, user definitions, and runtime observations require evidence keys; inference, assumption, and speculation require a rationale.",
        "Item, source, conflict, condition, evidence, and tag keys must be unique and every reference must close locally.",
        "Conflict resolution fields must match unresolved, resolved, or accepted-assumption status.",
        "A supplied objective contract must exactly match the foundation objective and reference only declared items.",
        "The payload may frame the bounded question but must not generalize beyond supplied evidence.",
        payload_rule_id="intake.internal_closure",
        context_rule_id="intake.source_binding",
    )
    hypothesis_semantic_contract = scientific_semantic_contract(
        "hypothesis",
        "research_objective_key references the immutable global objective; stage_objective is the role-authored bounded goal for this hypothesis action.",
        "A hypothesis Worker may not replace or paraphrase the global research objective.",
        "Hypothesis, prediction, falsifier, competitor, and evidence keys must be unique and closed.",
        "A bounded hypothesis revision preserves the complete hypothesis key set; adding, removing, or renaming a hypothesis requires a new proposal action.",
        "Every hypothesis must contain at least one falsifiable prediction and one explicit falsifier.",
        "Portfolio order is a proposal only and does not qualify or select a candidate.",
        payload_rule_id="hypothesis.portfolio_closure",
        context_rule_id="hypothesis.objective_binding",
    )
    critic_semantic_contract = scientific_semantic_contract(
        "critic",
        "The contextual validator requires exactly one review for every hypothesis in the bound portfolio.",
        "Every non-passing review dimension requires the smallest resolving action.",
        "The critic owns mechanism plausibility, falsifiability, and finite discriminability in principle; experiment design owns thresholds, extraction algorithms, and uncertainty propagation.",
        "The structured disposition is the scientific finding; only ready-for-experiment and model-counterfactual-design dispositions pass this review edge.",
        "The critic checks that factual premises stay inside the already qualified foundation and that inferences remain explicit.",
        "The disposition distinguishes unsupported premises from missing model counterfactuals without selecting a successor Operation.",
        "Current evidence need not already distinguish competitors when a finite discriminating action exists.",
        "Inconclusive is a valid terminal scientific result when no bounded resolving action is available.",
        payload_rule_id="critic.review_consistency",
        context_rule_id="critic.portfolio_binding",
    )
    evidence_audit_semantic_contract = scientific_semantic_contract(
        "evidence.audit",
        "Every evidence reference must close over the audit's declared exact source keys.",
        "Audit status measures whether the reviewed object is faithful to the exact sources, not whether those sources are sufficient for a broader objective or qualification.",
        "Pass applies to supported statements and to statements that faithfully preserve limitations, gaps, detection limits, shared dependencies, or unresolved identity.",
        "Fail applies to overstatement, hidden limitations, incorrect identity binding, or unsupported affirmative claims; unknown applies only when required material is missing, unreadable, or not comparable; not_applicable applies only when the check does not apply.",
        "The audit must contain a check; decisive pass or fail checks require evidence keys; fail maps to blocked, unknown to inconclusive, otherwise pass.",
        payload_rule_id="evidence.audit.check_consistency",
        context_rule_id="evidence.audit.source_binding",
    )
    scientific_intake_schema = schema_resource(
        ScientificIntake, "scidiscovery.scientific-intake.v1"
    )
    scientific_foundation_schema = schema_resource(
        ScientificFoundation, "scidiscovery.scientific-foundation.v1"
    )
    problem_frame_schema = schema_resource(ProblemFrame, "scidiscovery.problem-frame.v1")
    hypothesis_schema = schema_resource(
        HypothesisProposal, "scidiscovery.hypothesis-proposal.v2"
    )
    critic_review_schema = schema_resource(CriticReview, "scidiscovery.critic-review.v2")
    evidence_audit_schema = schema_resource(EvidenceAudit, "scidiscovery.evidence-audit.v1")

    evidence_prompt = OPERATION_AGENT_PREAMBLE + EVIDENCE_PROMPT
    ideator_prompt = OPERATION_AGENT_PREAMBLE + IDEATOR_PROMPT
    critic_prompt = OPERATION_AGENT_PREAMBLE + CRITIC_PROMPT
    auditor_prompt = OPERATION_AGENT_PREAMBLE + AUDITOR_PROMPT

WILDCARD_SCHEMA = json.dumps(
    {"$id": "*", "description": "Lineage-only input; payload is never exposed."},
    ensure_ascii=True,
    separators=(",", ":"),
    sort_keys=True,
)


class TransformResources:
    wildcard_schema = WILDCARD_SCHEMA


__all__ = ["Resources", "TransformResources"]
