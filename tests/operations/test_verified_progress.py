"""Sealed evidence -> actual consumption -> the existing dispatch guard."""
import json
from copy import copy, deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.operations.test_progression import progression, unmanaged_progression, row
from tests.operations.test_progress_assist import configure, next_turn
from tests.operations.test_progress_shadow import native_delivery
from tests.operations.test_scientific_progress import active, request, assess, INTENT
from tests.operations.test_local_worker_contracts import _worker, _write_result
from tests.operations.test_human_progress_continuation import paused, human_ui, submit


@pytest.fixture
def science_progression(tmp_path, request, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_system
    from tests.operations import test_m2_curve_analysis_boundary as curve
    from tests.operations.research_loop_fixtures import authorize_loop
    from tests.operations.test_progression import Host
    from scidiscovery.artifact_agent.service.progression import ProgressionCoordinator
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    options = getattr(request, 'param', {})
    plan = curve._plan().model_dump(mode='json')
    check = plan['validation_plans'][0]['numerical']['checks'][0]
    if options.get('multiple_checks'):
        from dataclasses import replace
        from curve_score import analysis_tool
        checks = []
        for index in range(options['multiple_checks']):
            checks.append(dict(check, check_key=f'm{index:03}', evaluator_profile='fixture.finite-counts.v1',
                evaluator_metric=f'point_count_plus_{index}', threshold=dict(operator='le', value=3+index, unit='1')))
        plan['validation_plans'][0]['numerical']['checks'] = checks[:128]
        if len(checks) > 128:
            plan['validation_plans'][0]['physical'] = dict(applicability='required', rationale='A further finite check.', checks=checks[128:])
        # A registered test evaluator uses the public projection and normal
        # controlled completion. The Agent never authors values or receipts.
        monkeypatch.setattr(analysis_tool, 'CURVE_SCORE_TOOL', replace(analysis_tool.CURVE_SCORE_TOOL,
            contextual_handler=finite_count_tool))
    if options.get('negative'):
        plan['validation_plans'][0]['physical'] = dict(applicability='required', rationale='A finite falsifiable observation.', checks=[check])
        plan['validation_plans'][0]['numerical'] = dict(applicability='not_applicable', rationale='This finite math fixture has no solver prerequisite.', checks=[])
    if options.get('qualitative'):
        plan['objective_key'] = 'finite_target'
        check.update(evaluation_mode='reviewed_qualitative', evaluator_profile=None, evaluator_metric=None, threshold=None)
    catalog, runtime, root, _, artifacts, register = analysis_system(tmp_path, plan=ExperimentPortfolio.model_validate_json(canonical_json(plan)))
    instance = root.facade._instance_id()
    user = 'sch_'+'a'*32
    runtime.scheduler_bindings.bind_session(session_key=user, instance_id=instance)
    root.facade.session_key = user
    now = [1000.]
    runtime.scheduler_bindings.progression_clock = lambda: now[0]
    root.call_tool('progression_command', dict(command='takeover', mode='interactive'))
    root.call_tool('artifact_ingest_text', dict(name='goal', text='Resolve the predeclared finite test, retaining its boundary.'))
    root.call_tool('progression_command', dict(command='pause'))
    criterion = artifacts['plan'].ref
    if options.get('prestart'):
        goal_ref = runtime.artifacts.get_by_id(root.facade._resolve('artifact', 'goal')).ref
        criterion = register('prestart-plan', runtime.artifacts.read(criterion),
            'scidiscovery.experiment-portfolio.v1', parents=(goal_ref,)).ref
    settings = runtime.scheduler_bindings.global_settings
    runtime.scheduler_bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist', no_progress_threshold=100, refinement_threshold=100, observation_gap_threshold=100))))
    contract = curve._contract().model_dump(mode='json')
    if options.get('negative'):
        contract['comparison_spec']['comparisons'][0]['gate_scope'] = 'objective'
    if not options.get('posthoc'):
        register('conditions', canonical_json(contract), 'scidiscovery.curve-experiment-contract.v1', parents=(criterion,))
    bundle = curve._bundle().model_dump(mode='json')
    if not options.get('negative'):
        bundle['series'][1]['points'] = deepcopy(bundle['series'][0]['points'])
    parents = (criterion,) if options.get('posthoc') or options.get('qualitative') else (criterion, artifacts['conditions'].ref)
    register('generic_results', b'Exact later bounded observation.', 'opaque', parents=parents)
    register('generic_bundle', canonical_json(bundle), 'scidiscovery.curve-bundle.v1', parents=parents)
    if options.get('posthoc'):
        register('conditions', canonical_json(contract), 'scidiscovery.curve-experiment-contract.v1', parents=(artifacts['plan'].ref,))
    if options.get('prestart'):
        root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='goal'))
    else:
        authorize_loop(runtime, instance, user, 'goal')
        root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    def facade(session):
        value = copy(root.facade)
        value.session_key = session
        return value
    coordinator = ProgressionCoordinator(runtime=runtime, host_factory=Host, facade_factory=facade, clock=lambda: now[0])
    p = SimpleNamespace(catalog=catalog, runtime=runtime, root=root, instance=instance, user=user,
        now=now, facade=facade, coordinator=coordinator, register=register, artifacts=artifacts, options=options, contract=contract)
    yield p
    coordinator.close()


def finite_count_tool(request, context):
    """Registered fixture evaluator: exact finite point count plus named offset."""
    import hashlib
    from curve_score.analysis_tool import evaluate_analysis_request
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    from scidiscovery.artifact_agent.schema.validation import ValidationCheckResult, evaluate_threshold
    from scidiscovery.plugin_runtime.calculations import CalculationResult, CalculationValidation
    plan_alias, = context.input_names_for_port('experiment_plan')
    conditions_alias, = context.input_names_for_port('reference_material')
    sources = {alias: context.read_evidence(alias) for alias in (plan_alias, conditions_alias, 'curve_bundle')}
    portfolio = ExperimentPortfolio.model_validate_json(sources[plan_alias], strict=True)
    plan, = portfolio.validation_plans
    bundle = json.loads(sources['curve_bundle'])
    count = len(bundle['series'][0]['points'])
    results = []
    for dimension in (plan.numerical, plan.physical, plan.experimental):
        for check in dimension.checks:
            observed = count + int(check.evaluator_metric.removeprefix('point_count_plus_'))
            passed = evaluate_threshold(observed, check.threshold, observed_unit='1')
            results.append(ValidationCheckResult(check_key=check.check_key, status='pass' if passed else 'fail',
                evaluation_mode='deterministic_threshold', observed_value=observed, observed_text=str(observed),
                unit='1', evidence_keys=('curve_bundle',), rationale='Count.'))
    curve_result = evaluate_analysis_request(record_key=request.record_key, request=request.request.raw_request,
        sources={'curve_bundle': sources['curve_bundle']})
    assert curve_result.status == 'computed'
    record = CalculationResult(record_key=request.record_key, request=request.request.raw_request,
        algorithm_version='fixture.finite-counts.v1', status='computed', result=curve_result.result,
        input_digests={alias: hashlib.sha256(raw).hexdigest() for alias, raw in sources.items()},
        validation=CalculationValidation(plan_source=plan_alias, conditions_source=conditions_alias,
            result_sources=('curve_bundle',), evaluator_profile='fixture.finite-counts.v1',
            experiment_key=plan.experiment_key, plan_key=plan.plan_key, results=tuple(results)))
    return context.complete_calculation(record, summary=True)


