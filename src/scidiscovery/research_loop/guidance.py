"""Short scientific role advice, frozen as literal text when preparing a task."""
MAX_BYTES = 2048
DEFAULT = {
    'H': 'Use exploratory latitude within the scientific scope. Choose competing mechanisms and minimal discriminating observations, not a fixed full campaign. Add or revise only changed commitments; retain prior limitations and unresolved mechanisms. Read original science through lineage pages. A name change or engineering repair does not create new evidence.',
    'W': 'Work within the frozen H scope and remaining node budget. Use the configured domain interface to select a new branch, improve a named parent or return to an earlier plan. Use each observed result to choose the next useful experiment; a cheap batch needs a scientific purpose. Explain why an improvement or repair can change a decision. Query exact status for unknown calls and do not replay; known failures permit reasoned repair within the original budget. No auxiliary agents in this phase.',
    'A': 'Judge global contribution from original findings. State target support, proxy-only support or uncertainty, with scope and limits. Compare metrics within their exact evaluation version. Proxy leads or weak stress tests must not force candidate swaps or elimination. Missing/unbound audit is unknown, not failed or qualified. If audit action is available, request audit before committing an unaudited choice: candidate_recommendation is the audit target, not a final recommendation; review the receipt before deciding. Otherwise report the qualification gap. Audit qualification is not target evidence. Under uncertainty discriminate or retain findings without claiming optimality. Recommendation, proxy, observed submission and confirmed delivery are distinct. Do not maintain a mechanical ledger.',
    'E': 'Answer the requester\'s bounded evidence question using exact available originals. Return the scientific finding and its limitations to the requester. Missing evidence remains missing; do not expand the search or infer authorization from a citation.',
}


def policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('Guidance requires exact H/W/A/E scientific text')
    if any(not isinstance(text, str) or not text.strip() for text in value.values()):
        raise ValueError('Role guidance must contain scientific text')
    if sum(len(text.encode()) for text in value.values()) > MAX_BYTES:
        raise ValueError('All scientific role guidance exceeds its frozen byte bound')
    return {role: value[role] for role in DEFAULT}
