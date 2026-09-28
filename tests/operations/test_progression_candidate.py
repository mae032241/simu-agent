"""Acceptance retains old science but never selects an instance for the user."""
import sqlite3

import pytest

from scripts.accept_progression import require_existing_instance


def test_missing_candidate_does_not_create_state(tmp_path):
    root = tmp_path / 'missing'
    with pytest.raises(ValueError, match='Prepare an upgrade candidate'):
        require_existing_instance(root)
    assert not root.exists()


@pytest.mark.parametrize('instances', [0, 2])
def test_existing_state_is_required_without_implicit_selection(tmp_path, instances):
    (tmp_path / 'candidate.json').write_text('{}')
    path = tmp_path / 'state/database/scheduler-bindings.sqlite3'
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE scheduler_instances(instance_id); '
                         'CREATE TABLE scheduler_sessions(session_key, instance_id);')
        db.executemany('INSERT INTO scheduler_instances VALUES(?)', [(i,) for i in range(instances)])
    if instances:
        require_existing_instance(tmp_path)
    else:
        with pytest.raises(ValueError, match='no existing instance'):
            require_existing_instance(tmp_path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM scheduler_sessions').fetchall() == []