def scientific_result(p, root, name, *, controlled=False, conditions=True, scope_mismatch=False,
                      plan_name='plan', condition_name='conditions', bundle_name='generic_bundle', result_name='generic_results', deliver=True):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from tests.operations.test_result_analysis_tool import score_inputs
    from tests.operations import test_m2_curve_analysis_boundary as curve
    if p.options.get('prestart') and plan_name == 'plan':
        plan_name = 'prestart-plan'
    inputs = [dict(port='experiment_plan', artifact_names=[plan_name]),
        dict(port='experiment_results', artifact_names=[result_name]), dict(port='curve_bundle', artifact_names=[bundle_name])]
    if conditions:
        inputs.append(dict(port='reference_material', artifact_names=[condition_name]))
    root.call_tool('operation_invoke', dict(name=name, operation_id='science.result.diagnose.v1', inputs=inputs,
        instruction='Resolve this exact predeclared test and preserve its limits.', scientific_intent=INTENT))
    run_id = root.facade._resolve('run', name)
    caller = ('source-session', name+'-thread')
    p.runtime.runs.worker_connections.attach(run_id=run_id, platform_session=caller[0], thread_id=caller[1])
    worker = LocalWorkerMCPRouter(p.runtime.runs, operation_id='science.result.diagnose.v1',
        operation_digest=p.catalog.operation('science.result.diagnose.v1').digest, run_id=run_id, trusted_caller=caller)
    opened = worker.call_tool('worker_open_assignment', {})
    description = next(tool['description'] for tool in worker.list_tools() if tool['name'] == 'worker_curve_score')
    assert 'immutable ancestors' in description and '64 distinct original envelopes' in description
    assert 'do not prove original generation time' in description
    scoring = score_inputs()[1]
    scoring['comparison_spec'] = deepcopy(p.contract['comparison_spec'])
    if scope_mismatch:
        scoring['comparison_spec']['comparisons'][0]['domain']['stop'] = .5
    score = worker.call_tool('worker_curve_score', dict(record_key=name, request=scoring)) if controlled else None
    alias = score['calculation_ref'] if score else 'experiment_results'
    payload = curve._passing_diagnosis().model_dump(mode='json')
    payload['summary'] = name+' provides a bounded observation, not physical identification.'
    if p.options.get('negative'):
        payload['gates']['observation'].update(status='fail', summary='The predeclared finite observation is contradicted.')
        payload['overall_verdict'] = 'fail'
    if p.options.get('qualitative'):
        payload['objective_assessment'] = dict(objective_key='finite_target', status='pass',
            summary='The exact finite qualitative condition was observed.', evidence_keys=[alias])
    payload['evidence'] = [dict(source_key=alias, source_type='runtime_output', title='Exact observation', locator=alias)]
    payload['source_references'] = [dict(source_key=alias, input_alias=alias)]
    for gate in payload['gates'].values():
        if isinstance(gate, dict) and gate.get('evidence_keys'):
            gate['evidence_keys'] = [alias]
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(payload=payload)))
    from tests.operations.research_loop_fixtures import measured_fixture_usage
    measured_fixture_usage(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assess(root, name, outcome='advance')
    if deliver:
        native_delivery(p, root, name)
    return worker, score


def settle(p):
    p.coordinator.host.finish()
    next_turn(p)
    return p.root.call_tool('progression_status', {})


def test_real_registered_calculation_first_resolution_clears_once_then_repetition_pauses(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'unverified-first')
    worker, score = scientific_result(p, root, 'resolved', controlled=True)
    records = p.runtime.runs.tool_evidence(worker._run_id)
    receipt = next(record for record in records if record['alias'] == score['calculation_ref'])
    assert receipt['metadata']['calculation_proof'].get('validation'), receipt['metadata']['calculation_proof']
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof['status'] == 'verified_test_resolution', proof
    scientific_result(p, root, 'repeat-a', controlled=True)
    status = p.root.call_tool('progression_status', {})
    assert status['progress_shadow']['counts']['unverified_progress'] == 0
    assert status['progress_shadow']['counts']['verified_test_resolutions'] == 1
    for name in ('repeat-b', 'repeat-c'):
        scientific_result(p, root, name, controlled=True)
    status = settle(p)
    assert status['progress_shadow']['counts']['verified_test_resolutions'] == 1
    assert status['progress_shadow']['counts']['unverified_progress'] == 3, status['progress_shadow']
    assert row(p)['state'] == 'paused'


def test_existing_registered_tool_without_validation_remains_normal_and_unknown(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    worker, score = scientific_result(p, active(p), 'ordinary-score', controlled=True, conditions=False)
    assert score['status'] == 'computed'
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof['status'] == 'unknown' and proof['resolutions'] == []
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1


@pytest.mark.parametrize('science_progression', [dict(negative=True)], indirect=True)
def test_frozen_valid_negative_resolves_once_and_repeated_negative_cannot_renew(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'unknown-before-negative')
    worker, _ = scientific_result(p, root, 'finite-negative', controlled=True)
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    # Preserve a bounded timing/projection diagnostic if the strict prior-seal
    # proof fails; the resource runner removes its temporary control stores.
    import os
    value = p.runtime.runs.status(worker._run_id)
    receipts = p.runtime.runs.tool_evidence(worker._run_id)
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    calculations = [json.loads(p.runtime.artifacts.read(ArtifactRef.model_validate(item['artifact_ref'])))
        for item in receipts if item['metadata'].get('kind') == 'calculation_record']
    diagnostic = dict(proof=proof, sealed_inputs={item.source_name: p.runtime.artifacts.catalog(item.artifact_ref).created_at
        for item in value.inputs}, calculations=[{key: item.get(key) for key in ('status', 'validation', 'attempt')}
            for item in calculations])
    if log_directory := os.environ.get('SCID_TEST_LOG_DIR'):
        directory = Path(log_directory)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'negative-proof.json').write_text(json.dumps(diagnostic, indent=2))
    assert proof['status'] == 'verified_test_resolution' and proof['resolutions'][0]['result'] == 'fail', diagnostic
    for name in ('negative-repeat-a', 'negative-repeat-b', 'negative-repeat-c'):
        scientific_result(p, root, name, controlled=True)
    status = settle(p)
    assert status['progress_shadow']['counts']['verified_test_resolutions'] == 1
    assert status['progress_shadow']['counts']['unverified_progress'] == 3
    assert row(p)['state'] == 'paused'


@pytest.mark.parametrize('science_progression', [dict(posthoc=True), {}], indirect=True)
def test_posthoc_condition_or_different_comparison_scope_is_unknown(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    worker, score = scientific_result(p, active(p), 'not-frozen-science', controlled=True,
        scope_mismatch=not p.options.get('posthoc'))
    assert score['status'] == 'computed'
    assert terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']['status'] == 'unknown'
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1


def scientific_review(p, root, name, subject, *, explicit=True, mismatch=None):
    from tests.operations.test_shared_review_admission import request
    from tests.operations.worker_fixtures import attached_worker
    from tests.operations.research_loop_fixtures import measured_fixture_usage
    query = request(name, subject+'.output')
    if mismatch == 'subject':
        query['inputs'].append(dict(port='scientific_materials', artifact_names=['generic_results']))
    root.call_tool('operation_invoke', query)
    worker = attached_worker(p.runtime, root, name)
    opened = worker.call_tool('worker_open_assignment', {})
    # The same optional science field is present in the actual Worker schema.
    schema = Path(opened['output_directory']).parent / 'schema' / 'result.schema.json'
    form = json.loads(schema.read_text())['properties']['payload']
    assert 'scientific_test' in form['properties'] and 'scientific_test' not in form['required']
    assert 'immutable ancestor' in form['properties']['scientific_test']['description']
    assert '64 distinct original envelopes' in form['properties']['scientific_test']['description']
    subject_input = Path(opened['output_directory']).parent / 'inputs' / 'subject.json'
    assert json.loads(subject_input.read_text())['plan_key'] == 'validate_implementation'
    payload = dict(verdict='pass', summary='The exact scientific test conclusion meets its prior qualitative criterion.')
    if explicit:
        payload['scientific_test'] = dict(experiment_key='implementation_check',
            plan_key='another_plan' if mismatch == 'plan' else 'validate_implementation',
            result=dict(check_key='profile_rms', status='pass', evaluation_mode='reviewed_qualitative',
                observed_text='The exact finite qualitative condition was observed.',
                evidence_keys=['scientific_materials' if mismatch == 'subject' else 'subject'],
                rationale='Independently compared this exact conclusion with the prior acceptance condition.'))
    Path(opened['output_directory'], 'result.json').write_text(json.dumps(dict(payload=payload)))
    measured_fixture_usage(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    if explicit:
        read = root.call_tool('run_status', dict(name=name, output_fields=['scientific_test']))
        conclusion = read['selected_output']['items'][0]
        assert conclusion['status'] == 'selected' and conclusion['value']['plan_key'] == payload['scientific_test']['plan_key']
    native_delivery(p, root, name)
    return worker


@pytest.mark.parametrize('science_progression', [dict(qualitative=True)], indirect=True)
def test_qualified_independent_exact_qualitative_test_and_duplicate_review(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'qualitative-subject')
    reviewer = scientific_review(p, root, 'exact-review', 'qualitative-subject')
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(reviewer._run_id))['verified_progress']
    assert proof['status'] == 'verified_test_resolution', proof
    scientific_result(p, root, 'after-review')
    status = p.root.call_tool('progression_status', {})
    assert status['progress_shadow']['counts']['consumed_research_tasks'] == 1
    assert status['progress_shadow']['counts']['unverified_progress'] == 0
    scientific_review(p, root, 'repeat-review', 'qualitative-subject')
    status = settle(p)
    assert status['progress_shadow']['counts']['consumed_research_tasks'] == 2
    assert status['progress_shadow']['counts']['unverified_progress'] == 1
    assert status['progress_shadow']['counts']['verified_test_resolutions'] == 1


def test_independent_quality_pass_without_exact_qualitative_check_is_unknown(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'numeric-unverified')
    reviewer = scientific_review(p, root, 'quality-only', 'numeric-unverified')
    assert terminal_fact(p.runtime.runs, p.runtime.runs.status(reviewer._run_id))['verified_progress']['status'] == 'unknown'
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1


@pytest.mark.parametrize('science_progression', [dict(qualitative=True)], indirect=True)
@pytest.mark.parametrize('mismatch', [None, 'plan', 'subject'])
def test_quality_only_or_wrong_plan_or_subject_remains_normal_review_unknown(science_progression, mismatch):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'exact-qualitative-subject')
    reviewer = scientific_review(p, root, 'not-a-test-resolution', 'exact-qualitative-subject',
        explicit=mismatch is not None, mismatch=mismatch)
    assert p.runtime.runs.status(reviewer._run_id).state == 'completed'
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(reviewer._run_id))['verified_progress']
    assert proof['status'] == 'unknown', proof
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1


