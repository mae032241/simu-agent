"""Upgrade, failed collection, proof admission and error settlement boundaries."""
import json
import sqlite3
from pathlib import Path
import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service import reference_proofs


@pytest.mark.parametrize('collection_state', ['failed', 'timed_out', 'interrupted'])
@pytest.mark.parametrize('outcome', ['blocked', 'inconclusive'])
def test_failed_collection_allows_only_explicit_limited_report(tmp_path, monkeypatch, collection_state, outcome):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from tests.operations.test_experiment_continuation import submit
    f = experiment(tmp_path, monkeypatch, seconds=60)
    assert start(f)['state'] == 'running'
    f.adapter.state = 'succeeded'
    monkeypatch.setattr(f.coordinator.collection, 'summary', lambda _: {'state': collection_state}, raising=False)
    assert submit(f, [f.alias], outcome=outcome)['state'] == 'rejected'
    path = f.workspace / 'output/result.json'
    raw = json.loads(path.read_bytes())
    raw['payload']['limitations'] = ['Collection failed; no solver results were delivered or scored.']
    path.write_bytes(canonical_json(raw))
    assert f.worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert f.adapter.submits == 1
    assert not [r for r in f.runs.tool_evidence(f.run_id) if r['metadata'].get('kind') == 'experiment_execution']
    # A finite negative report must not hide the original recoverable execution.
    from types import SimpleNamespace
    f.root.facade.execution_bridge = f.coordinator.bridge
    f.root.facade.execution_collection = SimpleNamespace(collect=f.coordinator.collection.collect, summary=lambda _: {})
    listed = f.root.call_tool('execution_list', {}, surface='execution')['executions']
    assert len(listed) == 1
    f.root.call_tool('execution_collect', {'name': listed[0]['name']}, surface='execution')
    assert f.adapter.submits == 1
    report = f.runtime.artifacts.read(f.runs.status(f.run_id).output_ref)
    assert json.loads(report)['outcome'] == outcome


@pytest.mark.parametrize('solver_state', ['succeeded', 'failed', 'cancelled'])
def test_failed_collection_cannot_claim_completion_or_disappear_while_active(tmp_path, monkeypatch, solver_state):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from tests.operations.test_experiment_continuation import submit
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    f.adapter.state = solver_state
    monkeypatch.setattr(f.coordinator.collection, 'summary', lambda _: {'state': 'failed'}, raising=False)
    assert submit(f, [f.alias], outcome='completed')['state'] == 'rejected'
    monkeypatch.setattr(f.coordinator.collection, 'summary', lambda _: {'state': 'interrupted', 'recovery_pending': True})
    assert 'experiment_outstanding_work' in json.dumps(submit(f, [f.alias], outcome='blocked'))


def test_proof_failure_settles_reference_reservation(tmp_path, monkeypatch):
    from tests.operations.test_reference_access import Harness, prepared
    harness = Harness(tmp_path)
    _, _, handle = prepared(harness)
    monkeypatch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
    response = harness.call('reader', action='read', reference=handle, pointer='/answer')
    assert response['state'] == 'rejected' and response['code'] == 'reference_proof_limit'
    with harness._connect() as db:
        events = harness._reference_events(db, harness._reference_scope(db, 'reader'))
    reserved = {r['reservation_id'] for k, r in events if k == 'reference_read_reserved'}
    settled = {r['reservation_id'] for k, r in events if k == 'reference_read_settled'}
    assert reserved == settled
    assert not harness.reference_access_records('reader')


def test_assignment_proof_failure_records_terminal_failure(tmp_path, monkeypatch):
    from tests.operations.test_analysis_claim_scope import generic_worker
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    worker, _, system = generic_worker(tmp_path, return_system=True)
    runs = system[1].runs
    owner = runs.status(worker._run_id)
    def unavailable(_):
        raise reference_proofs.proof_error('reference_proof_limit', 'Preserved proof exceeds budget.')
    monkeypatch.setattr(runs, 'adopt_tool_evidence', unavailable)
    with pytest.raises(RunStateConflict, match='preserved tool evidence'):
        runs.reopen(run_id=owner.run_id, operation_id=owner.operation_id, operation_digest=owner.operation_digest)
    assert runs.status(owner.run_id).state == 'failed'


def legacy_schema(resource):
    schema = json.loads(resource)
    for node in [schema, *schema['$defs'].values()]:
        if 'bindings' in node.get('properties', {}):
            node['properties']['bindings']['maxProperties'] = 128
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


