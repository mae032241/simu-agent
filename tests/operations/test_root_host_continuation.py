import json
import sqlite3

import pytest

from scripts import probe_root_host_live as live
from scripts.root_host_usage import audit


def database(path, sql):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(sql)


def test_explicit_next_task_requires_terminal_work_and_completed_root(tmp_path):
    database(tmp_path / 'state/database/runs.sqlite3', "CREATE TABLE runs(state); INSERT INTO runs VALUES('completed');")
    database(tmp_path / 'state/database/executions.sqlite3', 'CREATE TABLE executions(state);')
    task = tmp_path / 'task.txt'
    task.write_text('A new explicit task')
    live.write(tmp_path / 'progress.json', {'state': 'scientific_turn'})
    with pytest.raises(ValueError, match='completed prior'):
        live.continuation_task(tmp_path, task)
    live.write(tmp_path / 'progress.json', {'state': 'root_returned_requires_sealed_audit'})
    assert live.continuation_task(tmp_path, task) == task.read_text()
    database(tmp_path / 'state/database/executions.sqlite3', "INSERT INTO executions VALUES('submitted');")
    with pytest.raises(ValueError, match='unfinished'):
        live.continuation_task(tmp_path, task)


def test_real_notification_reduction_persists_control_attribution_and_resume_delta(tmp_path):
    database(tmp_path / 'state/database/runs.sqlite3', """
        CREATE TABLE runs(run_id,state);
        INSERT INTO runs VALUES('run-1','failed');
        CREATE TABLE worker_connections(run_id,thread_id,platform_session);
        INSERT INTO worker_connections VALUES('run-1','child','root');
        CREATE TABLE worker_participants(run_id,thread_id,platform_session);
    """)
    prior = tmp_path / 'live'
    prior.mkdir()
    live.write(tmp_path / 'progress.json', {'state': 'root_returned_requires_sealed_audit'})
    def totals(n): return {'inputTokens': n, 'cachedInputTokens': 0, 'outputTokens': n // 10}
    live.write(prior / 'usage.json', {'threads': {'root': totals(100)}})
    evidence = tmp_path / 'resume'
    (evidence / 'fixture-logs').mkdir(parents=True)
    live.write(evidence / 'thread.json', {'thread_id': 'root', 'session_id': 'root'})
    live.write(evidence / 'task-source.json', {'prior_evidence': str(prior)})
    events = [{'method': 'thread/tokenUsage/updated', 'params': {'threadId': thread, 'tokenUsage': {'total': totals(n)}}}
              for thread, n in [('root', 100), ('root', 140), ('root', 140), ('child', 60), ('unknown', 20)]]
    (evidence / 'fixture-logs/events.log').write_text(''.join(json.dumps(e) + '\n' for e in events))
    audit(tmp_path, evidence)
    report = json.loads((evidence / 'usage-reduced.json').read_text())
    assert report['records']['root']['counted_tokens']['input_tokens'] == 40
    assert report['records']['child']['owner'] == 'run-1'
    assert report['records']['child']['role'] == 'worker'
    assert report['summary']['groups']['worker']['failed_threads'] == 1
    assert report['records']['unknown']['role'] == 'unattributed'
    assert report['summary']['individual_request_usage'] == 'unavailable'
    before = report
    audit(tmp_path, evidence)
    assert json.loads((evidence / 'usage-reduced.json').read_text()) == before
