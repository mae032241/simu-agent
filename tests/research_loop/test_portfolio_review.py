"""Finite global portfolio reconsideration, without scientific value classification."""
import copy
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import contracts as c, controller, decision, history, native, search
from test_history_handoff import finish

P, Q, R = 'h001.m1', 'h001.m2', 'h001.m3'
TRADEOFF = 'Retain the current branch for its decision value; remaining commitments remain unresolved under the original constraints.'
REQUEST = dict(decision='mechanism', question='Which declared mechanism should receive the next scientific comparison?',
               change_criterion='A controlled contradiction would change the mechanism choice.')


def prepare(tmp_path, *, threshold=2, enabled=True):
    public = tmp_path / 'public'; public.mkdir(parents=True)
    objective = public / 'objective.md'; objective.write_text('Judge the whole committed mechanism portfolio without abandoning original constraints.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000, max_seconds=3600,
        max_steps=64, model='fixture', reasoning_effort='high', decision_contract_version=1,
        portfolio_policy=dict(review_after_cycles=threshold) if enabled else None)
    plan = dict(scope='Competing solutions', commitments=[dict(label=label, minimal_test='A discriminating comparison', existing_ref=None)
                for label in ('P', 'Q', 'R', 'S')], focus=dict(label='P', action='screen'))
    finish(root, 1, 'H', [], action='experiment', search_choice=plan)
    worker(root, 2, [1])
    return root


def worker(root, step, parents):
    c.build_job(root, step, 'W', parents, instruction='Exact scientific question')
    finish(root, step, 'W', parents, text=f'Distinct observed scientific comparison at W{step}; target uncertainty remains.')


def author(root, step, parents, *, branch=P, portfolio=None, action='continue_w', request=REQUEST, dispositions=()):
    path = root / 'jobs' / f'{step:03d}.json'
    previous = c.read(path) if path.exists() else {}
    job = c.build_job(root, step, 'A', parents, instruction=previous.get('instruction', ''),
                      author_correction=previous.get('author_correction'))
    record = c.host_record(c.workspace(root, step))
    payload = dict(summary='Global portfolio judgment', scientific_result='Retain scientific limitations while choosing the next direction.',
        limitations=['Unobserved target performance is unknown'], implementation_selection=None,
        search_review=dict(dispositions=list(dispositions), next_focus=dict(mechanism_ref=branch, action='screen')),
        progress_assessment=dict(verdict='no_progress'), candidate_recommendation=None,
        next_action=action, route_reason='Exact scientific question', decision_request=request)
    if job['handoff_protocol'] >= 11:
        payload['portfolio_review'] = portfolio
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs' / f'{step:03d}.json')))
    c.write(record / 'science-output.json', payload)
    c.write(record / 'usage.json', dict(input_tokens=7, cached_input_tokens=2, output_tokens=3))
    c.write(record / 'native-outcome.json', dict(returncode=0, stop_reason=None, usage=native.usage(root),
                                             raw_sha256=c.digest(record / 'science-output.json')))
    c.seal_result(root, step)
    return job, payload


def two_cycles(root, *, action='continue_w', branch=P, portfolio=None):
    author(root, 3, [1, 2])
    worker(root, 4, [1, 2, 3])
    return author(root, 5, [1, 4], action=action, branch=branch, portfolio=portfolio)


def test_real_controller_requires_tradeoff_then_allows_same_branch_without_recount(tmp_path, monkeypatch):
    root = prepare(tmp_path)
    job, payload = two_cycles(root)
    raw = (c.host_record(c.workspace(root, 5)) / 'science-output.json').read_bytes()
    view = c.science_view(job, root)['lineage']['mechanisms']
    assert view['portfolio']['completed_cycles'] == 1
    assert view['portfolio']['cycles_if_assessed'] == 2 and view['portfolio']['pending_assessment'] is True
    assert view['portfolio']['review_due_for_same_branch'] is True
    assert len(view['overview']) == 4 and view['overview_omitted_count'] == 0 and view['index']
    assert c.read(c.host_record(c.workspace(root, 5)) / 'result-identity.json')['control_outcome']['portfolio_status'] == 'unresolved'
    accepted = []
    def execute(root, step):
        current = c.read(root / 'jobs' / f'{step:03d}.json')
        parents = [int(Path(ref['path']).parts[2]) for ref in current['direct_refs']]
        accepted.append((step, current['role']))
        if step == 6:
            assert current['role'] == 'A' and current['author_correction']['root']['step'] == 5
            author(root, step, parents, portfolio=TRADEOFF)
            state = search.project(root, 7)['portfolio']
            assert state['invested'] == {} and state['deferred'] == {} and state['pending_w'] is None
            assert len(state['seen_w']) == 2
        else:
            assert step == 7 and current['role'] == 'W' and current['search']['focus']['mechanism_ref'] == P
            c.write(root / 'pause.request', dict(reason='Stop fixture after accepted same-branch work'))
            worker(root, step, parents)
    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused'
    assert accepted == [(6, 'A'), (7, 'W')]
    assert (c.host_record(c.workspace(root, 5)) / 'science-output.json').read_bytes() == raw
    author(root, 8, [1, 7])
    worker(root, 9, [1, 7, 8])
    renewed, result = author(root, 10, [1, 9])
    assert decision.reason(root, renewed, result) == 'a_portfolio_review_required'
    assert controller.run(root)['status'] == 'paused' and accepted == [(6, 'A'), (7, 'W')]