@pytest.mark.parametrize('recover', [None, 'draft_from', 'resume_from'])
def test_old_task_reopens_or_recovers_under_exact_supported_contract(tmp_path, monkeypatch, recover):
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    from tests.operations.test_result_analysis_tool import limited_report
    from tests.operations.test_tcad_result_analysis import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service import tool_evidence
    from scidiscovery.operations.catalog import compile_catalog
    current = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    with monkeypatch.context() as patch:
        patch.setattr(tool_evidence, 'TOOL_EVIDENCE_SCHEMA', legacy_schema(tool_evidence.TOOL_EVIDENCE_SCHEMA))
        worker, opened, system = generic_worker(tmp_path, return_system=True)
    old_catalog, runtime, root, *_ = system
    runs = runtime.runs
    owner = runs.status(worker._run_id)
    golden = json.loads((Path(__file__).parents[1] / 'fixtures/operation_digests_964713f.json').read_bytes())
    assert owner.operation_digest == golden['operation_digests'][owner.operation_id]
    assert owner.operation_digest != current.operation(owner.operation_id).digest
    historical = current.operation(owner.operation_id, digest=owner.operation_digest)
    assert historical.output_contracts == old_catalog.operation(owner.operation_id).output_contracts
    assert historical.digest == owner.operation_digest
    assert not current.can_recover(owner.operation_id, '0' * 64, current.operation(owner.operation_id).digest)
    with pytest.raises(KeyError):
        current.operation(owner.operation_id, digest='0' * 64)
    runs.operation_catalog = current
    root.facade._operation_catalog = current
    if recover:
        runs.record_failure(owner.run_id, reason='Interrupted before upgrade', expected_state=owner.state,
            expected_last_activity_at=owner.last_activity_at)
        made = root.call_tool('operation_invoke', dict(name='upgraded_recovery', **{recover: 'generic_analysis'}, max_attempts=2,
            operation_id=owner.operation_id, instruction='Continue exact interrupted task.', inputs=[
                dict(port='experiment_plan', artifact_names=['plan']),
                dict(port='experiment_results', artifact_names=['generic_results']), dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
        assert made['result']['state'] == 'queued', made
        following = LocalWorkerMCPRouter(runs, operation_id=owner.operation_id, operation_digest=current.operation(owner.operation_id).digest)
        opened = following.call_tool('worker_open_assignment', {})
    else:
        following = LocalWorkerMCPRouter(runs, operation_id=owner.operation_id, operation_digest=owner.operation_digest)
        opened = following.call_tool('worker_open_assignment', {})
        # The old identity keeps its old output constraint, not just its hash.
        raw = json.loads(runs._evidence_snapshot(owner.run_id))
        binding = next(iter(raw['bindings'].values()))
        raw['bindings'] = {f'bound_{i}': binding for i in range(129)}
        with monkeypatch.context() as patch:
            patch.setattr(runs, '_evidence_snapshot', lambda _: canonical_json(raw))
            with pytest.raises(reference_proofs.ReferenceProofError) as caught:
                runs._prepare_evidence_snapshot(owner.run_id)
            assert caught.value.details[0]['code'] == 'reference_proof_contract_limit'
    assert submit(following, opened, limited_report())['state'] == 'completed'
    name = 'upgraded_recovery' if recover else 'generic_analysis'
    status = root.call_tool('run_status', dict(name=name))
    assert status['operation_contract_status'] == ('current' if recover else 'supported_historical')
    assert status['sealed_output_status'] == 'available'
    downstream = root.call_tool('operation_invoke', dict(name='downstream_analysis', max_attempts=2,
        operation_id=owner.operation_id, instruction='Use the exact sealed prior analysis.', inputs=[
            dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']),
            dict(port='curve_bundle', artifact_names=['generic_bundle']),
            dict(port='prior_analysis', artifact_names=[name + '.output'])]))
    assert downstream['result']['state'] == 'queued', downstream
    consumer = LocalWorkerMCPRouter(runs, operation_id=owner.operation_id,
        operation_digest=current.operation(owner.operation_id).digest)
    assignment = consumer.call_tool('worker_open_assignment', {})
    assert submit(consumer, assignment, limited_report())['state'] == 'completed'


def test_attachment_streaming_does_not_hold_run_write_lock(tmp_path, monkeypatch):
    from tests.operations.test_scientific_attachments import publish_fixture
    _, runtime, _, worker, _, _, _, _, _, args = publish_fixture(tmp_path)
    put = runtime.artifacts.cas.put_file
    def verify_unlocked(*values, **options):
        with runtime.runs._connect() as db:
            db.execute('PRAGMA busy_timeout=50')
            db.execute('BEGIN IMMEDIATE')
            db.rollback()
        return put(*values, **options)
    monkeypatch.setattr(runtime.artifacts.cas, 'put_file', verify_unlocked)
    saved = worker.call_tool('worker_publish_files', args)
    assert saved['state'] == 'retained'
    assert worker.call_tool('worker_publish_files', args) == saved


def test_exhausted_attachment_budget_rejects_before_cas_copy(tmp_path, monkeypatch):
    from tests.operations.test_scientific_attachments import publish_fixture
    from scidiscovery.operation_contract import DiagnosticError
    _, runtime, _, worker, _, _, _, _, _, args = publish_fixture(tmp_path)
    runs, rid = runtime.runs, worker._run_id
    owner = runs.status(rid)
    policy = dict(owner.recovery_policy)
    policy['attachments'] = {**policy['attachments'], 'max_files': 1}
    with runs._connect() as db:
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (canonical_json(policy), rid))
    monkeypatch.setattr(runtime.artifacts.cas, 'put_file', lambda *a, **k: pytest.fail('over-budget files copied to CAS'))
    with pytest.raises(DiagnosticError):
        worker.call_tool('worker_publish_files', args)


def test_delivery_reconciliation_proof_error_is_structured(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment
    from tests.operations.test_experiment_continuation import submit
    f = experiment(tmp_path, monkeypatch, seconds=60)
    def failed(_):
        raise reference_proofs.proof_error('reference_proof_limit', 'Complete receipt proof exceeds budget.')
    monkeypatch.setattr(f.coordinator, 'require_idle', failed)
    result = submit(f, [f.alias], outcome='inconclusive')
    assert result['state'] == 'failed'
    assert 'reference_proof_limit' in json.dumps(result)
    assert 'Root' in json.dumps(result)
    assert f.runs.status(f.run_id).state == 'failed'


def test_derived_receipt_retains_its_exact_parent_edges(tmp_path):
    from tests.operations.test_sealed_reference_replay import evidence_submission
    runs, owner, args = evidence_submission(tmp_path)
    result = runs.accept_tool_evidence(**args)
    assert result['control_parents'] == [owner.inputs[0].artifact_ref.model_dump(mode='json')]
    assert runs.accept_tool_evidence(**args) == result


def test_real_recovery_proof_limit_fails_open_without_partial_adoption(tmp_path, monkeypatch):
    from tests.operations.test_analysis_claim_scope import generic_worker
    from tests.operations.test_result_analysis_tool import score_inputs
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    worker, _, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    assert worker.call_tool('worker_curve_score', {'record_key': 'before_failure', 'request': score_inputs()[1]})['status'] == 'computed'
    owner = runs.status(worker._run_id)
    runs.record_failure(owner.run_id, reason='Interrupted', expected_state=owner.state,
        expected_last_activity_at=owner.last_activity_at)
    made = root.call_tool('operation_invoke', dict(name='proof_recovery', draft_from='generic_analysis', max_attempts=2,
        operation_id=owner.operation_id, instruction='Continue with the retained evidence.', inputs=[
            dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']), dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    assert made['result']['state'] == 'queued'
    rid = runtime.scheduler_bindings.resolve(instance=owner.instance_id, namespace='run', name='proof_recovery')
    monkeypatch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
    with pytest.raises(RunStateConflict, match='preserved tool evidence'):
        runs.open(run_id=rid, operation_id=owner.operation_id, operation_digest=catalog.operation(owner.operation_id).digest)
    assert runs.status(rid).state == 'failed'
    assert not runs.tool_evidence(rid)


def test_explicit_adopt_checks_combined_proof_before_commit(tmp_path, monkeypatch):
    from dataclasses import replace
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    from tests.operations.test_result_analysis_tool import limited_report
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    _, runtime, root, *_ = system
    runs, owner = runtime.runs, runtime.runs.status(worker._run_id)
    receipt = runs.accept_tool_evidence(owner.run_id, tool_name='worker_curve_score', allowed_ports=('tool_evidence',),
        raw=b'{}', media_type='application/json', metadata={'kind': 'analysis_derived'}, derived_from=(owner.inputs[0].source_name,))
    assert submit(worker, opened, limited_report())['state'] == 'completed'
    completed = runs.status(owner.run_id)
    manifest = next(ref for ref in runtime.artifacts.catalog(completed.output_ref).parent_refs
        if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1')
    root.call_tool('operation_invoke', dict(name='adopting', operation_id=owner.operation_id,
        instruction='Reuse exact receipts.', inputs=[dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['generic_results']), dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    rid = runtime.scheduler_bindings.resolve(instance=owner.instance_id, namespace='run', name='adopting')
    following, _ = runs.open(run_id=rid, operation_id=owner.operation_id, operation_digest=owner.operation_digest)
    # Bind the exact completed manifest and member as a control-prepared input
    # fixture. Receipt identity and producer verification remain real.
    inputs = (*following.inputs,
        replace(following.inputs[0], source_name='preserved', artifact_ref=manifest),
        replace(following.inputs[0], source_name='member', artifact_ref=ArtifactRef.model_validate(receipt['artifact_ref'])))
    original = runs._require_running
    monkeypatch.setattr(runs, '_require_running', lambda value: replace(following, inputs=inputs) if value == rid else original(value))
    with monkeypatch.context() as patch:
        patch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
        with pytest.raises(reference_proofs.ReferenceProofError):
            runs.adopt_bound_tool_evidence(rid, allowed_ports=('tool_evidence',), manifest_alias='preserved')
    assert not runs.tool_evidence(rid)
    saved = runs.adopt_bound_tool_evidence(rid, allowed_ports=('tool_evidence',), manifest_alias='preserved')
    assert saved
    assert len(runs.tool_evidence(rid)) == 1
    with monkeypatch.context() as patch:
        patch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
        assert runs.adopt_bound_tool_evidence(rid, allowed_ports=('tool_evidence',), manifest_alias='preserved') == saved


@pytest.mark.parametrize('error', [sqlite3.OperationalError('database is locked'),
    TimeoutError('control observation timed out')])
def test_transient_reconciliation_rejects_without_failing_owner(tmp_path, monkeypatch, error):
    from tests.operations.test_experiment_approval_handoff import experiment
    from tests.operations.test_experiment_continuation import submit
    f = experiment(tmp_path, monkeypatch, seconds=60)
    def unavailable(_):
        raise error
    with monkeypatch.context() as patch:
        patch.setattr(f.coordinator, 'require_idle', unavailable)
        reply = submit(f, [f.alias], outcome='inconclusive')
    assert reply['state'] == 'rejected' and 'submission_temporarily_unavailable' in str(reply)
    assert f.runs.status(f.run_id).state == 'running'
    assert f.worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert f.adapter.submits == 0


@pytest.mark.parametrize('error', [ValueError('ambiguous control mapping'), OSError('CAS unavailable')])
def test_unclassified_reconciliation_error_preserves_task_and_diagnostics(tmp_path, monkeypatch, error):
    from tests.operations.test_experiment_approval_handoff import experiment
    from tests.operations.test_experiment_continuation import submit
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import WorkerToolError
    f = experiment(tmp_path, monkeypatch, seconds=60)
    def unavailable(_):
        raise error
    with monkeypatch.context() as patch:
        patch.setattr(f.coordinator, 'require_idle', unavailable)
        reply = submit(f, [f.alias], outcome='inconclusive')
    assert reply['state'] == 'rejected' and 'submission_intervention_required' in str(reply)
    assert f.runs.status(f.run_id).state == 'running'
    assert f.worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_limited_completed_owner_cannot_start_legacy_unsubmitted_request(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment, start
    from tests.operations.test_experiment_continuation import submit
    from scidiscovery.artifact_agent.service.executions import ExecutionServiceError
    f = experiment(tmp_path, monkeypatch, seconds=5400)
    assert start(f)['state'] == 'awaiting_authorization'
    # Represent a legacy/control-inconsistent closed owner. Current delivery
    # admission normally prevents closing with an unsubmitted request.
    with monkeypatch.context() as patch:
        patch.setattr(f.coordinator, 'require_idle', lambda _: ())
        assert submit(f, [f.alias], outcome='blocked')['state'] == 'completed'
    binding = next(b for b in f.runtime.scheduler_bindings.list(instance=f.instance.instance_id,
        namespace='execution') if b.name.startswith('experiment-' + f.run_id + '-'))
    assert f.runs.task_recovery_available(f.run_id, instance_id=f.instance.instance_id)
    assert not f.runs.task_recovery_available(f.run_id, instance_id=f.instance.instance_id, for_start=True)
    # Even auto-authorization eligibility must not add start to the menu.
    monkeypatch.setattr(f.coordinator, '_approval_status', lambda _: None)
    assert 'execution_start' not in f.coordinator.recovery_actions(binding.object_id)
    f.root.facade.execution_bridge = f.coordinator.bridge
    with pytest.raises(ExecutionServiceError, match='result recovery only'):
        f.root.call_tool('execution_start', {'name': binding.name}, surface='execution')
    assert f.adapter.submits == 0


def test_real_964713f_operation_identities_remain_resolvable():
    # Generated once by importing the actual archived commit, not by modifying
    # current schema definitions. The fixture needs neither git nor old code in CI.
    from tests.operations.test_tcad_result_analysis import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    golden = json.loads((Path(__file__).parents[1] / 'fixtures/operation_digests_964713f.json').read_bytes())
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    for operation_id, digest in golden['operation_digests'].items():
        assert catalog.operation(operation_id, digest=digest).digest == digest
