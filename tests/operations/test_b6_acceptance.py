"""Acceptance must never promote missing evidence, unsafe retries or cheaper failure."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import accept_b6 as suite
from scripts.b6_evidence import assess, compare, digest, usage_report, verdict, write, token_totals


def _s0_fixture(root, topic='negative', count=2, adopted=True):
    """Real payload/receipt columns, with synthetic native observations only."""
    import hashlib
    import sqlite3
    from scripts import s0_scoring as scorer
    from scripts.b6_evidence import sealed_outputs
    case = 'manual-'+topic+'-1'
    target = root/case
    journey = target/'journey-1'
    journey.mkdir(parents=True)
    database = target/'state/database'
    database.mkdir(parents=True)

    def store(body, schema=scorer.REPORT):
        raw = json.dumps(body, ensure_ascii=False).encode()
        sha = hashlib.sha256(raw).hexdigest()
        path = target/'state/artifacts/sha256'/sha[:2]/sha[2:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return dict(artifact_id='a-'+sha[:12], sha256=sha, kind='report', schema_id=schema)

    stage = store(dict(stage='validity', conclusion='修正后采用合法联合参数 a=2.1,b=0.9,c=0.12；存活不等于证明。',
        limitations=['误差硬界，参数相关'], remaining_question='追加观测', materials=[]), 'scidiscovery.tool-evidence.v1')
    receipt = dict(alias='tool_evidence_001', artifact_ref=stage, metadata=dict(kind='experiment_stage', stage='validity'),
        tool_name='worker_experiment_stage')
    runs = []
    with sqlite3.connect(database/'runs.sqlite3') as db:
        db.executescript('CREATE TABLE runs(run_id,state,output_ref_json,operation_id,request_digest,inputs_json,created_at,completed_at,output_binding_name); '
            'CREATE TABLE worker_connections(run_id,thread_id); '
            'CREATE TABLE worker_participants(run_id,name,platform_session,owner_thread,thread_id,admitted_at,released_at); '
            'CREATE TABLE run_tool_evidence(run_id,ordinal,record_json);')
        for i in range(count):
            final = i == count-1
            body = dict(summary=('c 不可辨识，a=2,b=1；候选 baseline 模型需要新 x 和误差模型。' if topic == 'stagnation' else
                'L 不可行：最小 SSR=0.3>0.04。Q 可行示例 a=2.1,b=0.9,c=0.12，精确插值 c=1/6 唯一，机制不唯一。')
                if final else '此前错误：a=9,b=8,c=0，L 唯一正确。', outcome='inconclusive',
                limitations=['无误差模型或重复测量' if topic == 'stagnation' else 'Q 存活不等于证明；不能任意组合坐标范围'],
                remaining_question='建议追加 x=4 并声明误差界。', adopted_stages=['tool_evidence_001'] if final else [])
            ref = store(body)
            run = dict(run_id=f'r{i+1}', state='completed', output_ref_json=json.dumps(ref))
            inputs = [dict(producer_run_id=runs[0]['run_id'], artifact_ref=json.loads(runs[0]['output_ref_json']),
                port_name='subject', source_name='earlier')] if i else []
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)', (*run.values(), 'science.experiment.v1', f'request-{i}',
                json.dumps(inputs).encode(), f'2026-09-30T00:0{i}:00Z', f'2026-09-30T00:0{i}:50Z', f'output-{i}'))
            runs.append(run)
        db.execute('INSERT INTO run_tool_evidence VALUES(?,?,?)', (runs[-1]['run_id'], 1, json.dumps(receipt).encode()))
    with sqlite3.connect(database/'scheduler-bindings.sqlite3') as db:
        db.executescript('CREATE TABLE scheduler_instances(instance_id,name); CREATE TABLE scheduler_progression(instance_id,checkpoint_json);')
    config = suite.configuration(suite.SCRIPTS/'acceptance/scientific_progress.json')
    config['cases'] = {case:config['cases'][case]}
    manifest = dict(config=config)
    write(root/'suite.json', manifest)
    write(target/'acceptance-case.json', dict(baseline_digest='b', conditions_digest='c', text=config['objectives'][topic]))
    write(journey/'before-runs.json', [])
    sealed = sealed_outputs(target, runs)
    write(journey/'sealed-evidence.json', sealed)
    write(journey/'summary.json', dict(status='evidence_ready', checks={'sealed_delivery':'passed'}))
    write(journey/'resource.json', dict(returncode=0, stop_reason='exited'))
    write(root/(case+'.exit.json'), dict(returncode=0))
    write(journey/'usage.json', dict(root_thread='actual-root', threads={'actual-root':dict(inputTokens=10,cachedInputTokens=0,outputTokens=1)}))
    logs = journey/'fixture-logs'
    logs.mkdir()
    message = '最终采用 output-'+str(count-1)+' 的修正结论。候选 baseline 科学词保留。'
    events = []
    for state in ('running', 'completed'):
        events.append(dict(method='item/completed', params=dict(threadId='actual-root', item=dict(type='mcpToolCall',
            tool='scid_call', status='completed', arguments=dict(name='run_status', arguments={'name':'task-final'}),
            result={'structuredContent':dict(name='task-final', state=state,
                output_artifact_name=f'output-{count-1}' if state == 'completed' else None)}))))
    events.append(dict(method='item/completed', params=dict(threadId='actual-root', item=dict(type='agentMessage', text=message))))
    (logs/'events.log').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in events))
    if adopted:
        record = scorer.root_records(journey, None)[-1]
        write(root/(case+'.adoption.json'), dict(evidence_digest=digest(sealed), run_ids=[runs[-1]['run_id']],
            root_record_digest=record['record_digest'], root_excerpt=message, reason='人工依据 Root 明确最终采用的原句定位。'))
    return manifest, case, target, journey


def _s0_review(report, scores=(2,2,2,2,2)):
    review = deepcopy(report['review_template'])
    review['reviewer'] = 'independent-local-reviewer'
    for decision, score in zip(review['decisions'], scores):
        decision.update(score=score, status='not_observed' if score is None else 'passed' if score else 'failed',
            reason='依据确切最终封存字段和 Root 记录；局部人工评审。')
    return review


def test_s0_parameter_roles_accept_joint_example_and_distinguish_ranges():
    from scripts.s0_scoring import parameter_predicate as check
    assert check('feasible_example', dict(a=2.1,b=.9,c=.12))['holds']
    assert check('exact_interpolation', dict(a=2,b=1,c=1/6))['holds']
    assert not check('exact_interpolation', dict(a=2.1,b=.9,c=.12))['holds']
    assert not check('feasible_example', dict(a=2.1,b=1.1,c=.12))['holds']
    assert not check('complete_coordinate_projections', dict(a=[1.9,2.1],b=[.9,1.1],c=[.16,.17]))['holds']
    assert check('conservative_envelope', dict(a=[1,3],b=[0,2],c=[0,1]))['holds']
    with pytest.raises(ValueError, match='finite_numeric'):
        check('feasible_example', dict(a=2,b=1,c=float('nan')))


def test_s0_text_numbers_only_locate_and_final_correction_uses_adopted_stage(tmp_path):
    from scripts import s0_scoring as scorer
    manifest, case, _, _ = _s0_fixture(tmp_path)
    report = suite.result(tmp_path, manifest, case)
    assert report['auto_checks']['verdict'] == 'not_observed'
    assert not report['auto_checks']['blocking_failures']
    assert all(v['status'] not in {'passed','failed'} for v in report['auto_checks']['checks'].values())
    hits = report['auto_checks']['checks']['N-B3']['evidence']
    assert any(h['run_id']=='r1' and not h['final_adopted'] for h in hits)
    assert any(h['stage_alias']=='tool_evidence_001' and h['path']=='/conclusion' for h in hits)
    review = _s0_review(report)
    assert assess(report['scoring_evidence'], review['rubric'], review, objective='negative') == 'passed'
    qualification = scorer.assess_domains(report['scoring_evidence'], review, 'negative')
    assert qualification['science'] == qualification['overall'] == 'passed'


def test_s0_single_ls_residual_and_coincidental_numbers_never_exclude_l(tmp_path):
    from scripts.s0_scoring import auto_checks
    manifest, case, _, _ = _s0_fixture(tmp_path)
    evidence = deepcopy(suite.result(tmp_path, manifest, case)['scoring_evidence'])
    evidence['outputs'][-1]['fields']['/summary'] = '某次最小二乘残差0.4>0.1；另列数字0.3、0.04；c=0.12只是候选。'
    checks = auto_checks(evidence, 'negative')
    assert checks['checks']['N-B2']['status'] == 'hit'
    assert checks['verdict'] == 'not_observed' and not checks['blocking_failures']


def test_s0_missing_explicit_adoption_is_pending_and_rejects_foreign_annotation(tmp_path):
    manifest, case, _, _ = _s0_fixture(tmp_path, adopted=False)
    report = suite.result(tmp_path, manifest, case)
    review = _s0_review(report)
    assert assess(report['scoring_evidence'], review['rubric'], review, objective='negative') == 'not_observed'
    annotation = report['adoption_template']
    annotation.update(run_ids=['foreign-run'],root_record_digest=report['scoring_evidence']['root_records'][-1]['record_digest'],
        root_excerpt='最终采用',reason='场外对象')
    write(tmp_path/(case+'.adoption.json'), annotation)
    with pytest.raises(ValueError, match='exact_sealed_subjects'):
        suite.result(tmp_path, manifest, case)


def test_s0_stagnation_single_task_passes_without_cross_task(tmp_path):
    from scripts.s0_scoring import assess_domains
    manifest, case, _, _ = _s0_fixture(tmp_path, topic='stagnation', count=1)
    report = suite.result(tmp_path, manifest, case)
    q = assess_domains(report['scoring_evidence'], _s0_review(report), 'stagnation')
    assert q == dict(science='passed',cross_task='not_observed',root_scheduling='passed',overall='passed')


def test_s0_negative_single_task_keeps_science_passed_and_cross_task_unknown(tmp_path):
    from scripts.s0_scoring import assess_domains
    manifest, case, _, _ = _s0_fixture(tmp_path, count=1)
    report = suite.result(tmp_path, manifest, case)
    q = assess_domains(report['scoring_evidence'], _s0_review(report, (2,2,None,2,2)), 'negative')
    assert q == dict(science='passed',cross_task='not_observed',root_scheduling='passed',overall='not_observed')
    q = assess_domains(report['scoring_evidence'], _s0_review(report, (2,2,0,2,2)), 'negative')
    assert q['science'] == 'passed' and q['cross_task'] == q['overall'] == 'failed'


def test_s0_worker_text_and_final_state_do_not_prove_root_stop_or_wait(tmp_path):
    from scripts.s0_scoring import assess_domains, waiting_observation
    manifest, case, _, _ = _s0_fixture(tmp_path)
    report = suite.result(tmp_path, manifest, case)
    evidence = deepcopy(report['scoring_evidence'])
    evidence['root_records'] = []
    evidence['control'] = dict(state='stopped',reason='goal_completed')
    q = assess_domains(evidence, _s0_review(report), 'negative')
    assert q['science'] == 'passed' and q['root_scheduling'] == q['overall'] == 'not_observed'
    assert not waiting_observation([dict(content=dict(type='agentMessage',text='已正确等待并停止。'))])
    assert not waiting_observation(report['scoring_evidence']['root_records'], {'foreign-output'})
    # A definite reviewed failure remains visible even when scheduling is missing.
    q = assess_domains(evidence, _s0_review(report,(0,2,2,2,2)), 'negative')
    assert q['science'] == q['overall'] == 'failed'


@pytest.mark.parametrize('identity', ['host', 'checkpoint', 'missing'])
def test_s0_autonomous_setup_reads_do_not_qualify_background_root(tmp_path, identity):
    from scripts import s0_scoring as scorer
    manifest, case, target, journey = _s0_fixture(tmp_path, adopted=False)
    original = suite.result(tmp_path, manifest, case)
    checkpoint = dict(usage_records={'actual-background':dict(role='root')}) if identity == 'checkpoint' else {}
    control = dict(host_json=json.dumps({'thread_id':'actual-background'}) if identity == 'host' else None,
        checkpoint_json=json.dumps(checkpoint), state='stopped', reason='goal_completed')
    records = scorer.root_records(journey, control)
    assert records and all(v['role'] == 'setup_root' for v in records)
    assert not scorer.waiting_observation(records, {'output-1'})
    annotation = dict(evidence_digest=digest(original['scoring_evidence']['sealed_outputs']), run_ids=['r2'],
        root_record_digest=records[-1]['record_digest'], root_excerpt=records[-1]['content']['text'],
        reason='setup/audit Root 的科学内容供人工审阅；不是后台调度记录。')
    evidence = scorer.collect(target, journey, original['scoring_evidence']['sealed_outputs'],
        original['scoring_evidence']['details'], [], control, annotation)
    assert evidence['final_selection']['root_record_role'] == 'setup_root'
    q = scorer.assess_domains(evidence, _s0_review(original), 'negative')
    assert q['science'] == q['cross_task'] == 'passed'
    assert q['root_scheduling'] == q['overall'] == 'not_observed'
    # The same setup MCP calls cannot qualify stagnation stop/continue either.
    assert scorer.assess_domains(evidence, _s0_review(original), 'stagnation')['root_scheduling'] == 'not_observed'


def test_s0_only_final_evidence_gaps_block_science(tmp_path):
    from scripts.s0_scoring import assess_domains
    manifest, case, _, _ = _s0_fixture(tmp_path)
    report = suite.result(tmp_path, manifest, case)
    evidence = deepcopy(report['scoring_evidence'])
    evidence['omissions'] = [dict(run_id='r1',reason='unsupported_output_schema')]
    assert assess_domains(evidence, _s0_review(report), 'negative')['science'] == 'passed'
    evidence['omissions'].append(dict(run_id='r2',reason='adopted_receipt_missing_or_ambiguous'))
    assert assess_domains(evidence, _s0_review(report), 'negative')['science'] == 'not_observed'


def test_s0_schema_projection_does_not_guess_nested_keys():
    from scripts.s0_scoring import decision_fields, REPORT
    assert decision_fields({'unknown':{'summary':'假的'}}, 'unknown.schema') == {}
    assert decision_fields({'summary':'正式', 'unknown':{'summary':'假的'}}, REPORT) == {'/summary':'正式'}


def test_s0_blind_package_preserves_scientific_words_and_review_import(tmp_path, monkeypatch):
    from scripts import s0_scoring as scorer
    manifest, case, _, _ = _s0_fixture(tmp_path, topic='stagnation', count=1)
    report = suite.result(tmp_path, manifest, case)
    batch = scorer.package(tmp_path, manifest, {case:report})
    blind_id = batch['packages'][0]['blind_id']
    folder = tmp_path/'blind'/blind_id
    delivery = (folder/'delivery.md').read_text()
    assert '候选 baseline' in delivery
    assert 'r1' not in delivery and 'output-0' not in delivery
    assert (tmp_path/'blind-key.json').stat().st_mode & 0o777 == 0o600
    score = json.loads((folder/'score.json').read_text())
    score.update(_s0_review(report))
    write(folder/'score.json', score)
    monkeypatch.setattr(suite.sys,'argv',['accept_b6.py','review',case,'--suite',str(tmp_path),'--review-file',str(folder/'score.json')])
    assert suite.main() == 0
    final = suite.result(tmp_path,manifest,case)
    assert final['status'] == final['qualification']['overall'] == 'passed'
    assert compare(final,final)['qualification']['science']['both_passed']
    with pytest.raises(FileExistsError):
        suite.main()
    (folder/'delivery.md').write_text(delivery+'tampered')
    with pytest.raises(ValueError, match='blind_package_changed'):
        scorer.validate_blind_review(tmp_path, case, score)


def test_config_covers_required_boundaries_without_new_instance_selection():
    config=suite.configuration(suite.DEFAULT)
    assert config['instance']=='b0a-calibration'
    assert set(config['cases'])=={'closeout','recovery','authority','helper','helper-crash','manual-known','auto-known',
        'manual-ambiguous','auto-ambiguous','managed','rollback'}
    assert 'automatic_recovery' in config['cases']['recovery']['requires']
    assert config['managed']['per_service_memory_bytes']*2<=2_000_000_000


def test_progress_benchmark_freezes_repeats_cost_and_scientific_not_runtime_verdicts():
    config = suite.configuration(suite.SCRIPTS/'acceptance/scientific_progress.json')
    assert len(config['cases']) == 12
    for topic in ('stagnation', 'negative'):
        for repeat in range(1, 4):
            left = config['cases'][f'manual-{topic}-{repeat}']
            right = config['cases'][f'auto-{topic}-{repeat}']
            assert left['objective'] == right['objective'] == topic
            assert left['multi_task'] and right['multi_task']
            assert 'quality' in left['requires'] and 'quality' in right['requires']
    assert config['budget']['suite']['total_tokens'] == 16_000_000
    assert config['budget']['suite']['uncached_tokens'] == 1_200_000


def test_budget_counts_cache_once_and_refuses_partial_or_invalid_accounting():
    usage = dict(coverage='observed', groups={'root':dict(input_tokens=100,cached_input_tokens=80,output_tokens=5)})
    assert token_totals(usage) == dict(total_tokens=105, uncached_tokens=25)
    with pytest.raises(ValueError, match='incomplete'):
        token_totals({**usage, 'coverage':'partial'})
    assert token_totals({**usage, 'coverage':'partial'}, require_complete=False)['total_tokens'] == 105
    usage['groups']['root']['cached_input_tokens'] = 101
    with pytest.raises(ValueError, match='invalid'):
        token_totals(usage)


def test_suite_budget_charges_failed_attempt_and_blocks_unknown_or_missing_usage(tmp_path, monkeypatch):
    config = suite.configuration(suite.SCRIPTS/'acceptance/scientific_progress.json')
    manifest = dict(config=config)
    case_id = next(iter(config['cases']))
    target = tmp_path/case_id
    target.mkdir()
    write(tmp_path/(case_id+'.attempt.json'), {})
    with pytest.raises(ValueError, match='outcome_unknown'):
        suite.budget_admission(tmp_path, manifest)
    write(tmp_path/(case_id+'.exit.json'), {'returncode':1})
    (target/'model-submission-started').touch()
    report = dict(status='failed',resource=dict(elapsed_seconds=10),usage=dict(coverage='partial',groups={}))
    monkeypatch.setattr(suite, 'result', lambda *args: report)
    with pytest.raises(ValueError, match='incomplete'):
        suite.budget_admission(tmp_path, manifest)
    report['usage'] = dict(coverage='observed',groups={'root':dict(input_tokens=100,cached_input_tokens=80,output_tokens=5)})
    assert suite.budget_admission(tmp_path, manifest)['spent'] == dict(total_tokens=105,uncached_tokens=25,execution_seconds=10)
    config['budget']['suite']['uncached_tokens'] = config['budget']['session']['uncached_tokens'] + 24
    with pytest.raises(ValueError, match='insufficient'):
        suite.budget_admission(tmp_path, manifest)


def test_native_case_observed_budget_stops_even_with_partial_usage(tmp_path, monkeypatch):
    from scripts import acceptance_native_cases as native
    config = suite.configuration(suite.SCRIPTS/'acceptance/scientific_progress.json')
    host = object.__new__(native.NativeCaseJourney)
    host.case_config = dict(scenario='manual', budget=deepcopy(config['budget']))
    host.case_config['budget']['session']['uncached_tokens'] = 25
    host.logdir = tmp_path/'logs'
    host.started_threads = {'r','missing'}
    host.case_started_at = native.time.monotonic()
    host.save_usage = lambda: write(tmp_path/'usage.json', dict(root_thread='r',threads={
        'r':dict(inputTokens=100,cachedInputTokens=80,outputTokens=5)}))
    with pytest.raises(RuntimeError, match='uncached_tokens'):
        host.check_case_budget([], [])
    saved = json.loads((tmp_path/'budget-observation.json').read_text())
    assert saved['coverage'] == 'partial'
    assert saved['observed']['total_tokens'] == 105


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
