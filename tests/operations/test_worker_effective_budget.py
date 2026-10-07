"""Trusted loop time reaches scientific Workers without changing Run authority."""
import json
import time
from datetime import datetime
from pathlib import Path

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_research_loop_budget import loop_ui, authorize, start, checkpoint
from tests.operations.test_loop_review_budget import configure
from tests.operations.test_tcad_result_analysis import analysis_materials
from tests.operations.worker_fixtures import attached_worker


def analysis(p, name='analysis'):
    from curve_score.plugin import PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.catalog import compile_catalog
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, PLUGIN))
    p.runtime.runs.operation_catalog = catalog
    p.root.facade._operation_catalog = catalog
    plan = analysis_materials()[0]
    for alias, raw, schema, parents in (
            ('plan', plan.canonical_json(), 'scidiscovery.experiment-portfolio.v1', ()),
            ('observations', b'Bound execution observation.', 'opaque', ())):
        artifact = p.runtime.artifacts.register(raw, ArtifactRegistration(kind='fixture',
            schema_id=schema, payload_schema_version=1, media_type='application/json',
            creator=p.runtime.actor, parent_refs=parents), idempotency_key=alias)
        p.runtime.scheduler_bindings.bind(instance=p.instance, namespace='artifact',
            name=alias, object_id=artifact.artifact_id)
    p.root.call_tool('operation_invoke', dict(name=name, operation_id='science.result.diagnose.v1',
        instruction='Independently analyze the exact bound plan and observations.', inputs=[
            dict(port='experiment_plan', artifact_names=['plan']),
            dict(port='experiment_results', artifact_names=['observations'])]))
    worker = attached_worker(p.runtime, p.root, name)
    return worker, worker.call_tool('worker_open_assignment', {})


def test_analysis_sees_earliest_authorized_deadline_and_live_remaining(loop_ui):
    p = loop_ui
    p.now[0] = time.time()
    configure(p, max_calendar_seconds=100, max_elapsed_seconds=200)
    assert authorize(p) == 303
    start(p, mode='interactive')
    worker, opened = analysis(p)
    frozen = json.loads(Path(opened['assignment_path']).read_text())
    deadline = p.root.call_tool('progression_status', {})['budget']['deadline_at']
    assert frozen['budget']['deadline_at'] == deadline
    assert datetime.fromisoformat(frozen['budget']['run_deadline_at'].replace('Z', '+00:00')) > datetime.fromisoformat(deadline)
    assert opened['budget']['deadline_at'] == deadline
    assert opened['remaining_seconds'] <= 100
    assert json.loads(Path(opened['start_here_path']).read_text())['budget'] == opened['budget']
    p.now[0] += 30
    later = worker.call_tool('worker_open_assignment', {})
    assert later['remaining_seconds'] <= 70
    assert later['budget']['loop']['enabled_remaining_seconds'] == 170
    assert json.loads(Path(opened['assignment_path']).read_text()) == frozen
    pulse = worker.call_tool('worker_heartbeat', {})
    assert pulse['remaining_seconds'] == later['remaining_seconds']
    assert pulse['budget']['deadline_at'] == deadline


def test_reopen_pause_new_authorization_cannot_refill_existing_worker(loop_ui):
    p = loop_ui
    p.now[0] = time.time()
    configure(p, max_calendar_seconds=100, max_elapsed_seconds=200)
    assert authorize(p) == 303
    start(p, mode='interactive')
    worker, opened = analysis(p)
    identity = checkpoint(p)['current_loop_id']
    deadline = opened['budget']['deadline_at']
    p.now[0] += 20
    p.root.call_tool('progression_command', dict(command='pause'))
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    reopened.progression_clock = lambda: p.now[0]
    p.runtime.runs.scheduler_bindings = reopened
    p.now[0] += 10
    assert worker.call_tool('worker_open_assignment', {})['remaining_seconds'] <= 70
    # A new UI loop cannot be granted while work is unresolved. After the Run
    # ends, historical/recovery budget reads still belong to its original loop.
    configure(p, max_calendar_seconds=300, max_elapsed_seconds=400)
    assert authorize(p) == 409
    run_id = worker._run_id
    p.runtime.runs.fail(run_id, reason='fixture concluded without a scientific result')
    assert authorize(p) == 303
    assert checkpoint(p)['current_loop_id'] != identity
    view = p.runtime.runs.worker_budget(p.runtime.runs.status(run_id))
    assert view['deadline_at'] == deadline
    assert view['loop']['id'] == identity
    assert view['remaining_seconds'] <= 70
    assert view['loop']['enabled_remaining_seconds'] == 180


def test_ordinary_worker_keeps_run_deadline_and_reports_unknown_outer(loop_ui):
    p = loop_ui
    p.now[0] = time.time()
    p.root.call_tool('progression_command', dict(command='resume'))
    worker, opened = analysis(p)
    budget = opened['budget']
    assert budget['deadline_at'] == budget['run_deadline_at']
    assert budget['loop'] is None
    assert budget['external_host_deadline'] == 'unknown'
    assert opened['remaining_seconds'] > 100
    assert worker.call_tool('worker_open_assignment', {})['budget']['deadline_at'] == budget['deadline_at']
