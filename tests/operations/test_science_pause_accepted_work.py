"""Science pauses stop new research while exact accepted work retains authority."""
import json
import hashlib
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from tests.operations.test_local_worker_contracts import _write_result
from tests.operations.test_progression import progression, row, checkpoint
from tests.operations.test_progress_assist import configure
from tests.operations.test_scientific_progress import active, request
from tests.operations.test_progress_shadow import native_delivery
from tests.operations.test_unified_mcp import call, result
from blind_csv_plugin.contracts import CsvReview
from tests.operations.test_l3_review_and_human_policy import _envelope


def accepted_before_pause(p, monkeypatch, *, review=False, before_pause=None, **limits):
    monkeypatch.setattr('scidiscovery.artifact_agent.service.scheduling_control.time', lambda: p.now[0])
    configure(p, **limits)
    root = active(p)
    if before_pause:
        before_pause(root)
    gateway = UnifiedMCPRouter(root)
    for index in range(3):
        name = 'prior-' + str(index)
        root.call_tool('operation_invoke', request(name))
        prior = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name=name)
        profile = p.runtime.runs.status(prior).execution_profile['profile']
        result(call(gateway, 'worker_attach', dict(name=name, thread_id=name), session='native-root'))
        result(call(gateway, 'worker_open_assignment', child=name, session='native-root', profile=profile))
        compiled = p.catalog.operation('blind.csv.observe.v1')
        worker = LocalWorkerMCPRouter(p.runtime.runs, operation_id=compiled.spec.operation_id,
            operation_digest=compiled.digest, run_id=prior, trusted_caller=('native-root', name))
        worker.call_tool('worker_open_assignment', {})
        _write_result(worker)
        assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
        if index < 2:
            native_delivery(p, root, 'prior-' + str(index))
    root.call_tool('operation_invoke', request('accepted'))
    run_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='accepted')
    profile = p.runtime.runs.status(run_id).execution_profile['profile']
    if review:
        result(call(gateway, 'worker_attach', dict(name='accepted', thread_id='accepted-child'), session='native-root'))
        result(call(gateway, 'worker_open_assignment', child='accepted-child', session='native-root', profile=profile))
        subject_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='artifact', name='prior-2.output')
        review_request = dict(name='exact-review', operation_id='blind.csv.review.v1',
            inputs=[dict(port='csv_observation', artifact_names=['prior-2.output']),
                    dict(port='source_table', artifact_names=['source_csv'])], instruction='Review the exact accepted dependency.')
        # Control-generated immutable wait, then actual public preflight/create/attach.
        p.runtime.runs.request_implementation_review(run_id, p.runtime.artifacts.get_by_id(subject_id).ref, review_request)
    native_delivery(p, root, 'prior-2')
    p.coordinator.host.finish()
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    return root, gateway, run_id, profile


def test_science_pause_allows_original_first_attach_and_failure_settlement(progression, monkeypatch):
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch)
    before = checkpoint(p)
    result(call(gateway, 'worker_attach', dict(name='accepted', thread_id='accepted-child'), session='native-root'))
    root.call_tool('run_record_failure', dict(name='accepted', reason='Reconciled accepted task failure.',
        expected_state='queued', expected_last_activity_at=None))
    assert p.runtime.runs.status(run_id).state == 'failed'
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert checkpoint(p)['rounds'] == before['rounds']
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', request('new-research'))


@pytest.mark.parametrize('frontend', [False, True])
def test_science_pause_exact_review_public_creation_and_independent_attach(progression, monkeypatch, frontend):
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, review=True)
    platform = 'native-root'
    if frontend:
        root = type(root)(p.facade(p.user))
        gateway = UnifiedMCPRouter(root)
        platform = 'front-root'
    req = p.runtime.runs.review_wait(run_id)['request']
    checked = root.call_tool('operation_preflight', req)
    assert checked['admissible'], checked
    created = root.call_tool('operation_invoke', req)
    budget_before = checkpoint(p)
    assert root.call_tool('operation_invoke', req)['result']['name'] == created['result']['name']
    assert checkpoint(p)['admissions'] == budget_before['admissions']
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', dict(req, instruction='A changed purpose.', on_conflict='create_revision'))
    result(call(gateway, 'worker_attach', dict(name='exact-review', thread_id='independent-child'), session=platform))
    opened = result(call(gateway, 'worker_open_assignment', child='independent-child', session=platform, profile=profile))
    subject = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='artifact', name='prior-2.output')
    payload = CsvReview(subject_sha256=hashlib.sha256(p.runtime.artifacts.read(p.runtime.artifacts.get_by_id(subject).ref)).hexdigest(),
        verdict='pass', rationale='Independent bounded review of the exact original.').model_dump(mode='json')
    Path(opened['output_directory'], 'result.json').write_bytes(_envelope(payload))
    assert result(call(gateway, 'worker_submit_result', child='independent-child', session=platform, profile=profile))['state'] == 'completed'
    assert p.runtime.runs.review_wait(run_id)['state'] == 'completed'
    assert row(p)['state'] == 'paused'


