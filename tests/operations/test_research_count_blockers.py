"""E5a: existing research counters through Root, Worker, receipt and restart.

Finite local evaluations are internal Worker observations, not remote exp
submissions. Scientific judgments and native usage counters remain fixtures;
these checks make no claim about live model behavior or scientific validity.
"""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from tests.operations.test_progression import Host, checkpoint, progression, row
from tests.operations.test_progress_assist import configure
from tests.operations.test_scientific_progress import active
from tests.operations.test_progress_shadow import native_delivery
from tests.operations.test_generic_research_progress import analysis, experiment, facts, proposal
from tests.operations.research_loop_fixtures import measured_fixture_usage
from tests.operations.worker_fixtures import attached_worker


def finite_evaluations(p, root, hypothesis, count):
    """Seal one actual native execution containing count internal evaluations."""
    request = dict(name='internal-evaluations', operation_id='science.experiment.v1',
        inputs=[dict(port='subject', artifact_names=[hypothesis])],
        instruction='Evaluate this bounded contrast internally and retain its observations for analysis.')
    assert root.call_tool('operation_preflight', request)['admissible']
    assert root.call_tool('operation_invoke', request)['result']['state'] == 'queued'
    worker = attached_worker(p.runtime, root, request['name'])
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['workspace_path'])

    def publish(filename, raw, sources):
        (workspace / 'scratch' / filename).write_bytes(raw)
        return worker.call_tool('worker_publish_files', dict(files=[dict(path='scratch/' + filename,
            purpose='Retained finite internal evaluation evidence')], source_aliases=sources))['files'][0]['reference']

    program = publish('program.py', ('import json\nprint(json.dumps(['
        f'{{"evaluation": i, "observation": i + 1}} for i in range({count})]))\n').encode(), ['hypothesis_portfolio'])
    implementation = worker.call_tool('worker_experiment_stage', dict(stage='implementation',
        conclusion='Evaluate the finite contrast without creating separate framework tasks.',
        materials=[program]))['reference']
    executed = subprocess.run([sys.executable, '-B', 'program.py'], cwd=workspace / 'scratch',
        capture_output=True, check=True, timeout=5)
    observations = json.loads(executed.stdout)
    assert len(observations) == count and observations[-1]['observation'] == count
    log = publish('execution.log', executed.stdout + executed.stderr, [implementation])
    result = publish('observations.json', executed.stdout, [implementation])
    execution = worker.call_tool('worker_experiment_stage', dict(stage='execution',
        conclusion=f'One native execution retained {count} internal evaluations.',
        native_execution=dict(implementation=implementation, state='succeeded', logs=[log], results=[result])))['reference']
    validity = worker.call_tool('worker_experiment_stage', dict(stage='validity',
        conclusion='Every finite evaluation has a retained observation; scientific interpretation remains pending.',
        materials=[execution]))['reference']
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        payload=dict(summary=f'Retained {count} internal evaluations in one Worker result.', outcome='completed',
            remaining_question='Interpret these exact observations.', limitations=['No live model or remote experiment.'],
            adopted_stages=[implementation, execution, validity]))))
    measured_fixture_usage(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    native_delivery(p, root, request['name'])
    return root.call_tool('run_status', dict(name=request['name']))['output_artifact_name']


def wake(p):
    # A newly sealed terminal result wakes an idle Root through its real poll.
    # Idle-turn tool receipts deliberately cannot prove a native read.
    p.now[0] += json.loads(row(p)['config_json'])['effective']['progression']['poll_seconds'] + 1
    p.coordinator.tick()


def settle(p):
    wake(p)
    assert checkpoint(p)['phase'] == 'running'
    p.coordinator.host.finish()
    wake(p)
    return p.root.call_tool('progression_status', {})['progress_shadow']


@pytest.mark.parametrize('internal_evaluations', [1, 25])
def test_internal_evaluations_wait_analysis_continue_and_restart_without_recount(progression, internal_evaluations):
    p = progression
    configure(p)  # Assist mode; retain the existing frozen budgets and thresholds.
    root = active(p)
    hypothesis = proposal(p, root)
    prepared = settle(p)
    assert prepared['policy']['observation_gap_threshold'] == 3
    assert prepared['policy']['unverified_progress_threshold'] == 3
    assert prepared['policy']['no_progress_threshold'] == 3
    assert prepared['policy']['refinement_threshold'] == 4
    assert prepared['counts']['consumed_research_tasks'] == 0
    assert prepared['counts']['awaiting_analysis'] == 1 and not prepared['notices']
    assert row(p)['state'] == 'active'

    subject = finite_evaluations(p, root, hypothesis, internal_evaluations)
    waiting = settle(p)
    assert waiting['counts']['consumed_research_tasks'] == 0
    assert waiting['counts']['consumed'] == 0 and waiting['counts']['unverified_progress'] == 0
    assert waiting['counts']['awaiting_analysis'] == 1 and not waiting['notices']
    assert row(p)['state'] == 'active'
    assert len(facts(p)) == 2  # Only the H and W terminal deliveries exist.
    analysis(p, root, subject, 'first-analysis')  # Real preflight, admission and Worker submission.
    first = settle(p)
    assert first['counts']['consumed_research_tasks'] == first['counts']['consumed'] == 1
    assert first['counts']['awaiting_analysis'] == first['counts']['unverified_progress'] == 0
    assert not first['notices'] and row(p)['state'] == 'active'

    # Reconnect the persisted native turn with a new coordinator and DB service.
    before = checkpoint(p)
    before_facts = facts(p)
    p.coordinator.close()
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path,
        global_settings=p.runtime.scheduler_bindings.global_settings)
    reopened.progression_clock = lambda: p.now[0]
    p.runtime = replace(p.runtime, scheduler_bindings=reopened)
    p.root.facade.bindings = reopened
    p.coordinator = ProgressionCoordinator(runtime=p.runtime, host_factory=Host,
        facade_factory=p.facade, clock=lambda: p.now[0])
    p.coordinator.tick()
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    assert checkpoint(p)['rounds'] == before['rounds']

    # A distinct exact W output wakes a real native turn after reconnection.
    next_subject = experiment(p, root, hypothesis, 'next-experiment')
    wake(p)
    assert checkpoint(p)['phase'] == 'running'
    for _ in range(3):
        root.call_tool('run_status', dict(name='first-analysis'))
        native_delivery(p, root, 'first-analysis')
        assert root.call_tool('progression_status', {})['progress_shadow']['counts'] == first['counts']
    assert facts(p) == before_facts

    # Consuming the next W leaves one pending A under the unchanged allowance.
    next_wait = settle(p)
    assert next_wait['counts']['consumed_research_tasks'] == 1
    assert next_wait['counts']['awaiting_analysis'] == 1 and not next_wait['notices']
    analysis(p, root, next_subject, 'next-analysis')
    continued = settle(p)
    assert continued['counts']['consumed_research_tasks'] == continued['counts']['consumed'] == 2
    assert continued['counts']['awaiting_analysis'] == 0
    assert continued['counts']['unverified_progress'] == 1  # Same family is not another new scientific change.
    assert not continued['notices'] and row(p)['state'] == 'active'
    assert len(facts(p)) == 5
    assert checkpoint(p)['rounds'] < 25  # Root turn allowance is a separate counter.
