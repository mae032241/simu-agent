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
    def unavailable(*args):
        raise proof_error('reference_proof_limit', 'Exact implementation proof exceeds budget.')
    monkeypatch.setattr(f.coordinator, '_run_implementation_record', unavailable)
    with pytest.raises(ReferenceProofError):
        from dataclasses import replace
        f.coordinator.require_idle(replace(f.runs.status(f.old_id), accepted_candidate_digest=None))