@pytest.mark.parametrize('outcome', ['completed', 'failed', 'timed_out'])
def test_science_pause_same_host_finishes_accepted_review_chain(progression, monkeypatch, outcome):
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, review=True)
    host = p.coordinator.host
    elapsed = root.call_tool('progression_status', {})['budget']['elapsed_seconds']
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 2
    assert 'exact-review' in host.prompts[-1]
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert checkpoint(p)['rounds'] == 2
    req = p.runtime.runs.review_wait(run_id)['request']
    result(call(gateway, 'operation_invoke', req, session='native-root'))
    assert p.runtime.runs.review_wait(run_id)['state'] == 'queued'
    p.coordinator.tick()
    assert not host.interrupted  # Root still needs to spawn and attach this exact reviewer.
    result(call(gateway, 'worker_attach', dict(name='exact-review', thread_id='independent-child'), session='native-root'))
    opened = result(call(gateway, 'worker_open_assignment', child='independent-child', session='native-root', profile=profile))
    assert p.runtime.runs.review_wait(run_id)['state'] == 'running'
    p.coordinator.tick()
    assert not host.interrupted
    host.finish()
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 2  # Waiting does not open another model round.
    assert not host.interrupted
    if outcome == 'completed':
        subject = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='artifact', name='prior-2.output')
        payload = CsvReview(subject_sha256=hashlib.sha256(p.runtime.artifacts.read(p.runtime.artifacts.get_by_id(subject).ref)).hexdigest(),
            verdict='pass', rationale='Independent bounded review of the accepted dependency.').model_dump(mode='json')
        Path(opened['output_directory'], 'result.json').write_bytes(_envelope(payload))
        assert result(call(gateway, 'worker_submit_result', child='independent-child', session='native-root', profile=profile))['state'] == outcome
    else:
        reviewer_id = p.runtime.runs.review_wait(run_id)['reviewer_run_id']
        reviewer = p.runtime.runs.status(reviewer_id)
        with monkeypatch.context() as expiry:
            if outcome == 'timed_out':
                # Advance only the review deadline check; the parent remains live.
                expiry.setattr('scidiscovery.artifact_agent.service.runs.expired', lambda value: value == reviewer.deadline_at)
            result(call(gateway, 'run_record_failure', dict(name='exact-review', reason='Confirmed review ' + outcome,
                timed_out=outcome == 'timed_out', expected_state='running', expected_last_activity_at=reviewer.last_activity_at), session='native-root'))
    terminal_state = 'completed' if outcome == 'completed' else 'failed'  # Real timeout settlement seals a failed Run.
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 3
    brief = json.loads(host.prompts[-1].split('\n')[-1])
    assert brief['review_requests'][0]['state'] == terminal_state
    assert brief['review_requests'][0]['review_name'] == 'exact-review'
    assert 'read its sealed conclusion and notify the existing owner' in brief['review_requests'][0]['instruction']
    sealed = result(call(gateway, 'run_status', dict(name='exact-review', intent='decision'), session='native-root'))
    assert sealed['state'] == terminal_state
    if outcome != 'completed':
        assert ('time limit' if outcome == 'timed_out' else 'Run failed') in sealed['reason']
    # Native send_message is transport: simulate delivery to the actual attached owner.
    owner, = [identity for identity in p.runtime.runs.native_identities(run_id) if identity['role'] == 'worker']
    assert gateway.connections.resolve(platform_session=owner['platform_session'], thread_id=owner['thread_id']).run_id == run_id
    notifications = [(owner['thread_id'], sealed['state'])]
    assert notifications == [('accepted-child', terminal_state)]
    compiled = p.catalog.operation('blind.csv.observe.v1')
    worker = LocalWorkerMCPRouter(p.runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=run_id, trusted_caller=(owner['platform_session'], owner['thread_id']))
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    assert result(call(gateway, 'worker_submit_result', child=owner['thread_id'], session=owner['platform_session'], profile=profile))['state'] == 'completed'
    assert p.runtime.runs.review_wait(run_id) is None
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', request('unrelated'))
    host.finish()
    p.coordinator.tick()
    assert host.closed and p.coordinator.host is None
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert checkpoint(p)['rounds'] == 3
    assert root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == elapsed + 12
    p.now[0] += 20
    assert root.call_tool('progression_status', {})['budget']['elapsed_seconds'] == elapsed + 12


