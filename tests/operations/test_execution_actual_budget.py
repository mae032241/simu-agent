"""Single-request admission, cumulative reservations and actual terminal usage."""
import pytest

from tests.operations.test_experiment_approval_handoff import experiment, start
from tests.operations.test_approval_wait_recovery import execution
from tests.operations.tcad_policy_fixtures import policy_snapshot


def test_config_separates_one_hour_request_from_six_hour_pool():
    policy = policy_snapshot()
    admission = policy.admission(budget={'wall_time_seconds': 3600, 'max_storage_bytes': 100}, budget_key='a'*64)
    assert admission.outcome == 'policy'
    assert admission.per_execution_allowance['wall_time_seconds'] == 3600
    assert admission.allowance['wall_time_seconds'] == 21600
    assert policy.admission(budget={'wall_time_seconds': 3601, 'max_storage_bytes': 100},
        budget_key='a'*64).outcome == 'require_human_approval'


@pytest.mark.parametrize('terminal', ['succeeded', 'failed', 'cancelled'])
def test_background_settles_existing_terminal_request_even_without_worker(tmp_path, monkeypatch, terminal):
    from scidiscovery.agent_execution_settings import LifecycleSettings
    from scidiscovery.artifact_agent.service.lifecycle import LifecycleReconciler
    f = experiment(tmp_path, monkeypatch, seconds=3600)
    start(f)
    eid = execution(f).object_id
    status = f.runtime.executions.status(eid)
    before = f.runtime.executions.authorization(eid)['budget_usage']['remaining']['wall_time_seconds']
    f.runtime.executions.record_status(execution_id=eid, external_run_id=status.external_run_id, state=terminal)
    monkeypatch.setattr(f.adapter, 'status_details', lambda external: {'state': terminal,
        'consumed_budget': {'wall_time_seconds': 17 if external == status.external_run_id else 1, 'max_storage_bytes': 100}}, raising=False)
    assert eid in f.runtime.executions.observation_candidates()
    LifecycleReconciler(runs=f.runs, bridge=f.coordinator.bridge, settings=LifecycleSettings()).tick()
    value = f.runtime.executions.authorization(eid)
    assert value['accounting']['actual']['wall_time_seconds'] == 17
    assert value['budget_usage']['remaining']['wall_time_seconds'] == before + 3600 - 17
    assert eid not in f.runtime.executions.observation_candidates()
    assert f.adapter.submits == 1


def test_partial_actual_usage_releases_time_without_inventing_storage(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=3600)
    start(f)
    eid = execution(f).object_id
    before = f.runtime.executions.authorization(eid)['budget_usage']['remaining']['wall_time_seconds']
    f.adapter.state = 'succeeded'
    monkeypatch.setattr(f.adapter, 'status_details', lambda _: {'state': 'succeeded',
        'consumed_budget': {'wall_time_seconds': 12}}, raising=False)
    f.coordinator.bridge.sync(execution_id=eid)
    value = f.runtime.executions.authorization(eid)
    assert value['accounting']['state'] == 'partial'
    assert value['accounting']['unsettled_reservation'] == {'max_storage_bytes': 1800000000}
    assert value['budget_usage']['remaining']['wall_time_seconds'] == before + 3600 - 12
    f.runtime.executions.settle_budget(eid, {'wall_time_seconds': 0, 'max_storage_bytes': 100})
    assert f.runtime.executions.budget_accounting(eid)['actual'] == {'wall_time_seconds': 12, 'max_storage_bytes': 100}
    assert not f.runtime.executions.budget_needs_settlement(eid)


def test_preparation_failure_releases_only_unsubmitted_reservation(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=3600)
    def broken(*args, **kwargs):
        raise RuntimeError('fixture failed before submission')
    monkeypatch.setattr(f.adapter, 'prepare_with_artifacts', broken, raising=False)
    with pytest.raises(Exception):
        start(f)
    eid = execution(f).object_id
    assert f.runtime.executions.budget_accounting(eid) == {}
    assert f.runtime.executions.prepared_submission(eid) is None and f.adapter.submits == 0


def test_immediate_terminal_submission_settles_actual_time(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=3600)
    f.adapter.state = 'succeeded'
    monkeypatch.setattr(f.adapter, 'status_details', lambda _: {'state': 'succeeded',
        'consumed_budget': {'wall_time_seconds': 3, 'max_storage_bytes': 100}}, raising=False)
    assert start(f)['state'] == 'succeeded'
    assert f.runtime.executions.budget_accounting(execution(f).object_id)['actual']['wall_time_seconds'] == 3


def test_admin_increase_keeps_existing_consumption(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=3600)
    start(f)
    eid = execution(f).object_id
    owner = f.runtime.executions.budget_owner(eid)
    remaining_before = f.runtime.executions.authorization(eid)['budget_usage']['remaining']['wall_time_seconds']
    with f.runtime.executions._connect() as db:
        db.execute('UPDATE execution_budget_pools SET allowance_json=?',
            ('{"max_storage_bytes":2000000000,"wall_time_seconds":3600}',))
    admission = policy_snapshot().admission(budget={'wall_time_seconds': 3600, 'max_storage_bytes': 100}, budget_key=owner)
    assert f.runtime.executions.budget_admission(executor='tcad_artifact:tcad', admission=admission).outcome == 'policy'
    with f.runtime.executions._connect() as db:
        assert f.runtime.executions._budget_remaining(db, 'tcad_artifact:tcad', admission)['wall_time_seconds'] == remaining_before


def test_debug_timing_settles_once_and_keeps_other_reservations():
    from tcad_artifact.local_debug_service import _settle_wall_usage
    ledger, record = {'reserved_wall_seconds': 360}, {'reserved_wall_seconds': 120}
    _settle_wall_usage(ledger, record, 2.2)
    assert ledger['reserved_wall_seconds'] == 243 and record['actual_wall_seconds'] == 3
    _settle_wall_usage(ledger, record, 0)
    assert ledger['reserved_wall_seconds'] == 243


@pytest.mark.parametrize('manifest,expected', [
    ({'resource_usage': {'elapsed_seconds': 2.1}}, {'wall_time_seconds': 3}),
    ({'started_at': '2026-09-30T00:00:00Z', 'completed_at': '2026-09-30T00:00:07Z'}, {'wall_time_seconds': 7}),
    ({'resource_usage': {'elapsed_seconds': True, 'observed_storage_high_water_bytes': False}}, None),
    ({}, None),
])
def test_runner_and_local_control_report_only_observed_dimensions(manifest, expected):
    from tcad_artifact.remote_runner_py36 import _consumed_budget as remote
    from tcad_artifact.execution_control import _consumed_budget as local
    assert remote(manifest) == local(manifest) == expected


def test_approval_displays_single_request_separately_from_cumulative_overage():
    from scidiscovery.artifact_agent.approval_ui.approval_focus import render_approval_focus
    html = render_approval_focus({}, subject_ids=[], evidence_href=lambda *_: '', authorization={
        'reason': 'cumulative_budget_exceeded', 'budget': {'wall_time_seconds': 900},
        'per_execution_allowance': {'wall_time_seconds': 3600}, 'allowance': {'wall_time_seconds': 21600},
        'budget_usage': {'remaining': {'wall_time_seconds': 0}, 'overage': {'wall_time_seconds': 500}}})
    assert '900 秒' in html and '3,600 秒' in html
    assert '累计超额（不是本次申请）' in html and '-500' not in html
