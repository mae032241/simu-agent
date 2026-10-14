"""Exact implementation reuse through real thin seals; no model calls."""
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import contracts, controller, native


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr(contracts, 'HANDOFF_PROTOCOL', 6)  # Legacy marker semantics are intentionally unchanged.
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Test a revised mechanism against a retained implementation.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['fake'], max_tokens=1000,
        max_seconds=60, max_steps=6, model='fake', reasoning_effort='high',
        search_policy=None,
        max_output_item_bytes=64, max_output_total_bytes=96)
    return root


def finish(root, step, role, parents, text='A bounded scientific finding', action='wait', files=None, summary='A contribution', limitations=None, recommendation=None, search_choice=None, progress=None, selection=None, mechanism_findings=None):
    path = root / 'jobs' / f'{step:03d}.json'
    previous = contracts.read(path) if path.exists() else {}
    job = contracts.build_job(root, step, role, parents, previous.get('instruction', ''),
                              previous.get('evidence_return'), previous.get('correction_request'), previous.get('author_correction'))
    work = contracts.workspace(root, step)
    record = contracts.host_record(work)
    payload = dict(summary=summary, scientific_result=text, limitations=limitations if limitations is not None else ['Fixture only'])
    if job.get('handoff_protocol', 1) >= 7:
        payload['implementation_selection'] = selection
    if (role == 'A' and job.get('handoff_protocol', 1) >= 4) or recommendation is not None:
        payload['candidate_recommendation'] = recommendation
    if job.get('handoff_protocol', 1) >= 5 and role in {'H', 'A'}:
        payload['search_plan' if role == 'H' else 'search_review'] = search_choice
    if job.get('handoff_protocol', 1) >= 6 and role == 'A':
        payload['progress_assessment'] = progress
    if role=='W':payload.update(stage_intent='review',mechanism_findings=mechanism_findings)
    if role=='A':payload.update(decision_request=None,portfolio_review=None)
    if role in {'H', 'A'}:
        payload.update(next_action=action, route_reason='Exact scientific question')
    for name, contents in (files or {}).items():
        path = work / 'artifacts' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    contracts.write(record / 'native-intent.json', dict(task_sha256=contracts.digest(root / 'jobs' / f'{step:03d}.json')))
    contracts.write(record / 'science-output.json', payload)
    contracts.write(record / 'usage.json', dict(input_tokens=7, cached_input_tokens=2, output_tokens=3))
    contracts.write(record / 'native-outcome.json', dict(returncode=0, stop_reason=None,
        usage=native.usage(root), raw_sha256=contracts.digest(record / 'science-output.json')))
    contracts.seal_result(root, step)
    return job, work, record


def source(scene, files=None):
    finish(scene, 1, 'H', [], action='experiment')
    return finish(scene, 2, 'W', [1], files=files or {'candidate.py': 'def predict(): return 42\n', 'unused.txt': 'Do not forward me'})


REUSED = 'inputs/parents/002/artifacts/candidate.py'
MARKED = f'[retained implementation]({REUSED}#reuse-implementation)'


def test_real_scientific_route_reuses_only_selected_file_without_ancestry(scene, monkeypatch):
    def execute(root, step):
        role = ('H', 'W', 'A', 'H', 'W', 'A')[step - 1]
        job = contracts.read(root / 'jobs' / f'{step:03d}.json')
        action = 'experiment' if role == 'H' else 'revise_h' if step == 3 else 'finish'
        text = MARKED if step == 4 else f'Ordinary [citation]({REUSED})' if step == 3 else 'Bounded finding'
        files = {'candidate.py': 'def predict(): return 42\n', 'unused.txt': 'Private to old direct handoff'} if step == 2 else None
        if step == 5:
            work = contracts.workspace(root, step)
            assert (work / REUSED).read_text() == 'def predict(): return 42\n'
            assert not (work / Path(REUSED).parent / 'unused.txt').exists()
            assert [ref['path'] for ref in job['direct_refs']] == ['inputs/parents/004/conclusion.json']
            view = contracts.read(work / 'science-task.json')
            assert view['reused_implementations'] == [dict(label='retained implementation', path=REUSED)]
            assert 'sha256' not in json.dumps(view) and 'origin_result' not in json.dumps(view)
        # build_job is idempotent for an identical request; use the actual route.
        parents = [int(Path(ref['path']).parts[2]) for ref in job['direct_refs']]
        finish(root, step, role, parents, text, action, files)
    monkeypatch.setattr(native, 'execute_native', execute)
    result = controller.run(scene)
    assert result['status'] == 'finish' and result['completed_steps'] == 6, result
    final = contracts.workspace(scene, 6)
    assert not (final / REUSED).exists()  # Retained H4 must not re-send to A6.
    assert contracts.read(contracts.host_record(final) / 'result-identity.json').get('selected_inputs', []) == []
    assert controller.run(scene)['status'] == 'finish'


def test_every_hop_requires_new_scientific_intent_and_deduplicates(scene):
    source(scene)
    finish(scene, 3, 'A', [2], text=MARKED + ' ' + MARKED)
    job, work, _ = finish(scene, 4, 'H', [3], text=MARKED)
    assert len(job['selected_inputs']) == 1 and (work / REUSED).is_file()
    successor = contracts.build_job(scene, 5, 'W', [4])
    assert len(successor['selected_inputs']) == 1
    assert len([row for row in successor['direct_materials'] if row['path'] == REUSED]) == 1
    assert not list((contracts.workspace(scene, 5) / 'inputs').rglob('unused.txt'))


