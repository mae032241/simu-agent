"""Real Root/Worker publication, finalization, downstream and UI file delivery."""
import json
from pathlib import Path

import pytest

from scidiscovery.operation_contract import DiagnosticError
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.presentation_render import render_presentation
from tests.operations.test_evidence_source_capture import open_extraction
from tests.operations.worker_fixtures import attached_worker
from tests.operations.test_general_transform_operations import _intake
from tests.operations.test_instance_content_display import picture
from tests.operations.test_r4_stage_delivery import _model


def publish_fixture(tmp_path):
    catalog, runtime, root, worker, opened, request = open_extraction(tmp_path)
    workspace = Path(opened['assignment_path']).parent
    sources = json.loads(Path(opened['assignment_path']).read_bytes())['inputs']
    alias = sources[0]['source_name']
    files = {'rows.csv': b'x,y\n1,2\n3,4\n', 'contract.json': b'{"threshold":0.25}',
             'overlay.png': picture('blue'), 'derive.py': b'print("scientific method")\n'}
    for name, data in files.items():
        (workspace/'scratch'/name).write_bytes(data)
    args = {'source_aliases':[alias], 'files':[{'path':'scratch/'+name, 'purpose':'Scientific fixture '+name} for name in files]}
    return catalog, runtime, root, worker, opened, request, workspace, alias, files, args


def finish(worker, opened, alias):
    payload = _intake().model_dump(mode='json')
    payload['scientific_foundation']['evidence'][0]['source_key'] = alias
    payload['scientific_foundation']['items'][0]['evidence_keys'] = [alias]
    Path(opened['output_directory'],'result.json').write_text(json.dumps({
        'handoff':{'verdict':'pass','summary':'Bounded attachment fixture.'},'payload':payload}))
    return worker.call_tool('worker_submit_result', {})


def configured_publication(tmp_path, settings):
    from scidiscovery.agent_execution_settings import AgentSettings
    catalog, runtime, root, worker, _, request = open_extraction(tmp_path)
    runtime.runs.fail(worker._run_id, reason='close default fixture before configured admission')
    runtime.runs.agent_settings = AgentSettings.model_validate(settings)
    request = {**request, 'name': 'configured'}
    root.call_tool('operation_invoke', request)
    worker = attached_worker(runtime, root, request['name'])
    opened = worker.call_tool('worker_open_assignment', {})
    alias = runtime.runs.status(worker._run_id).inputs[0].source_name
    return catalog, runtime, root, worker, opened, request, Path(opened['assignment_path']).parent, alias


def test_concurrent_last_new_receipt_slot_has_one_commit_and_accurate_budget(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from scidiscovery.attachment_tools import PublishFiles
    _, runtime, _, worker, _, _, workspace, alias = configured_publication(tmp_path,
        {'attachments': {'max_files': 1}, 'evidence_capacity': {'max_new_records': 1}})
    gate = Barrier(2)
    original = runtime.artifacts.register_file
    def register(*args, **kwargs):
        value = original(*args, **kwargs)
        gate.wait(timeout=10)
        return value
    monkeypatch.setattr(runtime.artifacts, 'register_file', register)
    def publish(number):
        path = f'scratch/concurrent_{number}.csv'
        (workspace/path).write_bytes(b'x\n1\n')
        request = PublishFiles.model_validate_json(json.dumps(dict(files=[dict(path=path, purpose='Concurrent file')], source_aliases=[alias])))
        try:
            return runtime.runs.publish_attachments(worker._run_id, request, workspace=workspace)
        except DiagnosticError as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(publish, range(2)))
    assert sum(isinstance(value, DiagnosticError) for value in values) == 1
    assert len(runtime.runs.tool_evidence(worker._run_id)) == 1
    budget = runtime.runs.worker_budget(runtime.runs.status(worker._run_id))['evidence_capacity']
    assert budget['attachments']['remaining'] == budget['records']['remaining'] == 0


