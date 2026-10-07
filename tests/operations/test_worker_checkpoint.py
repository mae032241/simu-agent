"""Real owner-tool delivery and sealed H-W-A-W-A, without models or solvers."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_experiment_goal_origin import _setup, _request
from tests.operations.test_historical_compatibility_paths import _complete, _artifact
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.worker_fixtures import attached_worker
from tests.operations.research_loop_fixtures import authorize_loop, measured_fixture_usage


def _owner(tmp_path, interval=30):
    runtime, instance, root = _setup(tmp_path, native_only=True)
    bindings = runtime.scheduler_bindings
    now = [time.time()]
    bindings.progression_clock = lambda: now[0]
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update={'progression': settings.progression.model_copy(
        update={'worker_checkpoint_seconds': interval})})
    root.facade.session_key = 'sch_' + 'a' * 32
    bindings.bind_session(session_key=root.facade.session_key, instance_id=instance.instance_id)
    root.call_tool('artifact_ingest_text', {'name': 'goal', 'text': 'Compute 2+2; retain original criteria and all sealed trials.'})
    root.call_tool('progression_command', {'command': 'pause'})
    from scidiscovery.artifact_agent.approval_ui.home_render import session_controls
    proposal = bindings.loop_authorization_proposal(instance_id=instance.instance_id, session_key=root.facade.session_key)
    html = session_controls([], token='fixture', csrf='fixture', current=instance,
        progression=root.call_tool('progression_status', {}), loop_proposal=proposal)
    assert 'worker_checkpoint_seconds' in html and str(interval) in html
    authorize_loop(runtime, instance.instance_id, root.facade.session_key, 'goal')
    root.call_tool('progression_command', {'command': 'start', 'mode': 'interactive', 'objective_name': 'goal'})
    proposal = _proposal(hypothesis_keys=('mechanism',))
    proposal.pop('research_objective_key')
    subject = _complete(runtime, root, 'hypothesis', 'science.hypothesis.propose.v1',
        {'subject': 'goal'}, proposal, measure_usage=True)
    assert root.call_tool('operation_invoke', _request(subject))['result']['state'] == 'queued'
    worker = attached_worker(runtime, root, 'experiment')
    opened = worker.call_tool('worker_open_assignment', {})
    now[0] = datetime.fromisoformat(runtime.runs.status(worker._run_id).started_at).timestamp()
    return runtime, instance, root, worker, opened, now


@pytest.mark.parametrize('interval', [0, 30])
def test_actual_startup_heartbeat_stage_and_safe_boundary(tmp_path, interval):
    runtime, instance, root, worker, opened, now = _owner(tmp_path, interval)
    startup = json.loads(Path(opened['start_here_path']).read_bytes())
    heartbeat = worker.call_tool('worker_heartbeat', {})
    if not interval:
        assert 'checkpoint' not in heartbeat['budget']
        assert 'checkpoint' not in startup['reading']
        assert 'checkpoint' not in worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Optional design.'})
        return
    before = heartbeat['budget']
    assert before['checkpoint']['index'] == 0 and not before['checkpoint']['due']
    assert 'original criterion' in startup['reading']['checkpoint']
    # A native command has no Worker MCP boundary: elapsed time alone performs
    # no handoff, interruption, acknowledgement or new Root decision.
    actual = subprocess.run([sys.executable, '-B', '-c', 'print(2+2)'], capture_output=True, timeout=5, check=True)
    assert actual.stdout == b'4\n'
    now[0] += interval
    assert runtime.runs.status(worker._run_id).state == 'running'
    due = worker.call_tool('worker_heartbeat', {})['budget']
    assert due['checkpoint']['index'] == 1 and due['checkpoint']['due']
    stage = worker.call_tool('worker_experiment_stage', {'stage': 'validity',
        'conclusion': 'Cheap discriminator under original criterion remains useful.', 'remaining_question': 'Check the bounded contrast.'})
    assert stage['state'] == 'sealed' and stage['checkpoint'] == due['checkpoint']
    assert worker.call_tool('worker_experiment_stage', {'stage': 'validity',
        'conclusion': 'Cheap discriminator under original criterion remains useful.', 'remaining_question': 'Check the bounded contrast.'}) == stage
    assert worker.call_tool('worker_open_assignment', {})['budget']['checkpoint'] == due['checkpoint']
    assert runtime.runs.status(worker._run_id).state == 'running'
    assert due['deadline_at'] == before['deadline_at'] and due['remaining_seconds'] <= before['remaining_seconds'] - interval
    private = runtime.runs.status(worker._run_id)
    encoded = json.dumps(stage['checkpoint'])
    assert private.run_id not in encoded and private.recovery_policy['loop_id'] not in encoded
    assert len(encoded.encode()) < 256 and 'instruction' not in stage['checkpoint']
    preview = root.call_tool('run_status', {'name': 'experiment', 'stage_offset': 0})['sealed_stages']
    assert preview['final_selection'] == 'pending' and preview['items'][0]['reference'] == stage['reference']
    refused = root.call_tool('operation_preflight', {'name': 'premature_analysis', 'operation_id': 'science.result.analyze.v1',
        'inputs': [{'port': 'subject', 'artifact_names': [stage['artifact_name']]}]})
    assert not refused['admissible']


def test_frozen_original_loop_and_legacy_missing_field(tmp_path):
    runtime, instance, root, worker, opened, now = _owner(tmp_path)
    run = runtime.runs.status(worker._run_id)
    bindings = runtime.scheduler_bindings
    old_loop = run.recovery_policy['loop_id']
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update={'progression': settings.progression.model_copy(
        update={'worker_checkpoint_seconds': 600})})
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerInstanceConflict
    with pytest.raises(SchedulerInstanceConflict, match='requires resolved work'):
        authorize_loop(runtime, instance.instance_id, root.facade.session_key, 'goal')
    now[0] += 30
    budget = worker.call_tool('worker_open_assignment', {})['budget']
    assert budget['loop']['id'] == old_loop and budget['checkpoint']['interval_seconds'] == 30
    assert budget['checkpoint']['index'] == 1 and budget['run_deadline_at'] == run.deadline_at
    row = bindings.progression_status(instance_id=instance.instance_id, internal=True)
    checkpoint = json.loads(row['checkpoint_json'])
    checkpoint['loop_authorizations'][old_loop]['config']['effective']['progression'].pop('worker_checkpoint_seconds')
    # Historical configuration fixture only; no live DB mutation.
    from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
    with bindings._connect() as db:
        checkpoint = store_checkpoint(db, instance.instance_id, checkpoint)
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
            (checkpoint, instance.instance_id))
    assert 'checkpoint' not in worker.call_tool('worker_heartbeat', {})['budget']
    assert 'checkpoint' not in json.loads(Path(worker.call_tool('worker_open_assignment', {})['start_here_path']).read_bytes())['reading']


def test_projection_secondary_failure_preserves_success_receipt(tmp_path, monkeypatch):
    runtime, instance, root, worker, opened, now = _owner(tmp_path)
    def unavailable(status):
        assert worker._active_attempt is None  # Entire observed-call finally ran.
        raise OSError('local reminder read failed')
    with monkeypatch.context() as patch:
        patch.setattr(runtime.runs, 'worker_budget', unavailable)
        patch.setattr(worker, '_record_tool_failure', lambda *args: pytest.fail('Reminder became a tool failure'))
        reply = worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Exact sealed finding.'})
    assert reply['state'] == 'sealed' and reply['checkpoint']['availability'] == 'unavailable'
    record = runtime.runs.sealed_material_record(runtime.runs.status(worker._run_id), reply['reference'])
    assert json.loads(runtime.artifacts.read(_artifact(runtime, instance, reply['artifact_name']).ref))['conclusion'] == 'Exact sealed finding.'
    assert record['producer_run_id'] == worker._run_id
    # Retry the exact stage reuses its receipt; the failed reminder did not
    # replace the scientific evidence or require effect replay.
    again = worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Exact sealed finding.'})
    assert again['reference'] == reply['reference']


def _finite_final(worker, opened):
    workspace = Path(opened['workspace_path'])
    def publish(name, raw, sources):
        (workspace / 'scratch' / name).write_bytes(raw)
        return worker.call_tool('worker_publish_files', {'files': [{'path': 'scratch/' + name, 'purpose': 'Finite native evidence'}],
            'source_aliases': sources})['files'][0]['reference']
    code = publish('sum.py', b'print(2+2)\n', ['hypothesis_portfolio'])
    impl = worker.call_tool('worker_experiment_stage', {'stage': 'implementation', 'conclusion': 'Exact sum program.', 'materials': [code]})['reference']
    actual = subprocess.run([sys.executable, '-B', 'sum.py'], cwd=workspace / 'scratch', capture_output=True, timeout=5, check=True)
    log = publish('sum.log', actual.stdout + actual.stderr, [impl])
    result = publish('sum.txt', actual.stdout, [impl])
    execution = worker.call_tool('worker_experiment_stage', {'stage': 'execution', 'conclusion': 'Executed finite sum.',
        'native_execution': {'implementation': impl, 'state': 'succeeded', 'logs': [log], 'results': [result]}})['reference']
    validity = worker.call_tool('worker_experiment_stage', {'stage': 'validity', 'conclusion': 'Observed 4 under original criterion.', 'materials': [execution]})['reference']
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'schema_version': 1, 'payload': {
        'summary': 'Original bounded question answered; global trial obligations retained.', 'outcome': 'completed',
        'remaining_question': 'Global requirements remain outside this bounded delivery.',
        'limitations': ['Worker-reported native execution without independent attestation.'], 'adopted_stages': [impl, execution, validity]}}))
    measured_fixture_usage(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_real_checkpoint_final_analysis_successor_analysis_lineage(tmp_path):
    runtime, instance, root, worker, opened, now = _owner(tmp_path)
    original = runtime.runs.status(worker._run_id)
    now[0] += 30
    assert worker.call_tool('worker_heartbeat', {})['budget']['checkpoint']['due']
    _finite_final(worker, opened)
    experiment = root.call_tool('run_status', {'name': 'experiment'})['output_artifact_name']
    payload = {'summary': 'Bounded observation retained; original global criteria remain.', 'overall_verdict': 'inconclusive',
        'claim_allowed': False, 'next_action': 'One original-criterion contrast remains useful.',
        'remaining_contradiction': 'Global requirements remain unresolved.', 'limitations': ['Authored fixture judgment.']}
    a1 = _complete(runtime, root, 'analysis1', 'science.result.analyze.v1', {'subject': experiment}, payload,
        verdict='inconclusive', measure_usage=True)
    request = {**_request(experiment), 'name': 'successor'}
    request['inputs'].append({'port': 'scientific_materials', 'artifact_names': [a1]})
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    w2 = attached_worker(runtime, root, 'successor')
    opened2 = w2.call_tool('worker_open_assignment', {})
    bound = {item.port_name: item.artifact_ref for item in runtime.runs.status(w2._run_id).inputs}
    assert bound['hypothesis_portfolio'] == next(item.artifact_ref for item in original.inputs if item.port_name == 'hypothesis_portfolio')
    assert bound['scientific_materials'] == _artifact(runtime, instance, a1).ref
    _finite_final(w2, opened2)
    second = root.call_tool('run_status', {'name': 'successor'})['output_artifact_name']
    _complete(runtime, root, 'analysis2', 'science.result.analyze.v1', {'subject': second}, payload,
        verdict='inconclusive', measure_usage=True)
    a2 = runtime.runs.status(runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='analysis2'))
    assert next(item.artifact_ref for item in a2.inputs if item.port_name == 'experiment_results') == _artifact(runtime, instance, second).ref
    assert runtime.runs.status(original.run_id).state == 'completed'  # Both histories remain sealed.
    assert 'checkpoint' not in runtime.runs.worker_budget(a2)


@pytest.mark.parametrize('value', [1, 29, 86401, True])
def test_checkpoint_configuration_rejects_out_of_bounds(value):
    with pytest.raises(ValueError, match='worker_checkpoint_seconds'):
        ProgressionSettings(worker_checkpoint_seconds=value)
