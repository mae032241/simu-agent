"""Task-context restrictions are conservative permissions, never adoption proof."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.scientific_usage import (
    EDGE_ACTIVITY, ScientificProvenanceError, _context_identity, _owner_identity,
    scientific_use_restricted,
)
from scidiscovery.operations.tooling import reference_policy
from scidiscovery.reference_tools import ReferencePolicy
from tests.operations.test_artifact_capture import experiment as open_experiment, records
from tests.operations.test_scientific_use_provenance_continuation import system, consume
from tests.operations.test_scientific_use_provenance_edges import setup, experiment
from tests.operations.worker_fixtures import attached_worker


def copy_task(tmp_path, *, restricted=True, extra_restricted=False):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    prior = experiment(runtime, instance, root, 'prior', restricted=restricted)
    request = {'name':'copy', 'operation_id':'science.experiment.v1', 'max_attempts':2,
        'instruction':'Retain this exact prior report without inferring a new result.',
        'inputs':[{'port':'subject', 'artifact_names':['prior.output']}]}
    if extra_restricted:
        request['inputs'].append({'port':'scientific_materials','artifact_names':['restricted']})
    root.call_tool('operation_invoke', request)
    worker = attached_worker(runtime, root, 'copy')
    opened = worker.call_tool('worker_open_assignment', {})
    run = runtime.runs.status(worker._run_id)
    subject = next(i.source_name for i in run.inputs if i.port_name == 'subject')
    goal = next(i.source_name for i in run.inputs if i.port_name == 'objective_source')
    raw = runtime.artifacts.read(prior)
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/artifacts/copied.json').write_bytes(raw)
    return runtime, instance, root, worker, opened, prior, subject, goal, raw, request


def seal_copy(worker, opened, *, declaration=None):
    request = {'stage':'design', 'conclusion':'Retain the exact prior report bytes.',
        'materials':['file:scratch/artifacts/copied.json']}
    if declaration:
        request['capture_sources'] = [{'source_aliases':[declaration]}]
    stage = worker.call_tool('worker_experiment_stage', request)
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload':{
        'summary':'The exact original is retained.', 'outcome':'inconclusive',
        'remaining_question':'Independent interpretation is still required.',
        'limitations':['Sealing does not verify the reported science.'],
        'adopted_stages':[stage['reference']]}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    return stage


@pytest.mark.parametrize('declaration', ['default','subject','clean'])
def test_restricted_subject_cannot_be_laundered_by_default_or_clean_declaration(tmp_path,declaration):
    runtime, _, root, worker, opened, prior, subject, goal, raw, _ = copy_task(tmp_path)
    seal_copy(worker,opened,declaration={'subject':subject,'clean':goal}.get(declaration))
    item = next(r for r in records(runtime,worker) if r['metadata'].get('locator') == 'scratch/artifacts/copied.json')
    ref = ArtifactRef.model_validate(item['artifact_ref'])
    assert runtime.artifacts.read(ref) == raw
    assert prior in runtime.artifacts.catalog(ref).parent_refs
    assert (subject in item['metadata']['derived_from']) is (declaration == 'subject')
    assert item['metadata']['provenance_basis'] == ('task_scope' if declaration == 'default' else 'author_declared')
    assert item['metadata']['capture_source_scope'] == 'task_inputs_v1'
    assert item['metadata']['scientific_claim_admissible'] is False
    assert runtime.artifacts.catalog(ref).labels['scientific_claim_admissible'] == 'false'
    assert scientific_use_restricted(runtime.runs,(ref,))
    final = runtime.runs.status(worker._run_id).output_ref
    assert scientific_use_restricted(runtime.runs,(final,))
    admission = consume(root,'copy.output','experiment')
    assert not admission['admissible'] and admission['reason_code'] == 'input_scientific_claim_forbidden'
    with pytest.raises(Exception,match='input_scientific_claim_forbidden'):
        consume(root,'copy.output','experiment','operation_invoke')


def test_clean_task_scope_remains_readable_and_claim_admissible_without_false_adoption(tmp_path):
    runtime, _, root, worker, opened, _, subject, _, raw, _ = copy_task(tmp_path,restricted=False)
    seal_copy(worker,opened)
    item = next(r for r in records(runtime,worker) if r['metadata'].get('locator') == 'scratch/artifacts/copied.json')
    ref = ArtifactRef.model_validate(item['artifact_ref'])
    assert subject not in item['metadata']['derived_from']
    assert runtime.artifacts.read(ref) == raw
    assert item['metadata']['scientific_claim_admissible'] is True
    assert runtime.artifacts.catalog(ref).labels.get('scientific_claim_admissible') != 'false'
    assert consume(root,'copy.output','experiment')['admissible']


def test_optional_scientific_material_restriction_cannot_be_omitted_from_capture_scope(tmp_path):
    runtime, _, root, worker, opened, _, _, _, _, _ = copy_task(tmp_path,restricted=False,extra_restricted=True)
    seal_copy(worker,opened)
    run = runtime.runs.status(worker._run_id)
    optional = next(i.source_name for i in run.inputs if i.port_name == 'scientific_materials')
    item = next(r for r in records(runtime,worker) if r['metadata'].get('locator') == 'scratch/artifacts/copied.json')
    assert optional not in item['metadata']['derived_from']
    assert item['metadata']['scientific_claim_admissible'] is False
    assert runtime.artifacts.catalog(ArtifactRef.model_validate(item['artifact_ref'])).labels['scientific_claim_admissible'] == 'false'
    assert not consume(root,'copy.output','experiment')['admissible']


def legacy_receipt(runtime,worker):
    """Emulate old private receipt/edge facts; never rewrite sealed Artifact bytes."""
    run = runtime.runs.status(worker._run_id)
    item = next(r for r in records(runtime,worker) if r['metadata'].get('locator') == 'scratch/artifacts/copied.json')
    old = json.loads(canonical_json(item))
    old['metadata'].pop('capture_source_scope')
    old['metadata'].pop('provenance_basis')
    ref = ArtifactRef.model_validate(old['artifact_ref'])
    with runtime.runs._connect() as db:
        db.execute('UPDATE run_tool_evidence SET record_json=? WHERE run_id=? AND alias=?',
            (canonical_json(old),run.run_id,item['alias']))
        rows = db.execute('SELECT rowid,diagnostic_json FROM run_activity WHERE run_id=? AND activity=?',
            (run.run_id,EDGE_ACTIVITY)).fetchall()
        for row in rows:
            value = json.loads(row[1])
            if value['artifact_ref'] == old['artifact_ref']:
                value['check_key'] = canonical_sha256({'context':_context_identity(runtime.runs,
                    reference_policy(runtime.runs._compiled(run)) or ReferencePolicy()),
                    'owner':_owner_identity(run,ref,old)})
                value.pop('edge_digest')
                value['edge_digest'] = canonical_sha256(value)
                db.execute('UPDATE run_activity SET diagnostic_json=? WHERE rowid=?',
                    (canonical_json(value),row[0]))
    return ref


@pytest.mark.parametrize('state',['warm','cold','restart'])
def test_markerless_auto_original_and_final_are_readable_but_unconfirmed_before_cached_edges(tmp_path,state):
    runtime, _, root, worker, opened, _, _, _, raw, _ = copy_task(tmp_path,restricted=False)
    seal_copy(worker,opened)
    ref = legacy_receipt(runtime,worker)
    final = runtime.runs.status(worker._run_id).output_ref
    checker = runtime.runs
    if state == 'cold':
        with checker._connect() as db:
            db.execute('DELETE FROM run_activity WHERE activity=?',(EDGE_ACTIVITY,))
    elif state == 'restart':
        from scidiscovery.artifact_agent.service.runs import RunService
        checker = RunService(artifacts=checker.artifacts,database_path=checker.database_path,
            service_actor=checker.service_actor,operation_catalog=checker.operation_catalog,
            backend=checker.backend,scheduler_bindings=checker.scheduler_bindings)
    assert runtime.artifacts.read(ref) == raw
    for source in (ref,final):
        with pytest.raises(ScientificProvenanceError,match='scope is unconfirmed'):
            scientific_use_restricted(checker,(source,))
    reply = consume(root,'copy.output','experiment')
    assert not reply['admissible'] and reply['reason_code'] == 'input_scientific_provenance_unavailable'


@pytest.mark.parametrize('receipt',['scope_checked','legacy'])
def test_scope_marked_capture_recovery_requires_original_subject_even_when_only_goal_is_declared(tmp_path,receipt):
    runtime, _, root, worker, opened, _, _, goal, _, request = copy_task(tmp_path,restricted=False)
    worker.call_tool('worker_experiment_stage',{'stage':'design','conclusion':'Retain exact bytes.',
        'materials':['file:copied.json'],'capture_sources':[{'source_aliases':[goal]}]})
    saved = records(runtime,worker)
    assert any(r['metadata'].get('capture_source_scope') for r in saved)
    if receipt == 'legacy':
        legacy_receipt(runtime,worker)
    prior = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(prior.run_id,reason='fixture interruption',expected_state=prior.state,
        expected_last_activity_at=prior.last_activity_at)
    root.call_tool('operation_invoke',{**request,'name':'changed','draft_from':'copy',
        'inputs':[{'port':'subject','artifact_names':['objective.hypothesis.output']}]})
    changed = attached_worker(runtime,root,'changed')
    changed.call_tool('worker_open_assignment',{})
    assert not any(r['metadata'].get('capture_source_scope') for r in records(runtime,changed))
    assert runtime.runs.recovery_evidence_status(runtime.runs.status(changed._run_id))['adopted_count'] == 0


@pytest.mark.parametrize('keep_optional',[True,False])
def test_capture_recovery_requires_undeclared_optional_scope_and_keeps_exact_restrictions(tmp_path,keep_optional):
    runtime, _, root, worker, opened, _, _, goal, raw, request = copy_task(
        tmp_path,restricted=False,extra_restricted=True)
    worker.call_tool('worker_experiment_stage',{'stage':'design','conclusion':'Retain exact bytes.',
        'materials':['file:copied.json'],'capture_sources':[{'source_aliases':[goal]}]})
    saved = records(runtime,worker)
    item = next(r for r in saved if r['metadata'].get('locator') == 'scratch/artifacts/copied.json')
    assert item['metadata']['scientific_claim_admissible'] is False
    prior = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(prior.run_id,reason='fixture interruption',expected_state=prior.state,
        expected_last_activity_at=prior.last_activity_at)
    inputs = request['inputs'] if keep_optional else request['inputs'][:1]
    root.call_tool('operation_invoke',{**request,'name':'continued','draft_from':'copy','inputs':inputs})
    following = attached_worker(runtime,root,'continued')
    following.call_tool('worker_open_assignment',{})
    adopted = records(runtime,following)
    ref = ArtifactRef.model_validate(item['artifact_ref'])
    assert runtime.artifacts.read(ref) == raw
    if keep_optional:
        assert adopted == saved
        assert scientific_use_restricted(runtime.runs,(ref,))
        assert runtime.runs.recovery_evidence_status(runtime.runs.status(following._run_id))['adopted_count'] == len(saved)
    else:
        assert not any(r['artifact_ref'] == item['artifact_ref'] for r in adopted)
        assert runtime.runs.recovery_evidence_status(runtime.runs.status(following._run_id))['adopted_count'] == 0


@pytest.mark.parametrize('restricted',[False,True])
def test_third_party_auto_capture_cannot_omit_feedback_restriction_at_claim_consumer(tmp_path,restricted):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.general_science_agent_operations import INTAKE_OUTPUT, _input
    from scidiscovery.operation_declaration import scientific_agent_operation
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import ArtifactCaptureSpec, ComponentRef, ComponentSpec, PluginDependency, PluginDefinition
    from tests.operations.test_artifact_capture import draft
    from tests.operations.test_general_transform_operations import _root, _register
    def general(reference):
        return ComponentRef(reference.component_id,'general_science') if reference is not None else None
    def source(name,schema,*,min_items=1,usage='claim_evidence'):
        port = _input(name,'Exact original for the capture fixture.',schema,
            media_types=('application/json',) if schema != 'opaque' else ('text/plain',),
            min_items=min_items,usage=usage)
        return port.model_copy(update={'codec':general(port.codec),'schema_resource':general(port.schema_resource)})
    output = INTAKE_OUTPUT.model_copy(update={key:general(getattr(INTAKE_OUTPUT,key)) for key in
        ('codec','schema_resource','validator','context_validator','semantic_contract')})
    def declaration(name,inputs,**kwargs):
        return scientific_agent_operation(name,'Retain one exact custom-root batch.',
            'Capture needs immutable originals.','Independent qualification.',
            agent=ComponentRef('evidence_agent','general_science'),workspace=ComponentRef('workspace','general_science'),
            prompt=ComponentRef('prompt'),tools=(),inputs=inputs,outputs=(output,),timeout=300,
            max_input_bytes=1024*1024,max_output_bytes=65536,max_files=1,**kwargs)
    producer = declaration('third_party.scope_capture.v1',
        (source('source_material','opaque'),source('feedback','opaque',min_items=0,usage='evidence_inventory')),
        artifact_capture=ArtifactCaptureSpec(roots=('scratch/results',),required_source_ports=('source_material',)))
    consumer = declaration('third_party.scope_consume.v1',
        (source('source_material','scidiscovery.scientific-intake.v1',usage='claim_evidence'),))
    plugin = PluginDefinition(plugin_id='third_party_scope',version='0.1.0',protocol_version='1',
        dependencies=(PluginDependency('builtin','0.1.0'),PluginDependency('general_science','0.1.0')),
        components=(ComponentSpec('prompt','resource','scidiscovery.general_science_resources:Resources.evidence_prompt'),),
        operations=(producer,consumer))
    catalog = compile_catalog((CORE_PLUGIN,PLUGIN,plugin))
    runtime, instance, root = _root(tmp_path,catalog=catalog)
    runtime.runs.operation_catalog = catalog
    for name in ('original','feedback'):
        _register(runtime,instance,name=name,raw=name.encode(),kind='source',schema='opaque',
            media_type='text/plain',provisional=restricted and name == 'feedback')
    root.call_tool('operation_invoke',{'name':'captured','operation_id':producer.operation_id,
        'instruction':'Retain the custom-root source bytes.',
        'inputs':[{'port':name,'artifact_names':[alias]} for name,alias in
            [('source_material','original'),('feedback','feedback')]]})
    worker = attached_worker(runtime,root,'captured')
    opened = worker.call_tool('worker_open_assignment',{})
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/results/data.csv').write_bytes(b'x,y\n1,2\n')
    clean = next(i.source_name for i in runtime.runs.status(worker._run_id).inputs if i.port_name == 'source_material')
    draft(opened,'file:scratch/results/data.csv',batch_sources=[clean])
    assert worker.call_tool('worker_submit_result',{})['state'] == 'completed'
    item = next(r for r in records(runtime,worker) if r['metadata'].get('locator') == 'scratch/results/data.csv')
    assert item['metadata']['derived_from'] == [clean]
    assert item['metadata']['capture_source_scope'] == 'task_inputs_v1'
    assert item['metadata']['scientific_claim_admissible'] is not restricted
    assert runtime.artifacts.read(ArtifactRef.model_validate(item['artifact_ref'])) == b'x,y\n1,2\n'
    request = {'name':'claim','operation_id':consumer.operation_id,'instruction':'Use the retained intake as claim evidence.',
        'inputs':[{'port':'source_material','artifact_names':['captured.output']}]}
    reply = root.call_tool('operation_preflight',request)
    assert reply['admissible'] is not restricted
    if restricted:
        assert reply['reason_code'] == 'input_scientific_claim_forbidden'
        with pytest.raises(Exception,match='input_scientific_claim_forbidden'):
            root.call_tool('operation_invoke',request)


@pytest.mark.parametrize('surface',['publication','declaration'])
def test_author_cannot_supply_control_scope_marker(tmp_path,surface):
    runtime, _, _, worker, _, workspace = open_experiment(tmp_path)
    goal = next(i.source_name for i in runtime.runs.status(worker._run_id).inputs if i.port_name == 'objective_source')
    (workspace/'scratch/artifacts/data.txt').write_bytes(b'bounded data\n')
    before = records(runtime,worker)
    if surface == 'publication':
        name,args = 'worker_publish_files',{'files':[{'path':'scratch/artifacts/data.txt','purpose':'Fixture.'}],
            'source_aliases':[goal],'capture_source_scope':'task_inputs_v1'}
    else:
        name,args = 'worker_experiment_stage',{'stage':'design','conclusion':'Fixture.',
            'materials':['file:data.txt'],'capture_sources':[{'source_aliases':[goal],
                'capture_source_scope':'task_inputs_v1'}]}
    with pytest.raises(Exception): worker.call_tool(name,args)
    assert records(runtime,worker) == before


def test_unknown_scope_check_does_not_publish_a_positive_file_receipt(tmp_path,monkeypatch):
    runtime, _, _, worker, _, _ = open_experiment(tmp_path)
    workspace = runtime.runs.backend.open(worker._run_id).root
    (workspace/'scratch/artifacts/data.txt').write_bytes(b'bounded data\n')
    import scidiscovery.artifact_agent.service.scientific_usage as usage
    def unavailable(*args,**kwargs): raise ScientificProvenanceError('Scope fixture unavailable')
    monkeypatch.setattr(usage,'scientific_use_restricted',unavailable)
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    with pytest.raises(WorkerToolError,match='control diagnostic has been retained'):
        worker.call_tool('worker_experiment_stage',{'stage':'design','conclusion':'Fixture.','materials':['file:data.txt']})
    assert not records(runtime,worker)


@pytest.mark.parametrize('fault',['actual_byte_cap','unsupported_npz'])
def test_cited_oversized_or_unsupported_auto_file_fails_closed(tmp_path,fault):
    runtime, instance, root = system(tmp_path)
    setup(runtime,instance,root)
    if fault == 'actual_byte_cap':
        from scidiscovery.agent_execution_settings import parse_settings
        runtime.runs.agent_settings = parse_settings({'attachments':{
            'max_item_bytes':1024,'max_total_bytes':8192}})
    root.call_tool('operation_invoke',{'name':'capture','operation_id':'science.experiment.v1',
        'inputs':[{'port':'subject','artifact_names':['objective.hypothesis.output']}],
        'instruction':'Retain exact bounded data.'})
    worker = attached_worker(runtime,root,'capture')
    opened = worker.call_tool('worker_open_assignment',{})
    workspace = Path(opened['assignment_path']).parent
    name = 'large.csv' if fault == 'actual_byte_cap' else 'data.npz'
    raw = b'x\n'+b'1\n'*1024 if fault == 'actual_byte_cap' else b'\x00safe binary fixture\x00'
    path = workspace/'scratch/artifacts'/name
    path.write_bytes(raw)
    if fault == 'actual_byte_cap': assert path.stat().st_size > 1024
    with pytest.raises(Exception):
        worker.call_tool('worker_experiment_stage',{'stage':'design','conclusion':'Retain original.',
            'materials':['file:'+name]})
    current = records(runtime,worker)
    assert not any(r['metadata'].get('kind') == 'experiment_stage' for r in current)
    assert not any(r['metadata'].get('locator') == 'scratch/artifacts/'+name for r in current)
    inventory = next(r for r in current if r['metadata'].get('kind') == 'capture_inventory')
    entry = next(e for e in json.loads(runtime.artifacts.read(ArtifactRef.model_validate(inventory['artifact_ref'])))['entries']
        if e.get('path') == 'scratch/artifacts/'+name)
    if fault == 'actual_byte_cap':
        assert entry['status'] == 'incomplete' and entry['reason'] == 'attachment_publication_invalid'
    else:
        assert entry['status'] == 'metadata_only'
        goal = next(i.source_name for i in runtime.runs.status(worker._run_id).inputs if i.port_name == 'objective_source')
        published = worker.call_tool('worker_publish_files',{'files':[{'path':'scratch/artifacts/'+name,
            'purpose':'Explicit authorized binary.'}],'source_aliases':[goal]})['files'][0]['reference']
        assert runtime.runs.read_tool_evidence(runtime.runs.status(worker._run_id),published) == raw
        assert worker.call_tool('worker_experiment_stage',{'stage':'design','conclusion':'Retain explicitly authorized data.',
            'materials':[published]})['state'] == 'sealed'
