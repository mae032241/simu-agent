"""Unserved commitments need a scientific tradeoff, not host scientific ranking."""
import copy
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import contracts as c, controller, guidance, history, native, search
from test_history_handoff import finish
from test_portfolio_review import P, Q, R, REQUEST, TRADEOFF, author, prepare, worker

S = 'h001.m4'


def three_branches(tmp_path, *, version=2):
    root = prepare(tmp_path, threshold=3, version=version)
    author(root, 3, [1, 2], branch=Q)
    worker(root, 4, [1, 2, 3])
    author(root, 5, [1, 4], branch=R)
    worker(root, 6, [1, 4, 5])
    return root


@pytest.mark.parametrize('branch,review,required', [(R, None, True), (S, None, False), (R, TRADEOFF, False)])
def test_p_q_r_cannot_indefinitely_skip_s_but_selection_or_explanation_can_continue(tmp_path, branch, review, required):
    root = three_branches(tmp_path)
    job, payload = author(root, 7, [1, 6], branch=branch, portfolio=review)
    assert job['handoff_protocol'] == 12 and c.settings(root)['portfolio_policy']['version'] == 2
    diagnostics = search.portfolio_assess(root, job, payload)
    assert bool(diagnostics) is required
    if required:
        assert diagnostics == [dict(code='a_portfolio_review_required', subject=R)]
    seal = c.read(c.host_record(c.workspace(root, 7)) / 'result-identity.json')
    assert seal['control_outcome']['portfolio_status'] == ('unresolved' if required else 'applied')
    state = search.project(root, 8)['portfolio']
    assert len(state['seen_w']) == 3 and state['pending_w'] is None
    if review:
        assert state['deferred'] == {}
    else:
        assert state['deferred'][S] == 3


def test_selecting_one_overdue_commitment_is_not_blocked_by_another_overdue_commitment():
    mechanisms = {ref: dict(status='deferred') for ref in (P, Q, R, S)}
    portfolio = dict(last_branch=R, invested={P: 1, Q: 1, R: 1}, deferred={P: 3, S: 3})
    assert not search.portfolio_due(portfolio, mechanisms, S, 3, version=2)
    assert search.portfolio_due(portfolio, mechanisms, R, 3, version=2)
    waived = copy.deepcopy(mechanisms)
    waived[P]['status'] = waived[S]['status'] = 'waived'
    assert not search.portfolio_due(portfolio, waived, R, 3, version=2)


def test_real_controller_author_review_retains_r_and_renews_finite_window_without_recount(tmp_path, monkeypatch):
    root = three_branches(tmp_path)
    author(root, 7, [1, 6], branch=R)
    record = c.host_record(c.workspace(root, 7))
    original = (record / 'science-output.json').read_bytes()
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        parents = [int(Path(ref['path']).parts[2]) for ref in job['direct_refs']]
        accepted.append((step, job['role']))
        if step == 8:
            assert job['role'] == 'A' and job['author_correction']['root']['step'] == 7
            author(root, step, parents, branch=R, portfolio=TRADEOFF)
            state = search.project(root, 9)['portfolio']
            assert len(state['seen_w']) == 3 and state['pending_w'] is None
            assert state['invested'] == state['deferred'] == {}
        else:
            assert step == 9 and job['role'] == 'W' and job['search']['focus']['mechanism_ref'] == R
            c.write(root / 'pause.request', dict(reason='Stop after the explained allocation'))
            worker(root, step, parents)

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused'
    assert accepted == [(8, 'A'), (9, 'W')]
    assert (record / 'science-output.json').read_bytes() == original
    assert controller.run(root)['status'] == 'paused' and accepted == [(8, 'A'), (9, 'W')]
    author(root, 10, [1, 9], branch=R)
    worker(root, 11, [1, 9, 10])
    author(root, 12, [1, 11], branch=R)
    worker(root, 13, [1, 11, 12])
    job, payload = author(root, 14, [1, 13], branch=R)
    assert search.portfolio_assess(root, job, payload)
    assert len(search.project(root, 15)['portfolio']['seen_w']) == 6