def test_recovery_reads_old_bytes_without_copying_them_into_new_storage(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    catalog, runtime, root, worker, _, request, workspace, alias = configured_publication(tmp_path,
        {'attachments': {'max_item_bytes': 10, 'max_total_bytes': 10}})
    old = []
    for number, raw in enumerate([b'x\n123\n', b'x\n1\n']):
        path = f'scratch/old_{number}.csv'
        (workspace/path).write_bytes(raw)
        old.append(dict(path=path, purpose='Exact prior bytes'))
    worker.call_tool('worker_publish_files', dict(files=old, source_aliases=[alias]))
    assert runtime.runs.worker_budget(runtime.runs.status(worker._run_id))['evidence_capacity']['attachments']['remaining_bytes'] == 0
    runtime.runs.fail(worker._run_id, reason='seal full original bytes')
    root.call_tool('operation_invoke', {**request, 'name': 'new_bytes', 'draft_from': request['name'], 'max_attempts': 2})
    compiled = catalog.operation(request['operation_id'])
    following = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = following.call_tool('worker_open_assignment', {})
    page = following.call_tool('worker_reference_read', {'history_task': request['name'], 'action': 'list'})
    for item in page['references']:
        if item.get('original_name', '').startswith('attachment_'):
            following.call_tool('worker_reference_read', {'history_task': request['name'], 'action': 'read',
                'reference': item['reference'], 'delivery': 'file'})
    assert runtime.runs.tool_evidence(following._run_id) == []
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/new.csv').write_bytes(b'x\n2\n')
    new = dict(files=[dict(path='scratch/new.csv', purpose='New bytes')], source_aliases=[alias])
    assert following.call_tool('worker_publish_files', new) == following.call_tool('worker_publish_files', new)
    budget = runtime.runs.worker_budget(runtime.runs.status(following._run_id))['evidence_capacity']['attachments']
    assert budget['used_bytes'] == 4 and budget['remaining_bytes'] == 6
    assert len(runtime.runs.reference_access_records(following._run_id)) == 2


def test_generated_files_publish_submit_and_reach_downstream_and_ui(tmp_path, monkeypatch):
    catalog, runtime, root, worker, opened, request, workspace, alias, files, args = publish_fixture(tmp_path)
    saved = worker.call_tool('worker_publish_files', args)
    assert saved == worker.call_tool('worker_publish_files', args)
    assert len(saved['files']) == 4
    assert not any(k in json.dumps(saved) for k in ('artifact_ref','sha256','output_port','run_id'))
    records = runtime.runs.tool_evidence(worker._run_id)
    refs = {ArtifactRef.model_validate(r['artifact_ref']) for r in records}
    # Validation/finalization must never load attachment contents into RAM.
    read = runtime.artifacts.read
    def bounded_read(ref):
        assert ref not in refs, 'Attachment was bulk-read during finalization'
        return read(ref)
    monkeypatch.setattr(runtime.artifacts, 'read', bounded_read)
    assert finish(worker, opened, saved['files'][0]['reference'])['state'] == 'completed'
    monkeypatch.setattr(runtime.artifacts, 'read', read)
    status = root.call_tool('run_status', {'name':'evidence', 'intent':'navigation'})
    names = [item['artifact_name'] for item in status['evidence_outputs']]
    assert len(names) == 4
    for record in records:
        assert read(ArtifactRef.model_validate(record['artifact_ref'])) == files[record['metadata']['file_name']]
    run = runtime.runs.status(worker._run_id)
    model = _model(runtime,catalog)
    context = model.node_context(run.instance_id, 'run:evidence')
    view = presentation.build_presentation(context['artifacts'],focus_artifact_ids=context['focus_artifact_ids'])
    assert len(view['figures']) == 1
    page = render_presentation(view,evidence_href=lambda aid,p:f'/evidence/{aid}',image_href=lambda aid:f'/image/{aid}')
    assert all(name in page for name in files)
    root.call_tool('operation_invoke', {'name':'audit-attachments','operation_id':'science.evidence.audit.intake.v1',
        'instruction':'Check the exact attachment data.', 'inputs':[
            {'port':'scientific_intake','artifact_names':['evidence.output']}]})
    assert root.call_tool('run_status',{'name':'audit-attachments'})['state']=='queued'
    start = json.loads((workspace/'worker-start.json').read_text())
    assert 'worker_publish_files' in start['output']['attachments']
    assert start['budget']['attachments']['max_item_bytes']==2_000_000_000


@pytest.mark.parametrize('fault',['symlink','outside','output','missing_source','budget'])
def test_rejects_invalid_publication_without_partial_receipts(tmp_path,fault):
    _,runtime,_,worker,_,_,workspace,alias,_,args=publish_fixture(tmp_path)
    if fault=='symlink':
        (workspace/'scratch/link.csv').symlink_to(workspace/'scratch/rows.csv');args['files'][-1]['path']='scratch/link.csv'
    elif fault=='outside':args['files'][-1]['path']='scratch/../../private.csv'
    elif fault=='output':args['files'][-1]['path']='output/result.json'
    elif fault=='missing_source':args['source_aliases']=['not_bound']
    elif fault=='budget':
        with runtime.runs._connect() as db:
            run=runtime.runs.status(worker._run_id);policy=dict(run.recovery_policy);policy['attachments']['max_total_bytes']=1
            db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?',(json.dumps(policy),worker._run_id))
    with pytest.raises(DiagnosticError):worker.call_tool('worker_publish_files',args)
    assert runtime.runs.tool_evidence(worker._run_id)==[]


def test_current_scientific_agents_all_declare_publication_without_form_ports(tmp_path):
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    from curve_figure_evidence.plugin import PLUGIN as figure
    catalog=compile_catalog((CORE_PLUGIN,PLUGIN,tcad,curve,figure))
    for identity in catalog.operation_ids():
        compiled=catalog.operation(identity)
        if compiled.spec.executor.kind!='agent':continue
        assert 'worker_publish_files' in {t.name for t in compiled.worker_tools}, identity
        port=next(p for p in compiled.spec.outputs if p.name=='attachments')
        assert not port.agent_visible


def audit_worker(root, runtime, name='audit'):
    root.call_tool('operation_invoke', {'name':name, 'operation_id':'science.evidence.audit.intake.v1',
        'instruction':'Read the exact published attachments through their sealed intake.', 'inputs':[
            {'port':'scientific_intake','artifact_names':['evidence.output']}]})
    auditor=attached_worker(runtime,root,name)
    opened=auditor.call_tool('worker_open_assignment',{})
    inputs=json.loads(Path(opened['assignment_path']).read_bytes())['inputs']
    source=next(i.source_name for i in runtime.runs.status(auditor._run_id).inputs if i.port_name=='scientific_intake')
    return auditor,source


def test_downstream_discovers_and_streams_large_attachment_without_bulk_reads(tmp_path,monkeypatch):
    _,runtime,root,worker,opened,_,workspace,alias,_,args=publish_fixture(tmp_path)
    large=workspace/'scratch/large.csv'
    with large.open('wb') as stream:
        stream.write(b'x,y\n')
        stream.truncate(34*1024*1024)
    args['files']=[{'path':'scratch/large.csv','purpose':'Large generated scientific table'}]
    saved=worker.call_tool('worker_publish_files',args)
    with pytest.raises(ValueError,match='requires streamed'):
        runtime.runs.read_tool_evidence(runtime.runs.status(worker._run_id),saved['files'][0]['reference'])
    assert finish(worker,opened,saved['files'][0]['reference'])['state']=='completed'
    attachment=ArtifactRef.model_validate(runtime.runs.tool_evidence(worker._run_id)[0]['artifact_ref'])
    auditor,source=audit_worker(root,runtime)
    read=runtime.artifacts.read
    def reject_bulk(ref):
        assert ref!=attachment,'Reference file delivery must stream'
        return read(ref)
    monkeypatch.setattr(runtime.artifacts,'read',reject_bulk)
    listing=auditor.call_tool('worker_reference_read',{'source':source})
    references=listing['references']
    published=[item for item in references if item['locator'].startswith('/@attachments/')]
    assert len(published)==1
    assert {item['locator'] for item in references} == {
        published[0]['locator'], '/scientific_foundation/items/0/evidence_keys/0'}
    assert len({item['reference'] for item in references})==2
    reference=published[0]['reference']
    request={'source':source,'action':'read','reference':reference,'delivery':'file'}
    result=auditor.call_tool('worker_reference_read',request)
    path=Path(result['file_path'])
    assert path.stat().st_size==large.stat().st_size
    with path.open('rb') as stream: assert stream.read(4)==b'x,y\n'
    path.unlink()
    assert auditor.call_tool('worker_reference_read',request)['file_path']==str(path)
    assert path.exists(),'Committed receipt must rematerialize on retry'
    records=runtime.runs.reference_access_records(auditor._run_id)
    assert len(records)==1 and ArtifactRef.model_validate(records[0]['artifact_ref'])==attachment
    from tests.operations.test_l2_run_invariants import _audit_envelope
    audit_output=runtime.runs.backend.open(auditor._run_id).output_directory
    (audit_output/'result.json').write_bytes(_audit_envelope(result['source']))
    assert auditor.call_tool('worker_submit_result',{})['state']=='completed'


def test_attachment_recovery_reuses_exact_receipts(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    catalog,runtime,root,worker,_,request,_,_,files,args=publish_fixture(tmp_path)
    saved=worker.call_tool('worker_publish_files',args)
    records=runtime.runs.tool_evidence(worker._run_id)
    prior=runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(prior.run_id,reason='fixture interruption',
        expected_state=prior.state,expected_last_activity_at=prior.last_activity_at)
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    extra=runtime.artifacts.register(b'Reconsider the exact earlier sources.', ArtifactRegistration(
        kind='source',schema_id='opaque',payload_schema_version=1,media_type='text/plain',creator=runtime.actor),
        idempotency_key='additional-material')
    runtime.scheduler_bindings.bind(instance=prior.instance_id,namespace='artifact',name='new_material',object_id=extra.artifact_id)
    root.call_tool('operation_invoke',{**request,'name':'continued','draft_from':'evidence','max_attempts':2,
        'inputs':[{'port':'source_material','artifact_names':['new_material']},{'port':'feedback','artifact_names':['source_paper']}]})
    op=catalog.operation(request['operation_id'])
    following=LocalWorkerMCPRouter(runtime.runs,operation_id=op.spec.operation_id,operation_digest=op.digest)
    opened=following.call_tool('worker_open_assignment',{})
    assert runtime.runs.tool_evidence(following._run_id) == []
    page = following.call_tool('worker_reference_read', {'history_task': 'evidence', 'action': 'list'})
    selected = next(item for item in page['references'] if item.get('original_name') == records[0]['alias'])
    read = following.call_tool('worker_reference_read', {'history_task': 'evidence', 'action': 'read',
        'reference': selected['reference'], 'delivery': 'file'})
    access = runtime.runs.reference_access_records(following._run_id)[0]
    assert access['artifact_ref'] == records[0]['artifact_ref']
    assert access['producer_run_id'] == prior.run_id
    assert runtime.runs.tool_evidence(following._run_id) == []
    # The child's former alias points at new_material; selected proof retains
    # the exact original producer namespace without copying its receipts.
    proof = ArtifactRef.model_validate(access['proof_manifest_ref'])
    document = json.loads(runtime.artifacts.read(proof))
    original_alias = prior.inputs[0].source_name
    assert document['bindings'][original_alias]['artifact_ref'] == prior.inputs[0].artifact_ref.model_dump(mode='json')
    assert runtime.runs.status(following._run_id).inputs[0].artifact_ref != prior.inputs[0].artifact_ref
    assert finish(following, opened, read['source'])['state'] == 'completed'
    assert runtime.runs.tool_evidence(prior.run_id) == records


def test_full_64_attachment_history_is_referenced_and_new_storage_has_its_own_budget(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    catalog, runtime, root, worker, _, request, workspace, alias, _, _ = publish_fixture(tmp_path)
    files = []
    for number in range(64):
        path = f'scratch/retained_{number:03d}.csv'
        (workspace/path).write_bytes(b'x\n1\n')
        files.append(dict(path=path, purpose='Exact retained data'))
    saved = worker.call_tool('worker_publish_files', dict(files=files, source_aliases=[alias]))
    originals = runtime.runs.tool_evidence(worker._run_id)
    runtime.runs.fail(worker._run_id, reason='seal full original attachment capacity')
    root.call_tool('operation_invoke', {**request, 'name': 'continued_capacity', 'draft_from': request['name'], 'max_attempts': 2})
    compiled = catalog.operation(request['operation_id'])
    following = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = following.call_tool('worker_open_assignment', {})
    run = runtime.runs.status(following._run_id)
    budget = runtime.runs.worker_budget(run)['evidence_capacity']
    assert budget['attachments']['used'] == budget['records']['used'] == 0
    assert budget['attachments']['remaining'] == 64 and 'historical_references' not in budget
    assert runtime.runs.tool_evidence(run.run_id) == []
    page = following.call_tool('worker_reference_read', {'history_task': request['name'], 'action': 'list'})
    selected = next(item for item in page['references'] if item.get('original_name') == originals[0]['alias'])
    read = following.call_tool('worker_reference_read', {'history_task': request['name'], 'action': 'read',
        'reference': selected['reference'], 'delivery': 'file'})
    assert runtime.runs.reference_access_records(run.run_id)[0]['artifact_ref'] == originals[0]['artifact_ref']
    continued_workspace = Path(opened['assignment_path']).parent
    (continued_workspace/'scratch/new.csv').write_bytes(b'x\n2\n')
    added = following.call_tool('worker_publish_files', dict(files=[dict(path='scratch/new.csv', purpose='New observation')], source_aliases=[alias]))
    snapshot = json.loads(runtime.runs._evidence_snapshot(run.run_id))
    assert len(snapshot['records']) == len(snapshot['accesses']) == 1
    assert snapshot['recovery'] is None and 'references' not in snapshot
    assert runtime.runs.tool_evidence(worker._run_id) == originals
    assert runtime.runs.worker_budget(run)['evidence_capacity']['attachments']['used'] == 1
    before = runtime.runs._evidence_snapshot(run.run_id)
    assert finish(following, opened, added['files'][0]['reference'])['state'] == 'completed'
    assert runtime.runs._evidence_snapshot(run.run_id) == before


def test_recovery_64_actual_attempts_still_allow_file_and_reject_next_handler(tmp_path):
    from dataclasses import replace
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    catalog, runtime, root, worker, _, request, _, alias, _, args = publish_fixture(tmp_path)
    worker.call_tool('worker_publish_files', {**args, 'files': args['files'][:1]})
    tool = worker._registered['worker_capture_source']
    for ordinal in range(64):
        runtime.runs.begin_tool_attempt(worker._run_id, tool, {'ordinal': ordinal})
    runtime.runs.fail(worker._run_id, reason='seal spent actual starts')
    root.call_tool('operation_invoke', {**request, 'name': 'continued_attempts', 'draft_from': request['name'], 'max_attempts': 2})
    compiled = catalog.operation(request['operation_id'])
    following = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = following.call_tool('worker_open_assignment', {})
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/new.csv').write_bytes(b'x\n2\n')
    assert following.call_tool('worker_publish_files', dict(files=[dict(path='scratch/new.csv', purpose='New file')], source_aliases=[alias]))['state'] == 'retained'
    following._registered['worker_capture_source'] = replace(following._registered['worker_capture_source'],
        contextual_handler=lambda *a: pytest.fail('Spent attempt reached its handler'))
    with pytest.raises(WorkerToolError) as caught:
        following.call_tool('worker_capture_source', {'url': 'https://example.org/next'})
    assert caught.value.details[0]['code'] == 'tool_attempt_limit'
    budget = runtime.runs.worker_budget(runtime.runs.status(following._run_id))['evidence_capacity']
    assert budget['attempts']['remaining'] == 0 and budget['attachments']['used'] == 1


@pytest.mark.parametrize('field', ['tool_name', 'media_type', 'size_bytes'])
def test_history_read_cannot_change_original_receipt_identity(tmp_path, field):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.operation_contract import DiagnosticError
    catalog, runtime, root, worker, _, request, _, _, _, args = publish_fixture(tmp_path)
    worker.call_tool('worker_publish_files', {**args, 'files': args['files'][:1]})
    runtime.runs.fail(worker._run_id, reason='retain original identity')
    root.call_tool('operation_invoke', {**request, 'name': 'reference_identity', 'draft_from': request['name'], 'max_attempts': 2})
    compiled = catalog.operation(request['operation_id'])
    following = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    following.call_tool('worker_open_assignment', {})
    page = following.call_tool('worker_reference_read', {'history_task': request['name'], 'action': 'list'})
    selected = next(item for item in page['references'] if item.get('original_name') == 'attachment_001')
    with runtime.runs._connect() as db:
        stored = db.execute('SELECT evidence_key,record_json FROM run_tool_evidence WHERE run_id=? ORDER BY ordinal LIMIT 1', (worker._run_id,)).fetchone()
        original = json.loads(stored['record_json'])
        original[field] = original[field] + 1 if field == 'size_bytes' else 'forged'
        db.execute('UPDATE run_tool_evidence SET record_json=? WHERE run_id=? AND evidence_key=?',
            (json.dumps(original), worker._run_id, stored['evidence_key']))
    with pytest.raises(DiagnosticError):
        following.call_tool('worker_reference_read', {'history_task': request['name'], 'action': 'read',
            'reference': selected['reference'], 'delivery': 'file'})
    assert runtime.runs.tool_evidence(following._run_id) == []
    assert runtime.runs.reference_access_records(following._run_id) == []


def test_attachment_publication_and_retry_allow_large_binding_aggregate(tmp_path, monkeypatch):
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.attachments import publish_attachments
    from scidiscovery.attachment_tools import PublishFiles
    from scidiscovery.artifact_agent.schema.common import canonical_json
    _, runtime, _, worker, _, _, workspace, alias, _, args = publish_fixture(tmp_path)
    runs, rid = runtime.runs, worker._run_id
    owner = runs.status(rid)
    # Model a legacy frozen input set; each input and the new file are bounded.
    expanded = replace(owner, inputs=tuple(replace(owner.inputs[0], source_name=alias if i == 0 else f'legacy_{i}')
        for i in range(128)))
    require = runs._require_running
    monkeypatch.setattr(runs, '_require_running', lambda current: expanded if current == rid else require(current))
    monkeypatch.setattr(runs, '_refresh_evidence_schema', lambda _: None)
    request = PublishFiles.model_validate_json(canonical_json({**args, 'files': args['files'][:1]}))
    first = publish_attachments(runs, rid, request, workspace=workspace)
    assert publish_attachments(runs, rid, request, workspace=workspace) == first
    snapshot = json.loads(runs._encode_evidence_snapshot(expanded, runs.tool_evidence(rid), [], None, []))
    assert len(snapshot['bindings']) == 129


def test_reference_access_does_not_consume_attachment_receipt_allowance(tmp_path):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    _, runtime, root, worker, opened, _, _, _, _, args = publish_fixture(tmp_path)
    args['files'] = args['files'][:1]
    saved = worker.call_tool('worker_publish_files', args)
    assert finish(worker, opened, saved['files'][0]['reference'])['state'] == 'completed'
    auditor, source = audit_worker(root, runtime)
    listed = auditor.call_tool('worker_reference_read', {'source': source})
    auditor.call_tool('worker_reference_read', {'source': source, 'action': 'read',
        'reference': listed['references'][0]['reference'], 'delivery': 'file'})
    runs, rid = runtime.runs, auditor._run_id
    assert len(runs.reference_access_records(rid)) == 1
    # Recreate a legacy owner with 127 receipts and one independently bounded
    # reference access. Its last allowed scientific file must still fit.
    template = runs.tool_evidence(worker._run_id)[0]
    with runs._connect() as db:
        for number in range(2, 129):
            record = {**template, 'alias': f'legacy_{number}', 'output_port': 'tool_evidence',
                'metadata': {'kind': 'historical_observation', 'derived_from': [source]}}
            db.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                (rid, number, f'legacy-{number}', canonical_json(record), record['alias']))
    workspace = Path(auditor.call_tool('worker_open_assignment', {})['assignment_path']).parent
    (workspace / 'scratch' / 'last.csv').write_text('x,y\n1,2\n')
    request = {'source_aliases': [source], 'files': [{'path': 'scratch/last.csv', 'purpose': 'Last bounded receipt'}]}
    retained = auditor.call_tool('worker_publish_files', request)
    assert retained['state'] == 'retained'
    assert auditor.call_tool('worker_publish_files', request) == retained
    snapshot = json.loads(runs._evidence_snapshot(rid))
    assert len(snapshot['records']) == 128 and len(snapshot['accesses']) == 1
    (workspace / 'scratch' / 'last.csv').write_text('x,y\n1,3\n')
    with pytest.raises(DiagnosticError):
        auditor.call_tool('worker_publish_files', request)
