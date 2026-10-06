"""Generic science composes with consumption control through real source routes.

No model or solver: the native fixture executes a finite Python calculation and
seals its real program/log/output; scientific assessments are authored fixtures.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.scientific_progress import ScientificProgressProjection
from scidiscovery.operations.spec import CallableComponent, ComponentRef, ComponentSpec, ScientificProgressSpec
from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact, reduce_shadow, background_snapshot
from scidiscovery.artifact_agent.service.research_progress import research_progress, cycle_facts
from tests.operations.test_progression import progression, row
from tests.operations.test_progress_assist import configure
from tests.operations.test_scientific_progress import active
from tests.operations.test_progress_shadow import native_delivery
from tests.operations.test_historical_compatibility_paths import _complete
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.worker_fixtures import attached_worker
from tests.operations.research_loop_fixtures import measured_fixture_usage


def setup(p, **limits):
    configure(p, max_tasks=32, max_rounds=32, refinement_threshold=100, **limits)
    return active(p)


def proposal(p, root, name='hypothesis'):
    payload = _proposal(hypothesis_keys=('mechanism',))
    payload.pop('research_objective_key')
    output = _complete(p.runtime, root, name, 'science.hypothesis.propose.v1', {'subject': 'goal'}, payload, measure_usage=True)
    if p.coordinator.host is not None:
        native_delivery(p, root, name)
    return output


def experiment(p, root, hypothesis, name, *, blocked=False):
    assert root.call_tool('operation_invoke', dict(name=name, operation_id='science.experiment.v1',
        inputs=[dict(port='subject', artifact_names=[hypothesis])],
        instruction='One bounded discriminating contrast; interpret before choosing another question.'))['result']['state'] == 'queued'
    worker = attached_worker(p.runtime, root, name)
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['workspace_path'])
    stages = []
    if not blocked:
        def publish(filename, raw, sources):
            (workspace / 'scratch' / filename).write_bytes(raw)
            return worker.call_tool('worker_publish_files', dict(files=[dict(path='scratch/'+filename,
                purpose='Finite native evidence')], source_aliases=sources))['files'][0]['reference']
        # A changed comment makes bytes novel while the scientific question stays fixed.
        program = publish('program.py', f'# {name}\nprint(2+2)\n'.encode(), ['hypothesis_portfolio'])
        impl = worker.call_tool('worker_experiment_stage', dict(stage='implementation',
            conclusion='Compute the finite sum for this contrast.', materials=[program]))['reference']
        actual = subprocess.run([sys.executable, '-B', 'program.py'], cwd=workspace / 'scratch',
            capture_output=True, check=True, timeout=5)
        log = publish('execution.log', actual.stdout + actual.stderr, [impl])
        result = publish('result.txt', actual.stdout, [impl])
        execution = worker.call_tool('worker_experiment_stage', dict(stage='execution',
            conclusion='Worker records one actual finite local execution.', native_execution=dict(
                implementation=impl, state='succeeded', logs=[log], results=[result])))['reference']
        validity = worker.call_tool('worker_experiment_stage', dict(stage='validity',
            conclusion='The retained output is 4; native provenance remains Worker reported.', materials=[execution]))['reference']
        stages = [impl, execution, validity]
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        payload=dict(summary='Blocked without observations.' if blocked else 'Observed the bounded sum.',
            outcome='blocked' if blocked else 'completed', remaining_question='Supply the environment.' if blocked else '',
            limitations=['Native execution has no independent attestation.'], adopted_stages=stages))))
    measured_fixture_usage(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    native_delivery(p, root, name)
    return root.call_tool('run_status', dict(name=name))['output_artifact_name']


def analysis(p, root, subject, name, *, outcome='supports', assessment=None, missing=False, evidence_keys=None, supplement=False):
    payload = dict(summary='Bounded interpretation of exact observations.', overall_verdict='inconclusive',
        claim_allowed=False, remaining_contradiction='The global goal still has unresolved requirements.',
        limitations=['Fixture scientific judgment, not an independently validated mechanism.'])
    if not missing:
        payload['hypothesis_assessments'] = [dict(hypothesis_key='mechanism', outcome=outcome,
            evidence_keys=evidence_keys or ['experiment_results'], rationale='The retained observation changes this bounded judgment.')]
    if assessment is not None:
        payload['progress_assessment'] = dict(outcome=assessment, reason='The bounded decision did not change.',
            evidence_keys=['experiment_results'])
    if supplement:
        root.call_tool('operation_invoke', dict(name=name, operation_id='science.result.analyze.v1',
            inputs=[dict(port='subject', artifact_names=[subject])], instruction='Interpret exact observations and retain calculation sources.'))
        worker = attached_worker(p.runtime, root, name)
        opened = worker.call_tool('worker_open_assignment', {})
        workspace = Path(opened['workspace_path'])
        for index in range(3):
            path = workspace / 'scratch' / f'criterion_checks_{index}.json'
            path.write_text(json.dumps(dict(observation=4, note='Fixture native supplement, no independent attestation.')))
            published = worker.call_tool('worker_publish_files', dict(files=[dict(path='scratch/'+path.name,
                purpose='Retained analysis calculation')], source_aliases=['experiment_results']))
        assert published['files'][0]['reference'] == 'attachment_003'
        payload['source_references'] = [dict(source_key='recalculation', input_alias='attachment_003')]
        Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1, payload=payload,
            handoff=dict(verdict='inconclusive', summary='Exact analysis with sealed native supplement.'))))
        measured_fixture_usage(worker)
        assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
        output = root.call_tool('run_status', dict(name=name))['output_artifact_name']
    else:
        output = _complete(p.runtime, root, name, 'science.result.analyze.v1', {'subject': subject}, payload,
            verdict='inconclusive', measure_usage=True)
    if p.coordinator.host is not None:
        native_delivery(p, root, name)
    return output


def settled(p):
    p.coordinator.host.finish()
    p.coordinator.tick()
    return p.root.call_tool('progression_status', {})


def facts(p):
    with p.runtime.scheduler_bindings._connect() as db:
        return [dict(json.loads(item['fact_json']), sequence=json.loads(item['fact_json'])['consumption_sequence'])
            for item in db.execute("SELECT fact_json FROM scheduler_progress_facts WHERE instance_id=? "
                "ORDER BY json_extract(fact_json,'$.consumption_sequence')", (p.instance,))]


@pytest.mark.parametrize('outcome', ['supports', 'contradicts'])
def test_raw_task_native_experiment_analysis_counts_one_source_bound_cycle(progression, outcome):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis', outcome=outcome)
    view = settled(p)
    counts = view['progress_shadow']['counts']
    assert (counts['consumed'], counts['consumed_research_tasks'], counts['unverified_progress'],
        counts['awaiting_analysis'], counts['coverage_gap']) == (1, 1, 0, 0, 0), counts
    assert counts['assessed_scientific_changes'] == 1 and counts['verified_test_resolutions'] == 0
    assert not view['progress_shadow']['notices'] and row(p)['state'] == 'active'
    status = root.call_tool('run_status', dict(name='analysis'))
    assert status['scientific_progress']['status'] == 'worker_assessed'
    assert status['scientific_progress']['scientific_validity'] == 'not_independently_verified'
    assert status['scientific_progress']['evidence_aliases'] == ['experiment_results']
    assert not {'cycle_key', 'families', 'ref'} & status['scientific_progress'].keys()
    assert len(facts(p)) == 3  # The ledger retains all deliveries; the reducer counts one question.


def test_repeated_analysis_delivery_and_restart_do_not_double_count(progression):
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis', missing=True)
    analysis(p, root, subject, 'rewritten-analysis', missing=True)
    native_delivery(p, root, 'analysis')
    view = settled(p)['progress_shadow']
    assert view['counts']['consumed_research_tasks'] == 1
    assert view['counts']['unverified_progress'] == 1 and view['counts']['no_progress'] == 0
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    restored = reopened.progress_shadow(instance_id=p.instance, objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json']))
    assert restored['counts'] == view['counts']
    assert reduce_shadow(facts(p))['consumed'] == 1
    # Consumption before an experiment's delivery must not reopen a closed cycle.
    ordered = facts(p)
    assert cycle_facts([ordered[2], ordered[1], ordered[0]])[1] == 0


@pytest.mark.parametrize('assessment', [None, 'no_progress'])
def test_repeated_local_optimization_or_missing_assessment_brakes_after_cycles(progression, assessment):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    for index in range(3):
        subject = experiment(p, root, hypothesis, f'experiment-{index}')
        analysis(p, root, subject, f'analysis-{index}', outcome='inconclusive', assessment=assessment,
            missing=assessment is None)
    view = settled(p)['progress_shadow']
    assert view['counts']['consumed_research_tasks'] == 3 and view['counts']['unverified_progress'] == 3
    assert view['counts']['no_progress'] == (3 if assessment else 0)
    assert view['counts']['coverage_gap'] == (0 if assessment else 3)
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    blocked = root.call_tool('operation_preflight', dict(name='unrelated-new-work', operation_id='blind.csv.observe.v1',
        inputs=[dict(port='source_table', artifact_names=['source_csv'])]))
    assert not blocked['admissible']


def test_new_files_and_repeated_supported_dimension_do_not_renew_window(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    for index in range(4):
        subject = experiment(p, root, hypothesis, f'experiment-{index}')
        analysis(p, root, subject, f'analysis-{index}')
    view = settled(p)['progress_shadow']
    assert view['counts']['assessed_scientific_changes'] == 1
    assert view['counts']['unverified_progress'] == 3 and view['counts']['consumed_research_tasks'] == 4
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'


def test_legacy_policy_without_exploration_window_brakes_repeated_worker_family(progression):
    p = progression
    root = setup(p, unverified_progress_threshold=None)
    hypothesis = proposal(p, root)
    for index in range(4):
        subject = experiment(p, root, hypothesis, f'experiment-{index}')
        analysis(p, root, subject, f'analysis-{index}')
    view = settled(p)['progress_shadow']
    assert view['counts']['consumed'] == 4 and view['counts']['coverage_gap'] == 3
    assert view['counts']['no_progress'] == 0
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'
    assert root.call_tool('run_status', dict(name='analysis-3'))['scientific_progress']['outcome'] == 'advance'


def test_unclosed_work_brakes_but_exact_analysis_can_close_it_under_same_budget(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subjects = [experiment(p, root, hypothesis, f'experiment-{index}', blocked=True) for index in range(3)]
    view = settled(p)['progress_shadow']
    assert view['counts']['awaiting_analysis'] == 3 and view['counts']['consumed_research_tasks'] == 0
    assert view['counts']['no_progress'] == 0 and row(p)['state'] == 'paused'
    before = json.loads(row(p)['config_json'])
    analysis(p, root, subjects[0], 'close-existing', missing=True)
    assert json.loads(row(p)['config_json']) == before
    # The same experiment cannot be a perpetual new-analysis exemption.
    request = dict(name='repeated-closeout', operation_id='science.result.analyze.v1',
        inputs=[dict(port='subject', artifact_names=[subjects[0]])], instruction='Repeated interpretation.')
    assert not root.call_tool('operation_preflight', request)['admissible']
    with pytest.raises(Exception, match='paused|progress'):
        root.call_tool('operation_invoke', request)


def test_accepted_running_wait_and_observation_ticks_do_not_create_attempts(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    root.call_tool('operation_invoke', dict(name='still-running', operation_id='science.experiment.v1',
        inputs=[dict(port='subject', artifact_names=[hypothesis])], instruction='One bounded test.'))
    worker = attached_worker(p.runtime, root, 'still-running')
    worker.call_tool('worker_open_assignment', {})
    measured_fixture_usage(worker)
    before = p.root.call_tool('progression_status', {})['progress_shadow']
    for _ in range(4):
        p.coordinator.tick()
        assert p.root.call_tool('progression_status', {})['progress_shadow'] == before
    assert before['counts']['consumed_research_tasks'] == 0 and before['counts']['no_progress'] == 0
    assert row(p)['state'] == 'active'


def test_preexisting_generic_family_enters_bounded_background_knowledge(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis', outcome='contradicts')
    run_id = p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='analysis')
    projection = research_progress(p.runtime.runs, p.runtime.runs.status(run_id))
    snapshot = background_snapshot(p.runtime.runs, instance_id=p.instance)
    assert snapshot['proof_coverage'] == 'complete'
    assert projection['families'][0]['key'] in snapshot['known_resolutions']
    assert projection['cycle_key'] in snapshot['known_cycles']
    terminal = terminal_fact(p.runtime.runs, p.runtime.runs.status(run_id))
    sample = dict(sequence=1, task_name='analysis', terminal=terminal)
    advances = []
    reduce_shadow([sample], known_resolutions=snapshot['known_resolutions'], advances=advances)
    assert advances == []
    assert cycle_facts([sample], known_cycles=snapshot['known_cycles'])[0] == []


def test_new_file_self_reported_advance_without_scientific_change_remains_unknown(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'self-reported', missing=True, assessment='advance')
    view = settled(p)['progress_shadow']
    assert view['counts']['unverified_progress'] == 1 and view['counts']['assessed_scientific_changes'] == 0
    assert view['counts']['no_progress'] == 0


@pytest.mark.parametrize('assessment', ['no_progress', 'unknown'])
def test_repeated_support_can_have_no_decision_increment_or_unknown(progression, assessment):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis', assessment=assessment)
    view = settled(p)['progress_shadow']
    assert view['counts']['unverified_progress'] == 1 and view['counts']['assessed_scientific_changes'] == 0
    assert view['counts']['no_progress'] == (1 if assessment == 'no_progress' else 0)
    status = root.call_tool('run_status', dict(name='analysis'))
    assert status['scientific_progress']['outcome'] == assessment
    hypotheses = next(item['value'] for item in status['selected_output']['items']
        if item['pointer'] == '/hypothesis_assessments')
    assert hypotheses[0]['outcome'] == 'supports'


def test_analysis_admission_can_consume_the_boundary_that_first_triggers_pending_pause(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subjects = [experiment(p, root, hypothesis, f'experiment-{index}', blocked=True) for index in range(3)]
    # The third experiment has been delivered but not yet consumed. Admission
    # itself consumes it, reaches the pending limit and must still close it.
    assert p.root.call_tool('progression_status', {})['progress_shadow']['counts']['awaiting_analysis'] == 2
    analysis(p, root, subjects[-1], 'close-at-boundary', missing=True)
    assert p.runtime.runs.status(p.runtime.scheduler_bindings.resolve(
        instance=p.instance, namespace='run', name='close-at-boundary')).state == 'completed'


def test_same_subject_reanalysis_has_a_bounded_observation_signal_not_new_attempts(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    for index in range(4):
        analysis(p, root, subject, f'analysis-{index}', missing=True)
    view = settled(p)['progress_shadow']
    assert view['counts']['consumed_research_tasks'] == 1 and view['counts']['unverified_progress'] == 1
    assert view['counts']['repeated_analysis'] == 3 and view['counts']['no_progress'] == 0
    assert any(item['reason'] == 'repeated_analysis' for item in view['notices'])
    assert row(p)['reason'] == 'scientific_progress_persistent_gap'


def project_csv_progress(payload, sources):
    return ScientificProgressProjection(outcome='no_progress', question='Does this finite table establish a mechanism?',
        answer=payload['interpretation'], remaining_question='A further independent observation is needed.',
        evidence_keys=('source_table',))


PLUGIN_PROGRESS = CallableComponent('projector', project_csv_progress)


def test_third_party_standalone_analysis_projects_without_generic_schema_or_portfolio(tmp_path):
    from blind_csv_plugin.plugin import PLUGIN
    from tests.operations.test_local_worker_contracts import _system, _invoke, _worker, _write_result
    progress = ScientificProgressSpec(stage='analysis', subject_port='source_table', objective_port='source_table',
        projector=ComponentRef('progress_projection'), source_ports=('source_table',))
    plugin = PLUGIN.model_copy(update=dict(operations=tuple(op.model_copy(update=dict(scientific_progress=progress))
        for op in PLUGIN.operations), components=(*PLUGIN.components,
            ComponentSpec('progress_projection', 'projector', __name__+':PLUGIN_PROGRESS'))))
    catalog, runtime, instance, root = _system(tmp_path, blind_plugin=plugin)
    _invoke(root, 'standalone-analysis')
    worker = _worker(catalog, runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    run = runtime.runs.status(runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace='run', name='standalone-analysis'))
    projected = terminal_fact(runtime.runs, run)
    assert projected['scientific_progress']['status'] == 'worker_assessed'
    assert projected['scientific_progress']['outcome'] == 'no_progress'
    assert projected['verified_progress']['status'] == 'unknown'
    assert {item.port_name for item in run.inputs} == {'source_table'}
    assert root.call_tool('run_status', dict(name='standalone-analysis'))['scientific_progress']['outcome'] == 'no_progress'


@pytest.mark.parametrize('citation', ['objective_source', 'hypothesis_portfolio'])
def test_original_goal_or_hypothesis_alone_is_not_an_observation_progress_anchor(progression, citation):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis', evidence_keys=[citation])
    status = root.call_tool('run_status', dict(name='analysis'))
    assert status['state'] == 'completed' and status['scientific_progress']['status'] == 'unknown'
    counts = settled(p)['progress_shadow']['counts']
    assert counts['unverified_progress'] == 1 and counts['assessed_scientific_changes'] == 0


def test_experiment_prompt_exposes_minimal_question_handoff_in_real_assignment(progression):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    root.call_tool('operation_invoke', dict(name='bounded', operation_id='science.experiment.v1',
        inputs=[dict(port='subject', artifact_names=[hypothesis])], instruction='One bounded test.'))
    worker = attached_worker(p.runtime, root, 'bounded')
    opened = worker.call_tool('worker_open_assignment', {})
    prompt = json.loads(Path(opened['assignment_path']).read_bytes())['role_instructions']
    from scidiscovery.general_science_experiment_task import PROMPT
    assert PROMPT in prompt  # The compiled assignment delivers the current owner guidance.
    assert 'separate result-analysis task' in prompt


@pytest.mark.parametrize('keys, expected', [(['experiment_results', 'recalculation'], 'worker_assessed'),
    (['recalculation'], 'unknown')])
def test_s9_self_published_attachment_cocitation_uses_exact_completed_manifest(progression, keys, expected):
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis', supplement=True, evidence_keys=keys)
    status = root.call_tool('run_status', dict(name='analysis'))
    assert status['scientific_progress']['status'] == expected
    assert 'attachment_003' in status['scientific_progress']['evidence_aliases']
    counts = settled(p)['progress_shadow']['counts']
    assert counts['consumed_research_tasks'] == 1
    assert counts['assessed_scientific_changes'] == (1 if expected == 'worker_assessed' else 0)


@pytest.mark.parametrize('retired_consumer', [False, True])
def test_retired_contract_never_grants_or_crashes_exact_analysis_closeout(retired_consumer):
    from types import SimpleNamespace as S
    from scidiscovery.artifact_agent.service.run_admission import RunAdmissionMixin
    from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
    subject = object()
    declaration = S(stage='analysis', subject_port='subject')
    producer = S(instance_id='instance', run_id='producer')
    consumer = S(state='completed')
    def compiled(value):
        if value is consumer or not retired_consumer:
            raise RunContractUnavailable('Historical operation retired.')
        return S(spec=S(scientific_progress=S(stage='experiment')))
    runs = S(completed_for_output=lambda ref: producer, compiled_operation=compiled,
        related_runs=lambda **kwargs: [consumer])
    bound = S(compiled=S(spec=S(scientific_progress=declaration)),
        inputs=[S(port_name='subject', artifact=S(ref=subject))])
    assert RunAdmissionMixin.requested_analysis_owner(runs, bound, instance_id='instance') is None


def test_new_identity_for_identical_original_goal_cannot_create_new_scientific_family(progression):
    from dataclasses import replace
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    p = progression
    root = setup(p)
    hypothesis = proposal(p, root)
    subject = experiment(p, root, hypothesis, 'experiment')
    analysis(p, root, subject, 'analysis')
    run = p.runtime.runs.status(p.runtime.scheduler_bindings.resolve(instance=p.instance, namespace='run', name='analysis'))
    original = next(item for item in run.inputs if item.port_name == 'objective_source')
    envelope = p.runtime.artifacts.catalog(original.artifact_ref)
    clone = p.runtime.artifacts.register(p.runtime.artifacts.read(original.artifact_ref), ArtifactRegistration(
        artifact_id='identical_goal_new_identity', kind=envelope.kind, schema_id=envelope.schema_id,
        payload_schema_version=1, media_type=envelope.media_type, creator=p.runtime.actor,
        parent_refs=envelope.parent_refs), idempotency_key='identical-goal').ref
    rebound = replace(run, inputs=tuple(replace(item, artifact_ref=clone)
        if item is original else item for item in run.inputs))
    assert clone != original.artifact_ref
    assert research_progress(p.runtime.runs, rebound)['families'] == research_progress(p.runtime.runs, run)['families']


def test_public_unknown_adapter_metadata_does_not_claim_an_interpreted_scientific_cycle():
    from scidiscovery.artifact_agent.service.research_progress import public_progress
    value = public_progress(dict(status='unknown', reason='scientific_progress_not_declared'))
    assert value['counting_basis'] == 'completed_task_observation_without_scientific_adapter'
    pending = public_progress(dict(status='awaiting_analysis', stage='experiment'))
    assert pending['counting_basis'] == 'completed_work_awaits_interpretation'
    interpreted = public_progress(dict(status='worker_assessed', stage='analysis'))
    assert interpreted['counting_basis'] == 'one_exact_interpreted_subject'
