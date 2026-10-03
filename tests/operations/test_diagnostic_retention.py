"""Engineering trace retention cannot grow with every rejected submission."""
import os
import time
import pytest
from scidiscovery.agent_execution_settings import DiagnosticsSettings
from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics


def capture(store, message, scope='instance:one'):
    return store.capture(RuntimeError(message), scope=scope, layer='fixture', action='submit')


def test_repeated_failure_reuses_reference_but_scopes_and_logs_remain_distinct(tmp_path):
    store = EngineeringDiagnostics(tmp_path)
    first = capture(store, 'same failure')
    assert capture(store, 'same failure')['reference'] == first['reference']
    assert capture(store, 'same failure', 'instance:two')['reference'] != first['reference']
    error = RuntimeError('same failure')
    error.stdout = b'first'
    log1 = store.capture(error, scope='instance:one', layer='fixture', action='submit')
    error.stdout = b'second'
    log2 = store.capture(error, scope='instance:one', layer='fixture', action='submit')
    assert log1['reference'] != log2['reference']
    assert store.read(log1['reference'], scopes=('instance:one',), section='stdout')['text'] == 'first'
    with pytest.raises(ValueError, match='another instance'):
        store.read(first['reference'], scopes=('instance:two',))


def test_retention_enforces_count_bytes_and_age_without_touching_other_files(tmp_path):
    store = EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=2, max_total_bytes=4096, retention_seconds=10))
    unrelated = tmp_path / 'sealed-result.json'
    unrelated.write_text('preserve')
    for n in range(6):
        capture(store, str(n))
    records = list(tmp_path.glob('diag_*'))
    assert len(list(tmp_path.glob('diag_*.json'))) <= 2
    assert sum(p.stat().st_size for p in records) <= 4096
    for p in records:
        os.utime(p, (time.time()-20, time.time()-20))
    store.prune()
    assert not list(tmp_path.glob('diag_*')) and unrelated.read_text() == 'preserve'


def test_oversized_trace_does_not_return_dangling_reference(tmp_path):
    store = EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_total_bytes=1024))
    result = capture(store, 'large' * 20000)
    assert 'reference' not in result and result['retention'] == 'trace_exceeded_storage_budget'
    assert not list(tmp_path.glob('diag_*'))


def test_daemon_maintenance_applies_configured_retention_without_new_failures(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service.lifecycle import LifecycleReconciler
    from scidiscovery.agent_execution_settings import AgentSettings, LifecycleSettings
    root = tmp_path / 'engineering-diagnostics'
    store = EngineeringDiagnostics(root)
    for n in range(4):
        capture(store, str(n))
    runs = SimpleNamespace(database_path=tmp_path / 'runs/runs.sqlite',
        agent_settings=AgentSettings(diagnostics=DiagnosticsSettings(max_records=1)),
        expired_active_ids=lambda **_: [])
    bridge = SimpleNamespace(executions=SimpleNamespace(observation_candidates=lambda **_: []))
    LifecycleReconciler(runs=runs, bridge=bridge, settings=LifecycleSettings()).tick()
    assert len(list(root.glob('diag_*.json'))) == 1


def test_separate_capture_process_uses_configured_policy(tmp_path):
    configured = EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=1))
    configured.publish_retention_policy(DiagnosticsSettings(max_records=1))
    capture(configured, 'first')
    capture(EngineeringDiagnostics(tmp_path), 'second')
    assert len(list(tmp_path.glob('diag_*.json'))) == 1
    configured.publish_retention_policy(DiagnosticsSettings(max_records=3))
    capture(EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=1)), 'third')
    capture(EngineeringDiagnostics(tmp_path), 'fourth')
    assert len(list(tmp_path.glob('diag_*.json'))) == 3


@pytest.mark.parametrize('raw', ['{broken', '{"max_records":0}', '[]'])
def test_broken_cache_does_not_disable_capture_or_cleanup_and_daemon_repairs(tmp_path, raw):
    policy = tmp_path / '.retention.json'
    policy.write_text(raw)
    store = EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=1))
    assert capture(store, 'first').get('reference')
    assert capture(store, 'second').get('reference')
    store.prune()
    assert len(list(tmp_path.glob('diag_*.json'))) == 1
    assert policy.read_text() == raw  # Recorders cannot publish policy.
    store.publish_retention_policy(DiagnosticsSettings(max_records=4))
    capture(EngineeringDiagnostics(tmp_path), 'third')
    assert len(list(tmp_path.glob('diag_*.json'))) == 2


def test_capture_processes_cannot_overwrite_authoritative_policy(tmp_path):
    import json
    authority = EngineeringDiagnostics(tmp_path)
    authority.publish_retention_policy(DiagnosticsSettings(max_records=2))
    for n, configured_count in enumerate((1, 10, 1, 10)):
        capture(EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=configured_count)), str(n))
        assert json.loads((tmp_path / '.retention.json').read_text())['max_records'] == 2
    assert len(list(tmp_path.glob('diag_*.json'))) == 2


def test_interrupted_log_replacement_preserves_previous_complete_file(tmp_path, monkeypatch):
    store = EngineeringDiagnostics(tmp_path)
    def error():
        result = RuntimeError('fixture')
        result.stdout = b'complete log'
        return result
    first = store.capture(error(), scope='instance:one', layer='fixture', action='submit')
    replace = os.replace
    def interrupted(source, target):
        if str(target).endswith('.stdout'):
            raise OSError('interrupted before atomic replacement')
        return replace(source, target)
    monkeypatch.setattr(os, 'replace', interrupted)
    result = store.capture(error(), scope='instance:one', layer='fixture', action='submit')
    assert 'recording_error' in result
    assert store.read(first['reference'], scopes=('instance:one',), section='stdout')['text'] == 'complete log'
    assert not list(tmp_path.glob('.diagnostic-*.tmp'))


def test_read_holds_shared_lock_against_writer_and_retention(tmp_path, monkeypatch):
    import fcntl
    from scidiscovery.artifact_agent.service import engineering_diagnostics as module
    store = EngineeringDiagnostics(tmp_path)
    first = capture(store, 'fixture')
    read_json = module.read_json
    observed = []
    def reading(path, **kwargs):
        with (tmp_path / '.retention.lock').open('r+b') as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            observed.append(True)
        return read_json(path, **kwargs)
    monkeypatch.setattr(module, 'read_json', reading)
    assert store.read(first['reference'], scopes=('instance:one',))['text']
    assert observed == [True]


def test_old_read_only_archive_without_lock_is_readable(tmp_path):
    store = EngineeringDiagnostics(tmp_path)
    first = capture(store, 'fixture')
    (tmp_path / '.retention.lock').unlink()
    assert store.read(first['reference'], scopes=('instance:one',))['text']
    assert not (tmp_path / '.retention.lock').exists()


def test_equal_timestamps_retain_newly_published_reference(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import engineering_diagnostics as module
    store = EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=1))
    stamp = time.time()
    atomic = module.atomic_json
    def coarse_clock(path, value):
        atomic(path, value)
        os.utime(path, (stamp, stamp))
    monkeypatch.setattr(module, 'atomic_json', coarse_clock)
    first = capture(store, 'first')['reference']
    second = capture(store, 'second')['reference']
    assert list(tmp_path.glob('diag_*.json')) == [tmp_path / (second + '.json')]
    with pytest.raises(ValueError, match='expired'):
        store.read(first, scopes=('instance:one',))
