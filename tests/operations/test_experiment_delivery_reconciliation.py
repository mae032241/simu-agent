"""Delayed collection and historical provenance must preserve exact deliveries."""
import json
from types import SimpleNamespace

import pytest

from tests.operations.test_experiment_approval_handoff import experiment, start
from tests.operations.test_approval_wait_recovery import execution
from tests.operations.test_experiment_continuation import submit


@pytest.mark.parametrize('first_read', ['status', 'finalize'])
def test_async_collection_seals_once_without_second_collect(tmp_path, monkeypatch, first_read):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    eid = execution(f).object_id
    f.adapter.state = 'succeeded'
    f.worker.call_tool('worker_experiment_execute', {'action': 'advance'})
    finish = f.coordinator.collection.collect
    monkeypatch.setattr(f.coordinator.collection, 'collect', lambda *a, **kw: {'state': 'pending'})
    pending = f.worker.call_tool('worker_experiment_execute', {'action': 'collect'})
    assert 'reference' not in pending
    assert pending['outputs_status'] == 'not_collected'
    assert pending['next_action']['arguments']['action'] == 'status'
    finish(eid)
    if first_read == 'finalize':
        rejected = submit(f, [f.alias])
        assert rejected['state'] == 'rejected'
        assert 'collected_execution' in json.dumps(rejected)
    observed = f.worker.call_tool('worker_experiment_execute', {'action': 'status'})
    again = f.worker.call_tool('worker_experiment_execute', {'action': 'status'})
    assert observed['reference'] == again['reference']
    native = f.worker.call_tool('worker_experiment_execute', {'action': 'export', 'output_name': 'case-A/final.tdr'})
    assert (f.workspace / native['path']).read_bytes() == b'observed fixture\n'
    receipts = [r for r in f.runs.tool_evidence(f.run_id) if r['metadata'].get('kind') == 'experiment_execution']
    assert len(receipts) == 1 and len(receipts[0]['control_parents']) == 1
    stage = f.worker.call_tool('worker_experiment_stage', {'stage': 'validity', 'conclusion': 'Fixture qualifies.',
        'materials': [observed['reference']]})
    assert submit(f, [f.alias, observed['reference'], stage['reference']])['state'] == 'completed'
    assert f.adapter.submits == 1


@pytest.mark.parametrize('historical', [False, True])
def test_execution_receipt_distinguishes_inherited_result_from_its_own(tmp_path, monkeypatch, historical):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.reference_access import ReferenceAccessError
    f = experiment(tmp_path, monkeypatch, seconds=60)
    original = next(r for r in f.records if r['metadata'].get('kind') == 'experiment_execution')
    ref = ArtifactRef.model_validate(original['artifact_ref'])
    env = f.runtime.artifacts.catalog(ref)
    result = next(p for p in env.parent_refs if p.schema_id == 'scidiscovery.execution-result')
    manifest = json.loads(f.runtime.artifacts.read(result))
    manifest['execution_id'] = 'earlier_probe'
    prior = f.runtime.artifacts.register(canonical_json(manifest), ArtifactRegistration(kind='execution_result',
        schema_id='scidiscovery.execution-result', payload_schema_version=1, media_type='application/json',
        creator=f.runtime.actor), idempotency_key='prior_probe_result').ref
    receipt = f.runtime.artifacts.register(f.runtime.artifacts.read(ref), ArtifactRegistration(kind='experiment_material',
        schema_id='opaque', payload_schema_version=1, media_type='application/json',
        creator=f.runtime.actor, parent_refs=(prior, *env.parent_refs)), idempotency_key='receipt_with_old_input').ref
    selected = dict(original)
    if historical:
        selected.pop('control_parents', None)
    monkeypatch.setattr(f.runs, '_reference_read_bytes', lambda value, ref, policy, call: f.runtime.artifacts.read(ref))
    monkeypatch.setattr(f.runs, '_reference_deadline', lambda _: None)
    kwargs = dict(selected=selected, manifest={'bindings': {'old_probe': {'artifact_ref': prior.model_dump(mode='json')}}})
    edges = f.runs._execution_output_edges(None, receipt, None, {}, SimpleNamespace(run_id=f.old_id),
        result, None, None, **kwargs)
    assert {e['alias'] for e in edges} == {'observation', 'binary'}
    if historical:
        kwargs['manifest'] = {'bindings': {}}
    else:
        kwargs['selected'] = {**selected, 'control_parents': [prior.model_dump(mode='json')]}
    with pytest.raises(ReferenceAccessError):
        f.runs._execution_output_edges(None, receipt, None, {}, SimpleNamespace(run_id=f.old_id), result, None, None, **kwargs)