@pytest.mark.parametrize('action,branch', [('continue_w', Q), ('revise_h', P), ('audit', P), ('extract', P)])
def test_switch_revision_audit_or_extraction_is_not_forced_to_review(tmp_path, action, branch):
    root = prepare(tmp_path)
    job, payload = two_cycles(root, action=action, branch=branch)
    assert search.portfolio_assess(root, job, payload) == []
    state = search.project(root, 6)['portfolio']
    if action in {'audit', 'extract'}:
        assert state['last_review'] is None and state['invested'][P] == 1
    else:
        assert state['invested'][P] == 2


@pytest.mark.parametrize('action', ['audit', 'extract'])
def test_actual_audit_or_e_return_route_consumes_original_w_only_once(tmp_path, monkeypatch, action):
    root = prepare(tmp_path, threshold=3)
    author(root, 3, [1, 2], action=action, request=REQUEST if action == 'extract' else None, portfolio=TRADEOFF)
    accepted = []
    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        parents = [int(Path(ref['path']).parts[2]) for ref in job['direct_refs']]
        accepted.append(job['role'])
        if job['role'] == 'E':
            finish(root, step, 'E', parents, text='Exact requested public evidence')
        else:
            assert job['role'] == 'A' and 2 in parents
            c.write(root / 'pause.request', dict(reason='Stop after one assessed W'))
            author(root, step, parents)
    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused'
    assert accepted == (['A'] if action == 'audit' else ['E', 'A'])
    state = search.project(root, max(int(p.stem) for p in (root / 'jobs').glob('*.json')) + 1)['portfolio']
    assert state['invested'][P] == 1 and len(state['seen_w']) == 1 and state['pending_w'] is None
    assert state['last_review'] is None  # A audit/extract prose never renewed the window.
    assert controller.run(root)['status'] == 'paused' and len(state['seen_w']) == 1


def test_qualified_author_finishes_original_cycle_and_review_prevents_h_analyze_recount(tmp_path, monkeypatch):
    root = prepare(tmp_path, threshold=1)
    author(root, 3, [1, 2], request=None)
    assert search.project(root, 4)['portfolio']['pending_w']['step'] == 2
    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        assert step == 4 and job['role'] == 'A'
        parents = [int(Path(ref['path']).parts[2]) for ref in job['direct_refs']]
        c.write(root / 'pause.request', dict(reason='Stop after bounded author resolution'))
        author(root, step, parents, action='revise_h', portfolio=TRADEOFF)
    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused'
    state = search.project(root, 5)['portfolio']
    assert len(state['seen_w']) == 1 and state['pending_w'] is None and state['invested'] == {}
    c.build_job(root, 5, 'H', [1, 2, 4], instruction='Exact scientific question')
    finish(root, 5, 'H', [1, 2, 4], action='analyze', search_choice=dict(scope='Reconsider target solution', commitments=[], focus=dict(label=P,action='screen')))
    author(root, 6, [5, 2], action='revise_h')
    assert len(search.project(root, 7)['portfolio']['seen_w']) == 1
    assert search.project(root, 7)['portfolio']['invested'] == {}


def test_same_status_omissions_and_existing_ref_rename_do_not_erase_window_deferral(tmp_path):
    root = prepare(tmp_path)
    author(root, 3, [1, 2], dispositions=[dict(mechanism_ref=Q,status='deferred',reason='A scientific tradeoff')])
    worker(root, 4, [1, 2, 3])
    author(root, 5, [1, 4], action='revise_h', dispositions=[dict(mechanism_ref=Q,status='deferred',reason='Same-status prose is not a reset')])
    c.build_job(root, 6, 'H', [1, 4, 5], instruction='Exact scientific question')
    finish(root, 6, 'H', [1, 4, 5], action='experiment', search_choice=dict(scope='Original portfolio remains',
        commitments=[dict(label='Renamed Q',minimal_test='Same discriminating test',existing_ref=Q)], focus=dict(label=P,action='screen')))
    state = search.project(root, 7)
    assert state['mechanisms'][Q]['label'] == 'Renamed Q' and state['portfolio']['deferred'][Q] == 2
    worker(root, 7, [6])
    job, payload = author(root, 8, [6, 7])
    assert search.portfolio_assess(root, job, payload)[0]['code'] == 'a_portfolio_review_required'


