"""Submission interruption, deterministic termination and idempotent publication."""
import sqlite3

import pytest

from tests.operations.test_analysis_claim_scope import generic_worker, submit
from tests.operations.test_result_analysis_tool import limited_report
from scidiscovery.artifact_agent.service.reference_proofs import proof_error
from scidiscovery.artifact_agent.storage import CASIntegrityError


@pytest.mark.parametrize('stage', ['_finalize_workspace', '_prepare_evidence_snapshot', '_validation_inputs',
    '_accept_candidate', '_register_candidate', '_complete'])
def test_transient_failure_at_every_submission_stage_reuses_original_delivery(tmp_path, monkeypatch, stage):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    original = getattr(runs, stage)
    published = []
    def interrupted(*args, **kwargs):
        # Exercise committed intermediate mutations as well as read failures.
        if stage in {'_accept_candidate', '_register_candidate'}:
            published.append(original(*args, **kwargs))
        raise sqlite3.OperationalError('database is locked')
    with monkeypatch.context() as patch:
        patch.setattr(runs, stage, interrupted)
        reply = submit(worker, opened, limited_report())
    assert reply['state'] == 'rejected' and 'submission_temporarily_unavailable' in str(reply)
    assert runs.status(worker._run_id).state == 'running'
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    completed = runs.status(worker._run_id)
    if stage == '_register_candidate':
        assert completed.output_ref == published[0]
    if stage == '_accept_candidate':
        assert completed.accepted_candidate_digest
    # A repeated Worker submission reads the committed result, not another result.
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert runs.status(worker._run_id).output_ref == completed.output_ref


@pytest.mark.parametrize('stage', ['_prepare_evidence_snapshot', '_validation_inputs', '_register_candidate'])
@pytest.mark.parametrize('code', ['reference_proof_limit', 'reference_proof_incomplete'])
def test_terminal_proof_failure_retains_draft_and_can_recover_after_repair(tmp_path, monkeypatch, stage, code):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    def unavailable(*args, **kwargs):
        raise proof_error(code, 'Fixture proof cannot be finalized.')
    with monkeypatch.context() as patch:
        patch.setattr(runs, stage, unavailable)
        reply = submit(worker, opened, limited_report())
    assert reply['state'] == 'failed' and code in str(reply)
    stopped = runs.status(worker._run_id)
    assert stopped.state == 'failed' and stopped.output_ref is None
    assert stopped.recovery_draft and stopped.recovery_draft.get('draft_digest')
    request = dict(name='repaired', operation_id=stopped.operation_id, resume_from='generic_analysis',
        max_attempts=2, instruction='Continue after control repair.', inputs=[
            dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']),
            dict(port='curve_bundle', artifact_names=['generic_bundle'])])
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    next_worker = LocalWorkerMCPRouter(runs, operation_id=stopped.operation_id,
        operation_digest=catalog.operation(stopped.operation_id).digest)
    following = next_worker.call_tool('worker_open_assignment', {})
    assert submit(next_worker, following, limited_report())['state'] == 'completed'


