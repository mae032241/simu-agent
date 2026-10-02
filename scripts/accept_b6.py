"""Serial B6 acceptance: init, prepare CASE, run CASE, report, review CASE.

No implicit run-all, submission retry, instance selection or production install.
Run native cases from an ordinary terminal. Report/status never launch a model.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from scidiscovery.agent_execution_settings import ProgressionSettings, effective_settings, parse_settings

try:
    from scripts.run_tests import serial_lock
    from scripts.b6_evidence import read, write, digest, rows, control_rows, run_snapshot, participants, sealed_outputs, usage_report, verdict, compare, assess, token_totals, budget_assessment
    from scripts.root_host_upgrade import _files
    from scripts import s0_scoring
except ModuleNotFoundError:
    from run_tests import serial_lock
    from b6_evidence import read, write, digest, rows, control_rows, run_snapshot, participants, sealed_outputs, usage_report, verdict, compare, assess, token_totals, budget_assessment
    from root_host_upgrade import _files
    import s0_scoring

SCRIPTS = Path(__file__).resolve().parent
DEFAULT = SCRIPTS/'acceptance/b6.json'


def configuration(path):
    value=read(path)
    if value['version']!=1 or not value['instance']:
        raise ValueError('unsupported_acceptance_config')
    ProgressionSettings.model_validate(value['progression'])
    for case in value['cases'].values():
        ProgressionSettings.model_validate({**value['progression'], **case.get('progression', {})})
    for group in ('resources','managed'):
        if any(type(v) is not int or v<=0 for v in value[group].values()):
            raise ValueError('positive_integer_limits_required')
    for key in ('poll_seconds','stage_timeout_seconds','max_observed_runs'):
        if type(value[key]) not in (int,float) or not 0<value[key]<float('inf'):
            raise ValueError('positive_limits_required')
    if type(value.get('human_wait_seconds')) is not int or value['human_wait_seconds'] <= 0:
        raise ValueError('explicit_human_wait_budget_required')
    allowed={'recovery','authority','helper','helper-crash','manual','autonomous'}
    for key, case in value['cases'].items():
        if not re.fullmatch(r'[a-z][a-z0-9-]*',key) or case['runner'] not in {'native','managed'}:
            raise ValueError('invalid_case')
        if case['runner']=='native' and case['scenario'] not in allowed:
            raise ValueError('unknown_native_scenario')
        if not case['requires'] or ('objective' in case and case['objective'] not in value['objectives']):
            raise ValueError('case_contract_incomplete')
    budget = value.get('budget')
    if budget:
        for group in ('suite', 'session'):
            for key in ('total_tokens', 'uncached_tokens', 'execution_seconds'):
                number = budget[group][key]
                if type(number) is not int or number <= 0:
                    raise ValueError('positive_acceptance_budget_required')
                if budget['session'][key] > budget['suite'][key]:
                    raise ValueError('session_exceeds_suite_budget')
        for key in ('sample_seconds', 'human_review_hours'):
            if type(budget[key]) not in (int, float) or not 0 < budget[key] < float('inf'):
                raise ValueError('positive_acceptance_budget_required')
    return value


def prior_costs(paths):
    """Freeze observed costs of earlier suites without importing their outcomes."""
    records, seen = [], set()
    for path in paths:
        path = path.resolve()
        report = read(path)
        identity = report.get('evidence')
        if not identity or report.get('status') not in {'failed', 'passed', 'not_observed'}:
            raise ValueError('prior_result_requires_terminal_evidence')
        identity = str(Path(identity).resolve())
        if identity in seen:
            raise ValueError('duplicate_prior_attempt')
        seen.add(identity)
        costs = token_totals(report.get('usage', {}))
        seconds = (report.get('resource') or {}).get('elapsed_seconds')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('acceptance_execution_time_missing')
        records.append(dict(source=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            evidence=identity, costs={**costs, 'execution_seconds':seconds}))
    return records


def budget_admission(root, manifest):
    """Reserve one full session; every previous attempt, including failure, counts."""
    budget = manifest.get('config', {}).get('budget')
    if not budget:
        return None
    spent = dict(total_tokens=0, uncached_tokens=0, execution_seconds=0)
    for prior in manifest.get('prior_attempt_costs', []):
        for key in spent:
            spent[key] += prior['costs'][key]
    for case_id in manifest['config']['cases']:
        if not (root/(case_id+'.attempt.json')).exists():
            continue
        if not (root/(case_id+'.exit.json')).exists():
            raise ValueError('prior_attempt_outcome_unknown')
        report = result(root, manifest, case_id)
        started = (root/case_id/'model-submission-started').exists()
        if not started:
            # A failed pre-model start has no model spend. Resource evidence is
            # still charged when present, rather than silently deleting retries.
            seconds = report.get('resource', {}).get('elapsed_seconds', 0)
        else:
            totals = token_totals(report.get('usage', {}))
            for key, number in totals.items():
                spent[key] += number
            seconds = report.get('resource', {}).get('elapsed_seconds')
            if type(seconds) not in (float, int) or seconds < 0 or not math.isfinite(seconds):
                raise ValueError('acceptance_execution_time_missing')
        spent['execution_seconds'] += seconds
    remaining = {key: budget['suite'][key] - spent[key] for key in spent}
    if any(remaining[key] < budget['session'][key] for key in spent):
        raise ValueError('acceptance_suite_budget_insufficient')
    return dict(spent=spent, remaining=remaining, reservation=budget['session'])


def exclusive_intent(path, value):
    # The record precedes subprocess creation. A crash leaves an explicit unknown
    # attempt; report cannot silently turn that into a fresh submission.
    with path.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False)
        stream.flush();os.fsync(stream.fileno())


def harness_digest():
    return digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*SCRIPTS.glob('*.py'), SCRIPTS/'test_resources.json', SCRIPTS/'root_host_resources.json'])})


def installed_contract(program, settings_file=None, instance_settings=None):
    """Check the actual installed interpreter's schema/config API without a host."""
    code=('import json,sys;from scidiscovery.agent_execution_settings import ProgressionSettings,load_settings,effective_settings;'
        'from scidiscovery.artifact_agent.service.scheduling_control import CONTROL_VERSION;'
        'value=dict(control_schema=CONTROL_VERSION,progression_fields=sorted(ProgressionSettings.model_fields));'
        'value.update(effective_settings=effective_settings(load_settings(sys.argv[1]),json.loads(sys.argv[2]))) if len(sys.argv)>1 else None;'
        'print(json.dumps(value))')
    arguments=[str(settings_file),json.dumps(instance_settings or {})] if settings_file else []
    value=json.loads(subprocess.check_output([program['python'],'-I','-c',code,*arguments],
        cwd=program['project'],text=True,timeout=15))
    if value['control_schema'] != 9:
        raise ValueError('installed_candidate_requires_control_schema_9')
    return value


