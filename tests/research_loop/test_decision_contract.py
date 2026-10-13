"""Scientific decision declarations, exact request admission and bounded clarification."""
import copy
from pathlib import Path

import pytest

from scidiscovery.research_loop import cli, contracts as c, controller, correction, decision, native, semantic
from test_history_handoff import finish

REQUEST = dict(decision='candidate', question='Should the candidate be retained under the declared target condition?',
               change_criterion='A controlled contradiction would change the candidate choice.')


def prepare(tmp_path, *, enabled=True, correction_enabled=False):
    from scidiscovery.research_loop import search
    public = tmp_path / 'public'; public.mkdir(parents=True)
    objective = public / 'objective.md'; objective.write_text('Compare mechanisms without abandoning required controls.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000,
        max_seconds=3600, max_steps=16, model='fixture', reasoning_effort='high',
        decision_contract_version=1 if enabled else None,
        search_policy=search.DEFAULT_POLICY if correction_enabled else None,
        correction_policy=dict(review_after=1, pause_after=1) if correction_enabled else None)
    plan = dict(scope='Target discrimination', commitments=[dict(label='M',minimal_test='Required control',existing_ref=None)],
                focus=dict(label='M',action='screen')) if correction_enabled else None
    finish(root, 1, 'H', [], action='experiment', search_choice=plan)
    c.build_job(root, 2, 'W', [1], instruction='Exact scientific question')
    finish(root, 2, 'W', [1], text='Negative controlled result; target uncertainty remains.')
    return root


def author(root, step, parents, request, *, action='continue_w', review=None):
    previous = c.read(root / 'jobs' / f'{step:03d}.json') if (root / 'jobs' / f'{step:03d}.json').exists() else {}
    job = c.build_job(root, step, 'A', parents, instruction=previous.get('instruction', ''),
                      author_correction=previous.get('author_correction'))
    record = c.host_record(c.workspace(root, step))
    payload = dict(summary='Global decision with limitations', scientific_result='Explain the scientific decision and remaining gap.',
                   limitations=['No target conclusion from the proxy alone'], implementation_selection=None,
                   search_review=review, progress_assessment=dict(verdict='no_progress'),
                   candidate_recommendation=None, next_action=action, route_reason='Exact scientific question')
    if job['handoff_protocol'] >= 10:
        payload['decision_request'] = request
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs' / f'{step:03d}.json')))
    c.write(record / 'science-output.json', payload)
    c.write(record / 'usage.json', dict(input_tokens=7, cached_input_tokens=2, output_tokens=3))
    c.write(record / 'native-outcome.json', dict(returncode=0, stop_reason=None, usage=native.usage(root),
                                             raw_sha256=c.digest(record / 'science-output.json')))
    c.seal_result(root, step)
    return job, payload


def next_worker(root, *, text):
    c.build_job(root, 4, 'W', [1, 2, 3], instruction='Exact scientific question')
    finish(root, 4, 'W', [1, 2, 3], text=text)


@pytest.mark.parametrize('action', ['continue_w', 'revise_h', 'extract'])
def test_missing_scientific_declaration_preserves_raw_and_returns_to_a(tmp_path, action):
    root = prepare(tmp_path)
    job, payload = author(root, 3, [1, 2], None, action=action)
    record = c.host_record(c.workspace(root, 3))
    raw = (record / 'science-output.json').read_bytes()
    assert c.validate(c.workspace(root, 3))['next_action'] == action
    receipt = c.read(record / 'result-identity.json')['control_outcome']
    assert receipt['decision_status'] == 'unresolved'
    route = controller._route(root, 3, 'A', payload, job, 1, 2)
    route = semantic.effective_route(root, 3, payload, job, (*route, None))
    assert route[0] == 'A' and route[7]['reason'] == 'a_decision_request_missing'
    following = c.build_job(root, 4, 'A', route[1], instruction=route[2], author_correction=route[7])
    assert following['author_correction']['root']['step'] == 3
    assert (record / 'science-output.json').read_bytes() == raw
    assert not (c.host_record(c.workspace(root, 4)) / 'native-intent.json').exists()


