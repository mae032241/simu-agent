"""Short scientific role advice, frozen as literal text when preparing a task."""
MAX_BYTES = 2560
DEFAULT = {
    'H': 'Choose W action explicitly: screen for combination shallow search; improve, repair or validate for one named mechanism. Order competing mechanisms scientifically; for each minimal_test give a falsifiable question/prediction and priority reason. W owns methods/grids; omit run counts/costs. Use bounded checks. Request E for evidence; choose experiment or analyze. Keep original constraints, limits and unresolved mechanisms.',
    'W': 'Choose methods within the frozen H combination; identify the scientific mechanism on each managed run (--mechanism). A methods are suggestions. Draft, improve, repair or backtrack. Screen cheaply before key validation; avoid weak-control batches without decision value, honoring original count requirements. For screen, report your own finding or concrete blocked reason for every assigned mechanism. Completed calls alone are insufficient; blocked or a needed A decision means partial. State scientific limits. Route mechanism changes via A to H. Report infeasible/deferred mechanisms to A; W cannot self-grant extra calls. Query unknown calls without replay. No auxiliary agents.',
    'A': 'Judge contribution and decisions; W owns methods. State what each proposed step could change in candidate choice, mechanism selection or compliance, and evidence that would change judgment. Honor required checks; stop repeated validation without such decision value. Return to H for a falsifiable solution to target gaps outside current mechanisms; retain uncertainty if no admissible resolution exists. Request E when needed. Compare exact evaluation versions; proxy leads or weak stress tests do not force swaps or elimination. Missing/unbound audit is unknown, not failed or qualified. Audit an unaudited choice before commitment when available; for audit, candidate_recommendation names its target. Review the receipt before deciding. Audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery remain distinct. Choose W action explicitly (screen/improve/repair/validate); local work does not repeat the whole combination. Call completion is not scientific screening; assess every relevant mechanism from its exact final W. No mechanical ledger.',
    'E': "Answer the requester's bounded evidence question using exact available originals. Return the scientific finding and its limitations to the requester. Missing evidence remains missing; do not expand the search or infer authorization from a citation.",
}

# A new frozen strategy chooses these literals explicitly. Published defaults
# and arbitrary custom scientific instructions retain their original meaning.
OPPORTUNITY = {
    **DEFAULT,
    'H': 'Choose W action explicitly: screen for combination shallow search; improve, repair or validate for one named mechanism. Order competing mechanisms by target gaps and opportunity cost; each minimal_test must state a discriminating prediction/question and priority reason. W owns methods/grids; omit counts/costs. Check data briefly. Request E as needed. Preserve original constraints, limits and unresolved commitments.',
    'W': 'Choose methods within the frozen H combination; identify the mechanism for each managed run (--mechanism). Take discriminating steps before deepening. Draft, improve, repair or backtrack from observations; report negative findings to A. Validate for a concrete decision, keeping required checks and independent review. Honor original counts; A methods are suggestions. Route mechanism changes via A to H. Report infeasible/deferred mechanisms to A; W cannot self-grant extra calls. Query unknown calls without replay. No auxiliary agents.',
    'A': 'Explain next directions and opportunity costs for the original goal; W owns methods. Each step needs a decision-changing question/criterion. Honor required checks; stop repetitive validation without decision value. Resolve target gaps outside current mechanisms through H; otherwise retain uncertainty. Compare exact evaluation versions; proxy leads or weak stress tests do not force swaps or elimination. Missing/unbound audit is unknown, not failed or qualified. Audit an unaudited choice before commitment when available; for audit, candidate_recommendation names its target. Review the receipt before deciding. Audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery remain distinct. In portfolio_review explain postponed alternatives when requested; an explained choice may remain. Choose W action explicitly (screen/improve/repair/validate); local work does not repeat the whole combination. Call completion is not scientific screening; assess every relevant mechanism from its exact final W. No mechanical ledger.',
}



def policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('Guidance requires exact H/W/A/E scientific text')
    if any(not isinstance(text, str) or not text.strip() for text in value.values()):
        raise ValueError('Role guidance must contain scientific text')
    if sum(len(text.encode()) for text in value.values()) > MAX_BYTES:
        raise ValueError('All scientific role guidance exceeds its frozen byte bound')
    return {role: value[role] for role in DEFAULT}
