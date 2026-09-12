import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tests/operations'))
import test_l4_local_tcad as fixture
from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.operation_workspace import snapshot_workspace
from tcad_artifact.project_packager import ImplementationGap, validate_implementation_gap


@pytest.mark.parametrize("broken_metadata", [False, True])
def test_gap_records_reach_fresh_revision_worker(tmp_path, broken_metadata):
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
    (deck / 'attempts.md').write_text('Attempted fixture change; initialization failed.\n')
    if broken_metadata:
        (deck / 'project.json').chmod(0o600)
        (deck / 'project.json').write_text('{unfinished')
    fixture._write_gap(opened)
    gap = json.loads((deck / 'gap.json').read_bytes())
    gap['missing_inputs'] = ['A bounded input required by this implementation is absent.']
    (deck / 'gap.json').write_bytes(canonical_json(gap))
    # The gap carries this detail once; the handoff does not repeat the list.
    assert not json.loads((deck / 'handoff.json').read_bytes()).get('missing_inputs')
    snapshot = snapshot_workspace(Path(opened['workspace_path']))
    assert {'deck/gap.json', 'deck/handoff.json', 'deck/files/main.cmd', 'deck/reports/failure.log'} <= {x.relative_path for x in snapshot}
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    status = root.call_tool('run_status', {'name': 'probe_author'})
    assert status['sealed_output']['payload']['result_kind'] == 'implementation_gap'
    assert status['sealed_output']['payload']['missing_inputs'] == gap['missing_inputs']
    assert not status['recovery_available']
    review_request = {'name': 'probe_review', 'operation_id': 'tcad.deck.review.v1', 'instruction': 'Review the exact fixture gap.',
        'inputs': [{'port': 'project', 'artifact_names': [status['output_artifact_name']]}, *inputs]}
    root.call_tool('operation_invoke', review_request)
    compiled = catalog.operation('tcad.deck.review.v1')
    reviewer = fixture.LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    reviewed = reviewer.call_tool('worker_open_assignment', {})
    review_deck = Path(reviewed['workspace_path']) / 'deck'
    assert (review_deck / 'files/main.cmd').read_text() == 'set continuation_probe 1\n'
    assert (review_deck / 'reports/failure.log').read_text() == 'fixture diagnostic: exit 1\n'
    envelope = json.loads((review_deck / 'review-template.json').read_bytes())
    envelope['handoff'].update(verdict='revise', summary='Fixture requests bounded repair.')
    envelope['payload'].update(verdict='revise', syntax_fidelity='fail', summary='Fixture initialization gap.', rationale='Exact source and diagnostic required for repair.')
    Path(reviewed['output_directory'], 'result.json').write_bytes(canonical_json(envelope))
    assert reviewer.call_tool('worker_submit_result', {})['state'] == 'completed'
    review = root.call_tool('run_status', {'name': 'probe_review'})
    request = {'name': 'probe_revision', 'operation_id': 'tcad.deck.author.revise.v1', 'instruction': 'Repair the exact reviewed fixture.',
        'inputs': [*inputs,
            {'port': 'prior_project', 'artifact_names': [status['output_artifact_name']]},
            {'port': 'change_request', 'artifact_names': [review['output_artifact_name']]}]}
    assert root.call_tool('operation_preflight', request)['admissible']
    root.call_tool('operation_invoke', request)
    compiled = catalog.operation('tcad.deck.author.revise.v1')
    services = {'tcad_artifact:tcad.development_debug': fixture.LocalTCADDebugService(adapter=fixture._ImmediateDebugAdapter(), exchange_root=tmp_path / 'revision-debug')}
    revision = fixture.LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest, tool_services=services)
    fresh = revision.call_tool('worker_open_assignment', {})
    fresh_deck = Path(fresh['workspace_path']) / 'deck'
    assert (fresh_deck / 'files/main.cmd').read_text() == 'set continuation_probe 1\n'
    assert len(tuple((fresh_deck / 'reports/history').glob('*_failure.log'))) == 1
    assert not (fresh_deck / 'reports/initialization.json').exists()
    assert not (fresh_deck / 'reports/preflight.json').exists()
    assert (fresh_deck / 'attempts.md').read_text() == 'Attempted fixture change; initialization failed.\n'
    if broken_metadata:
        assert len(tuple((fresh_deck / 'reports/history').glob('*_project.json'))) == 1
    fixture._write_gap(fresh)
    assert revision.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_completed_local_router_claims_new_run_with_fresh_tool_state(tmp_path):
    catalog, runtime, root, _ = fixture._system(tmp_path, solver_kind='sprocess')
    inputs = [{'port': 'execution_capability', 'artifact_names': ['execution_capability']},
              {'port': 'experiment_plan', 'artifact_names': ['experiment_plan']}]
    fixture._invoke(root, 'first', 'tcad.deck.author.initial.v1', inputs)
    worker = fixture._debug_worker(catalog, runtime, fixture._ImmediateDebugAdapter(), tmp_path / 'debug')
    first = worker.call_tool('worker_open_assignment', {})
    fixture._write_gap(first)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert worker.call_tool('worker_open_assignment', {}) == {'state': 'completed'}
    worker._tool_state['old'] = {'reserved_wall_seconds': 600, 'runs': {'stale': {}}}
    fixture._invoke(root, 'second', 'tcad.deck.author.initial.v1', inputs)
    second = worker.call_tool('worker_open_assignment', {})
    assert second['state'] == 'opened'
    assert second['workspace_path'] != first['workspace_path']
    assert worker._tool_state == {}
    assert root.call_tool('run_status', {'name': 'first'})['state'] == 'completed'
    fixture._write_gap(second)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_gap_paths_and_prior_gap_validation():
    gap = ImplementationGap.model_validate_json(canonical_json(fixture._task_gap()), strict=True)
    inputs = {'experiment_plan': canonical_json(fixture._portfolio()), 'prior_project': canonical_json(fixture._task_gap())}
    validate_implementation_gap(gap, inputs, {'verdict': 'blocked', 'missing_inputs': []})
    for path in ('../outside', 'contract/override.json', '/tmp/outside'):
        with pytest.raises(ValueError):
            ImplementationGap.model_validate_json(canonical_json({**fixture._task_gap(), 'attempt_files': [{'relative_path': path, 'content': 'bad'}]}), strict=True)