def test_cumulative_p_q_p_and_waiver_use_existing_scientific_status(tmp_path):
    root = prepare(tmp_path)
    author(root, 3, [1, 2], branch=Q)
    worker(root, 4, [1, 2, 3])
    author(root, 5, [1, 4], branch=P)
    worker(root, 6, [1, 4, 5])
    job, payload = author(root, 7, [1, 6])
    assert search.project(root, 8)['portfolio']['invested'][P] == 2
    assert search.portfolio_assess(root, job, payload)[0]['code'] == 'a_portfolio_review_required'
    # Waive is a scientific decision with a reason; no host judgment or forced experiment.
    alternative = copy.deepcopy(payload)
    alternative['search_review']['dispositions'] = [dict(mechanism_ref=ref,status='waived',reason='Scientifically outside the retained objective scope')
                                                    for ref in (Q, R, 'h001.m4')]
    assert search.portfolio_assess(root, job, alternative) == []


def test_many_mechanisms_bounded_default_complete_index_and_page_tamper(tmp_path):
    root = prepare(tmp_path)
    author(root, 3, [1, 2], action='revise_h')
    # H delta declarations add 16 more mechanisms without restating earlier commitments.
    last = 3
    for step in range(4, 8):
        c.build_job(root, step, 'H', [last], instruction='Exact scientific question')
        finish(root, step, 'H', [last], action='analyze', search_choice=dict(scope='Global portfolio',
            commitments=[dict(label='机' * 70 + f'{step}-{i}',minimal_test='测' * 150,existing_ref=None) for i in range(4)],
            focus=dict(label=P,action='screen')))
        last = step
    job = c.build_job(root, 8, 'A', [7])
    view = c.science_view(job, root)['lineage']
    assert len((json.dumps(view,ensure_ascii=False,indent=2)+'\n').encode()) <= history.MAX_BRIEF_BYTES
    assert len(view['mechanisms']['overview']) <= 4
    assert view['mechanisms']['overview_omitted_count'] == 20 - len(view['mechanisms']['overview'])
    path = view['mechanisms']['index']; rows=[]
    while path:
        page_path=c.workspace(root,8)/path
        assert page_path.stat().st_mode & 0o222 == 0
        page=c.read(page_path);rows.extend(page['mechanisms']);path=page['next_page']
    assert len(rows)==20 and all('deferred_cycles_in_window' in row for row in rows)
    page_path.chmod(0o600);page_path.write_text('{}\n')
    with pytest.raises(ValueError):c._validate_inputs(root,c.workspace(root,8),job)


def test_old_ten_prepared_tasks_schema_and_future_tasks_do_not_upgrade(tmp_path):
    root = prepare(tmp_path, enabled=False)
    job, _ = author(root, 3, [1, 2], action='wait')
    assert job['handoff_protocol'] == 10 and 'portfolio_review' not in c.result_schema('A',10)['properties']
    paths=[root/'settings.json',root/'jobs/003.json',c.workspace(root,3)/'science-task.json',
           c.host_record(c.workspace(root,3))/'science-result.schema.json',c.host_record(c.workspace(root,3))/'result-identity.json']
    original={path:path.read_bytes() for path in paths}
    assert c.build_job(root,3,'A',[1,2]) == job
    assert all(path.read_bytes()==raw for path,raw in original.items())
    assert c.build_job(root,4,'H',[3])['handoff_protocol'] == 10
    assert 'portfolio' not in c.science_view(job,root)['lineage']['mechanisms']


@pytest.mark.parametrize('bad', [None, 0])
def test_portfolio_requires_model_visible_unified_layout(tmp_path, bad):
    public=tmp_path/'public';public.mkdir();objective=public/'objective';objective.write_text('Original goal')
    with pytest.raises(ValueError,match='unified lineage'):
        controller.prepare(tmp_path/'instance',objective,public,['never-launched'],max_tokens=1000,max_seconds=60,
            max_steps=8,model='fixture',reasoning_effort='high',lineage_projection_version=bad,
            portfolio_policy=dict(review_after_cycles=3))
    assert not (tmp_path/'instance').exists()
