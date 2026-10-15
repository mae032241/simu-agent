"""Control closeout shortlist: public facts, adapter smoke/audit screening, default.

Computed once per closeout boundary from sealed public observations. Each external
call is intent-before-outcome, never repeated when uncertain; receipts are
immutable files beside delivery originals, not a balance or mutable pointer.
The closeout A compares every member with the same fields and overrides the
pre-registered default only with a named, step-bound reason.
"""
from __future__ import annotations

import hashlib
import math

from . import budget, contracts as c, delivery, native, selection
from .candidate_audit import _save

DEFAULT = dict(version=1, shortlist_k=3, smoke_seconds=20)
CAPABILITY = 'smoke'


def policy(value):
    if (not isinstance(value, dict) or set(value) not in (set(DEFAULT), set(DEFAULT) | {'evaluation_key'})
            or type(value['version']) is not int or value['version'] != 1):
        raise ValueError('Selection policy requires version 1 shortlist size and smoke ceiling')
    seconds = value['smoke_seconds']
    if (type(value['shortlist_k']) is not int or not 1 <= value['shortlist_k'] <= 8
            or type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 600):
        raise ValueError('Selection shortlist size or smoke ceiling is out of bounds')
    key = value.get('evaluation_key')
    if key is not None and (not isinstance(key, str) or not key or len(key.encode()) > 2048):
        raise ValueError('Selection evaluation key must be an exact public version')
    return dict(value)


def configured(root):
    value = c.settings(root).get('selection_policy')
    return policy(value) if value is not None else None


def _directory(root):
    path = root / 'host-delivery/selection'
    if path.resolve() != path:
        raise ValueError('Control selection original location changed')
    return path


def _boundary(root, begin):
    return dict(seq=begin['seq'], sha256=c.digest(root / 'control-ledger' / f'{begin["seq"]:06d}.json'))


def _members(root, begin):
    from . import history
    records = selection.public_inputs(history.rebuild(root, begin['source_cutoff'] + 1, write_cache=False))
    try:
        limits = configured(root)
        return selection.shortlist(records, limits['shortlist_k'], evaluation_key=limits.get('evaluation_key'))
    except ValueError:  # Verified sources; only the optional public projection is unavailable.
        return dict(version=1, members=[], availability='public_projection_unavailable')


def _intents(root):
    directory = root / 'host-delivery/selection'
    return sorted(directory.glob('*.intent.json')) if directory.is_dir() else []


def calls(root):
    return len(_intents(root))


def blocked(root):
    for path in _intents(root):
        outcome = path.with_name(path.name.replace('.intent.json', '.outcome.json'))
        if not outcome.exists() or not c.read(c.regular(outcome))['cleanup_confirmed']:
            return True
    return False


def _affordable(root, begin, seconds):
    settings = c.settings(root)
    if budget.execution_blocked(root):
        return False
    floor = budget.closeout_floor(settings, preparation_seconds=begin['preparation_seconds'])
    author = settings['delivery_policy']['closeout_a']
    meter, limits = native.usage(root), budget.snapshot(root)
    pending = 0 if (root / 'jobs' / f'{begin["first_step"]:03d}.json').exists() else 1
    return (not meter['unknown_steps'] and limits['seconds_remaining'] > seconds + floor['seconds'] + author['max_seconds']
            and limits['max_tokens'] - meter['observed_tokens'] >= floor['tokens'] + author['max_observed_tokens']
            and settings['max_steps'] - budget.used_steps(root) >= 1 + pending + floor['steps'])


def _call(root, begin, index, kind, source, seconds):
    """Returns the immutable outcome, or None for an accepted call without one."""
    directory = _directory(root)
    name = f'{kind}-{index:02d}'
    intent_path, outcome_path = directory / (name + '.intent.json'), directory / (name + '.outcome.json')
    if outcome_path.exists():
        value = c.read(c.regular(outcome_path))
        if value['intent_sha256'] != c.digest(c.regular(intent_path)):
            raise ValueError('Control selection receipt differs from its accepted intent')
        return value
    if intent_path.exists():
        return None  # Never repeat an uncertain accepted call.
    budget.transition(root, 'advance', 'selection_' + kind)
    operation = hashlib.sha256(delivery._bytes(dict(settings_sha256=c.digest(root / 'settings.json'),
        closeout_begin=_boundary(root, begin), kind=kind, candidate_id=source['candidate_id'],
        artifact_sha256=source['objects']['artifact']['sha256']))).hexdigest()
    intent = dict(operation_id=operation, kind=kind, index=index, candidate_id=source['candidate_id'],
                  max_seconds=seconds, advance_seconds=budget.snapshot(root)['advance_seconds'])
    _save(intent_path, intent)
    def process(phase, identity):
        _save(directory / (name + '.process.json'), dict(operation_id=operation, phase=phase, identity=identity))
    try:
        result = delivery.leaf_phase(root, source, operation, kind, seconds, on_process=process)
    except delivery.DeliveryUnresolved as error:
        result = dict(status='unknown', note=error.code, cleanup_confirmed=error.code != 'delivery_cleanup_unknown')
    value = dict(intent_sha256=c.digest(intent_path), status=result['status'], note=result['note'].encode()[:1024].decode(errors='ignore'),
                 cleanup_confirmed=result['cleanup_confirmed'], leaf_output=delivery.leaf_refs(root, operation))
    _save(outcome_path, value)
    return value


