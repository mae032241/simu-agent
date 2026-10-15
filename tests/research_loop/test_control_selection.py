"""Control closeout shortlist, adapter smoke and pre-registered default; zero models."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, delivery, native, selection, shortlist
from test_delivery import FAKE_HARNESS, descriptor, delivery_policy
from test_history_handoff import finish

REPO = Path(__file__).resolve().parents[2]
OBSERVER = REPO / 'scripts/observe_covshift_candidates.py'
LAUNCHER = REPO.parents[1] / '.trial/rootless-task-unit-cov-20261014/launcher.json'
RUNNER = '''def split_X_y(df, meta):
    targets = meta['target_cols'];features = [c for c in df.columns if c not in targets]
    return df[features], df[targets].values, features
'''


def cand(cid, metric, key='v1', status='ok'):
    return dict(id=cid, label=cid, evaluation_key=key, metric=metric, direction='max', status=status)


def rec(step, role, candidates=(), recommendation=None, audit=False):
    return dict(step=step, role=role, recommendation=recommendation, coverage='complete' if candidates else None,
                candidates=list(candidates), current_candidate=None, actual_submission=None, **(dict(audit_request=True) if audit else {}))


def members(value):
    return [(row['candidate_id'], row['reasons']) for row in value['members']]


def test_shortlist_ranks_one_exact_version_and_ties_prefer_later_observation():
    records = [rec(1, 'H'), rec(2, 'W', [cand('run-1', .90), cand('run-2', .91), cand('run-3', .91), cand('run-4', .99, key='v0')]),
               rec(3, 'A', recommendation='run-1')]
    value = selection.shortlist(records, 2, evaluation_key='v1')
    assert value['evaluation_key'] == 'v1' and value['ranked_count'] == 3 and value['latest_a_step'] == 3
    # Equal public metric: the later observed run ranks first, never the earliest incumbent.
    assert members(value) == [('run-3', ['top_k']), ('run-2', ['top_k']), ('run-1', ['a_recommended'])]
    assert [row['rank'] for row in value['members']] == [1, 2, 3] and value['boundary_ties_omitted'] == 0
    assert selection.shortlist(records, 1, evaluation_key='v1')['boundary_ties_omitted'] == 1


def test_multiple_versions_have_no_ranked_default_even_when_one_has_more_candidates():
    records = [rec(2, 'W', [cand('majority-1', .9), cand('majority-2', .8), cand('other', .99, key='v0')])]
    value = selection.shortlist(records, 3)
    assert value['evaluation_key'] is None and value['direction'] is None and value['ranked_count'] == 0
    assert members(value) == [('other', ['evaluation_group_best']), ('majority-1', ['evaluation_group_best'])]
    assert all(row['rank'] is None for row in value['members'])
    assert selection.default_choice(value['members'], screened((row['candidate_id'], 'ok', 'passed') for row in value['members']))['candidate_id'] is None
    # Exact selection of the minority version is authoritative; prefixes never match.
    chosen = selection.shortlist(records, 3, evaluation_key='v0')
    assert members(chosen) == [('other', ['top_k', 'unassessed_best'])] and chosen['ranked_count'] == 1
    assert selection.shortlist(records, 3, evaluation_key='v')['members'] == []


def test_ambiguous_group_members_are_bounded_and_report_omissions():
    value = selection.shortlist([rec(2, 'W', [cand(f'run-{i}', i, key=f'v{i}') for i in range(12)]),
                                 rec(3, 'A', recommendation='run-9')], 2)
    assert len(value['members']) == 3 and value['evaluation_groups_omitted_count'] == 9
    assert value['members'][-1]['candidate_id'] == 'run-9' and value['ranked_count'] == 0


@pytest.mark.parametrize('evaluation_key', [None, 'v1'])
@pytest.mark.parametrize('status', ['ok', 'failed'])
def test_conflicting_directions_never_produce_a_default(evaluation_key, status):
    records = [rec(2, 'W', [cand('max', .9), dict(cand('min', .8, status=status), direction='min')])]
    value = selection.shortlist(records, 3, evaluation_key=evaluation_key)
    assert value['ranked_count'] == 0 and value['direction'] is None
    assert all(row['rank'] is None for row in value['members'])


@pytest.mark.parametrize('key', ['', 1, 'x' * 2049])
def test_selection_policy_and_projection_reject_invalid_evaluation_keys(key):
    with pytest.raises(ValueError, match='exact public version'):
        selection.shortlist([], 3, evaluation_key=key)
    with pytest.raises(ValueError, match='exact public version'):
        shortlist.policy(dict(shortlist.DEFAULT, evaluation_key=key))


def test_candidates_after_the_last_a_assessment_enter_the_shortlist():
    # rootless-u4-cov-20261014: A006 assessed through run-13; W007 then produced run-14..26.
    early = [cand(f'run-{i}', .90 + i / 1000) for i in range(1, 6)]
    records = [rec(2, 'W', early), rec(3, 'A', recommendation='run-2'), rec(4, 'W', [cand('run-6', .5), cand('run-7', .6)])]
    value = selection.shortlist(records, 2)
    assert members(value) == [('run-5', ['top_k']), ('run-4', ['top_k']), ('run-2', ['a_recommended']), ('run-7', ['unassessed_best'])]
    assert value['unassessed_count'] == 2
    # An audit request is an assessment boundary but not a recommendation.
    value = selection.shortlist([*records, rec(5, 'A', audit=True)], 2)
    assert value['a_recommended'] == 'run-2' and value['latest_a_step'] == 5 and value['unassessed_count'] == 0


def test_non_public_or_changed_candidate_facts_are_rejected():
    hidden = dict(cand('run-1', .9), hidden_score=1.0)
    with pytest.raises(ValueError):
        selection.shortlist([rec(2, 'W', [hidden])], 3)
    with pytest.raises(ValueError):
        selection.shortlist([rec(2, 'W', [cand('run-1', .9)]), rec(3, 'W', [cand('run-1', .8)])], 3)


def screened(rows):
    return {cid: dict(smoke=smoke, audit=audit) for cid, smoke, audit in rows}


def test_default_excludes_failed_or_unknown_smoke_and_prefers_passed_audit():
    value = selection.shortlist([rec(2, 'W', [cand('run-16', .9112), cand('run-40', .9102), cand('run-34', .90), cand('old', .99, key='v0')]),
                                 rec(3, 'A', recommendation='old')], 3, evaluation_key='v1')
    rows = value['members']
    pick = lambda *statuses: selection.default_choice(rows, screened(statuses))
    # rootless-task-unit-cov-20261014: public best run-16 cannot predict; it is never the default.
    assert pick(('run-16', 'failed', 'not_run'), ('run-40', 'ok', 'passed'), ('run-34', 'ok', 'not_run'), ('old', 'ok', 'passed'))['candidate_id'] == 'run-40'
    assert pick(('run-16', 'unknown', 'not_run'), ('run-40', 'unavailable', 'not_run'), ('run-34', 'ok', 'passed'), ('old', 'ok', 'passed')) == dict(
        candidate_id='run-34', basis='audit_passed', rule=selection.DEFAULT_RULE)
    assert pick(('run-16', 'ok', 'not_run'), ('run-40', 'ok', 'passed'), ('run-34', 'ok', 'not_run'), ('old', 'ok', 'passed'))['candidate_id'] == 'run-40'
    fallback = pick(('run-16', 'ok', 'failed'), ('run-40', 'ok', 'not_run'), ('run-34', 'ok', 'unknown'), ('old', 'ok', 'passed'))
    assert fallback['candidate_id'] == 'run-40' and fallback['basis'] == 'submit_audit_pending'
    assert pick(('run-16', 'ok', 'unconfigured'), ('run-40', 'ok', 'unconfigured'), ('run-34', 'ok', 'unconfigured'), ('old', 'ok', 'unconfigured'))['basis'] == 'audit_unconfigured'
    assert pick(('run-16', 'unavailable', 'not_run'), ('run-40', 'unavailable', 'not_run'), ('run-34', 'failed', 'not_run'), ('old', 'ok', 'passed')) == dict(
        candidate_id=None, basis='none_qualified', rule=selection.DEFAULT_RULE)


def _screen_files(root, default='run-2', ids=('run-1', 'run-2', 'run-3')):
    directory = root / 'host-delivery/selection';directory.mkdir(parents=True)
    c.write(directory / 'shortlist.json', dict(members=list(ids)))
    c.write(directory / 'screen.json', dict(shortlist_sha256=c.digest(directory / 'shortlist.json'), receipts={},
        rows=[dict(candidate_id=cid) for cid in ids], default=dict(candidate_id=default, basis='audit_passed')))
    return dict(selection=shortlist.marker(root), history=dict(nodes=[dict(step=1), dict(step=2), dict(step=3)]))


def table(keep, override=None, ids=('run-1', 'run-2', 'run-3'), risk='Public validation only'):
    return dict(rows=[dict(candidate_id=cid, key_risk=risk, decision='keep' if cid == keep else 'replace') for cid in ids], override=override)


@pytest.mark.parametrize('recommendation,comparison,expected', [
    (None, table('run-2'), 'run-2'), ('run-2', table('run-2'), 'run-2'),
    ('run-3', table('run-3', dict(default_candidate='run-2', chosen_candidate='run-3', reason='Smoke-ok and audited in W002', evidence_steps=[2])), 'run-3'),
    ('run-9', table(None, dict(default_candidate='run-2', chosen_candidate='run-9', reason='Outside shortlist after audit', evidence_steps=[3])), 'run-9'),
    (None, None, 'selection_comparison_missing'),
    (None, table('run-2', ids=('run-2', 'run-1', 'run-3')), 'selection_comparison_asymmetric'),
    (None, table('run-2', ids=('run-1', 'run-2')), 'selection_comparison_asymmetric'),
    (None, table('run-2', risk=' '), 'selection_comparison_asymmetric'),
    ('run-3', table('run-2'), 'selection_keep_mismatch'),
    (None, table('run-2', dict(default_candidate='run-2', chosen_candidate='run-2', reason='x', evidence_steps=[2])), 'selection_override_unneeded'),
    ('run-3', table('run-3'), 'selection_override_unbound'),
    ('run-3', table('run-3', dict(default_candidate='run-1', chosen_candidate='run-3', reason='Wrong default', evidence_steps=[2])), 'selection_override_unbound'),
    ('run-3', table('run-3', dict(default_candidate='run-2', chosen_candidate='run-3', reason='Unbound', evidence_steps=[9])), 'selection_override_unbound'),
    ('run-3', table('run-3', dict(default_candidate='run-2', chosen_candidate='run-3', reason='  ', evidence_steps=[2])), 'selection_override_unbound'),
])
def test_comparison_table_is_symmetric_and_override_names_default_alternative_and_evidence(tmp_path, recommendation, comparison, expected):
    root = tmp_path.resolve();job = _screen_files(root)
    payload = dict(candidate_recommendation=recommendation, candidate_comparison=comparison)
    if expected.startswith('selection_'):
        with pytest.raises(delivery.DeliveryUnresolved, match=expected):shortlist.choice(root, job, payload)
    else:
        assert shortlist.choice(root, job, payload) == expected


def test_no_default_requires_a_named_choice_and_tampered_screen_is_rejected(tmp_path):
    root = tmp_path.resolve();job = _screen_files(root, default=None)
    with pytest.raises(delivery.DeliveryUnresolved, match='delivery_no_decision'):
        shortlist.choice(root, job, dict(candidate_recommendation=None, candidate_comparison=table(None)))
    override = dict(default_candidate=None, chosen_candidate='run-1', reason='No qualified default; W002 evidence', evidence_steps=[2])
    assert shortlist.choice(root, job, dict(candidate_recommendation='run-1', candidate_comparison=table('run-1', override))) == 'run-1'
    path = root / 'host-delivery/selection/screen.json';path.write_text(path.read_text().replace('run-3', 'run-4'))
    with pytest.raises(ValueError, match='screen changed'):
        shortlist.choice(root, job, dict(candidate_recommendation=None, candidate_comparison=table(None)))


def test_schema_adds_one_nullable_table_only_for_bound_closeout():
    plain, bound = c.result_schema('A'), c.result_schema('A', comparison=True)
    assert set(bound['properties']) - set(plain['properties']) == {'candidate_comparison'}
    assert bound['required'] == list(bound['properties']) and 'candidate_comparison' not in c.result_schema('W', comparison=True)['properties']
    row = bound['properties']['candidate_comparison']['properties']['rows']['items']
    assert set(row['properties']) == {'candidate_id', 'key_risk', 'decision'} and row['properties']['decision']['enum'] == ['keep', 'replace']


def _adapter(tmp_path):
    adapter = tmp_path / 'adapter.py';adapter.write_text('raise AssertionError("Unexpected external action")\n')
    return dict(adapter=str(adapter), launcher_argv=[sys.executable, str(adapter)], config={}, target={}, inputs=[], source_roots=[str(tmp_path)])


@pytest.mark.parametrize('observer,audit,policy,expected', [
    (True, True, shortlist.DEFAULT, None), (True, False, shortlist.DEFAULT, None), (False, True, shortlist.DEFAULT, None),
    (True, True, None, None), (True, False, dict(shortlist.DEFAULT, shortlist_k=5), dict(shortlist.DEFAULT, shortlist_k=5)),
    (True, True, dict(shortlist.DEFAULT, evaluation_key='v1'), dict(shortlist.DEFAULT, evaluation_key='v1')),
    (False, True, dict(shortlist.DEFAULT), ValueError), (True, True, dict(shortlist.DEFAULT, shortlist_k=0), ValueError),
    (True, True, dict(shortlist.DEFAULT, extra=1), ValueError), (True, True, dict(shortlist.DEFAULT, version=2), ValueError),
])
def test_prepare_selection_requires_explicit_policy_and_observer_adapter(tmp_path, observer, audit, policy, expected):
    public = tmp_path / 'public';public.mkdir();objective = public / 'objective.md';objective.write_text('Bounded objective')
    kwargs = dict(max_tokens=100_000, max_seconds=600, max_steps=12, model='no-model', reasoning_effort='high', search_policy=None,
                  node_budget_policy={role: dict(max_observed_tokens=2000, max_seconds=60) for role in 'HWAE'},
                  delivery_policy=delivery_policy(_adapter(tmp_path)), candidate_audit_policy={'version': 1} if audit else None,
                  history_observer=dict(adapter=str(OBSERVER), config=dict(runs='runs', evaluation_key='v1')) if observer else None)
    if policy is not shortlist.DEFAULT:
        kwargs['selection_policy'] = policy
    if expected is ValueError:
        with pytest.raises(ValueError):controller.prepare(tmp_path / 'instance', objective, public, ['never'], **kwargs)
        return
    settings = controller.prepare(tmp_path / 'instance', objective, public, ['never'], **kwargs)
    assert settings.get('selection_policy') == expected and settings['handoff_protocol'] == 16


def test_cli_prepare_selection_policy_override_and_null(tmp_path):
    from scidiscovery.research_loop import cli
    public = tmp_path / 'public';public.mkdir();objective = public / 'objective.md';objective.write_text('Bounded objective')
    files = dict(node={role: dict(max_observed_tokens=2000, max_seconds=60) for role in 'HWAE'}, delivery=delivery_policy(_adapter(tmp_path)),
                 observer=dict(adapter=str(OBSERVER), config=dict(runs='runs', evaluation_key='v1')), custom=dict(shortlist.DEFAULT, shortlist_k=2))
    for name, value in files.items():c.write(tmp_path / (name + '.json'), value)
    (tmp_path / 'off.json').write_text('null\n')
    for name, extra, expected in (('d', [], None), ('c', ['--selection-policy', str(tmp_path / 'custom.json')], files['custom']),
                                  ('o', ['--selection-policy', str(tmp_path / 'off.json')], None)):
        assert cli.main(['prepare', '--root', str(tmp_path / name), '--objective', str(objective), '--public-root', str(public),
            '--native-launcher-json', '["never"]', '--node-budget-policy', str(tmp_path / 'node.json'), '--enable-candidate-audit',
            '--delivery-policy', str(tmp_path / 'delivery.json'), '--history-observer-config', str(tmp_path / 'observer.json'),
            '--max-tokens', '1000000', '--max-seconds', '600', '--max-steps', '12', *extra]) == 0
        assert c.settings(tmp_path / name).get('selection_policy') == expected


@pytest.mark.parametrize('mode', ['hard', 'soft'])
@pytest.mark.parametrize('seconds,tokens,expected', [(110, 2010, False), (111, 2010, True), (111, 2009, False)])
def test_smoke_preserves_author_time_tokens_and_execution_floor(tmp_path, monkeypatch, mode, seconds, tokens, expected):
    settings = dict(node_budget_mode=mode, max_steps=10, delivery_policy=dict(adapter={},
        closeout_a=dict(max_seconds=60, max_observed_tokens=2000), inflight_tokens=10,
        cleanup_seconds=10, submit_seconds=10, confirm_seconds=10))
    monkeypatch.setattr(c, 'settings', lambda root: settings)
    monkeypatch.setattr(budget, 'execution_blocked', lambda root: False)
    monkeypatch.setattr(budget, 'used_steps', lambda root: 0)
    monkeypatch.setattr(budget, 'snapshot', lambda root: dict(seconds_remaining=seconds, max_tokens=tokens + 100))
    monkeypatch.setattr(native, 'usage', lambda root: dict(unknown_steps=[], observed_tokens=100))
    assert shortlist._affordable(tmp_path, dict(first_step=1, preparation_seconds=0), 20) is expected


def science_python():
    if shutil.which('bwrap') is None:pytest.skip('Actual isolated adapter namespace required')
    for python in (sys.executable, c.read(LAUNCHER)['task_python'] if LAUNCHER.is_file() else None):
        if python and subprocess.run([python, '-I', '-c', 'import numpy,pandas'], capture_output=True).returncode == 0:
            return python
    pytest.skip('Smoke needs an interpreter with numpy/pandas (the frozen task Python)')


def scene(tmp_path, *, policy=shortlist.DEFAULT, metrics=(.9, .8, .7)):
    python = science_python()
    public, root = tmp_path / 'public', (tmp_path / 'instance').absolute()
    (public / 'harness').mkdir(parents=True)
    files = {'exp_cli.py': FAKE_HARNESS, 'runner.py': RUNNER, 'train.csv': 'public fixture only\n', 'val.csv': 'y0,y1,x0,x1\n1,2,0,0\n3,4,0,1\n'}
    for name, text in files.items():(public / 'harness' / name).write_text(text)
    c.write(public / 'harness/meta.json', dict(mode='ok', target_cols=['x0', 'x1'], control_path=str(root / 'settings.json'), hidden_path=str(tmp_path / 'hidden.json')))
    c.write(tmp_path / 'hidden.json', dict(secret='Never an input'))
    objective = public / 'objective.md';objective.write_text('Deliver one exact public candidate; completion is not asserted.')
    kwargs = dict(selection_policy=policy)
    controller.prepare(root, objective, public, ['fake-no-model'], max_tokens=100_000, max_seconds=600, max_steps=24, model='fixture',
        reasoning_effort='high', search_policy=None, node_budget_policy={role: dict(max_observed_tokens=2000, max_seconds=60) for role in 'HWAE'},
        delivery_policy=delivery_policy(descriptor(root, public, python=python)), candidate_audit_policy={'version': 1},
        history_observer=dict(adapter=str(OBSERVER), config=dict(runs='runs', evaluation_key='fixture-public')), **kwargs)
    (root / 'runs').mkdir();(root / 'submission').mkdir()
    finish(root, 1, 'H', [], action='experiment')
    script = c.workspace(root, 2) / 'artifacts/train.py'
    # run-1 is the public best but its saved bytes are not a loadable model; the others predict zeros.
    (root / 'runs/model-1.pkl').write_bytes(b'not a pickle')
    for run in (2, 3):
        subprocess.run([python, '-I', '-c', 'import numpy,pickle,sys,types;pickle.dump(types.SimpleNamespace(predict=numpy.zeros_like),open(sys.argv[1],"wb"))',
                        str(root / f'runs/model-{run}.pkl')], check=True, timeout=30)
    (root / 'runs/results.jsonl').write_text(''.join(json.dumps(dict(run_id=run, ok=True, val_acc=metric, val_score=metric,
        model_path=f'/opt/exp/runs/model-{run}.pkl', script=str(script))) + '\n' for run, metric in enumerate(metrics, 1)))
    finish(root, 2, 'W', [1], files={'train.py': 'def train(train_df, val_df): return None\n'})
    finish(root, 3, 'A', [1, 2], action='finish', recommendation='run-3', progress={'verdict': 'progress'})
    c.write(root / 'host-started.json', budget.clock_stamp())
    return root


def closeout_author(monkeypatch, *attempts):
    calls = []
    def complete(root, step):
        task = c.read(c.workspace(root, step) / 'science-task.json')
        payload = dict(summary='Closeout comparison', scientific_result='Public validation only; target suitability is not asserted.',
                       limitations=['Fixture transport, not a model'], implementation_selection=None, search_review=None,
                       progress_assessment=None, decision_request=None, portfolio_review=None, next_action='finish',
                       route_reason='Bounded delivery decision', **attempts[len(calls)](task))
        calls.append((step, task))
        record = c.host_record(c.workspace(root, step))
        c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs' / f'{step:03d}.json')))
        c.write(record / 'science-output.json', payload)
        c.write(record / 'usage.json', dict(input_tokens=7, cached_input_tokens=2, output_tokens=3))
        c.write(record / 'native-outcome.json', dict(returncode=0, stop_reason=None, usage=native.usage(root), raw_sha256=c.digest(record / 'science-output.json')))
        c.seal_result(root, step)
    monkeypatch.setattr(native, 'execute_native', complete)
    return calls


def keep_default(task):
    rows = task['closeout']['comparison']['rows'];default = task['closeout']['comparison']['default']['candidate_id']
    return dict(candidate_recommendation=None, candidate_comparison=dict(override=None, rows=[dict(candidate_id=row['candidate_id'],
        key_risk='Public proxy only', decision='keep' if row['candidate_id'] == default else 'replace') for row in rows]))


def leaf_phases(root):
    return sorted(path.name.split('-')[1] for path in (root / 'host-delivery/leaf-output').glob('*.json'))


def test_closeout_smoke_excludes_unloadable_public_best_and_null_delivers_default(tmp_path, monkeypatch):
    root = scene(tmp_path)
    calls = closeout_author(monkeypatch, keep_default)
    result = controller.closeout(root)
    assert result['status'] == 'delivery_confirmed', result
    screen = c.read(root / 'host-delivery/selection/screen.json')
    assert [(row['candidate_id'], row['reasons'], row['smoke']['status'], row['audit']['status']) for row in screen['rows']] == [
        ('run-1', ['top_k'], 'failed', 'not_run'), ('run-2', ['top_k'], 'ok', 'passed'), ('run-3', ['top_k', 'a_recommended'], 'ok', 'not_run')]
    assert screen['rows'][0]['smoke']['note'] == 'smoke_artifact_load_failed' and screen['rows'][2]['audit']['note'] == 'below_audited_default'
    assert screen['default'] == dict(candidate_id='run-2', basis='audit_passed', rule=selection.DEFAULT_RULE)
    assert result['last_confirmed']['candidate_id'] == 'run-2' and result['control_selection']['default'] == 'run-2'
    assert (root / 'submission/model.pkl').read_bytes() == (root / 'runs/model-2.pkl').read_bytes()
    (step, task), = calls
    view = task['closeout']['comparison']
    assert [row['candidate_id'] for row in view['rows']] == ['run-1', 'run-2', 'run-3'] and view['default']['candidate_id'] == 'run-2'
    assert set(view['rows'][0]) == {'candidate_id', 'public_metric', 'evaluation_version', 'comparable', 'rank', 'reasons', 'smoke', 'audit', 'default'}
    assert 'candidate_comparison' in task['final_response'] and 'host-delivery' not in json.dumps(task) and 'hidden' not in json.dumps(view)
    assert c.read(root / 'jobs' / f'{step:03d}.json')['selection'] == shortlist.marker(root)
    assert 'candidate_comparison' in c.read(c.host_record(c.workspace(root, step)) / 'science-result.schema.json')['properties']
    # Each control call is intent-before-outcome with host-only leaf output; counted as a bounded step.
    for name in ('smoke-00', 'smoke-01', 'smoke-02', 'audit-01'):
        outcome = c.read(root / 'host-delivery/selection' / (name + '.outcome.json'))
        assert outcome['cleanup_confirmed'] and outcome['leaf_output']
    assert shortlist.calls(root) == 4 and leaf_phases(root).count('smoke') == 3
    used = budget.used_steps(root)
    assert controller.closeout(root)['status'] == 'delivery_confirmed' and len(calls) == 1 and budget.used_steps(root) == used


def test_override_needs_symmetric_table_and_bound_reason_through_correction(tmp_path, monkeypatch):
    root = scene(tmp_path)
    rows = lambda keep, ids=('run-1', 'run-2', 'run-3'): [dict(candidate_id=cid, key_risk='Proxy only', decision='keep' if cid == keep else 'replace') for cid in ids]
    asymmetric = lambda task: dict(candidate_recommendation='run-3', candidate_comparison=dict(rows=rows('run-3', ('run-3',)), override=None))
    bound = lambda task: dict(candidate_recommendation='run-3', candidate_comparison=dict(rows=rows('run-3'),
        override=dict(default_candidate='run-2', chosen_candidate='run-3', reason='W002 run-3 is the simpler retained design', evidence_steps=[2])))
    calls = closeout_author(monkeypatch, asymmetric, bound)
    result = controller.closeout(root)
    assert result['status'] == 'delivery_confirmed' and result['last_confirmed']['candidate_id'] == 'run-3', result
    assert [step for step, _ in calls] == [4, 5]
    assert 'selection_comparison_asymmetric' in calls[1][1]['question']
    assert c.read(root / 'jobs/005.json')['selection'] == c.read(root / 'jobs/004.json')['selection']


def test_plugin_without_smoke_is_unavailable_never_ok(tmp_path, monkeypatch):
    root = scene(tmp_path)
    original = delivery.freeze_sources
    def undeclared(*args, **kwargs):
        refs = original(*args, **kwargs);refs.pop('capabilities');return refs
    monkeypatch.setattr(delivery, 'freeze_sources', undeclared)
    closeout_author(monkeypatch, keep_default)
    result = controller.closeout(root)
    screen = c.read(root / 'host-delivery/selection/screen.json')
    assert {row['smoke']['status'] for row in screen['rows']} == {'unavailable'} and screen['smoke_capability'] is False
    assert {row['audit']['note'] for row in screen['rows']} == {'smoke_not_ok'} and screen['default']['candidate_id'] is None
    assert result['status'] == 'closeout_unresolved' and result['reason'] == 'delivery_no_decision'
    assert shortlist.calls(root) == 0 and 'smoke' not in leaf_phases(root)


def test_uncertain_smoke_is_never_repeated_and_blocks_execution(tmp_path, monkeypatch):
    root = scene(tmp_path)
    def lost(*args, **kwargs):raise RuntimeError('Lost leaf process identity')
    monkeypatch.setattr(delivery, 'leaf_phase', lost)
    with pytest.raises(RuntimeError):controller.closeout(root)
    assert shortlist.blocked(root) and budget.execution_blocked(root)
    monkeypatch.setattr(delivery, 'leaf_phase', lambda *args, **kwargs: pytest.fail('Uncertain control call repeated'))
    assert controller.closeout(root)['status'] == 'selection_smoke_unknown'
    assert shortlist.calls(root) == 1 and not (root / 'jobs/004.json').exists()


def test_old_or_disabled_instance_keeps_original_closeout_without_table(tmp_path, monkeypatch):
    root = scene(tmp_path, policy=None)
    calls = closeout_author(monkeypatch, lambda task: dict(candidate_recommendation='run-1'))
    result = controller.closeout(root)
    assert result['status'] == 'delivery_confirmed' and result['last_confirmed']['candidate_id'] == 'run-1'
    assert 'comparison' not in calls[0][1]['closeout'] and 'candidate_comparison' not in calls[0][1]['final_response']
    assert not (root / 'host-delivery/selection').exists() and 'control_selection' not in result
    assert 'selection' not in c.read(root / 'jobs/004.json')


def test_tampered_screen_receipt_invalidates_the_bound_closeout(tmp_path, monkeypatch):
    root = scene(tmp_path)
    closeout_author(monkeypatch, keep_default)
    assert controller.closeout(root)['status'] == 'delivery_confirmed'
    path = root / 'host-delivery/selection/smoke-00.outcome.json';path.chmod(0o600)
    path.write_text(path.read_text().replace('"failed"', '"ok"'))
    with pytest.raises(ValueError, match='Control selection receipts changed'):
        c.validate(c.workspace(root, 4))
