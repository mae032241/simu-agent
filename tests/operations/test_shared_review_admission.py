"""One admission rule from public contract through exact reviewer attachment."""
import json
from pathlib import Path
import pytest
from scidiscovery.artifact_agent.service.run_records import RunStateConflict
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from tests.operations.test_frozen_input_execution import _system
from tests.operations.test_progression import progression


def request(name, subject):
    return dict(name=name, operation_id='science.object.review.v1',
        inputs=[dict(port='subject', artifact_names=[subject])],
        instruction='Review this exact subject independently.')


def attach(runtime, instance, root, name):
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace='run', name=name)
    runtime.runs.worker_connections.attach(run_id=run_id, platform_session='audit', thread_id=name)
    return run_id


def test_raw_subject_rejected_before_run_or_worker_creation(tmp_path, monkeypatch):
    runtime, instance, root, _ = _system(tmp_path, monkeypatch)
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_unified_mcp import rpc, result
    policy = result(rpc(UnifiedMCPRouter(root), 'scid_describe',
        {'name':'science.object.review.v1'}))['operations'][0]['review_subject_policy']
    assert policy['ports'] == ['subject'] and 'Original user text' in policy['requirement']
    req = request('raw-review', 'source')
    result = root.call_tool('operation_preflight', req)
    assert result['admissible'] is False
    assert result['reason_code'] == 'review_subject_not_authored'
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    before = len(runtime.runs.list(instance_id=instance.instance_id))
    with pytest.raises(RootToolError, match='review_subject_not_authored'):
        root.call_tool('operation_invoke', req)
    assert len(runtime.runs.list(instance_id=instance.instance_id)) == before


def test_transform_retains_exact_authors_and_rejects_self_review(tmp_path, monkeypatch):
    runtime, instance, root, split = _system(tmp_path, monkeypatch)
    intake = root.call_tool('run_status', {'name':'author'})['output_artifact_name']
    assert root.call_tool('operation_invoke', request('original-review', intake))['result']['state'] == 'queued'
    original_id = attach(runtime, instance, root, 'original-review')
    runtime.runs.record_failure(original_id, reason='End audit control case.', expected_state='queued', expected_last_activity_at=None)
    root.call_tool('operation_invoke', split)
    req = request('split-review', 'split.scientific_foundation')
    assert root.call_tool('operation_preflight', req)['admissible']
    assert root.call_tool('operation_invoke', req)['result']['state'] == 'queued'
    run_id = attach(runtime, instance, root, 'split-review')
    original = runtime.scheduler_bindings.resolve(instance=instance.instance_id,namespace='run',name='author')
    with pytest.raises(RunStateConflict, match='different Agent'):
        runtime.runs.worker_connections.attach(run_id=run_id,
            platform_session='source-test-session',thread_id='worker-'+original)


def test_generated_review_can_read_objective_through_reference(tmp_path, monkeypatch):
    from tests.operations.test_experiment_continuation import continuation
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    handoff = f.worker.call_tool('worker_experiment_execute', {'action':'review', 'implementation':f.alias})
    req = handoff['review']['request']
    assert [i['port'] for i in req['inputs']] == ['subject']
    assert 'research objective' in req['instruction']
    f.root.call_tool('operation_invoke', req)
    run_id = attach(f.runtime, f.instance, f.root, req['name'])
    status = f.runs.status(run_id)
    assert {i.port_name for i in status.inputs} == {'subject'}
    compiled = f.catalog.operation('science.object.review.v1')
    worker = LocalWorkerMCPRouter(f.runs,operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,run_id=run_id,trusted_caller=('audit',req['name']))
    opened = worker.call_tool('worker_open_assignment', {})
    directory = worker.call_tool('worker_reference_read', {'source':'subject'})
    # Counterexample to a suspected defect: exact provenance is readable through
    # the declared reference tool even though it is not a direct input port.
    goal = next(item for item in directory['references'] if item['alias']=='objective_source')
    read = worker.call_tool('worker_reference_read', {'source':'subject','action':'read','reference':goal['reference']})
    assert read['source']
    payload = json.loads(f.runtime.artifacts.read(status.inputs[0].artifact_ref))
    assert set(payload) == {'implementation','scientific_files'}


