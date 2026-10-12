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
        public_audits=[dict(candidate_id=cid,status=audit_by_id.get(cid,'unknown')) for cid in list(candidates)[:16]],
        audits_omitted_count=max(0,len(candidates)-16),
        limitation='Observed proxy groups do not establish target weights or optimality. Public audit projections do not authorize delivery. Read existing T2 indexes for omitted originals; A owns applicability judgments.')
    for field, omitted in (('public_audits','audits_omitted_count'), ('unranked_ids','unranked_omitted_count'), ('proxy_highest','proxy_groups_omitted_count')):
        while len(_bytes(value)) > MAX_BRIEF_BYTES and value[field]:
            value[field].pop()
            value[omitted] += 1
    if len(_bytes(value)) > MAX_BRIEF_BYTES:
        raise ValueError('Selection fixed fields exceed brief bound')
    return value