def initialize(root, config, source, installed, previous, prior_results=()):
    settings=configuration(config)
    if root.exists():raise ValueError('suite_already_exists')
    source,installed=source.resolve(),installed.resolve()
    if any(root==v or root.is_relative_to(v) or v.is_relative_to(root) for v in (source,installed)):
        raise ValueError('suite_must_be_separate_from_source_and_installation')
    original=read(source/'candidate.json'); program=read(installed/'candidate.json')
    try:
        from scripts.accept_progression import require_existing_instance, platform_identity
    except ModuleNotFoundError:
        from accept_progression import require_existing_instance, platform_identity
    require_existing_instance(source)
    expected=settings.get('benchmark', {}).get('candidate_source_commit')
    if expected and program.get('head') != expected:
        raise ValueError('candidate_source_revision_mismatch')
    if not program.get('wheels') or not program.get('profile',{}).get('model'):
        raise ValueError('installed_wheels_and_explicit_model_required_for_comparison')
    contract=installed_contract(program)
    if set(settings['progression'])-set(contract['progression_fields']):
        raise ValueError('installed_candidate_missing_acceptance_settings')
    matches=rows(source,'scheduler-bindings','SELECT instance_id FROM scheduler_instances WHERE name=?',(settings['instance'],))
    if len(matches)!=1 and rows(source,'scheduler-bindings','SELECT instance_id FROM scheduler_instances LIMIT 1'):
        raise ValueError('existing_instance_not_found; create_exact_instance_in_management_ui')
    control=control_rows(source)
    if control:
        raise ValueError('use_fresh_pre_progression_source; retain_existing_control_and_spent_budget')
    if any(v['state'] not in {'completed','failed'} for v in run_snapshot(source)):
        raise ValueError('source_has_unfinished_runs')
    carried = prior_costs(prior_results)
    frozen=dict(prior_attempt_costs=carried, source=str(source),installed=str(installed),previous=str(previous.resolve()) if previous else None,
        config=settings,harness_digest=harness_digest(),
        freeze_identity=dict(candidate_source_commit=program['head'], state_source_commit=original['head'],
            control_schema=9, runner_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SCRIPTS.parent,text=True).strip(),
            runner_digest=harness_digest(), platform=platform_identity(),
            installed_contract=contract,
            status='source_frozen_live_baseline_pending'),
        baseline_digest=digest(dict(state=_files(source/'state'),project=_files(Path(original['project']),project=True))),
        conditions_digest=digest(dict(program=program,settings=read(source/'agent-settings.json'),config=settings)),
        installed_config_digest=digest(program),source_settings_digest=digest(read(source/'agent-settings.json')))
    root.mkdir(mode=0o700,parents=True)
    write(root/'suite.json',frozen)


