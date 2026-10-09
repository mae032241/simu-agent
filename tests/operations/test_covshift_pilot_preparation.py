"""Paired public-view preparation and real owned MCP path boundaries, no models."""
import hashlib
import json

import pytest

from scripts import prepare_covshift_pilot as pilot
from tests.operations.test_covshift_local_preparation import prepared


def inputs(tmp_path, monkeypatch):
    old,_=prepared(tmp_path,monkeypatch)
    candidate=tmp_path/'candidate';(candidate/'build/wheelhouse').mkdir(parents=True)
    wheel=candidate/'build/wheelhouse/core.whl';wheel.write_bytes(b'fixture wheel identity')
    python=candidate/'bin/python';python.parent.mkdir();python.write_text('fixture identity, never executed')
    revision='e'*40
    (candidate/'candidate.json').write_text(json.dumps({'head':revision,'python':str(python),
        'profile':{'model':'gpt-5.6-sol','model_reasoning_effort':'high'},
        'worker_profile':{'model':'gpt-6.1-sol','model_reasoning_effort':'high'},
        'wheels':{'wheelhouse/core.whl':hashlib.sha256(wheel.read_bytes()).hexdigest()}}))
    env=tmp_path/'env';(env/'bin').mkdir(parents=True)
    (env/'bin/python').write_text('fixture identity, never executed');(env/'pyvenv.cfg').write_text('home=fixture')
    return old,candidate,env/'bin/python',revision


def test_two_arms_have_same_image_view_empty_outputs_and_frozen_shared_limits(tmp_path,monkeypatch):
    old,candidate,python,revision=inputs(tmp_path,monkeypatch)
    launch=pilot.prepare(tmp_path/'pair',old,candidate,python,revision)
    assert launch['limits']['per_mode_total_tokens']==200000
    assert launch['limits']['per_mode_wall_seconds']==1800
    assert launch['limits']['enforcement']=='not_verified'
    assert not launch['launch_ready'] and launch['instances_created']==launch['models_started']==0
    native=launch['arms']['native_goal'];scid=launch['arms']['scidiscovery']
    assert native['public_files_sha256']==scid['public_files_sha256']
    expected={'instruction.md','bin/exp',*(f'harness/{n}' for n in
        ('exp_cli.py','runner.py','train.csv','val.csv','meta.json'))}
    assert set(native['public_files_sha256'])==expected
    from pathlib import Path
    from scidiscovery.agent_execution_settings import load_settings
    assert launch['role_profile_version']==1
    for arm_name, arm in launch['arms'].items():
        project=Path(arm['project'])
        for name in ('workspace','runs','submission'):assert not list((project/name).iterdir())
        assert {str(p.relative_to(project)) for p in project.rglob('*') if p.is_file()}==expected
        assert arm['environment']['EXP_DEFAULT_SCRIPT']=='/workspace/train.py'
        assert arm['environment']['EXP_HARNESS']=='/opt/exp'
        assert '/opt/exp/exp_cli.py "$@"' in (project/'bin/exp').read_text()
        assert not arm['bindings_enforced']
        settings=load_settings(arm['agent_settings_proposal'])
        assert settings.debug_disable_task_network and not settings.progression.enabled
        assert settings.defaults.model=='gpt-6.1-sol'
        assert settings.progression.root_model==('gpt-5.6-sol' if arm_name=='scidiscovery' else 'gpt-6.1-sol')
        assert settings.defaults.reasoning_effort==settings.progression.root_reasoning_effort=='high'
        assert settings.helpers.profiles['lightweight'].model=='gpt-6.1-sol'
        assert launch['role_profiles'][arm_name]==pilot.role_profiles(arm_name)
    assert {k:v for k,v in native['environment'].items() if k!='PATH'}=={k:v for k,v in scid['environment'].items() if k!='PATH'}
    for arm in (native,scid):
        assert arm['environment']['PATH'].split(':')[0]==arm['project']+'/bin'
        assert not any(binding['target']=='/usr/local/bin/exp' for binding in arm['task_path_bindings'])


@pytest.mark.parametrize('change', ['wrong_commit','changed_wheel','changed_public','old_single_profile','wrong_worker_profile'])
def test_invalid_identity_fails_before_creating_pair(tmp_path,monkeypatch,change):
    old,candidate,python,revision=inputs(tmp_path,monkeypatch)
    if change=='wrong_commit':revision='a'*40
    elif change=='changed_wheel':(candidate/'build/wheelhouse/core.whl').write_bytes(b'changed')
    elif change=='changed_public':(old/'public/environment/harness/train.csv').write_bytes(b'changed')
    else:
        metadata=json.loads((candidate/'candidate.json').read_text())
        metadata['profile' if change=='old_single_profile' else 'worker_profile']['model']='gpt-6.1-sol' if change=='old_single_profile' else 'gpt-5.6-sol'
        (candidate/'candidate.json').write_text(json.dumps(metadata))
    output=tmp_path/'pair'
    with pytest.raises(ValueError):pilot.prepare(output,old,candidate,python,revision)
    assert not output.exists()


def test_owned_mcp_ingest_public_but_rejects_private_paths_without_registration(tmp_path):
    from tests.operations.test_local_worker_contracts import _system
    from tests.operations.test_unified_mcp import call,result
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    _,runtime,instance,root=_system(tmp_path)
    project=tmp_path/'project';private=tmp_path/'host-private';private.mkdir()
    secret=private/'canary.txt';secret.write_text('synthetic private, not benchmark answers')
    (project/'public.txt').write_text('public fixture')
    (project/'direct').symlink_to(secret)
    (project/'linked-parent').symlink_to(private,target_is_directory=True)
    gateway=UnifiedMCPRouter(root,worker_backend='local')
    accepted=result(call(gateway,'artifact_ingest_file',{'name':'public','relative_path':'public.txt'}))
    assert accepted['state']=='bound'
    ref=runtime.artifacts.get_by_id(root.facade._resolve('artifact','public')).ref
    assert runtime.artifacts.read(ref)==b'public fixture'
    before=len(runtime.scheduler_bindings.list(instance=instance.instance_id,namespace='artifact'))
    for index,path in enumerate((str(secret),'../host-private/canary.txt','direct','linked-parent/canary.txt')):
        reply=call(gateway,'artifact_ingest_file',{'name':'denied'+str(index),'relative_path':path})
        assert 'error' in reply,reply
        assert 'project-relative' in reply['error']['message'] or 'non-symlink' in reply['error']['message'] or 'outside project root' in reply['error']['message']
    assert len(runtime.scheduler_bindings.list(instance=instance.instance_id,namespace='artifact'))==before
    assert secret.read_text()=='synthetic private, not benchmark answers'