def changed_result(p, root, name, index):
    root.call_tool('operation_invoke', request(name, {**INTENT, 'target': f'Reworded question {index}'}))
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    path = worker._workspace.output_directory / 'result.json'
    result = json.loads(path.read_text())
    result['payload']['interpretation'] = f'New wording {index}; this mean does not identify a mechanism.'
    path.write_text(json.dumps(result))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assess(root, name, outcome='advance')
    native_delivery(p, root, name)


def test_new_outputs_and_supported_root_advances_still_require_direction_confirmation(progression):
    p = progression
    configure(p)
    root = active(p)
    for index in range(3):
        changed_result(p, root, f'novel-{index}', index)
    p.coordinator.host.finish()
    next_turn(p)
    status = p.root.call_tool('progression_status', {})
    assert status['progress_shadow']['counts']['unverified_progress'] == 3
    assert row(p)['state'] == 'paused'
    assert any(item['reason'] == 'unverified_progress' for item in status['progress_shadow']['notices'])
    with pytest.raises(Exception, match='paused|progress'):
        root.call_tool('operation_invoke', request('cannot-bypass'))


def test_late_root_claim_restart_reads_and_new_loop_preserve_frozen_trigger(progression):
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    p = progression
    configure(p)
    root = active(p)
    for index in range(3):
        changed_result(p, root, f'late-{index}', index)
    settle(p)
    before = p.root.call_tool('progression_status', {})['progress_shadow']
    frozen = next(n for n in before['notices'] if n['reason'] == 'unverified_progress')
    assess(root, 'late-2', reason='Late new assertion: this is now an advance.')
    for _ in range(2):
        assert p.root.call_tool('progression_status', {})['progress_shadow']['notices'] == before['notices']
    reopened = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    restored = reopened.progress_shadow(instance_id=p.instance, objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json']))
    restored_notice = next(n for n in restored['notices'] if n['id'] == frozen['id'])
    assert {key: restored_notice[key] for key in frozen} == frozen
    assert restored['counts']['unverified_progress'] == 3
    p.coordinator.tick()  # Release the confirmed terminal native host.
    bindings = p.runtime.scheduler_bindings
    proposal = bindings.loop_authorization_proposal(instance_id=p.instance, session_key=p.user)
    prior_loop = json.loads(row(p)['checkpoint_json'])['current_loop_id']
    bindings.authorize_loop_from_ui(instance_id=p.instance, session_key=p.user,
        confirmation_binding=proposal['confirmation_binding'], objective_name='goal',
        objective_ref=ArtifactRef.model_validate_json(row(p)['objective_ref_json']))
    assert json.loads(row(p)['checkpoint_json'])['current_loop_id'] != prior_loop
    assert frozen in p.root.call_tool('progression_status', {})['progress_shadow']['notices']
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))


def test_each_goal_revision_retains_the_same_consumed_window(progression):
    p = progression
    configure(p, no_progress_threshold=100, observation_gap_threshold=100, refinement_threshold=100)
    for index in range(3):
        if index:
            p.root.call_tool('progression_command', dict(command='pause'))
            p.coordinator.tick()
            p.root.call_tool('progression_command', dict(command='takeover'))
            name = f'goal-{index}'
            p.root.call_tool('artifact_ingest_text', dict(name=name, text=f'Reword the current objective {index}.'))
            p.root.call_tool('progression_command', dict(command='pause'))
            p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name=name))
            p.now[0] += 6  # Preserve the existing native observation cooldown.
        changed_result(p, active(p), f'goal-result-{index}', index)
        status = settle(p)
        assert status['progress_shadow']['counts']['unverified_progress'] == index+1
    assert row(p)['state'] == 'paused'


