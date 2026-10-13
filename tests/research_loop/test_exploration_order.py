"""Execute sealed scientific priorities without ranking science or forcing coverage."""
import copy
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import contracts as c, controller, history, native, search
from test_history_handoff import finish
from test_portfolio_review import P, Q, R, REQUEST, worker

S = 'h001.m4'
REASON = 'Deepen the observed branch because this comparison can change the scientific decision; retain the other opportunities.'


def plan(*, focus='P', priority=None, commitments=None):
    return dict(scope='Prioritize P then Q, R and S for discriminating value under the original goal.',
                commitments=commitments if commitments is not None else [
                    dict(label=label, minimal_test='A minimal decision-changing test', existing_ref=None)
                    for label in ('P', 'Q', 'R', 'S')],
                focus=dict(label=focus, action='screen'), exploration_order=priority)


def prepare(tmp_path, *, initial=None, action='experiment', enabled=True):
    public = tmp_path / 'public'
    public.mkdir(parents=True)
    goal = public / 'goal.md'
    goal.write_text('Compare declared mechanisms under the original constraints; keep independent checks.')
    root = tmp_path / 'instance'
    controller.prepare(root, goal, public, ['never-launched'], max_tokens=100_000, max_seconds=3600,
                       max_steps=64, model='fixture', reasoning_effort='high',
                       portfolio_policy=dict(review_after_cycles=3), exploration_order_version=1 if enabled else None)
    choice = initial if initial is not None else plan()
    if not enabled:
        choice = dict(choice)
        choice.pop('exploration_order', None)
    finish(root, 1, 'H', [], action=action, search_choice=choice)
    return root


def author(root, step, parents, *, focus=Q, mode='screen', priority=None, action='continue_w', dispositions=(), request=REQUEST):
    path = root / 'jobs' / f'{step:03d}.json'
    previous = c.read(path) if path.exists() else {}
    job = c.build_job(root, step, 'A', parents, instruction=previous.get('instruction', ''),
                      evidence_return=previous.get('evidence_return'), correction_request=previous.get('correction_request'),
                      author_correction=previous.get('author_correction'))
    review = dict(dispositions=list(dispositions), next_focus=dict(mechanism_ref=focus, action=mode) if focus else None)
    if job['handoff_protocol'] >= 13:
        review['exploration_order'] = priority
    payload = dict(summary='Scientific assessment of the current opportunity',
                   scientific_result='Assess the observed comparison while retaining target and validity limitations.',
                   limitations=['Unobserved target conditions remain unknown'], implementation_selection=None,
                   search_review=review, progress_assessment=dict(verdict='no_progress'), candidate_recommendation=None,
                   next_action=action, route_reason='Exact scientific question', decision_request=request, portfolio_review=None)
    record = c.host_record(c.workspace(root, step))
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(path)))
    c.write(record / 'science-output.json', payload)
    c.write(record / 'usage.json', dict(input_tokens=7, cached_input_tokens=2, output_tokens=3))
    c.write(record / 'native-outcome.json', dict(returncode=0, stop_reason=None, usage=native.usage(root),
                                              raw_sha256=c.digest(record / 'science-output.json')))
    c.seal_result(root, step)
    return job, payload


def refs(root, before):
    return [item['mechanism_ref'] for item in search.project(root, before)['order']['remaining']]


def parents(job):
    return [int(Path(row['path']).parts[2]) for row in job['direct_refs']]