def prepare(root, manifest, case_id):
    case=manifest['config']['cases'][case_id]
    target=root/case_id
    source=Path(manifest['source']);installed=Path(manifest['installed'])
    if case_id=='rollback':
        if not manifest['previous']:raise ValueError('rollback_requires_previous_installed_candidate')
        if result(root,manifest,'managed')['status']!='passed':raise ValueError('run_managed_case_before_rollback')
        source=root/'managed';installed=Path(manifest['previous'])
        if read(installed/'candidate.json').get('wheels')==read(Path(manifest['installed'])/'candidate.json').get('wheels'):
            raise ValueError('rollback_requires_different_previous_build')
    elif digest(read(installed/'candidate.json'))!=manifest['installed_config_digest']:
        raise ValueError('installed_configuration_changed')
    identity=dict(manifest['freeze_identity'])
    conditions=manifest['conditions_digest']
    if case_id=='rollback':
        program=read(installed/'candidate.json')
        contract=installed_contract(program)
        identity.update(candidate_source_commit=program['head'],
            state_source_commit=read(source/'candidate.json')['head'],
            control_schema=contract['control_schema'],installed_contract=contract)
        conditions=digest(dict(program=program,settings=read(source/'agent-settings.json'),config=manifest['config']))
    exclusive_intent(root/(case_id+'.prepare.json'),dict(started_ns=time.time_ns(),source=str(source),installed=str(installed)))
    command=[sys.executable,str(SCRIPTS/'probe_root_host_live.py'),'prepare-upgrade',
        '--candidate',str(target),'--from-candidate',str(source),'--installed-candidate',str(installed)]
    completed=subprocess.run(command,check=False)
    if completed.returncode:raise RuntimeError('prepare_failed; preserve_candidate_for_diagnosis')
    snapshot=read(target/'state-snapshot.json')
    baseline=digest(dict(state=snapshot['state_files'],project=snapshot['project_files']))
    if case_id!='rollback' and baseline!=manifest['baseline_digest']:
        raise ValueError('source_changed_since_suite_init')
    config=manifest['config']
    frozen={**{k:v for k,v in config.items() if k not in {'cases','objectives','quality','auto_checks','grading'}},**case,
        'text':config['objectives'].get(case.get('objective'),''),
        'baseline_digest':baseline,'conditions_digest':conditions,
        'freeze_identity':identity}
    frozen['progression']={**config['progression'], **case.get('progression', {})}
    source_settings=read(target/'agent-settings.json')
    if digest(source_settings)!=manifest['source_settings_digest'] and case_id!='rollback':
        raise ValueError('source_settings_changed')
    source_settings['progression']={**source_settings.get('progression', {}), **frozen['progression']}
    global_settings=parse_settings(source_settings)
    source_settings=global_settings.model_dump(exclude_none=True)
    write(target/'agent-settings.json',source_settings)
    instance=rows(target,'scheduler-bindings','SELECT agent_settings_json FROM scheduler_instances WHERE name=?',(config['instance'],))
    instance_settings=json.loads(instance[0]['agent_settings_json'] or '{}') if instance else {}
    effective=effective_settings(global_settings,instance_settings)
    actual=installed_contract(read(target/'candidate.json'),target/'agent-settings.json',instance_settings)
    if case_id=='rollback' and (read(target/'candidate.json')['head'] != identity['candidate_source_commit']
            or {k:v for k,v in actual.items() if k!='effective_settings'} != identity['installed_contract']):
        raise ValueError('rollback_installed_identity_changed')
    if actual['effective_settings'] != effective:
        raise ValueError('installed_effective_settings_mismatch')
    if any(effective['progression'][key]!=value for key,value in frozen['progression'].items()):
        raise ValueError('instance_override_conflicts_acceptance_budget')
    frozen.update(effective_settings=effective, agent_settings_digest=digest(source_settings),
        candidate_digest=digest(read(target/'candidate.json')))
    write(target/'acceptance-case.json',frozen)
    write(root/(case_id+'.prepared.json'),dict(case_digest=digest(frozen)))
    resources=read(SCRIPTS/'root_host_resources.json')
    resources['instance_wait_timeout_seconds']=config['human_wait_seconds']
    resources['execution_timeout_seconds']=config['resources']['timeout_seconds']
    if config.get('budget'):
        resources['execution_timeout_seconds'] = min(resources['execution_timeout_seconds'],
            config['budget']['session']['execution_seconds'])
    write(target/'host-resources.json',resources)
    print('已准备：'+str(target)+'。run 将先输出本候选精确管理 URL；仅用户页面选择/创建实例、暂停 bootstrap 并确认本场 loop 预算后才请求模型。',flush=True)


