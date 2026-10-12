"""All-role resource guards through real local transport, never real models."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, native, runtime, search
from scidiscovery.research_loop.cli import status
from test_history_handoff import finish


ROLES = ('H', 'W', 'A', 'E')


def policy(tokens=1000, seconds=30):
    return {role: dict(max_observed_tokens=tokens, max_seconds=seconds) for role in ROLES}


FAKE_NATIVE = '''import json,os,pathlib,sys,time
args=sys.argv[1:];sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE']);role=os.environ['THIN_HWA_ROLE']
task=json.loads((work/'science-task.json').read_text())
config=json.loads(pathlib.Path(sys.argv[0]).with_suffix('.json').read_text())
with (work/'work/launches.txt').open('a') as stream:stream.write('launch\\n')
payload={'summary':'A bounded finding','scientific_result':'Original fixture observation','limitations':['No scientific effectiveness claim']}
if 'implementation_selection' in task['final_response']:payload['implementation_selection']=None
if role=='H':payload.update(next_action='wait',route_reason='No further work required',search_plan=None)
if role=='A':payload.update(next_action='finish',route_reason='A bounded conclusion',candidate_recommendation=None,search_review=None,progress_assessment=None)
mode=config['mode']
if mode!='no_usage':
 print(json.dumps({'type':'turn.completed','usage':{'input_tokens':config['input'],'cached_input_tokens':config['cached'],'output_tokens':config['output']}}),flush=True)
(work/'work/ready').touch()
if mode in ('time','tokens','no_usage'):time.sleep(20)
if mode=='hold':
 while not (work/'work/release').exists():time.sleep(.02)
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(payload))
'''


def instance(tmp_path, *, limits=None, mode='normal', max_tokens=100_000,
             max_seconds=120, search_policy=None, observed=(7, 2, 3)):
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Resolve the original bounded scientific question.')
    launcher = tmp_path / 'native.py'
    launcher.write_text(FAKE_NATIVE)
    c.write(launcher.with_suffix('.json'), dict(mode=mode, input=observed[0],
                                              cached=observed[1], output=observed[2]))
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, [sys.executable, str(launcher)],
                       max_tokens=max_tokens, max_seconds=max_seconds, max_steps=6,
                       model='fixture-no-model', reasoning_effort='high', node_budget_mode='hard',
                       search_policy=search_policy, node_budget_policy=limits)
    return root


def target(root, role, *, with_search=False):
    if role == 'H':
        return 1
    action = {'W': 'experiment', 'A': 'analyze', 'E': 'extract'}[role]
    plan = (dict(scope='Discriminating mechanism', commitments=[dict(label='Mechanism',
                minimal_test='Bounded screen', existing_ref=None)],
                focus=dict(label='Mechanism', action='screen')) if with_search else None)
    finish(root, 1, 'H', [], action=action, search_choice=plan)
    return 2


@pytest.mark.parametrize('mutation', [
    'missing_role', 'extra_role', 'missing_limit', 'extra_limit', 'zero_tokens',
    'boolean_tokens', 'float_tokens', 'negative_seconds', 'boolean_seconds',
    'infinite_seconds', 'nan_seconds',
])
def test_strict_node_policy_has_no_silent_defaults(mutation):
    value = policy()
    if mutation == 'missing_role':
        value.pop('E')
    elif mutation == 'extra_role':
        value['Root'] = value['H'].copy()
    elif mutation == 'missing_limit':
        value['H'].pop('max_seconds')
    elif mutation == 'extra_limit':
        value['H']['retries'] = 3
    else:
        key, invalid = {
            'zero_tokens': ('max_observed_tokens', 0),
            'boolean_tokens': ('max_observed_tokens', True),
            'float_tokens': ('max_observed_tokens', 1.5),
            'negative_seconds': ('max_seconds', -1),
            'boolean_seconds': ('max_seconds', True),
            'infinite_seconds': ('max_seconds', float('inf')),
            'nan_seconds': ('max_seconds', float('nan')),
        }[mutation]
        value['H'][key] = invalid
    with pytest.raises(ValueError):
        budget.node_policy(value)


def test_valid_policy_is_explicit_and_does_not_mutate_caller():
    value = policy(tokens=123, seconds=2.5)
    before = copy.deepcopy(value)
    assert budget.node_policy(value) == before
    assert value == before


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('mode', ['time', 'tokens'])
def test_each_role_real_process_stops_without_seal_handoff_or_replay(tmp_path, role, mode):
    limits = policy(tokens=100, seconds=1.5 if mode == 'time' else 10)
    observed = (20_000, 19_999, 3) if mode == 'tokens' else (7, 2, 3)
    root = instance(tmp_path, limits=limits, mode=mode, observed=observed)
    step = target(root, role)
    result = controller.run(root)
    assert result['status'] == 'native_stopped', result
    work = c.workspace(root, step)
    record = c.host_record(work)
    outcome = c.read(record / 'native-outcome.json')
    assert outcome['stop_reason'] == f'node_slice_{"time" if mode == "time" else "token"}_limit'
    assert not (record / 'result-identity.json').exists()
    assert not (root / 'jobs' / f'{step + 1:03d}.json').exists()
    intent = c.read(record / 'native-intent.json')
    assert 'budget_slice' in intent and 'search_slice' not in intent
    assert (work / 'work/launches.txt').read_text() == 'launch\n'
    meter = c.read(record / 'usage.json')
    report = budget.node_report(root, c.read(root / 'jobs' / f'{step:03d}.json'), intent, meter)
    assert report['dispatches'] == 1
    assert report['observed_tokens'] == observed[0] + observed[2]
    if mode == 'tokens':
        # One delayed completion may greatly exceed the configured threshold.
        assert report['observed_tokens'] > 100
        assert report['observed_tokens'] != sum(observed)
    preserved = {path: path.read_bytes() for path in
                 (record / 'native-intent.json', record / 'native-outcome.json', record / 'usage.json')}
    assert controller.run(root)['status'] == 'native_outcome_unsealed'
    assert all(path.read_bytes() == raw for path, raw in preserved.items())
    assert (work / 'work/launches.txt').read_text() == 'launch\n'
    row = status(root)['nodes'][step - 1]
    assert row['role'] == role
    assert row['stop_reason'] == outcome['stop_reason']


def test_no_completed_usage_stays_unknown_after_real_time_stop(tmp_path):
    root = instance(tmp_path, limits=policy(seconds=1.5), mode='no_usage')
    result = controller.run(root)
    assert result['status'] == 'native_stopped', result
    record = c.host_record(c.workspace(root, 1))
    assert c.read(record / 'native-outcome.json')['stop_reason'] == 'node_slice_time_limit'
    assert not (record / 'usage.json').exists()
    assert c.read(record / 'native-outcome.json')['budget_slice']['usage_observed'] is False
    assert native.usage(root)['unknown_steps'] == [1]
    assert not (record / 'result-identity.json').exists()
    assert controller.run(root)['status'] == 'native_outcome_unsealed'


def test_cached_input_is_not_a_second_charge_in_actual_native_guard(tmp_path):
    root = instance(tmp_path, limits=policy(tokens=110), observed=(100, 99, 1))
    result = controller.run(root)
    assert result['status'] == 'wait' and result['completed_steps'] == 1, result
    record = c.host_record(c.workspace(root, 1))
    report = c.read(record / 'native-outcome.json')['budget_slice']
    assert report['observed_tokens'] == 101
    assert report['cached_input_tokens'] == 99
    assert report['usage_observed'] is True
    assert native.usage(root)['observed_tokens'] == 101
    assert c.validate(c.workspace(root, 1))['role'] == 'H'


def test_original_slice_excludes_explicit_pause_but_does_not_reset(tmp_path, monkeypatch):
    root = instance(tmp_path, limits=policy(seconds=10))
    now = [100.]
    monkeypatch.setattr(budget.time, 'time', lambda: now[0])
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: now[0])
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', 'first acceptance')
    job = c.build_job(root, 1, 'H', [])
    intent = dict(budget_slice=budget.accept_node(root, job))
    original = copy.deepcopy(intent)
    meter = dict(input_tokens=7, cached_input_tokens=2, output_tokens=3)
    now[0] += 3
    budget.inactive(root, 'no activity during explicit pause')
    now[0] += 5000
    budget.transition(root, 'advance', 'resume original identity')
    now[0] += 2
    assert budget.node_report(root, job, intent, meter)['advance_seconds'] == 5
    assert budget.stop_node(root, job, intent, budget.snapshot(root), meter) is None
    now[0] += 5
    assert budget.stop_node(root, job, intent, budget.snapshot(root), meter) == 'node_slice_time_limit'
    assert intent == original


@pytest.mark.parametrize('field', ['role', 'task_sha256', 'boot_id', 'limits'])
def test_changed_accepted_identity_cannot_refund_or_launch(tmp_path, field):
    root = instance(tmp_path, limits=policy())
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', 'original acceptance')
    job = c.build_job(root, 1, 'H', [])
    anchor = budget.accept_node(root, job)
    anchor[field] = dict(max_observed_tokens=9999, max_seconds=300) if field == 'limits' else 'forged'
    with pytest.raises(ValueError):
        budget.stop_node(root, job, dict(budget_slice=anchor), budget.snapshot(root),
                         dict(input_tokens=0, cached_input_tokens=0, output_tokens=0))


@pytest.mark.parametrize('node_tokens,search_tokens', [(50, 100), (100, 50)])
def test_new_w_uses_smaller_search_or_node_cap_with_one_anchor(tmp_path, node_tokens, search_tokens):
    search_limits = dict(search.DEFAULT_POLICY, max_w_observed_tokens=search_tokens)
    root = instance(tmp_path, limits=policy(tokens=node_tokens), mode='tokens',
                    observed=(70, 69, 5), search_policy=search_limits)
    target(root, 'W', with_search=True)
    result = controller.run(root)
    assert result['status'] == 'native_stopped', result
    record = c.host_record(c.workspace(root, 2))
    assert c.read(record / 'native-outcome.json')['stop_reason'] == 'node_slice_token_limit'
    intent = c.read(record / 'native-intent.json')
    assert 'budget_slice' in intent and 'search_slice' not in intent
    outcome = c.read(record / 'native-outcome.json')
    assert outcome['budget_slice']['limits']['max_observed_tokens'] == min(node_tokens, search_tokens)
    assert outcome['search_slice']['dispatches'] == 1
    assert outcome['search_slice']['observed_tokens'] == 75
    assert outcome['budget_slice']['observed_tokens'] == 75
    # A failed W contributes execution cost, never a fabricated scientific seal.
    with pytest.raises(ValueError, match='original regular file'):
        search.project(root, 3)


def test_successful_w_statistics_reuse_same_budget_anchor(tmp_path):
    root = instance(tmp_path, limits=policy(tokens=100), search_policy=search.DEFAULT_POLICY)
    target(root, 'W', with_search=True)
    result = controller.run(root)
    assert result['status'] == 'finish', result
    rows = search.project(root, 4)['accepted_slices']
    assert len(rows) == 1
    assert rows[0]['meter']['dispatches'] == 1
    assert rows[0]['meter']['observed_tokens'] == 10
    record = c.host_record(c.workspace(root, 2))
    intent = c.read(record / 'native-intent.json')
    assert 'budget_slice' in intent and 'search_slice' not in intent


@pytest.mark.parametrize('dimension', ['tokens', 'seconds'])
def test_controller_refuses_node_whose_full_cap_cannot_fit(tmp_path, dimension):
    root = instance(tmp_path, limits=policy(tokens=100, seconds=10),
                    max_tokens=99 if dimension == 'tokens' else 1000,
                    max_seconds=9 if dimension == 'seconds' else 120)
    result = controller.run(root)
    assert result['status'] == f'node_budget_unavailable_{dimension}', result
    record = c.host_record(c.workspace(root, 1))
    assert not (record / 'native-intent.json').exists()
    assert not (c.workspace(root, 1) / 'work/launches.txt').exists()


def test_amend_rejects_original_n6_intent_without_terminal_outcome(tmp_path):
    root = instance(tmp_path, limits=policy())
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', 'original accepted node')
    job = c.build_job(root, 1, 'H', [])
    record = c.host_record(c.workspace(root, 1))
    c.write(record / 'native-intent.json', dict(step=1, task_sha256=c.digest(root / 'jobs/001.json'),
                                              budget_slice=budget.accept_node(root, job)))
    paths = [root / 'settings.json', record / 'native-intent.json',
             *sorted((root / 'control-ledger').glob('*.json'))]
    preserved = {path: path.read_bytes() for path in paths}
    with pytest.raises(RuntimeError, match='running or unknown'):
        budget.amend(root, max_tokens=200_000, authorization_note='External operator request')
    assert all(path.read_bytes() == raw for path, raw in preserved.items())
    assert len(list((root / 'control-ledger').glob('*.json'))) == len(paths) - 2
    assert not (record / 'native-outcome.json').exists()


def test_amend_after_success_preserves_old_slice_report_and_consumption(tmp_path):
    root = instance(tmp_path, limits=policy())
    assert controller.run(root)['status'] == 'wait'
    record = c.host_record(c.workspace(root, 1))
    paths = [root / 'settings.json', record / 'native-intent.json',
             record / 'native-outcome.json', record / 'usage.json', record / 'result-identity.json']
    preserved = {path: path.read_bytes() for path in paths}
    before = status(root)
    result = budget.amend(root, max_tokens=200_000, max_seconds=240,
                          authorization_note='External operator changes total, not consumed work')
    assert result['status'] == 'budget_amended'
    assert all(path.read_bytes() == raw for path, raw in preserved.items())
    after = status(root)
    assert after['nodes'][0]['budget_slice'] == before['nodes'][0]['budget_slice']
    assert after['nodes'][0]['budget_report'] == before['nodes'][0]['budget_report']
    assert after['usage'] == before['usage']
    assert after['usage']['observed_tokens'] == 10
    assert after['budget']['advance_seconds'] == before['budget']['advance_seconds']
    assert after['budget']['max_tokens'] == 200_000
    assert after['budget']['max_seconds'] == 240


def test_actual_popen_rechecks_late_budget_before_native_submission(tmp_path, monkeypatch):
    root = instance(tmp_path, limits=policy(tokens=100, seconds=10), max_seconds=60)
    now = [100.]
    monkeypatch.setattr(budget.time, 'time', lambda: now[0])
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: now[0])
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', 'accepted original node')
    job = c.build_job(root, 1, 'H', [])
    record = c.host_record(c.workspace(root, 1))
    c.write(record / 'native-intent.json', dict(step=1, task_sha256=c.digest(root / 'jobs/001.json'),
                                              budget_slice=budget.accept_node(root, job)))
    now[0] = 155.  # The original intent is retained, but only five shared seconds remain.
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *a, **kw: pytest.fail('Late budget must block native Popen'))
    native.run_native(root, 1)
    outcome = c.read(record / 'native-outcome.json')
    assert outcome['native_started'] is False
    assert outcome['stop_reason'] in {'node_budget_unavailable_seconds', 'node_slice_time_limit'}
    assert not (record / 'native-process.json').exists()
    assert not (record / 'science-output.json').exists()


def _until(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    pytest.fail('Deterministic local process event did not arrive')


def test_controller_restart_rejoins_same_slice_and_counts_one_dispatch(tmp_path):
    root = instance(tmp_path, limits=policy(), mode='hold')
    work = c.workspace(root, 1)
    record = c.host_record(work)
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'src'))
    command = [sys.executable, '-m', 'scidiscovery.research_loop.cli', 'run', '--root', str(root)]
    fronts = []
    try:
        first = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        fronts.append(first)
        _until(lambda: (work / 'work/ready').exists())
        before = (record / 'native-intent.json').read_bytes()
        owner = c.read(record / 'runner-process.json')
        first.kill()
        first.communicate(timeout=3)
        assert runtime.process_matches(owner, owner['task_sha256'])
        second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        fronts.append(second)
        (work / 'work/release').touch()
        out, err = second.communicate(timeout=10)
        assert second.returncode == 0, out + err
        assert json.loads(out)['status'] == 'wait'
        assert (record / 'native-intent.json').read_bytes() == before
        assert (work / 'work/launches.txt').read_text() == 'launch\n'
        report = budget.node_report(root, c.read(root / 'jobs/001.json'), c.read(record / 'native-intent.json'),
                                    c.read(record / 'usage.json'))
        assert report['dispatches'] == 1 and report['observed_tokens'] == 10
        assert controller.run(root)['status'] == 'wait'
    finally:
        if (work / 'work').exists():
            (work / 'work/release').touch()
        for front in fronts:
            if front.poll() is None:
                front.communicate(timeout=12)


@pytest.mark.parametrize('legacy_w_guard', [False, True])
def test_absent_node_policy_keeps_protocol8_and_original_w_transport(tmp_path, legacy_w_guard):
    search_limits = dict(search.DEFAULT_POLICY, max_w_observed_tokens=50) if legacy_w_guard else None
    root = instance(tmp_path, limits=None, mode='tokens' if legacy_w_guard else 'normal',
                    search_policy=search_limits, observed=(70, 69, 5) if legacy_w_guard else (7, 2, 3))
    assert 'node_budget_policy' not in c.settings(root)
    if legacy_w_guard:
        target(root, 'W', with_search=True)
    result = controller.run(root)
    if legacy_w_guard:
        assert result['status'] == 'native_stopped', result
        record = c.host_record(c.workspace(root, 2))
        assert c.read(record / 'native-outcome.json')['stop_reason'] == 'w_slice_token_limit'
        assert 'search_slice' in c.read(record / 'native-intent.json')
    else:
        assert result['status'] == 'wait' and result['completed_steps'] == 1, result
        record = c.host_record(c.workspace(root, 1))
        assert c.read(root / 'jobs/001.json')['handoff_protocol'] == 8
        assert c.validate(c.workspace(root, 1))['summary'] == 'A bounded finding'
    assert 'budget_slice' not in c.read(record / 'native-intent.json')
    assert all('budget_slice' not in row for row in status(root)['nodes'])


def test_budget_changes_during_job_build_refuse_acceptance_without_claiming_retained_intent(tmp_path, monkeypatch):
    root = instance(tmp_path, limits=policy(tokens=100, seconds=10), max_seconds=60)
    now = [100.]
    monkeypatch.setattr(budget.time, 'time', lambda: now[0])
    monkeypatch.setattr(budget.time, 'clock_gettime', lambda _: now[0])
    original = c.build_job
    built = []
    def build(*args, **kwargs):
        job = original(*args, **kwargs)
        built.append(job)
        now[0] += 55  # Initial admission passed; the full node no longer fits.
        return job
    monkeypatch.setattr(c, 'build_job', build)
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *a, **kw: pytest.fail('No node was accepted'))
    result = controller.run(root)
    assert result['status'] == 'node_budget_unavailable_seconds'
    assert result['completed_steps'] == 0 and len(built) == 1
    assert 'retained' not in json.dumps(result).lower()
    record = c.host_record(c.workspace(root, 1))
    assert not (record / 'native-intent.json').exists()
    assert not (record / 'native-process.json').exists()
    assert not (record / 'science-output.json').exists()
    prepared = (root / 'jobs/001.json').read_bytes()
    assert controller.run(root)['status'] == 'node_budget_unavailable_seconds'
    assert len(built) == 1 and (root / 'jobs/001.json').read_bytes() == prepared
