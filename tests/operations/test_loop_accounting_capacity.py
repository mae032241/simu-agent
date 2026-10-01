"""Bounded accounting through control transactions and real admission APIs."""
import json
from copy import deepcopy
import pytest
from scidiscovery.agent_execution_settings import ProgressionSettings, progression_usage_capacity
from scidiscovery.artifact_agent.service.progression_records import PROJECTION, read_control_row, store_checkpoint
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from scidiscovery.platforms.codex_usage import observe_usage
from tests.operations.test_loop_review_budget import configure
from tests.operations.test_research_loop_budget import loop_ui, authorize, start, checkpoint, row, historical_checkpoint
from tests.operations.test_scientific_progress import request


def save(p, value):
    with p.runtime.scheduler_bindings._connect() as db:
        raw = store_checkpoint(db, p.instance, value)
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (raw, p.instance))


def records(p, identity, count):
    """Mechanical fixtures produce no scientific result or qualification."""
    admissions, usage = {}, {}
    for index in range(count):
        for kind in ('research', 'independent_review'):
            name = f'{identity}-{kind}-{index}'
            classification = dict(kind=kind)
            if kind == 'independent_review':
                classification.update(operation_digest='c'*64, subjects=[dict(port='subject', ref=json.loads(row(p)['objective_ref_json']))])
            admissions[name] = dict(state='accepted', run_id='run_' + name, output_fingerprint=name,
                logical_name=name, revision=1, task_classification=classification, loop_id=identity, usage_source='frontend_unconnected')
            for role, suffix in [('worker', 'worker'), *[('helper', str(i)) for i in range(4)]]:
                thread = name + '-' + suffix
                value = observe_usage(dict(threadId=thread, tokenUsage=dict(total=dict(inputTokens=10,
                    cachedInputTokens=4, outputTokens=1))), role=role, owner=p.instance, outcome='completed')
                usage[thread] = dict(value, loop_id=identity)
    return admissions, usage


@pytest.mark.parametrize('count', [10, 30, 100, 300])
def test_configured_capacity_complete_roles_and_real_quota_denial(loop_ui, count):
    p = loop_ui
    configure(p, max_tasks=count, max_reviews=count, max_rounds=2*count, max_tokens=10_000_000, closeout_reserve_tokens=0)
    with pytest.raises(Exception, match='explicit research loop budget authorization'):
        start(p)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    value = checkpoint(p)
    identity = value['current_loop_id']
    admissions, usage = records(p, identity, count)
    value.update(admissions=admissions, usage_records=usage)
    save(p, value)
    view = SchedulerBindingService(p.runtime.scheduler_bindings.database_path).progression_status(instance_id=p.instance)
    assert view['budget']['research_tasks'] == view['budget']['independent_reviews'] == count
    assert view['budget']['remaining_tokens'] == 10_000_000 - 2*count*5*11
    assert view['usage']['groups']['worker']['tokens']['input_tokens'] == 2*count*10
    assert view['usage']['groups']['helper']['tokens']['input_tokens'] == 2*count*4*10
    assert view['usage']['coverage'] == 'partial'
    checked = root.call_tool('operation_preflight', request('one-more'))
    assert not checked['admissible'] and checked['reason_code'] == 'background_task_budget_exhausted'
    before = checkpoint(p)
    with pytest.raises(Exception, match='background_task_budget_exhausted'):
        root.call_tool('operation_invoke', request('one-more'))
    assert checkpoint(p) == before
    assert progression_usage_capacity(before['loop_authorizations'][identity]['config']['effective']) == 12*count
    default = ProgressionSettings()
    assert (default.max_tasks, default.max_reviews, default.max_rounds) == (8, 2, 12)