@pytest.mark.parametrize('initial', [plan(focus='Q'), plan(priority=dict(priority=['unknown'], reason=REASON))])
def test_actual_initial_h_conflict_is_retained_and_returns_to_same_author_role(tmp_path, monkeypatch, initial):
    root = prepare(tmp_path, initial=initial)
    original = (c.host_record(c.workspace(root, 1)) / 'science-output.json').read_bytes()
    assert refs(root, 2) == [P, Q, R, S]
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        accepted.append(job['role'])
        if step == 2:
            assert job['role'] == 'H' and job['author_correction']['root']['step'] == 1
            finish(root, step, 'H', parents(job), action='experiment', search_choice=plan(focus=P, commitments=[]))
        else:
            assert step == 3 and job['role'] == 'W' and job['search']['order_head'] == dict(mechanism_ref=P, planned_step=1)
            c.write(root / 'pause.request', dict(reason='Stop after corrected scientific dispatch'))
            worker(root, step, parents(job))

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused' and accepted == ['H', 'W']
    assert (c.host_record(c.workspace(root, 1)) / 'science-output.json').read_bytes() == original
    assert controller.run(root)['status'] == 'paused' and accepted == ['H', 'W']


def test_scientific_reason_reschedules_screened_branch_for_improve_with_pending_alternatives(tmp_path):
    root = prepare(tmp_path)
    worker(root, 2, [1])
    job, _ = author(root, 3, [1, 2], focus=P, mode='improve', priority=dict(priority=[P], reason=REASON),
                    dispositions=[dict(mechanism_ref=P, status='screened', reason='The bound screen comparison completed')])
    state = search.project(root, 4)
    assert state['mechanisms'][P]['status'] == 'screened' and state['mechanisms'][Q]['status'] == 'pending'
    assert state['order']['remaining'][0] == dict(mechanism_ref=P, planned_step=3)
    assert len(state['portfolio']['seen_w']) == 1 and state['portfolio']['invested'] == {}
    assert c.read(c.host_record(c.workspace(root, 3)) / 'result-identity.json')['control_outcome']['order_status'] == 'applied'
    next_job = c.build_job(root, 4, 'W', [1, 2, 3], instruction='Exact scientific question')
    assert search.launch_reason(root, next_job) is None
    assert c.science_view(job, root)['lineage']['mechanisms']['exploration_order']['head'] == P


def test_actual_a_conflict_consumes_once_then_author_prefix_does_not_pop_reinserted_opportunity(tmp_path, monkeypatch):
    root = prepare(tmp_path)
    worker(root, 2, [1])
    original_job, _ = author(root, 3, [1, 2], focus=P, mode='improve')
    visible_order = c.science_view(original_job, root)['lineage']['mechanisms']['exploration_order']
    assert visible_order['head'] == P and 'precedes current A assessment' in visible_order['rule']
    assert 'resulting head' in visible_order['rule']  # P is shown before assessment, while Q is the remaining head.
    assert refs(root, 4) == [Q, R, S] and len(search.project(root, 4)['portfolio']['seen_w']) == 1
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        accepted.append(job['role'])
        if step == 4:
            assert job['role'] == 'A' and job['author_correction']['root']['step'] == 3
            author(root, step, parents(job), focus=P, mode='improve', priority=dict(priority=[P], reason=REASON))
            state = search.project(root, 5)
            assert state['order']['remaining'][0] == dict(mechanism_ref=P, planned_step=4)
            assert len(state['portfolio']['seen_w']) == 1
        else:
            assert step == 5 and job['role'] == 'W' and job['search']['order_head']['planned_step'] == 4
            c.write(root / 'pause.request', dict(reason='Stop after the newly scheduled opportunity'))
            worker(root, step, parents(job))

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused' and accepted == ['A', 'W']
    author(root, 6, [1, 5], focus=Q)
    assert refs(root, 7) == [Q, R, S] and len(search.project(root, 7)['portfolio']['seen_w']) == 2
    assert controller.run(root)['status'] == 'paused' and accepted == ['A', 'W']


