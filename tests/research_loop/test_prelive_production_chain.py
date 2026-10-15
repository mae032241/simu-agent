"""Pre-live gate: latest frozen settings, real launcher/bwrap/controller/delivery, zero models."""
import hashlib
import os
import runpy
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scidiscovery.research_loop import audit_recovery,budget,contracts as c,delivery
from scidiscovery.research_loop.protocol import CURRENT
from execution_fixtures import execution_registry
from test_cov_delivery_lineage import managed_scene
from test_delivery import accepted,closeout_decision

REPO=Path(__file__).resolve().parents[2];GATE=REPO/'scripts/acceptance/prelive_gate.py'
LATEST=Path(os.environ.get('SCID_PRELIVE_SETTINGS',REPO.parents[1]/'.trial/rootless-task-unit-cov-20261014/instance/settings.json'))


def latest():
    if shutil.which('bwrap') is None:pytest.skip('Actual namespace unavailable')
    if not LATEST.is_file():pytest.skip('Latest frozen real-run settings unavailable')
    installed=subprocess.run([sys.executable,'-I','-c',f'from scidiscovery.research_loop.protocol import CURRENT;assert CURRENT=={CURRENT}'],capture_output=True)
    if installed.returncode:pytest.skip(f'Real installed CURRENT{CURRENT} interpreter required for the gate')
    launcher=LATEST.parent.parent/'launcher.json'
    if not Path(c.read(launcher)['task_python']).is_file():pytest.skip('Frozen task interpreter unavailable')
    return LATEST,launcher


def gate(tmp_path,settings,launcher,*extra):
    output=tmp_path/'verdict.json'
    result=subprocess.run([sys.executable,'-I',str(GATE),'--settings',str(settings),'--launcher-config',str(launcher),
        '--work',str(tmp_path/'scene'),'--output',str(output),*extra],capture_output=True,text=True,timeout=900)
    assert output.is_file(),(result.stdout[-2000:],result.stderr[-4000:])
    assert output.stat().st_size<=64*1024
    return result,c.read(output)


def originals(*paths):
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.mark.parametrize('comparison',[False,True])
@pytest.mark.parametrize('audit_status',[None,'audited','unknown'])
def test_fake_closeout_author_uses_current_delivery_contract(tmp_path,comparison,audit_status):
    """Exercise the actual gate native program even without an installed lane."""
    work=tmp_path/'work';(work/'inputs/parents').mkdir(parents=True)
    sources=dict(items=[dict(candidate_id=cid,availability='available',audit=dict(qualification='not_observed'))
        for cid in ('run-1','run-2')],omitted_count=0)
    closeout=dict(sources=sources)
    if comparison:
        closeout['comparison']=dict(default=dict(candidate_id='run-1'),
            rows=[dict(candidate_id=cid) for cid in ('run-1','run-2')])
    task=dict(role='A',closeout=closeout)
    if audit_status is not None:
        task['candidate_audit']=dict(candidate_id='run-1',status=audit_status,
            qualification='passed' if audit_status=='audited' else 'unknown')
    c.write(work/'science-task.json',task)
    schema=tmp_path/'science-result.schema.json';c.write(schema,c.result_schema('A',CURRENT,comparison))
    program=tmp_path/'fake-native.py';program.write_text(runpy.run_path(str(GATE))['FAKE_NATIVE'])
    output=work/'result.pending.json'
    result=subprocess.run([sys.executable,str(program),'-C',str(work),'--output-schema',str(schema),
        '--output-last-message',str(output)],input='',text=True,capture_output=True,timeout=10,
        env={**os.environ,'CODEX_HOME':str(tmp_path/'native-home')})
    if audit_status=='unknown':
        assert result.returncode!=0 and not output.exists()
        return
    assert result.returncode==0,result.stderr
    payload=c.science_payload(output,'A',CURRENT,comparison)
    assert payload['next_action']==('deliver' if audit_status=='audited' else 'audit')
    assert payload['candidate_recommendation']==(None if comparison and audit_status else
        'run-1' if comparison or audit_status else 'run-2')
    if comparison and audit_status:
        assert [row['candidate_id'] for row in payload['candidate_comparison']['rows'] if row['decision']=='keep']==['run-1']


def test_latest_frozen_settings_drive_full_chain_to_confirmed_delivery(tmp_path):
    settings,launcher=latest();before=originals(settings,launcher)
    result,verdict=gate(tmp_path,settings,launcher)
    assert result.returncode==0 and verdict['passed'],(verdict.get('error'),{k:v for k,v in verdict['checks'].items() if not v},verdict.get('reason'))
    assert verdict['status']=='delivery_confirmed' and verdict['models_called']==0
    assert verdict['adopted_defaults']==[]
    if c.read(settings).get('selection_policy') is None:
        assert verdict['checks']['selection_disabled_preserved']
    assert verdict['source_protocol']==verdict['current_protocol']==CURRENT and verdict['settings_differences']==[]
    assert [(row['role'],row['purpose'],row['route']) for row in verdict['chain']]==[('H',None,'experiment'),('W',None,'review'),
        ('A',None,'audit'),('A',None,'continue_w'),('W',None,'review'),('A',None,'finish'),('A','closeout','audit'),('A','closeout','deliver')]
    assert verdict['chain'][4]['fragments']==2 and verdict['usage']['unknown_steps']==[]
    assert originals(settings,launcher)==before