def history(p, scopes=6, count=30):
    configure(p, max_tasks=count, max_reviews=count, max_rounds=2*count)
    assert authorize(p) == 303
    start(p, mode='interactive')
    value = checkpoint(p)
    current = value['current_loop_id']
    for index in range(scopes):
        identity = f'loop_retained_{index}'
        authorization = deepcopy(value['loop_authorizations'][current])
        authorization['budget_snapshot'] = dict(remaining_tokens=10000 + index)
        value['loop_authorizations'][identity] = authorization
        admissions, usage = records(p, identity, count)
        value.setdefault('admissions', {}).update(admissions)
        value.setdefault('usage_records', {}).update(usage)
    save(p, value)
    return current


def test_current_read_does_not_decode_history_and_write_retains_it(loop_ui, monkeypatch):
    import scidiscovery.artifact_agent.service.progression_records as module
    p = loop_ui
    current = history(p)
    before = historical_checkpoint(p)
    decoded, statements = [], []
    original = module.json.loads
    def measured(raw, *args, **kwargs):
        value = original(raw, *args, **kwargs)
        if isinstance(value, dict) and value.get('loop_id'):
            decoded.append(value['loop_id'])
        return value
    with p.runtime.scheduler_bindings._connect() as db:
        db.set_trace_callback(statements.append)
        monkeypatch.setattr(module.json, 'loads', measured)
        value = json.loads(read_control_row(db, p.instance)['checkpoint_json'])
        assert decoded == []
        assert value['admissions'] == value['usage_records'] == {}
        value['report'] = dict(summary='No budget mutation.', completed=False, question=None)
        raw = store_checkpoint(db, p.instance, value)
        db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?', (raw, p.instance))
        plan = db.execute("EXPLAIN QUERY PLAN SELECT record_json FROM scheduler_progression_details WHERE instance_id=? AND collection='usage_records' AND json_extract(record_json,'$.loop_id')=?", (p.instance, current)).fetchall()
    monkeypatch.setattr(module.json, 'loads', original)
    assert any('progression_detail_loop' in str(tuple(item)) for item in plan)
    reads = [item for item in statements if item.startswith('SELECT record_key,record_json') and "collection='usage_records'" in item]
    assert reads and all("json_extract(record_json,'$.loop_id') IN" in item and 'LIMIT' in item for item in reads)
    after = historical_checkpoint(p)
    assert after['admissions'] == before['admissions'] and after['usage_records'] == before['usage_records']
    assert after['loop_authorizations'] == before['loop_authorizations']
    view = p.runtime.scheduler_bindings.progression_status(instance_id=p.instance)
    assert view['accounting_details']['historical_records_omitted']['admissions'] == 360
    assert view['accounting_details']['historical_records_omitted']['usage_records'] == 1800


def test_missing_metadata_cannot_delete_ledger(loop_ui):
    p = loop_ui
    current = history(p, scopes=2, count=10)
    value = checkpoint(p)
    value['admissions'], value['usage_records'] = records(p, current, 1)
    save(p, value)
    before = historical_checkpoint(p)
    with p.runtime.scheduler_bindings._connect() as db:
        raw = json.loads(db.execute('SELECT checkpoint_json FROM scheduler_progression WHERE instance_id=?', (p.instance,)).fetchone()[0])
    scoped = checkpoint(p)
    missing, incomplete = deepcopy(scoped), deepcopy(scoped)
    missing.pop(PROJECTION)
    incomplete[PROJECTION]['keys'].pop('usage_records')
    missing_maps = []
    for collection in ('admissions', 'usage_records'):
        value = deepcopy(scoped)
        value.pop(collection)
        missing_maps.append(value)
    for value in (raw, missing, incomplete, *missing_maps):
        with pytest.raises(ValueError, match='Incomplete control detail projection'):
            save(p, value)
        assert historical_checkpoint(p) == before
    with pytest.raises(ValueError, match='scoped.*complete history'):
        with p.runtime.scheduler_bindings._connect() as db:
            store_checkpoint(db, p.instance, scoped, replace=True)
    assert historical_checkpoint(p) == before
    cleared = deepcopy(scoped)
    cleared['usage_records'] = {}
    save(p, cleared)
    after = historical_checkpoint(p)
    assert after['admissions'] == before['admissions']
    assert after['usage_records'] == {key: item for key, item in before['usage_records'].items()
        if item.get('loop_id') != current}