def test_already_accepted_worker_can_open_and_complete_after_exploration_pause(progression):
    from tests.operations.test_scientific_progress import finish
    p = progression
    configure(p, unverified_progress_threshold=2)
    root = active(p)
    # Deliver the old completed results only after the new task is accepted.
    finish(p, root, 'old-a')
    finish(p, root, 'old-b')
    root.call_tool('operation_invoke', request('accepted-before-observation'))
    native_delivery(p, root, 'old-a')
    native_delivery(p, root, 'old-b')
    settle(p)
    assert row(p)['state'] == 'paused'
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert p.root.call_tool('run_status', dict(name='accepted-before-observation'))['state'] == 'completed'


def test_real_ui_new_window_preserves_old_trigger_and_resource_high_water(human_ui):
    from tests.operations.test_progression import checkpoint
    p = human_ui.p
    before = checkpoint(p)
    old = p.root.call_tool('progression_status', {})['progress_shadow']
    assert old['counts']['unverified_progress'] == 3
    assert submit(human_ui) == 303
    new = p.root.call_tool('progression_status', {})['progress_shadow']
    assert new['counts']['unverified_progress'] == 0 and new['notices'] == old['notices']
    assert new['window_start_sequence'] == old['through_sequence']
    for key in ('admissions', 'rounds', 'attempts', 'usage_records', 'started_at', 'budget', 'current_loop_id'):
        assert checkpoint(p).get(key) == before.get(key)


def test_legacy_grant_missing_new_policy_is_not_silently_upgraded(progression):
    from tests.operations.test_progression import checkpoint
    from scidiscovery.artifact_agent.service.progression_records import store_checkpoint
    from scidiscovery.artifact_agent.service.scientific_progress import shadow_policy
    p = progression
    bindings = p.runtime.scheduler_bindings
    control = row(p)
    config, cp = json.loads(control['config_json']), checkpoint(p)
    config['effective']['progression'].pop('unverified_progress_threshold')
    cp['loop_authorizations'][cp['current_loop_id']]['config'] = config
    with bindings._connect() as db:
        db.execute('UPDATE scheduler_progression SET config_json=?,checkpoint_json=? WHERE instance_id=?',
            (json.dumps(config), store_checkpoint(db, p.instance, cp), p.instance))
    assert shadow_policy(row(p))['unverified_progress_threshold'] is None
    assert bindings._control_settings_match(p.instance, row(p)['config_json'])
    changed_result(p, active(p), 'legacy-still-accepted', 0)
    # The absent key grants no new policy, even if the administrator edits it.
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(unverified_progress_threshold=4))))
    assert bindings._control_settings_match(p.instance, row(p)['config_json'])


def test_modern_grant_rejects_actual_edit_to_frozen_threshold(progression):
    p = progression
    root = active(p)
    bindings = p.runtime.scheduler_bindings
    settings = bindings.global_settings
    bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(unverified_progress_threshold=4))))
    assert not bindings._control_settings_match(p.instance, row(p)['config_json'])
    with pytest.raises(Exception, match='[Cc]onfiguration|config'):
        root.call_tool('operation_invoke', request('cannot-edit-frozen-policy'))


def test_shadow_notice_cannot_suppress_new_frozen_assist_policy(progression):
    p = progression
    root = active(p)
    for index in range(3):
        changed_result(p, root, f'shadow-{index}', index)
    before = settle(p)['progress_shadow']
    assert row(p)['state'] == 'active' and before['mode'] == 'shadow'
    assert before['counts']['unverified_progress'] == 3
    old = next(n for n in before['notices'] if n['reason'] == 'unverified_progress')
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    configure(p, no_progress_threshold=100, refinement_threshold=100, observation_gap_threshold=100)
    after_config = p.root.call_tool('progression_status', {})['progress_shadow']
    assert after_config['mode'] == 'assist' and after_config['counts']['unverified_progress'] == 3, after_config
    from tests.operations.test_progression import Host
    def fresh_host(row, event):
        host = Host(row, event)
        host.identity = SimpleNamespace(thread_id='new-loop-root', session_id='new-loop-root')
        host.scheduler_session = 'sch_' + 'c'*32
        return host
    p.coordinator.host_factory = fresh_host
    p.now[0] += 6
    p.coordinator.tick()
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap', after_config
    after = p.root.call_tool('progression_status', {})['progress_shadow']
    assert old in after['notices']
    assert len({n['id'] for n in after['notices']}) == len(after['notices'])
    with pytest.raises(Exception, match='scientific_progress_persistent_gap'):
        p.root.call_tool('operation_invoke', request('cannot-hide-behind-shadow-notice'))


def test_posthoc_plan_with_paired_contract_cannot_bless_old_measured_bytes(science_progression):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    plan = json.loads(p.runtime.artifacts.read(p.artifacts['plan'].ref))
    plan['objective'] += ' (reworded after this observation)'
    p.register('late-plan', canonical_json(plan), 'scidiscovery.experiment-portfolio.v1')
    p.register('late-conditions', canonical_json(p.contract), 'scidiscovery.curve-experiment-contract.v1',
        parents=(p.artifacts['late-plan'].ref,))
    worker, score = scientific_result(p, active(p), 'late-plan-score', controlled=True,
        plan_name='late-plan', condition_name='late-conditions')
    receipt = next(r for r in p.runtime.runs.tool_evidence(worker._run_id) if r['alias'] == score['calculation_ref'])
    assert receipt['metadata']['calculation_proof']['validation']
    assert terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']['status'] == 'unknown'
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1


def test_resealed_reworded_plan_and_fresh_copy_of_result_do_not_renew_resolved_check(science_progression):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    root = active(p)
    original, _ = scientific_result(p, root, 'original-resolution', controlled=True)
    plan = json.loads(p.runtime.artifacts.read(p.artifacts['plan'].ref))
    plan['objective'] += ' (new words)'
    plan['proposals'][0]['cases'][0]['purpose'] += ' (same scientific conditions)'
    plan['validation_plans'][0]['numerical']['checks'][0]['basis'] += ' (reworded)'
    p.register('reworded-plan', canonical_json(plan), 'scidiscovery.experiment-portfolio.v1')
    p.register('reworded-conditions', canonical_json(p.contract), 'scidiscovery.curve-experiment-contract.v1',
        parents=(p.artifacts['reworded-plan'].ref,))
    p.register('fresh-bundle', p.runtime.artifacts.read(p.artifacts['generic_bundle'].ref),
        'scidiscovery.curve-bundle.v1', parents=(p.artifacts['reworded-plan'].ref, p.artifacts['reworded-conditions'].ref))
    rewritten, _ = scientific_result(p, root, 'reworded-resolution', controlled=True,
        plan_name='reworded-plan', condition_name='reworded-conditions', bundle_name='fresh-bundle')
    proof = lambda worker: terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof(original)['resolutions'][0]['key'] == proof(rewritten)['resolutions'][0]['key']
    status = settle(p)
    assert status['progress_shadow']['counts']['verified_test_resolutions'] == 1
    assert status['progress_shadow']['counts']['unverified_progress'] == 1


