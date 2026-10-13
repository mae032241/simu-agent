"""Decision-value advice stays scientific and frozen in actual task inputs."""
import json

import pytest

from scidiscovery.research_loop import contracts as c, controller, guidance
from test_history_handoff import finish

COV_USAGE = (' Cov public tools: exp run [--script FILE] --new-plan or --parent-plan NAME; '
             'exp lineage-status. Other exp commands keep their public meanings.')


def prepare(tmp_path, advice, *, marker=1):
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.md'
    objective.write_text('Keep data separation and the required five comparisons; resolve the target-condition gap.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['never-launched'], max_tokens=100_000,
                       max_seconds=3600, max_steps=8, model='fixture', reasoning_effort='high',
                       search_policy=None, role_guidance=advice, handoff_authority_version=marker)
    return root


@pytest.mark.parametrize('advice', [None, guidance.DEFAULT])
def test_current_role_advice_reaches_frozen_science_view_with_original_constraints(tmp_path, advice):
    root = prepare(tmp_path, advice)
    for step, role in enumerate(('H', 'W', 'A', 'E'), 1):
        job, work, _ = finish(root, step, role, [step - 1] if step > 1 else [])
        view = c.read(work / 'science-task.json')
        assert job['native_role_instruction'] == guidance.DEFAULT[role]
        assert view.get('role_guidance', view.get('role_instruction')) == job['native_role_instruction']
        assert 'required five comparisons' in (work / view['global']['objective']).read_text()
        assert 'Keep data separation' in (work / view['global']['objective']).read_text()
        assert 'decision_value' not in c.result_schema(role, job['handoff_protocol'])['properties']
        assert c.validate(work)['summary'] == 'A contribution'
    assert 'candidate choice, mechanism selection or compliance' in guidance.DEFAULT['A']
    assert 'Honor required checks' in guidance.DEFAULT['A']
    assert 'no admissible resolution' in guidance.DEFAULT['A']
    assert 'original count requirements' in guidance.DEFAULT['W']
    assert 'falsifiable' in guidance.DEFAULT['H'] and 'solution mechanisms' in guidance.DEFAULT['H']
    assert 'Audit an unaudited choice before commitment when available' in guidance.DEFAULT['A']
    assert 'for audit, candidate_recommendation names its target' in guidance.DEFAULT['A']


def test_actual_domain_usage_fits_existing_total_bound_and_only_w_receives_it(tmp_path):
    advice = dict(guidance.DEFAULT)
    advice['W'] += COV_USAGE
    assert sum(len(text.encode()) for text in guidance.DEFAULT.values()) + 200 <= 2048
    assert sum(len(text.encode()) for text in guidance.policy(advice).values()) <= 2048
    root = prepare(tmp_path, advice)
    finish(root, 1, 'H', [], action='experiment')
    job, work, _ = finish(root, 2, 'W', [1])
    assert c.science_view(job, root)['role_guidance'].endswith(COV_USAGE)
    assert 'Cov public tools' not in c.read(c.workspace(root, 1) / 'science-task.json')['role_guidance']
    assert 'exp run' not in guidance.DEFAULT['W']
    assert 'hidden' not in json.dumps(c.science_view(job, root))


@pytest.mark.parametrize('marker', [None, 1])
def test_prepared_literal_and_legacy_fallback_are_not_rewritten(tmp_path, monkeypatch, marker):
    legacy = {**guidance.DEFAULT, 'A': 'Legacy frozen global assessment: compare existing evidence and retain limitations.'}
    root = prepare(tmp_path, legacy if marker == 1 else None, marker=marker)
    finish(root, 1, 'H', [], action='analyze')
    job, work, record = finish(root, 2, 'A', [1])
    paths = [root / 'settings.json', root / 'jobs/002.json', work / 'science-task.json',
             record / 'science-output.json', record / 'science-result.schema.json', record / 'result-identity.json']
    originals = {path: path.read_bytes() for path in paths}
    monkeypatch.setitem(guidance.DEFAULT, 'A', 'Changed future guidance must not replace a prepared literal')
    assert c.build_job(root, 2, 'A', [1]) == job
    assert c.validate(work)['next_action'] == 'wait'
    if marker == 1:
        assert job['native_role_instruction'] == legacy['A']
    else:
        assert 'native_role_instruction' not in job
        assert 'role_instruction' not in c.science_view(job, root)
    assert all(path.read_bytes() == raw for path, raw in originals.items())
