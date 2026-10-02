"""Same-database detail authority with explicitly scoped transactional writes.

Managed control reads the current loop, plus an original loop when settling an
exact late thread. References count all retained rows; an ephemeral projection
describes which rows the caller may replace. Unread history is never deletion.
"""
import json
import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..schema.common import canonical_json


COLLECTIONS = {
    'human_continuations': list,
    'interactive_sessions': list,
    'admissions': dict,
    'usage_records': dict,
    'interactive_usage_records': dict,
    'loop_authorizations': dict,
}
SNAPSHOTS = frozenset({'decision_snapshot', 'processed_snapshot', 'notification_snapshot',
    'notified_snapshot', 'terminal_delivery'})
PROJECTION = '_detail_projection'
ACCOUNTING_PROJECTION = '_accounting_projection'


def history_cursor(position, *, secret):
    """Opaque read continuation; it grants no scheduling or management power."""
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError('Frozen history requires the configured local identity.')
    key = hashlib.sha256(b'scidiscovery.attempt-history.key.v1\0' + secret).digest()
    nonce = os.urandom(12)
    return base64.urlsafe_b64encode(nonce + AESGCM(key).encrypt(nonce,
        canonical_json(position), b'scidiscovery.attempt-history.v1')).rstrip(b'=').decode('ascii')


def read_history_cursor(cursor, *, secret, instance_id, state, limit):
    try:
        if type(secret) is not bytes or len(secret) < 32 or not 1 <= len(cursor) <= 2048:
            raise ValueError('invalid identity or cursor length')
        sealed = base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True)
        key = hashlib.sha256(b'scidiscovery.attempt-history.key.v1\0' + secret).digest()
        position = json.loads(AESGCM(key).decrypt(sealed[:12], sealed[12:],
            b'scidiscovery.attempt-history.v1'))
        if (position['version'] != 1 or position['instance_id'] != instance_id
                or position['state'] != state or position['limit'] != limit):
            raise ValueError('wrong history query')
        return position
    except (InvalidTag, ValueError, KeyError, TypeError, UnicodeError) as error:
        raise ValueError('Invalid history cursor; restart history or use the exact task navigation.') from error

DETAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_progression_details (
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    collection TEXT NOT NULL,
    record_key TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY(instance_id, collection, record_key)
);
CREATE INDEX IF NOT EXISTS progression_detail_loop ON scheduler_progression_details(
    instance_id, collection, json_extract(record_json,'$.loop_id'));
CREATE INDEX IF NOT EXISTS progression_detail_run ON scheduler_progression_details(
    instance_id, collection, json_extract(record_json,'$.run_id'));
CREATE INDEX IF NOT EXISTS progression_detail_sequence ON scheduler_progression_details(
    instance_id, collection, CAST(record_key AS INTEGER));
CREATE INDEX IF NOT EXISTS progression_detail_goal ON scheduler_progression_details(
    instance_id, collection, json_extract(record_json,'$.objective_ref.artifact_id'));