def memory_csv(p, name, goals):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from tests.operations.test_local_worker_contracts import RAW
    refs = tuple(p.runtime.artifacts.get_by_id(p.root.facade._resolve('artifact', goal)).ref for goal in goals)
    value = p.runtime.artifacts.register(RAW, ArtifactRegistration(kind='blind_csv_input',
        schema_id='blind.opaque.v1', payload_schema_version=1, media_type='text/csv',
        creator=p.runtime.actor, parent_refs=refs), idempotency_key=name)
    p.runtime.scheduler_bindings.bind(instance=p.instance, namespace='artifact', name=name, object_id=value.artifact_id)


def consumed_csv(p, root, name, source, *, deliver=True):
    query = request(name, intent=None)
    query['inputs'][0]['artifact_names'] = [source]
    root.call_tool('operation_invoke', query)
    worker = _worker(p.catalog, p.runtime)
    worker.call_tool('worker_open_assignment', {})
    _write_result(worker)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    if deliver:
        native_delivery(p, root, name)
    return worker._run_id


def switch_background_goal(p, goal):
    p.root.call_tool('progression_command', dict(command='pause'))
    p.coordinator.tick()
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name=goal))
    p.now[0] += 6
    root = active(p)
    assert json.loads(row(p)['checkpoint_json'])['phase'] == 'running'
    return root


def continue_window(p):
    # Reuse the real HTTP confirmation fixture, including its CSRF and sealed binding.
    generator = human_ui.__wrapped__(p)
    ui = next(generator)
    try:
        assert submit(ui) == 303
    finally:
        generator.close()


def test_cross_goal_redelivery_is_deduplicated_before_bounded_consumption_prefix(progression):
    p = progression
    configure(p, max_tasks=3, max_reviews=0, max_rounds=40, unverified_progress_threshold=2,
        no_progress_threshold=100, refinement_threshold=100, observation_gap_threshold=100)
    root = active(p)
    from tests.operations.test_progression import checkpoint
    capacity = sum(sum(grant['config']['effective']['progression'][key] for key in ('max_tasks', 'max_reviews'))
        for grant in checkpoint(p)['loop_authorizations'].values())
    goals = ['goal', *[f'delivery-goal-{index}' for index in range(capacity + 1)]]
    for goal in goals[1:]:
        root.call_tool('artifact_ingest_text', dict(name=goal, text='Retain the exact shared observation under '+goal))
    memory_csv(p, 'shared-observation', goals)
    old = consumed_csv(p, root, 'first-shared', 'shared-observation')
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1
    for goal in goals[1:]:
        root = switch_background_goal(p, goal)
        native_delivery(p, root, 'first-shared')
        if goal == goals[-1]:
            fresh = consumed_csv(p, root, 'later-new-run', 'shared-observation')
            status = settle(p)
        else:
            assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 1
    with p.runtime.scheduler_bindings._connect() as db:
        delivered = db.execute('SELECT run_id FROM scheduler_terminal_deliveries WHERE instance_id=? '
            'AND consumed_boundary IS NOT NULL', (p.instance,)).fetchall()
    assert [item['run_id'] for item in delivered].count(old) == len(goals)
    assert {item['run_id'] for item in delivered} == {old, fresh}
    assert status['progress_shadow']['counts']['consumed_research_tasks'] == 2, status['progress_shadow']
    assert status['progress_shadow']['counts']['unverified_progress'] == 2
    assert not status['progress_shadow']['omitted']
    assert row(p)['state'] == 'paused' and row(p)['reason'] == 'scientific_progress_persistent_gap'
    with pytest.raises(Exception, match='paused|progress'):
        root.call_tool('operation_invoke', request('after-unique-prefix-trigger'))


def test_awaiting_delivery_consumed_after_ui_window_counts_once_across_goals(progression, monkeypatch):
    p = progression
    monkeypatch.setattr('scidiscovery.artifact_agent.service.scheduling_control.time', lambda: p.now[0])
    configure(p, unverified_progress_threshold=1, observation_gap_threshold=1,
        no_progress_threshold=100, refinement_threshold=100)
    root = active(p)
    for goal in ('other-consumption-goal', 'repeat-consumption-goal'):
        root.call_tool('artifact_ingest_text', dict(name=goal, text='Retain exact evidence under '+goal))
    memory_csv(p, 'awaiting-source', ['goal', 'repeat-consumption-goal'])
    memory_csv(p, 'other-source', ['other-consumption-goal'])
    awaiting = consumed_csv(p, root, 'await-first', 'awaiting-source')
    host = p.coordinator.host
    host.completion = dict(id=host.turn_id, status='interrupted')
    host.event(dict(method='turn/completed', params=dict(threadId=host.identity.thread_id, turn=host.completion)))
    root = switch_background_goal(p, 'other-consumption-goal')
    consumed_csv(p, root, 'consume-second', 'other-source')
    before = settle(p)['progress_shadow']
    assert before['counts']['consumed_research_tasks'] == 1
    with p.runtime.scheduler_bindings._connect() as db:
        record = db.execute('SELECT sequence,consumed_boundary FROM scheduler_terminal_deliveries '
            'WHERE instance_id=? AND run_id=?', (p.instance, awaiting)).fetchone()
    assert record['consumed_boundary'] is None
    delivery_position = record['sequence']
    p.coordinator.tick()
    continue_window(p)
    window = p.root.call_tool('progression_status', {})['progress_shadow']['window_start_sequence']
    assert window == before['through_sequence']
    root = switch_background_goal(p, 'goal')
    native_delivery(p, root, 'await-first')
    after = settle(p)['progress_shadow']
    assert after['counts']['consumed_research_tasks'] == 1, after
    assert after['counts']['consumed'] == 1
    assert after['through_sequence'] > window
    assert row(p)['state'] == 'paused'
    for _ in range(2):
        root.call_tool('run_status', dict(name='await-first', intent='decision'))
        assert p.root.call_tool('progression_status', {})['progress_shadow']['counts']['consumed_research_tasks'] == 1
    with p.runtime.scheduler_bindings._connect() as db:
        records = db.execute('SELECT sequence FROM scheduler_terminal_deliveries WHERE instance_id=? AND run_id=?',
            (p.instance, awaiting)).fetchall()
    assert [record['sequence'] for record in records] == [delivery_position]
    p.coordinator.tick()
    continue_window(p)
    root = switch_background_goal(p, 'repeat-consumption-goal')
    native_delivery(p, root, 'await-first')
    repeated = settle(p)['progress_shadow']
    assert repeated['counts']['consumed_research_tasks'] == 0
    assert repeated['counts']['unverified_progress'] == 0


