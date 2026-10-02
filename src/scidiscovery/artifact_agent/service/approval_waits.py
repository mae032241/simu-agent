"""Read durable approval intervals without mutating task deadlines or decisions."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
from ..storage.control_io import connect_database


def parse_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def approval_records(events, approval_database_path):
    if not events:
        return {}
    if approval_database_path is None:
        raise RuntimeError('Approval timing store is unavailable for this task')
    ids = list({json.loads(event['diagnostic_json'])['approval_id'] for event in events})
    with connect_database(Path(approval_database_path).as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""SELECT r.approval_id,r.status,r.created_at,r.expires_at,r.closed_at,d.decided_at
            FROM approval_requests r LEFT JOIN approval_decisions d USING(approval_id)
            WHERE r.approval_id IN (SELECT value FROM json_each(?))""", (json.dumps(ids),)).fetchall()
    return {row['approval_id']: row for row in rows}


def effective_deadline(value, events, approval_database_path, *, now=None, records=None):
    if not events:
        return value.deadline_at
    from ...agent_execution_settings import ExecutionIOSettings
    settings = ExecutionIOSettings.model_validate((value.recovery_policy or {}).get('execution_io', {}))
    budget = settings.approval_wait_budget_seconds
    if records is None:
        records = approval_records(events, approval_database_path)
    current = now or datetime.now(timezone.utc)
    cutoff = min(current, parse_time(value.completed_at)) if value.completed_at else current
    intervals = []
    for event in events:
        approval_id = json.loads(event['diagnostic_json'])['approval_id']
        row = records.get(approval_id)
        if row is None:
            raise RuntimeError('Recorded task approval is unavailable')
        # Approval creation is the control-owned start, not the next status poll.
        start = max(parse_time(value.created_at), parse_time(row['created_at']))
        end = row['decided_at'] or row['closed_at']
        if end is None and row['status'] != 'pending':
            end = row['expires_at'] or row['created_at']
        end = min(cutoff, parse_time(end)) if end else cutoff
        if row['expires_at']:
            end = min(end, parse_time(row['expires_at']))
        if end > start:
            intervals.append((start, end))
    # Union overlapping approvals, then cap total credit for this frozen Run.
    deadline = parse_time(value.deadline_at)
    covered_until = parse_time(value.created_at)
    for start, end in sorted(intervals):
        start = max(start, covered_until)
        if start > deadline or budget <= 0:
            break
        if end > start:
            seconds = min((end - start).total_seconds(), budget)
            deadline += timedelta(seconds=seconds)
            budget -= seconds
            covered_until = end
    return deadline.isoformat(timespec='microseconds').replace('+00:00', 'Z')
