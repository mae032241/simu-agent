"""Retired priority option rejection and current unfinished-plan index originals."""
import json

import pytest

from scidiscovery.research_loop import contracts as c, controller, history, protocol, search
from test_history_handoff import finish


def test_retired_author_priority_option_rejects_before_creating_instance(tmp_path):
    public = tmp_path / 'public'; public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Keep explicit scientific choices and unfinished comparisons.')
    original = objective.read_bytes()
    root = tmp_path / 'instance'
    with pytest.raises(ValueError, match='Author priority-table strategy is retired'):
        controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000,
            max_seconds=3600, max_steps=16, model='fixture', reasoning_effort='high',
            exploration_order_version=1)
    assert not root.exists()
    assert objective.read_bytes() == original


def test_current_unfinished_plan_complete_index_is_bounded_readonly_and_tamper_checked(tmp_path):
    public = tmp_path / 'public'; public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Retain all unfinished mechanisms and their original limitations.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000,
        max_seconds=3600, max_steps=16, model='fixture', reasoning_effort='high',
        search_policy=search.DEFAULT_POLICY)
    expected = []
    # Bounded current H declarations exercise index publication without W observations.
    for step in range(1, 6):
        additions = [dict(label=f'{step}-{index}-' + '机' * 20, minimal_test='测' * 80, existing_ref=None)
                     for index in range(4)]
        finish(root, step, 'H', [step - 1] if step > 1 else [], action='analyze',
            search_choice=dict(scope='Preserve independent unfinished comparisons', commitments=additions,
                               focus=dict(label=None, action='screen')))
        expected.extend(f'h{step:03d}.m{index}' for index in range(1, 5))
    job = c.build_job(root, 6, 'A', [5])
    assert job['handoff_protocol'] == protocol.CURRENT
    assert 'exploration_order_version' not in c.settings(root)
    work = c.workspace(root, 6)
    view = c.read(work / 'science-task.json')
    assert view == c.science_view(job, root)
    brief = view['lineage']
    assert len((json.dumps(brief, ensure_ascii=False, indent=2) + '\n').encode()) <= history.MAX_BRIEF_BYTES
    plan = brief['mechanisms']['unfinished_plan']
    assert plan['remaining_count'] == 20
    assert len(plan['remaining']) + plan['omitted_count'] == 20
    assert 1 <= len(plan['remaining']) <= 4
    path, items, pages = plan['index'], [], []
    while path:
        original = work / path
        assert original.stat().st_mode & 0o222 == 0
        assert original.stat().st_size <= history.MAX_PAGE_BYTES
        page = c.read(original)
        items.extend(page['opportunities'])
        pages.append(original)
        path = page['next_page']
    assert len(pages) == 2
    assert [item['mechanism_ref'] for item in items] == expected
    assert all((work / item['original']).is_file() for item in items)
    assert 'planned_step' not in json.dumps(items) and 'sha256' not in json.dumps(plan)
    c._validate_inputs(root, work, job)
    pages[-1].chmod(0o600)
    pages[-1].write_text('{}\n')
    with pytest.raises(ValueError):
        c._validate_inputs(root, work, job)


def test_disposition_previews_retain_all_mechanisms_and_reach_full_a_reasons(tmp_path):
    public = tmp_path / 'public'; public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Preserve the scientific reasons for deferred and excluded mechanisms.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000,
        max_seconds=3600, max_steps=8, model='fixture', reasoning_effort='high',
        portfolio_policy=dict(review_after_cycles=3))
    commitments = [dict(label=f'Mechanism {index}', minimal_test='A discriminating question', existing_ref=None)
        for index in range(1, 8)]
    finish(root, 1, 'H', [], action='analyze', search_choice=dict(scope='Competing mechanisms',
        commitments=commitments, focus=None))
    dispositions = [dict(mechanism_ref=f'h001.m{index}', status='deferred' if index % 2 else 'waived',
        reason='反证条件与局限。' * 700 if index == 1 else f'Original scientific reason {index}')
        for index in range(1, 8)]
    finish(root, 2, 'A', [1], action='finish', search_choice=dict(dispositions=dispositions, next_focus=None))
    job = c.build_job(root, 3, 'H', [1, 2])
    work = c.workspace(root, 3)
    view = c.read(work / 'science-task.json')['lineage']
    assert len((json.dumps(view, ensure_ascii=False, indent=2) + '\n').encode()) <= history.MAX_BRIEF_BYTES
    rows = []
    path = view['indexes']['mechanisms']
    while path:
        assert (work / path).stat().st_size <= history.MAX_PAGE_BYTES
        page = c.read(work / path)
        rows.extend(page['mechanisms'])
        path = page['next_page']
    assert [row['mechanism_ref'] for row in rows] == [item['mechanism_ref'] for item in dispositions]
    for row, expected in zip(rows, dispositions):
        assert row['status'] == expected['status'] and 'view_omitted' not in row
        preview = row['disposition']
        assert preview['reason_truncated'] == (len(expected['reason'].encode()) > 160)
        assert expected['reason'].startswith(preview['reason'])
        assert len(preview['reason'].encode()) <= 160
        assert row['original'] == 'inputs/history/nodes/001/0001.json'
        original = work / preview['original']
        reported = c.read(original)['search_review']['dispositions']
        assert next(item for item in reported if item['mechanism_ref'] == row['mechanism_ref']) == expected
        assert original.stat().st_mode & 0o222 == 0
    assert 'sha256' not in json.dumps(rows) and str(root) not in json.dumps(rows)
    originals = [item for item in job['history']['files']
        if item['path'] == 'inputs/history/nodes/002/scientific-original.json']
    assert len(originals) == 1
    assert (work / originals[0]['path']).read_bytes() == c._execution_raw(root, 2).read_bytes()
    c._validate_inputs(root, work, job)