def test_actual_consumption_positions_survive_cold_read_archive_and_restore(paused):
    from scidiscovery.artifact_agent.state_format import STATE_FORMAT
    from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from tests.operations.synchronous_archive_fixture import SynchronousFixtureArchive
    from tests.operations.test_instance_archive import save_archive, restore_archive
    from scidiscovery.artifact_agent.service.instance_archive_records import readonly
    p = paused
    def positions(bindings):
        with bindings._connect() as db:
            records = db.execute('SELECT d.run_id,d.sequence,f.fact_json FROM scheduler_terminal_deliveries d '
                'JOIN scheduler_progress_facts f USING(instance_id,goal_key,run_id) '
                'WHERE d.instance_id=? AND d.consumed_boundary IS NOT NULL ORDER BY d.sequence', (p.instance,)).fetchall()
        return [(record['run_id'], record['sequence'], json.loads(record['fact_json'])) for record in records]
    expected = positions(p.runtime.scheduler_bindings)
    assert {fact['consumption_sequence'] for _, _, fact in expected} == {1, 2, 3}
    assert all(fact['delivery_sequence'] == sequence for _, sequence, fact in expected)
    objective = ArtifactRef.model_validate_json(row(p)['objective_ref_json'])
    before = p.runtime.scheduler_bindings.progress_shadow(instance_id=p.instance, objective_ref=objective)
    cold = SchedulerBindingService(p.runtime.scheduler_bindings.database_path)
    assert positions(cold) == expected
    assert cold.progress_shadow(instance_id=p.instance, objective_ref=objective) == before
    p.runtime.runs._synchronous_archive_fixture = True
    archive = SynchronousFixtureArchive(p.runtime)
    save_archive(archive, p.instance)
    manifest = archive._manifest(archive._index(p.instance))
    assert manifest['state_format'] == STATE_FORMAT
    assert archive._package_snapshot(archive._index(p.instance), manifest)['state_format'] == STATE_FORMAT
    archived = archive.archived_model(p.instance)
    raw_archive = SimpleNamespace(_connect=lambda: readonly(archive.root / p.instance / 'records' / 'scheduler.sqlite3'))
    assert positions(raw_archive) == expected
    assert archived.bindings.progress_shadow(instance_id=p.instance, objective_ref=objective) == before
    restore_archive(archive, p.instance)
    assert positions(p.runtime.scheduler_bindings) == expected
    assert p.runtime.scheduler_bindings.progress_shadow(instance_id=p.instance, objective_ref=objective) == before