def test_science_pause_rejects_mismatched_dependency_session_and_instance(progression, monkeypatch):
    from dataclasses import replace
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, review=True)
    req = p.runtime.runs.review_wait(run_id)['request']
    bindings = p.runtime.scheduler_bindings
    bindings.bind(instance=p.instance, namespace='artifact', name='other-source',
        object_id=bindings.resolve(instance=p.instance, namespace='artifact', name='source_csv'))
    for wrong in (dict(req, instruction='Do a different scientific task.'),
            dict(req, inputs=[dict(port='csv_observation', artifact_names=['prior-1.output']), req['inputs'][1]]),
            dict(req, inputs=[req['inputs'][0], dict(port='source_table', artifact_names=['other-source'])])):
        assert not root.call_tool('operation_preflight', wrong)['admissible']
        with pytest.raises(Exception):
            root.call_tool('operation_invoke', wrong)
    from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
    parsed = OperationCallInput.model_validate(req)
    bound, _ = root.facade._configured_operation_call({field: getattr(parsed, field) for field in type(parsed).model_fields})
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.runtime.runs.validate_admission(replace(bound, compiled=replace(bound.compiled, digest='another-version')),
            instance_id=p.instance)
    stranger = 'sch_' + 'd' * 32
    bindings.bind_session(session_key=stranger, instance_id=p.instance)
    wrong_root = type(root)(p.facade(stranger))
    assert not wrong_root.call_tool('operation_preflight', req)['admissible']
    assert 'error' in call(UnifiedMCPRouter(wrong_root), 'worker_attach',
        dict(name='accepted', thread_id='wrong-child'), session='wrong-root')
    other = bindings.create_instance(name='other-accepted-instance', title='Other', objective='Separate authority')
    bindings.bind(instance=other.instance_id, namespace='run', name='accepted', object_id=run_id)
    bindings.bind_session(session_key=stranger, instance_id=other.instance_id)
    assert 'error' in call(UnifiedMCPRouter(wrong_root), 'worker_attach',
        dict(name='accepted', thread_id='wrong-instance-child'), session='wrong-root')
    with p.runtime.runs._connect() as db:
        saved = json.loads(db.execute('SELECT review_wait_json FROM runs WHERE run_id=?', (run_id,)).fetchone()[0])
        saved.pop('operation_digest')
        db.execute('UPDATE runs SET review_wait_json=? WHERE run_id=?', (json.dumps(saved), run_id))
    assert root.call_tool('operation_preflight', req)['reason_code'] == 'review_dependency_unfrozen'


@pytest.mark.parametrize('barrier', ['pause', 'stop', 'client', 'unknown'])
def test_science_pause_continuation_cannot_override_explicit_controls_or_unknown(progression, monkeypatch, barrier):
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, review=True)
    bindings = p.runtime.scheduler_bindings
    if barrier in {'pause', 'stop'}:
        p.root.call_tool('progression_command', dict(command=barrier))
    elif barrier == 'client':
        bindings.register_client(session_key=root.facade.session_key)
        bindings.set_client_enabled(session_key=root.facade.session_key, enabled=False, expected=True)
    else:
        bindings.observe_progression(instance_id=p.instance, expected_host=json.loads(row(p)['host_json']),
            changes=dict(fault_class='outcome_unknown', phase='prepared', turn_id=None))
    before = row(p)
    req = p.runtime.runs.review_wait(run_id)['request']
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', req)
    assert 'error' in call(gateway, 'worker_attach', dict(name='accepted', thread_id='unaccepted-child'), session='native-root')
    p.now[0] += 6
    host = p.coordinator.host
    p.coordinator.tick()
    assert len(host.prompts) == 1
    assert p.runtime.runs.review_wait(run_id)['state'] == 'requested'
    assert row(p)['generation'] == before['generation']


