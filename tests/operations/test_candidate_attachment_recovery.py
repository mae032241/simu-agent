"""Shared candidate-budget policy and actual native Worker delivery; no models."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.agent_execution_settings import AgentSettings, AttachmentSettings
from scidiscovery.artifact_agent.schema.common import ContractDiagnostic
from scidiscovery.artifact_agent.service.submission_errors import (
    classify_candidate_attachment_error, classify_submission_error)
from scidiscovery.artifact_agent.storage import CASIntegrityError
from scidiscovery.operation_contract import DiagnosticError, ToolInputError
from tests.operations.test_native_experiment import installed, _start_native


MESSAGE = 'Attachment count or total byte budget exceeded'


def budget_error():
    return ToolInputError('attachment_publication_invalid', MESSAGE, path='$.materials')


class SnapshotRuns:
    """Only the helper's current budget snapshot, not native/scientific admission."""
    def __init__(self, path, records=(), settings=None):
        self.path = path
        self.statements = []
        with self._connect() as db:
            db.executescript('CREATE TABLE runs (run_id TEXT PRIMARY KEY,state TEXT,accepted_candidate_digest TEXT,deadline_at TEXT,recovery_policy_json BLOB);'
                'CREATE TABLE run_tool_evidence (run_id TEXT,ordinal INTEGER,record_json BLOB);')
            policy = {'attachments': (settings or AttachmentSettings(max_files=2, max_item_bytes=20, max_total_bytes=20)).model_dump(mode='json')}
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?)', ('exact', 'running', None, '2999-01-01T00:00:00Z', json.dumps(policy)))
            for ordinal, record in enumerate(records):
                db.execute('INSERT INTO run_tool_evidence VALUES (?,?,?)', ('exact', ordinal, json.dumps(record)))
        self.statements.clear()

    def _connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.set_trace_callback(self.statements.append)
        return db

    @staticmethod
    def _row(db, run_id):
        return db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()


def assert_bounded(failure):
    for item in failure.details:
        assert len(item['message']) <= 512
        assert ContractDiagnostic.model_validate(item).model_dump(mode='json', exclude_none=True) == item


def assert_recovery_does_not_reset_capacity(failure):
    messages = ' '.join(item['message'] for item in failure.details)
    assert 'draft_from preserves original nodes; it does not reset actual execution budgets' in messages
    assert 'new bounded task is allowed only if its fixed capture contract can contain required evidence' in messages
    assert 'Never reset global budgets, remove old receipts or increase caps' in messages


@pytest.mark.parametrize('boundary', ['files', 'bytes', 'receipts'])
def test_legal_committed_boundary_is_not_proof_no_candidate_can_fit(tmp_path, boundary):
    records = ([{'output_port':'attachments', 'size_bytes':1}]*2 if boundary == 'files' else
        [{'output_port':'attachments', 'size_bytes':20}] if boundary == 'bytes' else [{'size_bytes':0}]*128)
    # Reference-access observations do not consume the producer's 128 receipt cap.
    records += [{'record_type':'reference_access'}]*3
    runs = SnapshotRuns(tmp_path/'snapshot.sqlite', records)
    error = budget_error()
    worker = classify_candidate_attachment_error(error, runs=runs, run_id='exact', affected_action='tool_call')
    final = classify_submission_error(error, runs=runs, run_id='exact')
    for failure in (worker, final):
        assert failure.disposition == 'reject' and failure.category == 'output_rejected'
        assert all(item['repairable'] for item in failure.details)
        assert 'submission_intervention_required' not in str(failure.details)
        assert 'A compliant correction is not guaranteed' in str(failure.details)
        assert 'exact triggering dimension are unknown' in str(failure.details)
        assert 'do not evade capture of required unretained evidence' in str(failure.details)
        assert_bounded(failure)
        assert_recovery_does_not_reset_capacity(failure)
    assert {item['affected_action'] for item in worker.details} == {'tool_call'}
    assert {item['affected_action'] for item in final.details} == {'submit'}
    assert any(statement == 'BEGIN' for statement in runs.statements)
    assert any('PRAGMA query_only = ON' in statement for statement in runs.statements)


