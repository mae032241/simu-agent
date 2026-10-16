"""Controlled task paths and opaque originals through actual capture, without models."""
import hashlib
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_artifact_capture import experiment, records


def seal(worker, name):
    return worker.call_tool('worker_experiment_stage', dict(stage='design', conclusion='Retain the exact fixture.',
        materials=['file:scratch/artifacts/' + name, 'objective_source']))


def test_verified_task_path_keeps_original_and_has_distinct_safe_reading_copy(tmp_path):
    runtime, instance, root, worker, _, workspace = experiment(tmp_path)
    code = workspace / 'scratch/artifacts/derive.py'
    code.write_bytes(b'print(1)\n')
    raw = ('Traceback:\n  File "' + str(code) + '", line 1\nRuntimeError: controlled fixture\n').encode()
    (workspace / 'scratch/artifacts/run.log').write_bytes(raw)
    seal(worker, 'run.log')
    original = next(r for r in records(runtime, worker) if r['metadata'].get('locator') == 'scratch/artifacts/run.log')
    ref = ArtifactRef.model_validate(original['artifact_ref'])
    assert ref.sha256 == hashlib.sha256(raw).hexdigest() and runtime.artifacts.read(ref) == raw
    view = next(r for r in records(runtime, worker) if r['metadata'].get('kind') == 'capture_reading_view')
    visible = runtime.artifacts.read(ArtifactRef.model_validate(view['artifact_ref']))
    assert str(workspace).encode() not in visible and b'file:scratch/artifacts/derive.py' in visible
    assert view['metadata']['view_of'] == original['artifact_ref']
    directory = worker.call_tool('worker_reference_read', {'source': original['alias'], 'action': 'list'})
    entry = next(e for e in directory['references'] if e['reference'] == 'reading_copy')
    assert entry['alias'] == view['alias'] and entry['representation'] == 'reading_view'
    read = worker.call_tool('worker_reference_read', {'source': original['alias'], 'action': 'read', 'reference': 'reading_copy'})
    assert read['source'] == view['alias'] and read['fragment'].encode() == visible
    with pytest.raises(DiagnosticError) as rejected:
        worker.call_tool('worker_reference_read', {'source': original['alias'], 'action': 'read', 'reference': 'content'})
    assert rejected.value.details[0]['code'] == 'reference_reading_view_required'
    delivered = worker.call_tool('worker_reference_read', {'source': original['alias'], 'action': 'read', 'reference': 'content', 'delivery': 'file'})
    assert Path(delivered['file_path']).read_bytes() == raw
    with pytest.raises(DiagnosticError) as forbidden:
        worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'This view is not scientific evidence.', 'materials': [view['alias']]})
    assert forbidden.value.details[0]['code'] == 'capture_source_unconfirmed'
    from scidiscovery.artifact_agent.service.scientific_usage import scientific_use_restricted
    view_ref = ArtifactRef.model_validate(view['artifact_ref'])
    assert scientific_use_restricted(runtime.runs, (view_ref,))
    runtime.runs.fail(worker._run_id, reason='end capture before exact view admission check')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='reading-copy', object_id=view_ref.artifact_id)
    admission = root.call_tool('operation_preflight', {'name': 'view-consumer', 'operation_id': 'science.experiment.v1',
        'instruction': 'Check exact view admission.', 'inputs': [
            {'port': 'subject', 'artifact_names': ['objective.hypothesis.output']},
            {'port': 'scientific_materials', 'artifact_names': ['reading-copy']}]})
    assert admission['admissible'], 'Inventory reading does not authorize a scientific claim'
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import CompiledCatalog, compile_catalog
    # Reuse the existing typed claim consumer, not the wildcard material port
    # (material exposure is restricted to evidence_inventory by the compiler).
    from scidiscovery.general_science_agent_operations import _input
    existing = runtime.runs.operation_catalog
    operation = existing.operation('science.fixture.consume_experiment.v1').spec
    source = _input('source_material', 'Exact bounded original for scientific claim.', 'opaque',
        media_types=('text/plain',), exposure='on_demand', usage='claim_evidence')
    claim = operation.model_copy(update={'operation_id': 'science.fixture.view_claim.v1',
        'inputs': tuple(source if p.name == 'source_material' else p for p in operation.inputs)})
    catalog = compile_catalog((CORE_PLUGIN, PLUGIN.model_copy(update={'operations': (*PLUGIN.operations, claim)})))
    catalog = CompiledCatalog({**existing._operations, claim.operation_id: catalog.operation(claim.operation_id)},
        existing._runtime_factories, existing._runtime_configuration_digests, existing._runtime_identity_digests,
        existing._historical_operations)
    runtime.runs.operation_catalog = catalog
    root.facade._operation_catalog = catalog
    root._operation_catalog = catalog
    admission = root.call_tool('operation_preflight', {'name': 'claim-consumer', 'operation_id': claim.operation_id,
        'instruction': 'Check exact scientific-claim admission.', 'inputs': [
            {'port': 'source_material', 'artifact_names': ['reading-copy']}]})
    assert not admission['admissible'] and admission['reason_code'] == 'input_scientific_claim_forbidden'


