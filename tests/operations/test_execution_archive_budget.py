"""Policy records and shared scientific budget accounting survive instance archive."""
import hashlib
import json
import sqlite3

import pytest

from scidiscovery.artifact_agent.schema.approval import CompiledApprovalIdentity
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.instance_archive_records import TABLES, readonly
from tests.operations.test_instance_archive import archive_system, artifact, save_archive, restore_archive
from tests.operations.tcad_policy_fixtures import policy_fields
from tcad_artifact.execution_policy import ExecutionPolicySnapshot


def _policy_executions(system, *, estimated=False):
    runtime, _, first, second = system
    source = artifact(runtime, first, 'shared.subject')
    runtime.scheduler_bindings.bind(instance=second, namespace='artifact', name='same.subject', object_id=source.artifact_id)
    identity = CompiledApprovalIdentity(operation_id='fixture.effect', operation_version='1',
        operation_digest='a'*64, approval_contract_digest='b'*64)
    budget_key = runtime.executions.scientific_budget_owner_from_refs((source.ref,), (source.schema_id,))
    fields = policy_fields()
    fields["agent_execution_policy"]["max_total_wall_time_seconds"] = 3600
    policy = ExecutionPolicySnapshot.model_validate_json(json.dumps(fields), strict=True)
    admission = policy.admission(budget={'max_storage_bytes':1000,'wall_time_seconds':1000}, budget_key=budget_key)
    ids = []
    for index, instance in enumerate((first, second)):
        execution = runtime.executions.create(executor='fixture', preparation_profile='fixture',
            payload_ref=source.ref, compiled_identity=identity)
        runtime.scheduler_bindings.bind(instance=instance, namespace='execution', name='execution', object_id=execution)
        runtime.executions.authorize_policy(execution_id=execution, admission=admission, compiled_identity=identity)
        with sqlite3.connect(runtime.executions.database_path) as db:
            db.execute("UPDATE executions SET state='collected' WHERE execution_id=?", (execution,))
            db.execute('INSERT INTO execution_prepared_submissions VALUES (?,?)', (execution, canonical_json({'fixture':index})))
        runtime.executions.settle_budget(execution,
            {'wall_time_seconds':800} if estimated else {'max_storage_bytes':100,'wall_time_seconds':800},
            finalize_missing=estimated)
        runtime.executions.record_observation_result(execution, succeeded=False)
        ids.append(execution)
    return ids, admission


def test_estimated_settlement_survives_archive_and_later_actual_observation(archive_system):
    runtime, service, first, _ = archive_system
    (owned, _), _ = _policy_executions(archive_system, estimated=True)
    before = runtime.executions.budget_accounting(owned)
    assert before['estimated'] == {'max_storage_bytes': 1000}
    save_archive(service, first)
    assert service.archived_model(first).executions.authorization(owned)['accounting'] == before
    restore_archive(service, first)
    assert runtime.executions.budget_accounting(owned) == before
    runtime.executions.settle_budget(owned, {'max_storage_bytes': 100})
    after = runtime.executions.budget_accounting(owned)
    assert after['actual'] == {'max_storage_bytes': 100, 'wall_time_seconds': 800}
    assert 'estimated' not in after


