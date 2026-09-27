import json
import sys
from pathlib import Path

import pytest

REPO = Path('/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2')
sys.path.insert(0, str(REPO / 'tests/operations'))
import test_l4_local_tcad as fixture
from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.operation_workspace import snapshot_workspace
from tcad_artifact.project_packager import ImplementationGap, validate_implementation_gap


def test_reproduce_completed_gap_cannot_continue_to_revision(tmp_path):
    catalog, runtime, root, _ = fixture._system(tmp_path, solver_kind='sprocess')
    inputs = [
        {'port': 'execution_capability', 'artifact_names': ['execution_capability']},
        {'port': 'experiment_plan', 'artifact_names': ['experiment_plan']},
    ]
    fixture._invoke(root, 'probe_author', 'tcad.deck.author.initial.v1', inputs)
    worker = fixture._debug_worker(catalog, runtime, fixture._ImmediateDebugAdapter(), tmp_path / 'debug')
    opened = worker.call_tool('worker_open_assignment', {})
    deck = Path(opened['workspace_path']) / 'deck'
    (deck / 'files/main.cmd').write_text('set continuation_probe 1\n')
    (deck / 'reports/failure.log').write_text('fixture diagnostic: exit 1\n')
    fixture._write_gap(opened)
    snapshot = snapshot_workspace(Path(opened['workspace_path']))
    assert {x.relative_path for x in snapshot} == {'deck/gap.json', 'deck/handoff.json'}
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    status = root.call_tool('run_status', {'name': 'probe_author'})
    assert status['sealed_output']['payload'] == fixture._task_gap()
    assert not status['recovery_available']
    review_request = {'name': 'probe_review', 'operation_id': 'tcad.deck.review.v1', 'instruction': 'Review the exact fixture gap.',
        'inputs': [{'port': 'project', 'artifact_names': [status['output_artifact_name']]}, *inputs]}
    root.call_tool('operation_invoke', review_request)
    compiled = catalog.operation('tcad.deck.review.v1')
    reviewer = fixture.LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    reviewed = reviewer.call_tool('worker_open_assignment', {})
    review_deck = Path(reviewed['workspace_path']) / 'deck'
    assert not (review_deck / 'files/main.cmd').exists()
    assert not (review_deck / 'reports/failure.log').exists()
    envelope = json.loads((review_deck / 'review-template.json').read_bytes())
    envelope['handoff'].update(verdict='revise', summary='Fixture requests bounded repair.')
    envelope['payload'].update(verdict='revise', summary='Fixture initialization gap.', rationale='Exact source and diagnostic required for repair.')
    Path(reviewed['output_directory'], 'result.json').write_bytes(canonical_json(envelope))
    assert reviewer.call_tool('worker_submit_result', {})['state'] == 'completed'
    review = root.call_tool('run_status', {'name': 'probe_review'})
    request = {'name': 'probe_revision', 'operation_id': 'tcad.deck.author.revise.v1', 'instruction': 'Repair the exact reviewed fixture.',
        'inputs': [*inputs,
            {'port': 'prior_project', 'artifact_names': [status['output_artifact_name']]},
            {'port': 'change_request', 'artifact_names': [review['output_artifact_name']]}]}
    assert root.call_tool('operation_preflight', request)['admissible']
    with pytest.raises(Exception) as caught:
        root.call_tool('operation_invoke', request)
    chain = []
    error = caught.value
    while error is not None:
        chain.append(type(error).__name__ + ': ' + str(error))
        error = error.__cause__
    joined = '\n'.join(chain)
    assert 'local_run_creation_failed' in joined
    assert 'prior_project is invalid' in joined
    assert 'DeckProjectDraft' in joined
    print('REPRODUCED: gap drops source/log; completed gap has no recovery; fresh reviewer lacks source/log; revision preflight accepts but materializer rejects DeckProjectDraft.')
    print(joined)


def test_reproduce_revision_gap_validator_rejects_gap_base():
    gap = ImplementationGap.model_validate_json(canonical_json(fixture._task_gap()), strict=True)
    inputs = {'experiment_plan': canonical_json(fixture._portfolio()), 'prior_project': canonical_json(fixture._task_gap())}
    with pytest.raises(ValueError, match='DeckProjectDraft'):
        validate_implementation_gap(gap, inputs, {'verdict': 'blocked', 'missing_inputs': []})
    print('REPRODUCED: even a second honest gap is rejected when prior_project is a gap.')