@pytest.mark.parametrize('suffix', ['pkl', 'npz'])
def test_opaque_model_is_automatically_sealed_byte_identical_without_loading(tmp_path, suffix, monkeypatch):
    import pickle
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    raw = b'\x80\x05bounded opaque fixture\x00' if suffix == 'pkl' else b'PK\x03\x04bounded opaque fixture\x00'
    (workspace / ('scratch/artifacts/model.' + suffix)).write_bytes(raw)
    def forbidden(*args, **kwargs):
        raise AssertionError('Capture must not deserialize pickle')
    monkeypatch.setattr(pickle, 'load', forbidden)
    monkeypatch.setattr(pickle, 'loads', forbidden)
    seal(worker, 'model.' + suffix)
    original = next(r for r in records(runtime, worker) if r['metadata'].get('locator') == 'scratch/artifacts/model.' + suffix)
    ref = ArtifactRef.model_validate(original['artifact_ref'])
    assert ref.sha256 == hashlib.sha256(raw).hexdigest() and runtime.artifacts.read(ref) == raw
    assert not any(r['metadata'].get('kind') == 'capture_reading_view' for r in records(runtime, worker))


@pytest.mark.parametrize('private', [b'password=123456789012\n', b'-----BEGIN ' + b'PRIVATE KEY-----\nfixture\n'])
def test_real_secret_is_rejected_even_beside_a_valid_task_path(tmp_path, private):
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    code = workspace / 'scratch/artifacts/derive.py'
    code.write_bytes(b'print(1)\n')
    (workspace / 'scratch/artifacts/run.log').write_bytes(str(code).encode() + b'\n' + private)
    with pytest.raises(DiagnosticError) as rejected:
        seal(worker, 'run.log')
    assert rejected.value.details[0]['code'] == 'capture_reference_incomplete'
    inventory = next(r for r in records(runtime, worker) if r['metadata'].get('kind') == 'capture_inventory')
    entry = next(e for e in inventory['metadata']['capture_map']['entries'] if e.get('path') == 'scratch/artifacts/run.log')
    assert entry['status'] == 'incomplete' and entry['reason'] == 'capture_private_content'
    assert not any(r['metadata'].get('locator') == 'scratch/artifacts/run.log' for r in records(runtime, worker))


@pytest.mark.parametrize('fault', ['unknown', 'foreign', 'symlink', 'hidden', 'parent', 'sibling'])
def test_unverified_machine_path_is_a_capture_gap(tmp_path, fault):
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    task = workspace / 'scratch/artifacts'
    code = task / 'derive.py'
    code.write_bytes(b'print(1)\n')
    paths = {'unknown': '/home/' + 'unknown/not-authorized.py', 'foreign': str(tmp_path / 'other-run.py'),
        'hidden': str(workspace / 'assignment.json'), 'parent': str(task / '../artifacts/derive.py'),
        'sibling': str(workspace) + '-other/scratch/artifacts/derive.py'}
    if fault == 'symlink':
        link = task / 'link.py'
        link.symlink_to(code)
        paths[fault] = str(link)
    (task / 'run.log').write_bytes(('File "' + paths[fault] + '"\n').encode())
    with pytest.raises(DiagnosticError) as rejected:
        seal(worker, 'run.log')
    assert rejected.value.details[0]['code'] == 'capture_reference_incomplete'
    receipts = records(runtime, worker)
    inventory = next(r for r in receipts if r['metadata'].get('kind') == 'capture_inventory')
    entry = next(e for e in inventory['metadata']['capture_map']['entries'] if e.get('path') == 'scratch/artifacts/run.log')
    assert entry['reason'] == 'capture_private_content'
    assert not any(r['metadata'].get('locator') == 'scratch/artifacts/run.log' or
        r['metadata'].get('kind') == 'capture_reading_view' for r in receipts)


