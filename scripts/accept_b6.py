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

try:
    from scripts.run_tests import serial_lock
    from scripts.b6_evidence import read, write, digest, rows, control_rows, run_snapshot, participants, sealed_outputs, usage_report, verdict, compare, assess, token_totals
    from scripts.root_host_upgrade import _files
except ModuleNotFoundError:
    from run_tests import serial_lock
    from b6_evidence import read, write, digest, rows, control_rows, run_snapshot, participants, sealed_outputs, usage_report, verdict, compare, assess, token_totals
    from root_host_upgrade import _files

SCRIPTS = Path(__file__).resolve().parent
DEFAULT = SCRIPTS/'acceptance/b6.json'


def configuration(path):
    value=read(path)
    if value['version']!=1 or not value['instance']:
        raise ValueError('unsupported_acceptance_config')
    for group in ('progression','resources','managed'):
        if any(type(v) is not int or v<=0 for v in value[group].values()):
            raise ValueError('positive_integer_limits_required')
    for key in ('poll_seconds','stage_timeout_seconds','max_observed_runs'):
        if type(value[key]) not in (int,float) or not 0<value[key]<float('inf'):
            raise ValueError('positive_limits_required')
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


def budget_admission(root, manifest):
    """Reserve one full session; every previous attempt, including failure, counts."""
    budget = manifest.get('config', {}).get('budget')
    if not budget:
        return None
    spent = dict(total_tokens=0, uncached_tokens=0, execution_seconds=0)
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


def initialize(root, config, source, installed, previous):
    settings=configuration(config)
    if root.exists():raise ValueError('suite_already_exists')
    source,installed=source.resolve(),installed.resolve()
    if any(root==v or root.is_relative_to(v) or v.is_relative_to(root) for v in (source,installed)):
        raise ValueError('suite_must_be_separate_from_source_and_installation')
    original=read(source/'candidate.json'); program=read(installed/'candidate.json')
    if not program.get('wheels') or not program.get('profile',{}).get('model'):
        raise ValueError('installed_wheels_and_explicit_model_required_for_comparison')
    matches=rows(source,'scheduler-bindings','SELECT instance_id FROM scheduler_instances WHERE name=?',(settings['instance'],))
    if len(matches)!=1:raise ValueError('existing_instance_not_found')
    control=control_rows(source)
    if any(v['host_json'] or v['state'] in {'active','pending'} or json.loads(v['checkpoint_json']).get('started_at') for v in control):
        raise ValueError('use_quiescent_pre_progression_source; never_reset_spent_budget')
    if any(v['state'] not in {'completed','failed'} for v in run_snapshot(source)):
        raise ValueError('source_has_unfinished_runs')
    frozen=dict(source=str(source),installed=str(installed),previous=str(previous.resolve()) if previous else None,
        config=settings,harness_digest=harness_digest(),
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
    frozen={**{k:v for k,v in config.items() if k not in {'cases','objectives','quality'}},**case,
        'text':config['objectives'].get(case.get('objective'),''),
        'baseline_digest':baseline,'conditions_digest':manifest['conditions_digest']}
    write(target/'acceptance-case.json',frozen)
    write(root/(case_id+'.prepared.json'),dict(case_digest=digest(frozen)))
    resources=read(SCRIPTS/'root_host_resources.json')
    resources['execution_timeout_seconds']=config['resources']['timeout_seconds']
    if config.get('budget'):
        resources['execution_timeout_seconds'] = min(resources['execution_timeout_seconds'],
            config['budget']['session']['execution_seconds'])
    write(target/'host-resources.json',resources)
    if digest(read(target/'agent-settings.json'))!=manifest['source_settings_digest'] and case_id!='rollback':
        raise ValueError('source_settings_changed')
    print('已准备：'+str(target),flush=True)


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


def result(root,manifest,case_id):
    contract=manifest['config']['cases'][case_id]; target=root/case_id
    checks={}; output=dict(case=case_id,checks=checks,status='not_observed')
    journeys=sorted(target.glob('journey-*'))
    if len(journeys)>1:raise ValueError('multiple_attempts_require_separate_accounting')
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
    exit_file=root/(case_id+'.exit.json')
    closed=read(exit_file) if exit_file.exists() else {}
    if resource.get('stop_reason') not in {None,'exited'} or resource.get('returncode') not in {None,0} or closed.get('returncode') not in {None,0}:
        checks['execution']='failed'
    if 'execution' not in checks:
        checks['execution']='passed' if resource.get('returncode')==0 and closed.get('returncode')==0 else 'not_observed'
    output['resource']=resource
    frozen=read(target/'acceptance-case.json')
    output.update({k:frozen[k] for k in ('baseline_digest','conditions_digest')})
    output['objective_digest']=digest(frozen['text'])
    before=read(journey/'before-runs.json') if (journey/'before-runs.json').exists() else run_snapshot(target)
    previous_ids={v['run_id'] for v in before}
    new=[v for v in run_snapshot(target) if v['run_id'] not in previous_ids]
    workers,helpers=participants(target,[v['run_id'] for v in new])
    control=control_rows(target,'SELECT p.* FROM scheduler_progression p JOIN scheduler_instances i ON i.instance_id=p.instance_id WHERE i.name=?',(manifest['config']['instance'],))
    progression=control[0] if control and control[0].get('checkpoint_json') and json.loads(control[0]['checkpoint_json']).get('started_at') else None
    output['usage']=usage_report(journey,workers,helpers,progression)
    if (target/'model-submission-started').exists() and not output['usage']['groups']:
        output['usage']['coverage']='partial'
    evidence_path=journey/'sealed-evidence.json'
    if evidence_path.exists():
        evidence=sealed_outputs(target,new)
        if evidence!=read(evidence_path):raise ValueError('sealed_evidence_changed')
        rubric=manifest['config']['quality'][contract['objective']]
        output['review_template']=dict(evidence_digest=digest(evidence),rubric=rubric,reviewer='',
            decisions=[dict(status='not_observed',reason='') for _ in rubric])
        review_path=root/(case_id+'.review.json')
        if review_path.exists():
            quality=assess(evidence,rubric,read(review_path))
            checks['owner_integration' if case_id.startswith('helper') else 'quality']=quality
    if case_id=='rollback' and all(checks.get(k)=='passed' for k in ('terminal_independence','service_restart','state_preserved')):
        checks['rollback']='passed'  # Isolated old build reads state after new build startup.
    output['status']=verdict(checks,[*contract['requires'],'execution'])
    output['scope']='isolated installed candidates; formal installation, live TCAD and detached native resource coverage remain unqualified'
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('init','prepare','run','report','review'))
    parser.add_argument('case',nargs='?')
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=DEFAULT)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--installed',type=Path)
    parser.add_argument('--previous-installed',type=Path)
    parser.add_argument('--review-file',type=Path)
    args=parser.parse_args();os.umask(0o077);root=args.suite.resolve()
    if args.action=='init':
        if not args.source or not args.installed:parser.error('init requires --source and --installed')
        initialize(root,args.config,args.source,args.installed,args.previous_installed);return 0
    manifest=read(root/'suite.json')
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
        else:
            if not args.review_file:parser.error('review requires --review-file')
            current=result(root,manifest,args.case);template=current.get('review_template')
            if not template:raise ValueError('no_sealed_output_to_review')
            review=read(args.review_file)
            # Digest/rubric binding validated before writing the immutable review.
            assess(read(Path(current['evidence'])/'sealed-evidence.json'),template['rubric'],review)
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
