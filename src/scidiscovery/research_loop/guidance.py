"""Short scientific role advice, frozen as literal text when preparing a task."""
MAX_BYTES = 2048
DEFAULT = {
    'H': 'Propose competing solution mechanisms for target-condition gaps with falsifiable minimal tests, not a fixed campaign. Use bounded data checks. Request E for evidence; choose experiment or analyze. Keep original constraints, limits and unresolved mechanisms.',
    'W': 'Own observation-driven search under user/H constraints and commitments; A methods are suggestions. Draft, improve, repair or backtrack. Screen cheaply before key validation; avoid weak-control batches without decision value, honoring original count requirements. Complete a useful search loop; state limits. Route mechanism changes via A to H. Query unknown managed calls without replay. No auxiliary agents.',
    'A': 'Judge global contribution and next decisions; W owns methods and grids. State what each proposed step could change in candidate choice, mechanism selection or compliance, and evidence that would change judgment. Honor required checks; stop repeated validation without such decision value. Return to H for a falsifiable solution to target gaps outside current mechanisms; retain uncertainty if no admissible resolution exists. Request E when needed. Compare exact evaluation versions; proxy leads or weak stress tests do not force swaps or elimination. Missing/unbound audit is unknown, not failed or qualified. Audit an unaudited choice before commitment when available; for audit, candidate_recommendation names its target. Review the receipt before deciding. Audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery remain distinct. No mechanical ledger.',
    'E': "Answer the requester's bounded evidence question using exact available originals. Return the scientific finding and its limitations to the requester. Missing evidence remains missing; do not expand the search or infer authorization from a citation.",
}

# A new frozen strategy chooses these literals explicitly. Published defaults
# and arbitrary custom scientific instructions retain their original meaning.
OPPORTUNITY = {
    **DEFAULT,
    'H': 'Rank competing solutions and explain exploration order by target gaps, proxy observability, minimal decision-changing tests and opportunity cost. Check data briefly. Request E as needed; choose experiment or analyze. Preserve original constraints, limits and unresolved commitments.',
    'W': 'Within user/H constraints, take short discriminating steps before deepening. Draft, improve, repair or backtrack from observations; return clear negative findings promptly to A. Validate for a concrete decision, keeping required checks and independent review. Honor original counts; A methods are suggestions. Explain limits; route mechanism changes via A to H. Query unknown managed calls without replay. No auxiliary agents.',
    'A': 'Rank next directions and explain opportunity costs for the whole portfolio and original goal; W owns methods. Each step needs a decision-changing question/criterion. Honor required checks; stop repetitive validation without decision value. Resolve target gaps outside current mechanisms through H; otherwise retain uncertainty. Compare exact evaluation versions; proxy leads or weak stress tests do not force swaps or elimination. Missing/unbound audit is unknown, not failed or qualified. Audit an unaudited choice before commitment when available; for audit, candidate_recommendation names its target. Review the receipt before deciding. Audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery remain distinct. In portfolio_review explain postponed alternatives when requested; an explained choice may remain. No mechanical ledger.',
}



def policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('Guidance requires exact H/W/A/E scientific text')
    if any(not isinstance(text, str) or not text.strip() for text in value.values()):
        raise ValueError('Role guidance must contain scientific text')
    if sum(len(text.encode()) for text in value.values()) > MAX_BYTES:
        raise ValueError('All scientific role guidance exceeds its frozen byte bound')
    return {role: value[role] for role in DEFAULT}