def test_original_and_view_do_not_commit_when_index_exceeds_final_slot(tmp_path):
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    from scidiscovery.artifact_agent.schema.common import canonical_json
    run = runtime.runs.status(worker._run_id)
    policy = dict(run.recovery_policy)
    policy['attachments']['max_files'] = 2
    with runtime.runs._connect() as connection:
        connection.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (canonical_json(policy), worker._run_id))
    target = workspace / 'scratch/artifacts/run.log'
    target.write_bytes(('File "' + str(target) + '"\n').encode())
    with pytest.raises(DiagnosticError) as rejected:
        seal(worker, 'run.log')
    assert rejected.value.details[0]['code'] == 'attachment_publication_invalid'
    assert not records(runtime, worker)
    run = runtime.runs.status(worker._run_id)
    assert run.accepted_candidate_digest is None and run.output_ref is None


def test_original_and_view_receipts_roll_back_together_and_retry_reuses_cas(tmp_path, monkeypatch):
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    target = workspace / 'scratch/artifacts/run.log'
    raw = ('File "' + str(target) + '"\n').encode()
    target.write_bytes(raw)
    registered, register = [], runtime.artifacts.register_file
    def remember(*args, **kwargs):
        result = register(*args, **kwargs)
        registered.append(result.ref)
        return result
    monkeypatch.setattr(runtime.artifacts, 'register_file', remember)
    with monkeypatch.context() as patch:
        patch.setattr(runtime.runs, '_encode_evidence_snapshot', lambda *args: (_ for _ in ()).throw(ConnectionError('fixture rollback')))
        with pytest.raises(DiagnosticError):
            seal(worker, 'run.log')
    assert len(registered) == 3 and not records(runtime, worker)
    before = registered[:]
    seal(worker, 'run.log')
    assert registered[3:] == before
    receipts = records(runtime, worker)
    original = next(r for r in receipts if r['metadata'].get('locator') == 'scratch/artifacts/run.log')
    view = next(r for r in receipts if r['metadata'].get('kind') == 'capture_reading_view')
    assert view['metadata']['view_of'] == original['artifact_ref']
    assert runtime.artifacts.read(ArtifactRef.model_validate(original['artifact_ref'])) == raw


def test_conflicting_control_view_receipt_cannot_authorize_a_reading_copy(tmp_path):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    target = workspace / 'scratch/artifacts/run.log'
    target.write_bytes(('File "' + str(target) + '"\n').encode())
    seal(worker, 'run.log')
    original = next(r for r in records(runtime, worker) if r['metadata'].get('locator') == 'scratch/artifacts/run.log')
    view = next(r for r in records(runtime, worker) if r['metadata'].get('kind') == 'capture_reading_view')
    view['metadata']['scientific_claim_admissible'] = True
    with runtime.runs._connect() as connection:
        connection.execute('UPDATE run_tool_evidence SET record_json=? WHERE run_id=? AND alias=?',
            (canonical_json(view), worker._run_id, view['alias']))
    with pytest.raises(DiagnosticError) as rejected:
        worker.call_tool('worker_reference_read', {'source': original['alias'], 'action': 'list'})
    assert rejected.value.details[0]['code'] == 'reference_view_unconfirmed'