def test_initialization_delivers_native_files_without_output_path_declaration(tmp_path, monkeypatch):
    from tcad_artifact.debug_contract import CollectedTCADDebugFile, CollectedTCADDebugRun
    from tcad_artifact.experiment_capability import DebugInput
    f = experiment(tmp_path, monkeypatch, seconds=60)
    assert 'output_names' not in DebugInput.model_json_schema()['properties']
    debugger = f.coordinator.worker_services['tcad_artifact:tcad.development_debug'].adapter
    monkeypatch.setattr(debugger, 'collect_with_budget', lambda *a, **kw: CollectedTCADDebugRun(
        'succeeded', 0, 'complete', 'Fixture initialized.', 'done',
        (CollectedTCADDebugFile('debug.log.txt', 'text/plain', b'done'),
         CollectedTCADDebugFile('generated_native', 'application/x-synopsys-plx', b'EXACT PLX', 'case/t0.plx'))))
    value = f.worker.call_tool('worker_experiment_debug', {'name': 'native', 'mode': 'initialization', 'implementation': f.alias})
    assert value['scientific_claim_admissible'] is False
    output, = value['outputs']
    assert output['file_name'] == 'case/t0.plx'
    assert (f.workspace / output['path']).read_bytes() == b'EXACT PLX'
    record = f.runs.sealed_material_record(f.runs.status(f.run_id), output['reference'])
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    assert f.runtime.artifacts.read(ArtifactRef.model_validate(record['artifact_ref'])) == b'EXACT PLX'
    repeat = f.worker.call_tool('worker_experiment_debug', {'name': 'native', 'mode': 'initialization', 'implementation': f.alias})
    assert repeat['outputs'] == value['outputs'] and repeat['reference'] == value['reference']


@pytest.mark.parametrize('missing_required', [False, True])
def test_missing_later_case_preserves_completed_generated_files(tmp_path, missing_required):
    from tcad_artifact.remote_runner_py36 import _collect_expected
    raw = tmp_path / 'finished-case.plx'
    raw.write_bytes(b'previous case completed\n')
    if not missing_required:
        (tmp_path / 'later-case.plx').write_bytes(b'last case completed\n')
    records, errors = [], []
    _collect_expected(str(tmp_path), [{'name': 'later_case', 'relative_path': 'later-case.plx',
        'capture': 'workspace_file', 'required': True, 'max_bytes': 1024, 'media_type': 'text/plain'}],
        {'max_output_bytes': 4096, 'transfer_chunk_bytes': 1024}, records, errors,
        archive_entries=(), collect_generated_outputs=True)
    assert 'finished-case.plx' in {item['relative_path'] for item in records}
    assert bool(errors) == missing_required  # Partial bytes never turn failure into success.


@pytest.mark.parametrize('collect_pending', [False, True])
def test_final_delivery_waits_for_terminal_execution_collection(tmp_path, monkeypatch, collect_pending):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    eid = execution(f).object_id
    f.adapter.state = 'succeeded'
    if collect_pending:
        f.worker.call_tool('worker_experiment_execute', {'action': 'advance'})
        with monkeypatch.context() as patch:
            patch.setattr(f.coordinator.collection, 'collect', lambda *a, **kw: {'state': 'pending'})
            f.worker.call_tool('worker_experiment_execute', {'action': 'collect'})
    rejected = submit(f, [f.alias], outcome='blocked')
    assert rejected['state'] == 'rejected', rejected
    assert 'experiment_outstanding_work' in json.dumps(rejected)
    assert f.runs.status(f.run_id).state == 'running'
    assert f.runtime.executions.status(eid).state == 'succeeded'
    assert f.runtime.executions.status(eid).result_ref is None
    f.coordinator.collection.collect(eid)
    # Finalization itself must publish the completed collector's receipt.
    assert submit(f, [f.alias], outcome='blocked')['state'] == 'completed'
    receipts = [r for r in f.runs.tool_evidence(f.run_id) if r['metadata'].get('kind') == 'experiment_execution']
    assert len(receipts) == 1
    assert f.adapter.submits == 1


@pytest.mark.parametrize('terminal', ['failed', 'cancelled'])
def test_failed_solver_still_waits_for_active_collector(tmp_path, monkeypatch, terminal):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    f.adapter.state = terminal
    with monkeypatch.context() as patch:
        patch.setattr(f.coordinator.collection, 'summary', lambda _: {'state': 'running'}, raising=False)
        rejected = submit(f, [f.alias], outcome='blocked')
        assert rejected['state'] == 'rejected', rejected
    # A failure without an active collector may still report its limitation.
    assert submit(f, [f.alias], outcome='blocked')['state'] == 'completed'


def test_collection_completed_during_final_sync_is_reconciled(tmp_path, monkeypatch):
    f = experiment(tmp_path, monkeypatch, seconds=60)
    start(f)
    eid = execution(f).object_id
    f.adapter.state = 'succeeded'
    sync = f.coordinator.bridge.sync
    def finish_while_syncing(**kwargs):
        result = sync(**kwargs)
        f.coordinator.collection.collect(eid)
        return result
    monkeypatch.setattr(f.coordinator.bridge, 'sync', finish_while_syncing)
    assert submit(f, [f.alias], outcome='blocked')['state'] == 'completed'
    assert len([r for r in f.runs.tool_evidence(f.run_id)
        if r['metadata'].get('kind') == 'experiment_execution']) == 1