def test_failed_native_turn_is_a_retained_stop_without_seal_replay_or_delivery(tmp_path):
    # rootless-receipt-cov-20261014b: A005 turn.failed (service routing), reported as native_stopped.
    settings,launcher=latest()
    result,verdict=gate(tmp_path,settings,launcher,'--fault','a_turn_failed')
    assert result.returncode==0 and verdict['passed'],verdict['checks']
    assert verdict['status']=='native_stopped' and verdict['chain'][-1]=={'step':3,'role':'A','purpose':None,'sealed':False}


def test_polluted_public_harness_fails_before_any_scene_or_launch(tmp_path):
    # rootless-receipt-cov-20261014: a host smoke wrote harness/__pycache__ into the shared public copy.
    settings,launcher=latest();config=c.read(launcher)
    source=tmp_path/'source';(source/'instance').mkdir(parents=True)
    for name in ('settings.json','settings-identity.json'):shutil.copyfile(settings.parent/name,source/'instance'/name)
    public=tmp_path/'public'
    for name in c.read(Path(config['public_manifest']))['public_files_sha256']:
        (public/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path(config['public_root'])/name,public/name)
    (public/'environment/harness/__pycache__').mkdir();(public/'environment/harness/__pycache__/runner.cpython-312.pyc').write_bytes(b'host bytecode')
    c.write(source/'launcher.json',dict(config,public_root=str(public)))
    result,verdict=gate(tmp_path,source/'instance/settings.json',source/'launcher.json')
    assert result.returncode==1 and not verdict['passed']
    assert verdict['checks']['source_launcher_preflight'] is False
    assert verdict['preflight_error']=='public_directory_whitelist_changed'
    assert not (tmp_path/'scene/instance').exists() and 'status' not in verdict


def _leaf_files(root,phase,count=1):
    indexes=sorted((root/'host-delivery/leaf-output').glob(f'*-{phase}-*.json'))
    assert len(indexes)==count,indexes
    for path in indexes:
        index=c.read(path);stream=index['streams']['stderr']
        data=(path.parent/stream['path']).read_bytes()
        assert stream['sha256']==hashlib.sha256(data).hexdigest() and stream['kept_bytes']==len(data)
        yield index,data


@pytest.mark.parametrize('phase',['resolve','audit','promote','confirm'])
def test_isolated_leaf_failure_keeps_exact_traceback_as_host_only_output(tmp_path,monkeypatch,phase):
    # U4: cov_delivery leaf stderr was discarded, so the closeout traceback had to be inferred.
    root,nodes,first,*_=managed_scene(tmp_path)
    original=delivery._call
    def tamper(spec,request,seconds,**kwargs):
        if request['phase']==phase:
            protocol=Path(request['stage'])/'inputs/scid-current-protocol'
            protocol.chmod(0o600);protocol.write_bytes(protocol.read_bytes()+b'\n# altered frozen original\n')
        return original(spec,request,seconds,**kwargs)
    monkeypatch.setattr(delivery,'_call',tamper)
    if phase=='resolve':
        with pytest.raises(delivery.DeliveryUnresolved,match='delivery_resolver_unavailable'):
            delivery.freeze_sources(root,nodes)
    else:
        refs=delivery.freeze_sources(root,nodes)
        _,_,bound=closeout_decision(root,refs,recommendation=first['candidate_id'])
        submit=accepted(root,bound);result=delivery.invoke(root,submit,20)
        if phase=='confirm':
            budget.action_outcome(root,submit,result);result=delivery.invoke(root,accepted(root,bound,'confirm'),10)
        assert result['status']==('engineering_error' if phase=='audit' else 'unknown')
        keys={'status','operation_id','candidate_id','artifact_sha256','note','cleanup_confirmed'}
        if phase=='audit':
            assert result['failure_phase']=='audit'
            keys.add('failure_phase')
        else:
            assert 'failure_phase' not in result
        assert set(result)==keys
        assert 'Traceback' not in result['note']
    if phase=='audit':
        retries=list(audit_recovery.facts(root))
        assert len(retries)==1 and retries[0][1]['status']=='engineering_error'
        assert retries[0][1]['note']=='audit_process_failed'
    else:
        assert not list(audit_recovery.facts(root))
    for index,data in _leaf_files(root,phase,2 if phase=='audit' else 1):
        assert index['phase']==phase and index['returncode']!=0 and index['outcome']=='exited'
        assert b'Traceback' in data and b'Frozen current protocol original differs' in data
    for path in (root/'project').rglob('*'):
        if path.is_file():assert b'Frozen current protocol original differs' not in path.read_bytes()


def test_leaf_output_tail_is_bounded_and_does_not_change_the_reply(tmp_path):
    launcher=tmp_path/'noisy.py'
    launcher.write_text('import sys\nsys.stdin.read()\nsys.stderr.write("e"*100000+"END")\nprint("{}")\n')
    evidence=tmp_path/'host-delivery/leaf-output'
    value=delivery._call(dict(launcher_argv=[sys.executable,str(launcher)],adapter=str(launcher)),
        dict(phase='confirm',operation_id='a'*64),10,evidence=evidence)
    assert value=={}
    index=c.read(evidence/(('a'*64)+'-confirm-1.json'))
    stream=index['streams']['stderr']
    assert stream['total_bytes']==100003 and stream['kept_bytes']==delivery.MAX_LEAF_TAIL and stream['truncated']
    data=(evidence/stream['path']).read_bytes()
    assert len(data)==delivery.MAX_LEAF_TAIL and data.endswith(b'END')
    assert not (evidence/stream['path']).stat().st_mode&0o222
    assert delivery._call(dict(launcher_argv=[sys.executable,str(launcher)],adapter=str(launcher)),
        dict(phase='confirm',operation_id='a'*64),10,evidence=evidence)=={}
    assert (evidence/(('a'*64)+'-confirm-2.json')).is_file()
