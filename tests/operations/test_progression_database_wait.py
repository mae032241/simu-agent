"""Short SQLite contention waits share the existing observation/goal bounds."""
from contextlib import closing
import sqlite3
import time

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings
from scidiscovery.artifact_agent.storage.control_io import bounded_control_io, connect_database


@pytest.mark.parametrize('entry', ['execute', 'cursor', 'commit', 'exit'])
def test_each_sql_entry_refreshes_deadline_and_failed_commit_rolls_back(tmp_path, entry):
    path = tmp_path/'wait.sqlite3'
    with sqlite3.connect(path) as setup:
        setup.execute('CREATE TABLE sample(value INTEGER)')
        setup.execute('INSERT INTO sample VALUES(0)')
    with closing(sqlite3.connect(path, timeout=0)) as blocker:
        blocker.execute('BEGIN' if entry in {'commit', 'exit'} else 'BEGIN EXCLUSIVE')
        if entry in {'commit', 'exit'}:
            blocker.execute('SELECT * FROM sample').fetchall()
        deadline = time.monotonic()+.08
        with bounded_control_io(wait_seconds=lambda: .5, remaining_seconds=lambda: 1.):
            with closing(connect_database(path, timeout=30, deadline_monotonic=deadline)) as db:
                if entry in {'commit', 'exit'}:
                    db.execute('INSERT INTO sample VALUES(1)')
                time.sleep(.06)  # A connection/earlier statement cannot retain its original wait allowance.
                started = time.monotonic()
                with pytest.raises(sqlite3.OperationalError) as failure:
                    if entry == 'execute':
                        db.execute('SELECT * FROM sample').fetchall()
                    elif entry == 'cursor':
                        db.cursor().execute('SELECT * FROM sample').fetchall()
                    elif entry == 'commit':
                        db.commit()
                    else:
                        db.__exit__(None, None, None)
                assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
                assert time.monotonic()-started < .055
                if entry == 'exit':
                    assert not db.in_transaction  # SQLite's native __exit__ rolled the failed commit back.
                db.rollback()  # Expiry never prevents necessary cleanup.
        blocker.rollback()
    with sqlite3.connect(path) as verify:
        assert verify.execute('SELECT * FROM sample').fetchall() == [(0,)]


@pytest.mark.parametrize('value', [-.001, 1.001, float('inf'), float('nan')])
def test_administrator_sqlite_wait_has_finite_bounds(value):
    with pytest.raises(ValueError):
        ProgressionSettings(sqlite_busy_wait_seconds=value)
