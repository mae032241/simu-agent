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
    capture(configured, 'first')
    capture(EngineeringDiagnostics(tmp_path), 'second')
    assert len(list(tmp_path.glob('diag_*.json'))) == 1
    capture(EngineeringDiagnostics(tmp_path, settings=DiagnosticsSettings(max_records=3)), 'third')
    capture(EngineeringDiagnostics(tmp_path), 'fourth')
    assert len(list(tmp_path.glob('diag_*.json'))) == 3
