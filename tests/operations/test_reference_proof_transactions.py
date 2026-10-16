"""Receipt transaction, historical proof repair, and error classification regressions."""
import json
import sqlite3

import pytest

from scidiscovery.operation_contract import DiagnosticError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from tests.operations.test_sealed_reference_replay import evidence_submission
from tests.operations.test_instance_archive import archive_system


def test_configured_new_record_limit_is_enforced_before_receipt_33(tmp_path):
    from scidiscovery.agent_execution_settings import AgentSettings
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis
    from scidiscovery.artifact_agent.service.reference_proofs import ReferenceProofError
    system = analysis_system(tmp_path)
    runs = system[1].runs
    runs.agent_settings = AgentSettings(attachments={'max_files': 32}, evidence_capacity={'max_new_records': 32})
    worker, _ = open_analysis(system)
    value = runs.status(worker._run_id)
    alias = value.inputs[0].source_name
    for number in range(32):
        runs.accept_tool_evidence(value.run_id, tool_name='bounded_derived_fixture',
            allowed_ports=('tool_evidence',), raw=canonical_json({'value': number}), media_type='application/json',
            metadata={'kind': 'analysis_derived'}, derived_from=(alias,))
    before = runs._evidence_snapshot(value.run_id)
    with pytest.raises(ReferenceProofError):
        runs.accept_tool_evidence(value.run_id, tool_name='bounded_derived_fixture',
            allowed_ports=('tool_evidence',), raw=canonical_json({'value': 32}), media_type='application/json',
            metadata={'kind': 'analysis_derived'}, derived_from=(alias,))
    assert runs._evidence_snapshot(value.run_id) == before
    budget = runs.worker_budget(value)['evidence_capacity']
    assert budget['records']['remaining'] == 0 and budget['attempts']['used'] == 0


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


def test_complete_proof_preserves_large_transitive_dependencies(tmp_path):
    from scidiscovery.artifact_agent.service.reference_proofs import material_snapshot
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
    records[0]['metadata']['historical_notes'] = 'x' * (1024 * 1024)
    complete = json.loads(material_snapshot(owner, records[-1], records, [], [], None))
    assert len(complete['bindings']) == 129
    assert complete['records'][0]['metadata']['historical_notes'] == records[0]['metadata']['historical_notes']


def test_recovered_calculation_retains_exact_attempt_and_sources(tmp_path, monkeypatch):
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
    assert runs.tool_evidence(owner.run_id) == []
    page = following.call_tool('worker_reference_read', {'history_task': 'generic_analysis', 'action': 'list'})
    selected = next(item for item in page['references'] if item.get('original_name') == result['calculation_ref'])
    read = following.call_tool('worker_reference_read', {'history_task': 'generic_analysis', 'action': 'read',
        'reference': selected['reference'], 'delivery': 'file'})
    access = runs.reference_access_records(owner.run_id)[0]
    proof = ArtifactRef.model_validate(access['proof_manifest_ref'])
    manifest = json.loads(runs.artifacts.read(proof))
    record = runs.tool_evidence(previous.run_id)[0]
    calculation = ControlledCalculationRecord.model_validate_json(canonical_json(record['metadata']['calculation_proof']))
    origin, attempt = _calculation_origin(manifest, calculation)
    assert runs.artifacts.catalog(proof).labels['tool_producer_run'] == previous.run_id
    assert runs.artifacts.catalog(proof).labels['operation_digest'] == previous.operation_digest
    assert len(origin.attempts) == 1 and attempt.state == 'completed'
    assert manifest['recovery'] is None and len(manifest['attempts']) == 1
    original_sources = {item.source_name: item.artifact_ref for item in previous.inputs}
    assert all(origin.bindings[name].artifact_ref == original_sources[name] for name in attempt.read_sources)
    assert all(binding.artifact_ref in runs.artifacts.catalog(proof).parent_refs for binding in origin.bindings.values())
    # Altering an original read-source binding cannot preserve calculation proof.
    from copy import deepcopy
    from scidiscovery.artifact_agent.service.reference_access import ReferenceAccessError
    wrong = deepcopy(manifest)
    wrong['bindings'][next(iter(calculation.input_digests))]['artifact_ref'] = record['artifact_ref']
    with pytest.raises(ReferenceAccessError):
        _calculation_origin(wrong, calculation)
    from tests.operations.test_analysis_claim_scope import submit
    from tests.operations.test_analysis_artifact_references import cite
    from tests.operations.test_result_analysis_tool import limited_report
    opened = following.call_tool('worker_open_assignment', {})
    from pathlib import Path
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload': cite(limited_report(), read['source'])}))
    reads = {ArtifactRef.model_validate(record['artifact_ref']): 0, proof: 0}
    original_read = runs.artifacts.read
    def counted_read(ref):
        if ref in reads:
            reads[ref] += 1
        return original_read(ref)
    with monkeypatch.context() as patch:
        patch.setattr(runs.artifacts, 'read', counted_read)
        runs._validated_candidate(runs.status(owner.run_id), final_submission=False)
    assert set(reads.values()) == {1}, reads
    result = submit(following, opened, cite(limited_report(), read['source']))
    assert result['state'] == 'completed', (result, runs.diagnostic_summary(runs.status(owner.run_id)))
    assert runs.tool_evidence(owner.run_id) == [] and len(runs.reference_access_records(owner.run_id)) == 1


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
    assert manifest['recovery'] is None
    assert len(manifest['records']) == 1 and len(runs.tool_evidence(previous.run_id)) == 128


