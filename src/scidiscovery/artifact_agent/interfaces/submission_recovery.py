"""Administrator-only opt-in to remote retirement of legacy uncertain requests.

Not an MCP/Worker tool. This records the operator's assertion that every old
submitter has stopped; it does not change execution state or release any budget.
The ordinary cancel/abandon path must still obtain remote atomic retirement proof.
"""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3

from ..service.engineering_diagnostics import atomic_json, read_json
from ..service.execution_submission import ExecutionSubmission
from ..service.maintenance import StateMaintenanceLock


def authorize_legacy_retirement(state_root, execution_id, *, confirm_old_submitters_stopped, reason):
    if not confirm_old_submitters_stopped or not reason.strip() or len(reason) > 2048:
        raise ValueError("Confirm all old local/remote submitters have stopped and supply a bounded administrative reason")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", execution_id):
        raise ValueError("invalid execution identity")
    state = Path(state_root).expanduser().resolve(strict=True)
    directory = state / 'execution-exchange' / execution_id
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("execution exchange directory is unavailable")
    with StateMaintenanceLock(state / 'maintenance.lock', shared_group=True).exclusive(blocking=False):
        lock = ExecutionSubmission._lock(directory / 'submission.lock')
        if lock is None:
            raise RuntimeError("A local submitter still owns this execution; stop it before administrator recovery")
        try:
            with sqlite3.connect((state / 'database/executions.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
                row = db.execute('''SELECT e.state,e.external_run_id,p.descriptor_json
                    FROM executions e LEFT JOIN execution_prepared_submissions p USING(execution_id)
                    WHERE e.execution_id=?''', (execution_id,)).fetchone()
            if row is None or row[0] not in {'created', 'authorized'} or row[1] is not None or row[2] is None:
                raise ValueError("Only an unconfirmed prepared execution can enter legacy recovery")
            path = directory / 'submission.json'
            record = read_json(path) if path.exists() else {}
            descriptor = json.loads(row[2])
            if record.get('retirement_supported') is True:
                return {'execution_id': execution_id, 'state': 'retirement_already_enabled'}
            record.update(state='unknown', may_have_submitted=True, retirement_supported=True,
                administrator_recovery={
                    'recorded_at': datetime.now(timezone.utc).isoformat(), 'uid': os.getuid(),
                    'reason': reason, 'old_submitters_stopped': True,
                    'submission_sha256': descriptor['sha256']})
            atomic_json(path, record)
            return {'execution_id': execution_id, 'state': 'remote_retirement_required', 'budget_released': False}
        finally:
            os.close(lock)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--execution-id', required=True)
    parser.add_argument('--confirm-old-submitters-stopped', action='store_true', required=True)
    parser.add_argument('--reason', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(authorize_legacy_retirement(args.state_root, args.execution_id,
        confirm_old_submitters_stopped=args.confirm_old_submitters_stopped, reason=args.reason)))


if __name__ == '__main__':
    main()
