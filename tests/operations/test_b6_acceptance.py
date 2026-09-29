"""Acceptance must never promote missing evidence, unsafe retries or cheaper failure."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import accept_b6 as suite
from scripts.b6_evidence import assess, compare, digest, usage_report, verdict, write


def test_config_covers_required_boundaries_without_new_instance_selection():
    config=suite.configuration(suite.DEFAULT)
    assert config['instance']=='b0a-calibration'
    assert set(config['cases'])=={'closeout','recovery','authority','helper','helper-crash','manual-known','auto-known',
        'manual-ambiguous','auto-ambiguous','managed','rollback'}
    assert 'automatic_recovery' in config['cases']['recovery']['requires']
    assert config['managed']['per_service_memory_bytes']*2<=2_000_000_000


def test_uncertain_attempt_cannot_be_resubmitted(tmp_path,monkeypatch):
    from scripts import run_tests as guard
    monkeypatch.setattr(guard,'SERIAL_LOCK',tmp_path/'serial.lock')
    target=tmp_path/'manual-known';target.mkdir()
    case={'scenario':'manual'}
    write(target/'acceptance-case.json',case)
    write(tmp_path/'manual-known.prepared.json',dict(case_digest=digest(case)))
    manifest={'harness_digest':suite.harness_digest()}
    calls=[]
    def interrupted(command,**kwargs):
        assert kwargs['pass_fds'] and '--lock-fd' in command
        calls.append(command)
        raise TimeoutError('supervisor_died_after_possible_submit')
    monkeypatch.setattr(suite.subprocess,'run',interrupted)
    with pytest.raises(TimeoutError):suite.run(tmp_path,manifest,'manual-known')
    with pytest.raises(FileExistsError):suite.run(tmp_path,manifest,'manual-known')
    assert len(calls)==1
    assert not (tmp_path/'manual-known.exit.json').exists()
    assert suite.result(tmp_path,{'config':{'cases':{'manual-known':{}}}},'manual-known')['attempt']=='outcome_unknown'


def test_busy_serial_lock_does_not_consume_attempt_or_launch(tmp_path,monkeypatch):
    import fcntl
    from scripts import run_tests as guard
    monkeypatch.setattr(guard,'SERIAL_LOCK',tmp_path/'serial.lock')
    target=tmp_path/'authority';target.mkdir()
    case={'scenario':'authority'}
    write(target/'acceptance-case.json',case)
    write(tmp_path/'authority.prepared.json',dict(case_digest=digest(case)))
    def unexpected(*args,**kwargs):raise AssertionError('must not launch')
    monkeypatch.setattr(suite.subprocess,'run',unexpected)
    with guard.SERIAL_LOCK.open('a') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            suite.run(tmp_path,{'harness_digest':suite.harness_digest()},'authority')
    assert not (tmp_path/'authority.attempt.json').exists()
    assert not (tmp_path/'authority.exit.json').exists()
    assert not list(target.glob('journey-*'))


def test_inherited_serial_lock_rejects_wrong_inode(tmp_path,monkeypatch):
    from scripts import run_tests as guard
    monkeypatch.setattr(guard,'SERIAL_LOCK',tmp_path/'serial.lock')
    guard.SERIAL_LOCK.touch()
    with (tmp_path/'wrong').open('a') as wrong:
        with pytest.raises(ValueError,match='descriptor_mismatch'):
            with guard.serial_lock(wrong.fileno()):
                pytest.fail('unrelated descriptor accepted')


def test_authority_replay_uses_recorded_proxy_and_requires_original_binding(tmp_path,monkeypatch):
    from scripts import acceptance_native_cases as native
    from scidiscovery.plugin_runtime import transport
    writer=dict(owner_session='sch_old',instance_id='i',host_json=json.dumps(
        dict(platform_session='actual-root',thread_id='actual-root')))
    monkeypatch.setattr(native,'rows',lambda *args:[{'instance_id':'i'}])
    requests=[]
    def forward(path,raw,**kwargs):
        requests.append(json.loads(raw));return {'result':{}}
    monkeypatch.setattr(transport,'forward_request',forward)
    native.recorded_control_call(tmp_path,writer,'instance_current',{})
    assert requests[0]['_scidiscovery_scheduler_proxy']=='sch_old'
    assert requests[0]['params']['_meta']['x-codex-turn-metadata']==dict(
        session_id='actual-root',thread_id='actual-root')
    monkeypatch.setattr(native,'rows',lambda *args:[{'instance_id':'another'}])
    with pytest.raises(ValueError,match='binding_changed'):
        native.recorded_control_call(tmp_path,writer,'instance_current',{})
    assert len(requests)==1


@pytest.mark.parametrize('reply,expected',[
    ({'error':{'code':-32000,'message':'SchedulerInstanceConflict: Scheduling is paused or owned by another session; use an explicit control command.'}},'passed'),
    ({'error':{'code':-32000,'message':'RootToolError: this MCP session is not bound'}},'not_observed'),
    ({'result':{}},'failed'),
])
def test_authority_only_qualifies_exact_control_denial(tmp_path,monkeypatch,reply,expected):
    from scripts import acceptance_native_cases as native
    writer=dict(owner_session='old',instance_id='i')
    current=dict(state='active',mode='interactive',host_json=None,owner_session='new')
    monkeypatch.setattr(native,'rows',lambda root,db,query,args:[current] if 'scheduler_progression' in query else [])
    monkeypatch.setattr(native,'recorded_control_call',lambda root,writer,name,args:
        {'result':{'structuredContent':{'state':'active'}}} if name=='instance_current' else reply)
    assert native.check_stale_writer(tmp_path,writer,tmp_path)==expected
    current['state']='paused'
    with pytest.raises(RuntimeError,match='takeover_not_established'):
        native.check_stale_writer(tmp_path,writer,tmp_path)


def test_authority_unbound_read_never_attempts_write(tmp_path,monkeypatch):
    from scripts import acceptance_native_cases as native
    monkeypatch.setattr(native,'rows',lambda *args:[dict(state='active',mode='interactive',host_json=None,owner_session='new')])
    calls=[]
    def unbound(root,writer,name,args):
        calls.append(name);return {'result':{'structuredContent':{'state':'unbound'}}}
    monkeypatch.setattr(native,'recorded_control_call',unbound)
    with pytest.raises(RuntimeError,match='read_binding_unavailable'):
        native.check_stale_writer(tmp_path,dict(instance_id='i',owner_session='old'),tmp_path)
    assert calls==['instance_current']


def test_mutated_case_is_rejected_before_any_attempt(tmp_path):
    target=tmp_path/'helper';target.mkdir()
    write(target/'acceptance-case.json',{'scenario':'helper','progression':{'max_attempts':100}})
    write(tmp_path/'helper.prepared.json',dict(case_digest='original'))
    with pytest.raises(ValueError,match='prepared_case_changed'):
        suite.run(tmp_path,{'harness_digest':suite.harness_digest()},'helper')
    assert not (tmp_path/'helper.attempt.json').exists()


def test_usage_keeps_unknown_threads_failures_and_missing_distinct_from_zero(tmp_path):
    write(tmp_path/'usage.json',{'root_thread':'r','threads':{'r':{'inputTokens':100,'cachedInputTokens':80,'outputTokens':5},
        'unattached':{'inputTokens':10,'cachedInputTokens':0,'outputTokens':2}}})
    report=usage_report(tmp_path,[{'thread_id':'w'}],[])
    assert report['groups']['root']['input_plus_output']==105
    assert report['groups']['worker']['input_plus_output'] is None
    assert report['groups']['unattributed']['input_plus_output']==12
    assert report['coverage']=='partial'
    write(tmp_path/'started-threads.json',['r','failed-before-usage'])
    report=usage_report(tmp_path,[],[])
    assert report['groups']['unattributed']['missing_threads']==1


def test_background_usage_deduplicates_received_notifications(tmp_path):
    write(tmp_path/'usage.json',{'root_thread':'setup','threads':{'worker':{'inputTokens':100,'cachedInputTokens':90,'outputTokens':5}}})
    write(tmp_path/'started-threads.json',[])
    progression={'checkpoint_json':json.dumps({'usage_records':{
        'worker':{'role':'worker','counted_tokens':{'input_tokens':100,'cached_input_tokens':90,'output_tokens':5},'has_gaps':False},
        'background':{'role':'root','counted_tokens':{'input_tokens':50,'cached_input_tokens':30,'output_tokens':5},'has_gaps':False}}})}
    report=usage_report(tmp_path,[{'thread_id':'worker'}],[],progression)
    assert report['groups']['worker']['input_plus_output']==105
    assert report['groups']['root']['input_plus_output']==55
    assert 'setup_root' not in report['groups']  # Setup used no model turn.
    assert report['coverage']=='observed'


def test_quality_review_binds_exact_sealed_evidence_and_each_criterion():
    evidence=[{'run_id':'r','reference':{'sha256':'exact'}}];rubric=['preserves ambiguity','integrates helper']
    review=dict(evidence_digest=digest(evidence),rubric=rubric,reviewer='maintainer',
        decisions=[dict(status='passed',reason='result.json conclusion paragraph 2') for _ in rubric])
    assert assess(evidence,rubric,review)=='passed'
    for change in ({'evidence_digest':'other'},{'rubric':['different']},{'decisions':[]},
                   {'decisions':[dict(status='passed',reason='') for _ in rubric]}):
        with pytest.raises(ValueError):assess(evidence,rubric,{**review,**change})


def test_cost_comparison_needs_same_conditions_quality_and_complete_usage():
    left=dict(status='passed',baseline_digest='b',conditions_digest='c',objective_digest='o',checks={'quality':'passed'},
        usage={'coverage':'observed','groups':{'root':{'coverage':'observed','input_plus_output':100}}})
    right=deepcopy(left);right['usage']['groups']['root']['input_plus_output']=80
    assert compare(left,right)['roles']['root']['input_plus_output_ratio']==.8
    for change in ({'status':'failed'},{'baseline_digest':'other'},{'checks':{'quality':'not_observed'}},
                   {'usage':{'coverage':'partial','groups':right['usage']['groups']}}):
        assert compare(left,{**right,**change})['roles']['root']['input_plus_output_ratio'] is None


def test_pause_does_not_pass_recovery_and_exit_zero_does_not_pass_quality():
    assert verdict({'pause':'passed'},['automatic_recovery'])=='not_observed'
    assert verdict({'sealed_delivery':'passed'},['sealed_delivery','quality'])=='not_observed'
    assert verdict({'quality':'passed','execution':'failed'},['quality','execution'])=='failed'


def test_native_cleanup_does_not_hide_original_failure(tmp_path):
    from scripts.acceptance_native_cases import NativeCaseJourney
    host=NativeCaseJourney.__new__(NativeCaseJourney);host.logdir=tmp_path/'logs'
    def uncertain():
        host.control_attempted=True
        raise TimeoutError('uncertain_submit')
    host.run_case=uncertain
    calls=[]
    def unavailable(name,args):
        calls.append((name,args));raise RuntimeError('disconnected')
    host.call=unavailable
    with pytest.raises(TimeoutError,match='uncertain_submit'):host.run_journey()
    assert calls==[('progression_command',{'command':'pause'})]
    assert json.loads((tmp_path/'closeout-pause.json').read_text())['status']=='unconfirmed'


def test_managed_launcher_is_bounded_and_only_targets_its_owned_unit(tmp_path,monkeypatch):
    from scripts import acceptance_managed as managed
    host=managed.ManagedJourney.__new__(managed.ManagedJourney)
    host.root=tmp_path;host.logdir=tmp_path;host.config={'project':str(tmp_path)};host.children=[]
    host.case_config={'managed':{'per_service_memory_bytes':750000000,'runtime_seconds':180}}
    calls=[]
    monkeypatch.setattr(managed,'command',lambda argv: calls.append(argv) or SimpleNamespace(returncode=0,stdout='',stderr=''))
    unit=host.launch(['python','-m','example'],'daemon')
    assert calls[0][:3]==['systemd-run','--user','--quiet']
    assert '--property=MemoryMax=750000000' in calls[0]
    assert '--property=RuntimeMaxSec=180' in calls[0]
    assert '--property=KillMode=control-group' in calls[0]
    unit.terminate()
    assert calls[-1]==['systemctl','--user','stop',unit.name]
    assert unit.name.startswith('scid-b6-')


@pytest.mark.parametrize('storage', ['text', 'blob'])
def test_report_requires_successful_supervisor_close_and_exact_content_review(tmp_path, storage):
    import hashlib
    import sqlite3
    from scripts.b6_evidence import sealed_outputs
    target=tmp_path/'manual-known';journey=target/'journey-1';journey.mkdir(parents=True)
    database=target/'state/database';database.mkdir(parents=True)
    payload=b'{"conclusion":"synthetic evidence"}'
    sha=hashlib.sha256(payload).hexdigest()
    cas=target/'state/artifacts/sha256'/sha[:2]/sha[2:];cas.parent.mkdir(parents=True);cas.write_bytes(payload)
    run=dict(run_id='r',state='completed',output_ref_json=json.dumps({'sha256':sha}))
    with sqlite3.connect(database/'runs.sqlite3') as db:
        db.executescript('CREATE TABLE runs(run_id,state,output_ref_json); '
            'CREATE TABLE worker_connections(run_id,thread_id); '
            'CREATE TABLE worker_participants(run_id,name,platform_session,owner_thread,thread_id,admitted_at,released_at);')
        db.execute('INSERT INTO runs VALUES(?,?,?)', (run['run_id'],run['state'],
            run['output_ref_json'].encode() if storage=='blob' else run['output_ref_json']))
    with sqlite3.connect(database/'scheduler-bindings.sqlite3') as db:
        db.executescript('CREATE TABLE scheduler_instances(instance_id,name); '
            'CREATE TABLE scheduler_progression(instance_id,checkpoint_json);')
    write(target/'acceptance-case.json',dict(baseline_digest='b',conditions_digest='c',text='synthetic'))
    write(journey/'before-runs.json',[])
    write(journey/'sealed-evidence.json',sealed_outputs(target,[run]))
    write(journey/'summary.json',dict(status='evidence_ready',checks={'sealed_delivery':'passed'}))
    config=suite.configuration(suite.DEFAULT);manifest={'config':config}
    assert suite.result(tmp_path,manifest,'manual-known')['status']=='not_observed'
    write(journey/'resource.json',dict(returncode=0,stop_reason='exited'))
    current=suite.result(tmp_path,manifest,'manual-known')
    review=current['review_template'];review['reviewer']='maintainer'
    review['decisions']=[dict(status='passed',reason='exact sealed paragraph') for _ in review['rubric']]
    write(tmp_path/'manual-known.review.json',review)
    assert suite.result(tmp_path,manifest,'manual-known')['status']=='not_observed'
    write(tmp_path/'manual-known.exit.json',dict(returncode=0))
    assert suite.result(tmp_path,manifest,'manual-known')['status']=='passed'
    write(tmp_path/'manual-known.exit.json',dict(returncode=1))
    assert suite.result(tmp_path,manifest,'manual-known')['status']=='failed'
    cas.write_bytes(b'changed')
    with pytest.raises(ValueError,match='sealed_bytes_mismatch'):
        suite.result(tmp_path,manifest,'manual-known')


def test_managed_cleanup_attempts_all_owned_units_after_one_failure(tmp_path):
    from scripts.acceptance_managed import ManagedJourney
    host=ManagedJourney.__new__(ManagedJourney);host.logdir=tmp_path/'logs'
    host.save_usage=lambda:None;host.events=SimpleNamespace(close=lambda:None)
    called=[]
    def broken():called.append('broken');raise RuntimeError('bus_lost')
    host.children=[SimpleNamespace(name='owned-a',terminate=lambda:called.append('a')),
        SimpleNamespace(name='owned-b',terminate=broken)]
    with pytest.raises(RuntimeError,match='managed_cleanup_unconfirmed'):host.close()
    assert called==['broken','a']


def test_original_a6_snapshot_without_progression_table_is_a_fresh_baseline(tmp_path):
    import sqlite3
    from scripts.b6_evidence import control_rows
    database=tmp_path/'state/database';database.mkdir(parents=True)
    with sqlite3.connect(database/'scheduler-bindings.sqlite3') as db:
        db.execute('CREATE TABLE scheduler_instances(instance_id,name)')
    assert control_rows(tmp_path)==[]
    with sqlite3.connect(database/'scheduler-bindings.sqlite3') as db:
        db.execute('CREATE TABLE scheduler_progression(broken)')
    with pytest.raises(sqlite3.OperationalError):
        control_rows(tmp_path,'SELECT state FROM scheduler_progression')


def test_blob_snapshot_roundtrips_without_changing_frozen_reference(tmp_path):
    import sqlite3
    from scripts.b6_evidence import run_snapshot, rows, read
    database=tmp_path/'state/database';database.mkdir(parents=True)
    original='{"artifact_id":"原件", "sha256":"exact"}'
    with sqlite3.connect(database/'runs.sqlite3') as db:
        db.execute('CREATE TABLE runs(run_id,state,output_ref_json)')
        db.execute('INSERT INTO runs VALUES(?,?,?)',('r','completed',original.encode('utf-8')))
    snapshot=run_snapshot(tmp_path)
    write(tmp_path/'before-runs.json',snapshot)
    assert read(tmp_path/'before-runs.json')==run_snapshot(tmp_path)
    assert snapshot[0]['output_ref_json']==original
    with sqlite3.connect(database/'runs.sqlite3') as db:
        assert db.execute('SELECT typeof(output_ref_json) FROM runs').fetchone()[0]=='blob'
        db.execute('UPDATE runs SET output_ref_json=?',(b'\xff',))
    with pytest.raises(UnicodeDecodeError):run_snapshot(tmp_path)
    assert rows(tmp_path,'runs','SELECT output_ref_json AS payload FROM runs')[0]['payload']==b'\xff'


@pytest.mark.parametrize('status',['completed','failed','interrupted','inProgress'])
def test_followup_checks_exact_old_turn_before_starting_new_case(status):
    from scripts.acceptance_native_cases import verify_prior_turns
    ref={'thread_id':'old-worker','turn_id':'old-turn'}
    def rpc(method,params):
        assert method=='thread/read' and params=={'threadId':'old-worker','includeTurns':True}
        return {'thread':{'id':'old-worker','turns':[{'id':'old-turn','status':status}]}}
    if status=='inProgress':
        with pytest.raises(RuntimeError,match='not_terminal'):verify_prior_turns(rpc,[ref])
    else:
        assert verify_prior_turns(rpc,[ref])==[{**ref,'status':status}]
    with pytest.raises(RuntimeError,match='not_found'):
        verify_prior_turns(rpc,[{**ref,'turn_id':'different-turn'}])
