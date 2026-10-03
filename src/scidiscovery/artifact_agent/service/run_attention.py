"""Durable control issues, separate from the latest tool/form failure.

Stored in run_activity so existing archive/restore retains them. Only control
checks open/resolve issues; observing a notification does not resolve one.
"""
import json

from ..schema.common import canonical_json

SUBMISSION_CODES = frozenset({"submission_intervention_required", "submission_timeout_unclassified",
    "submission_state_unavailable"})
BINDING_CODES = frozenset({"experiment_implementation_ambiguous", "experiment_implementation_unavailable"})
ACTION = "Inspect this task with intent=status, diagnostic_after=0; preserve retained results and choose recovery. Do not repeat execution."


def record(runs, connection, run_id, *, scope, code, now):
    """An observation repeats a stable issue; code changes/recurrences notify again."""
    row = connection.execute("SELECT rowid, diagnostic_json FROM run_activity WHERE run_id=? "
        "AND activity='attention_state' AND json_extract(CAST(diagnostic_json AS TEXT),'$.scope')=? "
        "ORDER BY rowid DESC LIMIT 1", (run_id, scope)).fetchone()
    prior = json.loads(row['diagnostic_json']) if row else None
    if code is None and (prior is None or prior['state'] == 'resolved'):
        return
    same = prior and prior['state'] == 'open' and prior['code'] == code
    data = {'scope':scope, 'code':code or prior['code'], 'state':'open' if code else 'resolved',
        'first_seen_at':prior['first_seen_at'] if same or code is None else now,
        'last_seen_at':now, 'generation':prior['generation'] if same or code is None else None}
    # Repeated observations update only the projection row. Original errors remain
    # in their own append-only diagnostic records; notification generation is stable.
    if same:
        connection.execute("UPDATE run_activity SET diagnostic_json=? WHERE rowid=?",
            (canonical_json(data), row['rowid']))
        return
    event = runs._append_activity(connection, run_id, 'attention_state', now, canonical_json(data))
    if data['generation'] is None:
        data['generation'] = event
        connection.execute("UPDATE run_activity SET diagnostic_json=? WHERE rowid=?", (canonical_json(data), event))


def issues(connection, *, run_id=None, instance_id=None):
    predicate, values = ('a.run_id=?', (run_id,)) if run_id is not None else ('r.instance_id=?', (instance_id,))
    rows = connection.execute("SELECT a.run_id, a.diagnostic_json FROM run_activity a JOIN runs r ON r.run_id=a.run_id "
        "WHERE a.activity='attention_state' AND " + predicate + " AND NOT EXISTS (SELECT 1 FROM run_activity newer "
        "WHERE newer.run_id=a.run_id AND newer.activity='attention_state' AND newer.rowid>a.rowid "
        "AND json_extract(CAST(newer.diagnostic_json AS TEXT),'$.scope')="
        "json_extract(CAST(a.diagnostic_json AS TEXT),'$.scope')) ORDER BY a.rowid", values).fetchall()
    return [(row['run_id'], json.loads(row['diagnostic_json'])) for row in rows]


def projection(items):
    active = [item for item in items if item['state'] == 'open']
    if not active:
        return None
    # Never expose execution IDs, scope/bindings or engineering bodies to Root.
    return {'code':active[0]['code'], 'action':ACTION, 'total':len(active),
        'issues':[{'code':item['code'], 'first_seen_at':item['first_seen_at'],
            'last_seen_at':item['last_seen_at']} for item in active[:8]],
        'has_more':len(active)>8}


def migrate_running(runs, connection):
    """Retain pre-upgrade alerts, without interpreting bad aliases as missing bindings.

    Legacy events lack exact execution scopes. Keep their prior task-level alert
    until successful delivery; new execution observations use precise scopes.
    Resolved/new issues always take precedence over historical error records.
    """
    codes = sorted(SUBMISSION_CODES | {'experiment_implementation_ambiguous'})
    rows = connection.execute("SELECT a.run_id, json_extract(d.value,'$.code') AS code, "
        "MIN(a.recorded_at) AS first_seen, MAX(a.recorded_at) AS last_seen "
        "FROM run_activity a JOIN runs r ON r.run_id=a.run_id, "
        "json_each(CAST(a.diagnostic_json AS TEXT),'$.details') d "
        "WHERE r.state='running' AND a.activity IN ('tool_failed','output_rejected') "
        "AND json_extract(d.value,'$.code') IN (" + ','.join('?' for _ in codes) + ") "
        "AND NOT EXISTS (SELECT 1 FROM run_activity current WHERE current.run_id=a.run_id "
        "AND current.activity='attention_state' AND json_extract(CAST(current.diagnostic_json AS TEXT),'$.code')="
        "json_extract(d.value,'$.code')) GROUP BY a.run_id, code", codes).fetchall()
    for row in rows:
        scope = 'submission:' + row['code']
        record(runs, connection, row['run_id'], scope=scope, code=row['code'], now=row['first_seen'])
        if row['last_seen'] != row['first_seen']:
            record(runs, connection, row['run_id'], scope=scope, code=row['code'], now=row['last_seen'])