def _prior_audits(root, sources):
    """A-requested receipts qualify only the exact same frozen artifact bytes."""
    from . import candidate_audit
    found = {}
    if not c.settings(root).get('candidate_audit_policy'):
        return found
    for _, outcome in candidate_audit.facts(root):
        if outcome is None or outcome.get('binding_sha256') is None:
            continue
        cid, status = outcome['candidate_id'], outcome['result']['status']
        source = sources.get(cid)
        if (status in {'audited', 'failed'} and source is not None and source['status'] == 'audit_pending'
                and outcome['result'].get('artifact_sha256') == source['objects']['artifact']['sha256']):
            found[cid] = 'failed' if status == 'failed' or found.get(cid) == 'failed' else 'passed'
    return found


def screen(root, begin):
    """Freeze shortlist, smoke and audit as affordable; None once screen.json exists."""
    directory = _directory(root)
    final = directory / 'screen.json'
    if final.exists():
        return None
    limits = configured(root)
    path = directory / 'shortlist.json'
    computed = dict(_members(root, begin), closeout_begin=_boundary(root, begin))
    if path.exists():
        if c.read(c.regular(path)) != computed:
            raise ValueError('Control shortlist differs from its sealed public prefix')
    else:
        _save(path, computed)
    sources = {row['candidate_id']: row for row in (begin.get('delivery_sources') or {}).get('items', [])}
    capable = CAPABILITY in (begin.get('delivery_sources') or {}).get('capabilities', [])
    if (begin.get('delivery_sources') or {}).get('catalogue'):
        sources = {}
        for member in computed['members']:
            try:
                refs = delivery.selected_sources(root, begin['delivery_sources'], member['candidate_id'], prepare=True)
            except delivery.DeliveryUnresolved as error:
                if error.code == 'delivery_cleanup_unknown':
                    raise
                return 'closeout_preparation_unavailable'
            sources.update({row['candidate_id']: row for row in refs['items']})
            capable = capable or CAPABILITY in refs.get('capabilities', [])
    settings = c.settings(root)
    audit_on = bool(settings.get('candidate_audit_policy')) and settings['delivery_policy']['adapter'] is not None
    rows = []
    for index, member in enumerate(computed['members']):
        source = sources.get(member['candidate_id'])
        smoke = dict(status='unavailable', note='plugin_smoke_unavailable')
        if source is None or source['status'] != 'audit_pending':
            smoke = dict(status='unavailable', note='candidate_original_unavailable')
        elif capable:
            if (directory / f'smoke-{index:02d}.intent.json').exists() or _affordable(root, begin, limits['smoke_seconds']):
                outcome = _call(root, begin, index, 'smoke', source, limits['smoke_seconds'])
                if outcome is None or not outcome['cleanup_confirmed']:
                    return 'selection_smoke_unknown'
                smoke = dict(status=outcome['status'], note=outcome['note'], receipt=f'smoke-{index:02d}')
            else:
                smoke = dict(status='unknown', note='selection_reserve_unavailable')
        rows.append(dict(member, smoke=smoke, audit=dict(status='unconfigured', note='audit_unconfigured')))
    prior = _prior_audits(root, sources) if audit_on else {}
    found = False
    for index, row in sorted(enumerate(rows), key=lambda pair: (pair[1]['rank'] is None, pair[1]['rank'] or 0)):
        if not audit_on:
            continue
        cid = row['candidate_id']
        if cid in prior:
            row['audit'] = dict(status=prior[cid], note='a_requested_receipt')
        elif row['rank'] is None or row['smoke']['status'] != 'ok':
            row['audit'] = dict(status='not_run', note='not_comparable' if row['rank'] is None else 'smoke_not_ok')
        elif found:
            row['audit'] = dict(status='not_run', note='below_audited_default')
        elif (directory / f'audit-{index:02d}.intent.json').exists() or _affordable(root, begin, settings['delivery_policy']['submit_seconds']):
            outcome = _call(root, begin, index, 'audit', sources[cid], settings['delivery_policy']['submit_seconds'])
            if outcome is None or not outcome['cleanup_confirmed']:
                return 'selection_audit_unknown'
            row['audit'] = dict(status={'audited': 'passed', 'failed': 'failed'}.get(outcome['status'], 'unknown'),
                                note=outcome['note'], receipt=f'audit-{index:02d}')
        else:
            row['audit'] = dict(status='not_run', note='selection_reserve_unavailable')
        found = found or row['audit']['status'] == 'passed'
    receipts = {}
    for row in rows:
        for kind in ('smoke', 'audit'):
            name = row[kind].get('receipt')
            if name is not None:
                receipts[name] = c.digest(c.regular(directory / (name + '.outcome.json')))
    value = dict(version=1, shortlist_sha256=c.digest(path), closeout_begin=computed['closeout_begin'],
                 smoke_capability=capable, audit_configured=audit_on, rows=rows, receipts=receipts,
                 evaluation_key=computed.get('evaluation_key'), direction=computed.get('direction'),
                 evaluation_groups_omitted_count=computed.get('evaluation_groups_omitted_count', 0),
                 default=selection.default_choice(rows, {row['candidate_id']: dict(smoke=row['smoke']['status'],
                     audit=row['audit']['status']) for row in rows}))
    _save(final, value)
    return None


