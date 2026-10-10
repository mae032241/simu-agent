"""Present HWA contracts; proposed search allocation/policy is not implemented."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.cognitive import HypothesisProposal
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from scidiscovery.general_science_experiment_task import StageSubmission
from tests.operations.test_experiment_goal_origin import _setup
from tests.operations.test_historical_compatibility_paths import _artifact, _complete
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.worker_fixtures import attached_worker


_NATIVE_PAYLOADS = json.loads((Path(__file__).resolve().parents[2]
    / 'docs/plans/search_mvp/native-payloads.json').read_text())


def _hypotheses():
    payload = _proposal(hypothesis_keys=('mechanism',))
    payload.pop('research_objective_key')
    return payload


def _analysis(action):
    return dict(summary='No valid observations; assess the bounded evaluation gap.',
        overall_verdict='inconclusive', claim_allowed=False,
        objective_assessment=dict(status='inconclusive', summary='The proxy does not establish the original goal.'),
        hypothesis_assessments=[dict(hypothesis_key='mechanism', outcome='not_tested',
            evidence_keys=['hypothesis_portfolio'], rationale='No valid observation was produced.')],
        progress_assessment=dict(outcome='unknown', reason='The goal-representativeness gap remains.'),
        limitations=['No observations and no independently representative target evaluation.'],
        remaining_contradiction='The mechanism and global contribution remain untested.',
        next_action=action)


@pytest.mark.parametrize('model,payload,proposed_field', [
    (HypothesisProposal, _NATIVE_PAYLOADS['hypothesis'], 'search_allocation'),
    (LayeredDiagnosisReport, _NATIVE_PAYLOADS['analysis'], 'search_assessment'),
    (StageSubmission, dict(stage='implementation', conclusion='Fixture-only implementation.'), 'candidate'),
], ids=['H-allocation-not-implemented', 'A-disposition-not-implemented', 'stage-candidate-not-implemented'])
def test_current_fields_accept_but_proposed_search_fields_are_forbidden(model, payload, proposed_field):
    # First prove the baseline payload is valid, so another invalid field cannot
    # accidentally satisfy the negative check. These future fields remain absent.
    retained = model.model_validate_json(canonical_json(payload), strict=True)
    assert proposed_field not in retained.model_dump(mode='json')
    with pytest.raises(ValidationError) as caught:
        model.model_validate_json(canonical_json({**payload, proposed_field: {}}), strict=True)
    assert [(item['loc'], item['type']) for item in caught.value.errors()] == [
        ((proposed_field,), 'extra_forbidden')]


@pytest.mark.parametrize('direction', ['same_H_evaluation_design', 'scientific_boundary_revision'])
def test_sealed_A_action_preserves_exact_H_until_explicit_revision(tmp_path, direction):
    runtime, instance, root = _setup(tmp_path, native_only=True)
    root.call_tool('artifact_ingest_text', dict(name='goal', text=(
        'Test the declared mechanism using legal synthetic materials. Evaluation design may '
        'be refined without changing the mechanism, data permissions or precommitted criterion.')))
    original_goal = _artifact(runtime, instance, 'goal').ref
    h1 = _complete(runtime, root, 'H1', 'science.hypothesis.propose.v1',
        {'subject': 'goal'}, _hypotheses())
    h1_ref = _artifact(runtime, instance, h1).ref
    h1_original_bytes = runtime.artifacts.read(h1_ref)
    experiment = _complete(runtime, root, 'W1', 'science.experiment.v1', {'subject': h1},
        dict(summary='Environment unavailable.', outcome='blocked', limitations=['No observations.'],
             remaining_question='Repair the missing environment.', adopted_stages=[]), verdict='blocked')
    action = (
        f'W: improve the evaluation design within {h1}; use only its existing data permissions '
        'and preserve its mechanism and precommitted criterion. Seal the new design without '
        'rewriting prior observations.' if direction == 'same_H_evaluation_design' else
        f'H: revise {h1} explicitly before W executes a changed mechanism or precommitted criterion; '
        f'read {experiment} and the original goal, preserving the old portfolio and limits.')
    analysis = _complete(runtime, root, 'A1', 'science.result.analyze.v1',
        {'subject': experiment}, _analysis(action), verdict='inconclusive')
    a_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='A1')
    a_inputs = {item.port_name: item.artifact_ref for item in runtime.runs.status(a_id).inputs}
    assert a_inputs['hypothesis_portfolio'] == h1_ref
    assert a_inputs['objective_source'] == original_goal
    assert json.loads(runtime.artifacts.read(_artifact(runtime, instance, analysis).ref))['next_action'] == action
    decision = root.call_tool('run_status', dict(name='A1', intent='decision'))
    assert next(item['value'] for item in decision['selected_output']['items']
                if item['pointer'] == '/next_action') == action
    assert runtime.runs.status(a_id).signal.next_actions == (action,)

    if direction == 'scientific_boundary_revision':
        # Root relays the sealed instruction; it does not mechanically classify
        # its prose. H authors the new portfolio through the existing operation.
        h2_payload = _hypotheses()
        h2_payload['hypotheses'][0]['mechanism'] = 'An explicitly revised finite intervention.'
        selected_h = _complete(runtime, root, 'H2', 'science.hypothesis.propose.v1',
            {'subject': 'goal', 'previous_hypotheses': h1, 'result_analysis': analysis}, h2_payload)
        expected_h = _artifact(runtime, instance, selected_h).ref
        assert expected_h != h1_ref
        assert runtime.artifacts.read(h1_ref) == h1_original_bytes
    else:
        selected_h, expected_h = h1, h1_ref
        assert not any(run.operation_id == 'science.hypothesis.criticize.v1'
                       for run in runtime.runs.list(instance_id=instance.instance_id))

    request = dict(name='next_W', operation_id='science.experiment.v1', instruction=action,
        inputs=[dict(port='subject', artifact_names=[selected_h])])
    assert root.call_tool('operation_preflight', request)['admissible']
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    next_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='next_W')
    next_inputs = {item.port_name: item.artifact_ref for item in runtime.runs.status(next_id).inputs}
    assert next_inputs['hypothesis_portfolio'] == expected_h
    assert next_inputs['objective_source'] == original_goal
    worker = attached_worker(runtime, root, 'next_W')
    opened = worker.call_tool('worker_open_assignment', {})
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    assert start['instruction'] == action
    # This proves exact existing binding/startup, not scientific validity,
    # execution of a new evaluator, or automatic routing of free-text actions.