def test_startup_preserves_frozen_review_requirement(tmp_path, monkeypatch):
    from tests.operations.test_experiment_continuation import continuation
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    assignment = json.loads((f.workspace/'assignment.json').read_text())
    startup = json.loads((f.workspace/'worker-start.json').read_text())
    assert assignment['execution_requirements']['independent_implementation_review'] == 'required'
    assert startup['execution_requirements'] == assignment['execution_requirements']


def test_active_slot_has_same_repairable_preflight_and_creation_rejection(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    runtime, instance, root, _ = _system(tmp_path, monkeypatch)
    intake = root.call_tool('run_status', {'name':'author'})['output_artifact_name']
    root.call_tool('operation_invoke', request('first-review', intake))
    req = request('second-review', intake)
    checked = root.call_tool('operation_preflight',req)
    assert not checked['admissible'] and checked['reason_code'] == 'operation_busy'
    with pytest.raises(RootToolError, match='operation_busy'):
        root.call_tool('operation_invoke',req)


@pytest.mark.parametrize("verdict", ["pass", "revise"])
def test_background_review_wait_dispatch_complete_and_resume(tmp_path, monkeypatch, verdict):
    from copy import copy
    from tests.operations.test_experiment_continuation import continuation
    from tests.operations.test_progression import Host
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    from tests.operations.worker_fixtures import attached_worker
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    request = f.worker.call_tool('worker_experiment_execute',
        {'action':'review','implementation':f.alias})['review']['request']
    assert f.worker.call_tool('worker_experiment_prepare', {})['state'] == 'waiting_for_review'
    assert f.root.call_tool('run_status',{'name':'continuation','intent':'status'})['review_dependency']['state'] == 'requested'
    user = 'sch_' + 'a' * 32
    f.runtime.scheduler_bindings.bind_session(session_key=user, instance_id=f.instance.instance_id)
    f.root.facade.session_key = user
    f.root.call_tool('progression_command',{'command':'pause'})
    f.root.call_tool('progression_command',{'command':'start','mode':'background','objective_name':'objective'})
    def facade(session):
        result = copy(f.root.facade)
        result.session_key = session
        return result
    now = [1000.0]
    coordinator = ProgressionCoordinator(runtime=f.runtime,host_factory=Host,facade_factory=facade,clock=lambda:now[0])
    try:
        coordinator.tick()
        host = coordinator.host
        assert 'review_requests' in host.prompts[-1]
        root = type(f.root)(facade(host.scheduler_session))
        wrong = dict(request, name='unrelated-review', inputs=[{'port':'subject', 'artifact_names':['observe.output']}])
        rejected = root.call_tool('operation_preflight', wrong)
        assert not rejected['admissible'] and rejected['reason_code'] == 'background_task_busy'
        assert root.call_tool('operation_preflight',request)['admissible']
        created = root.call_tool('operation_invoke',request)
        assert created['result']['state'] == 'queued'
        wait = f.runs.review_wait(f.run_id)
        assert wait['state'] == 'queued' and wait['reviewer_run_id']
        unrelated = dict(f.invocation,name='unrelated')
        assert not root.call_tool('operation_preflight',unrelated)['admissible']
        worker = attached_worker(f.runtime,root,request['name'])
        opened = worker.call_tool('worker_open_assignment',{})
        host.finish()
        now[0] += 6
        coordinator.tick()
        assert len(host.prompts) == 1  # queue/open/heartbeat cannot wake Root again
        Path(opened['output_directory'],'result.json').write_text(json.dumps({'payload':{'verdict':verdict,'summary':'Exact implementation reviewed.'}}))
        assert worker.call_tool('worker_submit_result',{})['state']=='completed'
        host.finish()
        now[0] += 6
        coordinator.tick()
        assert len(host.prompts)==2
        assert 'notify the existing owner' in host.prompts[-1]
        assert f.runs.review_wait(f.run_id)['state']=='completed'
        # A fresh service object reads the same durable wait after restart.
        from scidiscovery.artifact_agent.service.runs import RunService
        restarted = RunService(database_path=f.runs.database_path, artifacts=f.runtime.artifacts,
            backend=f.runtime.local_backend, operation_catalog=f.catalog,
            scheduler_bindings=f.runtime.scheduler_bindings, service_actor=f.runs.service_actor,
            agent_settings=f.runs.agent_settings)
        assert restarted.review_wait(f.run_id) == f.runs.review_wait(f.run_id)
        assert f.runs.worker_review_wait(f.run_id,'worker_experiment_prepare',{}) is None
        # Waiting is durable, does not create a replacement owner, and an exact
        # repeated request never erases the already completed reviewer.
        outcome = f.worker.call_tool('worker_experiment_execute',{'action':'review','implementation':f.alias})['review']
        assert outcome['state'] == 'completed'
        assert outcome['outcome']['verdict'] == verdict
        if verdict == 'revise':
            from scidiscovery.operation_contract import DiagnosticError
            with pytest.raises(DiagnosticError) as denied:
                f.worker.call_tool('worker_experiment_execute', {'action':'start', 'implementation':f.alias})
            assert denied.value.details[0]['code'] == 'experiment_execution_review_not_passed'
        assert outcome['outcome']['summary'] == 'Exact implementation reviewed.'
        assert not {'artifact_ref', 'run_id', 'reviewer_run_id'} & outcome.keys()
        assert f.runs.review_wait(f.run_id)['reviewer_run_id']==wait['reviewer_run_id']
        assert f.runs.status(f.run_id).state=='running'
        checkpoint=json.loads(f.runtime.scheduler_bindings.progression_status(
            instance_id=f.instance.instance_id, internal=True)['checkpoint_json'])
        assert request['name'] in checkpoint['admissions']
    finally:
        coordinator.close()


def test_review_policy_and_transform_authorship_are_compiled():
    from tests.operations.test_agent_contract_alignment import _catalog
    from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    catalog = _catalog()
    projected = next(v for v in catalog.scheduler_projection() if v.operation_id=='science.object.review.v1')
    assert projected.review_subject_policy['ports']==['subject']
    assert 'Original user text' in projected.review_subject_policy['requirement']
    split = next(v for v in PLUGIN.operations if v.operation_id=='science.intake.split.v1')
    for ports in (('missing',), ('scientific_intake','scientific_intake')):
        plugin = PLUGIN.model_copy(update={'operations':tuple(
            v.model_copy(update={'authorship_source_ports':ports}) if v==split else v for v in PLUGIN.operations)})
        with pytest.raises(CatalogCompileError) as caught:
            compile_catalog((CORE_PLUGIN,plugin))
        assert caught.value.reason_code=='authorship_source_invalid'



def test_missing_author_identity_is_rejected_before_creation(tmp_path, monkeypatch):
    runtime, instance, root, _ = _system(tmp_path, monkeypatch)
    author = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='author')
    intake = root.call_tool('run_status', {'name':'author'})['output_artifact_name']
    with runtime.runs._connect() as db:
        db.execute('DELETE FROM worker_connections WHERE run_id=?', (author,))
    check = root.call_tool('operation_preflight', request('unknown-author', intake))
    assert not check['admissible']
    assert check['reason_code'] == 'review_author_identity_unavailable'