@pytest.mark.parametrize('action', ['audit', 'extract'])
def test_actual_audit_or_e_return_does_not_reset_delay_or_count_w_twice(tmp_path, monkeypatch, action):
    root = three_branches(tmp_path)
    author(root, 7, [1, 6], branch=R, action=action,
           request=REQUEST if action == 'extract' else None, portfolio=TRADEOFF)
    before = search.project(root, 8)['portfolio']
    assert len(before['seen_w']) == 2 and before['pending_w']['step'] == 6
    assert before['deferred'][S] == 2 and before['last_review'] is None
    accepted = []

    def execute(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        parents = [int(Path(ref['path']).parts[2]) for ref in job['direct_refs']]
        accepted.append(job['role'])
        if job['role'] == 'E':
            finish(root, step, 'E', parents, text='An independently requested bounded finding')
        else:
            assert job['role'] == 'A' and 6 in parents
            c.write(root / 'pause.request', dict(reason='Stop after assessing the original W'))
            author(root, step, parents, branch=S)

    monkeypatch.setattr(native, 'execute_native', execute)
    assert controller.run(root)['status'] == 'paused'
    assert accepted == (['A'] if action == 'audit' else ['E', 'A'])
    cutoff = max(int(path.stem) for path in (root / 'jobs').glob('*.json')) + 1
    after = search.project(root, cutoff)['portfolio']
    assert len(after['seen_w']) == 3 and after['pending_w'] is None
    assert after['deferred'][S] == 3 and after['last_review'] is None
    assert controller.run(root)['status'] == 'paused'
    assert len(search.project(root, cutoff)['portfolio']['seen_w']) == 3


def test_h_revision_rename_and_omission_preserve_unserved_commitment(tmp_path):
    root = three_branches(tmp_path)
    author(root, 7, [1, 6], branch=R, action='revise_h', dispositions=[
        dict(mechanism_ref=S, status='deferred', reason='Same scientific deferral remains unresolved')])
    assert search.project(root, 8)['portfolio']['deferred'][S] == 3
    c.build_job(root, 8, 'H', [1, 6, 7], instruction='Exact scientific question')
    finish(root, 8, 'H', [1, 6, 7], action='experiment', search_choice=dict(
        scope='Retain original constraints and explain prioritization',
        commitments=[dict(label='Renamed S', minimal_test='Original discriminating comparison', existing_ref=S)],
        focus=dict(label=R, action='screen')))
    assert search.project(root, 9)['mechanisms'][S]['label'] == 'Renamed S'
    assert search.project(root, 9)['portfolio']['deferred'][S] == 3
    # H experiment keeps its scientific authority; this version gates A continue_w.
    worker(root, 9, [8])
    job, payload = author(root, 10, [8, 9], branch=R)
    assert search.portfolio_assess(root, job, payload)
    assert search.project(root, 11)['portfolio']['deferred'][S] == 4


def test_actual_brief_separates_completed_and_pending_and_preserves_full_readonly_index(tmp_path):
    root = three_branches(tmp_path)
    job = c.build_job(root, 7, 'A', [1, 6])
    work = c.workspace(root, 7)
    view = c.read(work / 'science-task.json')
    assert view == c.science_view(job, root)
    brief = view['lineage']
    assert len((json.dumps(brief, ensure_ascii=False, indent=2) + '\n').encode()) <= history.MAX_BRIEF_BYTES
    mechanism_view = brief['mechanisms']
    portfolio = mechanism_view['portfolio']
    assert portfolio['version'] == 2 and portfolio['pending_assessment'] is True
    assert portfolio['review_after_cycles'] == 3 and portfolio['overdue_count_if_assessed'] == 1
    assert portfolio['completed_cycles'] == 0 and portfolio['cycles_if_assessed'] == 1
    assert portfolio['review_required_for_non_overdue_selection'] is True
    assert 0 < len(mechanism_view['overview']) <= 4
    assert len(mechanism_view['overview']) + mechanism_view['overview_omitted_count'] == 4
    rows = {row['mechanism_ref']: row for row in mechanism_view['overview']}
    assert S in rows  # The due commitment remains visible even when other rows are trimmed.
    assert rows[S]['deferred_cycles_in_window'] == 2 and rows[S]['deferred_cycles_if_assessed'] == 3
    page_path = work / mechanism_view['index']
    assert page_path.stat().st_mode & 0o222 == 0
    assert {row['mechanism_ref'] for row in c.read(page_path)['mechanisms']} == {P, Q, R, S}
    page_path.chmod(0o600)
    page_path.write_text('{}\n')
    with pytest.raises(ValueError):
        c._validate_inputs(root, work, job)


def test_old_eleven_schema_views_and_future_jobs_keep_original_same_branch_semantics(tmp_path):
    root = three_branches(tmp_path, version=1)
    job, payload = author(root, 7, [1, 6], branch=R)
    assert job['handoff_protocol'] == 11 and 'version' not in c.settings(root)['portfolio_policy']
    assert search.portfolio_assess(root, job, payload) == []
    assert 'review_due_for_same_branch' in c.science_view(job, root)['lineage']['mechanisms']['portfolio']
    paths = [root / 'settings.json', root / 'jobs/007.json', c.workspace(root, 7) / 'science-task.json',
             c.host_record(c.workspace(root, 7)) / 'science-result.schema.json',
             c.host_record(c.workspace(root, 7)) / 'result-identity.json']
    original = {path: path.read_bytes() for path in paths}
    assert c.build_job(root, 7, 'A', [1, 6]) == job
    c.validate(c.workspace(root, 7))
    assert all(path.read_bytes() == data for path, data in original.items())
    future = c.build_job(root, 8, 'W', [1, 6, 7], instruction='Exact scientific question')
    assert future['handoff_protocol'] == 11 and future['role_guidance'] == guidance.DEFAULT['W']


@pytest.mark.parametrize('custom', [False, True])
def test_new_real_task_guidance_is_frozen_domain_suffix_survives_and_custom_text_is_not_rewritten(tmp_path, custom):
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Original scientific goal and mandatory independent checks')
    domain = ' Configured experiment tools select a new plan or exact parent; query uncertain calls before further work.'
    advice = dict(guidance.OPPORTUNITY)
    if custom:
        advice = {role: f'Custom scientific permissions for {role}; preserve original constraints.' for role in advice}
    advice['W'] += domain
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000, max_seconds=3600,
                       max_steps=16, model='fixture', reasoning_effort='high', role_guidance=advice,
                       portfolio_policy=dict(review_after_cycles=3))
    plan = dict(scope='Prioritized falsifiable solutions', commitments=[
        dict(label='P', minimal_test='Cheap decision-changing comparison', existing_ref=None)],
        focus=dict(label='P', action='screen'))
    finish(root, 1, 'H', [], action='experiment', search_choice=plan)
    job = c.build_job(root, 2, 'W', [1], instruction='Exact scientific question')
    actual = c.read(c.workspace(root, 2) / 'science-task.json')
    assert actual['role_guidance'] == job['native_role_instruction'] == advice['W']
    assert actual['role_guidance'].endswith(domain)
    assert sum(len(value.encode()) for value in guidance.OPPORTUNITY.values()) + 200 <= guidance.MAX_BYTES
    assert c.settings(root)['role_guidance'] == advice
    assert c.build_job(root, 2, 'W', [1], instruction='Exact scientific question') == job