def run(root,manifest,case_id):
    target=root/case_id;case=read(target/'acceptance-case.json')
    if manifest['harness_digest']!=harness_digest():raise ValueError('harness_changed; create_new_suite_with_prior_evidence_retained')
    if digest(case)!=read(root/(case_id+'.prepared.json'))['case_digest']:
        raise ValueError('prepared_case_changed')
    command=[sys.executable,str(SCRIPTS/'accept_progression.py'),'--candidate',str(target),
        '--scenario',case.get('scenario','managed'),'--case-file',str(target/'acceptance-case.json')]
    with serial_lock() as lock:
        # Only an admitted start consumes the one-shot intent. The child inherits
        # this exact lock, so there is no release/reacquire race before launch.
        allowance = budget_admission(root, manifest)
        exclusive_intent(root/(case_id+'.attempt.json'),dict(started_ns=time.time_ns(),case_digest=digest(case), budget=allowance))
        completed=subprocess.run([*command,'--lock-fd',str(lock.fileno())],check=False,
            pass_fds=(lock.fileno(),))
    write(root/(case_id+'.exit.json'),dict(returncode=completed.returncode,ended_ns=time.time_ns()))
    report=result(root,manifest,case_id)
    write(root/(case_id+'.result.json'),report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return completed.returncode


def resume_wait(root,manifest,case_id,evidence,human_wait_seconds=None):
    """One explicit linked recovery of a confirmed pre-model human timeout."""
    try:
        from scripts.accept_progression import wait_source,file_hash
    except ModuleNotFoundError:
        from accept_progression import wait_source,file_hash
    target=(root/case_id).resolve();evidence=evidence.resolve()
    case=read(target/'acceptance-case.json')
    human_wait_seconds=human_wait_seconds if human_wait_seconds is not None else case['human_wait_seconds']
    if type(human_wait_seconds) is not int or human_wait_seconds<=0:
        raise ValueError('positive_human_wait_seconds_required')
    if digest(case)!=read(root/(case_id+'.prepared.json'))['case_digest']:
        raise ValueError('prepared_case_changed')
    with serial_lock() as lock:
        source=wait_source(target,case,evidence)
        if sorted(target.glob('journey-*'))!=[evidence]:
            raise ValueError('wait_resume_requires_one_exact_original_attempt')
        paths=[root/'suite.json',root/(case_id+'.attempt.json'),root/(case_id+'.exit.json'),root/(case_id+'.result.json'),
            root/(case_id+'.prepared.json'),target/'candidate.json',target/'agent-settings.json',
            target/'acceptance-case.json',target/'host-resources.json',
            *[evidence/name for name in ('summary.json','resource.json','thread.json','usage.json','started-threads.json')]]
        if read(root/(case_id+'.exit.json')).get('returncode')!=1:
            raise ValueError('wait_resume_original_exit_not_confirmed')
        allowance=budget_admission(root,manifest)
        link=root/(case_id+'.resume-wait.json')
        exclusive_intent(link,dict(kind='confirmed_pre_model_wait_timeout',native_session_policy='new_thread_start; old_identity_is_evidence_only',case_digest=digest(case),
            prior_evidence=str(evidence),source=source,prior_files={str(path):file_hash(path) for path in paths},
            prior_progress=read(target/'progress.json'),human_wait_seconds=human_wait_seconds,
            human_poll_seconds=case['effective_settings']['progression']['poll_seconds'],
            budget=allowance,
            output=str(target/('wait-resume-'+str(time.time_ns()))),
            original_harness_digest=manifest['harness_digest'],original_freeze_identity=case['freeze_identity'],
            runner_digest=harness_digest(),runner_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SCRIPTS.parent,text=True).strip()))
        command=[sys.executable,str(SCRIPTS/'accept_progression.py'),'--candidate',str(target),
            '--scenario',case['scenario'],'--case-file',str(target/'acceptance-case.json'),
            '--resume-wait',str(link),'--lock-fd',str(lock.fileno())]
        completed=subprocess.run(command,check=False,pass_fds=(lock.fileno(),))
        exclusive_intent(root/(case_id+'.resume-wait.exit.json'),dict(returncode=completed.returncode,ended_ns=time.time_ns()))
    report=result(root,manifest,case_id)
    write(root/(case_id+'.resume-wait.result.json'),report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return completed.returncode


def result(root,manifest,case_id):
    contract=manifest['config']['cases'][case_id]; target=root/case_id
    checks={}; output=dict(case=case_id,checks=checks,status='not_observed')
    case_file=target/'acceptance-case.json'
    identity=read(case_file) if case_file.exists() else manifest
    output.update({k:identity[k] for k in ('freeze_identity','baseline_digest','conditions_digest') if k in identity})
    journeys=sorted(target.glob('journey-*'))
    link=root/(case_id+'.resume-wait.json')
    if link.exists():
        try:
            from scripts.accept_progression import wait_link
        except ModuleNotFoundError:
            from accept_progression import wait_link
        recovery=wait_link(target,read(case_file),link)
        journeys=[Path(recovery['output'])] if Path(recovery['output']).is_dir() else []
        output['wait_resume']={k:recovery[k] for k in ('prior_evidence','output','native_session_policy','human_wait_seconds','human_poll_seconds',
            'original_harness_digest','runner_digest','runner_source_commit')}
        output['original_wait_failure']='instance_wait_timeout; retained separately'
    elif len(journeys)>1:raise ValueError('multiple_attempts_require_separate_accounting')
    if not journeys:
        if case_id=='rollback' and not manifest.get('previous'):
            output.update(status='blocked',blockers=['previous_installed_candidate_missing'])
        startup=target/'startup-check.json'
        if startup.exists() and read(startup).get('blockers'):
            output['status']='blocked'
            output['blockers']=read(startup)['blockers']
        output['attempt']='outcome_unknown' if (root/(case_id+'.attempt.json')).exists() else 'not_started'
        return output
    journey=journeys[0]
    summary=read(journey/'summary.json') if (journey/'summary.json').exists() else {}
    checks.update(summary.get('checks',{}))
    output.update(evidence=str(journey),execution_status=summary.get('status','outcome_unknown'))
    if summary.get('status') in {'failed','incomplete'}:
        checks['execution']='failed'
    resource=read(journey/'resource.json') if (journey/'resource.json').exists() else {}
    exit_file=root/(case_id+('.resume-wait.exit.json' if link.exists() else '.exit.json'))
    closed=read(exit_file) if exit_file.exists() else {}
    if resource.get('stop_reason') not in {None,'exited'} or resource.get('returncode') not in {None,0} or closed.get('returncode') not in {None,0}:
        checks['execution']='failed'
    if 'execution' not in checks:
        checks['execution']='passed' if resource.get('returncode')==0 and closed.get('returncode')==0 else 'not_observed'
    output['resource']=resource
    if manifest.get('freeze_identity'):
        execution=read(journey/'execution-time.json') if (journey/'execution-time.json').exists() else {}
        resource=dict(resource, supervisor_elapsed_seconds=resource.get('elapsed_seconds'),
            elapsed_seconds=execution.get('elapsed_seconds') if (target/'model-submission-started').exists() else 0)
        output['resource']=resource
    frozen=read(target/'acceptance-case.json')
    output.update({k:frozen[k] for k in ('baseline_digest','conditions_digest')})
    output['freeze_identity']=frozen.get('freeze_identity', {'status':'historical_unfrozen'})
    output['loop_authorization']=read(journey/'loop-authorization.json') if (journey/'loop-authorization.json').exists() else None
    output['objective_digest']=digest(frozen['text'])
    before=read(journey/'before-runs.json') if (journey/'before-runs.json').exists() else run_snapshot(target)
    previous_ids={v['run_id'] for v in before}
    new=[v for v in run_snapshot(target) if v['run_id'] not in previous_ids]
    workers,helpers=participants(target,[v['run_id'] for v in new])
    control=control_rows(target,'SELECT p.* FROM scheduler_progression p JOIN scheduler_instances i ON i.instance_id=p.instance_id WHERE i.name=?',
        (manifest['config']['instance'],), accounting=True,
        loop_id=(output['loop_authorization'] or {}).get('id'))
    progression=control[0] if control and control[0].get('checkpoint_json') and json.loads(control[0]['checkpoint_json']).get('started_at') else None
    output['usage']=usage_report(journey,workers,helpers,progression)
    if (target/'model-submission-started').exists() and not output['usage']['groups']:
        output['usage']['coverage']='partial'
    if frozen.get('budget') and (target/'model-submission-started').exists():
        final_path = journey/'budget-final.json'
        seconds = read(final_path).get('observed', {}).get('execution_seconds') if final_path.exists() else None
        output['budget'] = budget_assessment(output['usage'], frozen['budget']['session'], seconds)
        # A bounded stop is decisive even when final native telemetry is partial.
        terminal_path = journey/'terminal-control.json'
        if terminal_path.exists():
            terminal = read(terminal_path)
            output['stop_reason'] = terminal.get('reason')
            if terminal.get('reason') == 'budget_exhausted':
                output['budget']['status'] = 'failed'
        checks['budget'] = output['budget']['status']
        if checks['budget'] == 'failed':
            checks['execution'] = 'failed'
    evidence_path=journey/'sealed-evidence.json'
    if evidence_path.exists():
        evidence=sealed_outputs(target,new)
        if evidence!=read(evidence_path):raise ValueError('sealed_evidence_changed')
        rubric=manifest['config']['quality'][contract['objective']]
        objective = contract['objective'] if manifest['config'].get('grading', {}).get('format') == 's0-v1' else None
        review_evidence = evidence
        if objective:
            adoption_path = root/(case_id+'.adoption.json')
            details = s0_scoring.run_details(target, [v['run_id'] for v in new])
            review_evidence = s0_scoring.collect(target, journey, evidence, details, before, progression,
                read(adoption_path) if adoption_path.exists() else None)
            output['scoring_evidence'] = review_evidence
            output['auto_checks'] = s0_scoring.auto_checks(review_evidence, objective)
            checks['auto_quality'] = 'not_observed'
            output['qualification'] = dict(science='not_observed', cross_task='not_observed',
                root_scheduling='not_observed', overall='not_observed')
            output['adoption_template'] = dict(evidence_digest=digest(evidence), run_ids=[], root_record_digest='',
                root_excerpt='', reason='', scope='Optional local reviewer interpretation of an existing Root conclusion; never a production adoption.')
        output['review_template']=dict(evidence_digest=digest(review_evidence),rubric=rubric,reviewer='',
            decisions=[dict(status='not_observed',reason='', **({'score':None} if objective else {})) for _ in rubric])
        review_path=root/(case_id+'.review.json')
        if review_path.exists():
            review = read(review_path)
            quality=assess(review_evidence,rubric,review,objective=objective)
            if objective:
                output['qualification'] = s0_scoring.assess_domains(review_evidence, review, objective)
            checks['owner_integration' if case_id.startswith('helper') else 'quality']=quality
    if case_id=='rollback' and all(checks.get(k)=='passed' for k in ('terminal_independence','service_restart','state_preserved')):
        checks['rollback']='passed'  # Isolated old build reads state after new build startup.
    output['status']=verdict(checks,[*contract['requires'],'execution', *(['budget'] if 'budget' in checks else [])])
    output['scope']='isolated installed candidates; formal installation, live TCAD and detached native resource coverage remain unqualified'
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('init','prepare','run','resume-wait','report','review','package'))
    parser.add_argument('case',nargs='?')
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=DEFAULT)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--installed',type=Path)
    parser.add_argument('--previous-installed',type=Path)
    parser.add_argument('--prior-result',type=Path,action='append',default=[],
        help='Charge a previous observed attempt against this suite budget; repeatable')
    parser.add_argument('--from-evidence',type=Path,help='exact confirmed pre-model wait timeout directory; resume-wait only')
    parser.add_argument('--human-wait-seconds',type=int,help='explicit recovery-only human window; scientific budget unchanged')
    parser.add_argument('--review-file',type=Path)
    args=parser.parse_args();os.umask(0o077);root=args.suite.resolve()
    if args.action=='init':
        if not args.source or not args.installed:parser.error('init requires --source and --installed')
        initialize(root,args.config,args.source,args.installed,args.previous_installed,args.prior_result);return 0
    manifest=read(root/'suite.json')
    if args.action=='package':
        if manifest['config'].get('grading', {}).get('format') != 's0-v1':
            raise ValueError('package_requires_s0_grading')
        with (root/'suite.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            reports={k:result(root,manifest,k) for k in manifest['config']['cases']}
            batch=s0_scoring.package(root,manifest,reports)
        print(json.dumps(batch,ensure_ascii=False,indent=2));return 0
    if args.action=='report':
        cases={k:result(root,manifest,k) for k in manifest['config']['cases']}
        pairs={}
        for pair in sorted({c['pair'] for c in manifest['config']['cases'].values() if 'pair' in c}):
            pairs[pair]=compare(cases['manual-'+pair],cases['auto-'+pair])
        print(json.dumps(dict(cases=cases,comparisons=pairs,b6_passed=False,
            remaining=['formal deployment rollback','detached native process resource coverage','A6 TCAD deferred']),ensure_ascii=False,indent=2));return 0
    if args.case not in manifest['config']['cases']:parser.error('choose a configured case')
    with (root/'suite.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare(root,manifest,args.case)
        elif args.action=='run':return run(root,manifest,args.case)
        elif args.action=='resume-wait':
            if not args.from_evidence:parser.error('resume-wait requires --from-evidence')
            try:return resume_wait(root,manifest,args.case,args.from_evidence,args.human_wait_seconds)
            except (ValueError,FileNotFoundError) as error:
                write(root/args.case/'progress.json',dict(state='wait_resume_refused',diagnostic=str(error),model_requests='not_requested'))
                raise
        else:
            if not args.review_file:parser.error('review requires --review-file')
            current=result(root,manifest,args.case);template=current.get('review_template')
            if not template:raise ValueError('no_sealed_output_to_review')
            review=read(args.review_file)
            # Digest/rubric binding validated before writing the immutable review.
            objective = manifest['config']['cases'][args.case]['objective'] if current.get('scoring_evidence') else None
            bound_evidence = current.get('scoring_evidence', read(Path(current['evidence'])/'sealed-evidence.json'))
            assess(bound_evidence,template['rubric'],review,objective=objective)
            if review.get('blind'):
                s0_scoring.validate_blind_review(root,args.case,review)
            exclusive_intent(root/(args.case+'.review.json'),review)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except BlockingIOError:
        print('serial_lock_busy: another serial task is running; no new attempt was started. Retry this command after it finishes.',file=sys.stderr)
        raise SystemExit(75)
    except (ValueError,RuntimeError,FileExistsError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(2)