@pytest.mark.parametrize('target', [
    'work/candidate.py', 'inputs/parents/002/artifacts/unused-missing.py',
    'inputs/parents/002/artifacts/../candidate.py',
    'inputs/parents/002/artifacts/%2e%2e/candidate.py',
    '/etc/passwd', 'https://example.org/code.py', REUSED + '?latest=1',
])
def test_marked_unbound_or_ambiguous_paths_cannot_seal(scene, target):
    source(scene)
    with pytest.raises(ValueError, match='exact already bound input'):
        finish(scene, 3, 'A', [2], text=f'[implementation]({target}#reuse-implementation)')
    assert not (contracts.host_record(contracts.workspace(scene, 3)) / 'result-identity.json').exists()


def test_ordinary_citation_does_not_forward_old_inputs(scene):
    source(scene)
    finish(scene, 3, 'A', [2], text=f'[citation]({REUSED})')
    job = contracts.build_job(scene, 4, 'H', [3])
    assert job['direct_materials'] == [] and not job.get('selected_inputs')


@pytest.mark.parametrize('changed', ['original', 'read_copy', 'receipt'])
def test_changed_bound_reuse_is_rejected(scene, changed):
    source(scene)
    _, work, record = finish(scene, 3, 'A', [2], text=MARKED)
    if changed == 'receipt':
        seal = contracts.read(record / 'result-identity.json')
        seal['selected_inputs'][0]['label'] = 'Changed hidden selection'
        contracts.write(record / 'result-identity.json', seal)
    else:
        path = contracts.workspace(scene, 2) / 'artifacts/candidate.py' if changed == 'original' else work / REUSED
        path.chmod(0o600)
        path.write_text('different implementation')
    with pytest.raises(ValueError, match='changed'):
        contracts.build_job(scene, 4, 'H', [3])


def test_selected_input_bound_counts_unique_files(scene):
    source(scene, {f'file{i}.py': 'x' for i in range(17)})
    text = ' '.join(f'[code{i}](inputs/parents/002/artifacts/file{i}.py#reuse-implementation)' for i in range(17))
    with pytest.raises(ValueError, match='handoff bound'):
        finish(scene, 3, 'A', [2], text=text)


def test_selected_copy_cannot_follow_destination_directory_link(scene, tmp_path):
    source(scene)
    finish(scene, 3, 'A', [2], text=MARKED)
    work = contracts.workspace(scene, 4)
    work.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (work / 'inputs').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='directories must not be links'):
        contracts.build_job(scene, 4, 'H', [3])
    assert not list(outside.rglob('candidate.py'))


def test_final_input_bound_includes_new_outputs_and_selected_old_files(scene):
    source(scene, {'candidate.py': 'x' * 48})
    finish(scene, 3, 'A', [2], text=MARKED)
    finish(scene, 4, 'H', [3], text=MARKED, files={'revision.txt': 'y' * 64})
    with pytest.raises(ValueError, match='Combined input materials'):
        contracts.build_job(scene, 5, 'W', [4])
    assert not (scene / 'jobs/005.json').exists()
    assert not (contracts.workspace(scene, 5) / REUSED).exists()


def test_final_input_bound_deduplicates_direct_and_reused_original(scene):
    source(scene, {'candidate.py': 'x' * 64})
    finish(scene, 3, 'A', [2], text=MARKED)
    job = contracts.build_job(scene, 4, 'H', [2, 3])
    assert len(job['direct_materials']) == 1
    assert job['direct_materials'][0]['size_bytes'] == 64


def test_legacy_seal_and_prepared_job_keep_original_packets_on_resume(scene):
    # Simulate a job written before this protocol without editing any sealed byte.
    job = contracts.build_job(scene, 1, 'H', [])
    job.pop('handoff_protocol')
    job.pop('history', None)
    contracts.write(scene / 'jobs/001.json', job)
    contracts.write(contracts.workspace(scene, 1) / 'science-task.json', contracts.science_view(job))
    contracts.write(contracts.host_record(contracts.workspace(scene, 1)) / 'science-result.schema.json', contracts.result_schema('H', 1))
    finish(scene, 1, 'H', [], action='experiment')
    original = {path: path.read_bytes() for path in (
        scene / 'jobs/001.json', contracts.workspace(scene, 1) / 'science-task.json',
        contracts.host_record(contracts.workspace(scene, 1)) / 'result-identity.json')}
    contracts.validate(contracts.workspace(scene, 1))
    assert contracts.build_job(scene, 1, 'H', []) == job
    next_job = contracts.build_job(scene, 2, 'W', [1])
    assert next_job['handoff_protocol'] == contracts.HANDOFF_PROTOCOL
    assert 'implementation_reuse' in contracts.science_view(next_job)
    assert 'implementation_reuse' not in contracts.science_view(job)
    assert all(path.read_bytes() == contents for path, contents in original.items())


@pytest.mark.parametrize('origin', ['foreign', 'future'])
def test_selected_original_requires_same_instance_and_preceding_node(scene, origin):
    source(scene)
    job = contracts.build_job(scene, 3, 'A', [2])
    row = next(row for row in job['direct_materials'] if row['path'] == REUSED)
    row['source'] = (str(scene.parent / 'foreign/project/nodes/002/artifacts/candidate.py')
                     if origin == 'foreign' else str(contracts.workspace(scene, 4) / 'artifacts/candidate.py'))
    with pytest.raises(ValueError, match='original instance node|exact preceding node'):
        contracts.selected_inputs(contracts.workspace(scene, 3), {'scientific_result': MARKED}, job)