def test_creation_rechecks_slot_even_after_admissible_preflight(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    runtime, instance, root, _ = _system(tmp_path, monkeypatch)
    intake = root.call_tool('run_status', {'name':'author'})['output_artifact_name']
    req = request('later-review', intake)
    assert root.call_tool('operation_preflight', req)['admissible']
    root.call_tool('operation_invoke', request('slot-owner', intake))
    # Simulate stale outer observation; only the transaction's decision can stop creation.
    real = runtime.runs.validate_admission
    monkeypatch.setattr(runtime.runs, 'validate_admission', lambda *a, **kw:
        real(*a, **kw) if kw.get('connection') is not None else None)
    before = len(runtime.runs.list(instance_id=instance.instance_id))
    with pytest.raises(RootToolError, match='operation_busy'):
        root.call_tool('operation_invoke', req)
    assert len(runtime.runs.list(instance_id=instance.instance_id)) == before


def test_final_background_task_slot_is_not_charged_twice(progression, monkeypatch):
    from tests.operations.test_local_worker_contracts import _invoke
    p = progression
    p.coordinator.tick()
    root = type(p.root)(p.facade(p.coordinator.host.scheduler_session))
    settings = p.runtime.scheduler_bindings.control_settings(p.instance)
    settings['effective']['progression']['max_tasks'] = 1
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET config_json=? WHERE instance_id=?',
            (json.dumps(settings), p.instance))
    monkeypatch.setattr(p.runtime.scheduler_bindings, 'control_settings', lambda _: settings)
    _invoke(root, 'last-permitted-task')
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1


