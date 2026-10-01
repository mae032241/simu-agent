"""Execution identities isolate diagnostic caches and durable collection replaces them."""
import hashlib
import json

import pytest

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from scidiscovery.artifact_agent.storage.cas import CASIntegrityError
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameNotFound
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
from tests.operations.test_experiment_approval_handoff import experiment, start


def test_exact_execution_cache_collection_failure_cleanup_and_late_refresh(tmp_path, monkeypatch):
    runtime, instance, adapter, _, root, _ = _setup(tmp_path)
    executions = runtime.executions
    ids = {}
    snapshots = {}
    for name in ('job-a', 'job-b'):
        _create_effect(root, name=name)
        _decide_execution_approval(runtime, root, name=name)
        monkeypatch.setattr(adapter, 'submit', lambda _, n=name: ('remote-' + n, 'running'))
        monkeypatch.setattr(adapter, 'status_details', lambda _, n=name: {'state':'running', 'progress':{
            'log_tails':[{'source':'solver_log', 'tail':n + ': 日志\n', 'size_bytes':100,
                'truncated':True}]}}, raising=False)
        root.call_tool('execution_start', {'name':name}, surface='execution')
        root.call_tool('execution_status', {'name':name}, surface='execution')
        ids[name] = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
            namespace='execution', name=name)
        snapshots[name] = executions.observation(ids[name])
    assert ids['job-a'] != ids['job-b']
    monkeypatch.setattr(adapter, 'status_details', lambda _: pytest.fail('cache read queried remote'))
    for name in ids:
        page = root.call_tool('execution_logs', {'name':name}, surface='execution')
        assert page['text'] == name + ': 日志\n'
        assert page['source_truncated'] is True and page['observed_at']
        assert page['before'] is None and page['after']
    a = ids['job-a']
    executions.record_status(execution_id=a, external_run_id='remote-job-a', state='succeeded')
    raw = b'full durable solver log\n'
    path = tmp_path / 'solver.log'
    path.write_bytes(raw)
    descriptor = LocalFileDescriptor(name='tcad_log', local_path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw), media_type='text/plain')
    with pytest.raises(CASIntegrityError):
        executions.ingest_result(execution_id=a, external_run_id='remote-job-a',
            outputs=(descriptor.model_copy(update={'sha256':'0'*64}),))
    assert root.call_tool('execution_logs', {'name':'job-a'}, surface='execution')['text'] == 'job-a: 日志\n'
    executions.ingest_result(execution_id=a, external_run_id='remote-job-a', outputs=(descriptor,))
    assert root.call_tool('execution_logs', {'name':'job-a'}, surface='execution')['cache_state'] == 'released'
    assert 'tail' not in executions.observation(a)['progress']['log_tails'][0]
    # A refresh started before collection must not resurrect A's discarded body.
    executions.save_observation(a, snapshots['job-a'])
    assert 'tail' not in executions.observation(a)['progress']['log_tails'][0]
    assert executions.observation(ids['job-b']) == snapshots['job-b']
    assert root.call_tool('execution_logs', {'name':'job-b'}, surface='execution')['text'] == 'job-b: 日志\n'
    output = executions.outputs(a)[0]
    assert output.logical_name == 'tcad_log'
    assert runtime.artifacts.read(runtime.artifacts.get_by_id(output.artifact_id).ref) == raw
    # The same semantic name in another instance cannot resolve the cache.
    other = runtime.scheduler_bindings.create_instance(name='other', title='Other', objective='Isolation')
    root.facade.instance = other.instance_id
    with pytest.raises(SchedulerNameNotFound, match='not bound|not found|does not exist|unknown'):
        root.call_tool('execution_logs', {'name':'job-b'}, surface='execution')


