"""Configured effects are public facts, separate from scientific delivery coverage."""
import json

import pytest

from scidiscovery.research_loop import contracts as c, controller, delivery, generic_delivery


def configured_policy(tmp_path, *, declared=True):
    target = tmp_path / 'target'
    target.mkdir()
    adapter = generic_delivery.descriptor(target)
    if not declared:
        # Even the same executable is not a declaration: never infer from argv.
        adapter.pop('effect_scope')
    return dict(closeout_a=dict(max_observed_tokens=100, max_seconds=10),
        inflight_tokens=0, cleanup_seconds=5, submit_seconds=10,
        confirm_seconds=5, adapter=adapter)


def instance(tmp_path, policy=None):
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Preserve the evaluated object and original native receipt; report any missing deliverable.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-execute'],
        max_tokens=100000, max_seconds=600, max_steps=6,
        model='no-model', reasoning_effort='high', search_policy=None,
        delivery_policy=policy,
        node_budget_policy={role: dict(max_observed_tokens=100, max_seconds=10) for role in 'HWAE'})
    return root


def test_builtin_scope_is_explicit_frozen_and_public_without_private_bindings(tmp_path):
    policy = configured_policy(tmp_path)
    frozen = delivery.policy(policy)
    assert frozen['adapter']['effect_scope'] == policy['adapter']['effect_scope']
    view = delivery.public_configuration(frozen)
    assert view == dict(configured=True, effect_scope=policy['adapter']['effect_scope'])
    assert 'local directory only' in view['effect_scope']
    assert 'Does not train' in view['effect_scope']
    assert 'task-native submission' in view['effect_scope'] and 'scientific audit' in view['effect_scope']
    assert set(view) == {'configured', 'effect_scope'}
    assert str(tmp_path) not in json.dumps(view)
    assert list((tmp_path / 'target').iterdir()) == []


@pytest.mark.parametrize('scope', [None, False, {}, '', ' \n'])
def test_scope_requires_nonempty_public_text(tmp_path, scope):
    policy = configured_policy(tmp_path)
    policy['adapter']['effect_scope'] = scope
    with pytest.raises(ValueError, match='effect_scope'):
        delivery.policy(policy)


@pytest.mark.parametrize('scope', ['x' * 1025, '界' * 342, 'Actual retained delivery effects and missing task steps. ' * 100])
def test_long_scope_is_frozen_and_public_without_authorizing_effects(tmp_path, scope):
    policy = configured_policy(tmp_path)
    policy['adapter']['effect_scope'] = scope
    frozen = delivery.policy(policy)
    assert frozen['adapter']['effect_scope'] == scope
    assert delivery.public_configuration(frozen) == dict(configured=True, effect_scope=scope)
    assert frozen['adapter']['capabilities'] == []
    assert list((tmp_path / 'target').iterdir()) == []


def test_undeclared_scope_stays_absent_from_wire_and_unknown_in_public_view(tmp_path):
    frozen = delivery.policy(configured_policy(tmp_path, declared=False))
    assert 'effect_scope' not in frozen['adapter']
    assert delivery.public_configuration(frozen) == dict(configured=True, effect_scope='unknown')
    assert delivery.public_configuration(None) == dict(configured=False,
        effect_scope='No delivery adapter is configured.')
    assert delivery.public_configuration(dict(adapter=None))['configured'] is False


@pytest.mark.parametrize('declared', [False, True])
def test_new_job_freezes_scope_and_retained_job_keeps_exact_identity(tmp_path, declared):
    root = instance(tmp_path, configured_policy(tmp_path, declared=declared))
    job = c.build_job(root, 1, 'A', [])
    task = c.workspace(root, 1) / 'science-task.json'
    originals = {path: path.read_bytes() for path in (root / 'jobs/001.json', task)}
    expected = delivery.public_configuration(c.settings(root)['delivery_policy'])
    assert job['configured_delivery'] == c.read(task)['configured_delivery'] == expected
    assert c.build_job(root, 1, 'A', []) == job
    assert all(path.read_bytes() == value for path, value in originals.items())
    assert not (c.host_record(c.workspace(root, 1)) / 'native-intent.json').exists()
    assert list((tmp_path / 'target').iterdir()) == []
    assert set(c.read(task)['configured_delivery']) == {'configured', 'effect_scope'}
    task.write_text(json.dumps(dict(c.read(task), configured_delivery=dict(configured=True, effect_scope='different'))))
    with pytest.raises(ValueError):
        c._validate_inputs(root, c.workspace(root, 1), job)


@pytest.mark.parametrize('role', ['W', 'A'])
def test_task_coverage_guidance_maps_original_deliverables_without_completion_gate(tmp_path, role):
    root = instance(tmp_path, configured_policy(tmp_path))
    job = c.build_job(root, 1, role, [])
    view = c.read(c.workspace(root, 1) / 'science-task.json')
    advice = view['delivery_requirements']
    assert 'original task' in advice and 'native' in advice
    if role == 'W':
        assert 'declared outputs' in advice and 'before temporary work is removed' in advice
        assert 'not every intermediate' in advice and 'Do not write hashes' in advice
    else:
        assert 'best existing partial result, including in FINAL' in advice
        assert 'missing deliverables' in advice and 'grant no execution permission' in advice
    # Coverage remains scientific reasoning, not an extra schema field or gate.
    schema = c.result_schema(role, job['handoff_protocol'], **c.response_options(job))
    assert 'delivery_requirements' not in schema['properties']
    assert 'configured_delivery' not in schema['properties']


def test_final_partial_report_uses_same_scope_without_new_completion_gate(tmp_path):
    from test_final_a_completion_native import instance as final_instance
    root = final_instance(tmp_path, delay=0)
    result = controller.run(root)
    assert result['status'] == 'final_a_completed', result
    task = c.read(c.workspace(root, 2) / 'science-task.json')
    assert task['configured_delivery']['configured'] is False
    assert 'best existing partial result, including in FINAL' in task['delivery_requirements']
    accepted = c.validate(c.workspace(root, 2))
    assert 'objective remains unresolved' in accepted['scientific_result']
    assert not (root / 'jobs/003.json').exists()
