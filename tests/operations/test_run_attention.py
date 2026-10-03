"""Control issues survive normal failures; delivery is not acknowledgement."""
import sqlite3

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter
from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
from tests.operations.test_analysis_claim_scope import generic_worker, submit
from tests.operations.test_result_analysis_tool import limited_report


def test_attention_survives_rejection_restart_and_repeat_then_resolves(tmp_path):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    run_id = worker._run_id
    runs._submission_failure(run_id, RuntimeError('intervention required'))
    first = root.call_tool('instance_current', {})['attention_notifications']['events']
    assert len(first) == 1 and first[0]['name'] == 'generic_analysis'
    assert first[0]['attention_required']['code'] == 'submission_intervention_required'
    request = first[0]['read_request']
    assert root.call_tool(request['name'], request['arguments'])['diagnostic_events']['events']
    first_seen = runs.submission_attention(runs.status(run_id))['issues'][0]['first_seen_at']
    runs._submission_failure(run_id, RunOutputError('form correction'))
    runs._submission_failure(run_id, RuntimeError('same control problem'))
    # Fresh router/Run service initialization must not reset attention or notification cursor.
    runs._initialize()
    root = RootMCPRouter(root.facade)
    status = root.call_tool('run_status', {'name':'generic_analysis', 'intent':'status'})
    assert status['attention_required']['code'] == 'submission_intervention_required'
    assert status['attention_required']['issues'][0]['first_seen_at'] == first_seen
    assert 'attention_notifications' not in status
    assert run_id not in str(first) and 'traceback' not in str(first)
    # Lifecycle consumers have an independent, also deduplicated notification cursor.
    assert root.call_tool('lifecycle_events', {})['attention_notifications']['events'][0]['name'] == 'generic_analysis'
    assert 'attention_notifications' not in root.call_tool('lifecycle_events', {})
    assert submit(worker, opened, limited_report())['state'] == 'completed'
    closed = root.call_tool('run_status', {'name':'generic_analysis', 'intent':'status'})
    assert 'attention_required' not in closed
    assert closed['attention_notifications']['events'] == [{'name':'generic_analysis', 'state':'resolved'}]
    assert 'attention_notifications' not in root.call_tool('instance_current', {})


def test_transient_and_output_corrections_do_not_open_attention(tmp_path):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    for error in (sqlite3.OperationalError('database is locked'), ConnectionError('offline'), RunOutputError('correct form')):
        assert runs._submission_failure(worker._run_id, error)[0] == 'rejected'
    assert runs.submission_attention(runs.status(worker._run_id)) is None
    assert 'attention_notifications' not in root.call_tool('instance_current', {})


def test_scopes_resolve_independently_and_recurrence_notifies(tmp_path):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    run_id = worker._run_id
    code = 'experiment_implementation_unavailable'
    for scope in ('implementation:one', 'implementation:two'):
        runs.record_attention(run_id, scope=scope, code=code)
    reply = root.call_tool('instance_current', {})
    assert reply['attention_notifications']['events'][0]['attention_required']['total'] == 2
    runs.record_attention(run_id, scope='implementation:one', code=None)
    assert runs.submission_attention(runs.status(run_id))['total'] == 1
    root.call_tool('instance_current', {})
    runs.record_attention(run_id, scope='implementation:two', code=None)
    assert root.call_tool('instance_current', {})['attention_notifications']['events'][0]['state'] == 'resolved'
    runs.record_attention(run_id, scope='implementation:one', code=code)
    assert root.call_tool('instance_current', {})['attention_notifications']['events'][0]['state'] == 'attention_required'
    # Notifications never cross instance boundaries.
    assert runs.attention_issues(instance_id='another-instance') == []


def test_notification_failure_cannot_turn_success_into_failed_tool(tmp_path, monkeypatch):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    original = root.facade.attention_notifications
    def busy(**_):
        raise sqlite3.OperationalError('database is locked')
    with monkeypatch.context() as patch:
        patch.setattr(root.facade, 'prepare_attention_notifications', busy)
        assert 'attention_notifications' not in root.call_tool('instance_current', {})
    assert original()['events'][0]['state'] == 'attention_required'


def test_exact_missing_execution_binding_alerts_and_repairs_but_bad_alias_does_not(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from tests.operations.test_implementation_receipt_identity import execution_id
    from scidiscovery.artifact_agent.service.sealed_materials import material_error
    from scidiscovery.operation_contract import DiagnosticError
    f = experiment(tmp_path, monkeypatch, seconds=60)
    with pytest.raises(DiagnosticError):
        f.worker.call_tool('worker_experiment_execute', {'action':'review', 'implementation':'no-such-alias'})
    assert f.runs.submission_attention(f.runs.status(f.run_id)) is None
    assert start(f)['state'] == 'running'
    eid = execution_id(f)
    def missing(*args, **kwargs):
        raise material_error('experiment_implementation_unavailable', 'Exact historical receipt missing')
    with monkeypatch.context() as patch:
        patch.setattr(f.coordinator, '_run_implementation_record', missing)
        with pytest.raises(DiagnosticError):
            f.coordinator._execution_implementation_record(f.runs.status(f.run_id), eid)
    notice = f.root.call_tool('instance_current', {})['attention_notifications']['events'][0]
    assert notice['attention_required']['code'] == 'experiment_implementation_unavailable'
    f.runs.record_attention(f.old_id, scope='implementation:' + eid, code='experiment_implementation_unavailable')
    f.coordinator._execution_implementation_record(f.runs.status(f.run_id), eid)
    assert f.runs.submission_attention(f.runs.status(f.run_id)) is None
    assert f.runs.submission_attention(f.runs.status(f.old_id)) is None
    assert f.root.call_tool('instance_current', {})['attention_notifications']['events'][0]['state'] == 'resolved'
    assert f.adapter.submits == 1


def test_different_submission_codes_coexist_and_repeats_do_not_notify(tmp_path):
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    runs._submission_failure(worker._run_id, RuntimeError('control'))
    root.call_tool('instance_current', {})
    runs._submission_failure(worker._run_id, TimeoutError('unclassified'))
    notice = root.call_tool('instance_current', {})['attention_notifications']['events'][0]
    assert set(notice['attention_required']['codes']) == {'submission_intervention_required', 'submission_timeout_unclassified'}
    assert runs.submission_attention(runs.status(worker._run_id))['total'] == 2
    runs._submission_failure(worker._run_id, RuntimeError('control again'))
    assert 'attention_notifications' not in root.call_tool('instance_current', {})


def test_upgrade_recovers_existing_alert_without_resurrecting_resolved_issue(tmp_path):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    with runs._connect() as connection:
        # Original pre-upgrade layout: ordinary last error obscures an older alert.
        for code in ('submission_intervention_required', 'output_invalid'):
            connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,?)",
                (worker._run_id, 'output_rejected', '2026-10-01T00:00:00Z',
                 canonical_json({'details':[{'code':code}]})))
    runs._initialize()
    assert runs.submission_attention(runs.status(worker._run_id))['code'] == 'submission_intervention_required'
    runs.record_attention(worker._run_id, scope='submission:submission_intervention_required', code=None)
    runs._initialize()
    assert runs.submission_attention(runs.status(worker._run_id)) is None
