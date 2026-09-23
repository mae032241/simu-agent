"""The installed Root contract and generated reading guide match their sources."""
import json
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_root import RunStatusInput


def test_installed_root_reading_contract_and_guide(installed_probe):
    guide = (Path(__file__).parents[2]/'roles/scheduler/results.md').read_text()
    schema = RunStatusInput.model_json_schema()
    installed_probe('core', f'''
import json, tempfile
from pathlib import Path
from scidiscovery.artifact_agent.interfaces.mcp_root import RunStatusInput
from scidiscovery.platforms import initialize_platform
from scidiscovery.platforms.scheduler_prompt import load_scheduler_guides
from scidiscovery.artifact_agent.service.result_materialization import materialize_analysis_handoff
value = dict(payload=dict(overall_verdict='inconclusive', summary='Bounded scientific finding.'))
original = json.dumps(value['payload'], sort_keys=True)
materialize_analysis_handoff(value)
assert json.dumps(value['payload'], sort_keys=True) == original
assert value['handoff']['verdict'] == 'inconclusive'
assert 'payload.summary' in value['handoff']['summary']
assert 'run_status.' not in value['handoff']['summary']
assert RunStatusInput.model_json_schema() == json.loads({json.dumps(schema)!r})
assert load_scheduler_guides()['results.md'] == {guide!r}
root = Path(tempfile.mkdtemp())
project = root/'project'
initialize_platform('codex', project, control_socket=root/'control.sock')
assert (project/'.codex/scidiscovery-guides/results.md').read_text() == {guide!r}
from types import SimpleNamespace
from unittest.mock import Mock
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root_run_routes import _output_index
def status(**args):
    assert args['output_mode'] == 'index' and args['output_paths'] is None
    return dict(name=args['name'], state='completed', output_index=_output_index(
        dict(artifact_name='original', kind='scientific', schema='fixture',
             payload=dict(summary='Do not expand this text.')), '', args['index_offset'], args['index_limit']))
facade = SimpleNamespace(runs=SimpleNamespace(), session_key=None,
    engineering_diagnostics=SimpleNamespace(capture=Mock()), _instance_id=lambda:'fixture', run_status=status)
router = MCPRouter(RootMCPRouter(facade), name='installed')
reply = router.handle(dict(jsonrpc='2.0', id=1, method='tools/call', params=dict(
    name='run_status', arguments=dict(name='report', output_mode='index', index_limit=1))))
directory = reply['result']['structuredContent']['output_index']
assert directory['children'][0]['pointer'] == '/summary'
assert 'Do not expand' not in json.dumps(directory)
assert len(json.dumps(directory, ensure_ascii=False).encode()) < 8192
''')