def test_real_multi_subject_review_exceeds_old_record_limit(loop_ui):
    from blind_csv_plugin.plugin import PLUGIN as BLIND
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.catalog import compile_catalog
    from tests.operations.test_research_loop_budget import finish_task
    from tests.operations.test_shared_review_admission import request as review_request
    p = loop_ui
    original = next(item for item in GENERAL.operations if item.operation_id == 'science.object.review.v1')
    multi = original.model_copy(update=dict(inputs=tuple(port.model_copy(update=dict(max_items=24))
        if port.name == 'subject' else port for port in original.inputs)))
    catalog = compile_catalog((CORE_PLUGIN, BLIND, GENERAL.model_copy(update=dict(
        operations=tuple(multi if item == original else item for item in GENERAL.operations)))))
    p.runtime.runs.operation_catalog = p.root.facade._operation_catalog = catalog
    configure(p, max_tasks=24, max_reviews=1)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    names = [f'subject-{index}' for index in range(24)]
    for name in names:
        finish_task(p, root, name)
    req = review_request('multi-subject-audit', names[0] + '.output')
    req['inputs'][0]['artifact_names'] = [name + '.output' for name in names]
    assert root.call_tool('operation_preflight', req)['admissible']
    root.call_tool('operation_invoke', req)
    admission = checkpoint(p)['admissions'][req['name']]
    assert len(admission['task_classification']['subjects']) == 24
    assert len(json.dumps(admission, sort_keys=True).encode()) > 4096
    frozen = p.runtime.runs.status(admission['run_id']).recovery_policy['task_classification']
    assert admission['task_classification'] == frozen
    view = p.runtime.scheduler_bindings.progression_status(instance_id=p.instance)
    assert view['budget']['research_tasks'] == 24 and view['budget']['independent_reviews'] == 1


def test_total_detail_bytes_failure_rolls_back_runtime_observation(loop_ui):
    from tests.operations.test_progression_records import physical
    p = loop_ui
    configure(p, max_tasks=2, max_reviews=0, max_rounds=2,
        detail_record_bytes=4096, detail_read_bytes=8192)
    assert authorize(p) == 303
    start(p, mode='interactive')
    value = checkpoint(p)
    identity = value['current_loop_id']
    item = observe_usage(dict(threadId='retained', tokenUsage=dict(total=dict(
        inputTokens=10, cachedInputTokens=4, outputTokens=1))), role='worker', owner=p.instance)
    item = dict(item, loop_id=identity, retained_note='')
    item['retained_note'] = 'x' * (4000 - len(json.dumps(item, sort_keys=True).encode()))
    assert len(json.dumps(item, sort_keys=True).encode()) == 4000
    value['usage_records'] = {'retained': item}
    save(p, value)
    before = physical(p)
    observation = dict(params=dict(threadId='new', tokenUsage=dict(total=dict(
        inputTokens=5, cachedInputTokens=0, outputTokens=1))),
        identity=dict(role='worker', loop_id=identity), root_thread='unused-root')
    with pytest.raises(ValueError, match='detail byte capacity'):
        p.runtime.scheduler_bindings.observe_progression(instance_id=p.instance,
            expected_host=None, changes=dict(runtime_status='would-change'), usage_observation=observation)
    assert physical(p) == before


