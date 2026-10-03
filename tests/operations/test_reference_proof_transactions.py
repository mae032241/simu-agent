"""Receipt transaction, historical proof repair, and error classification regressions."""
import json
import sqlite3

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from tests.operations.test_sealed_reference_replay import evidence_submission
from tests.operations.test_instance_archive import archive_system


def test_evidence_write_survives_delete_journal_cache_spill(tmp_path, monkeypatch):
    runs, owner, args = evidence_submission(tmp_path)
    with runs._connect() as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    def small_cache():
        db = sqlite3.connect(runs.database_path, timeout=.05)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA cache_size=2')
        db.execute('PRAGMA cache_spill=2')
        return db
    monkeypatch.setattr(runs, '_connect', small_cache)
    record = runs.accept_tool_evidence(**{**args,
        'metadata': {'kind': 'figure_file', 'note': 'x'*32000}})
    assert len(runs.tool_evidence(owner.run_id)) == 1
    proof = runs.reference_manifest(owner, subject_ref=ArtifactRef.model_validate(record['artifact_ref']))
    assert json.loads(runs.artifacts.read(proof))['records'][0]['metadata']['note'] == 'x'*32000


@pytest.mark.parametrize('proof_exists', [False, True])
def test_legacy_overfull_run_repairs_only_required_material_proof(tmp_path, monkeypatch, proof_exists):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    runs, owner, args = evidence_submission(tmp_path)
    with monkeypatch.context() as patch:
        if not proof_exists:
            patch.setattr(runs, 'reference_manifest', lambda *a, **k: None)
        first = runs.accept_tool_evidence(**args)
    # Reconstruct a legacy Run's 128 stored receipts. Inputs push the whole-Run
    # snapshot over 128 bindings, despite the requested receipt itself being small.
    template = runs.tool_evidence(owner.run_id)[0]
    with runs._connect() as db:
        for number in range(2, 129):
            ref = runs.artifacts.register(canonical_json({'number': number}), ArtifactRegistration(
                kind='tool_evidence', schema_id='opaque', payload_schema_version=1,
                media_type='application/json', creator=runs.service_actor), idempotency_key=f'legacy-{number}').ref
            record = {**template, 'alias': f'tool_evidence_{number:03d}', 'artifact_ref': ref.model_dump(mode='json')}
            db.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                (owner.run_id, number, f'legacy-{number}', canonical_json(record), record['alias']))
    assert runs.accept_tool_evidence(**args) == first
    ref = ArtifactRef.model_validate(first['artifact_ref'])
    proof = runs.reference_manifest(owner, subject_ref=ref)
    document = json.loads(runs.artifacts.read(proof))
    assert len(document['records']) == 1
    assert set(document['bindings']) == {first['alias'], args['derived_from'][0]}
    assert runs.accept_tool_evidence(**args) == first
    assert runs.reference_manifest(owner, subject_ref=ref) == proof
    assert len(runs.tool_evidence(owner.run_id)) == 128


def test_programming_error_keeps_technical_failure_identity(archive_system, monkeypatch):
    from tests.operations.test_budget_pool_isolation import grants
    runtime, _, requests = grants(archive_system)
    def programming_error(**kwargs):
        raise TypeError('fixture programming bug')
    monkeypatch.setattr(runtime.approvals, 'budget_extension_decisions', programming_error)
    with pytest.raises(TypeError, match='fixture programming bug'):
        runtime.executions.record_budget_extension_decision(**requests[0])
    assert runtime.approvals.status(requests[0]['approval_id']).status == 'pending'