def test_exact_completed_request_without_new_original_is_rejected_but_negative_new_result_is_allowed(tmp_path):
    root = prepare(tmp_path)
    original, _ = author(root, 3, [1, 2], REQUEST)
    prior_raw = c.read(c.host_record(c.workspace(root, 2)) / 'science-output.json')['scientific_result']
    next_worker(root, text=prior_raw)  # Same original raw bytes at a second node are not fresh evidence.
    job, payload = author(root, 5, [1, 4], copy.deepcopy(REQUEST))
    assert c.read(c.host_record(c.workspace(root, 5)) / 'result-identity.json')['control_outcome']['decision_status'] == 'unresolved'
    assert decision.reason(root, job, payload) == 'a_decision_request_repeated'
    # A different negative finding is new evidence; no proxy/unknown-value filter is applied.
    root2 = prepare(tmp_path / 'other')
    author(root2, 3, [1, 2], REQUEST)
    next_worker(root2, text='New controlled counterexample contradicts retention; target performance is still unknown.')
    job2, payload2 = author(root2, 5, [1, 4], REQUEST)
    assert decision.reason(root2, job2, payload2) is None
    assert c.read(c.host_record(c.workspace(root2, 5)) / 'result-identity.json')['control_outcome']['decision_status'] == 'applied'
    assert decision._key(original, {'decision_request': REQUEST, 'next_action': 'continue_w', 'candidate_recommendation': None})[-2] is None


@pytest.mark.parametrize('action', ['audit', 'finish', 'wait'])
def test_nonresearch_choices_do_not_need_decision_request(tmp_path, action):
    root = prepare(tmp_path)
    job, payload = author(root, 3, [1, 2], None, action=action)
    assert decision.reason(root, job, payload) is None
    assert c.read(c.host_record(c.workspace(root, 3)) / 'result-identity.json')['control_outcome']['decision_status'] == 'applied'


def test_no_completed_dependency_does_not_consume_request_and_changed_prose_is_not_semantic_duplicate(tmp_path):
    root = prepare(tmp_path)
    author(root, 3, [1, 2], REQUEST)
    job, payload = author(root, 4, [1, 2, 3], REQUEST)
    assert decision.reason(root, job, payload) is None  # A itself is not a W response.
    assert decision._completed(c.read(root/'jobs/003.json'), c.read(c.host_record(c.workspace(root,3))/'science-output.json'),
                               {4: (job, payload, {}, '')}) is False
    changed = copy.deepcopy(payload)
    changed['decision_request']['question'] += ' Is there another explanation?'
    assert decision._key(job, changed) != decision._key(job, payload)


def test_real_controller_clarification_is_bounded_and_not_counted_as_progress(tmp_path, monkeypatch):
    root = prepare(tmp_path, correction_enabled=True)
    review = dict(dispositions=[], next_focus=dict(mechanism_ref='h001.m1', action='screen'))
    author(root, 3, [1, 2], None, review=review)
    assert correction.project(root)['eligible'] == []
    accepted = []
    def respond(root, step):
        job = c.read(root / 'jobs' / f'{step:03d}.json')
        assert job['role'] == 'A' and job['author_correction']['root']['step'] == 3
        accepted.append(step)
        parents = [int(Path(row['path']).parts[2]) for row in job['direct_refs']]
        author(root, step, parents, None, review=review)
    monkeypatch.setattr(native, 'execute_native', respond)
    result = controller.run(root)
    assert result['status'] == 'semantic_correction_required' and result['reason'] == 'semantic_correction_limit'
    assert accepted == [4, 5] and result['completed_steps'] == 5
    assert correction.project(root)['eligible'] == []
    before = [(root / 'jobs' / f'{step:03d}.json').read_bytes() for step in (3, 4, 5)]
    assert controller.run(root)['status'] == 'semantic_correction_required'
    assert accepted == [4, 5]
    assert before == [(root / 'jobs' / f'{step:03d}.json').read_bytes() for step in (3, 4, 5)]


def test_recursive_strict_schema_and_old_settings_future_tasks_stay_frozen(tmp_path):
    def check(value):
        if isinstance(value, dict):
            if 'properties' in value:
                assert set(value['properties']) == set(value['required']) and value['additionalProperties'] is False
            for child in value.values():check(child)
        elif isinstance(value, list):
            for child in value:check(child)
    check(c.result_schema('A', 10))
    assert 'decision_request' not in c.result_schema('A', 9)['properties']
    root = prepare(tmp_path, enabled=False)
    job, _ = author(root, 3, [1, 2], None, action='wait')
    originals = {path:path.read_bytes() for path in (root/'settings.json', root/'jobs/003.json',
                 c.workspace(root,3)/'science-task.json', c.host_record(c.workspace(root,3))/'result-identity.json')}
    assert job['handoff_protocol'] == 8 and 'decision_contract_version' not in c.settings(root)
    assert c.build_job(root, 3, 'A', [1, 2]) == job
    assert all(path.read_bytes() == raw for path,raw in originals.items())
    assert c.build_job(root, 4, 'H', [3])['handoff_protocol'] == 8
