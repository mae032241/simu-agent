"""Real input binding and lazy file delivery, without solver or model processes."""
import hashlib
from dataclasses import replace
import json
from pathlib import Path

import pytest

from scidiscovery.agent_execution_settings import AgentSettings, MaterialInputSettings
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_hypothesis_objective_boundary import _foundation
from scidiscovery.operations.invoke import InvocationArtifact, preflight_operation
from scidiscovery.operations.input_validation import OperationInvocationError
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN


@pytest.fixture
def catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))


def test_material_files_stream_through_real_root_and_worker(tmp_path, monkeypatch, catalog):
    from scidiscovery.artifact_agent import runtime as runtime_module
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections
    monkeypatch.setattr(runtime_module, 'compile_installed_catalog', lambda: catalog)
    project = tmp_path / 'project'
    project.mkdir()
    settings = AgentSettings(input_materials=MaterialInputSettings(
        max_item_bytes=6_000_000, max_total_bytes=7_000_000,
        inline_max_bytes=128, transfer_chunk_bytes=4096))
    runtime = runtime_module.open_runtime(project_root=project, state_root=tmp_path / 'state',
        approval_receipt_secret=b'a'*32, agent_settings=settings)
    instance = runtime.scheduler_bindings.create_instance(name='materials', title='Materials', objective='Read exact files.')
    def register(name, raw, media, schema='opaque'):
        envelope = runtime.artifacts.register(raw, ArtifactRegistration(kind='material', schema_id=schema,
            payload_schema_version=1, media_type=media, creator=runtime.actor), idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name=name, object_id=envelope.artifact_id)
        return envelope
    register('objective', canonical_json({'objective_key':'objective', 'intent':'engineering',
        'statement':'Read exact files.', 'closure_requirements':[{'requirement_key':'files',
        'description':'Retain exact material.', 'requirement_type':'comparison_present',
        'comparison_purposes':['exploratory_diagnostic']}]}), 'application/json', 'scidiscovery.research-objective.v1')
    materials = {
        'paper': (b'%PDF-' + b'x'*4_714_969, 'application/pdf'),
        'png': (b'png bytes', 'image/png'),
        'csv': (b'x,y\n1,2\n', 'text/csv'),
        'large_csv': (b'x,y\n1,2\n'*1000, 'text/csv'),
        'archive': (b'archive bytes', 'application/zip'),
        'grid': (b'grid bytes', 'application/octet-stream'),
        'report': (b'{"summary":"Observation"}', 'application/json'),
    }
    envelopes = {name: register(name, raw, media, 'scidiscovery.synthetic-report.v1' if name=='report' else 'opaque')
                 for name,(raw,media) in materials.items()}
    root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
        instance=instance.instance_id, operation_catalog=catalog))
    protected = {e.ref for name,e in envelopes.items() if name not in ('csv',)}
    read = runtime.artifacts.read
    def no_bulk(ref):
        assert ref not in protected, 'A referenced material was loaded as one bytes object'
        return read(ref)
    monkeypatch.setattr(runtime.artifacts, 'read', no_bulk)
    # Explicit file references accept JSON schemas and text/image MIME types too.
    created = root.call_tool('operation_invoke', {'name':'read-materials', 'operation_id':'science.experiment.v1',
        'inputs':[{'port':'subject','artifact_names':['objective']},
                  {'port':'scientific_materials','artifact_names':['paper','csv','large_csv','archive','grid']},
                  {'port':'scientific_files','artifact_names':['png','report']}],
        'instruction':'Read exact materials without dropping the original paper.'})
    assert created['result']['state']=='queued'
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='read-materials')
    run = runtime.runs.status(run_id)
    assert run.recovery_policy['input_materials']==settings.input_materials.model_dump()
    by_name = {v.artifact_name:v for v in run.inputs}
    assert by_name['csv'].exposure=='on_demand'
    assert all(by_name[n].exposure=='file_reference' for n in materials if n!='csv')
    WorkerConnections(runtime.runs).attach(run_id=run_id,platform_session='session',thread_id='author')
    compiled = catalog.operation('science.experiment.v1')
    assert compiled.spec.executor.native_tools.view_image
    class UnusedExecutionService:
        def __getattr__(self, name):
            raise AssertionError('Material delivery must not invoke an executor')
    services = {key: UnusedExecutionService() for tool in compiled.worker_tools for key in tool.required_services}
    worker = LocalWorkerMCPRouter(runtime.runs,operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    opened = worker.call_tool('worker_open_assignment',{})
    workspace=Path(opened['workspace_path'])
    startup=json.loads(Path(opened['start_here_path']).read_text())
    assert 'worker_materialize_input' in startup['reading']['files']
    assert all('artifact_ref' not in v for v in startup['inputs'])
    # Check actual streaming read calls and frozen chunk configuration.
    original = runtime.artifacts.open_original
    from contextlib import contextmanager
    sizes=[]
    @contextmanager
    def bounded(ref):
        with original(ref) as source:
            class Reader:
                def read(self,size=-1):
                    assert 0<size<=4096
                    sizes.append(size)
                    return source.read(size)
            yield Reader()
    monkeypatch.setattr(runtime.artifacts,'open_original',bounded)
    for name,(raw,media) in materials.items():
        reply=worker.call_tool('worker_materialize_input',{'source_name':by_name[name].source_name})
        path=workspace/reply['relative_path']
        digest=hashlib.sha256()
        with path.open('rb') as f:
            while chunk:=f.read(4096):digest.update(chunk)
        assert digest.hexdigest()==hashlib.sha256(raw).hexdigest()
        assert reply['size_bytes']==len(raw)
        assert len(json.dumps(reply))<1024
    assert sizes
    with pytest.raises(Exception,match='undeclared|input'):
        worker.call_tool('worker_materialize_input',{'source_name':'../../secret'})
    contract=root.call_tool('operation_catalog',{'operation_id':'science.experiment.v1','view':'detail','scope':'all'})['operations'][0]
    assert contract['input_materials']['max_total_bytes']==7_000_000
    assert next(p for p in contract['inputs'] if p['name']=='scientific_materials')['max_item_bytes']==6_000_000


def test_material_budget_rejects_before_any_content_read(catalog):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    compiled=catalog.operation('science.experiment.v1')
    def artifact(name,size,schema='opaque',media='application/pdf'):
        return InvocationArtifact(name, ArtifactRef(artifact_id=name,kind='material',sha256='a'*64,schema_id=schema),schema,media,size)
    inputs={p.name:() for p in compiled.spec.inputs}
    goal = _foundation()
    source = artifact('objective',len(goal),'scidiscovery.scientific-foundation.v1','application/json')
    source = replace(source, ref=source.ref.model_copy(update={'sha256': hashlib.sha256(goal).hexdigest()}))
    inputs['subject']=inputs['objective_source']=(source,)
    inputs['scientific_materials']=(artifact('paper',4_714_974),)
    def forbidden(ref):raise AssertionError('Rejected inputs must not be read')
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(compiled,name='large',artifacts_by_port=inputs,instruction='Read',read_artifact=forbidden,
            material_settings=MaterialInputSettings(max_item_bytes=4_000_000))
    assert error.value.reason_code=='input_item_too_large'
    assert 'paper' in error.value.details[0]['message'] and '4714974' in error.value.details[0]['message']
    inputs['scientific_files']=(artifact('grid',10),)
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(compiled,name='total',artifacts_by_port=inputs,instruction='Read',read_artifact=forbidden,
            material_settings=MaterialInputSettings(max_total_bytes=4_714_974))
    assert error.value.reason_code=='input_total_too_large'
    assert 'grid' in error.value.details[0]['message'] and 'max_total_bytes' in error.value.details[0]['message']

    # Metadata-only boundary checks exercise GB budgets without allocating GBs.
    inputs['scientific_files']=()
    inputs['scientific_materials']=(artifact('paper',2_000_000_000),)
    bound=preflight_operation(compiled,name='boundary',artifacts_by_port=inputs,instruction='Read',read_artifact=lambda ref: goal if ref==source.ref else forbidden(ref))
    assert next(v for v in bound.inputs if v.artifact_name=='paper').exposure=='file_reference'
    inputs['scientific_materials']=(artifact('paper',2_000_000_001),)
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(compiled,name='over',artifacts_by_port=inputs,instruction='Read',read_artifact=forbidden)
    assert error.value.reason_code=='input_item_too_large'
    bound=preflight_operation(compiled,name='configured',artifacts_by_port=inputs,instruction='Read',read_artifact=lambda ref: goal if ref==source.ref else forbidden(ref),
        material_settings=MaterialInputSettings(max_item_bytes=3_000_000_000,max_total_bytes=3_000_000_000))
    assert next(v for v in bound.inputs if v.artifact_name=='paper').exposure=='file_reference'


def test_configuration_owned_declarations_use_default_and_explicit_frozen_limits(catalog):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.invoke import material_input_limit
    compiled = catalog.operation('science.evidence.extract.v1')
    port = next(p for p in compiled.spec.inputs if p.name == 'source_material')
    assert port.max_item_bytes is None
    assert material_input_limit(port, MaterialInputSettings()) == 2_000_000_000
    attachment = next(p for p in compiled.spec.outputs if p.name == 'attachments')
    assert attachment.max_item_bytes is None and attachment.collection.max_total_bytes is None
    assert port.model_copy(update={'exposure': 'on_demand'}).issue() == 'port_size_invalid'
    assert attachment.model_copy(update={'agent_visible': True}).issue() == 'port_size_invalid'
    def bound(size, **kwargs):
        artifact = InvocationArtifact('paper', ArtifactRef(artifact_id='paper', kind='material',
            sha256='a' * 64, schema_id='opaque'), 'opaque', 'application/pdf', size)
        inputs = {p.name: () for p in compiled.spec.inputs}
        inputs['source_material'] = (artifact,)
        return preflight_operation(compiled, name='extract', artifacts_by_port=inputs,
            instruction='Read the exact material.', read_artifact=lambda _: pytest.fail('file must stay lazy'), **kwargs)
    assert bound(2_000_000_000).inputs[0].exposure == 'file_reference'
    with pytest.raises(OperationInvocationError, match='input_item_too_large'):
        bound(2_000_000_001)
    assert bound(2_000_000_001, material_settings=MaterialInputSettings(
        max_item_bytes=3_000_000_000, max_total_bytes=3_000_000_000)).inputs[0].exposure == 'file_reference'


def test_instance_material_settings_merge_and_freeze_without_changing_model(tmp_path):
    from scidiscovery.artifact_agent.service.runs import RunService
    from types import SimpleNamespace
    owner=SimpleNamespace(agent_settings=AgentSettings(input_materials=MaterialInputSettings(max_item_bytes=100)),
        scheduler_bindings=SimpleNamespace(agent_settings=lambda instance: {'settings':{'input_materials':{'max_item_bytes':200}}}))
    assert RunService.material_input_settings(owner).max_item_bytes==100
    merged=RunService.material_input_settings(owner,'instance')
    assert merged.max_item_bytes==200 and merged.transfer_chunk_bytes==1048576


def test_file_delivery_preserves_declared_limits_and_bounds_aggregate_inline(catalog):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.invoke import material_input_limit
    compiled=catalog.operation('science.experiment.v1')
    port=next(p for p in compiled.spec.inputs if p.name=='scientific_files')
    concrete=port.model_copy(update={'schema_id':'opaque','media_types':('image/png',),'max_item_bytes':100})
    assert concrete.issue() is None
    assert material_input_limit(concrete,MaterialInputSettings(max_item_bytes=500))==100
    assert material_input_limit(concrete,MaterialInputSettings(max_item_bytes=50))==50
    inputs={p.name:() for p in compiled.spec.inputs}
    def item(name, size, schema, media):
        return InvocationArtifact(name,ArtifactRef(artifact_id=name,kind='material',schema_id=schema,sha256='a'*64),schema,media,size)
    goal = _foundation()
    source = item('objective',len(goal),'scidiscovery.scientific-foundation.v1','application/json')
    source = replace(source, ref=source.ref.model_copy(update={'sha256': hashlib.sha256(goal).hexdigest()}))
    inputs['subject']=inputs['objective_source']=(source,)
    raw = b'x'*100
    inputs['scientific_materials']=tuple(replace(value, ref=value.ref.model_copy(update={'sha256':hashlib.sha256(raw).hexdigest()}))
        for value in (item(name,100,'opaque','text/csv') for name in ('a','b','c')))
    bound=preflight_operation(compiled,name='inline',artifacts_by_port=inputs,instruction='Read',
        material_settings=MaterialInputSettings(inline_max_bytes=100,inline_total_bytes=2*len(goal)+200),
        read_artifact=lambda ref: goal if ref==source.ref else raw)
    assert {x.artifact_name:x.exposure for x in bound.inputs if x.port_name=='scientific_materials'}=={
        'a':'on_demand','b':'on_demand','c':'file_reference'}