@pytest.mark.parametrize('fault', ['over_count', 'over_bytes', 'over_item', 'over_receipts', 'malformed',
    'reference_attachment', 'missing_policy', 'unknown_run', 'unavailable', 'accepted', 'expired'])
def test_unknown_or_illegal_committed_budget_never_promises_worker_correction(tmp_path, fault):
    records = [{'output_port':'attachments', 'size_bytes':1}]*3 if fault == 'over_count' else (
        [{'output_port':'attachments', 'size_bytes':11}]*2 if fault == 'over_bytes' else
        [{'output_port':'attachments', 'size_bytes':21}] if fault == 'over_item' else
        [{'size_bytes':0}]*129 if fault == 'over_receipts' else
        [{'record_type':'reference_access', 'output_port':'attachments', 'size_bytes':21}] if fault == 'reference_attachment' else
        [{'output_port':'attachments', 'size_bytes':'1'}] if fault == 'malformed' else [])
    runs = SnapshotRuns(tmp_path/'snapshot.sqlite', records)
    with runs._connect() as db:
        if fault == 'missing_policy': db.execute("UPDATE runs SET recovery_policy_json='{}'")
        if fault == 'accepted': db.execute("UPDATE runs SET accepted_candidate_digest='already accepted'")
        if fault == 'expired': db.execute("UPDATE runs SET deadline_at='2000-01-01T00:00:00Z'")
    if fault == 'unavailable': runs._connect = lambda: (_ for _ in ()).throw(sqlite3.OperationalError('unavailable'))
    run_id = 'unknown' if fault == 'unknown_run' else 'exact'
    for failure in (classify_candidate_attachment_error(budget_error(), runs=runs, run_id=run_id, affected_action='tool_call'),
            classify_submission_error(budget_error(), runs=runs, run_id=run_id)):
        assert failure.disposition == 'intervene'
        assert not any(item['repairable'] for item in failure.details)
        assert 'submission_intervention_required' in str(failure.details)
        assert_bounded(failure)
        assert_recovery_does_not_reset_capacity(failure)


@pytest.mark.parametrize('cause,expected', [(CASIntegrityError('exact evidence'), 'integrity_failure'),
    (OSError(28, 'disk full'), 'runtime_failure'), (ConnectionError('reset'), 'runtime_failure')])
def test_final_budget_rule_cannot_override_integrity_storage_or_transport(cause, expected):
    error = budget_error()
    error.__cause__ = cause
    runs = SimpleNamespace(_connect=lambda: pytest.fail('Higher-priority failure read candidate budget'))
    failure = classify_submission_error(error, runs=runs, run_id='exact')
    assert failure.category == expected
    assert failure.disposition == ('retry' if isinstance(cause, ConnectionError) else 'fail')
    assert classify_submission_error(budget_error(), deadline_expired=True, runs=runs, run_id='exact').category == 'run_timeout'


def test_unrecognized_publication_errors_keep_existing_policy():
    for message in ('This task has no attachment capability', 'Unknown publication failure',
            'Attachment byte budget exceeded', 'Attachment grew beyond the byte budget'):
        error = ToolInputError('attachment_publication_invalid', message)
        assert classify_candidate_attachment_error(error) is None
        assert classify_submission_error(error).disposition == 'intervene'
    assert classify_candidate_attachment_error(DiagnosticError('unowned', details=budget_error().details)) is None


def test_actual_publish_rejection_preserves_old_receipt_and_exact_reuse(tmp_path, installed):
    f = _start_native(tmp_path, settings=AgentSettings(attachments=AttachmentSettings(max_files=1)))
    alias = f.runtime.runs.status(f.run_id).inputs[0].source_name
    first = f.workspace/'scratch/first.txt'
    first.write_bytes(b'exact original')
    request = {'files':[{'path':'scratch/first.txt', 'purpose':'Original evidence'}], 'source_aliases':[alias]}
    published = f.worker.call_tool('worker_publish_files', request)
    receipts = f.runtime.runs.tool_evidence(f.run_id)
    (f.workspace/'scratch/second.txt').write_bytes(b'current unaccepted draft')
    with pytest.raises(DiagnosticError) as caught:
        f.worker.call_tool('worker_publish_files', {**request, 'files':[{'path':'scratch/second.txt', 'purpose':'Candidate'}]})
    assert all(item['repairable'] for item in caught.value.details)
    assert 'submission_intervention_required' not in str(caught.value.details)
    assert 'attention_required' not in f.root.call_tool('run_status', {'name':'compute', 'intent':'status'})
    assert f.runtime.runs.tool_evidence(f.run_id) == receipts
    assert f.worker.call_tool('worker_publish_files', request) == published
    first.write_bytes(b'changed identity')
    with pytest.raises(DiagnosticError): f.worker.call_tool('worker_publish_files', request)
    assert f.runtime.runs.tool_evidence(f.run_id) == receipts