@pytest.mark.parametrize('action', ['audit', 'extract'])
def test_actual_a_deferred_actions_and_return_assess_original_w_once_without_reordering(tmp_path, monkeypatch, action):
    root = prepare(tmp_path)
    worker(root, 2, [1])
    author(root, 3, [1, 2], focus=S, action=action, priority=dict(priority=[S], reason=REASON),
           request=REQUEST if action == 'extract' else None)
    assert refs(root, 4) == [P, Q, R, S]
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        accepted.append(job['role'])
        if job['role'] == 'E':
            finish(root, step, 'E', parents(job), text='A bounded independent finding')
        else:
            assert job['role'] == 'A' and 2 in parents(job)
            c.write(root / 'pause.request', dict(reason='Stop after the original scientific assessment'))
            author(root, step, parents(job), focus=Q)

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused'
    assert accepted == (['A'] if action == 'audit' else ['E', 'A'])
    cutoff = max(int(path.stem) for path in (root / 'jobs').glob('*.json')) + 1
    assert refs(root, cutoff) == [Q, R, S]
    assert len(search.project(root, cutoff)['portfolio']['seen_w']) == 1


def test_repair_keeps_original_opportunity_until_scientific_assessment_finishes_it(tmp_path):
    root = prepare(tmp_path)
    worker(root, 2, [1])
    author(root, 3, [1, 2], focus=P, mode='repair')
    assert refs(root, 4) == [P, Q, R, S]
    repair = c.build_job(root, 4, 'W', [1, 2, 3], instruction='Exact scientific question')
    assert repair['search']['repair_root'] == 2 and repair['search']['order_head'] == dict(mechanism_ref=P, planned_step=1)
    worker(root, 4, [1, 2, 3])
    assert refs(root, 5) == [P, Q, R, S]
    author(root, 5, [1, 4], focus=Q)
    assert refs(root, 6) == [Q, R, S]
    assert len(search.project(root, 6)['portfolio']['seen_w']) == 2


@pytest.mark.parametrize('priority', [dict(priority=['unknown'], reason=REASON), dict(priority=[Q, Q], reason=REASON)])
def test_bad_prefix_preserves_partial_science_and_every_unlisted_tail_item(tmp_path, priority):
    root = prepare(tmp_path)
    worker(root, 2, [1])
    job, payload = author(root, 3, [1, 2], priority=priority,
                          dispositions=[dict(mechanism_ref=S, status='deferred', reason='Explicit scientific deferral')])
    state = search.project(root, 4)
    assert state['mechanisms'][S]['status'] == 'deferred' and refs(root, 4) == [Q, R, S]
    seal = c.read(c.host_record(c.workspace(root, 3)) / 'result-identity.json')
    assert seal['control_outcome']['search_status'] == 'applied' and seal['control_outcome']['order_status'] == 'unresolved'
    assert c.validate(c.workspace(root, 3))['scientific_result'] == payload['scientific_result']
    planned = c.build_job(root, 4, 'W', [1, 2, 3], instruction='Exact scientific question')
    assert search.launch_reason(root, planned) == 'order_priority_unresolved'


def test_actual_a_to_h_to_w_preserves_order_and_h_conflict_is_bounded_author_correction(tmp_path, monkeypatch):
    root = prepare(tmp_path)
    worker(root, 2, [1])
    author(root, 3, [1, 2], focus=P, action='revise_h')
    assert refs(root, 4) == [Q, R, S]
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        accepted.append(job['role'])
        if step == 4:
            assert job['role'] == 'H'
            finish(root, step, 'H', parents(job), action='experiment', search_choice=plan(focus=P, commitments=[]))
        elif step == 5:
            assert job['role'] == 'H' and job['author_correction']['root']['step'] == 4
            finish(root, step, 'H', parents(job), action='experiment', search_choice=plan(focus=Q, commitments=[]))
        else:
            assert step == 6 and job['role'] == 'W' and job['search']['focus']['mechanism_ref'] == Q
            c.write(root / 'pause.request', dict(reason='Stop at the confirmed scientific head'))
            worker(root, step, parents(job))

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused' and accepted == ['H', 'H', 'W']
    assert refs(root, 7) == [Q, R, S]


