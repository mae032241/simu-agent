"""Original selection public view from commit 8a92b028; compatibility fixture only."""
from scidiscovery.research_loop.shortlist import _screen, _clip

DEFAULT_RULE = ('Default: best-ranked comparable member whose smoke is ok and audit passed (or audit unconfigured); '
    'else, when no audit passed, the best-ranked smoke-ok member whose audit did not fail (the submit audit still gates promotion). '
    'Failed or unknown smoke and failed audit never become the default.')


def public_table(root, mark):
    value = _screen(root, mark)
    default = value['default']['candidate_id']
    return dict(evaluation_key=_clip(value['evaluation_key'], 96), direction=value['direction'],
        evaluation_groups_omitted_count=value.get('evaluation_groups_omitted_count', 0),
        default=dict(candidate_id=default, basis=value['default']['basis']),
        rows=[dict(candidate_id=row['candidate_id'], public_metric=row['metric'], evaluation_version=_clip(row['evaluation_key'], 96),
                   comparable=row['rank'] is not None, rank=row['rank'], reasons=row['reasons'], smoke=row['smoke']['status'],
                   audit=row['audit']['status'], default=row['candidate_id'] == default) for row in value['rows']],
        rule=value['default']['rule'],
        fields='candidate_comparison.rows: every listed candidate in this order with key_risk and decision keep|replace; '
               'keep marks only the delivered candidate. A choice other than the default requires override '
               '(default_candidate, chosen_candidate, reason, evidence_steps: exact frozen node steps).')
