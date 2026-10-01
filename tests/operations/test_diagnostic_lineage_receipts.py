"""Recovery identity and immutable report regressions through real Root/Worker routes."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.operations.test_experiment_continuation import continuation
from tests.operations.test_review_delivery_and_debug_scope import debug, debug_service
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.operation_contract import DiagnosticError
from tcad_artifact.local_debug_service import _record_key


def test_prior_receipt_after_later_same_mode_diagnostic(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    collect = service.adapter.collect_with_budget
    sequence = iter(['first diagnostic', 'second diagnostic'])
    monkeypatch.setattr(service.adapter, 'collect_with_budget', lambda *a, **k:
        replace(collect(*a, **k), summary=next(sequence), timing={'elapsed_seconds': .2}))
    debug(f, 'first')
    debug(f, 'second')
    first = debug(f, 'first')
    assert first['summary'] == 'first diagnostic'
    assert first['budget']['created_runs'] == 2
    assert service.adapter.submits == 3
    private = service.exchange_root / 'experiment-workspaces' / f.run_id / 'deck/reports'
    assert json.loads((private / 'preflight-first.json').read_bytes())['summary'] == 'first diagnostic'
    assert json.loads((private / 'preflight-second.json').read_bytes())['summary'] == 'second diagnostic'
    assert json.loads((private / 'preflight.json').read_bytes())['summary'] == 'first diagnostic'


@pytest.mark.parametrize('scope', ['task', 'scientific_subject'])
def test_recovery_changed_objective_budget(tmp_path, monkeypatch, scope):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    limit = 1 if scope == 'task' else 2  # The fixture already charged an independent task.
    policy = service.adapter.policy.model_copy(update={'max_runs': limit, 'budget_scope': scope})
    monkeypatch.setattr(type(service.adapter), 'policy', property(lambda _: policy))
    debug(f, 'first')
    with pytest.raises(DiagnosticError, match=f'attempts={limit}/{limit}'):
        debug(f, 'second')
    recover_changed_objective(f)
    with pytest.raises(DiagnosticError, match=f'attempts={limit}/{limit}'):
        debug(f, 'second')
    assert service.adapter.submits == 2
    assert debug(f, 'first')['budget']['created_runs'] == limit
    assert f.worker.call_tool('worker_experiment_debug', {'action':'status', 'name':'first'})['state'] == 'collected'


def recover_changed_objective(f, *, name='recovered', max_attempts=None):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
    old = f.runs.status(f.run_id)
    subject = next(i.artifact_ref for i in old.inputs if i.port_name == 'objective_source')
    raw = json.loads(f.runtime.artifacts.read(subject))
    raw['statement'] += ' Refine the objective wording.'
    artifact = f.runtime.artifacts.register(canonical_json(raw), ArtifactRegistration(kind='objective',
        schema_id='scidiscovery.research-objective.v1', payload_schema_version=1,
        media_type='application/json', creator=f.runtime.actor), idempotency_key=name + '-objective-revised')
    f.runtime.scheduler_bindings.bind(instance=f.instance.instance_id, namespace='artifact',
        name=name + '-objective-revised', object_id=artifact.artifact_id)
    f.runs.record_failure(f.run_id, reason='fixture interruption', expected_state='running',
        expected_last_activity_at=old.last_activity_at)
    inputs = [{**i, 'artifact_names':[name + '-objective-revised']} if i['port']=='subject' else i for i in f.invocation['inputs']]
    result = f.root.call_tool('operation_invoke', {**f.invocation, 'name':name,
        'draft_from':f.invocation['name'], 'inputs':inputs,
        **({'max_attempts':max_attempts} if max_attempts is not None else {})})
    assert result['result']['state'] == 'queued', result
    recovered = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace='run', name=name)
    assert f.runs.recovery_authorized(recovered, f.run_id)
    f.runs.worker_connections.attach(run_id=recovered, platform_session='recovery-fixture', thread_id=name)
    compiled = f.catalog.operation('science.experiment.v1')
    services = bind_experiment_services(f.runs, compiled, dict(f.coordinator.worker_services), coordinator=f.coordinator)
    f.worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    f.workspace = Path(f.worker.call_tool('worker_open_assignment', {})['workspace_path'])
    f.run_id = recovered
    f.invocation = {**f.invocation, 'name':name, 'inputs':inputs}


def test_changed_goal_keeps_uncertain_reservation_and_blocks_finalization(tmp_path, monkeypatch):
    from copy import deepcopy
    from tests.operations.test_experiment_continuation import submit
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    collect = service.adapter.collect_with_budget
    monkeypatch.setattr(service.adapter, 'collect_with_budget', lambda *a, **k:
        replace(collect(*a, **k), timing={'elapsed_seconds': .2}))
    debug(f, 'first')
    source_path = next((service.exchange_root / 'budgets').glob('*.json'))
    source = json.loads(source_path.read_bytes())
    source_run = f.run_id
    recover_changed_objective(f)
    path = source_path
    assert path.stem == canonical_sha256({'subject':f.coordinator.budget_subject(f.runs.status(f.run_id))})
    pending = deepcopy(source['reservations'][_record_key(source_run, 'first')])
    pending['record'].update(run_id=f.run_id, run_name='uncertain', reserved_wall_seconds=4)
    source['reservations'][_record_key(f.run_id, 'uncertain')] = pending
    source['reserved_wall_seconds'] += 4
    path.write_bytes(canonical_json(source))
    policy = service.adapter.policy.model_copy(update={'max_runs':2})
    monkeypatch.setattr(type(service.adapter), 'policy', property(lambda _:policy))
    monkeypatch.setattr(service.adapter, 'lookup_submission', lambda _:None)
    first = debug(f, 'first')
    assert first['budget']['created_runs'] == 2
    assert first['budget']['actual_wall_seconds'] == 1
    assert first['budget']['reserved_wall_seconds'] == 4
    with pytest.raises(DiagnosticError, match='attempts=2/2'):
        debug(f, 'third')
    status = f.worker.call_tool('worker_experiment_debug', {'action':'status', 'name':'uncertain'})
    assert status['state'] == 'submission_unknown' and status['allowance_reserved']
    before = path.read_bytes()
    assert submit(f, [f.alias], outcome='blocked')['state'] == 'rejected'
    with pytest.raises(DiagnosticError, match='could not be confirmed'):
        f.worker.call_tool('worker_experiment_debug', {'action':'cancel', 'name':'uncertain'})
    assert path.read_bytes() == before
    assert service.adapter.submits == 2


def test_independent_task_same_implementation_keeps_exact_old_result_isolated(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    path = next((service.exchange_root / 'budgets').glob('*.json'))
    old = json.loads(path.read_bytes())
    result = debug(f, 'diagnostic')  # The independent observe task already used this name.
    assert result['budget']['created_runs'] == 1
    current = json.loads(path.read_bytes())
    old_key = _record_key(f.old_id, 'diagnostic')
    assert current['runs'][old_key] == old['runs'][old_key]
    assert current['reservations'][old_key] == old['reservations'][old_key]
    assert current['runs'][_record_key(f.run_id, 'diagnostic')]['run_id'] == f.run_id
    assert debug(f, 'diagnostic')['budget']['created_runs'] == 1
    assert debug(f, 'fresh')['budget']['created_runs'] == 2
    assert service.adapter.submits == 3


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('mode', ['preflight', 'initialization'])
def test_report_receipt_recovery_preserves_original_and_selected_proof(tmp_path, monkeypatch, legacy, mode):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    collect = service.adapter.collect_with_budget
    summaries = iter(['first retained', 'second retained'])
    monkeypatch.setattr(service.adapter, 'collect_with_budget', lambda *a, **k:
        replace(collect(*a, **k), summary=next(summaries)))
    def diagnostic(name):
        return f.worker.call_tool('worker_experiment_debug', {'implementation':f.alias, 'name':name, 'mode':mode})
    diagnostic('first')
    receipt_path = service.exchange_root / 'budgets/receipts' / canonical_sha256({'run_id':f.run_id, 'run_name':'first'}) / 'receipt.json'
    if legacy:
        receipt = json.loads(receipt_path.read_bytes())
        report = next(item for item in receipt['proof']['files'] if item['relative_path'] == f'reports/{mode}-first.json')
        report['relative_path'] = f'reports/{mode}.json'
        receipt_path.chmod(0o600)
        receipt_path.write_bytes(canonical_json(receipt))
    original = receipt_path.read_bytes()
    diagnostic('second')
    recover_changed_objective(f)
    before = service.adapter.submits
    assert diagnostic('first')['summary'] == 'first retained'
    assert service.adapter.submits == before
    assert receipt_path.read_bytes() == original
    state = f.worker._tool_state['worker_experiment_debug']
    proof = json.loads(state['finalization_records'][mode])
    assert f'reports/{mode}-first.json' in {item['relative_path'] for item in proof['files']}
    assert f'reports/{mode}.json' not in {item['relative_path'] for item in proof['files']}
    assert proof['original_receipt_sha256'] == canonical_sha256(json.loads(original))
    assert proof['recovered_from_run_id'] != f.run_id
    private = service.exchange_root / 'experiment-workspaces' / proof['recovered_from_run_id'] / 'deck/reports'
    archive = private / f'{mode}-first.json'
    archive.chmod(0o600)
    archive.write_bytes(b'conflicting immutable archive')
    with pytest.raises(DiagnosticError) as caught:
        diagnostic('first')
    assert 'current diagnostic conflicts with the retained original' in str(caught.value.__cause__)


def test_ambiguous_authorized_ancestors_fail_without_mutation_after_goal_changes(tmp_path, monkeypatch):
    from copy import deepcopy
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    debug(f, 'first')
    original_path = next((service.exchange_root / 'budgets').glob('*.json'))
    source = json.loads(original_path.read_bytes())
    first_run = f.run_id
    recover_changed_objective(f)
    pending = deepcopy(source['reservations'][_record_key(first_run, 'first')])
    pending['record']['run_id'] = f.run_id
    source['reservations'][_record_key(f.run_id, 'first')] = pending
    source['reserved_wall_seconds'] += 1
    original_path.write_bytes(canonical_json(source))
    recover_changed_objective(f, name='second-recovery', max_attempts=3)
    before = original_path.read_bytes()
    for action in ('run', 'status', 'cancel'):
        request = {'action':action, 'name':'first'}
        if action == 'run':
            request['implementation'] = f.alias
        with pytest.raises(DiagnosticError) as caught:
            f.worker.call_tool('worker_experiment_debug', request)
        assert caught.value.details[0]['code'] == 'tcad_debug_recovery_ambiguous'
        assert original_path.read_bytes() == before
    assert service.adapter.submits == 2


def test_shared_scope_settles_foreign_usage_without_changing_owner(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    path = next((service.exchange_root / 'budgets').glob('*.json'))
    ledger = json.loads(path.read_bytes())
    ledger['reserved_wall_seconds'] = 4
    old_key = _record_key(f.old_id, 'diagnostic')
    fresh_key = _record_key(f.run_id, 'fresh')
    ledger['runs'][old_key]['reserved_wall_seconds'] = 4
    ledger['reservations'][old_key]['record']['reserved_wall_seconds'] = 4
    ledger['runs'][old_key].pop('actual_wall_seconds', None)
    path.write_bytes(canonical_json(ledger))
    policy = service.adapter.policy.model_copy(update={'budget_scope':'scientific_subject', 'total_wall_seconds':5})
    monkeypatch.setattr(type(service.adapter), 'policy', property(lambda _:policy))
    monkeypatch.setattr(service.adapter, 'status_details', lambda _: {'state':'succeeded',
        'consumed_budget':{'wall_time_seconds':1}}, raising=False)
    fresh = debug(f, 'fresh')
    assert fresh['budget']['created_runs'] == 2
    assert fresh['budget']['actual_wall_seconds'] == 1
    assert fresh['budget']['reserved_wall_seconds'] == 1
    saved = json.loads(path.read_bytes())
    assert saved['runs'][old_key]['run_id'] == f.old_id
    assert saved['runs'][old_key]['actual_wall_seconds'] == 1
    assert saved['runs'][fresh_key]['run_id'] == f.run_id
    # Switching scope preserves both original records and counts only the owner.
    policy = policy.model_copy(update={'budget_scope':'task'})
    assert debug(f, 'fresh')['budget']['created_runs'] == 1
    assert json.loads(path.read_bytes())['runs'][old_key]['run_id'] == f.old_id


def test_legacy_run_only_shared_ledger_keeps_its_charge(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    path = next((service.exchange_root / 'budgets').glob('*.json'))
    ledger = json.loads(path.read_bytes())
    ledger['reservations'].clear()
    path.write_bytes(canonical_json(ledger))
    policy = service.adapter.policy.model_copy(update={'budget_scope':'scientific_subject', 'max_runs':1})
    monkeypatch.setattr(type(service.adapter), 'policy', property(lambda _:policy))
    with pytest.raises(DiagnosticError, match='attempts=1/1'):
        debug(f, 'fresh')
    saved = json.loads(path.read_bytes())
    assert saved['runs'] == ledger['runs']
    assert saved['reserved_wall_seconds'] == ledger['reserved_wall_seconds']
    assert not saved['reservations']


def test_recovered_new_diagnostic_keeps_instance_charges_when_scope_changes(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    debug(f, 'first')
    original_path = next((service.exchange_root / 'budgets').glob('*.json'))
    first_key = _record_key(f.run_id, 'first')
    original = json.loads(original_path.read_bytes())['runs'][first_key]
    recover_changed_objective(f)
    second = debug(f, 'second')
    assert second['budget']['created_runs'] == 2
    current_path = service.exchange_root / 'budgets' / (canonical_sha256({'subject':f.coordinator.budget_subject(f.runs.status(f.run_id))}) + '.json')
    assert current_path == original_path
    assert json.loads(current_path.read_bytes())['runs'][_record_key(f.run_id, 'second')]['run_id'] == f.run_id
    assert json.loads(original_path.read_bytes())['runs'][first_key] == original
    policy = service.adapter.policy.model_copy(update={'budget_scope':'scientific_subject', 'max_runs':3})
    monkeypatch.setattr(type(service.adapter), 'policy', property(lambda _:policy))
    assert debug(f, 'second')['budget']['created_runs'] == 3
    with pytest.raises(DiagnosticError, match='attempts=3/3'):
        debug(f, 'third')
    policy = policy.model_copy(update={'budget_scope':'task', 'max_runs':2})
    with pytest.raises(DiagnosticError, match='attempts=2/2'):
        debug(f, 'third')
    assert service.adapter.submits == 3


@pytest.mark.parametrize('owned_duplicates', [False, True])
def test_unrelated_repeated_name_does_not_block_an_exact_request(tmp_path, monkeypatch, owned_duplicates):
    from copy import deepcopy
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    debug(f, 'unique')
    original_path = next((service.exchange_root / 'budgets').glob('*.json'))
    original = json.loads(original_path.read_bytes())
    ancestor = f.run_id
    recover_changed_objective(f)
    first = deepcopy(original['runs'][_record_key(ancestor, 'unique')])
    second = deepcopy(first)
    first['run_name'] = second['run_name'] = 'repeated'
    if owned_duplicates:
        second['run_id'] = f.run_id
    else:
        first['run_id'] = f.old_id
        second['run_id'] = 'unrelated-independent-task'
    original['runs'][_record_key(first['run_id'], 'repeated')] = first
    original['runs'][_record_key(second['run_id'], 'repeated')] = second
    original['reserved_wall_seconds'] += first['reserved_wall_seconds'] + second['reserved_wall_seconds']
    original_path.write_bytes(canonical_json(original))
    assert f.worker.call_tool('worker_experiment_debug', {'action':'status', 'name':'unique'})['state'] == 'collected'
    fresh = debug(f, 'fresh')
    assert fresh['budget']['created_runs'] == (4 if owned_duplicates else 2)
    # The current owner wins; unrelated same-name records grant no access.
    repeated = f.worker.call_tool('worker_experiment_debug', {'action':'status', 'name':'repeated'})
    assert repeated['state'] == ('collected' if owned_duplicates else 'not_created')


def test_forked_recovery_keeps_the_common_tasks_consumed_allowance(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    original_id, invocation = f.run_id, f.invocation
    policy = service.adapter.policy.model_copy(update={'max_runs':2})
    monkeypatch.setattr(type(service.adapter), 'policy', property(lambda _:policy))
    debug(f, 'first')
    recover_changed_objective(f)
    debug(f, 'second')
    branch_id = f.run_id
    branch = f.runs.status(branch_id)
    f.runs.record_failure(branch_id, reason='fixture branch interruption', expected_state='running',
        expected_last_activity_at=branch.last_activity_at)
    reply = f.root.call_tool('operation_invoke', {**invocation, 'name':'forked', 'draft_from':'continuation', 'max_attempts':3})
    assert reply['result']['state'] == 'queued', reply
    current = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace='run', name='forked')
    assert f.runs.recovery_authorized(current, original_id)
    assert not f.runs.recovery_authorized(current, branch_id)
    f.runs.worker_connections.attach(run_id=current, platform_session='fork-fixture', thread_id='forked')
    compiled = f.catalog.operation('science.experiment.v1')
    services = bind_experiment_services(f.runs, compiled, dict(f.coordinator.worker_services), coordinator=f.coordinator)
    f.worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    f.worker.call_tool('worker_open_assignment', {})
    with pytest.raises(DiagnosticError, match='attempts=2/2'):
        debug(f, 'third')
    assert service.adapter.submits == 3


def test_nonexperiment_receipt_restore_keeps_public_reports_for_finalization(tmp_path, monkeypatch):
    from copy import deepcopy
    import hashlib
    from types import SimpleNamespace
    from tcad_artifact.project_packager import ProjectPreflightAttestation, ProjectInitializationAttestation
    f = continuation(tmp_path, monkeypatch)
    service = debug_service(f)
    debug(f, 'first')
    debug(f, 'later')
    f.worker.call_tool('worker_experiment_debug', {'implementation':f.alias, 'name':'initialize', 'mode':'initialization'})
    state = deepcopy(f.worker._tool_state['worker_experiment_debug'])
    project = json.loads(state['experiment_project'])
    for key in tuple(state):
        if key.startswith('experiment_'):
            del state[key]
    private = service.exchange_root / 'experiment-workspaces' / f.run_id
    output = private / 'output'
    output.mkdir(exist_ok=True)
    subject = next(i.artifact_ref for i in f.runs.status(f.run_id).inputs if i.port_name == 'objective_source')
    snapshots = []
    def candidate():
        # The legacy artifact form reads these public mode reports while the
        # trusted proof retains immutable attempt identities.
        finalized = dict(project)
        for mode, model in [('preflight', ProjectPreflightAttestation), ('initialization', ProjectInitializationAttestation)]:
            report = model.model_validate_json((private / f'deck/reports/{mode}.json').read_bytes(), strict=True)
            finalized[mode + '_attestation'] = report.model_dump(mode='json')
            proof = json.loads(state['finalization_records'][mode])
            for item in proof['files']:
                raw = (private / 'deck' / item['relative_path']).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == item['sha256']
        (output / 'result.json').write_bytes(canonical_json({'schema_version':1, 'payload':finalized}))
        snapshots.append(finalized)
    context = SimpleNamespace(state=state, workspace=private, output_directory=output,
        run_id=f.run_id, operation_id='science.experiment.v1', remaining_seconds=100,
        input_ref=lambda _:subject, recovery_authorized=lambda source:source == f.run_id,
        recovery_scope=lambda:(f.run_id, (f.run_id,), (('objective_source',subject),)),
        candidate_snapshot=candidate)
    restored = service.run(context, run_name='first', mode='preflight',
        budget_subject=f.coordinator.budget_subject(f.runs.status(f.run_id)))
    assert restored['state'] == 'succeeded'
    assert snapshots and snapshots[-1]['preflight_attestation']['qualified']
    assert snapshots[-1]['initialization_attestation']['qualified']