def test_review_policy_hides_private_and_derived_ports():
    from scidiscovery.general_science_experiment_review import OPERATION
    from scidiscovery.operations.spec import InputDerivationSpec, scheduler_operation_view
    subject = OPERATION.inputs[0]
    hidden = subject.model_copy(update={'name':'private_subject', 'agent_visible':False})
    derived = subject.model_copy(update={'name':'derived_subject',
        'derivation':InputDerivationSpec(anchor_port='subject')})
    spec = OPERATION.model_copy(update={'inputs':(*OPERATION.inputs, hidden, derived),
        'independent_review_ports':('subject', 'private_subject', 'derived_subject')})
    view = scheduler_operation_view(spec).model_dump(mode='json')
    assert view['review_subject_policy']['ports'] == ['subject']
    assert 'private_subject' not in json.dumps(view)
    assert 'derived_subject' not in json.dumps(view)


def test_absent_optional_contributor_does_not_require_agent_binding(tmp_path, monkeypatch):
    from tests.operations import test_frozen_input_execution as fixtures
    split = next(op for op in fixtures.GENERAL.operations if op.operation_id == 'science.intake.split.v1')
    optional = split.inputs[0].model_copy(update={'name':'optional_coauthor', 'min_items':0})
    projected = split.model_copy(update={'inputs':(*split.inputs, optional),
        'authorship_source_ports':('scientific_intake', 'optional_coauthor')})
    plugin = fixtures.GENERAL.model_copy(update={'operations':tuple(
        projected if op == split else op for op in fixtures.GENERAL.operations)})
    monkeypatch.setattr(fixtures, 'GENERAL', plugin)
    runtime, instance, root, split_request = fixtures._system(tmp_path, monkeypatch)
    root.call_tool('operation_invoke', split_request)
    assert root.call_tool('operation_preflight', request('review', 'split.scientific_foundation'))['admissible']


def test_shared_authorship_diagnostic_uses_visible_anchor(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scidiscovery.general_science_experiment_review import OPERATION
    from scidiscovery.operations.spec import InputDerivationSpec
    from scidiscovery.operations.invoke import OperationInvocationError
    runtime, instance, root, _ = _system(tmp_path, monkeypatch)
    source_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='artifact', name='source')
    subject = OPERATION.inputs[0]
    hidden = subject.model_copy(update={'name':'private_subject',
        'derivation':InputDerivationSpec(anchor_port='subject')})
    spec = OPERATION.model_copy(update={'inputs':(*OPERATION.inputs, hidden),
        'independent_review_ports':('private_subject',)})
    selected = SimpleNamespace(port_name='private_subject', artifact_name='source',
        artifact_ref=runtime.artifacts.get_by_id(source_id).ref)
    with runtime.runs._connect() as db, pytest.raises(OperationInvocationError) as rejected:
        runtime.runs.worker_connections.review_authors(db, SimpleNamespace(spec=spec), [selected], instance.instance_id)
    assert rejected.value.port == 'subject'
    assert 'private_subject' not in json.dumps(rejected.value.details)