"""


def read_control_row(db, instance_id, *, schema='', usage_thread=None, extra_loop=None, full=False):
    return hydrate_control_row(db, db.execute('SELECT * FROM ' + schema + 'scheduler_progression '
        'WHERE instance_id=?', (instance_id,)).fetchone(), usage_thread=usage_thread,
        extra_loop=extra_loop, full=full, schema=schema)


def detail_record(db, instance_id, collection, key, *, schema=''):
    row = db.execute('SELECT record_json FROM ' + schema + 'scheduler_progression_details '
        'WHERE instance_id=? AND collection=? AND record_key=?', (instance_id, collection, key)).fetchone()
    return json.loads(row[0]) if row else None


def goal_admission_run(db, instance_id, name, objective, *, bindings):
    """One exact historical admission, its full goal and actual Run binding."""
    admission = detail_record(db, instance_id, 'admissions', name)
    if (not admission or admission.get('state') != 'accepted'
            or admission.get('objective_ref') != objective):
        return None
    run_id = bindings.resolve(instance=instance_id, namespace='run', name=name)
    return run_id if admission.get('run_id') == run_id else None


def goal_admissions(db, instance_id, objective, limit):
    """Bounded identities for old same-goal handoff; no historical JSON hydration."""
    rows = db.execute("SELECT record_key,json_extract(record_json,'$.run_id') AS run_id "
        "FROM scheduler_progression_details WHERE instance_id=? AND collection='admissions' "
        "AND json_extract(record_json,'$.objective_ref.artifact_id')=? "
        "AND json_extract(record_json,'$.objective_ref.sha256')=? "
        "AND json_extract(record_json,'$.state')='accepted' ORDER BY record_key LIMIT ?",
        (instance_id, objective['artifact_id'], objective['sha256'], limit + 1)).fetchall()
    return {item['record_key']: item['run_id'] for item in rows[:limit] if item['run_id']}, len(rows) > limit


def _capacity(checkpoint, identity, collection):
    from ...agent_execution_settings import progression_usage_capacity, require_progression_capacity
    settings = checkpoint['loop_authorizations'][identity]['config']['effective']
    require_progression_capacity(settings)
    return (settings['progression']['max_tasks'] + settings['progression']['max_reviews']
        if collection == 'admissions' else progression_usage_capacity(settings))


def hydrate_control_row(db, row, *, usage_thread=None, extra_loop=None, full=False, accounting_only=False, schema=''):
    """Accounting reads omit snapshots/history and can never be written back."""
    if row is None:
        return None
    row = dict(row)
    checkpoint = json.loads(row['checkpoint_json'])
    references = checkpoint.pop('detail_collections', {})
    if PROJECTION in checkpoint or ACCOUNTING_PROJECTION in checkpoint:
        raise ValueError('Persisted control projection is invalid; retain the original ledger.')
    projection = dict(counts=references, keys={}, scopes=[], offsets={})
    loaded_bytes = 0
    # Authorization history still has its separate frozen max_loop_scopes bound.
    # Read it first so each loop's own capacity governs its detail projection.
    if accounting_only and (full or extra_loop or usage_thread or not checkpoint.get('current_loop_id')):
        raise ValueError('Accounting projection requires one exact current research loop.')
    ordered = sorted((name for name in references if not accounting_only or name in
        {'loop_authorizations', 'admissions', 'usage_records'}), key=lambda name: name != 'loop_authorizations')
    scopes = {checkpoint.get('current_loop_id'), extra_loop} - {None}
    if usage_thread:
        original = detail_record(db, row['instance_id'], 'usage_records', usage_thread, schema=schema)
        if original and original.get('loop_id'):
            scopes.add(original['loop_id'])
    if not full and len(scopes) > 2:
        raise ValueError('Native usage identity conflicts across research loops; retain original bindings.')
    for collection in ordered:
        factory = COLLECTIONS[collection]
        count = references[collection]
        actual = db.execute('SELECT COUNT(*) FROM ' + schema + 'scheduler_progression_details '
            'WHERE instance_id=? AND collection=?', (row['instance_id'], collection)).fetchone()[0]
        if actual != count:
            raise ValueError('Control detail records differ from checkpoint reference.')
        query = 'SELECT record_key,record_json FROM ' + schema + 'scheduler_progression_details WHERE instance_id=? AND collection=?'
        args = [row['instance_id'], collection]
        managed = checkpoint.get('current_loop_id') is not None and not full
        if managed and collection in {'admissions', 'usage_records'}:
            if not scopes <= checkpoint.get('loop_authorizations', {}).keys():
                raise ValueError('Research loop authorization is missing; retain the original ledger.')
            query += " AND json_extract(record_json,'$.loop_id') IN (" + ','.join('?' for _ in scopes) + ')'
            args.extend(sorted(scopes))
            sizes = db.execute("SELECT json_extract(record_json,'$.loop_id'),COUNT(*),"
                'MAX(length(CAST(record_json AS BLOB))),SUM(length(CAST(record_json AS BLOB))) '
                'FROM ' + schema + 'scheduler_progression_details WHERE instance_id=? AND collection=? '
                "AND json_extract(record_json,'$.loop_id') IN (" + ','.join('?' for _ in scopes)
                + ") GROUP BY json_extract(record_json,'$.loop_id')", args).fetchall()
            for identity, size, maximum, _ in sizes:
                limits = checkpoint['loop_authorizations'][identity]['config']['effective']['progression']
                if size > _capacity(checkpoint, identity, collection) or maximum > limits['detail_record_bytes']:
                    raise ValueError('Research loop detail capacity reached; retain the original ledger.')
            loaded_bytes += sum(item[3] for item in sizes)
            if loaded_bytes > max(checkpoint['loop_authorizations'][identity]['config']['effective']['progression']['detail_read_bytes']
                    for identity in scopes):
                raise ValueError('Research loop detail read byte capacity reached; retain the original ledger.')
            # Query limits protect corrupted state too, before JSON is decoded.
            query += ' LIMIT ?'
            args.append(sum(_capacity(checkpoint, identity, collection) for identity in scopes) + 1)
        elif accounting_only and collection == 'loop_authorizations':
            query += ' AND record_key=?'
            args.append(checkpoint['current_loop_id'])
            limits = json.loads(row['config_json'])['effective']['progression']
            sizes = db.execute('SELECT length(CAST(record_json AS BLOB)) FROM ' + schema + 'scheduler_progression_details '
                'WHERE instance_id=? AND collection=? AND record_key=?', args).fetchone()
            if not sizes or sizes[0] > limits['detail_record_bytes']:
                raise ValueError('Research loop authorization is missing or exceeds its byte capacity.')
            loaded_bytes += sizes[0]
        elif managed and collection == 'interactive_usage_records':
            query += ' AND record_key=?'
            args.append(usage_thread or '')
        elif managed and factory is list:
            offset = max(0, count - 8)
            projection['offsets'][collection] = offset
            query += ' AND CAST(record_key AS INTEGER)>=? ORDER BY CAST(record_key AS INTEGER)'
            args.append(offset)
        records = db.execute(query, args).fetchall()
        values = {item['record_key']: json.loads(item['record_json']) for item in records}
        if managed and collection in {'admissions', 'usage_records'}:
            for identity in scopes:
                if sum(item.get('loop_id') == identity for item in values.values()) > _capacity(checkpoint, identity, collection):
                    raise ValueError('Research loop detail capacity reached; retain the original ledger.')
        if collection == 'loop_authorizations':
            limit = json.loads(row['config_json']).get('effective', {}).get('progression', {}).get('max_loop_scopes', 8)
            if (actual if accounting_only else len(values)) > limit:
                raise ValueError('Research loop authorization capacity reached; retain the original ledger.')
        if collection not in checkpoint:
            offset = projection['offsets'].get(collection, 0)
            checkpoint[collection] = ([values[str(index)] for index in range(offset, count)]
                if factory is list else values)
        projection['keys'][collection] = list(values)
    for name in ([] if accounting_only else checkpoint.pop('detail_snapshots', [])):
        if name not in SNAPSHOTS:
            raise ValueError('Unknown control snapshot reference.')
        record = detail_record(db, row['instance_id'], 'snapshot', name, schema=schema)
        # None is a valid snapshot value; distinguish a missing row.
        if record is None and not db.execute('SELECT 1 FROM ' + schema + 'scheduler_progression_details '
                'WHERE instance_id=? AND collection=? AND record_key=?',
                (row['instance_id'], 'snapshot', name)).fetchone():
            raise ValueError('Control snapshot is missing.')
        checkpoint.setdefault(name, record)
    if accounting_only:
        # Deliberately no writable projection metadata. Retain raw references
        # and an explicit marker so even replace=True cannot persist this view.
        checkpoint['detail_collections'] = references
        checkpoint[ACCOUNTING_PROJECTION] = True
    elif references:
        projection['scopes'] = sorted(scopes) if checkpoint.get('current_loop_id') and not full else None
        checkpoint[PROJECTION] = projection
        if checkpoint.get('current_loop_id') and not full:
            # These historical ordinary-session totals are projections of the
            # same rows, not budget authority or another persisted ledger.
            groups = {}
            for item in db.execute("SELECT json_extract(record_json,'$.role') AS role,"
                    "SUM(json_extract(record_json,'$.counted_tokens.input_tokens')) AS inputs,"
                    "SUM(json_extract(record_json,'$.counted_tokens.cached_input_tokens')) AS cached,"
                    "SUM(json_extract(record_json,'$.counted_tokens.output_tokens')) AS outputs,"
                    "SUM(json_extract(record_json,'$.outcome')='failed') AS failed,"
                    "SUM(json_extract(record_json,'$.has_gaps')) AS missing "
                    'FROM ' + schema + "scheduler_progression_details WHERE instance_id=? AND collection='interactive_usage_records' "
                    "GROUP BY json_extract(record_json,'$.role')", (row['instance_id'],)):
                groups[item['role']] = dict(tokens=dict(input_tokens=item['inputs'],
                    cached_input_tokens=item['cached'], output_tokens=item['outputs']),
                    failed_threads=item['failed'], unmeasured_threads=item['missing'])
            checkpoint['_interactive_usage_summary'] = dict(platform='codex', groups=groups,
                coverage='missing' if not groups else 'partial' if any(group['unmeasured_threads'] for group in groups.values()) else 'observed',
                individual_request_usage='unavailable')
            checkpoint['_interactive_tasks'] = db.execute('SELECT COUNT(*) FROM ' + schema + 'scheduler_progression_details '
                "WHERE instance_id=? AND collection='admissions' AND json_extract(record_json,'$.interactive_session_id') IS NOT NULL",
                (row['instance_id'],)).fetchone()[0]
    row['checkpoint_json'] = json.dumps(checkpoint)
    return row


def store_checkpoint(db, instance_id, checkpoint, *, replace=False):
    """Inside the control transaction; replace=True requires a complete caller view.

    Raw persisted references are never a complete view. Normal callers retain
    the projection metadata through JSON roundtrips. Initialization has no old
    references; maintenance may explicitly request a complete replacement.
    """
    if ACCOUNTING_PROJECTION in checkpoint:
        raise ValueError('Read-only accounting projection cannot be persisted.')
    compact = dict(checkpoint)
    compact.pop('_interactive_usage_summary', None)
    compact.pop('_interactive_tasks', None)
    projection = compact.pop(PROJECTION, None)
    persisted = db.execute('SELECT checkpoint_json FROM scheduler_progression WHERE instance_id=?',
        (instance_id,)).fetchone()
    old_references = json.loads(persisted[0]).get('detail_collections', {}) if persisted else {}
    if 'detail_collections' in compact or 'detail_snapshots' in compact:
        raise ValueError('Incomplete control detail projection; hydrate before writing.')
    if projection is None and old_references and not replace:
        raise ValueError('Incomplete control detail projection; retain metadata or explicitly replace a complete view.')
    if projection is not None:
        if not replace and any(collection not in compact for collection in old_references):
            raise ValueError('Incomplete control detail projection; retain every referenced collection before writing.')
        if (set(projection) != {'counts', 'keys', 'scopes', 'offsets'}
                or projection['counts'] != old_references or set(projection['keys']) != set(old_references)):
            raise ValueError('Incomplete control detail projection metadata; retain the original ledger.')
        if (not isinstance(projection['counts'], dict) or not isinstance(projection['keys'], dict)
                or not isinstance(projection['offsets'], dict)
                or (projection['scopes'] is not None and (not isinstance(projection['scopes'], list)
                    or not 1 <= len(projection['scopes']) <= 2))):
            raise ValueError('Incomplete control detail projection metadata; retain the original ledger.')
        if replace and projection['scopes'] is not None:
            raise ValueError('A scoped control projection cannot replace complete history.')
        for collection, count in old_references.items():
            if db.execute('SELECT COUNT(*) FROM scheduler_progression_details WHERE instance_id=? AND collection=?',
                    (instance_id, collection)).fetchone()[0] != count:
                raise ValueError('Control detail records differ from checkpoint reference.')
            keys = projection['keys'][collection]
            if not isinstance(keys, list) or len(set(keys)) != len(keys):
                raise ValueError('Incomplete control detail projection metadata; retain the original ledger.')
            if collection in {'admissions', 'usage_records'} and projection['scopes'] is not None:
                scopes = projection['scopes']
                expected = {item[0] for item in db.execute('SELECT record_key FROM scheduler_progression_details '
                    "WHERE instance_id=? AND collection=? AND json_extract(record_json,'$.loop_id') IN ("
                    + ','.join('?' for _ in scopes) + ')', (instance_id, collection, *scopes))}
            elif COLLECTIONS[collection] is list:
                expected = {str(index) for index in range(projection['offsets'].get(collection, 0), count)}
            elif collection == 'interactive_usage_records' and projection['scopes'] is not None:
                expected = {key for key in keys if db.execute('SELECT 1 FROM scheduler_progression_details '
                    'WHERE instance_id=? AND collection=? AND record_key=?', (instance_id, collection, key)).fetchone()}
            else:
                expected = {item[0] for item in db.execute('SELECT record_key FROM scheduler_progression_details '
                    'WHERE instance_id=? AND collection=?', (instance_id, collection))}
            if set(keys) != expected:
                raise ValueError('Incomplete control detail projection metadata; retain the original ledger.')
    references, details = {}, {}
    for collection, factory in COLLECTIONS.items():
        value = compact.pop(collection, factory())
        if not isinstance(value, factory):
            raise ValueError('Invalid control detail collection.')
        offset = projection['offsets'].get(collection, 0) if projection else 0
        records = {str(index + offset): item for index, item in enumerate(value)} if factory is list else value
        details[collection] = records
        if projection and projection['scopes'] is not None and collection in {'admissions', 'usage_records'}:
            for identity in {item.get('loop_id') for item in records.values()} - {None}:
                if sum(item.get('loop_id') == identity for item in records.values()) > _capacity(checkpoint, identity, collection):
                    raise ValueError('Research loop detail capacity reached; retain the original ledger.')
    snapshots = {name: compact.pop(name) for name in SNAPSHOTS if name in compact}
    details['snapshot'] = snapshots
    for collection, records in details.items():
        if projection and collection != 'snapshot' and not replace:
            previous = set(projection['keys'].get(collection, []))
        else:
            previous = {item[0] for item in db.execute('SELECT record_key FROM scheduler_progression_details '
                'WHERE instance_id=? AND collection=? AND (collection!=? OR record_key IN ('
                + ','.join('?' for _ in SNAPSHOTS) + '))', (instance_id, collection, 'snapshot', *SNAPSHOTS))}
        db.executemany('DELETE FROM scheduler_progression_details WHERE instance_id=? AND collection=? AND record_key=?',
            ((instance_id, collection, key) for key in previous - records.keys()))
        # Only immutable loop identities are needed for this guard. Keep its
        # complete scope check, without reading/decoding each old record body
        # through a separate query before the already conditional UPSERT.
        previous_loops = dict(db.execute("SELECT record_key,json_extract(record_json,'$.loop_id') "
            'FROM scheduler_progression_details WHERE instance_id=? AND collection=? '
            'AND record_key IN (SELECT value FROM json_each(?))',
            (instance_id, collection, json.dumps(list(records)))).fetchall()) if (
                collection in {'admissions', 'usage_records'} and not replace and records) else {}
        encoded = []
        for key, item in records.items():
            raw = json.dumps(item, sort_keys=True, allow_nan=False)
            if collection in {'admissions', 'usage_records'} and item.get('loop_id'):
                limits = checkpoint['loop_authorizations'][item['loop_id']]['config']['effective']['progression']
                if len(raw.encode()) > limits['detail_record_bytes']:
                    raise ValueError('Research loop detail record byte capacity reached; retain original records.')
            if collection in {'admissions', 'usage_records'} and not replace:
                if key in previous_loops and previous_loops[key] != item.get('loop_id'):
                    raise ValueError('Control detail identity cannot be reassigned across research loops.')
            encoded.append((instance_id, collection, key, raw))
        db.executemany('INSERT INTO scheduler_progression_details VALUES(?,?,?,?) '
            'ON CONFLICT(instance_id,collection,record_key) DO UPDATE SET record_json=excluded.record_json '
            'WHERE record_json != excluded.record_json',
            encoded)
        if collection != 'snapshot':
            count = db.execute('SELECT COUNT(*) FROM scheduler_progression_details '
                'WHERE instance_id=? AND collection=?', (instance_id, collection)).fetchone()[0]
            if count or collection in checkpoint:
                references[collection] = count
    # Bound each original loop before committing, including inserts that were
    # not among the original projection keys. Two loop reads then stay bounded.
    for identity in ({item.get('loop_id') for collection in ('admissions', 'usage_records')
            for item in details[collection].values()} - {None}):
        limits = checkpoint['loop_authorizations'][identity]['config']['effective']['progression']
        size = db.execute('SELECT COALESCE(SUM(length(CAST(record_json AS BLOB))),0) '
            'FROM scheduler_progression_details WHERE instance_id=? '
            "AND collection IN ('admissions','usage_records') AND json_extract(record_json,'$.loop_id')=?",
            (instance_id, identity)).fetchone()[0]
        if 2 * size > limits['detail_read_bytes']:
            raise ValueError('Research loop detail byte capacity reached; retain original records.')
    if references:
        compact['detail_collections'] = references
    if snapshots:
        compact['detail_snapshots'] = sorted(snapshots)
    value = json.dumps(compact, sort_keys=True, allow_nan=False)
    if len(value.encode()) > 65536:
        raise ValueError('Control checkpoint capacity reached; retain original records.')
    return value