def test_h_can_confirm_order_before_e_but_e_does_not_consume_an_opportunity(tmp_path, monkeypatch):
    root = prepare(tmp_path, action='extract', initial=plan(priority=dict(priority=['Q', 'P'], reason=REASON), focus='Q'))
    assert refs(root, 2) == [Q, P, R, S]
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        accepted.append(job['role'])
        if step == 2:
            finish(root, step, 'E', parents(job), text='Bounded evidence for the confirmed H priorities')
        elif step == 3:
            finish(root, step, 'H', parents(job), action='experiment', search_choice=plan(focus=Q, commitments=[]))
        else:
            assert step == 4 and job['role'] == 'W' and job['search']['focus']['mechanism_ref'] == Q
            c.write(root / 'pause.request', dict(reason='Stop at the confirmed head after E'))
            worker(root, step, parents(job))

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused' and accepted == ['E', 'H', 'W']
    assert refs(root, 5) == [Q, P, R, S] and search.project(root, 5)['portfolio']['seen_w'] == set()


def test_old_twelve_bytes_and_pending_improve_gate_are_unchanged(tmp_path):
    root = prepare(tmp_path, enabled=False)
    worker(root, 2, [1])
    job, _ = author(root, 3, [1, 2], focus=P, mode='improve')
    paths = [root / 'settings.json', root / 'jobs/003.json', c.workspace(root, 3) / 'science-task.json',
             c.host_record(c.workspace(root, 3)) / 'science-result.schema.json',
             c.host_record(c.workspace(root, 3)) / 'result-identity.json']
    original = {path: path.read_bytes() for path in paths}
    assert 'exploration_order' not in c.result_schema('H', 12)['properties']['search_plan']['properties']
    assert c.build_job(root, 3, 'A', [1, 2]) == job and c.validate(c.workspace(root, 3))
    assert all(path.read_bytes() == data for path, data in original.items())
    future = c.build_job(root, 4, 'W', [1, 2, 3], instruction='Exact scientific question')
    assert future['handoff_protocol'] == 12 and search.launch_reason(root, future) == 'search_commitments_pending'


def test_full_order_index_bounded_brief_and_tamper_guard(tmp_path):
    root = prepare(tmp_path, action='analyze')
    for step in range(2, 6):
        c.build_job(root, step, 'H', [step - 1], instruction='Exact scientific question')
        additions = [dict(label='机' * 20 + f'{step}-{index}', minimal_test='测' * 80, existing_ref=None) for index in range(4)]
        finish(root, step, 'H', [step - 1], action='analyze', search_choice=plan(focus=P, commitments=additions))
    job = c.build_job(root, 6, 'A', [5])
    view = c.read(c.workspace(root, 6) / 'science-task.json')
    assert view == c.science_view(job, root)
    brief = view['lineage']
    assert len((json.dumps(brief, ensure_ascii=False, indent=2) + '\n').encode()) <= history.MAX_BRIEF_BYTES
    order = brief['mechanisms']['exploration_order']
    assert order['head'] == P and order['remaining_count'] == 20
    assert len(order['remaining']) + order['omitted_count'] == 20 and 1 <= len(order['remaining']) <= 4
    path = order['index']
    items = []
    while path:
        original = c.workspace(root, 6) / path
        assert original.stat().st_mode & 0o222 == 0 and original.stat().st_size <= history.MAX_PAGE_BYTES
        page = c.read(original)
        items.extend(page['opportunities'])
        path = page['next_page']
    assert len(items) == 20 and [item['mechanism_ref'] for item in items[:4]] == [P, Q, R, S]
    assert 'planned_step' not in json.dumps(items) and 'sha256' not in json.dumps(order)
    original.chmod(0o600)
    original.write_text('{}\n')
    with pytest.raises(ValueError):
        c._validate_inputs(root, c.workspace(root, 6), job)