def test_worker_cache_utf8_pagination_is_read_only_and_uses_frozen_limit(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    text = '日' * 6000 + '\nlast line'
    monkeypatch.setattr(f.adapter, 'status_details', lambda _: {'state':'running', 'progress':{
        'log_tails':[{'source':'solver_log', 'tail':text, 'size_bytes':len(text.encode())}]}}, raising=False)
    status = start(f)
    assert 'last line' not in json.dumps(status)
    # Submission completion does not itself populate the remote observation cache.
    assert status['state'] == 'running'
    f.worker.call_tool('worker_experiment_execute', {'action':'status'})
    before = f.runs.tool_evidence(f.run_id)
    monkeypatch.setattr(f.adapter, 'status_details', lambda _: pytest.fail('cache read queried remote'))
    page = f.worker.call_tool('worker_experiment_execute', {'action':'logs'})
    assert page['text'].endswith('last line')
    assert len(page['text'].encode()) <= 16384
    newest = page['after']
    parts = [page['text']]
    while page['before'] is not None:
        page = f.worker.call_tool('worker_experiment_execute',
            {'action':'logs', 'direction':'before', 'cursor':page['before']})
        assert len(page['text'].encode()) <= 16384
        parts.insert(0, page['text'])
    assert ''.join(parts) == text and len(parts) == 2
    unchanged = f.worker.call_tool('worker_experiment_execute',
        {'action':'logs', 'direction':'after', 'cursor':newest})
    assert unchanged['text'] == '' and unchanged['gap'] is None
    assert f.runs.tool_evidence(f.run_id) == before and f.adapter.submits == 1
    with pytest.raises(DiagnosticError, match='offset is only'):
        f.worker.call_tool('worker_experiment_execute', {'action':'logs', 'offset':1})
    with pytest.raises(DiagnosticError, match='log_count'):
        f.worker.call_tool('worker_experiment_execute', {'action':'logs', 'log_index':1})


def test_incremental_cursor_scopes_continuity_and_redaction():
    from scidiscovery.artifact_agent.service.execution_log_reader import log_page
    log = {'source':'stdout', 'stream_id':'first-stream', 'start_byte':0, 'size_bytes':10,
        'tail':'old 日志\n'}
    def read(value, **kw):
        return log_page('execution-a', 0, value, max_bytes=16,
            direction=kw.get('direction', 'tail'), cursor=kw.get('cursor'))
    first = read(log)
    appended = {**log, 'tail':log['tail']+'new line\n', 'size_bytes':19}
    delta = read(appended, direction='after', cursor=first['after'])
    assert delta['text'] == 'new line\n' and delta['gap'] is None
    assert read(appended, direction='after', cursor=delta['after'])['text'] == ''
    for changed in ({**appended, 'stream_id':'rotation'},
                    {**appended, 'tail':'replacement\n'},
                    {**appended, 'start_byte':5},
                    {**appended, 'stream_id':None}):
        value = read(changed, direction='after', cursor=first['after'])
        assert value['gap'] == 'snapshot_replaced' and value['after']
    with pytest.raises(DiagnosticError, match='another execution/log'):
        log_page('execution-b', 0, log, direction='after', cursor=first['after'], max_bytes=16)
    with pytest.raises(DiagnosticError, match='another execution/log'):
        log_page('execution-a', 1, log, direction='after', cursor=first['after'], max_bytes=16)
    for bad in ('not a cursor', 'W10', 'e30'):
        with pytest.raises(DiagnosticError, match='Cursor is invalid'):
            read(log, direction='after', cursor=bad)
    private = read({**log, 'tail':'token=hidden-value /private/solver/log\n'})
    assert 'hidden-value' not in private['text'] and '/private' not in private['text']


def test_incremental_pages_drain_new_text_before_waiting_for_more():
    from scidiscovery.artifact_agent.service.execution_log_reader import log_page
    old = {'source':'stdout', 'stream_id':'stable', 'start_byte':0, 'tail':'old\n'}
    cursor = log_page('e', 0, old, direction='tail', cursor=None, max_bytes=8)['after']
    current = {**old, 'tail':'old\n' + '日' * 9 + '\n'}
    pages = []
    while True:
        page = log_page('e', 0, current, direction='after', cursor=cursor, max_bytes=8)
        assert page['gap'] is None and len(page['text'].encode()) <= 8
        pages.append(page['text'])
        cursor = page['after']
        if not page['has_more']:
            break
    assert ''.join(pages) == '日' * 9 + '\n'
