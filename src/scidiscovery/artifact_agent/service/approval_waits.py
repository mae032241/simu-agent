"""Read durable approval intervals without mutating task deadlines or decisions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def parse_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def effective_deadline(value, events, approval_database_path, *, now=None):
    if not events:
        return value.deadline_at
    if approval_database_path is None:
        raise RuntimeError('Approval timing store is unavailable for this task')
    current = now or datetime.now(timezone.utc)
    cutoff = min(current, parse_time(value.completed_at)) if value.completed_at else current
    intervals = []
    with sqlite3.connect(Path(approval_database_path).as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        for event in events:
            approval_id = json.loads(event['diagnostic_json'])['approval_id']
            row = db.execute('''SELECT r.status,r.created_at,r.expires_at,r.closed_at,d.decided_at
                FROM approval_requests r LEFT JOIN approval_decisions d USING(approval_id)
                WHERE r.approval_id=?''', (approval_id,)).fetchone()
            if row is None:
                raise RuntimeError('Recorded task approval is unavailable')
            start = max(parse_time(event['recorded_at']), parse_time(row['created_at']))
            end = row['decided_at'] or row['closed_at']
            if end is None and row['status'] != 'pending':
                # Older administratively expired requests have no closing timestamp.
                end = row['expires_at'] or row['created_at']
            end = min(cutoff, parse_time(end)) if end else cutoff
            if row['expires_at']:
                end = min(end, parse_time(row['expires_at']))
            if end > start:
                intervals.append((start, end))
    # Union overlapping approvals: waiting for two people does not double credit.
    deadline = parse_time(value.deadline_at)
    covered_until = parse_time(value.created_at)
    for start, end in sorted(intervals):
        start = max(start, covered_until)
        if start > deadline:
            break  # An approval created after expiry cannot revive a task.
        if end > start:
            deadline += end - start
            covered_until = end
    return deadline.isoformat(timespec='microseconds').replace('+00:00', 'Z')