def test_dependency_count_does_not_replace_complete_proof_byte_budget(tmp_path):
    from scidiscovery.artifact_agent.service.reference_proofs import material_snapshot
    from scidiscovery.operation_contract import DiagnosticError
    runs, owner, args = evidence_submission(tmp_path)
    runs.accept_tool_evidence(**args)
    template = runs.tool_evidence(owner.run_id)[0]
    records = []
    previous = owner.inputs[0].source_name
    # One input and 128 transitively required receipts: none may be discarded.
    for number in range(128):
        alias = f'required_{number:03d}'
        records.append({**template, 'alias': alias,
            'metadata': {'derived_from': [previous]}})
        previous = alias
    complete = json.loads(material_snapshot(owner, records[-1], records, [], [], None))
    assert len(complete['bindings']) == 129
    # Actual oversize still fails, without truncating any dependency.
    records[0]['metadata']['historical_notes'] = 'x' * (1024 * 1024)
    with pytest.raises(DiagnosticError) as caught:
        material_snapshot(owner, records[-1], records, [], [], None)
    assert caught.value.details[0]['code'] == 'reference_proof_limit'
    assert caught.value.details[0]['repairable'] is False


def test_recovered_calculation_retains_exact_attempt_and_sources(tmp_path):
    from tests.operations.test_analysis_claim_scope import generic_worker
    from tests.operations.test_result_analysis_tool import score_inputs
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.calculation_proof import ControlledCalculationRecord
    from scidiscovery.artifact_agent.service.reference_access import _calculation_origin
    worker, _, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    result = worker.call_tool('worker_curve_score', {'record_key': 'retained', 'request': score_inputs()[1]})
    assert result['status'] == 'computed', result
    previous = runs.status(worker._run_id)
    runs.record_failure(previous.run_id, reason='fixture interrupted after calculation',
        expected_state=previous.state, expected_last_activity_at=previous.last_activity_at)
    made = root.call_tool('operation_invoke', dict(name='recovered', draft_from='generic_analysis', max_attempts=2,
        operation_id='science.result.diagnose.v1', instruction='Reuse the exact retained calculation.',
        inputs=[dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']),
            dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    assert made['result']['state'] == 'queued', made
    operation = catalog.operation('science.result.diagnose.v1')
    following = LocalWorkerMCPRouter(runs, operation_id=operation.spec.operation_id,
        operation_digest=operation.digest)
    following.call_tool('worker_open_assignment', {})
    owner = runs.status(following._run_id)
    record = next(r for r in runs.tool_evidence(owner.run_id) if r['alias'] == result['calculation_ref'])
    proof = runs.reference_manifest(owner, subject_ref=ArtifactRef.model_validate(record['artifact_ref']))
    manifest = json.loads(runs.artifacts.read(proof))
    calculation = ControlledCalculationRecord.model_validate_json(canonical_json(record['metadata']['calculation_proof']))
    origin, _ = _calculation_origin(manifest, calculation)
    assert origin.source_request_digest == previous.request_digest
    assert len(origin.attempts) == 1
    assert set(origin.bindings) == set(origin.attempts[0].read_sources) | set(calculation.input_digests)
    assert not manifest['attempts']
    assert origin.attempts[0].state == 'completed'
    assert all(binding.artifact_ref in runs.artifacts.catalog(proof).parent_refs for binding in origin.bindings.values())


def test_legacy_large_recovery_proof_allows_tool_call_and_finalization(tmp_path):
    from tests.operations.test_analysis_claim_scope import generic_worker
    from tests.operations.test_result_analysis_tool import score_inputs
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.calculation_proof import ControlledCalculationRecord
    from scidiscovery.artifact_agent.service.reference_access import _calculation_origin
    worker, _, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    result = worker.call_tool('worker_curve_score', {'record_key': 'retained', 'request': score_inputs()[1]})
    assert result['status'] == 'computed', result
    previous = runs.status(worker._run_id)
    runs.record_failure(previous.run_id, reason='fixture interrupted after calculation',
        expected_state=previous.state, expected_last_activity_at=previous.last_activity_at)
    made = root.call_tool('operation_invoke', dict(name='recovered', draft_from='generic_analysis', max_attempts=2,
        operation_id='science.result.diagnose.v1', instruction='Reuse the exact retained calculation.',
        inputs=[dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']),
            dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    assert made['result']['state'] == 'queued', made
    operation = catalog.operation('science.result.diagnose.v1')
    following = LocalWorkerMCPRouter(runs, operation_id=operation.spec.operation_id,
        operation_digest=operation.digest)
    following.call_tool('worker_open_assignment', {})
    owner = runs.status(following._run_id)
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    template = runs.tool_evidence(previous.run_id)[0]
    with runs._connect() as db:
        count = db.execute('SELECT COUNT(*) FROM run_tool_evidence WHERE run_id=?', (previous.run_id,)).fetchone()[0]
        for number in range(count + 1, 129):
            raw = canonical_json({'historical_observation': number})
            original = runs.artifacts.register(raw, ArtifactRegistration(kind='tool_evidence', schema_id='opaque',
                payload_schema_version=1, media_type='application/json', creator=runs.service_actor,
                parent_refs=(previous.inputs[0].artifact_ref,),
                labels={'tool_producer_run': previous.run_id, 'tool_name': 'historical_tool'}),
                idempotency_key=f'legacy-observation-{number}').ref
            record = {**template, 'alias': f'legacy_{number:03d}', 'artifact_ref': original.model_dump(mode='json'),
                'source_ref': previous.inputs[0].artifact_ref.model_dump(mode='json'), 'size_bytes': len(raw),
                'metadata': {'kind': 'analysis_derived', 'derived_from': [previous.inputs[0].source_name]},
                'tool_name': 'historical_tool'}
            db.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                (previous.run_id, number, f'legacy-{number}', canonical_json(record), record['alias']))
    reply = following.call_tool('worker_curve_score', {'record_key': 'after_recovery', 'request': score_inputs()[1]})
    assert reply['status'] == 'computed', reply
    from tests.operations.test_analysis_claim_scope import submit
    from tests.operations.test_analysis_artifact_references import cite
    from tests.operations.test_result_analysis_tool import limited_report
    opened = following.call_tool('worker_open_assignment', {})
    assert submit(following, opened, cite(limited_report(), reply['calculation_ref']))['state'] == 'completed'
    manifest = json.loads(runs._evidence_snapshot(owner.run_id))
    assert len(manifest['recovery']['bindings']) > 128


def test_new_receipt_checks_complete_snapshot_budget_before_commit(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import reference_proofs
    runs, owner, args = evidence_submission(tmp_path)
    original = runs.accept_tool_evidence(**args)
    limit = len(runs._evidence_snapshot(owner.run_id))
    with monkeypatch.context() as patch:
        patch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', limit)
        with pytest.raises(reference_proofs.ReferenceProofError) as caught:
            runs.accept_tool_evidence(**{**args, 'raw': b'new observation'})
        assert caught.value.details[0]['code'] == 'reference_proof_limit'
        assert len(runs.tool_evidence(owner.run_id)) == 1
        assert runs.accept_tool_evidence(**args) == original
    assert runs.accept_tool_evidence(**{**args, 'raw': b'new observation'})['alias'] == 'tool_evidence_002'


def test_final_submission_reports_control_proof_limit_and_retains_draft(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import reference_proofs
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    from tests.operations.test_result_analysis_tool import limited_report
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    with monkeypatch.context() as patch:
        patch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
        result = submit(worker, opened, limited_report())
    assert result['state'] == 'failed', result
    assert 'reference_proof_limit' in json.dumps(result)
    assert 'checker_failure' not in json.dumps(result)
    stopped = system[1].runs.status(worker._run_id)
    assert stopped.state == 'failed' and stopped.output_ref is None
    assert stopped.recovery_draft['draft_digest']
    assert stopped.recovery_draft['evidence_proof_unavailable'] == 'reference_proof_limit'
    assert system[1].runs.diagnostic_summary(stopped)['failure']['category'] == 'runtime_failure'
