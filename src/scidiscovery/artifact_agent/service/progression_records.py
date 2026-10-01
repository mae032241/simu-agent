"""Same-database detail records behind the bounded active control checkpoint.

Callers retain the complete internal projection. Reads and writes share their
control transaction, so admission intent, scope identity and usage never diverge
from the active checkpoint. Public projections retain their own output bounds.
"""
import json


COLLECTIONS = {
    'human_continuations': list,
    'interactive_sessions': list,
    'admissions': dict,
    'usage_records': dict,
    'interactive_usage_records': dict,
}
SNAPSHOTS = frozenset({'decision_snapshot', 'processed_snapshot', 'terminal_delivery', 'human_handoff'})

DETAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_progression_details (
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    collection TEXT NOT NULL,
    record_key TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY(instance_id, collection, record_key)
);
"""


def hydrate_control_row(db, row):
    if row is None:
        return None
    row = dict(row)
    checkpoint = json.loads(row['checkpoint_json'])
    for collection, count in checkpoint.pop('detail_collections', {}).items():
        factory = COLLECTIONS[collection]
        records = db.execute('SELECT record_key,record_json FROM scheduler_progression_details '
            'WHERE instance_id=? AND collection=?', (row['instance_id'], collection)).fetchall()
        if len(records) != count:
            raise ValueError('Control detail records differ from checkpoint reference.')
        # Inline values are only supplied by trusted checkpoint replacement callers.
        # Normal persisted writes always remove them below.
        if collection not in checkpoint:
            values = {item['record_key']: json.loads(item['record_json']) for item in records}
            checkpoint[collection] = ([values[str(index)] for index in range(count)]
                if factory is list else values)
    for name in checkpoint.pop('detail_snapshots', []):
        if name not in SNAPSHOTS:
            raise ValueError('Unknown control snapshot reference.')
        record = db.execute('SELECT record_json FROM scheduler_progression_details '
            'WHERE instance_id=? AND collection=? AND record_key=?',
            (row['instance_id'], 'snapshot', name)).fetchone()
        if record is None:
            raise ValueError('Control snapshot is missing.')
        if name not in checkpoint:
            checkpoint[name] = json.loads(record['record_json'])
    row['checkpoint_json'] = json.dumps(checkpoint)
    return row


def store_checkpoint(db, instance_id, checkpoint):
    """Must run inside the caller's transaction; capacity failure rolls back details."""
    compact = dict(checkpoint)
    references = {}
    for collection, factory in COLLECTIONS.items():
        if collection not in compact:
            db.execute('DELETE FROM scheduler_progression_details WHERE instance_id=? AND collection=?',
                (instance_id, collection))
            continue
        value = compact.pop(collection)
        if not isinstance(value, factory):
            raise ValueError('Invalid control detail collection.')
        records = {str(index): item for index, item in enumerate(value)} if factory is list else value
        previous = {item[0] for item in db.execute('SELECT record_key FROM scheduler_progression_details '
            'WHERE instance_id=? AND collection=?', (instance_id, collection))}
        db.executemany('DELETE FROM scheduler_progression_details '
            'WHERE instance_id=? AND collection=? AND record_key=?',
            ((instance_id, collection, key) for key in previous - records.keys()))
        db.executemany('INSERT INTO scheduler_progression_details VALUES(?,?,?,?) '
            'ON CONFLICT(instance_id,collection,record_key) DO UPDATE SET record_json=excluded.record_json '
            'WHERE record_json != excluded.record_json',
            ((instance_id, collection, key, json.dumps(item, sort_keys=True, allow_nan=False))
                for key, item in records.items()))
        references[collection] = len(records)
    if references:
        compact['detail_collections'] = references
    snapshots = set()
    for name in SNAPSHOTS:
        if name not in compact:
            db.execute('DELETE FROM scheduler_progression_details '
                'WHERE instance_id=? AND collection=? AND record_key=?', (instance_id, 'snapshot', name))
            continue
        record = json.dumps(compact.pop(name), sort_keys=True, allow_nan=False)
        db.execute('INSERT INTO scheduler_progression_details VALUES(?,?,?,?) '
            'ON CONFLICT(instance_id,collection,record_key) DO UPDATE SET record_json=excluded.record_json '
            'WHERE record_json != excluded.record_json', (instance_id, 'snapshot', name, record))
        snapshots.add(name)
    if snapshots:
        compact['detail_snapshots'] = sorted(snapshots)
    value = json.dumps(compact, sort_keys=True, allow_nan=False)
    if len(value.encode()) > 65536:
        raise ValueError('Control checkpoint capacity reached; retain original records.')
    return value