def test_prestart_terminal_history_beyond_detail_capacity_never_counts_as_new_exploration(unmanaged_progression):
    from tests.operations.research_loop_fixtures import authorize_loop
    p = unmanaged_progression
    p.root.call_tool('progression_command', dict(command='takeover'))
    p.root.call_tool('artifact_ingest_text', dict(name='history-revision', text='Retain the exact shared historical evidence.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    p.root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='goal'))
    memory_csv(p, 'prestart-shared', ['goal', 'history-revision'])
    for index in range(22):
        consumed_csv(p, p.root, f'old-background-{index}', 'prestart-shared', deliver=False)
    settings = p.runtime.scheduler_bindings.global_settings
    p.runtime.scheduler_bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist', no_progress_threshold=100, refinement_threshold=100, observation_gap_threshold=100))))
    p.root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    for index in range(22):
        native_delivery(p, root, f'old-background-{index}')
    old = settle(p)['progress_shadow']
    assert old['counts']['consumed_research_tasks'] == 0, old
    assert old['counts']['unverified_progress'] == 0 and row(p)['state'] == 'active'
    root = switch_background_goal(p, 'history-revision')
    native_delivery(p, root, 'old-background-21')
    consumed_csv(p, root, 'new-observed-first', 'prestart-shared')
    assert settle(p)['progress_shadow']['counts']['consumed_research_tasks'] == 1
    root = switch_background_goal(p, 'goal')
    native_delivery(p, root, 'new-observed-first')
    consumed_csv(p, root, 'new-observed-second', 'prestart-shared')
    assert settle(p)['progress_shadow']['counts']['consumed_research_tasks'] == 2
    root = switch_background_goal(p, 'history-revision')
    consumed_csv(p, root, 'new-observed-third', 'prestart-shared')
    assert settle(p)['progress_shadow']['counts']['unverified_progress'] == 3
    assert row(p)['state'] == 'paused'
    with pytest.raises(Exception, match='paused|progress'):
        root.call_tool('operation_invoke', request('after-real-exploration-window'))


@pytest.mark.parametrize('science_progression', [dict(prestart=True)], indirect=True)
def test_background_verified_family_is_known_without_claiming_fresh_progress(science_progression):
    from tests.operations.research_loop_fixtures import authorize_loop
    p = science_progression
    scientific_result(p, p.root, 'old-scientific-solution', controlled=True, deliver=False)
    p.root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    for index in range(3):
        scientific_result(p, root, f'background-family-repeat-{index}', controlled=True)
    status = settle(p)['progress_shadow']
    assert status['counts']['consumed_research_tasks'] == 3, status
    assert status['counts']['unverified_progress'] == 3
    assert row(p)['state'] == 'paused'


@pytest.mark.parametrize('science_progression', [dict(prestart=True, multiple_checks=128),
    dict(prestart=True, multiple_checks=129)], indirect=True)
def test_background_family_budget_retains_exact_128_129_omission(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import background_snapshot
    from scidiscovery.artifact_agent.service.verified_progress import verified_progress
    p = science_progression
    worker, _ = scientific_result(p, p.root, 'old-multiple-checks', controlled=True, deliver=False)
    proof = verified_progress(p.runtime.runs, p.runtime.runs.status(worker._run_id))
    assert proof['status'] == 'verified_test_resolution', proof
    assert len({item['key'] for item in proof['resolutions']}) == p.options['multiple_checks']
    snapshot = background_snapshot(p.runtime.runs, instance_id=p.instance)
    assert len(snapshot['known_resolutions']) == 128
    assert snapshot['candidate_count'] == 1 and snapshot['checked_runs'] == [worker._run_id]
    assert snapshot.get('family_omitted', False) == (p.options['multiple_checks'] > 128), snapshot
    assert snapshot['proof_coverage'] == ('complete' if p.options['multiple_checks'] == 128 else 'bounded_unknown')


@pytest.mark.parametrize('science_progression', [dict(prestart=True, multiple_checks=129)], indirect=True)
def test_background_truncated_old_family_cannot_clear_real_consumption_window(science_progression):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.verified_progress import verified_progress
    from tests.operations.research_loop_fixtures import authorize_loop
    p = science_progression
    old_worker, _ = scientific_result(p, p.root, 'old-129-families', controlled=True, deliver=False)
    old_proof = verified_progress(p.runtime.runs, p.runtime.runs.status(old_worker._run_id))
    assert old_proof['status'] == 'verified_test_resolution' and len(old_proof['resolutions']) == 129, old_proof
    omitted = sorted(old_proof['resolutions'], key=lambda item: item['key'])[-1]
    # The old task is outside this goal's initial brief. Its proof remains in
    # the instance background snapshot, without being redelivered in full.
    p.root.call_tool('artifact_ingest_text', dict(name='current-multiple-check-goal', text='Retain prior checks while confirming this new direction.'))
    p.root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(p.runtime, p.instance, p.user, 'current-multiple-check-goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='current-multiple-check-goal'))
    root = active(p)
    plan = json.loads(p.runtime.artifacts.read(p.artifacts['prestart-plan'].ref))
    checks = [check for dimension in ('numerical', 'physical', 'experimental')
        for check in plan['validation_plans'][0][dimension]['checks'] if check['check_key'] == omitted['check_key']]
    assert len(checks) == 1
    plan['validation_plans'][0]['numerical']['checks'] = checks
    for dimension in ('physical', 'experimental'):
        plan['validation_plans'][0][dimension] = dict(applicability='not_applicable', rationale='No further check.', checks=[])
    goal_ref = p.runtime.artifacts.get_by_id(root.facade._resolve('artifact', 'current-multiple-check-goal')).ref
    p.register('omitted-family-plan', canonical_json(plan), 'scidiscovery.experiment-portfolio.v1', parents=(goal_ref,))
    p.register('omitted-family-conditions', canonical_json(p.contract), 'scidiscovery.curve-experiment-contract.v1',
        parents=(p.artifacts['omitted-family-plan'].ref,))
    p.register('omitted-family-measurement', p.runtime.artifacts.read(p.artifacts['generic_bundle'].ref),
        'scidiscovery.curve-bundle.v1', parents=(p.artifacts['omitted-family-plan'].ref, p.artifacts['omitted-family-conditions'].ref))
    for index in range(3):
        worker, _ = scientific_result(p, root, f'old-truncated-family-repeat-{index}', controlled=True,
            plan_name='omitted-family-plan', condition_name='omitted-family-conditions', bundle_name='omitted-family-measurement')
        proof = verified_progress(p.runtime.runs, p.runtime.runs.status(worker._run_id))
        assert [item['key'] for item in proof['resolutions']] == [omitted['key']], proof
    status = settle(p)['progress_shadow']
    assert status['counts']['consumed_research_tasks'] == 3, status
    assert status['counts']['unverified_progress'] == 3, status
    assert status['background_proof_coverage'] == 'bounded_unknown'
    assert row(p)['state'] == 'paused'


@pytest.mark.parametrize('science_progression', [{}, dict(negative=True)], indirect=True)
def test_threshold_micro_revisions_do_not_renew_exploration_family(science_progression):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'first-threshold-solution', controlled=True)
    for index in range(3):
        plan = json.loads(p.runtime.artifacts.read(p.artifacts['plan'].ref))
        dimension = 'physical' if p.options.get('negative') else 'numerical'
        check = plan['validation_plans'][0][dimension]['checks'][0]
        check['threshold']['value'] += (index+1)*.000001
        contract = deepcopy(p.contract)
        contract['comparison_spec']['comparisons'][0]['operators'][0]['threshold']['value'] = check['threshold']['value']
        p.contract = contract
        plan_name, conditions_name, bundle_name = (f'threshold-{index}-{suffix}' for suffix in ('plan', 'conditions', 'bundle'))
        p.register(plan_name, canonical_json(plan), 'scidiscovery.experiment-portfolio.v1')
        p.register(conditions_name, canonical_json(contract), 'scidiscovery.curve-experiment-contract.v1',
            parents=(p.artifacts[plan_name].ref,))
        p.register(bundle_name, p.runtime.artifacts.read(p.artifacts['generic_bundle'].ref),
            'scidiscovery.curve-bundle.v1', parents=(p.artifacts[plan_name].ref, p.artifacts[conditions_name].ref))
        scientific_result(p, root, f'threshold-repeat-{index}', controlled=True,
            plan_name=plan_name, condition_name=conditions_name, bundle_name=bundle_name)
    status = settle(p)['progress_shadow']
    assert status['counts']['verified_test_resolutions'] == 1, status
    assert status['counts']['unverified_progress'] == 3
    assert row(p)['state'] == 'paused'


def test_new_structured_experimental_condition_can_resolve_a_new_family(science_progression):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    p = science_progression
    root = active(p)
    scientific_result(p, root, 'original-condition', controlled=True)
    scientific_result(p, root, 'unknown-between-conditions')
    plan = json.loads(p.runtime.artifacts.read(p.artifacts['plan'].ref))
    plan['proposals'][0]['changed_factors'] = [dict(name='mesh_level', factor_type='implementation',
        values=[2], unit='level', rationale='A distinct structured implementation condition.')]
    plan['proposals'][0]['cases'][0]['settings'] = [dict(name='mesh_level', value=2, unit='level')]
    p.register('changed-condition-plan', canonical_json(plan), 'scidiscovery.experiment-portfolio.v1')
    p.register('changed-condition-contract', canonical_json(p.contract), 'scidiscovery.curve-experiment-contract.v1',
        parents=(p.artifacts['changed-condition-plan'].ref,))
    p.register('changed-condition-result', p.runtime.artifacts.read(p.artifacts['generic_bundle'].ref),
        'scidiscovery.curve-bundle.v1', parents=(p.artifacts['changed-condition-plan'].ref, p.artifacts['changed-condition-contract'].ref))
    scientific_result(p, root, 'new-condition-resolution', controlled=True, plan_name='changed-condition-plan',
        condition_name='changed-condition-contract', bundle_name='changed-condition-result')
    status = settle(p)['progress_shadow']
    assert status['counts']['verified_test_resolutions'] == 2
    assert status['counts']['unverified_progress'] == 0
    assert row(p)['state'] == 'active'


@pytest.mark.parametrize('science_progression', [dict(prestart=True)], indirect=True)
def test_optional_corrupt_background_proof_does_not_block_first_start(science_progression, monkeypatch):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from tests.operations.research_loop_fixtures import authorize_loop
    p = science_progression
    worker, _ = scientific_result(p, p.root, 'old-unavailable-proof', controlled=True, deliver=False)
    value = p.runtime.runs.status(worker._run_id)
    paired = next(ref for ref in p.runtime.artifacts.catalog(value.output_ref).parent_refs
        if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1')
    read = p.runtime.artifacts.read
    manifest = json.loads(read(paired))
    manifest['records'][0].pop('alias')
    monkeypatch.setattr(p.runtime.artifacts, 'read', lambda ref: canonical_json(manifest) if ref == paired else read(ref))
    p.root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(p.runtime, p.instance, p.user, 'goal')
    p.root.call_tool('progression_command', dict(command='start', mode='background', objective_name='goal'))
    root = active(p)
    assert p.root.call_tool('progression_status', {})['progress_shadow']['background_proof_coverage'] == 'bounded_unknown'
    native_delivery(p, root, 'old-unavailable-proof')
    assert settle(p)['progress_shadow']['counts']['consumed_research_tasks'] == 0


@pytest.mark.parametrize('damage', ['missing_alias', 'missing_attempt', 'duplicate_attempt'])
def test_optional_corrupt_manifest_stays_unknown_without_blocking_real_delivery(science_progression, monkeypatch, damage):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    from scidiscovery.artifact_agent.service.verified_progress import verified_progress
    p = science_progression
    root = active(p)
    worker, _ = scientific_result(p, root, 'corrupt-optional-proof', controlled=True, deliver=False)
    value = p.runtime.runs.status(worker._run_id)
    paired = next(ref for ref in p.runtime.artifacts.catalog(value.output_ref).parent_refs
        if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1')
    read = p.runtime.artifacts.read
    manifest = json.loads(read(paired))
    if damage == 'missing_alias':
        manifest['records'][0].pop('alias')
    elif damage == 'missing_attempt':
        manifest['attempts'] = []
    else:
        manifest['attempts'].append(deepcopy(manifest['attempts'][0]))
    monkeypatch.setattr(p.runtime.artifacts, 'read', lambda ref: canonical_json(manifest) if ref == paired else read(ref))
    proof = verified_progress(p.runtime.runs, value)
    assert proof['status'] == 'unknown' and not proof['resolutions'], proof
    assert terminal_fact(p.runtime.runs, value)['verified_progress']['status'] == 'unknown'
    assert root.call_tool('run_status', dict(name='corrupt-optional-proof', intent='decision'))['state'] == 'completed'
    native_delivery(p, root, 'corrupt-optional-proof')
    after = settle(p)['progress_shadow']
    assert after['counts']['unverified_progress'] == 1 and after['counts']['verified_test_resolutions'] == 0


@pytest.mark.parametrize('science_progression', [{}, dict(qualitative=True)], indirect=True)
@pytest.mark.parametrize('timing', ['strict', 'same_time', 'rollback'])
def test_parent_lineage_sealing_proof_ignores_wall_clock(science_progression, monkeypatch, timing):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service import artifacts as artifact_service
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    clock = ['2030-01-02T00:00:00Z']
    with monkeypatch.context() as patched:
        patched.setattr(artifact_service, '_utc_now', lambda: clock[0])
        p.register('lineage-plan', p.runtime.artifacts.read(p.artifacts['plan'].ref), 'scidiscovery.experiment-portfolio.v1')
        p.register('lineage-conditions', canonical_json(p.contract), 'scidiscovery.curve-experiment-contract.v1',
            parents=(p.artifacts['lineage-plan'].ref,))
        clock[0] = {'strict': '2030-01-03T00:00:00Z', 'same_time': clock[0], 'rollback': '2030-01-01T00:00:00Z'}[timing]
        source = 'generic_results' if p.options.get('qualitative') else 'generic_bundle'
        # Reusing old bytes is permitted: this proves sealing before evaluation,
        # never their original generation time or scientific authenticity.
        original = p.artifacts[source]
        p.register('lineage-observation', p.runtime.artifacts.read(original.ref), original.schema_id,
            parents=(p.artifacts['lineage-plan' if p.options.get('qualitative') else 'lineage-conditions'].ref,))
    root = active(p)
    worker, _ = scientific_result(p, root, 'lineage-subject', controlled=not p.options.get('qualitative'),
        conditions=not p.options.get('qualitative'), plan_name='lineage-plan', condition_name='lineage-conditions',
        bundle_name='generic_bundle' if p.options.get('qualitative') else 'lineage-observation',
        result_name='lineage-observation' if p.options.get('qualitative') else 'generic_results')
    if p.options.get('qualitative'):
        worker = scientific_review(p, root, 'lineage-review', 'lineage-subject')
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof['status'] == 'verified_test_resolution' and proof['resolutions'], proof


@pytest.mark.parametrize('science_progression', [{}, dict(qualitative=True)], indirect=True)
@pytest.mark.parametrize('damage', ['no_path', 'wrong_refs', 'missing_original', 'cycle'])
def test_unproven_exact_lineage_is_unknown_without_blocking_delivery(science_progression, monkeypatch, damage):
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    from scidiscovery.artifact_agent.storage.sqlite import ArtifactRegistryError
    p = science_progression
    source = 'generic_results' if p.options.get('qualitative') else 'generic_bundle'
    original = p.artifacts[source]
    parents = ()
    if damage == 'wrong_refs':
        p.register('other-plan', p.runtime.artifacts.read(p.artifacts['plan'].ref), 'scidiscovery.experiment-portfolio.v1')
        p.register('other-conditions', canonical_json(p.contract), 'scidiscovery.curve-experiment-contract.v1',
            parents=(p.artifacts['other-plan'].ref,))
        parents = (p.artifacts['other-conditions'].ref,)
    elif damage in {'missing_original', 'cycle'}:
        intermediate = p.register('lineage-intermediate', b'An immutable intermediate.', 'opaque',
            parents=(p.artifacts['conditions'].ref,))
        parents = (intermediate.ref,)
    observation = p.register('unproven-observation', p.runtime.artifacts.read(original.ref), original.schema_id, parents=parents)
    root = active(p)
    worker, _ = scientific_result(p, root, 'unproven-subject', controlled=not p.options.get('qualitative'), deliver=False,
        bundle_name='generic_bundle' if p.options.get('qualitative') else 'unproven-observation',
        result_name='unproven-observation' if p.options.get('qualitative') else 'generic_results')
    if p.options.get('qualitative'):
        worker = scientific_review(p, root, 'unproven-review', 'unproven-subject')
    catalog = p.runtime.artifacts.catalog
    def damaged_catalog(ref):
        if damage in {'missing_original', 'cycle'} and ref == intermediate.ref:
            if damage == 'missing_original':
                raise ArtifactRegistryError('Original lineage record is unavailable.')
            return catalog(ref).model_copy(update={'parent_refs': (observation.ref,)})
        return catalog(ref)
    with monkeypatch.context() as patched:
        patched.setattr(p.runtime.artifacts, 'catalog', damaged_catalog)
        proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof['status'] == 'unknown' and not proof['resolutions'], proof
    assert proof['reason'] == {'no_path': 'sealing_order_unproven', 'wrong_refs': 'sealing_order_unproven',
        'missing_original': 'sealing_order_original_unavailable_or_inconsistent', 'cycle': 'sealing_order_lineage_inconsistent'}[damage], proof
    assert p.runtime.runs.status(worker._run_id).state == 'completed'


@pytest.mark.parametrize('science_progression', [{}, dict(qualitative=True)], indirect=True)
@pytest.mark.parametrize('depth', [61, 62])
def test_exact_lineage_budget_keeps_omission_unknown(science_progression, depth):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    parent = p.artifacts['conditions'].ref
    for index in range(depth):
        parent = p.register(f'lineage-hop-{index}', b'Finite ancestry.', 'opaque', parents=(parent,)).ref
    source = 'generic_results' if p.options.get('qualitative') else 'generic_bundle'
    original = p.artifacts[source]
    p.register('bounded-observation', p.runtime.artifacts.read(original.ref), original.schema_id, parents=(parent,))
    root = active(p)
    worker, _ = scientific_result(p, root, 'bounded-subject', controlled=not p.options.get('qualitative'),
        bundle_name='generic_bundle' if p.options.get('qualitative') else 'bounded-observation',
        result_name='bounded-observation' if p.options.get('qualitative') else 'generic_results')
    if p.options.get('qualitative'):
        worker = scientific_review(p, root, 'bounded-review', 'bounded-subject')
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof['status'] == ('verified_test_resolution' if depth == 61 else 'unknown'), proof
    if depth == 62:
        assert proof['reason'] == 'sealing_order_proof_omitted', proof


def test_quantitative_conditions_must_be_exact_observation_ancestors(science_progression):
    from scidiscovery.artifact_agent.service.scientific_progress import terminal_fact
    p = science_progression
    p.register('plan-only-measurement', p.runtime.artifacts.read(p.artifacts['generic_bundle'].ref),
        'scidiscovery.curve-bundle.v1', parents=(p.artifacts['plan'].ref,))
    worker, _ = scientific_result(p, active(p), 'conditions-unproven', controlled=True, bundle_name='plan-only-measurement')
    proof = terminal_fact(p.runtime.runs, p.runtime.runs.status(worker._run_id))['verified_progress']
    assert proof['status'] == 'unknown' and proof['reason'] == 'sealing_order_unproven', proof


def test_source_is_not_its_own_prior_sealed_ancestor(science_progression):
    from scidiscovery.artifact_agent.service.verified_progress import _prior_sealed_sources
    p = science_progression
    ref = p.artifacts['plan'].ref
    assert _prior_sealed_sources(p.runtime.runs.artifacts, (ref,), (ref,)) == 'sealing_order_unproven'
    limitations = p.root.call_tool('progression_status', {})['progress_shadow']['limitations']
    assert any('64 distinct original envelopes' in item and 'do not prove original generation time' in item for item in limitations)