def _rows(path):
    with readonly(path) as db:
        return {table: [dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
            for table in TABLES['executions']}


@pytest.mark.parametrize('interrupt', [False, True])
def test_policy_archive_restores_exact_records_without_refunding_shared_budget(archive_system, interrupt):
    runtime, service, first, second = archive_system
    (owned, foreign), admission = _policy_executions(archive_system)
    before = _rows(runtime.executions.database_path)
    probe = admission.model_copy(update={'budget': {'max_storage_bytes':1000, 'wall_time_seconds':2500}})
    remaining = runtime.executions.budget_admission(executor='fixture', admission=probe)
    assert remaining.reason == 'cumulative_budget_exceeded'
    if interrupt:
        def fault(point):
            if point == 'after_database_commit':
                raise OSError('interrupted policy archive')
        service._fault = fault
        with pytest.raises(OSError, match='policy archive'):
            save_archive(service, first)
        service._fault = lambda _: None
        assert service.resume(first)['storage_state'] == 'archived'
    else:
        save_archive(service, first)
    package = service.root / first
    stored = _rows(package / 'records/executions.sqlite3')
    active = _rows(runtime.executions.database_path)
    for table in TABLES['executions']:
        if table == 'execution_budget_pools':
            assert stored[table] == active[table] == before[table]
        else:
            assert stored[table] == [row for row in before[table] if row['execution_id'] == owned]
            expected = before[table] if table in {'execution_budget_reservations', 'execution_budget_estimates'} else [row for row in before[table] if row['execution_id'] == foreign]
            assert active[table] == expected
    assert runtime.executions.budget_admission(executor='fixture', admission=probe).reason == 'cumulative_budget_exceeded'
    assert service.archived_model(first).executions.status(owned).authorization['source'] == 'policy'
    restore_archive(service, first)
    for table, rows in _rows(runtime.executions.database_path).items():
        assert sorted(rows, key=repr) == sorted(before[table], key=repr)
    assert runtime.scheduler_bindings.get_instance(instance_id=second).state == 'active'


def test_restore_rejects_modified_retained_budget_without_overwriting(archive_system):
    runtime, service, first, _ = archive_system
    (owned, _), _ = _policy_executions(archive_system)
    save_archive(service, first)
    with sqlite3.connect(runtime.executions.database_path) as db:
        db.execute('UPDATE execution_budget_reservations SET consumed_json=? WHERE execution_id=?',
            (canonical_json({'max_storage_bytes':999, 'wall_time_seconds':999}), owned))
    before = _rows(runtime.executions.database_path)
    preview = service.restore_preview(first)
    assert not preview['ready']
    assert 'restore_record_identity_conflict' in str(preview)
    assert _rows(runtime.executions.database_path) == before


@pytest.mark.parametrize('human_decision', [False, True])
def test_old_execution_archive_reads_and_restores_without_inventing_authorization(
        archive_system, monkeypatch, human_decision):
    from scidiscovery.artifact_agent.schema.approval import ApprovalOption, LocalIdentityRef
    runtime, service, first, _ = archive_system
    source = artifact(runtime, first, 'old.subject')
    identity = CompiledApprovalIdentity(operation_id='fixture.effect', operation_version='1',
        operation_digest='a'*64, approval_contract_digest='b'*64)
    execution = runtime.executions.create(executor='fixture', preparation_profile='old',
        payload_ref=source.ref, compiled_identity=identity)
    runtime.scheduler_bindings.bind(instance=first, namespace='execution', name='old.execution', object_id=execution)
    expected = {'source': 'none'}
    if human_decision:
        launch = runtime.approvals.create_request(approval_id='apr_historical', kind='execution_authorization',
            subject_refs=runtime.executions.approval_subject_refs(execution), question='Authorize exact fixture?',
            options=(
                ApprovalOption(option_id='authorize_execution', label='Authorize',
                    description='Authorize this exact execution.', requires_rationale=False),
                ApprovalOption(option_id='cancel', label='Cancel',
                    description='Cancel this request.', requires_rationale=False,
                    terminal_state='cancelled_by_human'),
            ), requested_by=runtime.actor,
            idempotency_key='old.execution.approval', compiled_identity=identity)
        runtime.scheduler_bindings.bind(instance=first, namespace='approval', name='old.approval', object_id='apr_historical')
        review = runtime.approvals.review('apr_historical', access_token=launch.access_token)
        runtime.approvals.record_ui_decision(approval_id='apr_historical', access_token=launch.access_token,
            csrf_token=review.csrf_token, decision_nonce=review.decision_nonce, selected_option='authorize_execution',
            rationale='Exact synthetic fixture.', decided_by=LocalIdentityRef(identity_id='fixture', display_name='Fixture'),
            ui_session_id='fixture_ui')
        runtime.executions.authorize(execution_id=execution, approval_id='apr_historical', compiled_identity=identity)
        decision = runtime.approvals.status('apr_historical').decision_ref
        expected = {'source': 'human', 'decision_ref': decision.model_dump(mode='json')}
    with sqlite3.connect(runtime.executions.database_path) as db:
        db.execute("UPDATE executions SET state='cancelled' WHERE execution_id=?", (execution,))
        for table in TABLES['executions'][1:]:
            db.execute('DROP TABLE '+table)
    # Produce the old archive with the old runtime's absence of policy lookup.
    # Current archived_model below gets the real implementation after this scope.
    with monkeypatch.context() as old_runtime:
        old_runtime.setattr(runtime.executions, '_current_policy_record', lambda *_: None)
        save_archive(service, first)
    archive_db = service.root / first / 'records/executions.sqlite3'
    original = archive_db.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    model = service.archived_model(first)
    status = model.executions.status(execution)
    assert status.state == 'cancelled' and status.authorization == expected
    if human_decision:
        summary = model.approvals.navigation_summary("apr_historical")
        assert summary["question"] == "Authorize exact fixture?"
        with pytest.raises(AttributeError):
            model.approvals.expire_pending("apr_historical")
    listing = model.nodes(first)
    node = next(item for item in listing['items'] if item['key'] == 'execution:old.execution')
    assert node['state'] == 'cancelled' and not node.get('gaps')
    detail = model.node(first, 'execution:old.execution')
    assert detail['record']['payload']['authorization'] == expected
    assert detail['qualification']['state'] == 'not_evaluated'
    assert not any(gap['code'] == 'source_read_error' for gap in detail['gaps'])
    with readonly(archive_db) as db:
        assert {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {'executions'}
    assert hashlib.sha256(archive_db.read_bytes()).hexdigest() == digest
    runtime.executions._initialize()
    restore_archive(service, first)
    assert hashlib.sha256(archive_db.read_bytes()).hexdigest() == digest
    rows = _rows(runtime.executions.database_path)
    assert rows['executions'][0]['execution_id'] == execution
    assert all(not rows[table] for table in TABLES['executions'][1:])
    assert runtime.executions.status(execution).authorization == expected


@pytest.mark.parametrize('defect', ['missing_current', 'missing_history', 'missing_column'])
def test_archive_policy_lookup_does_not_hide_partial_schema_damage(defect):
    from scidiscovery.artifact_agent.service.executions import EXECUTION_POLICY_SCHEMA
    from scidiscovery.artifact_agent.service.instance_archive_reader import _historical_policy_record
    with sqlite3.connect(':memory:') as db:
        db.row_factory = sqlite3.Row
        db.executescript(EXECUTION_POLICY_SCHEMA)
        if defect == 'missing_column':
            db.execute('ALTER TABLE execution_policy_authorizations DROP COLUMN record_json')
        else:
            db.execute('DROP TABLE ' + ('execution_current_policy' if defect == 'missing_current'
                                       else 'execution_policy_authorizations'))
        db.execute('PRAGMA query_only=ON')
        with pytest.raises(sqlite3.OperationalError):
            _historical_policy_record(db, 'historical')
