"""Pure projections of verified public selection facts; no execution authority."""
import json
import math

MAX_CANDIDATES = 4096
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_BRIEF_BYTES = 4096
RECORD_FIELDS = {'step', 'role', 'recommendation', 'coverage', 'candidates', 'current_candidate', 'actual_submission'}
CANDIDATE_FIELDS = {'id', 'label', 'evaluation_key', 'metric', 'direction', 'status'}


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def _public_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower().startswith('hidden') or key.lower() in {'reward', 'test_score'}:
                raise ValueError('non_public_field')
            _public_keys(item)
    elif isinstance(value, list):
        for item in value:
            _public_keys(item)


def _object(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Public fields differ from selection contract')


def _record(value):
    deferred = isinstance(value, dict) and 'audit_request' in value
    _object(value, RECORD_FIELDS | ({'audit_request'} if deferred else set()))
    if deferred and (value['audit_request'] is not True or value['role'] != 'A' or value['recommendation'] is not None):
        raise ValueError('An audit request defers candidate recommendation')


def _finite_metric(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _id(value):
    if not isinstance(value, str) or not value or len(value.encode()) > 160:
        raise ValueError('Invalid public candidate identity')


def public_inputs(records):
    """Discard private receipt/contexts; caller already verified sealed sources."""
    result = []
    for record in records:
        observation = record['observation']
        candidates = []
        if observation is not None:
            for item in observation['candidates']:
                # Explicit hidden columns must not silently disappear during projection.
                _public_keys({key: None for key in item})
                candidates.append({key: item[key] for key in CANDIDATE_FIELDS})
        actual = observation.get('actual_submission') if observation else None
        current = observation.get('current_candidate') if observation else None
        result.append(dict(step=record['step'], role=record['role'], recommendation=record['recommendation'],
            coverage=observation['coverage']['status'] if observation else None,
            candidates=candidates, current_candidate=dict(candidate_id=current['candidate_id']) if current else None,
            actual_submission=dict(candidate_id=actual['candidate_id'],
                artifact_retention=actual.get('artifact', {}).get('retention', 'unknown')) if actual else None,
            **(dict(audit_request=True) if record.get('audit_request') is True else {})))
    return result


def project(records, *, audits=(), delivery=None):
    """Report observed comparisons and authored judgments, never target optimality."""
    if not isinstance(records, list) or not isinstance(audits, (list, tuple)):
        raise ValueError('Public records and audits must be bounded sequences')
    for record in records:
        _record(record)
        if type(record['step']) is not int or record['step'] <= 0:
            raise ValueError('Invalid sealed record identity')
    _public_keys(records)
    _public_keys(list(audits))
    _public_keys(delivery)
    if len(_bytes(dict(records=records, audits=list(audits), delivery=delivery))) > MAX_INPUT_BYTES:
        raise ValueError('Public selection inputs exceed bound')
    candidates, steps, observations, authors = {}, set(), [], []
    for record in sorted(records, key=lambda row: row['step']):
        _record(record)
        step = record['step']
        if type(step) is not int or step <= 0 or step in steps or not isinstance(record['role'], str) or record['role'] not in {'H', 'W', 'A', 'E'}:
            raise ValueError('Invalid sealed record identity')
        steps.add(step)
        if record['coverage'] is not None and (not isinstance(record['coverage'], str) or record['coverage'] not in {'complete', 'partial', 'unavailable'}):
            raise ValueError('Invalid public coverage')
        if not isinstance(record['candidates'], list):
            raise ValueError('Candidates must be a bounded list')
        for item in record['candidates']:
            _object(item, CANDIDATE_FIELDS)
            _id(item['id'])
            if (not isinstance(item['label'], str) or len(item['label'].encode()) > 640
                or item['evaluation_key'] is not None and (not isinstance(item['evaluation_key'], str) or len(item['evaluation_key'].encode()) > 2048)
                or not isinstance(item['direction'], str) or item['direction'] not in {'min', 'max'} or not isinstance(item['status'], str) or item['status'] not in {'ok', 'failed', 'unknown'}
                or item['metric'] is not None and not _finite_metric(item['metric'])):
                raise ValueError('Invalid public evaluation fact')
            if item['id'] in candidates and candidates[item['id']] != item:
                raise ValueError('Observed candidate identity changed')
            candidates.setdefault(item['id'], dict(item))
        if len(candidates) > MAX_CANDIDATES:
            raise ValueError('Candidate count exceeds bound')
        for field in ('current_candidate', 'actual_submission'):
            value = record[field]
            if value is not None:
                _object(value, {'candidate_id'} | ({'artifact_retention'} if field == 'actual_submission' else set()))
                if value['candidate_id'] is not None:
                    _id(value['candidate_id'])
                if value['candidate_id'] is not None and value['candidate_id'] not in candidates:
                    raise ValueError('Public observation references unknown candidate')
                if field == 'actual_submission' and (not isinstance(value['artifact_retention'], str) or value['artifact_retention'] not in {'archived', 'digest_only', 'unavailable', 'unknown'}):
                    raise ValueError('Invalid public artifact retention')
        if record['coverage'] is not None:
            observations.append(record)
        elif record['candidates'] or record['current_candidate'] is not None or record['actual_submission'] is not None:
            raise ValueError('Missing observer coverage for public observation')
        if record['role'] == 'A':
            if record['recommendation'] is not None:
                _id(record['recommendation'])
            if record['recommendation'] is not None and record['recommendation'] not in candidates:
                raise ValueError('A recommended unknown candidate')
            if not record.get('audit_request'):
                authors.append(record)
        elif record['recommendation'] is not None:
            raise ValueError('Only sealed A supplies recommendation')
    groups, unranked = {}, []
    for item in candidates.values():
        if not item['evaluation_key']:
            unranked.append(item['id'])
            continue
        if item['status'] != 'ok' or item['metric'] is None:
            continue
        key = item['evaluation_key'], item['direction']
        previous = groups.get(key)
        better = previous is None or (item['metric'] > previous['metric'] if key[1] == 'max' else item['metric'] < previous['metric'])
        if better:
            groups[key] = dict(evaluation_key=key[0], direction=key[1], metric=item['metric'], candidate_ids=[item['id']])
        elif item['metric'] == previous['metric']:
            previous['candidate_ids'].append(item['id'])
    audit_by_id = {}
    for fact in audits:
        _object(fact, {'candidate_id', 'status', 'artifact_bound', 'leakage_flag'})
        cid = fact['candidate_id']
        _id(cid)
        if cid not in candidates or cid in audit_by_id or not isinstance(fact['status'], str) or fact['status'] not in {'completed', 'pending', 'skipped', 'failed', 'unknown'}:
            raise ValueError('Invalid verified public audit reference')
        if any(value is not None and type(value) is not bool for value in (fact['artifact_bound'], fact['leakage_flag'])):
            raise ValueError('Invalid public audit fact')
        audit_by_id[cid] = ('public_audit_passed' if fact['status'] == 'completed' and fact['artifact_bound'] is True and fact['leakage_flag'] is False
            else 'public_audit_failed' if fact['status'] == 'failed' or fact['leakage_flag'] is True else 'unknown')
    if delivery is None:
        delivery = dict(state='unknown', last_confirmed=None)
    _object(delivery, {'state', 'last_confirmed'})
    if not isinstance(delivery['state'], str) or delivery['state'] not in {'none', 'confirmed', 'failed', 'unknown'}:
        raise ValueError('Invalid delivery state')
    confirmed = delivery['last_confirmed']
    if confirmed is not None:
        _object(confirmed, {'candidate_id'})
        _id(confirmed['candidate_id'])
        if confirmed['candidate_id'] not in candidates:
            raise ValueError('Unknown confirmed delivery candidate')
    if delivery['state'] == 'confirmed' and confirmed is None:
        raise ValueError('Confirmed delivery lacks verified candidate')
    latest = authors[-1] if authors else None
    old = next((row for row in reversed(authors[:-1]) if row['recommendation'] is not None), None)
    actual = next((row for row in reversed(observations) if row['actual_submission'] is not None), None)
    alerts=[dict(candidate_id=item['id'],status=item['status']) for item in candidates.values() if item['status'] in {'failed','unknown'}]
    important=[latest['recommendation'] if latest else None,
        observations[-1]['current_candidate']['candidate_id'] if observations and observations[-1]['current_candidate'] else None,
        actual['actual_submission']['candidate_id'] if actual else None,
        confirmed['candidate_id'] if confirmed else None]
    preferred=set(cid for cid in important if cid is not None)
    alerts.sort(key=lambda row:row['candidate_id'] not in preferred)
    audit_ids=list(candidates)
    if len(audit_ids)>16:
        audit_ids.sort(key=lambda cid:0 if cid in preferred else 1 if audit_by_id.get(cid)=='public_audit_failed' else 2)
    proxy = []
    for group in groups.values():
        ids = group['candidate_ids']
        key = group['evaluation_key']
        proxy.append(dict(group, evaluation_key=key.encode()[:192].decode(errors='ignore'), evaluation_key_truncated=len(key.encode()) > 192,
                          candidate_ids=ids[:4], ties_omitted_count=max(0, len(ids)-4)))
    value = dict(scope='observed_only', target_best=None,
        coverage='partial' if any(row['coverage'] != 'complete' for row in observations) else 'complete' if observations else 'unknown',
        candidate_count=len(candidates), current_candidate=observations[-1]['current_candidate'] if observations else None,
        latest_a_step=latest['step'] if latest else None,
        a_recommended=dict(candidate_id=latest['recommendation'], author_step=latest['step']) if latest and latest['recommendation'] is not None else None,
        historical_a_recommendation=dict(candidate_id=old['recommendation'], author_step=old['step']) if old else None,
        observed_actual_submission=dict(actual['actual_submission'], observed_at=actual['step']) if actual else None,
        delivery=dict(state=delivery['state'], current_confirmed=confirmed if delivery['state']=='confirmed' else None, last_confirmed=confirmed),
        proxy_highest=proxy[:8], proxy_groups_omitted_count=max(0,len(proxy)-8),
        unranked_ids=unranked[:16], unranked_omitted_count=max(0,len(unranked)-16),
        public_audits=[dict(candidate_id=cid,status=audit_by_id.get(cid,'unknown')) for cid in audit_ids[:16]],
        audits_omitted_count=max(0,len(candidates)-16),
        candidate_alerts=alerts[:4],candidate_alerts_omitted_count=max(0,len(alerts)-4),
        failed_candidate_count=sum(item['status']=='failed' for item in candidates.values()),
        unknown_candidate_count=sum(item['status']=='unknown' for item in candidates.values()),
        limitation='Observed proxy groups do not establish target weights or optimality. Public audit projections do not authorize delivery. Read existing T2 indexes for omitted originals; A owns applicability judgments.')
    for field, omitted in (('proxy_highest','proxy_groups_omitted_count'), ('unranked_ids','unranked_omitted_count'), ('public_audits','audits_omitted_count')):
        while len(_bytes(value)) > MAX_BRIEF_BYTES and value[field]:
            value[field].pop()
            value[omitted] += 1
    while len(_bytes(value))>MAX_BRIEF_BYTES and value['candidate_alerts']:
        value['candidate_alerts'].pop()
        value['candidate_alerts_omitted_count']+=1
    if len(_bytes(value)) > MAX_BRIEF_BYTES:
        raise ValueError('Selection fixed fields exceed brief bound')
    return value


SHORTLIST_RULE = ('Rank completed candidates of one exact evaluation version by the declared public metric; '
    'equal metric ranks the later observed candidate first. Members: top-k, the current A recommendation and '
    'the best candidate first observed at or after the latest A assessment. Multiple versions require an explicit '
    'evaluation key; conflicting directions never rank. Without a ranking, retain bounded group bests for A.')
DEFAULT_RULE = ('Default: best-ranked comparable member whose smoke is ok or not provided and audit passed (or audit unconfigured); '
    'else, when no audit passed, the best-ranked such member whose audit is pending (the submit audit still gates promotion). '
    'Unavailable, failed or unknown smoke and failed, engineering-failed or unknown audit never become the default.')


def shortlist(records, k, *, evaluation_key=None):
    """Control default inputs from public facts only; no target optimality claim."""
    if type(k) is not int or not 1 <= k <= 8:
        raise ValueError('Shortlist size must be a small positive integer')
    if evaluation_key is not None and (not isinstance(evaluation_key, str) or not evaluation_key or len(evaluation_key.encode()) > 2048):
        raise ValueError('Selection evaluation key must be an exact public version')
    project(records)  # Identical public validation: no hidden columns, stable identities.
    items, first, order = {}, {}, {}
    for record in sorted(records, key=lambda row: row['step']):
        for item in record['candidates']:
            if item['id'] not in items:
                items[item['id']], first[item['id']], order[item['id']] = item, record['step'], len(order)
    reviews = [row for row in records if row['role'] == 'A']
    authors = [row for row in reviews if not row.get('audit_request')]
    assessed = max((row['step'] for row in reviews), default=None)
    recommended = max(authors, key=lambda row: row['step'])['recommendation'] if authors else None
    groups = {}
    for item in items.values():
        if item['status'] == 'ok' and item['metric'] is not None and item['evaluation_key']:
            groups.setdefault((item['evaluation_key'], item['direction']), []).append(item['id'])
    versions = {item['evaluation_key'] for item in items.values() if item['evaluation_key']}
    chosen_key = evaluation_key if evaluation_key is not None else next(iter(versions)) if len(versions) == 1 else None
    directions = {item['direction'] for item in items.values() if item['evaluation_key'] == chosen_key}
    version = (chosen_key, next(iter(directions))) if chosen_key is not None and len(directions) == 1 else None
    def rank(cid):
        item = items[cid]
        return (-item['metric'] if item['direction'] == 'max' else item['metric'], -order[cid])
    ranked = sorted(groups.get(version, []), key=rank)
    reasons = {}
    for cid in ranked[:k]:
        reasons.setdefault(cid, []).append('top_k')
    retained_groups = sorted(key for key in groups if evaluation_key is None or key[0] == evaluation_key) if version is None else []
    for key in retained_groups[:k]:
        reasons.setdefault(min(groups[key], key=rank), []).append('evaluation_group_best')
    if recommended is not None:
        reasons.setdefault(recommended, []).append('a_recommended')
    fresh = [cid for cid in ranked if assessed is None or first[cid] >= assessed]
    if fresh:
        reasons.setdefault(fresh[0], []).append('unassessed_best')
    members = [dict(candidate_id=cid, metric=items[cid]['metric'], evaluation_key=items[cid]['evaluation_key'],
                    direction=items[cid]['direction'], status=items[cid]['status'], first_step=first[cid],
                    rank=ranked.index(cid) + 1 if cid in ranked else None, reasons=value) for cid, value in reasons.items()]
    tail = ranked[k:]
    return dict(version=1, k=k, evaluation_key=chosen_key, direction=version[1] if version else None,
                candidate_count=len(items), ranked_count=len(ranked), latest_a_step=assessed, a_recommended=recommended,
                unassessed_count=len(fresh), boundary_ties_omitted=sum(items[cid]['metric'] == items[ranked[k - 1]]['metric'] for cid in tail),
                evaluation_groups_omitted_count=sum(not any(cid in reasons for cid in groups[key]) for key in retained_groups),
                members=members, rule=SHORTLIST_RULE)


def default_choice(members, statuses):
    """Pre-registered default over screened members; statuses map id -> smoke/audit status."""
    ranked = sorted((row for row in members if row['rank'] is not None), key=lambda row: row['rank'])
    usable = [row for row in ranked if statuses[row['candidate_id']]['smoke'] in {'ok', 'not_provided'}
              and statuses[row['candidate_id']]['audit'] in {'passed', 'unconfigured', 'not_run'}]
    passed = [row for row in usable if statuses[row['candidate_id']]['audit'] in {'passed', 'unconfigured'}]
    chosen, basis = ((passed[0], 'audit_passed' if statuses[passed[0]['candidate_id']]['audit'] == 'passed' else 'audit_unconfigured') if passed
                     else (usable[0], 'submit_audit_pending') if usable else (None, 'none_qualified'))
    return dict(candidate_id=chosen['candidate_id'] if chosen else None, basis=basis, rule=DEFAULT_RULE)
