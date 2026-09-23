"""Initialization selections traverse MCP, packaging, runner collection and readable files."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge
from tcad_artifact.execution_control import TCADJobSpec
from tcad_artifact import remote_runner_py36 as runner
from tests.operations.test_l4_local_tcad import _system, _invoke, _project, _write_author_workspace, _write_sprocess_workspace, _debug_worker
from tests.operations.test_log_preservation import _descriptor

RAW = b'"Fig4C"\n0 1.692157e19\n1 1.692157e19\n'


class RunnerFixture:
    """No solver: exercise the production collector over controlled fixture bytes."""
    def __init__(self, directory, capability, failure=None):
        self.directory = directory
        self.capability = capability
        self.failure = failure
        self.jobs = []

    def capabilities(self):
        return (SimpleNamespace(schema_id="tcad.solver-capability.v2",
            content=canonical_json(self.capability.public_snapshot().model_dump(mode="json"))),)

    def prepare_development_debug(self, *, job_spec_file, archive, exchange_directory):
        return job_spec_file

    def submit(self, submission):
        self.jobs.append(TCADJobSpec.model_validate_json(Path(submission.local_path).read_bytes(), strict=True))
        return str(len(self.jobs)), "succeeded"

    def collect_with_budget(self, run_id, *, context):
        context.remaining_seconds()
        job = self.jobs[int(run_id)-1]
        work = self.directory / run_id
        work.mkdir(parents=True)
        for item in job.expected_outputs:
            if self.failure in {"missing", "timeout"}:
                continue
            path = work / item.relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"" if self.failure == "empty" else b"x"*(item.max_bytes+1) if self.failure == "oversize" else RAW)
        errors = []
        records = runner._collect_expected(str(work), [x.model_dump(mode="json") for x in job.expected_outputs],
            job.limits.model_dump(mode="json"), errors=errors)
        log = work / 'runner.log'; log.write_text('Initialization finished\n')
        manifest = work / 'manifest.json'; manifest.write_text(json.dumps({
            'terminal_state': 'failed' if errors else 'succeeded', 'exit_code':124 if self.failure == 'timeout' else 0,
            'error': '; '.join(errors), 'outputs':records}))
        return (_descriptor('tcad_log', log, 'text/plain'), _descriptor('tcad_manifest', manifest, 'application/json'),
            *(_descriptor(x['name'], work/x['relative_path'], x['media_type']) for x in records))


def setup_case(tmp_path, *, solver='sprocess', failure=None, output_name='coarse_pre'):
    catalog, runtime, root, capability = _system(tmp_path, solver_kind=solver)
    _invoke(root, 'initialization_outputs', 'tcad.deck.author.initial.v1', [
        {'port':'execution_capability', 'artifact_names':['execution_capability']},
        {'port':'experiment_plan', 'artifact_names':['experiment_plan']}])
    transport = RunnerFixture(tmp_path/'runner', capability, failure)
    transport.root, transport.catalog = root, catalog
    bridge = TCADDevelopmentDebugBridge(transport)
    worker = _debug_worker(catalog, runtime, bridge, tmp_path/'exchange')
    opened = worker.call_tool('worker_open_assignment', {})
    project = _project(capability)
    first = project.expected_outputs[0].model_copy(update={'name':output_name,'relative_path':'results/coarse_pre.plx','media_type':'text/plain'})
    later = first.model_copy(update={'name':'fine_post', 'relative_path':'results/fine_post.plx'})
    project = project.model_copy(update={'solver_kind':solver, 'development_initialization_entrypoint':'main.cmd', 'expected_outputs':(first,later)})
    if solver == 'sprocess':
        _write_sprocess_workspace(opened)
        path = Path(opened['workspace_path'])/'deck/declarations.json'
        declarations = json.loads(path.read_bytes())
        declarations['raw_outputs'] = [dict(name=x.name,relative_path=x.relative_path,media_type=x.media_type) for x in (first,later)]
        path.write_bytes(canonical_json(declarations))
    else:
        _write_author_workspace(opened, project)
    return worker, transport, Path(opened['workspace_path'])


@pytest.mark.parametrize('solver', ['sprocess','sdevice'])
def test_initialization_selected_file_is_readable_without_expanding_poll(tmp_path, solver):
    worker, runner_fixture, workspace = setup_case(tmp_path, solver=solver)
    schema = next(x for x in worker.list_tools() if x['name']=='worker_tcad_debug_run')['inputSchema']
    assert 'output_names' in schema['properties']
    request = dict(run_name='init', mode='initialization', output_names=['coarse_pre'])
    reply = worker.call_tool('worker_tcad_debug_run', request)
    assert reply['state']=='succeeded', reply
    assert reply['output_count']==1
    assert 'outputs' not in reply and 'Fig4C' not in json.dumps(reply)
    detail = json.loads(Path(reply['details_path']).read_bytes())
    assert detail['scientific_claim_admissible'] is False
    item = detail['outputs'][0]
    assert item['name']=='coarse_pre' and (workspace/item['relative_path']).read_bytes()==RAW
    assert (workspace/item['relative_path']).stat().st_mode & 0o222 == 0
    assert [x.name for x in runner_fixture.jobs[0].expected_outputs]==['coarse_pre']
    assert runner_fixture.jobs[0].execution_purpose=='development_debug'
    assert json.loads((workspace/'deck/reports/initialization.json').read_bytes())['qualified']
    polled = worker.call_tool('worker_tcad_debug_run', dict(run_name='init',mode='initialization'))
    assert polled['output_count']==1 and len(runner_fixture.jobs)==1
    changed = worker.call_tool('worker_tcad_debug_run', dict(request,output_names=['fine_post']))
    assert changed['state']=='rejected' and len(runner_fixture.jobs)==1


@pytest.mark.parametrize('failure', ['missing','empty','oversize'])
def test_initialization_missing_data_cannot_qualify(tmp_path, failure):
    worker, transport, workspace = setup_case(tmp_path, failure=failure)
    result = worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode='initialization',output_names=['coarse_pre']))
    assert result['missing_outputs']==['coarse_pre'], result
    assert result['diagnostic_layer']=='collection'
    report = json.loads((workspace/'deck/reports/initialization.json').read_bytes())
    assert not report['qualified'] and report['diagnostic_layer']=='collection'
    worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode='initialization'))
    assert len(transport.jobs)==1


@pytest.mark.parametrize('mode,names', [('preflight',['coarse_pre']),('smoke',['coarse_pre']),('initialization',['undeclared']),('initialization',['../outside'])])
def test_invalid_selection_never_starts_solver(tmp_path, mode, names):
    worker, transport, workspace = setup_case(tmp_path)
    reply = worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode=mode,output_names=names))
    assert reply['state']=='rejected', reply
    assert not transport.jobs


def test_legacy_initialization_stays_log_only(tmp_path):
    worker, transport, workspace = setup_case(tmp_path)
    result = worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode='initialization'))
    assert result['state']=='succeeded' and result['output_count']==0
    assert not transport.jobs[0].expected_outputs


def test_public_output_symlink_cannot_write_outside_workspace(tmp_path):
    worker, transport, workspace = setup_case(tmp_path)
    outside = tmp_path/'outside';outside.mkdir()
    (workspace/'deck/reports/init').symlink_to(outside, target_is_directory=True)
    result = worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode='initialization',output_names=['coarse_pre']))
    assert result['state']=='rejected', result
    assert not list(outside.iterdir())


def test_missing_output_does_not_hide_solver_timeout(tmp_path):
    worker, _, workspace = setup_case(tmp_path, failure='timeout')
    result = worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode='initialization',output_names=['coarse_pre']))
    assert result['missing_outputs']==['coarse_pre']
    assert result['exit_code']==124 and result['diagnostic_layer']=='resource_limit'
    assert not json.loads((workspace/'deck/reports/initialization.json').read_bytes())['qualified']


def test_declared_nested_output_name_is_readable(tmp_path):
    worker, _, workspace = setup_case(tmp_path, solver='sdevice', output_name='coarse/pre')
    result = worker.call_tool('worker_tcad_debug_run',dict(run_name='init',mode='initialization',output_names=['coarse/pre']))
    assert result['state']=='succeeded', result
    detail = json.loads(Path(result['details_path']).read_bytes())
    assert (workspace/detail['outputs'][0]['relative_path']).read_bytes()==RAW
