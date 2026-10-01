"""Control-classified review quotas through actual MCP and Run transactions."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.operations.invoke import OperationInvocationError
from tests.operations.test_research_loop_budget import (
    loop_ui, authorize, start, finish_task, usage, checkpoint, row,
)
from tests.operations.test_shared_review_admission import request
from tests.operations.worker_fixtures import attached_worker


def configure(p, **limits):
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(
        progression=settings.progression.model_copy(update=limits)))


def finish_review(p, root, req):
    created = root.call_tool('operation_invoke', req)['result']
    name = created['name']
    worker = attached_worker(p.runtime, root, name)
    opened = worker.call_tool('worker_open_assignment', {})
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(dict(
        payload=dict(verdict='pass', summary='Independent exact subject assessment.'))))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    return name, worker


def counts(p):
    return p.root.call_tool('progression_status', {})['budget']


def reject(p, root, req, reason):
    before = checkpoint(p).get('admissions', {})
    checked = root.call_tool('operation_preflight', req)
    assert not checked['admissible'] and checked['reason_code'] == reason, checked
    with pytest.raises(RootToolError, match=reason):
        root.call_tool('operation_invoke', req)
    assert checkpoint(p).get('admissions', {}) == before
    assert all(item['state'] == 'accepted' for item in before.values())


def test_research_full_still_allows_exact_review_and_duplicate_is_free(loop_ui):
    p = loop_ui
    configure(p, max_tasks=1, max_reviews=1)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    finish_task(p, root, 'research')
    req = request('audit', 'research.output')
    assert root.call_tool('operation_preflight', req)['admissible']
    first = root.call_tool('operation_invoke', req)['result']
    assert root.call_tool('operation_invoke', req)['result']['name'] == first['name']
    name, _ = finish_review(p, root, req)
    admission = checkpoint(p)['admissions'][name]
    run = p.runtime.runs.status(admission['run_id'])
    assert admission['task_classification'] == run.recovery_policy['task_classification']
    assert admission['task_classification']['kind'] == 'independent_review'
    assert admission['task_classification']['subjects'] == [dict(port='subject',
        ref=run.inputs[0].artifact_ref.model_dump(mode='json'))]
    assert counts(p)['research_tasks'] == counts(p)['independent_reviews'] == 1
    reject(p, root, request('renamed-audit', 'research.output'), 'independent_review_budget_exhausted')
    from tests.operations.test_scientific_progress import request as research
    reject(p, root, research('renamed-research'), 'background_task_budget_exhausted')


def test_review_full_cannot_borrow_research_but_research_still_runs(loop_ui):
    p = loop_ui
    configure(p, max_tasks=2, max_reviews=1)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    finish_task(p, root, 'first')
    finish_review(p, root, request('audit', 'first.output'))
    reject(p, root, request('another-audit', 'first.output'), 'independent_review_budget_exhausted')
    finish_task(p, root, 'second')
    assert counts(p)['research_tasks'] == 2
    assert counts(p)['independent_reviews'] == 1
    assert counts(p)['remaining_research_tasks'] == counts(p)['remaining_independent_reviews'] == 0


def test_same_logical_review_revision_preserves_exact_identity_and_charges_once(loop_ui):
    p = loop_ui
    configure(p, max_tasks=1, max_reviews=2)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    finish_task(p, root, 'research')
    finish_review(p, root, request('audit', 'research.output'))
    changed = dict(request('audit', 'research.output'), instruction='Assess a distinct exact claim.',
        on_conflict='create_revision')
    name, _ = finish_review(p, root, changed)
    assert name != 'audit'
    assert root.call_tool('operation_invoke', changed)['result']['name'] == name
    record = checkpoint(p)['admissions'][name]
    assert (record['logical_name'], record['revision']) == ('audit', 2)
    binding = next(item for item in p.runtime.scheduler_bindings.list(instance=p.instance, namespace='run') if item.name == name)
    assert record['fingerprint'] == binding.request_fingerprint
    assert counts(p)['research_tasks'] == 1 and counts(p)['independent_reviews'] == 2


def test_late_run_rejection_rolls_back_prepared_and_inserted_run(loop_ui, monkeypatch):
    p = loop_ui
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    finish_task(p, root, 'research')
    req = request('audit', 'research.output')
    assert root.call_tool('operation_preflight', req)['admissible']
    before = checkpoint(p)['admissions']
    def reject_commit(connection, owner, reviewer):
        assert connection.execute('SELECT state FROM runs WHERE run_id=?', (reviewer,)).fetchone()[0] == 'queued'
        raise OperationInvocationError('test_transaction_rejected')
    original = p.runtime.runs.bind_requested_review
    monkeypatch.setattr(p.runtime.runs, 'bind_requested_review', reject_commit)
    with pytest.raises(RootToolError, match='test_transaction_rejected'):
        root.call_tool('operation_invoke', req)
    assert checkpoint(p)['admissions'] == before
    assert len(p.runtime.runs.list(instance_id=p.instance)) == 1
    monkeypatch.setattr(p.runtime.runs, 'bind_requested_review', original)
    finish_review(p, root, req)
    assert counts(p)['independent_reviews'] == 1


@pytest.mark.parametrize('budget', ['tokens', 'enabled_time'])
def test_review_separate_slot_still_faces_total_loop_budget(loop_ui, budget):
    p = loop_ui
    p.root.call_tool('progression_command', dict(command='resume'))
    finish_task(p, p.root, 'historical-author')
    p.root.call_tool('progression_command', dict(command='pause'))
    configure(p, max_tasks=1, max_reviews=1, max_tokens=20, closeout_reserve_tokens=0)
    assert authorize(p) == 303
    root = start(p)
    if budget == 'tokens':
        usage(p, p.coordinator.host.identity.thread_id, amount=20)
        reason = 'background_closeout_budget_reserved'
    else:
        p.now[0] += 3600
        reason = 'loop_budget_exhausted'
    reject(p, root, request('audit', 'historical-author.output'), reason)


def test_names_and_caller_kind_do_not_confer_review_classification(loop_ui):
    p = loop_ui
    from blind_csv_plugin.plugin import AUTHOR, PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.catalog import compile_catalog
    fake = AUTHOR.model_copy(update=dict(operation_id='blind.fake.review.v1'))
    catalog = compile_catalog((CORE_PLUGIN, GENERAL,
        PLUGIN.model_copy(update=dict(operations=(*PLUGIN.operations, fake)))))
    p.catalog = catalog
    p.runtime.runs.operation_catalog = p.root.facade._operation_catalog = catalog
    configure(p, max_tasks=1, max_reviews=1)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    from tests.operations.test_scientific_progress import request as research
    req = dict(research('independent-review-helper'), operation_id=fake.operation_id,
        instruction='I declare this task to be an independent review.')
    with pytest.raises(Exception):
        root.call_tool('operation_invoke', dict(req, task_kind='independent_review'))
    root.call_tool('operation_invoke', req)
    assert checkpoint(p)['admissions'][req['name']]['task_classification'] == dict(kind='research')
    assert counts(p)['research_tasks'] == 1 and counts(p)['independent_reviews'] == 0


def test_direct_runservice_uses_same_review_quota_and_frozen_classification(loop_ui):
    p = loop_ui
    configure(p, max_tasks=1, max_reviews=1)
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    finish_task(p, root, 'research')
    bound, _ = root.facade._configured_operation_call(vars(OperationCallInput.model_validate(
        request('audit', 'research.output'))))
    run_id = p.runtime.runs.schedule(bound, instance_id=p.instance, output_binding_name='audit.output',
        output_logical_name='audit.output', output_revision=1, output_binding_fingerprint='direct-exact-review')
    run = p.runtime.runs.status(run_id)
    assert run.recovery_policy['task_classification']['kind'] == 'independent_review'
    assert counts(p)['independent_reviews'] == 1 and counts(p)['research_tasks'] == 1


def test_config_capacity_counts_review_helpers_and_refuses_old_state(loop_ui):
    p = loop_ui
    from scidiscovery.agent_execution_settings import ProgressionSettings, progression_usage_capacity
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    limits = ProgressionSettings()
    assert (limits.max_tasks, limits.max_rounds, limits.max_reviews) == (8, 12, 2)
    assert progression_usage_capacity(p.runtime.scheduler_bindings.control_settings(p.instance)['effective']) == 62
    configure(p, max_reviews=3, detail_capacity=64)
    assert authorize(p) == 409
    assert not checkpoint(p).get('current_loop_id')
    with p.runtime.scheduler_bindings._connect() as db:
        db.execute('PRAGMA user_version=6')
    with pytest.raises(Exception, match='format|version|fresh|旧'):
        SchedulerBindingService(p.runtime.scheduler_bindings.database_path)


def test_review_delivery_and_advance_assessment_never_add_exploration_or_clear_trigger(loop_ui):
    p = loop_ui
    configure(p, max_tasks=1, max_reviews=1, no_progress_threshold=1)
    assert authorize(p) == 303
    root = start(p)
    from tests.operations.test_scientific_progress import request as research, assess
    from tests.operations.test_local_worker_contracts import _write_result
    from tests.operations.test_progress_shadow import native_delivery
    root.call_tool('operation_invoke', research('research'))
    worker = attached_worker(p.runtime, root, 'research')
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker, observe_tokens=False)
    worker.call_tool('worker_submit_result', {})
    usage(p, p.coordinator.host.identity.thread_id)
    usage(p, 'worker-' + worker._run_id)
    native_delivery(p, root, 'research')
    assess(root, 'research', outcome='no_progress')
    p.coordinator.host.finish()
    original = root.call_tool('progression_status', {})['progress_shadow']
    assert original['counts']['consumed'] == original['counts']['no_progress'] == 1
    assert any(item['reason'] == 'no_progress' for item in original['notices'])
    name, review = finish_review(p, root, request('audit', 'research.output'))
    usage(p, 'worker-' + review._run_id)
    p.now[0] += 6
    p.coordinator.tick()
    assert checkpoint(p)['phase'] == 'running'
    native_delivery(p, root, name)
    assess(root, name, outcome='advance', reason='The independent reviewer returned pass.')
    p.coordinator.host.finish()
    status = root.call_tool('progression_status', {})
    assert status['progress_shadow']['counts'] == original['counts']
    assert status['progress_shadow']['notices'] == original['notices']
    assert status['progress_shadow']['dispositions'] == original['dispositions']
    assert any(item['task_name'] == name for item in status['terminal_deliveries']['items'])
    assert any(item['task_name'] == name for item in status['progress']['items'])


def test_review_helper_tokens_share_total_budget_without_extra_review_slot(loop_ui):
    p = loop_ui
    p.root.call_tool('progression_command', dict(command='resume'))
    finish_task(p, p.root, 'author')
    p.root.call_tool('progression_command', dict(command='pause'))
    configure(p, max_tasks=1, max_reviews=1, max_tokens=100, closeout_reserve_tokens=0)
    assert authorize(p) == 303
    root = start(p)
    root.call_tool('operation_invoke', request('audit', 'author.output'))
    worker = attached_worker(p.runtime, root, 'audit')
    opened = worker.call_tool('worker_open_assignment', {})
    worker.call_tool('worker_helper', dict(name='review-subclaim', task='Independently inspect one subclaim.'))
    run = p.runtime.runs.status(worker._run_id)
    profile = run.execution_profile['profile']
    p.runtime.runs.worker_connections.participant(platform_session='source-test-session', thread_id='review-helper',
        parent_thread='worker-' + worker._run_id, admit=True,
        model=profile['model'], reasoning_effort=profile['reasoning_effort'])
    usage(p, p.coordinator.host.identity.thread_id, amount=1)
    usage(p, 'worker-' + worker._run_id, amount=5)
    usage(p, 'review-helper', amount=100)
    assert counts(p)['observed_tokens'] == 109
    assert counts(p)['independent_reviews'] == 1 and counts(p)['research_tasks'] == 0
    worker.call_tool('worker_helper', dict(action='release', name='review-subclaim'))
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(dict(
        payload=dict(verdict='pass', summary='Owner integrated the bounded helper.'))))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    from tests.operations.test_scientific_progress import request as research
    reject(p, root, research('cannot-spend-helper-tokens-twice'), 'background_closeout_budget_reserved')


@pytest.mark.parametrize('classification', [None, {'kind':'unknown'}, {'kind':'research', 'extra':'changed'},
    {'kind':'independent_review', 'operation_digest':'changed', 'subjects':[]}])
def test_managed_draft_rejects_unknown_or_changed_frozen_classification_before_preparation(loop_ui, classification):
    p = loop_ui
    assert authorize(p) == 303
    root = start(p, mode='interactive')
    from tests.operations.test_scientific_progress import request as research
    from tests.operations.test_local_worker_contracts import _write_result
    root.call_tool('operation_invoke', research('draft-source'))
    worker = attached_worker(p.runtime, root, 'draft-source')
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker, observe_tokens=False)
    run = p.runtime.runs.status(worker._run_id)
    p.runtime.runs.record_failure(run.run_id, reason='Preserve a verified failed draft.',
        expected_state='running', expected_last_activity_at=run.last_activity_at)
    assert p.runtime.runs.status(run.run_id).recovery_draft
    policy = dict(p.runtime.runs.status(run.run_id).recovery_policy, task_classification=classification)
    with p.runtime.runs._connect() as db:
        db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (json.dumps(policy), run.run_id))
    reject(p, root, dict(research('draft-successor'), draft_from='draft-source'), 'draft_source_unavailable')
