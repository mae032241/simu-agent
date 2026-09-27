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
            {'port':'scientific_intake','artifact_names':['evidence.output']},
            {'port':'source_material','artifact_names':['source_paper',*names]}]})
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
            {'port':'scientific_intake','artifact_names':['evidence.output']},
            {'port':'source_material','artifact_names':['source_paper']}]})
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
    reference=listing['references'][0]['reference']
    assert len(listing['references'])==1
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
    assert runtime.runs.tool_evidence(following._run_id)==records
    workspace=Path(opened['assignment_path']).parent
    for name,data in files.items():(workspace/'scratch'/name).write_bytes(data)
    # The same original is now bound under another alias. Identity is unchanged.
    args['source_aliases']=[next(i.source_name for i in runtime.runs.status(following._run_id).inputs if i.port_name=='feedback')]
    assert following.call_tool('worker_publish_files',args)==saved
    assert runtime.runs.tool_evidence(following._run_id)==records
    assert finish(following,opened,saved['files'][0]['reference'])['state']=='completed'
