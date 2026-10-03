"""Sealed evidence -> actual consumption -> the existing dispatch guard."""
import json
from copy import copy, deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.operations.test_progression import progression, row
from tests.operations.test_progress_assist import configure, next_turn
from tests.operations.test_progress_shadow import native_delivery
from tests.operations.test_scientific_progress import active, request, assess, INTENT
from tests.operations.test_local_worker_contracts import _worker, _write_result
from tests.operations.test_human_progress_continuation import paused, human_ui, submit


@pytest.fixture
def science_progression(tmp_path, request):
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
    settings = runtime.scheduler_bindings.global_settings
    runtime.scheduler_bindings.global_settings = settings.model_copy(update=dict(progression=settings.progression.model_copy(
        update=dict(progress_mode='assist', no_progress_threshold=100, refinement_threshold=100, observation_gap_threshold=100))))
    contract = curve._contract().model_dump(mode='json')
    if options.get('negative'):
        contract['comparison_spec']['comparisons'][0]['gate_scope'] = 'objective'
    if not options.get('posthoc'):
        register('conditions', canonical_json(contract), 'scidiscovery.curve-experiment-contract.v1', parents=(artifacts['plan'].ref,))
    bundle = curve._bundle().model_dump(mode='json')
    if not options.get('negative'):
        bundle['series'][1]['points'] = deepcopy(bundle['series'][0]['points'])
    register('generic_results', b'Exact later bounded observation.', 'opaque', parents=(artifacts['plan'].ref,))
    register('generic_bundle', canonical_json(bundle), 'scidiscovery.curve-bundle.v1', parents=(artifacts['plan'].ref,))
    if options.get('posthoc'):
        register('conditions', canonical_json(contract), 'scidiscovery.curve-experiment-contract.v1', parents=(artifacts['plan'].ref,))
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


def scientific_result(p, root, name, *, controlled=False, conditions=True, scope_mismatch=False,
                      plan_name='plan', condition_name='conditions', bundle_name='generic_bundle'):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from tests.operations.test_result_analysis_tool import score_inputs
    from tests.operations import test_m2_curve_analysis_boundary as curve
    inputs = [dict(port='experiment_plan', artifact_names=[plan_name]),
        dict(port='experiment_results', artifact_names=['generic_results']), dict(port='curve_bundle', artifact_names=[bundle_name])]
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
        'scidiscovery.curve-bundle.v1', parents=(p.artifacts['reworded-plan'].ref,))
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
