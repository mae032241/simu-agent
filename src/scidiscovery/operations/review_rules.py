"""Independent review rules over verified identities, without storage or dispatch."""
from typing import Literal

ReviewVerdict = Literal['pass', 'revise', 'blocked', 'inconclusive']
REVIEW_INSTRUCTION = ('Assess only the exact supplied scientific subject and requested claims. '
    'Findings may question the science; unrequested templates and fixed diagnostic sequences are not pass conditions.')


def independence(authors, reviewers, *, authors_complete=True, reviewers_complete=True):
    if not authors_complete or not reviewers_complete:
        return 'unknown'
    return 'overlap' if set(authors) & set(reviewers) else 'independent'