def test_native_loop_queries_retain_all_reused_run_ids_and_missing_sample(loop_ui, monkeypatch):
    from tests.operations.test_research_loop_budget import finish_task, release, usage
    from tests.operations.test_local_worker_contracts import _write_result
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    p = loop_ui
    assert authorize(p) == 303
    root = start(p)
    native_run, thread = finish_task(p, root, 'native-first')
    usage(p, p.coordinator.host.identity.thread_id)
    usage(p, thread)
    release(p)
    root = start(p, mode='interactive')
    root.call_tool('operation_invoke', request('frontend-second'))
    frontend_run = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='frontend-second')
    run = p.runtime.runs.status(frontend_run)
    p.runtime.runs.worker_connections.attach(run_id=frontend_run,
        platform_session='source-test-session', thread_id=thread)
    worker = LocalWorkerMCPRouter(p.runtime.runs, operation_id=run.operation_id,
        operation_digest=run.operation_digest, run_id=frontend_run, trusted_caller=('source-test-session', thread))
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker, observe_tokens=False)
    worker.call_tool('worker_submit_result', {})
    identity = checkpoint(p)['current_loop_id']
    statements = []
    original = p.runtime.runs._connect
    def traced():
        connection = original()
        connection.set_trace_callback(statements.append)
        return connection
    with monkeypatch.context() as scoped:
        scoped.setattr(p.runtime.runs, '_connect', traced)
        identities = p.runtime.runs.native_loop_identities(instance_id=p.instance, loop_id=identity, capacity=62)
        assert p.runtime.runs.native_usage_identity(instance_id=p.instance, thread_id=thread) == dict(role='worker', loop_id=identity)
    assert set(identities[thread]['run_ids']) == {native_run, frontend_run}
    queries = [query for query in statements if query.startswith('SELECT')]
    with original() as db:
        plans = [' '.join(str(tuple(item)) for item in db.execute('EXPLAIN QUERY PLAN ' + query)) for query in queries]
    assert 'run_loop_scope' in plans[0]
    assert 'worker_usage_thread' in plans[1] and 'helper_usage_thread' in plans[1]
    # Reconciliation must detect a missing original sample even when the last
    # accepted reuse came from an unconnected frontend. Preserve all bindings.
    value = checkpoint(p)
    value['usage_records'].pop(thread)
    save(p, value)
    p.root.call_tool('progression_command', dict(command='pause'))
    before = row(p)
    assert authorize(p) == 409  # A later unconnected Run cannot hide this native Run's missing sample.
    assert row(p) == before


def test_capacity_failure_and_missing_identity_preserve_accounting(loop_ui):
    p = loop_ui
    configure(p, max_tasks=300, max_reviews=300, max_rounds=600, detail_capacity=64)
    before = row(p)
    assert authorize(p) == 409 and row(p) == before
    configure(p, max_tasks=1, max_reviews=0, max_rounds=1)
    assert authorize(p) == 303
    start(p, mode='interactive')
    value = checkpoint(p)
    identity = value['current_loop_id']
    admissions, usage = records(p, identity, 1)
    value.update(admissions={key:item for key,item in admissions.items() if item['task_classification']['kind']=='research'},
        usage_records={key:item for key,item in usage.items() if '-research-' in key})
    save(p, value)
    limit = progression_usage_capacity(value['loop_authorizations'][identity]['config']['effective'])
    value = checkpoint(p)
    value['usage_records']['unknown'] = dict(next(iter(usage.values())), thread_id='unknown', role='unattributed')
    save(p, value)
    before = historical_checkpoint(p)
    value = checkpoint(p)
    value['usage_records']['one-more-unknown'] = dict(next(iter(usage.values())), thread_id='one-more-unknown', role='unattributed')
    assert len(value['usage_records']) == limit + 1
    with pytest.raises(ValueError, match='capacity'):
        save(p, value)
    assert historical_checkpoint(p) == before
    with p.runtime.scheduler_bindings._connect() as db:
        key = db.execute("SELECT record_key FROM scheduler_progression_details WHERE instance_id=? AND collection='usage_records' LIMIT 1", (p.instance,)).fetchone()[0]
        db.execute("DELETE FROM scheduler_progression_details WHERE instance_id=? AND collection='usage_records' AND record_key=?", (p.instance, key))
    with pytest.raises(ValueError, match='detail records differ'):
        row(p)