def test_actual_stage_and_final_candidate_correction_preserves_frozen_roots_and_original(tmp_path, installed):
    f = _start_native(tmp_path, settings=AgentSettings(attachments=AttachmentSettings(max_files=2)))
    runs = f.runtime.runs
    policy_before = runs.status(f.run_id).recovery_policy
    root = f.workspace/'scratch/artifacts'
    root.mkdir(exist_ok=True)
    required = root/'required.txt'
    required.write_bytes(b'required exact observation')
    optional = root/'unadopted.txt'
    optional.write_bytes(b'unaccepted draft')
    request = {'stage':'design', 'conclusion':'Retain the required exact observation.', 'materials':['file:scratch/artifacts/required.txt']}
    with pytest.raises(DiagnosticError) as caught: f.worker.call_tool('worker_experiment_stage', request)
    assert all(item['repairable'] for item in caught.value.details)
    assert 'attention_required' not in f.root.call_tool('run_status', {'name':'compute', 'intent':'status'})
    optional.rename(f.workspace/'scratch/unadopted.txt')
    stage = f.worker.call_tool('worker_experiment_stage', request)
    old = runs.tool_evidence(f.run_id)
    original = next(record for record in old if record.get('metadata', {}).get('file_name') == 'required.txt')
    assert runs.read_tool_evidence(runs.status(f.run_id), original['alias']) == b'required exact observation'
    # Require a new candidate without discarding the already retained original.
    (root/'new-unadopted.txt').write_bytes(b'new draft')
    result = {'payload':{'summary':'The exact observation was retained; no scientific success inferred.',
        'outcome':'inconclusive', 'limitations':['Fixture has no independent scientific validation.'],
        'remaining_question':'Needs scientific judgment.', 'adopted_stages':[stage['reference']]}}
    (f.workspace/'output/result.json').write_text(json.dumps(result))
    rejected = f.worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected' and all(item['repairable'] for item in rejected['diagnostics'])
    assert 'submission_intervention_required' not in str(rejected)
    assert runs.status(f.run_id).state == 'running'
    assert 'attention_required' not in f.root.call_tool('run_status', {'name':'compute', 'intent':'status'})
    for path in tuple(root.iterdir()): path.rename(f.workspace/'scratch'/path.name)
    assert f.worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    current = runs.tool_evidence(f.run_id)
    assert all(record in current for record in old)
    assert runs.read_tool_evidence(runs.status(f.run_id), original['alias']) == b'required exact observation'
    assert runs.status(f.run_id).recovery_policy['attachments'] == policy_before['attachments']
    assert f.compiled.spec.artifact_capture.roots == ('scratch/artifacts',)


def test_actual_worker_unknown_snapshot_replaces_default_repairable_and_notifies_control(tmp_path, installed):
    f = _start_native(tmp_path)
    runs = f.runtime.runs
    with runs._connect() as db:
        policy = dict(runs.status(f.run_id).recovery_policy)
        policy['attachments'] = {**policy['attachments'], 'max_files':'invalid control settings'}
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (json.dumps(policy), f.run_id))
    # Exercise the actual common error wrapper with a recognized producer error.
    # A broken snapshot must not keep ToolInputError's default repairable=True.
    error = f.worker._engineering_failure('worker_publish_files', budget_error())
    assert not any(item['repairable'] for item in error.details)
    assert 'submission_intervention_required' in str(error.details)
    f.worker._record_failure_safely('worker_publish_files', error)
    assert f.root.call_tool('run_status', {'name':'compute', 'intent':'status'})['attention_required']
    assert runs.status(f.run_id).state == 'running'
