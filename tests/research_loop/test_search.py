"""Scientific scope and real local W resource guards; no model calls."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, correction, native, search
from test_history_handoff import finish


def plan(label='Mechanism', existing_ref=None, action='screen', other=False):
    rows = [dict(label=label, minimal_test='A bounded discriminating measurement', existing_ref=existing_ref)]
    if other:
        rows.append(dict(label='Unexplored mechanism', minimal_test='Independent negative control', existing_ref=None))
    return dict(scope='Original scientific H scope', commitments=rows,
                focus=dict(label=label, action=action, repair_source=None))


def focus(ref='h001.m1', action='improve', source=None):
    return dict(mechanism_ref=ref, action=action, repair_source=source)


def review(ref='h001.m1', status='screened', evidence='inputs/parents/002/conclusion.json', next_focus=None):
    return dict(dispositions=[dict(mechanism_ref=ref, status=status,
                                  reason='Scientific judgment includes negative and limited results', evidence=[evidence])], next_focus=next_focus)


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'HANDOFF_PROTOCOL', 6)  # Preserve coverage of published path-based contracts.
    public = tmp_path / 'public';public.mkdir()
    objective = public / 'objective.md';objective.write_text('Resolve mechanisms without assuming proxy optimality.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['fake'], max_tokens=10_000_000,
        max_seconds=3600, max_steps=24, model='fake', reasoning_effort='high')
    return root


def start(root, other=False):
    finish(root, 1, 'H', [], action='experiment', search_choice=plan(other=other))
    return finish(root, 2, 'W', [1], files={'candidate.py': 'def predict(): return 1\n'})


def test_normal_scientific_screen_then_improve_has_small_views(scene):
    start(scene)
    finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review(next_focus=focus()))
    job = c.build_job(scene, 4, 'W', [1, 2, 3])
    assert search.launch_reason(scene, job) is None
    assert job['search']['focus']['action'] == 'improve'
    assert job['search']['view']['accepted_w_slices'] == 1
    assert job['search']['view']['recent_w'][0]['candidate_coverage'] == 'unknown'
    assert len(json.dumps(job['history']['view'], ensure_ascii=False).encode()) <= 4096
    assert len(json.dumps(job['search']['view'], ensure_ascii=False, indent=2).encode()) <= search.MAX_VIEW_BYTES
    without = dict(job);without.pop('search')
    added = len(json.dumps(c.science_view(job), ensure_ascii=False, indent=2).encode()) - len(json.dumps(c.science_view(without), ensure_ascii=False, indent=2).encode())
    assert added <= 4608  # Contains pretty-print nesting overhead; schema is not in the packet.
    finish(scene, 4, 'W', [1, 2, 3])
    finish(scene, 5, 'A', [1, 4], action='finish')
    assert len(search.project(scene, 6)['accepted_slices']) == 2  # Candidates do not create dispatches.


def test_pending_old_ref_survives_h_omission_and_rename(scene):
    start(scene, other=True)
    finish(scene, 3, 'A', [1, 2], action='revise_h', search_choice=review())
    finish(scene, 4, 'H', [1, 2, 3], action='experiment', search_choice=plan('Renamed', 'h001.m1', 'improve'))
    job = c.build_job(scene, 5, 'W', [4])
    assert search.launch_reason(scene, job) == 'search_commitments_pending'
    state = search.project(scene, 5)
    assert state['mechanisms']['h001.m2']['status'] == 'pending'
    assert len(state['mechanisms']) == 2


def test_h_reauthorizes_exact_pending_ref_for_screen(scene):
    start(scene, other=True)
    finish(scene, 3, 'A', [1, 2], action='revise_h', search_choice=review())
    finish(scene, 4, 'H', [1, 2, 3], action='experiment', search_choice=plan('Renamed pending', 'h001.m2'))
    job = c.build_job(scene, 5, 'W', [4])
    assert job['search']['focus']['mechanism_ref'] == 'h001.m2'
    assert search.launch_reason(scene, job) is None


def test_negative_or_infeasible_bound_evidence_can_waive_without_new_w(scene):
    finish(scene, 1, 'H', [], action='analyze', search_choice=plan())
    finish(scene, 2, 'A', [1], action='continue_w', search_choice=review(status='waived',
        evidence='inputs/parents/001/conclusion.json', next_focus=focus()))
    job = c.build_job(scene, 3, 'W', [1, 2])
    assert search.launch_reason(scene, job) is None


def test_screened_requires_same_mechanism_screen_evidence(scene):
    start(scene, other=True)
    with pytest.raises(ValueError, match='same-mechanism'):
        finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review('h001.m2', next_focus=focus()))
    assert not (c.host_record(c.workspace(scene, 3)) / 'result-identity.json').exists()


def test_screened_carries_from_bound_a_history_while_screening_new_mechanism(scene):
    start(scene, other=True)
    finish(scene, 3, 'A', [1, 2], action='continue_w',
           search_choice=review(next_focus=focus('h001.m2', 'screen')))
    finish(scene, 4, 'W', [1, 2, 3])
    choice = review(evidence='inputs/history/nodes/003/0001.json')
    choice['dispositions'].extend(review('h001.m2', evidence='inputs/parents/004/conclusion.json')['dispositions'])
    finish(scene, 5, 'A', [1, 4], action='finish', search_choice=choice)
    state = search.project(scene, 6)
    assert {ref: row['status'] for ref, row in state['mechanisms'].items()} == {
        'h001.m1': 'screened', 'h001.m2': 'screened'}
    job = c.read(scene / 'jobs/005.json')
    assert job['direct_materials'] == []  # Historical A evidence does not inherit W2 attachments.
    assert c.validate(c.workspace(scene, 5))['next_action'] == 'finish'


@pytest.mark.parametrize('restate', [True, False])
def test_a_reports_only_changes_and_restatements_do_not_replace_originals(scene, restate):
    choice = plan(other=True)
    choice['commitments'].extend([dict(label=label, minimal_test='Bounded screen', existing_ref=None)
                                  for label in ('Heavy tail', 'Supervised regression')])
    finish(scene, 1, 'H', [], action='experiment', search_choice=choice)
    finish(scene, 2, 'W', [1])
    finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review(next_focus=focus('h001.m2', 'screen')))
    finish(scene, 4, 'W', [1, 2, 3])
    finish(scene, 5, 'A', [1, 4], action='continue_w',
           search_choice=review('h001.m2', evidence='inputs/parents/004/conclusion.json', next_focus=focus('h001.m4', 'screen')))
    finish(scene, 6, 'W', [1, 4, 5])
    original = (c.host_record(c.workspace(scene, 3)) / 'science-output.json').read_bytes()
    choice = review('h001.m4', evidence='inputs/parents/006/conclusion.json', next_focus=focus('h001.m3', 'screen'))
    if restate:
        choice['dispositions'] += review(evidence='inputs/history/pages/0001.json')['dispositions']
        choice['dispositions'] += review('h001.m2', evidence='inputs/history/nodes/005/0001.json')['dispositions']
        choice['dispositions'] += review('h001.m3', status='pending', evidence='inputs/history/pages/0001.json')['dispositions']
    finish(scene, 7, 'A', [1, 6], action='continue_w', search_choice=choice)
    state = search.project(scene, 8)
    assert [state['mechanisms'][f'h001.m{i}']['status'] for i in range(1, 5)] == ['screened', 'screened', 'pending', 'screened']
    assert state['focus'] == focus('h001.m3', 'screen')
    assert (c.host_record(c.workspace(scene, 3)) / 'science-output.json').read_bytes() == original
    job = c.read(scene / 'jobs/007.json')
    assert c.read(c.host_record(c.workspace(scene, 7)) / 'science-output.json')['search_review'] == choice
    with pytest.raises(ValueError, match='bound original'):
        correction.validate_payload(scene, job, dict(progress_assessment=dict(
            verdict='progress', evidence=['inputs/history/pages/0001.json'])))


@pytest.mark.parametrize('forged_view', [False, True])
def test_first_screened_cannot_use_a_only_evidence_or_forged_view(scene, forged_view):
    finish(scene, 1, 'H', [], action='analyze', search_choice=plan())
    finish(scene, 2, 'A', [1], action='continue_w',
           search_choice=dict(dispositions=[], next_focus=focus(action='screen')))
    finish(scene, 3, 'W', [1, 2])
    job = c.build_job(scene, 4, 'A', [1, 3])
    if forged_view:
        job['search']['view']['commitments'][0]['status'] = 'screened'
    with pytest.raises(ValueError, match='same-mechanism'):
        search.validate_payload(scene, job,
            dict(search_review=review(evidence='inputs/history/nodes/002/0001.json')))
    assert search.project(scene, 4)['mechanisms']['h001.m1']['status'] == 'pending'
    assert not (c.host_record(c.workspace(scene, 4)) / 'result-identity.json').exists()


def test_first_screened_requires_screen_not_improve_w_evidence(scene):
    finish(scene, 1, 'H', [], action='analyze', search_choice=plan())
    finish(scene, 2, 'A', [1], action='continue_w',
           search_choice=review(status='waived', evidence='inputs/parents/001/conclusion.json', next_focus=focus()))
    finish(scene, 3, 'W', [1, 2])
    assert c.read(scene / 'jobs/003.json')['search']['focus']['action'] == 'improve'
    with pytest.raises(ValueError, match='same-mechanism'):
        finish(scene, 4, 'A', [1, 3], action='finish',
               search_choice=review(evidence='inputs/parents/003/conclusion.json'))
    assert not (c.host_record(c.workspace(scene, 4)) / 'result-identity.json').exists()


@pytest.mark.parametrize('invalid', ['empty', 'tampered_history'])
def test_restatement_is_noop_but_changes_and_frozen_history_still_validate(scene, invalid):
    start(scene)
    finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review(next_focus=focus()))
    finish(scene, 4, 'W', [1, 2, 3])
    job = c.build_job(scene, 5, 'A', [1, 4])
    choice = review(evidence='inputs/history/nodes/003/0001.json')
    if invalid == 'empty':
        choice['dispositions'][0]['evidence'] = []
        search.validate_payload(scene, job, dict(search_review=choice))
        choice['dispositions'][0]['status'] = 'waived'
        with pytest.raises(ValueError, match='original evidence'):
            search.validate_payload(scene, job, dict(search_review=choice))
    else:
        page = c.workspace(scene, 5) / 'inputs/history/nodes/003/0001.json'
        page.chmod(0o600);page.write_text('{}')
        with pytest.raises(ValueError, match='history page changed'):
            c._validate_inputs(scene, c.workspace(scene, 5), job)
        choice['dispositions'][0]['status'] = 'waived'
        with pytest.raises(ValueError, match='exactly bound'):
            search.validate_payload(scene, job, dict(search_review=choice))
    assert not (c.host_record(c.workspace(scene, 5)) / 'result-identity.json').exists()


def test_protocol6_task_schema_and_view_survive_protocol7_upgrade(scene, monkeypatch):
    monkeypatch.setattr(c, 'HANDOFF_PROTOCOL', 6)
    start(scene)
    finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review(next_focus=focus()))
    paths = [scene / 'jobs/003.json', c.workspace(scene, 3) / 'science-task.json',
             c.host_record(c.workspace(scene, 3)) / 'science-result.schema.json']
    originals = [path.read_bytes() for path in paths]
    monkeypatch.setattr(c, 'HANDOFF_PROTOCOL', 7)
    retained = c.build_job(scene, 3, 'A', [1, 2])
    assert retained['handoff_protocol'] == 6
    assert [path.read_bytes() for path in paths] == originals
    c.validate(c.workspace(scene, 3))
    new = c.build_job(scene, 4, 'W', [1, 2, 3])
    assert new['handoff_protocol'] == 7
    assert 'only changed dispositions' in new['search']['view']['instructions']
    assert 'only this round' in c.result_schema('A', 7)['properties']['search_review']['description']
    assert 'only this round' not in c.result_schema('A', 6)['properties']['search_review']['description']


def test_reopened_pending_rejects_old_a_only_screened_claim(scene):
    start(scene)
    finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review(next_focus=focus()))
    finish(scene, 4, 'W', [1, 2, 3])
    finish(scene, 5, 'A', [1, 4], action='continue_w',
           search_choice=dict(dispositions=[dict(mechanism_ref='h001.m1', status='pending',
               reason='Reopened scientific question', evidence=[])], next_focus=focus(action='screen')))
    finish(scene, 6, 'W', [1, 4, 5])
    assert search.project(scene, 7)['mechanisms']['h001.m1']['status'] == 'pending'
    with pytest.raises(ValueError, match='same-mechanism'):
        finish(scene, 7, 'A', [1, 6], action='finish',
               search_choice=review(evidence='inputs/history/nodes/003/0001.json'))
    assert not (c.host_record(c.workspace(scene, 7)) / 'result-identity.json').exists()


def test_null_review_clears_focus_and_does_not_force_recommendation(scene):
    start(scene)
    finish(scene, 3, 'A', [1, 2], action='continue_w')
    job = c.build_job(scene, 4, 'W', [1, 2, 3])
    assert search.launch_reason(scene, job) == 'search_focus_required'
    assert c.read(c.host_record(c.workspace(scene, 3)) / 'science-output.json')['candidate_recommendation'] is None


def test_exact_requested_repair_chain_is_bounded_and_restart_deduplicated(scene):
    start(scene)
    for a_step, w_step, source_step in [(3, 4, 2), (5, 6, 4)]:
        finish(scene, a_step, 'A', [1, source_step], action='continue_w',
            search_choice=dict(dispositions=[], next_focus=focus(action='repair', source=f'inputs/parents/{source_step:03d}/conclusion.json')))
        job = c.build_job(scene, w_step, 'W', [1, source_step, a_step])
        assert job['search']['repair_root'] == 2
        assert search.launch_reason(scene, job) is None
        finish(scene, w_step, 'W', [1, source_step, a_step], files={'renamed.py': str(w_step)})
    finish(scene, 7, 'A', [1, 6], action='continue_w',
        search_choice=dict(dispositions=[], next_focus=focus(action='repair', source='inputs/parents/006/conclusion.json')))
    job = c.build_job(scene, 8, 'W', [1, 6, 7])
    assert search.launch_reason(scene, job) == 'search_repair_limit'
    assert search.project(scene, 8)['repairs'] == {2: 2}
    assert search.project(scene, 8)['repairs'] == {2: 2}
    assert search.project(scene, 8)['mechanisms']['h001.m1']['status'] == 'pending'


@pytest.mark.parametrize('evidence', ['../../foreign/conclusion.json', 'inputs/history/pages/0001.json'])
def test_evidence_must_be_an_exact_bound_original(scene, evidence):
    start(scene)
    with pytest.raises(ValueError, match='bound original'):
        finish(scene, 3, 'A', [1, 2], action='continue_w', search_choice=review(evidence=evidence))


def test_same_boot_slice_anchor_paused_time_and_cached_tokens(scene, monkeypatch):
    start(scene)
    job = c.read(scene / 'jobs/002.json')
    now = [100.]
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: now[0])
    monkeypatch.setattr(budget.time, 'time', lambda: now[0])
    c.write(scene / 'host-started.json', budget.clock_stamp())
    budget.transition(scene, 'advance', 'test')
    anchor = search.accept(scene, job)
    intent = dict(search_slice=anchor)
    meter = dict(input_tokens=1_000_000, cached_input_tokens=999_999, output_tokens=0)
    now[0] += 3
    budget.inactive(scene, 'controller paused after accepted test work')
    now[0] += 5000
    budget.transition(scene, 'advance', 'same original test work')
    assert search.stop_reason(scene, job, intent, budget.snapshot(scene), meter) is None
    assert search.report(scene, job, intent, meter)['advance_seconds'] == 3
    meter['output_tokens'] = 1_000_000
    assert search.stop_reason(scene, job, intent, budget.snapshot(scene), meter) == 'w_slice_token_limit'
    now[0] += 900
    assert search.stop_reason(scene, job, intent, budget.snapshot(scene), meter) == 'w_slice_time_limit'
    assert intent['search_slice'] == anchor


FAKE_NATIVE = '''import json,os,pathlib,sys,time
args=sys.argv[1:];sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);role=os.environ['THIN_HWA_ROLE']
job=json.loads((work/'science-task.json').read_text())
mode=os.environ.get('N3_FIXTURE_MODE','normal')
step=int(work.name)
payload={'summary':'Scientific fixture result','scientific_result':'Negative and bounded evidence','limitations':['No scientific effectiveness qualification']}
if role=='H':
 payload.update(next_action='experiment',route_reason='Screen the declared mechanism',search_plan={'scope':'Bounded H scope','commitments':[{'label':'Mechanism','minimal_test':'Discriminating measurement','existing_ref':None}],'focus':{'label':'Mechanism','action':'screen','repair_source':None}})
elif role=='A':
 payload['progress_assessment']=None
 if 'search' not in job and not job.get('lineage',{}).get('mechanisms',{}).get('count'):
  payload.update(next_action='finish',route_reason='Legacy policy remains unchanged',candidate_recommendation=None,search_review=None)
 else:
  if 'search' in job:ref=job['search']['commitments'][0]['mechanism_ref']
  else:ref=json.loads((work/job['lineage']['indexes']['mechanisms']).read_text())['mechanisms'][0]['mechanism_ref']
  payload.update(next_action='continue_w' if step==3 else 'finish',route_reason='Evidence warrants this scientific route',candidate_recommendation=None,search_review={'dispositions':[{'mechanism_ref':ref,'status':'screened','reason':'Bounded negative result counts as screening','evidence':['inputs/parents/002/conclusion.json']}] if step==3 else [],'next_focus':{'mechanism_ref':ref,'action':'improve','repair_source':None} if step==3 else None})
if 'implementation_selection' in job['final_response']:
 payload['implementation_selection']=None
 if payload.get('search_plan'):
  payload['search_plan']['focus'].pop('repair_source',None)
 if payload.get('search_review'):
  for item in payload['search_review']['dispositions']:item.pop('evidence',None)
  if payload['search_review']['next_focus']:payload['search_review']['next_focus'].pop('repair_source',None)
(work/'artifacts'/'observation.txt').write_text('Original observed candidate evidence')
if role=='W':
 (work/'work'/'launches.txt').write_text('one accepted native process')
 if mode=='time':
  time.sleep(10)
 if mode=='tokens':
  print(json.dumps({'type':'turn.completed','usage':{'input_tokens':101,'cached_input_tokens':100,'output_tokens':1}}),flush=True)
  time.sleep(10)
output=pathlib.Path(args[args.index('--output-last-message')+1]);output.write_text(json.dumps(payload))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'cached_input_tokens':2,'output_tokens':3}}),flush=True)
'''


def process_instance(tmp_path, mode='normal'):
    public = tmp_path / 'public';public.mkdir()
    objective = public / 'objective.md';objective.write_text('Bounded original question')
    launcher = tmp_path / 'native.py';launcher.write_text(FAKE_NATIVE)
    root = tmp_path / 'instance'
    limits = dict(search.DEFAULT_POLICY)
    if mode == 'time':
        limits['max_w_seconds'] = 1.5
    if mode == 'tokens':
        limits['max_w_observed_tokens'] = 100
    controller.prepare(root, objective, public, [sys.executable, str(launcher)], max_tokens=100_000,
        max_seconds=60, max_steps=6, model='fixture', reasoning_effort='high', search_policy=None if mode == 'legacy' else limits)
    return root


def test_real_native_five_roles_complete_short_steps_without_root(tmp_path):
    root = process_instance(tmp_path)
    result = controller.run(root)
    assert result['status'] == 'finish', result
    assert result['completed_steps'] == 5
    assert search.project(root, 6)['accepted_slices'][0]['meter']['observed_tokens'] == 10
    assert search.project(root, 6)['accepted_slices'][1]['meter']['dispatches'] == 1
    assert controller.run(root) == result


@pytest.mark.parametrize('mode', ['time', 'tokens'])
def test_real_hard_slice_keeps_original_failure_without_a_or_replay(tmp_path, monkeypatch, mode):
    root = process_instance(tmp_path, mode)
    monkeypatch.setenv('N3_FIXTURE_MODE', mode)
    result = controller.run(root)
    assert result['status'] == 'native_stopped', result
    record = c.host_record(c.workspace(root, 2))
    outcome = c.read(record / 'native-outcome.json')
    assert outcome['stop_reason'] == f'w_slice_{"time" if mode == "time" else "token"}_limit'
    assert (c.workspace(root, 2) / 'artifacts/observation.txt').is_file()
    assert not (record / 'result-identity.json').exists()
    assert not (root / 'jobs/003.json').exists()
    original = {p: p.read_bytes() for p in [record / 'native-intent.json', record / 'native-outcome.json']}
    assert controller.run(root)['status'] == 'native_outcome_unsealed'
    assert all(p.read_bytes() == data for p, data in original.items())


def test_utf8_long_scientific_commitments_keep_default_view_bounded(scene):
    value = plan()
    value['commitments'] = [dict(label='机制' + str(i) + '文' * 30, minimal_test='科学' * 400, existing_ref=None) for i in range(4)]
    value['focus']['label'] = value['commitments'][0]['label']
    finish(scene, 1, 'H', [], action='experiment', search_choice=value)
    job = c.build_job(scene, 2, 'W', [1])
    assert len(json.dumps(job['search']['view'], ensure_ascii=False, indent=2).encode()) <= 4096
    assert len(json.dumps(job['history']['view'], ensure_ascii=False).encode()) <= 4096


def test_missing_h_plan_preserves_science_and_stops_new_w_dispatch(scene, monkeypatch):
    monkeypatch.setattr(native, 'execute_native', lambda root, step:
        finish(root, step, 'H', [], action='experiment'))
    result = controller.run(scene)
    assert result['status'] == 'search_pending'
    assert result['reason'] == 'search_focus_required'
    assert result['completed_steps'] == 1
    assert not (c.host_record(c.workspace(scene, 2)) / 'native-intent.json').exists()


def test_e_route_keeps_requester_and_mechanism_identity(scene, monkeypatch):
    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        parents = [int(Path(row['path']).parts[2]) for row in job['direct_refs']]
        if step == 1:
            finish(root, step, 'H', parents, action='extract', search_choice=plan())
        elif step == 2:
            assert job['evidence_return'] == dict(role='H', step=1)
            finish(root, step, 'E', parents)
        elif step == 3:
            finish(root, step, 'H', parents, action='experiment', search_choice=plan(existing_ref='h001.m1'))
        elif step == 4:
            finish(root, step, 'W', parents)
        else:
            finish(root, step, 'A', parents, action='finish', search_choice=review(evidence='inputs/parents/004/conclusion.json'))
    monkeypatch.setattr(native, 'execute_native', execute)
    result = controller.run(scene)
    assert result['status'] == 'finish', result
    assert len(search.project(scene, 6)['mechanisms']) == 1


def test_old_settings_without_policy_complete_without_search_gates(tmp_path):
    root = process_instance(tmp_path, 'legacy')
    assert 'search_policy' not in c.settings(root)
    result = controller.run(root)
    assert result['status'] == 'finish', result
    assert result['completed_steps'] == 3
    for step in range(1, 4):
        assert 'search' not in c.read(root / 'jobs' / f'{step:03d}.json')
        assert 'search_slice' not in c.read(c.host_record(c.workspace(root, step)) / 'native-intent.json')