@pytest.mark.parametrize('route', ['failed_parent', 'direct_original'])
def test_authorized_original_reaches_same_producer_reading_copy_without_inheritance(tmp_path, route):
    from tests.operations.worker_fixtures import attached_worker
    runtime, instance, root, worker, _, workspace = experiment(tmp_path)
    target = workspace / 'scratch/artifacts/run.log'
    raw = ('File "' + str(target) + '"\n').encode()
    target.write_bytes(raw)
    seal(worker, 'run.log')
    receipts = records(runtime, worker)
    original = next(r for r in receipts if r['metadata'].get('locator') == 'scratch/artifacts/run.log')
    view = next(r for r in receipts if r['metadata'].get('kind') == 'capture_reading_view')
    original_ref = ArtifactRef.model_validate(original['artifact_ref'])
    request = {'name': 'reader', 'operation_id': 'science.experiment.v1', 'max_attempts': 2,
        'instruction': 'Read the exact bounded original and its navigation copy.',
        'inputs': [{'port': 'subject', 'artifact_names': ['objective.hypothesis.output']}]}
    runtime.runs.fail(worker._run_id, reason='fixture interruption after immutable capture')
    if route == 'failed_parent':
        request['draft_from'] = 'capture'
    else:
        # Failed producer has no final report: bind O only, never V/history.
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='exact-original', object_id=original_ref.artifact_id)
        request['inputs'].append({'port': 'scientific_materials', 'artifact_names': ['exact-original']})
    root.call_tool('operation_invoke', request)
    child = attached_worker(runtime, root, 'reader')
    child.call_tool('worker_open_assignment', {})
    assert not records(runtime, child)
    if route == 'failed_parent':
        directory = child.call_tool('worker_reference_read', {'history_task': 'capture', 'action': 'list'})
        entry = next(e for e in directory['references'] if e.get('original_name') == original['alias'])
        delivered = child.call_tool('worker_reference_read', {'history_task': 'capture', 'action': 'read',
            'reference': entry['reference'], 'delivery': 'file'})
        assert Path(delivered['file_path']).read_bytes() == raw
        alias = delivered['source']
    else:
        alias = next(i.source_name for i in runtime.runs.status(child._run_id).inputs if i.artifact_ref == original_ref)
    directory = child.call_tool('worker_reference_read', {'source': alias, 'action': 'list'})
    copy = next(e for e in directory['references'] if e['reference'] == 'reading_copy')
    assert copy['representation'] == 'reading_view'
    read = child.call_tool('worker_reference_read', {'source': alias, 'action': 'read', 'reference': copy['reference']})
    assert read['fragment'].encode() == runtime.artifacts.read(ArtifactRef.model_validate(view['artifact_ref']))
    assert str(workspace) not in read['fragment']
    followup = child.call_tool('worker_reference_read', {'source': read['source'], 'action': 'list'})
    content = next(e for e in followup['references'] if e['reference'] == 'content')
    replay = child.call_tool('worker_reference_read', {'source': read['source'], 'action': 'read', 'reference': content['reference']})
    assert replay['fragment'] == read['fragment']
    assert not records(runtime, child), 'Reading must not inherit parent receipts/indexes'
    access = runtime.runs.reference_access_records(child._run_id)
    assert any(r['artifact_ref'] == view['artifact_ref'] for r in access)
    assert runtime.artifacts.read(original_ref) == raw


@pytest.mark.parametrize('scope', ['restricted_subject', 'optional_restricted'])
def test_reading_copy_does_not_clean_restricted_task_scope(tmp_path, scope):
    from tests.operations.test_capture_scope_restrictions import copy_task
    runtime, _, _, worker, opened, _, _, goal, _, _ = copy_task(tmp_path,
        restricted=scope == 'restricted_subject', extra_restricted=scope == 'optional_restricted')
    workspace = Path(opened['assignment_path']).parent
    target = workspace / 'scratch/artifacts/run.log'
    target.write_bytes(('File "' + str(target) + '"\n').encode())
    worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Retain navigation without scientific adoption.',
        'materials': ['file:run.log'], 'capture_sources': [{'source_aliases': [goal]}]})
    original = next(r for r in records(runtime, worker) if r['metadata'].get('locator') == 'scratch/artifacts/run.log')
    view = next(r for r in records(runtime, worker) if r['metadata'].get('kind') == 'capture_reading_view')
    assert original['metadata']['scientific_claim_admissible'] is False
    assert view['metadata']['scientific_claim_admissible'] is False
    for receipt in (original, view):
        assert runtime.artifacts.catalog(ArtifactRef.model_validate(receipt['artifact_ref'])).labels['scientific_claim_admissible'] == 'false'
    read = worker.call_tool('worker_reference_read', {'source': original['alias'], 'action': 'read', 'reference': 'reading_copy'})
    assert str(workspace) not in read['fragment']
    with pytest.raises(DiagnosticError) as rejected:
        worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'A view cannot be an adopted scientific source.', 'materials': [view['alias']]})
    assert rejected.value.details[0]['code'] == 'capture_source_unconfirmed'