def test_cache_budget_does_not_block_new_receipt(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import reference_proofs
    runs, owner, args = evidence_submission(tmp_path)
    original = runs.accept_tool_evidence(**args)
    monkeypatch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
    accepted = runs.accept_tool_evidence(**{**args, 'raw': b'new observation'})
    assert accepted['alias'] == 'tool_evidence_002'
    assert len(runs.tool_evidence(owner.run_id)) == 2
    assert runs.accept_tool_evidence(**args) == original


def test_final_submission_is_independent_of_cache_size(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import reference_proofs
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    from tests.operations.test_result_analysis_tool import limited_report
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    monkeypatch.setattr(reference_proofs, 'MAX_SNAPSHOT_BYTES', 1)
    result = submit(worker, opened, limited_report())
    assert result['state'] == 'completed', result
    sealed = system[1].runs.status(worker._run_id)
    assert sealed.state == 'completed' and sealed.output_ref is not None


def test_two_recoveries_keep_128_original_receipts_on_parent_nodes(tmp_path, monkeypatch):
    from pathlib import Path
    from scidiscovery.agent_execution_settings import AgentSettings
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    from tests.operations.test_result_analysis_tool import limited_report
    worker, _, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    runs.fail(worker._run_id, reason='close default fixture')
    runs.agent_settings = AgentSettings(attachments={'max_files': 128})
    request = dict(name='parent_one', operation_id='science.result.diagnose.v1', max_attempts=4,
        instruction='Retain bounded exact originals.', inputs=[
        dict(port='experiment_plan', artifact_names=['plan']),
        dict(port='experiment_results', artifact_names=['generic_results']),
        dict(port='curve_bundle', artifact_names=['generic_bundle'])])
    compiled = catalog.operation(request['operation_id'])
    def open_node(values):
        assert root.call_tool('operation_invoke', values)['result']['state'] == 'queued'
        router = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
        opened = router.call_tool('worker_open_assignment', {})
        return router, opened, Path(opened['assignment_path']).parent
    worker, _, workspace = open_node(request)
    alias = runs.status(worker._run_id).inputs[0].source_name
    files = []
    for number in range(128):
        path = f'scratch/old_{number:03d}.csv'
        (workspace/path).write_bytes(b'x\n1\n')
        files.append(dict(path=path, purpose='Exact parent original'))
    for start in (0, 64):
        worker.call_tool('worker_publish_files', dict(files=files[start:start+64], source_aliases=[alias]))
    origin = runs.status(worker._run_id)
    assert len(runs.tool_evidence(origin.run_id)) == 128
    runs.fail(origin.run_id, reason='retain full original node')
    first, _, workspace = open_node({**request, 'name': 'parent_two', 'draft_from': 'parent_one'})
    assert runs.tool_evidence(first._run_id) == []
    (workspace/'scratch/new.csv').write_bytes(b'x\n2\n')
    first.call_tool('worker_publish_files', dict(files=[dict(path='scratch/new.csv', purpose='New node original')], source_aliases=[alias]))
    runs.fail(first._run_id, reason='retain one new node original')
    second, opened, _ = open_node({**request, 'name': 'child', 'draft_from': 'parent_two'})
    assert runs.tool_evidence(second._run_id) == [] and runs.reference_access_records(second._run_id) == []
    # A legacy standalone assignment can have no frozen memory snapshot.
    with runs._connect() as db:
        db.execute('UPDATE runs SET memory_scope_json=NULL WHERE run_id=?', (second._run_id,))
    assert not runs._worker_memory_binding(second._run_id)['available']
    # Directory pages never touch payload bytes or construct a whole parent proof.
    with monkeypatch.context() as patch:
        patch.setattr(runs.artifacts, 'verify', lambda *a, **k: pytest.fail('navigation hashed payload'))
        patch.setattr(runs, 'reference_manifest', lambda *a, **k: pytest.fail('navigation built parent proof'))
        page = second.call_tool('worker_reference_read', dict(history_task='parent_one', action='list'))
    assert page['next_cursor'] is not None and page['omitted'] > 0
    item = next(i for i in page['references'] if i.get('original_name') == 'attachment_001')
    read = second.call_tool('worker_reference_read', dict(history_task='parent_one', action='read', reference=item['reference'], delivery='file'))
    assert Path(read['file_path']).read_bytes() == b'x\n1\n'
    page = second.call_tool('worker_reference_read', dict(history_task='parent_two', action='list'))
    item = next(i for i in page['references'] if i.get('original_name') == 'attachment_001')
    read = second.call_tool('worker_reference_read', dict(history_task='parent_two', action='read', reference=item['reference'], delivery='file'))
    assert Path(read['file_path']).read_bytes() == b'x\n2\n'
    assert runs.tool_evidence(second._run_id) == []
    assert len(runs.reference_access_records(second._run_id)) == 2
    snapshot = json.loads(runs._evidence_snapshot(second._run_id))
    assert snapshot['records'] == [] and snapshot['recovery'] is None and 'references' not in snapshot
    assert len(runs.tool_evidence(origin.run_id)) == 128 and len(runs.tool_evidence(first._run_id)) == 1
    assert submit(second, opened, limited_report())['state'] == 'completed'


def test_previous_reader_contract_recovers_without_rewriting_original_digest(tmp_path, monkeypatch):
    from scidiscovery.reference_tools import ReferenceReadRequest, LEGACY_REFERENCE_HISTORY_DESCRIPTION
    from tests.operations.test_agent_contract_alignment import _catalog
    from tests.operations.test_analysis_claim_scope import generic_worker
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from pathlib import Path
    # Independently compile the real pre-change public field description.
    with monkeypatch.context() as patch:
        patch.setattr(ReferenceReadRequest.model_fields['history_task'], 'description', LEGACY_REFERENCE_HISTORY_DESCRIPTION)
        ReferenceReadRequest.model_rebuild(force=True)
        legacy = _catalog()
    ReferenceReadRequest.model_rebuild(force=True)
    current = _catalog()
    identity = 'science.result.diagnose.v1'
    old, new = legacy.operation(identity), current.operation(identity)
    assert old.digest != new.digest
    assert current.recorded_operation(identity, version=old.spec.version, digest=old.digest).digest == old.digest
    assert current.can_recover(identity, old.digest, new.digest)
    worker, _, system = generic_worker(tmp_path, return_system=True)
    _, runtime, root, *_ = system
    runs = runtime.runs
    runs.fail(worker._run_id, reason='close current setup fixture')
    runs.operation_catalog = root.facade._operation_catalog = legacy
    request = dict(name='old_reader', operation_id=identity, instruction='Retain one exact old-contract original.', inputs=[
        dict(port='experiment_plan', artifact_names=['plan']),
        dict(port='experiment_results', artifact_names=['generic_results']),
        dict(port='curve_bundle', artifact_names=['generic_bundle'])])
    root.call_tool('operation_invoke', request)
    worker = LocalWorkerMCPRouter(runs, operation_id=identity, operation_digest=old.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/old.csv').write_bytes(b'x\n1\n')
    alias = runs.status(worker._run_id).inputs[0].source_name
    worker.call_tool('worker_publish_files', dict(files=[dict(path='scratch/old.csv', purpose='Original')], source_aliases=[alias]))
    previous = runs.fail(worker._run_id, reason='seal supported old reader')
    # The real frozen legacy reader retains only its old memory surface.
    root.call_tool('operation_invoke', {**request, 'name': 'legacy_frozen_reader', 'resume_from': 'old_reader', 'max_attempts': 3})
    frozen_reader = LocalWorkerMCPRouter(runs, operation_id=identity, operation_digest=old.digest)
    frozen_reader.call_tool('worker_open_assignment', {})
    old_page = frozen_reader.call_tool('worker_reference_read', dict(history_task='old_reader', action='list'))
    assert old_page['references']
    assert all(item.get('original_name') != 'attachment_001' for item in old_page['references'])
    runs.fail(frozen_reader._run_id, reason='close frozen legacy reader')
    runs.operation_catalog = root.facade._operation_catalog = current
    assert runs._compiled(runs.status(previous.run_id)).digest == old.digest
    assert root.call_tool('operation_invoke', {**request, 'name': 'new_reader', 'resume_from': 'old_reader', 'max_attempts': 3})['result']['state'] == 'queued'
    following = LocalWorkerMCPRouter(runs, operation_id=identity, operation_digest=new.digest)
    following.call_tool('worker_open_assignment', {})
    assert runs.status(previous.run_id).operation_digest == old.digest
    assert runs.status(following._run_id).operation_digest == new.digest
    assert runs.tool_evidence(following._run_id) == []
    page = following.call_tool('worker_reference_read', dict(history_task='old_reader', action='list'))
    selected = next(item for item in page['references'] if item.get('original_name') == 'attachment_001')
    read = following.call_tool('worker_reference_read', dict(history_task='old_reader', action='read', reference=selected['reference'], delivery='file'))
    assert Path(read['file_path']).read_bytes() == b'x\n1\n'
    assert 'references' not in json.loads(runs._evidence_snapshot(following._run_id))


def _file_parent_reader(tmp_path, *, content=b'x\n1\n'):
    from pathlib import Path
    from tests.operations.test_analysis_claim_scope import generic_worker
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/original.csv').write_bytes(content)
    alias = runs.status(worker._run_id).inputs[0].source_name
    worker.call_tool('worker_publish_files', dict(files=[dict(path='scratch/original.csv', purpose='Original')], source_aliases=[alias]))
    parent = runs.status(worker._run_id)
    target = ArtifactRef.model_validate(runs.tool_evidence(parent.run_id)[0]['artifact_ref'])
    runs.fail(parent.run_id, reason='read exact parent original')
    root.call_tool('operation_invoke', dict(name='reader_child', draft_from='generic_analysis', max_attempts=2,
        operation_id='science.result.diagnose.v1', instruction='Read only selected parent original.', inputs=[
        dict(port='experiment_plan', artifact_names=['plan']), dict(port='experiment_results', artifact_names=['generic_results']),
        dict(port='curve_bundle', artifact_names=['generic_bundle'])]))
    compiled = catalog.operation('science.result.diagnose.v1')
    child = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    child.call_tool('worker_open_assignment', {})
    page = child.call_tool('worker_reference_read', dict(history_task='generic_analysis', action='list'))
    selected = next(item for item in page['references'] if item.get('original_name') == 'attachment_001')
    return runs, child, target, selected


@pytest.mark.parametrize('fault', ['file_limit', 'io_budget'])
def test_parent_payload_is_not_read_or_verified_before_io_admission(tmp_path, monkeypatch, fault):
    runs, child, target, selected = _file_parent_reader(tmp_path)
    value = runs.status(child._run_id)
    policy = runs._reference_policy(value)
    with runs._connect() as db:
        if fault == 'file_limit':
            frozen = dict(value.recovery_policy)
            frozen['input_materials'] = {**frozen['input_materials'], 'max_item_bytes': 1}
            db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (canonical_json(frozen), value.run_id))
        else:
            runs._reference_event(db, value.run_id, 'reference_io_reserved', {
                'budget_scope': runs._reference_scope(db, value.run_id), 'reservation_id': 'previous-spent',
                'bytes': frozen_total(value) + policy.max_io_bytes})
    proof = runs.reference_manifest(runs.status(selected['_manifest_run']) if '_manifest_run' in selected else
        runs.status(runs.artifacts.catalog(target).labels['tool_producer_run']), subject_ref=target)
    read, verify = runs.artifacts.read, runs.artifacts.verify
    def forbidden_read(ref, *args, **kwargs):
        assert ref not in {target, proof}, 'Rejected target/proof was read before IO admission'
        return read(ref, *args, **kwargs)
    def forbidden_verify(ref, *args, **kwargs):
        assert ref not in {target, proof}, 'Rejected target/proof was hashed before IO admission'
        return verify(ref, *args, **kwargs)
    monkeypatch.setattr(runs.artifacts, 'read', forbidden_read)
    monkeypatch.setattr(runs.artifacts, 'verify', forbidden_verify)
    with pytest.raises(DiagnosticError) as caught:
        child.call_tool('worker_reference_read', dict(history_task='generic_analysis', action='read', reference=selected['reference'], delivery='file'))
    assert any(item['code'] == ('reference_file_limit' if fault == 'file_limit' else 'reference_io_limit') for item in caught.value.details)
    assert runs.reference_access_records(value.run_id) == []


def frozen_total(value):
    from scidiscovery.agent_execution_settings import MaterialInputSettings
    return MaterialInputSettings.model_validate(value.recovery_policy['input_materials']).max_total_bytes


def test_parent_reader_does_not_expose_hidden_ancillary_port(tmp_path):
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
    from curve_score.plugin import PLUGIN as CURVE_PLUGIN
    from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
    from tests.operations.test_analysis_claim_scope import generic_worker
    from tests.operations.test_result_analysis_tool import score_inputs
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    worker, _, system = generic_worker(tmp_path, return_system=True)
    _, runtime, root, *_ = system
    runs = runtime.runs
    runs.fail(worker._run_id, reason='close default setup')
    identity = 'science.result.diagnose.v1'
    changed = CURVE_PLUGIN.model_copy(update={'operations': tuple(
        op.model_copy(update={'outputs': tuple(port.model_copy(update={'agent_visible': False})
            if port.name == 'tool_evidence' else port for port in op.outputs)})
        if op.operation_id == identity else op for op in CURVE_PLUGIN.operations)})
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, changed, TCAD_PLUGIN))
    compiled = catalog.operation(identity)
    port = next(port for port in compiled.spec.outputs if port.name == 'tool_evidence')
    assert not port.agent_visible and port.kind != 'scientific_attachment'
    runs.operation_catalog = root.facade._operation_catalog = catalog
    request = dict(name='private_parent', operation_id=identity, instruction='Retain a private ancillary calculation.', inputs=[
        dict(port='experiment_plan', artifact_names=['plan']), dict(port='experiment_results', artifact_names=['generic_results']),
        dict(port='curve_bundle', artifact_names=['generic_bundle'])])
    root.call_tool('operation_invoke', request)
    worker = LocalWorkerMCPRouter(runs, operation_id=identity, operation_digest=compiled.digest)
    worker.call_tool('worker_open_assignment', {})
    result = worker.call_tool('worker_curve_score', {'record_key': 'private', 'request': score_inputs()[1]})
    assert result['status'] == 'computed'
    runs.fail(worker._run_id, reason='seal hidden ancillary')
    root.call_tool('operation_invoke', {**request, 'name': 'private_child', 'draft_from': 'private_parent', 'max_attempts': 2})
    child = LocalWorkerMCPRouter(runs, operation_id=identity, operation_digest=compiled.digest)
    child.call_tool('worker_open_assignment', {})
    page = child.call_tool('worker_reference_read', dict(history_task='private_parent', action='list'))
    assert all(item.get('original_name') != result['calculation_ref'] for item in page['references'])
    with pytest.raises(DiagnosticError):
        child.call_tool('worker_reference_read', dict(history_task='private_parent', action='read', reference='ref_' + '0'*64))
    assert runs.reference_access_records(child._run_id) == []


def test_unselected_large_file_access_is_not_loaded_by_scientific_validation(tmp_path, monkeypatch):
    from tests.operations.test_analysis_claim_scope import submit
    from tests.operations.test_result_analysis_tool import limited_report
    runs, child, target, selected = _file_parent_reader(tmp_path, content=b'x,y\n' + b'1,2\n' * 1_000_000)
    child.call_tool('worker_reference_read', {'history_task': 'generic_analysis', 'action': 'read',
        'reference': selected['reference'], 'delivery': 'file'})
    original_read, original_verify = runs.artifacts.read, runs.artifacts.verify
    def guarded_read(ref):
        assert ref != target, 'Unselected file access was loaded by scientific validation'
        return original_read(ref)
    def guarded_verify(ref):
        assert ref != target, 'Unselected file access was hashed by scientific validation'
        return original_verify(ref)
    monkeypatch.setattr(runs.artifacts, 'read', guarded_read)
    monkeypatch.setattr(runs.artifacts, 'verify', guarded_verify)
    opened = child.call_tool('worker_open_assignment', {})
    assert submit(child, opened, limited_report())['state'] == 'completed'
    assert runs.tool_evidence(child._run_id) == [] and len(runs.reference_access_records(child._run_id)) == 1
