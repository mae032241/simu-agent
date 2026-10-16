"""Public candidate identities and latest authored recommendations use exact seals."""
from scidiscovery.research_loop import contracts as c, controller, history
from scidiscovery.research_loop.cli import status
from test_history_handoff import finish


def scene(tmp_path, other='a'):
    tmp_path.mkdir()
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Compare exact retained candidate originals.')
    observer = tmp_path / 'observer.py'
    observer.write_text('''import json,sys
r=json.load(sys.stdin)
rows=[dict(id='P',label='Candidate P',implementation='history/nodes/002/artifacts/p/model.py',evaluation_key='public-v1',metric=.8,direction='max',status='ok',evidence=['project/global/objective.md']),dict(id='unknown',label='No implementation',implementation=None,evaluation_key='public-v1',metric=None,direction='max',status='unknown',evidence=['project/global/objective.md'])] if r['step']==2 else []
print(json.dumps(dict(candidates=rows,current_candidate=None,actual_submission=None,coverage=dict(status='complete',note='Fixture public observation'))))
''')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-invoked'], max_tokens=100000,
        max_seconds=300, max_steps=12, model='fixture-no-model', reasoning_effort='high',
        search_policy=None, history_observer=dict(adapter=str(observer), config={}))
    finish(root, 1, 'H', [], action='experiment')
    finish(root, 2, 'W', [1], files={'p/model.py': 'P original\n', f'{other}/model.py': 'Other original\n'})
    finish(root, 3, 'A', [2], recommendation='P')
    finish(root, 4, 'H', [3])
    return root


def candidates(root, step, job):
    work = c.workspace(root, step)
    path = c.science_view(job, root)['lineage']['indexes']['candidates']
    result = []
    while path:
        page = c.read(work / path)
        result.extend(page['candidates'])
        path = page['next_page']
    return {row['id']: row for row in result}


def test_same_basename_candidate_exposes_exact_selectable_implementation_id(tmp_path):
    public_pages = []
    for other, expected in [('a', 'W002-I002'), ('z', 'W002-I001')]:
        root = scene(tmp_path / other, other)
        finish(root, 5, 'A', [4], recommendation=None)
        job = c.build_job(root, 6, 'H', [5])
        work = c.workspace(root, 6)
        rows = candidates(root, 6, job)
        chosen = rows['P']['implementation_id']
        assert chosen == expected
        assert rows['unknown']['implementation_id'] is None
        selected = history.resolve_implementation(root, chosen, job['history']['nodes'])
        assert history.handle(selected) == rows['P']['implementation']
        assert not (work / 'inputs/parents/002/artifacts/p/model.py').exists()
        public_pages.append({row['path']: c.read(work / row['path']) for row in job['history']['files']})
        finish(root, 6, 'H', [5], selection=[chosen])
        successor = c.build_job(root, 7, 'W', [6])
        assert len(successor['selected_inputs']) == 1
        material = successor['selected_inputs'][0]['material']
        assert (c.workspace(root, 7) / material['path']).read_text() == 'P original\n'
        assert not (c.workspace(root, 7) / f'inputs/parents/002/artifacts/{other}/model.py').exists()
    assert public_pages[0] != public_pages[1]
    assert public_pages[0]['inputs/history/implementations/002/0001.json'] == public_pages[1]['inputs/history/implementations/002/0001.json']


def test_latest_null_clears_cache_closeout_and_status_recommendation(tmp_path):
    root = scene(tmp_path / 'recommendation')
    assert c.read(root / 'host-history/overview.json')['a_recommended'] == dict(candidate_id='P', author_step=3)
    finish(root, 5, 'A', [4], recommendation=None)
    job = c.build_job(root, 6, 'H', [5])
    view = c.science_view(job, root)['lineage']['candidates']
    assert view['a_recommended'] is None
    assert view['historical_a_recommendation'] == dict(candidate_id='P', author_step=3)
    cache = c.read(root / 'host-history/overview.json')
    assert cache['a_recommended'] is None
    assert cache['historical_a_recommendation'] == view['historical_a_recommendation']
    closed = controller.closeout(root, export_only=True)
    assert closed['status'] == 'exported_unsubmitted'
    assert closed['existing_A_recommendation'] is None
    assert status(root)['closeout']['existing_A_recommendation'] is None
    assert not (root / 'host-delivery/actions').exists()
