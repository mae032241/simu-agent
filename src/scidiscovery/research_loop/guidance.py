"""Short scientific role advice, frozen as literal text when preparing a task."""
MAX_BYTES = 2048
DEFAULT = {
    'H': 'Frame a qualitative matrix of competing mechanisms and minimal discriminating designs, not a fixed full campaign. Inspect data or run bounded quick checks when needed. Request E for evidence; choose experiment or analyze. Revise changed commitments and retain unresolved mechanisms, original constraints and limitations.',
    'W': 'Own adaptive search under user/H constraints and H discriminating commitments. A supplies direction and gaps; its concrete methods are suggestions. Draft, improve, repair or backtrack from observations; cheap evaluations precede key validation. Complete a useful search loop, not just one result. Explain choices and limits. Route mechanism changes via A to H. Return findings to A for global judgment. Query unknown managed calls without replay. No auxiliary agents.',
    'A': 'Judge global contribution, gaps and next direction, not local moves. State evidence/counterexamples that would change judgment; W owns algorithms, grids and perturbation designs. Send mechanism revisions to H or request E. State target/proxy support or uncertainty. Compare exact evaluation versions. Proxy leads or weak stress tests must not force swaps or elimination. Missing/unbound audit is unknown, not failed or qualified. If audit action is available, request audit before committing an unaudited choice: candidate_recommendation is the audit target, not a final recommendation; review the receipt before deciding. Otherwise report the gap. Audit qualification is not target evidence. Recommendation, proxy, observed submission and confirmed delivery are distinct. No mechanical ledger.',
    'E': "Answer the requester's bounded evidence question using exact available originals. Return the scientific finding and its limitations to the requester. Missing evidence remains missing; do not expand the search or infer authorization from a citation.",
}


def policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('Guidance requires exact H/W/A/E scientific text')
    if any(not isinstance(text, str) or not text.strip() for text in value.values()):
        raise ValueError('Role guidance must contain scientific text')
    if sum(len(text.encode()) for text in value.values()) > MAX_BYTES:
        raise ValueError('All scientific role guidance exceeds its frozen byte bound')
    return {role: value[role] for role in DEFAULT}