def test_actual_snapshot_byte_limit_stops_without_destroying_draft(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import reference_proofs
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    monkeypatch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
    reply = submit(worker, opened, limited_report())
    stopped = system[1].runs.status(worker._run_id)
    assert reply['state'] == 'failed' and 'reference_proof_limit' in str(reply)
    assert stopped.recovery_draft['draft_digest']
    assert stopped.recovery_draft['evidence_proof_unavailable'] == 'reference_proof_limit'
    assert stopped.output_ref is None


def test_exact_cas_corruption_is_terminal_even_during_reconciliation(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment
    from tests.operations.test_experiment_continuation import submit as submit_experiment
    f = experiment(tmp_path, monkeypatch, seconds=60)
    def corrupt(_):
        raise CASIntegrityError('Exact immutable digest differs')
    monkeypatch.setattr(f.coordinator, 'require_idle', corrupt)
    reply = submit_experiment(f, [f.alias], outcome='blocked')
    assert reply['state'] == 'failed' and 'submission_integrity_failure' in str(reply)
    assert f.runs.status(f.run_id).state == 'failed'
    assert f.adapter.submits == 0


def test_committed_completion_is_not_reversed_by_post_commit_failure(tmp_path, monkeypatch):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    complete = runs._complete
    def late_failure(*args, **kwargs):
        complete(*args, **kwargs)
        raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(runs, '_complete', late_failure)
    assert submit(worker, opened, limited_report())['state'] == 'completed'
    assert runs.status(worker._run_id).state == 'completed'


def test_busy_diagnostic_writer_does_not_change_retry_into_failure(tmp_path, monkeypatch):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    def busy(*args, **kwargs):
        raise sqlite3.OperationalError('database is locked')
    with monkeypatch.context() as patch:
        patch.setattr(runs, '_finalize_workspace', busy)
        patch.setattr(runs, 'record_error_observation', busy)
        reply = submit(worker, opened, limited_report())
    assert reply['state'] == 'rejected' and 'submission_temporarily_unavailable' in str(reply)
    assert runs.status(worker._run_id).state == 'running'
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_collected_receipt_reconciliation_does_not_hide_proof_failures(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment
    from scidiscovery.artifact_agent.service.reference_proofs import ReferenceProofError
    f = experiment(tmp_path, monkeypatch, seconds=60)
    def unavailable(*args, **kwargs):
        raise proof_error('reference_proof_limit', 'Exact implementation proof exceeds budget.')
    monkeypatch.setattr(f.coordinator, '_run_implementation_record', unavailable)
    with pytest.raises(ReferenceProofError):
        from dataclasses import replace
        f.coordinator.require_idle(replace(f.runs.status(f.old_id), accepted_candidate_digest=None))


def test_reporting_survives_unreadable_status(tmp_path, monkeypatch):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    def locked(*args, **kwargs):
        raise sqlite3.OperationalError('database is locked')
    with monkeypatch.context() as patch:
        patch.setattr(runs, 'status', locked)
        state, details = runs._submission_failure(worker._run_id, sqlite3.OperationalError('database is locked'))
    assert state == 'rejected' and details[0]['code'] == 'submission_temporarily_unavailable'
    assert runs.status(worker._run_id).state == 'running'


def test_wrapped_connection_and_storage_errors_have_same_transient_policy():
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    from scidiscovery.artifact_agent.service.submission_errors import classify_submission_error
    for cause in (ConnectionError('reset'), sqlite3.OperationalError('database is locked')):
        error = RunCheckerError('wrapped transport')
        error.__cause__ = cause
        assert classify_submission_error(error).disposition == 'retry'
    timeout = RunCheckerError('bounded step', category='tool_timeout')
    timeout.__cause__ = TimeoutError()
    assert classify_submission_error(timeout).disposition == 'fail'
    assert classify_submission_error(TimeoutError()).disposition == 'intervene'
    assert classify_submission_error(ConnectionError(), deadline_expired=True).category == 'run_timeout'


@pytest.mark.parametrize('error,code', [(TimeoutError('step exhausted'), 'submission_step_timeout'),
    (OSError(28, 'disk full'), 'submission_storage_exhausted')])
def test_budget_or_storage_exhaustion_is_visible_as_failure(tmp_path, monkeypatch, error, code):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    def exhausted(*args, **kwargs):
        raise error
    if isinstance(error, TimeoutError):
        from scidiscovery.artifact_agent.service import runs as run_module
        monkeypatch.setattr(run_module, 'operation_workspace_hooks', lambda _: {'workspace_finalizer':exhausted})
    else:
        monkeypatch.setattr(runs, '_finalize_workspace', exhausted)
    reply = submit(worker, opened, limited_report())
    assert reply['state'] == 'failed' and code in str(reply)
    state = runs.status(worker._run_id)
    assert state.state == 'failed' and state.recovery_draft
    assert code in str(runs.diagnostic_summary(state))


def test_no_false_terminal_ack_when_failure_cannot_be_persisted(tmp_path, monkeypatch):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    def full(*args, **kwargs):
        raise OSError(28, 'disk full')
    monkeypatch.setattr(runs, '_finalize_workspace', full)
    monkeypatch.setattr(runs, 'record_failure', full)
    reply = submit(worker, opened, limited_report())
    assert reply['state'] == 'rejected' and 'submission_state_unavailable' in str(reply)
    assert runs.status(worker._run_id).state == 'running'


def test_normal_output_rejection_does_not_allocate_traceback(tmp_path):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
    runs = system[1].runs
    root = runs.database_path.parent.parent / 'engineering-diagnostics'
    before = set(root.glob('diag_*.json'))
    assert runs._submission_failure(worker._run_id, RunOutputError('correct the form'))[0] == 'rejected'
    assert set(root.glob('diag_*.json')) == before


def test_unclassified_failure_signals_root_in_normal_status(tmp_path, monkeypatch):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs, root = system[1].runs, system[2]
    def interrupted(*args, **kwargs):
        raise RuntimeError('Control needs investigation')
    with monkeypatch.context() as patch:
        patch.setattr(runs, '_finalize_workspace', interrupted)
        assert submit(worker, opened, limited_report())['state'] == 'rejected'
    status = root.call_tool('run_status', {'name':'generic_analysis', 'intent':'status'})
    assert status['attention_required']['code'] == 'submission_intervention_required'
    assert 'traceback' not in str(status)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert 'attention_required' not in root.call_tool('run_status', {'name':'generic_analysis', 'intent':'status'})


def test_deadline_exhaustion_during_submission_is_terminal_not_retry(tmp_path, monkeypatch):
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    def interrupted(*args, **kwargs):
        with runs._connect() as connection:
            connection.execute("UPDATE runs SET deadline_at='2000-01-01T00:00:00Z' WHERE run_id=?", (worker._run_id,))
        raise ConnectionError('interrupted after deadline')
    monkeypatch.setattr(runs, '_finalize_workspace', interrupted)
    reply = submit(worker, opened, limited_report())
    assert reply['state'] == 'failed' and 'submission_deadline_exhausted' in str(reply)
    assert runs.status(worker._run_id).state == 'failed'


def test_implicit_connection_cause_is_retryable_unless_explicitly_suppressed():
    from scidiscovery.artifact_agent.service.submission_errors import classify_submission_error
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    def wrapped(suppress):
        try:
            try:
                raise ConnectionError('reset')
            except ConnectionError:
                if suppress:
                    raise RunCheckerError('independent failure') from None
                raise RunCheckerError('wrapped failure')
        except RunCheckerError as error:
            return error
    assert classify_submission_error(wrapped(False)).disposition == 'retry'
    assert classify_submission_error(wrapped(True)).disposition == 'fail'
