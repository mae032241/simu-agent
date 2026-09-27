"""Isolated installed-package fixture; never opens production control state."""
import hashlib
import json
import os
import sys
from pathlib import Path

from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.operations.catalog import CompiledCatalog
from scidiscovery.operations.tooling import operation_agent_type, operation_worker_server_name
from scidiscovery.platforms.codex import initialize

base = Path(os.environ.get('SCID_SETTINGS_PROBE_ROOT', '/tmp/scid-execution-settings-p0'))
project = base / 'fixture'
project.mkdir(exist_ok=True)
runtime = open_runtime(project_root=project, state_root=base/'state', worker_backend='local')
operation = runtime.operation_catalog.operation('blind.csv.observe.v1')
action = sys.argv[1]
record_path = base/'fixture.json'
if action == 'prepare':
    instance = runtime.scheduler_bindings.create_instance(name=os.environ.get('SCID_SETTINGS_PROBE_INSTANCE','execution.settings.fixture'),
        title='Isolated configuration probe', objective='Verify model dispatch without real science.')
    item = runtime.artifacts.register(b'sample,value\na,1\nb,3\n', ArtifactRegistration(
        kind='fixture', schema_id='blind.opaque.v1', payload_schema_version=1,
        media_type='text/csv', creator=runtime.actor), idempotency_key='p0-source')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact',
        name='source', object_id=item.artifact_id)
    # Generate this exact compiled role via the installed platform generator.
    initialize(project_root=project, control_socket=base/'unused-root.sock',
        state_root=base/'state', local_workspace_root=project/'.scidiscovery-runs',
        python_executable=sys.executable, python_path=Path(os.environ.get('SCID_SETTINGS_PROBE_SITE',str(base/'site'))), worker_backend='local',
        operation_catalog=CompiledCatalog({operation.spec.operation_id: operation}))
    role = operation_agent_type(operation)
    profile = project/'.codex/agents'/f'{role}.toml'
    original = profile.read_bytes()
    (base/'fixed-role.toml').write_bytes(original)
    # P0 candidate differs only in removing the fixed model from the generated role.
    profile.write_text('\n'.join(line for line in original.decode().splitlines()
        if not line.startswith(('model = ', 'model_reasoning_effort = ')))+'\n')
    record = dict(instance_id=instance.instance_id, agent_type=role,
        operation_id=operation.spec.operation_id, operation_digest=operation.digest,
        server=operation_worker_server_name(operation), profile=str(profile),
        fixed_profile_sha256=hashlib.sha256(original).hexdigest(),
        dynamic_profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest())
    record_path.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
else:
    record = json.loads(record_path.read_text())
    root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
        instance=record['instance_id'], operation_catalog=runtime.operation_catalog))
    name = sys.argv[2]
    if action == 'settings':
        current=runtime.scheduler_bindings.agent_settings(record['instance_id'])
        runtime.scheduler_bindings.save_agent_settings(record['instance_id'],{'defaults':{'model':sys.argv[2],'reasoning_effort':sys.argv[3],'narrative_language':sys.argv[4]}}, expected_revision=current['revision'],maintenance=runtime.instance_maintenance)
        print(json.dumps({'settings_saved':True}))
    elif action == 'queue':
        request = dict(name=name, operation_id=operation.spec.operation_id,
            inputs=[dict(port='source_table',artifact_names=['source'])],
            instruction='Perform only the bounded CSV observation; this is a configuration fixture.')
        preflight = root.call_tool('operation_preflight',request)
        assert preflight['admissible'], preflight
        value = root.call_tool('operation_invoke',preflight.get('normalized_request',request))
        assert value['result']['state']=='queued',value
        print(json.dumps({'state':'queued','agent_type':record['agent_type'],'name':name}))
    elif action == 'fail':
        binding=runtime.scheduler_bindings.get_binding(instance=record['instance_id'],namespace='run',name=name)
        value=runtime.runs.fail(binding.object_id,reason=sys.argv[3] if len(sys.argv)>3 else 'P0 process tree terminated by memory guard before Worker assignment open')
        print(json.dumps({'state':value.state,'reason':value.reason}))
    elif action == 'status':
        value = root.call_tool('run_status',dict(name=name, output_paths=[]))
        Path(__file__).with_name(f'P0_{name}_STATUS.json').write_text(json.dumps(value,indent=2)+'\n')
        print(json.dumps({'state':value['state'],'agent_type':value.get('agent_type'),
            'output_artifact_name':value.get('output_artifact_name'),'reason':value.get('reason')}))
    else:
        raise ValueError('unknown action')