def test_exact_review_still_spends_original_task_and_model_round_budgets(progression, monkeypatch):
    p = progression
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, review=True, max_tasks=4, max_rounds=1)
    req = p.runtime.runs.review_wait(run_id)['request']
    check = root.call_tool('operation_preflight', req)
    assert not check['admissible'] and check['reason_code'] == 'background_task_budget_exhausted'
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', req)
    before = checkpoint(p)
    host = p.coordinator.host
    p.now[0] += 6
    p.coordinator.tick()
    assert len(host.prompts) == 1
    assert row(p)['reason'] == 'budget_exhausted'
    assert checkpoint(p)['rounds'] == before['rounds'] == 1


def test_science_pause_keeps_scoped_submitted_execution_settlement(progression, monkeypatch):
    from types import SimpleNamespace
    from tests.operations.test_r4_execution_approval_identity import _NoEffectAdapter, _create_effect, _decide_execution_approval
    from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN
    from tests.operations.test_local_worker_contracts import CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN, compile_catalog
    from scidiscovery.artifact_agent.runtime import open_runtime
    p = progression
    p.runtime = open_runtime(project_root=p.runtime.project_root, state_root=p.runtime.state_root,
        approval_receipt_secret=b'e' * 32)
    p.coordinator.runtime = p.runtime
    p.coordinator.bindings = p.runtime.scheduler_bindings
    p.root.facade.bindings = p.runtime.scheduler_bindings
    p.root.facade.runs = p.runtime.runs
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN, ARCHITECTURE_TEST_PLUGIN))
    p.root.facade._operation_catalog = catalog
    p.runtime.runs.operation_catalog = catalog
    p.root.facade.executions = p.runtime.executions
    p.root.facade.approvals = p.runtime.approvals
    payload = p.runtime.artifacts.register(b'{}', ArtifactRegistration(kind='architecture_test_input',
        schema_id='scidiscovery.architecture-test.v1', payload_schema_version=1, media_type='application/json', creator=p.runtime.actor),
        idempotency_key='accepted-effect-payload')
    bindings = p.runtime.scheduler_bindings
    bindings.bind(instance=p.instance, namespace='artifact', name='effect_input', object_id=payload.artifact_id)
    adapter = _NoEffectAdapter()
    adapter.status = lambda _: 'running'
    adapter.cancel = lambda _: 'cancelled'
    p.root.facade.execution_bridge = ExecutionBridge(p.runtime.executions, adapters={'architecture_fixture:fixture': adapter})
    def before_pause(root):
        _create_effect(root, name='accepted-effect')
        _decide_execution_approval(p.runtime, root, name='accepted-effect')
        root.call_tool('execution_start', dict(name='accepted-effect'), surface='execution')
        _create_effect(root, name='unsubmitted-effect')
    root, gateway, run_id, profile = accepted_before_pause(p, monkeypatch, before_pause=before_pause)
    frontend = type(root)(p.facade(p.user))
    for tool in ('execution_start', 'execution_outputs'):
        with pytest.raises(Exception):
            frontend.call_tool(tool, dict(name='unsubmitted-effect'), surface='execution')
    frontend.call_tool('execution_sync', dict(name='accepted-effect'), surface='execution')
    assert frontend.call_tool('execution_cancel', dict(name='accepted-effect'), surface='execution')['state'] == 'cancelled'
    execution = bindings.resolve(instance=p.instance, namespace='execution', name='accepted-effect')
    def collect(execution_id, *, scope, total_seconds):
        assert execution_id == execution and scope == 'instance:' + p.instance
        # A deterministic collector fixture seals the real service's retained result.
        p.runtime.executions.ingest_result(execution_id=execution_id, external_run_id='unexpected-run', outputs=())
        return dict(state='completed')
    frontend.facade.execution_collection = SimpleNamespace(collect=collect)
    assert frontend.call_tool('execution_collect', dict(name='accepted-effect'), surface='execution')['collection']['state'] == 'completed'
    published = frontend.call_tool('execution_outputs', dict(name='accepted-effect'), surface='execution')
    assert published['result_artifact_name'] == 'accepted-effect.result'
    assert adapter.submit_count == 1 and row(p)['state'] == 'paused'
