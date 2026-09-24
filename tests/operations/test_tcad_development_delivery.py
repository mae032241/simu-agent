"""Current tool bytes cross a real sealed Artifact into an independent Run."""
import hashlib
import json
import stat
from pathlib import Path

import pytest
from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.project_packager import AttemptFile, DeckProjectDraft, project_debug_sha256
from tests.operations.test_tcad_initialization_outputs import setup_case, RAW
from tests.operations.test_l4_local_tcad import _invoke, LocalWorkerMCPRouter


def _proofs(tmp_path):
    worker, adapter, workspace = setup_case(tmp_path)
    for mode, name in [('preflight', 'syntax'), ('initialization', 'evolution')]:
        reply = worker.call_tool('worker_tcad_debug_run', dict(run_name=name, mode=mode,
            **({'output_names':['coarse_pre']} if mode=='initialization' else {})))
        assert reply['state']=='succeeded', reply
    return worker, adapter, workspace, reply


def test_delivery_seals_selected_bytes_and_restores_independent_reviewer(tmp_path):
    worker, adapter, workspace, reply = _proofs(tmp_path)
    assert reply['delivery_budget']['final_delivery_guaranteed'] is False
    assert 20*1024*1024 < adapter.jobs[-1].limits.max_output_bytes <= 64*1024*1024
    assert worker.call_tool('worker_submit_result', {})['state']=='completed'
    status=worker.runs.status(worker._run_id)
    sealed=json.loads(worker.runs.artifacts.read(status.output_ref))
    # Artifact service stores the exact project payload, not the author envelope.
    project=DeckProjectDraft.model_validate_json(canonical_json(sealed), strict=True)
    selected={f.relative_path:f.raw_bytes() for f in project.development_diagnostics}
    assert selected['reports/evolution/coarse_pre']==RAW
    assert not any('fine_post' in p for p in selected)
    assert {'reports/preflight.json','reports/initialization.json'} <= selected.keys()
    metadata=json.loads((workspace/'deck/project.json').read_bytes())
    assert 'development_diagnostics' not in metadata
    root=adapter.root
    name=root.call_tool('run_status', {'name':'initialization_outputs'})['output_artifact_name']
    _invoke(root,'independent_delivery_review','tcad.deck.review.v1',[
        {'port':'project','artifact_names':[name]},
        {'port':'execution_capability','artifact_names':['execution_capability']},
        {'port':'experiment_plan','artifact_names':['experiment_plan']}])
    compiled=adapter.catalog.operation('tcad.deck.review.v1')
    reviewer=LocalWorkerMCPRouter(worker.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened=reviewer.call_tool('worker_open_assignment',{})
    assert reviewer._run_id != worker._run_id
    deck=Path(opened['workspace_path'])/'deck'
    assert 'development_diagnostics' not in json.loads((deck/'project.json').read_bytes())
    for path,raw in selected.items():
        target=deck/path
        assert target.read_bytes()==raw
        assert not target.stat().st_mode & (stat.S_IWUSR|stat.S_IWGRP|stat.S_IWOTH)
    debug_hash=project_debug_sha256(project)
    altered=project.model_copy(update={'development_diagnostics':(AttemptFile(relative_path='reports/changed', content='changed'),)})
    assert project_debug_sha256(altered)==debug_hash
    assert canonical_json(altered.model_dump(mode='json')) != canonical_json(project.model_dump(mode='json'))
    legacy=project.model_copy(update={'development_diagnostics':()})
    assert 'development_diagnostics' not in legacy.model_dump(mode='json')
    assert project_debug_sha256(legacy)==debug_hash
    from tcad_artifact.project_packager import package_deck_project
    import tarfile
    packages=[package_deck_project(p,capability=adapter.capability,output_root=tmp_path/f'package-{i}')
              for i,p in enumerate((project,altered))]
    assert packages[0].project_sha256 != packages[1].project_sha256
    assert Path(packages[0].archive.local_path).read_bytes()==Path(packages[1].archive.local_path).read_bytes()
    with tarfile.open(packages[0].archive.local_path) as archive:
        assert all('reports/' not in name for name in archive.getnames())
    assert packages[0].job_spec.expected_outputs==packages[1].job_spec.expected_outputs



@pytest.mark.parametrize('attack',['output','report_and_output','missing','state_lost','other_run','authored'])
def test_finalizer_rejects_workspace_forgery_and_missing_trusted_state(tmp_path,attack):
    worker, adapter, workspace, _ = _proofs(tmp_path)
    raw=workspace/'deck/reports/evolution/coarse_pre'
    if attack in {'output','report_and_output'}:
        raw.chmod(0o600);raw.write_bytes(b'forged')
    if attack=='report_and_output':
        p=workspace/'deck/reports/diagnostic-evolution.json';p.chmod(0o600)
        obj=json.loads(p.read_bytes());obj['outputs'][0]['sha256']=hashlib.sha256(b'forged').hexdigest();p.write_bytes(canonical_json(obj))
    if attack=='missing':raw.unlink()
    state=worker._tool_state['worker_tcad_debug_run']
    if attack=='state_lost':state.clear()
    if attack=='other_run':
        value=json.loads(state['finalization_records']['initialization']);value['run_id']='another-run';state['finalization_records']['initialization']=canonical_json(value)
    if attack=='authored':
        p=workspace/'deck/project.json';p.chmod(0o600);value=json.loads(p.read_bytes());value['development_diagnostics']=[];p.write_bytes(canonical_json(value))
    result=worker.call_tool('worker_submit_result',{})
    assert result['state']=='rejected',result
    assert result['diagnostics']


@pytest.mark.parametrize('raw', [b'time,state\n0,1\n1,1\n', b'time,state\n0,1\n1,2\n'])
def test_control_preserves_both_dynamic_observations_without_scientific_gate(tmp_path,monkeypatch,raw):
    import tests.operations.test_tcad_initialization_outputs as fixture
    monkeypatch.setattr(fixture,'RAW',raw)
    worker, adapter, workspace, _ = _proofs(tmp_path)
    assert worker.call_tool('worker_submit_result',{})['state']=='completed'
    project=json.loads(worker.runs.artifacts.read(worker.runs.status(worker._run_id).output_ref))
    item=next(x for x in project['development_diagnostics'] if x['relative_path']=='reports/evolution/coarse_pre')
    assert AttemptFile.model_validate(item).raw_bytes()==raw


def test_fixed_known_encoded_bytes_refuse_before_reservation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tcad_artifact import local_debug_service
    from tcad_artifact.debug_contract import TCADDebugError
    worker, adapter, workspace = setup_case(tmp_path)
    worker.runs.validate_candidate(worker._run_id)
    output = worker.runs.backend.open(worker._run_id).output_directory
    envelope=json.loads((output/'result.json').read_bytes())
    project=canonical_json(envelope['payload'])
    reserve = 256 * 1024 + 1024
    monkeypatch.setattr(local_debug_service, 'DEVELOPMENT_ARTIFACT_LIMIT_BYTES',
                        len(canonical_json(envelope)) + reserve + 128)
    envelope['handoff']['summary']+='\x00'*25
    (output/'result.json').chmod(0o600)
    (output/'result.json').write_bytes(canonical_json(envelope))
    # No handoff: use the fixed encoded candidate, including escaping inflation.
    (workspace/'deck/handoff.json').unlink()
    context=SimpleNamespace(state={},workspace=workspace,output_directory=output)
    with pytest.raises(TCADDebugError,match='before startup.*known_bytes=.*remaining_bytes='):
        local_debug_service._delivery_budget(context,project,'initialization',('coarse_pre',))
    assert adapter.jobs==[] and context.state=={}


def test_failed_diagnostic_is_not_charged_as_adopted_attachment(tmp_path):
    from types import SimpleNamespace
    from tcad_artifact.local_debug_service import _delivery_budget
    worker, adapter, workspace = setup_case(tmp_path)
    worker.runs.validate_candidate(worker._run_id)
    output=worker.runs.backend.open(worker._run_id).output_directory
    project=canonical_json(json.loads((output/'result.json').read_bytes())['payload'])
    state={'finalization_records':{'preflight':canonical_json({'mode':'preflight',
        'collection_complete':False,'project_sha256':project_debug_sha256(DeckProjectDraft.model_validate_json(project)),
        'files':[{'relative_path':'reports/not-adopted-and-missing'}]})}}
    context=SimpleNamespace(state=state,workspace=workspace,output_directory=output)
    budget=_delivery_budget(context,project,'initialization',('coarse_pre',))
    assert budget['effective_collection_bytes']>0 and adapter.jobs==[]


def test_initialization_budget_can_collect_first_hold_state_sequence(tmp_path):
    from types import SimpleNamespace
    from tcad_artifact.debug_contract import DEVELOPMENT_ARTIFACT_LIMIT_BYTES
    from tcad_artifact.local_debug_service import _delivery_budget
    worker, adapter, workspace = setup_case(tmp_path)
    worker.runs.validate_candidate(worker._run_id)
    output = worker.runs.backend.open(worker._run_id).output_directory
    payload = json.loads((output/'result.json').read_bytes())['payload']
    payload['resource_limits']['max_output_bytes'] = DEVELOPMENT_ARTIFACT_LIMIT_BYTES
    project = canonical_json(payload)
    context = SimpleNamespace(state={}, workspace=workspace, output_directory=output)
    names = tuple(f'state_{index}' for index in range(48))
    budget = _delivery_budget(context, project, 'initialization', names)
    assert budget['envelope_limit_bytes'] == DEVELOPMENT_ARTIFACT_LIMIT_BYTES
    assert budget['effective_collection_bytes'] > 20 * 1024 * 1024
    assert adapter.jobs == []


def test_large_initialization_state_sequence_is_sealed_for_review(tmp_path, monkeypatch):
    import tests.operations.test_tcad_initialization_outputs as fixture
    monkeypatch.setattr(fixture, 'RAW', b'\xff' * 400_000)
    worker, adapter, workspace = setup_case(tmp_path)
    names = [f'state_{index}' for index in range(48)]
    declarations_path = workspace/'deck/declarations.json'
    declarations = json.loads(declarations_path.read_bytes())
    declarations['raw_outputs'] = [
        {'name': name, 'relative_path': f'results/{name}.tdr',
         'media_type': 'application/octet-stream'} for name in names
    ]
    declarations_path.write_bytes(canonical_json(declarations))
    assert worker.call_tool('worker_tcad_debug_run', {'run_name': 'syntax', 'mode': 'preflight'})['state'] == 'succeeded'
    result = worker.call_tool('worker_tcad_debug_run', {
        'run_name': 'first_hold', 'mode': 'initialization', 'output_names': names,
    })
    assert result['state'] == 'succeeded', result
    assert result['output_count'] == len(names)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    sealed = worker.runs.artifacts.read(worker.runs.status(worker._run_id).output_ref)
    assert len(sealed) > 8 * 1024 * 1024
    project = DeckProjectDraft.model_validate_json(sealed, strict=True)
    selected = {item.relative_path: item.raw_bytes() for item in project.development_diagnostics}
    assert len([name for name in selected if name.startswith('reports/first_hold/')]) == len(names)
    assert selected['reports/first_hold/state_47'] == fixture.RAW
    review = adapter.catalog.operation('tcad.deck.review.v1')
    assert next(port for port in review.spec.inputs if port.name == 'project').max_item_bytes >= len(sealed)
    root = adapter.root
    project_name = root.call_tool('run_status', {'name': 'initialization_outputs'})['output_artifact_name']
    _invoke(root, 'large_state_review', 'tcad.deck.review.v1', [
        {'port': 'project', 'artifact_names': [project_name]},
        {'port': 'execution_capability', 'artifact_names': ['execution_capability']},
        {'port': 'experiment_plan', 'artifact_names': ['experiment_plan']},
    ])
    reviewer = LocalWorkerMCPRouter(worker.runs, operation_id=review.spec.operation_id,
                                    operation_digest=review.digest)
    opened = reviewer.call_tool('worker_open_assignment', {})
    assert (Path(opened['workspace_path'])/'deck/reports/first_hold/state_47').read_bytes() == fixture.RAW


def test_author_revision_navigates_readonly_originals_at_restored_history_paths(tmp_path):
    from tcad_artifact.project_packager import DeckReviewReport
    worker, adapter, workspace, _ = _proofs(tmp_path)
    assert worker.call_tool('worker_submit_result', {})['state']=='completed'
    project=DeckProjectDraft.model_validate_json(worker.runs.artifacts.read(worker.runs.status(worker._run_id).output_ref))
    root=adapter.root
    project_name=root.call_tool('run_status',{'name':'initialization_outputs'})['output_artifact_name']
    _invoke(root,'revision_request','tcad.deck.review.v1',[
        {'port':'project','artifact_names':[project_name]},
        {'port':'execution_capability','artifact_names':['execution_capability']},
        {'port':'experiment_plan','artifact_names':['experiment_plan']}])
    op=adapter.catalog.operation('tcad.deck.review.v1')
    reviewer=LocalWorkerMCPRouter(worker.runs,operation_id=op.spec.operation_id,operation_digest=op.digest)
    opened=reviewer.call_tool('worker_open_assignment',{})
    review=DeckReviewReport(verdict='revise',capability_sha256=adapter.capability.canonical_sha256(),
        summary='Revise the bounded diagnostic source correspondence.',
        rationale='The fixture requires one controlled source revision.',
        physical_fidelity='unknown',implementation_fidelity='fail',numerical_protocol_fidelity='unknown',execution_ready=False)
    Path(opened['output_directory'],'result.json').write_bytes(canonical_json({
        'schema_version':1,'handoff':{'verdict':'revise','summary':review.summary},'payload':review.model_dump(mode='json')}))
    assert reviewer.call_tool('worker_submit_result',{})['state']=='completed'
    change_name=root.call_tool('run_status',{'name':'revision_request'})['output_artifact_name']
    _invoke(root,'revised_author','tcad.deck.author.revise.v1',[
        {'port':'prior_project','artifact_names':[project_name]},
        {'port':'change_request','artifact_names':[change_name]},
        {'port':'execution_capability','artifact_names':['execution_capability']},
        {'port':'experiment_plan','artifact_names':['experiment_plan']}])
    op=adapter.catalog.operation('tcad.deck.author.revise.v1')
    reviser=LocalWorkerMCPRouter(worker.runs,operation_id=op.spec.operation_id,operation_digest=op.digest,tool_services=worker.tool_services)
    revised=reviser.call_tool('worker_open_assignment',{})
    root_path=Path(revised['workspace_path'])
    manifest=json.loads((root_path/'domain-workspace.json').read_bytes())
    paths=manifest['manifest']['development_diagnostic_paths']
    assert len(paths)==len(project.development_diagnostics)
    for path,item in zip(paths,project.development_diagnostics):
        original=root_path/path
        assert path.startswith('deck/reports/history/')
        assert original.read_bytes()==item.raw_bytes()
        assert not original.stat().st_mode & (stat.S_IWUSR|stat.S_IWGRP|stat.S_IWOTH)
    # Creating this Run's new proof cannot redirect the historical navigation.
    current=root_path/'deck/reports/initialization.json'
    assert not current.exists()
    current.write_bytes(b'{"new_current_report":true}')
    for path,item in zip(paths,project.development_diagnostics):
        assert (root_path/path).read_bytes()==item.raw_bytes()
    assert 'deck/reports/initialization.json' not in paths