def marker(root):
    path = root / 'host-delivery/selection/screen.json'
    if not path.exists() or not c.read(c.regular(path))['rows']:
        return None
    return dict(version=1, sha256=c.digest(path))


def _screen(root, mark):
    directory = _directory(root)
    path = directory / 'screen.json'
    if c.digest(c.regular(path)) != mark['sha256']:
        raise ValueError('Control selection screen changed')
    value = c.read(path)
    if value['shortlist_sha256'] != c.digest(c.regular(directory / 'shortlist.json')) or any(
            c.digest(c.regular(directory / (name + '.outcome.json'))) != digest for name, digest in value['receipts'].items()):
        raise ValueError('Control selection receipts changed')
    return value


def _clip(text, size):
    return text.encode()[:size].decode(errors='ignore') if isinstance(text, str) else text


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


def summary(root):
    path = root / 'host-delivery/selection/screen.json'
    if not path.exists():
        return None
    value = c.read(c.regular(path))
    return dict(default=value['default']['candidate_id'], basis=value['default']['basis'],
                members=[dict(candidate_id=row['candidate_id'], smoke=row['smoke']['status'], audit=row['audit']['status'])
                         for row in value['rows']])


def schema():
    row = dict(type='object', properties=dict(candidate_id=dict(type='string', maxLength=80),
        key_risk=dict(type='string', minLength=1, maxLength=512), decision=dict(type='string', enum=['keep', 'replace'])),
        required=['candidate_id', 'key_risk', 'decision'], additionalProperties=False)
    override = dict(type=['object', 'null'], properties=dict(default_candidate=dict(type=['string', 'null'], maxLength=80),
        chosen_candidate=dict(type='string', maxLength=80), reason=dict(type='string', minLength=1, maxLength=1024),
        evidence_steps=dict(type='array', minItems=1, maxItems=8, items=dict(type='integer', minimum=1))),
        required=['default_candidate', 'chosen_candidate', 'reason', 'evidence_steps'], additionalProperties=False)
    return dict(type=['object', 'null'], properties=dict(rows=dict(type='array', maxItems=10, items=row), override=override),
        required=['rows', 'override'], additionalProperties=False,
        description='Closeout comparison over closeout.comparison rows; null only when requesting audit.')


def choice(root, job, payload):
    """Effective delivery choice, or DeliveryUnresolved for an asymmetric/unbound table."""
    value = _screen(root, job['selection'])
    members = [row['candidate_id'] for row in value['rows']]
    default = value['default']['candidate_id']
    table = payload.get('candidate_comparison')
    if table is None:
        raise delivery.DeliveryUnresolved('selection_comparison_missing')
    rows = table['rows']
    if [row['candidate_id'] for row in rows] != members or any(not row['key_risk'].strip() for row in rows):
        raise delivery.DeliveryUnresolved('selection_comparison_asymmetric')
    chosen = payload.get('candidate_recommendation')
    chosen = default if chosen is None else chosen
    if chosen is None:
        raise delivery.DeliveryUnresolved('delivery_no_decision')
    if [row['candidate_id'] for row in rows if row['decision'] == 'keep'] != ([chosen] if chosen in members else []):
        raise delivery.DeliveryUnresolved('selection_keep_mismatch')
    override = table['override']
    if chosen == default:
        if override is not None:
            raise delivery.DeliveryUnresolved('selection_override_unneeded')
        return chosen
    steps = {row['step'] for row in job['history']['nodes']}
    if (override is None or override['default_candidate'] != default or override['chosen_candidate'] != chosen
            or not override['reason'].strip() or not set(override['evidence_steps']) <= steps):
        raise delivery.DeliveryUnresolved('selection_override_unbound')
    return chosen
