"""Approval lifetime, batched reads, backend isolation and public diagnostics."""
from datetime import timedelta
import json
import threading

import pytest

from tests.operations.test_approval_wait_recovery import clock, execution, policy
from tests.operations.test_experiment_approval_handoff import experiment, start
from scidiscovery.artifact_agent.service.approval_waits import parse_time


def test_pending_approval_cannot_extend_run_beyond_configured_total(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    time = clock(monkeypatch)
    io = f.runs.status(f.run_id).recovery_policy['execution_io']
    policy(f, execution_io={**io, 'approval_wait_budget_seconds': 3600})
    original = parse_time(f.runs.status(f.run_id).deadline_at)
    assert start(f)['state'] == 'awaiting_authorization'
    time.now += timedelta(hours=2)
    assert parse_time(f.runs.status(f.run_id).deadline_at) == original + timedelta(hours=1)
    time.now = original + timedelta(hours=1, seconds=1)
    assert f.runs.reconcile_expired_active(run_ids=(f.run_id,)) == 1


def test_delayed_wait_registration_credits_creation_time(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch)
    time = clock(monkeypatch)
    original = parse_time(f.runs.status(f.run_id).deadline_at)
    start(f)
    eid = execution(f).object_id
    with f.runs._connect() as db:
        db.execute("DELETE FROM run_activity WHERE run_id=? AND activity='approval_wait_started'", (f.run_id,))
    time.now += timedelta(hours=1)
    f.runs.record_approval_wait(f.run_id, 'apr_' + eid)
    assert parse_time(f.runs.status(f.run_id).deadline_at) == original + timedelta(hours=1)


def test_batch_status_opens_wait_stores_once(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import approval_waits
    f = experiment(tmp_path, monkeypatch)
    start(f)
    with f.runs._connect() as db:
        row = db.execute('SELECT * FROM runs WHERE run_id=?', (f.run_id,)).fetchone()
    connect = approval_waits.sqlite3.connect
    calls = []
    def observed(*args, **kwargs):
        calls.append(str(args[0]))
        return connect(*args, **kwargs)
    monkeypatch.setattr(approval_waits.sqlite3, 'connect', observed)
    statuses = f.runs._statuses_from_rows([row] * 20)
    assert len(statuses) == 20
    assert len(calls) == 2  # one activity query, one approval query
    assert all(status.deadline_at == statuses[0].deadline_at for status in statuses)


def test_distinct_backends_do_not_share_submission_slot(tmp_path, monkeypatch):
    from tests.operations.test_execution_submission import _ready, _wait
    from tests.operations.test_r4_execution_approval_identity import _create_effect, _decide_execution_approval
    from scidiscovery.artifact_agent.service.executions import ExecutionServiceError
    runtime, adapter, facade, root, first = _ready(tmp_path)
    _create_effect(root, name='other')
    _decide_execution_approval(runtime, root, name='other')
    second = facade._resolve('execution', 'other')
    bridge = facade.execution_bridge
    entered = {first: threading.Event(), second: threading.Event()}
    release = threading.Event()
    def slow(*, execution_id, **kwargs):
        entered[execution_id].set()
        assert release.wait(5)
    monkeypatch.setattr(bridge, 'start', slow)
    def launch(eid):
        bridge.submissions.start(execution_id=eid, scope='fixture', wait_seconds=0,
            on_authorization_required=None)
    try:
        launch(first)
        assert entered[first].wait(2)
        with pytest.raises(ExecutionServiceError, match='backend'):
            launch(second)
        with runtime.executions._connect() as db:
            db.execute('UPDATE executions SET executor=? WHERE execution_id=?', ('other_backend', second))
        bridge.adapters['other_backend'] = adapter
        launch(second)
        assert entered[second].wait(2)
    finally:
        release.set()
        _wait(lambda: bridge.submissions.summary(first).get('state') != 'pending')
        if entered[second].is_set():
            _wait(lambda: bridge.submissions.summary(second).get('state') != 'pending')


def test_public_diagnostics_hide_quoted_paths_and_source_literals(tmp_path):
    from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics
    store = EngineeringDiagnostics(tmp_path / 'diagnostics')
    private_path = '/tmp/private folder/秘密/model.cmd'
    secret_literal = 'source-literal-must-stay-private'
    try:
        exec(compile('raise RuntimeError("failure") # ' + secret_literal, private_path, 'exec'))
    except RuntimeError as error:
        error.stderr = ('File "' + private_path + '", line 1\n').encode()
        record = store.capture(error, scope='fixture', layer='execution', action='submit')
    for section in ('traceback', 'stderr', 'summary'):
        text = store.read(record['reference'], scopes=('fixture',), section=section)['text']
        assert private_path not in text and 'private folder' not in text and '秘密' not in text
        assert secret_literal not in text
    with pytest.raises(ValueError, match='another instance'):
        store.read(record['reference'], scopes=('foreign',), section='traceback')
