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

Use the exact assignment source_name in every factual item's evidence_keys;
optional citation locators do not require a second source registration. Do not
invent aliases from filenames or the local instruction. Preserve scope, conditions, units, uncertainty, conflicts,
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

When feedback is bound, compare it with previous_hypotheses and the original
problem frame. Read relevant original results and sealed analyses on demand.
Distinguish observations, interpretations, numerical/implementation failures,
and evidence that can support or weaken a mechanism. New results need not be
repackaged into the old foundation. Explain changed or retained judgments in
contradiction/stage_objective with exact evidence; do not reproduce all history.
A new proposal may add, replace or remove hypotheses, or retain competitors when
indistinguishable. No new result forces a changed hypothesis set. If the current
model set is insufficient and no supported candidate can be delivered, report
the bounded gap without inventing a mechanism or inheriting an old review.

When the assignment includes a prior_draft and change_request, output/result.json
is a copy-on-write draft of that portfolio. Read it first, edit only the fields
required by the exact critic request, and complete the new handoff. Submit the
entire revised HypothesisProposal, not a patch object; preserve the exact
hypothesis_key set and sound hypotheses, and do not inherit the critic verdict.
Read rebound feedback relevant to that correction. Genuinely new evidence that
requires reorganizing candidates belongs to a new proposal, not this correction.
"""


CRITIC_PROMPT = """Return exactly one RoleResultEnvelope whose payload is the
CriticReview required by output.schema.json. Independently review every exact
hypothesis only for physical plausibility, logical falsifiability, and whether
at least one finite discriminating observation or computation can exist in
principle. Do not require numerical thresholds, extraction algorithms,
interpolation rules, or uncertainty propagation here; those belong to
experiment design. Record an issue once and give the smallest resolving action
only for an unresolved dimension. Also enforce the boundary of the qualified
scientific foundation and exact bound experimental feedback: factual premises
must have a supplied source, inferences must remain explicit, and simulated
observations are not independent measurements. Read the relevant originals as
needed; an author's analysis alone is not independent verification. Distinguish
implementation/numerical failure from mechanism counterevidence. A bound new
observation need not already occur in the original foundation. Missing inputs
or historical observations must not be restated as established mechanisms.
State missing originals and limit the affected judgment instead of passing
unsupported claims. Do not require the entire author input set to be repeated. Choose exactly one disposition. Use
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
supported by the immutable sources. Use one compact check per material question,
preserve conflicts and missing support, and cite
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
        "Item, conflict, and condition identities must be unambiguous. Item references close locally; source references resolve to bound inputs without a duplicated source ledger. References and tags may repeat; one source may have multiple citation locators.",
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
        "Hypothesis, parameter, prediction, and falsifier identities must be unambiguous. Competitor references close locally. Evidence references resolve to bound inputs or the exact foundation provenance without a copied source ledger; repeated references and multiple locators for one source are permitted.",
        "A bounded hypothesis revision preserves the complete hypothesis key set; adding, removing, or renaming a hypothesis requires a new proposal action.",
        "Every hypothesis must contain at least one falsifiable prediction and one explicit falsifier.",
        "Portfolio order is a proposal only and does not qualify or select a candidate.",
        payload_rule_id="hypothesis.portfolio_closure",
        context_rule_id="hypothesis.objective_binding",
    )
    critic_semantic_contract = scientific_semantic_contract(
        "critic",
        "The contextual validator requires exactly one review for every hypothesis in the bound portfolio.",
        "Report a bounded resolving action when one is known; an unresolved question does not require inventing a remedy. The critic judges the portfolio disposition rather than deriving it from every dimension status.",
        "The critic owns mechanism plausibility, falsifiability, and finite discriminability in principle; experiment design owns thresholds, extraction algorithms, and uncertainty propagation.",
        "The structured disposition is the scientific finding; only ready-for-experiment and model-counterfactual-design dispositions pass this review edge.",
        "The critic checks factual premises against the exact foundation or bound experimental feedback; simulations, measurements and interpretations remain distinct. A new bound observation need not appear in the old foundation; unavailable originals limit the judgment. Evidence may cite bound aliases or provenance registered in the exact foundation, without copying a source ledger.",
        "The disposition distinguishes unsupported premises from missing model counterfactuals without selecting a successor Operation.",
        "Current evidence need not already distinguish competitors when a finite discriminating action exists.",
        "Inconclusive is a valid terminal scientific result when no bounded resolving action is available.",
        payload_rule_id="critic.review_consistency",
        context_rule_id="critic.portfolio_binding",
    )
    evidence_audit_semantic_contract = scientific_semantic_contract(
        "evidence.audit",
        "Every evidence reference must identify an exact bound source; a duplicate source entry in the audit is not required.",
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
