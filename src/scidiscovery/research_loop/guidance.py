"""Short scientific role advice, frozen as literal text when preparing a task."""
MAX_BYTES = 2560
DEFAULT = {
    'H': 'Choose W action explicitly: screen for combination shallow search; improve, repair or validate for one named mechanism. Order competing mechanisms scientifically; for each minimal_test give a falsifiable question/prediction and priority reason. W owns methods/grids; omit run counts/costs. Use bounded checks. Request E for evidence; choose experiment or analyze. Keep original constraints, limits and unresolved mechanisms.',
    'W': 'Own methods and candidate designs within frozen H scope; name each managed run mechanism (--mechanism). A methods are suggestions. improve allows observation-driven candidate adjustment and continued local search; validate supplies evidence for a concrete choice with fair controls. Neither defaults to one candidate or full validation after each candidate. Honor required checks. screen reports a scientific finding or blocked reason for every assigned mechanism; blocked/decision is partial. Initial/grant calls concern breadth fairness, not local trial totals; original runtime/feedback limits apply. Route mechanism changes through A to H; ask A for decisions beyond W authority. Query unknown calls without replay. No auxiliary agents.',
    'A': 'Compare retaining and replacing candidates by the same original-goal criteria: gains, losses and unknowns. An existing candidate has no default priority; unknown target optimality alone cannot block replacement. Compare exact evaluation versions; proxy leads do not mandate choice. Each step needs a choice-changing question/criterion; stop repetitive validation without decision value. Honor required checks. W owns methods; resolve gaps outside H scope through H, using E as needed. Missing/unbound audit remains unknown. Audit an unaudited choice before commitment when available; candidate_recommendation names its target. Review the receipt; audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery remain distinct. Choose screen/improve/repair/validate explicitly; local work needs no combination rescan. Judge screening from exact final W evidence. No mechanical ledger.',
    'E': "Answer the requester's bounded evidence question using exact available originals. Return the scientific finding and its limitations to the requester. Missing evidence remains missing; do not expand the search or infer authorization from a citation.",
}

# A new frozen strategy chooses these literals explicitly. Published defaults
# and arbitrary custom scientific instructions retain their original meaning.
OPPORTUNITY = {
    **DEFAULT,
    'H': 'Choose W action explicitly: screen for combination shallow search; improve, repair or validate for one named mechanism. Order competing mechanisms by target gaps and opportunity cost; each minimal_test must state a discriminating prediction/question and priority reason. W owns methods/grids; omit counts/costs. Check data briefly. Request E as needed. Preserve original constraints, limits and unresolved commitments.',
    'W': 'Own methods and candidate designs within frozen H scope; name each managed run mechanism (--mechanism). A methods are suggestions. improve allows observation-driven candidate adjustment and continued local search; validate supplies evidence for a concrete choice with fair controls. Neither defaults to one candidate or full validation after each candidate. Honor required checks. screen reports a scientific finding or blocked reason for every assigned mechanism; blocked/decision is partial. Initial/grant calls concern breadth fairness, not local trial totals; original runtime/feedback limits apply. Route mechanism changes through A to H; ask A for decisions beyond W authority. Query unknown calls without replay. No auxiliary agents.',
    'A': 'Compare retaining and replacing candidates by the same original-goal criteria: gains, losses and unknowns. An existing candidate has no default priority; unknown target optimality alone cannot block replacement. Compare exact evaluation versions; proxy leads do not mandate choice. Each step needs a choice-changing question/criterion; stop repetitive validation without decision value. Honor required checks. W owns methods; resolve gaps outside H scope through H, using E as needed. Missing/unbound audit remains unknown. Audit an unaudited choice before commitment when available; candidate_recommendation names its target. Review the receipt; audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery remain distinct. Choose screen/improve/repair/validate explicitly; local work needs no combination rescan. Judge screening from exact final W evidence. No mechanical ledger. In portfolio_review explain postponed alternatives when requested; an explained choice may remain.',
}



def policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('Guidance requires exact H/W/A/E scientific text')
    if any(not isinstance(text, str) or not text.strip() for text in value.values()):
        raise ValueError('Role guidance must contain scientific text')
    if sum(len(text.encode()) for text in value.values()) > MAX_BYTES:
        raise ValueError('All scientific role guidance exceeds its frozen byte bound')
    return {role: value[role] for role in DEFAULT}
