"""One fresh native process per scientific role; no model scheduler.

An explicit launcher owns native permissions and functional MCP configuration.
The controller never constructs MCP agent calls. Only explicit qualified continuation
can continue the exact original native thread.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

from . import budget as control_budget, execution, runtime, search, checkpoint, profiles
from .output_repair import OutputRepairRequired
from .native_usage import SessionUsage
from .contracts import (ACTIONS, actions, ROLE_INSTRUCTIONS, digest, host_record, read,
                        seal_result, workspace, write, settings as frozen_settings)


def usage(root: Path):
    """Sum distinct node meters, never re-add cumulative observations."""
    totals = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0)
    unknown = []
    settings = frozen_settings(root)
    for step in range(1, settings['max_steps'] + 1):
        for record in execution.records(root, step):
            if not (record / 'native-intent.json').exists():continue
            meter = record / 'usage.json'
            if not meter.exists():
                if step not in unknown:unknown.append(step)
                continue
            value = read(meter)
            if _usage_event(dict(type='turn.completed', usage=value)) != value:
                raise ValueError('Native usage observation changed')
            observation = record / 'usage-observation.json'
            outcome = record / 'native-outcome.json'
            metadata = read(outcome).get('metering') if outcome.exists() else None
            if metadata is None and observation.exists():metadata = read(observation)
            if metadata is not None and metadata.get('coverage') == 'unknown' and step not in unknown:
                unknown.append(step)
            for key in totals:totals[key] += value[key]
    return dict(**totals, observed_tokens=totals['input_tokens'] + totals['output_tokens'], unknown_steps=unknown)


def _usage_event(event):
    if event.get('type') != 'turn.completed':
        return None
    value = event.get('usage')
    if not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] < 0
                                          for k in ('input_tokens', 'output_tokens')):
        return None
    cached = value.get('cached_input_tokens', 0)
    if type(cached) is not int or not 0 <= cached <= value['input_tokens']:
        return None
    return dict(input_tokens=value['input_tokens'], cached_input_tokens=cached, output_tokens=value['output_tokens'])


def execute_native(root: Path, step: int):
    """Submit once, then wait for the same durable local runner."""
    from .protocol import require_current
    require_current(root)
    from . import contracts as _contracts
    require_current(root,_contracts.read(_contracts.regular(Path(root)/'jobs'/f'{step:03d}.json')))
    settings = frozen_settings(root)
    record = execution.record(root, step)
    record.mkdir(parents=True, exist_ok=True)
    job_path = root / "jobs" / f"{step:03d}.json"
    job = read(job_path)
    profile_binding = profiles.binding(settings, job)
    node_anchor = control_budget.accept_node(root, job)
    if node_anchor is not None and job['role'] == 'W' and search.launch_reason(root, job):
        raise ValueError('W dispatch violates its frozen search authorization')
    anchor = search.accept(root, job) if node_anchor is None else None
    with (record / "native-intent.json").open("x") as stream:
        json.dump(dict(step=step, task_sha256=digest(job_path), prepared_at=time.time(), **profile_binding,
                       **(dict(search_slice=anchor) if anchor is not None else {}),
                       **(dict(budget_slice=node_anchor) if node_anchor is not None else {})), stream)
        stream.flush()
        os.fsync(stream.fileno())
    runtime.start(root, step)
    return wait_native(root, step)


def wait_native(root: Path, step: int):
    """Completion polling is transport; only the original outcome can seal."""
    record = execution.record(root, step)
    startup_until = time.monotonic() + 5
    while True:
        from . import managed_wait
        if (record/managed_wait.NAME).exists() and not (execution.origin(root,step)/'result-identity.json').exists():
            managed_wait.wait_and_wake(root,step)
            record=execution.record(root,step);startup_until=time.monotonic()+5
            continue
        state = runtime.node_state(root, step)
        if state in {"terminal", "sealed"}:
            from . import continuation, worker_delivery
            job = read(root / 'jobs' / f'{step:03d}.json')
            fragments = checkpoint.enabled(root, job)
            if state == 'terminal' and job['role']=='W':
                # Outcome publication precedes the runner's final writes. Wait
                # for this exact owner before capturing a delivery checkpoint.
                runner = record / 'runner-process.json'
                if runner.exists() and runtime.process_matches(read(runner), execution.identity(root, step)):
                    time.sleep(.1)
                    continue
                if fragments and not (record/'checkpoint.json').exists():
                    raise continuation.ResumeUnavailable('worker_fragment_checkpoint_unavailable')
            try:result = continuation.seal_or_repair(root, step)
            except managed_wait.ExecutionWaiting:
                continue
            if result.get('fragment_continuation') is True:
                record = execution.record(root, step)
                startup_until = time.monotonic() + 5
                continue
            return result
        if state != "running":
            if not (record / "runner-process.json").exists() and time.monotonic() < startup_until:
                time.sleep(.05)
                continue
            raise RuntimeError("Original native execution is unknown; preserved without replay")
        time.sleep(.1)


def run_native(root: Path, step: int, attempt=0):
    from .protocol import require_current
    require_current(root)
    from . import contracts as _contracts
    require_current(root,_contracts.read(_contracts.regular(Path(root)/'jobs'/f'{step:03d}.json')))
    settings = frozen_settings(root)
    work = workspace(root, step)
    job_path = root / 'jobs' / f'{step:03d}.json'
    job = read(job_path)
    record = execution.record(root, step, attempt)
    record.mkdir(parents=True, exist_ok=True)
    intent = read(record / 'native-intent.json')
    if intent.get('task_sha256') != digest(job_path):
        raise ValueError('Native execution task changed')
    profile = profiles.validate_intent(settings, job, intent)
    if job.get('experiment_mode') != settings.get('experiment_mode'):
        raise ValueError('Frozen experiment mode changed')
    if job['role']=='W' and job.get('experiment_mode')=='local':
        from . import experiments
        experiments.configure(root,step,'local_execution:command',
            dict(run_argv=[sys.executable],max_seconds=min(65,settings['max_seconds']),cwd=str(work)),
            work/'work/experiment-config.json')
    if attempt:
        profiles.validate_intent(settings, job, read(execution.origin(root, step) / 'native-intent.json'))
    # W statistics reuse this exact node anchor, never a second acceptance clock.
    search_intent = dict(intent, search_slice=intent['budget_slice']) if intent.get('budget_slice') is not None and job.get('search') and job['role'] == 'W' else intent
    pending = record / 'result.pending.json'
    args = [*settings['native_launcher_argv'], 'exec', '--json', '--output-last-message', str(pending),
            '--model', profile['model'], '-c', f'model_reasoning_effort={json.dumps(profile["reasoning_effort"])}',
            '-c', f'service_tier={json.dumps(profile["service_tier"])}',
            '--sandbox', 'workspace-write', '-C', str(work), '-']
    role_instruction = job.get('native_role_instruction', ROLE_INSTRUCTIONS[job['role']])
    # Raw Codex is supported as a local soft-isolation entry. Existing qualified
    # launchers retain their own exact argv/config protocol and MCP settings.
    if len(settings['native_launcher_argv']) == 1 and Path(args[0]).name == 'codex':
        args[-1:-1] = ['--skip-git-repo-check', '--output-schema', str(execution.origin(root, step) / 'science-result.schema.json'),
                       '-c', 'project_doc_max_bytes=0', '-c', 'mcp_servers.scidiscovery.enabled=false',
                       '-c', 'features.multi_agent=false', '-c', 'features.fast_mode=false',
                       '-c', 'approval_policy="never"',
                       '-c', 'developer_instructions=' + json.dumps(role_instruction)]
    if settings.get('resume_policy') is not None:
        from . import continuation
        continuation.validate_launcher(root)
    if attempt and intent.get('context_mode') != 'new_context':
        from .contracts import regular
        continuation.validate_repair(root, step, intent)
        session = intent['session']
        if (session.get('home') != str(execution.home(root, step, attempt))
                or session.get('workspace') != str(work)
                or Path(session['path']).resolve() != Path(session['path'])
                or not Path(session['path']).is_relative_to(Path(session['home']) / 'sessions')):
            raise ValueError('Original native session binding changed')
        with regular(Path(session['path'])).open('rb') as stream:
            header = stream.readline()
        import hashlib
        if hashlib.sha256(header).hexdigest() != intent['session']['header_sha256']:
            raise ValueError('Original native session header changed')
        # Global permissions/cwd/config remain before the resume subcommand;
        # all turn output belongs exclusively to this accepted attempt.
        configs = [item for index, item in enumerate(args)
                   if index > len(settings['native_launcher_argv']) and args[index - 1] == '-c']
        global_args = ['-C', str(work), '--sandbox', 'workspace-write']
        for config in configs:global_args.extend(['-c', config])
        if '--skip-git-repo-check' in args:global_args.append('--skip-git-repo-check')
        args = [*settings['native_launcher_argv'], 'exec', *global_args, 'resume', '--json', '--model', profile['model'], '--output-schema',
                str(execution.origin(root, step) / 'science-result.schema.json'),
                '--output-last-message', str(pending), session['thread_id'], '-']
    (work / 'artifacts').mkdir(exist_ok=True)
    (work / 'work').mkdir(exist_ok=True)
    budget = usage(root)
    limits = control_budget.snapshot(root, settings)
    links_instruction = ('and limitations. Ordinary scientific citations and useful deliverable links are optional; unresolved links '
              'do not select files or acquire evidence qualification. Do not write handoff markers or mechanical '
              'evidence/repair paths. implementation_selection is a scientific choice: null keeps the already '
              'selected inputs, [] clears them, and listed object IDs replace them; do not restate unchanged choices. '
              if job.get('handoff_protocol', 1) >= 7 else
              'and Markdown links to the few needed deliverables, such as [comparison](artifacts/comparison.csv); '
              'the host resolves these links for the next role. ')
    completion = ("Complete your role's scientific work within the budget, preserving necessary validation. Report findings, uncertainties "
                  if job.get('handoff_authority_version') == 1 else
                  'Conclude once you have a decision-relevant scientific contribution. Report findings, uncertainties ')
    if job.get('scientific_work_unit'):
        completion=job['scientific_work_unit']+' Report findings, uncertainties '
    verification = '' if job.get('handoff_authority_version') == 1 else 'Leave further scientific verification requests to A. '
    prompt = (role_instruction + '\nRead science-task.json, then the global files and direct '
              'parent conclusions it names. Read particular parent artifacts only as scientifically needed. '
              'Use work/ for scratch code, logs, diagnostics and intermediate models; artifacts/ contains only '
              'necessary deliverables for the next role. Experiments may use experiments/<name>/{work,artifacts} '
              'and an optional brief scientific conclusion.md. Those are directories, not extra role agents. '
              + completion + links_instruction + verification
              + 'The controller collects deliverables, records paths and hashes, validates and seals your final response. '
              'Do not build attachment indexes, manifests, provenance inventories, hash lists, packaging scripts, '
              'or schema validators. Do not duplicate final responses in files or copy every model for handoff. '
              'Historical cross-node delivery uses A next_action=deliver and the controller adapter; native exp submit '
              'uses declared run paths and does not resolve archived historical originals. '
              'Scientific checks required by the task remain your work. Return the small scientific JSON described '
              'by final_response, directly as your final answer. Routing, when needed, uses next_action with a '
              'separate route_reason. The controller dispatches the next role; functional tools retain their permissions.\n'
              + json.dumps(dict(
                  next_action_options=actions(job['role'], job.get('handoff_protocol', 1),
                      audit_enabled=settings.get('candidate_audit_policy') == {'version': 1}),
                  shared_seconds_remaining=max(0, int(limits['seconds_remaining'])),
                  shared_observed_tokens_remaining=max(0, limits['max_tokens']-budget['observed_tokens']),
                  metering='Native usage may be delayed; this is not a guaranteed billing cap.',
                  **(dict(node_budget=intent['budget_slice']['limits']) if intent.get('budget_slice') else {})), ensure_ascii=False))
    if control_budget.node_mode(root)=='soft':
        prompt += ('\nNode and search limits are soft targets, not renewed grants. Between bounded actions read work/budget-status.json when available. '
                   'Near/reached targets or delivery reserve: preserve useful results and return your scientific JSON promptly. '
                   'This file is advisory and usage can be unknown; shared hard limits still apply. \n')
    if job['role']=='W' and job.get('experiment_mode')=='local':
        prompt += ('\nManaged local experiments: run '+json.dumps([sys.executable,'-m','scidiscovery.research_loop.experiments',
            '--config','work/experiment-config.json','run','--experiment-dir','experiments/<name>','--script','experiments/<name>/run.py','--','<script args>'])
            +'. Use real paths/arguments. Only the chosen directory is snapshotted, excluding its artifacts/. '
            'The copied script runs with that snapshot as cwd and writes artifacts/; original directories are unchanged. '
            'Control retains exit/time/logs/inputs/outputs. Optional artifacts/result.json is version 1 JSON with metrics '
            '(name,value; optional unit,evaluation_key,direction) and outputs (path relative to the experiment root, label). '
            'Optional candidate (label,metric,artifact) names one declared metric with explicit evaluation_key/direction and one declared output path; control assigns its identity and delivers its retained inputs/results after A chooses it. '
            'Use finite metric values; control does not infer metric meaning, candidate ranking or qualification. '
            'Do not write hashes or identities. Native shell remains available for scratch. Query lineage-status for original calls; never repeat an unknown call.\n')
    if job['role'] == 'W':
        prompt += ('\nAn optional engineering_check may follow a confirmed managed call while you remain in this task. Read its compact feedback and repair source in this same session when useful. '
            'sample_replay_ok covers only its declared sample path, never full training or audit qualification. Small-sample or bounded-check failures may be inconclusive. '
            'An isolated replay sees only frozen submitted source and declared public inputs plus the task runtime dependencies; sibling scratch helpers and your home are absent. '
            'Do not package dependencies or write hashes/manifests; make the submitted implementation self-contained or use an explicitly supported dependency input.\n')
    if checkpoint.enabled(root, job):
        prompt += ('\nA native turn can be a fragment of this same scientific stage. Give your current understanding, '
                   'unresolved questions and scientific next intent. stage_intent=continue requests more work in the assigned task; '
                   'review reports its completed scientific delivery, while decision requests A with partial work. The host can require review at the original investment boundary. '
                   'The host creates checkpoints and counts attempts; do not write mechanical checkpoint or budget fields.\n')
    if attempt:
        remaining = dict(observed_tokens=max(0, intent['budget_slice']['limits']['max_observed_tokens'] - intent['budget_slice']['previous_tokens']),
                         active_seconds=max(0., intent['budget_slice']['limits']['max_seconds'] - control_budget._node_duration(root, job, intent, limits)))
        if control_budget.node_mode(root)=='soft':
            remaining.update(mode='soft_targets',previous_observed_tokens=intent['budget_slice']['previous_tokens'])
        label = 'Original soft-target gaps (zero is not a new grant): ' if control_budget.node_mode(root)=='soft' else 'Original node remaining budget: '
        context = 'new context for this same task/workspace' if intent.get('context_mode') == 'new_context' else 'same task/session/workspace'
        prompt = (label + json.dumps(remaining) + '\nContinue this ' + context + '. Read existing checkpoints and confirmed results; '
                  'collect or recover managed executions by their original IDs rather than resubmitting. '
                  'Use scientific judgment for ordinary native shell checkpoints; no new mechanical registry is required.\n' + prompt)
        if intent.get('output_repair'):
            prompt = ('Repair only your final response for this same completed task. Preserve completed experiments and '
                      'their results; do not rerun or resubmit them. Return corrected scientific JSON using the frozen '
                      'final_response contract. Controller diagnosis: '
                      + json.dumps({key: intent['output_repair'][key] for key in ('code', 'diagnostic')}, ensure_ascii=False)
                      + '\n' + prompt)
    if intent.get('execution_wake'):
        from . import managed_wait
        from . import continuation
        continuation.validate_wake(root,step,intent,execution.record(root,step,attempt-1))
        managed_wait.wake_packet(root,job,intent)
        prompt=('The original managed execution has finished. Read work/execution-results.json and its exact retained outputs. '
            'Continue this same task/session from its checkpoint, interpret the results, and return your own scientific findings. '
            'Do not rerun or resubmit the completed execution.\n'+prompt)
    if intent.get('work_repair'):
        request=intent['work_repair']
        prompt=('Complete the missing scientific delivery for this same assigned task/session. Keep the original task action. '
            'Reuse confirmed observations and query existing original calls; never resubmit completed experiments. '
            'Add experiments only for scientifically unresolved assigned mechanisms within original authorization. '
            'Return your own mechanism findings, obstacles and limitations; require A decision if science cannot proceed. '
            'Controller diagnosis: '+json.dumps({key:request[key] for key in ('code','diagnostic')},ensure_ascii=False)+'\n'+prompt)
    if intent.get('continuation_kind') == 'fragment':
        prior = execution.record(root, step, attempt - 1)
        saved = intent['fragment_checkpoint']
        if saved['path'] != (prior / 'checkpoint.json').relative_to(root).as_posix() or saved['sha256'] != digest(prior / 'checkpoint.json'):
            raise ValueError('Native fragment checkpoint changed before launch')
        packet = checkpoint.brief(root, job, prior)
        write(work / 'work/science-resume.json', packet)
        prompt += ('\nRead work/science-resume.json for the bounded prior fragment preview. Continue within the original scientific scope; '
                   'the host retains exact execution and candidate identities. Return current understanding, remaining questions '
                   'and stage_intent (continue this mechanism or review by A). Do not write checkpoint IDs, counters or file manifests.\n')
    home = execution.home(root, step, attempt)
    home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'THIN_HWA_ROLE': job['role'], 'THIN_HWA_WORKSPACE': str(work),
           'THIN_HWA_NATIVE_HOME': str(home), 'THIN_HWA_JOB_MANIFEST': str(job_path)}
    if settings.get('resume_policy') is not None:env['CODEX_HOME'] = str(home)
    meter_home = home
    if settings.get('resume_policy') is None and len(settings['native_launcher_argv']) == 1 and Path(args[0]).name == 'codex':
        # Raw Codex keeps its inherited credentials/configuration and writes its
        # rollout into that same actual home, not the stage's launcher namespace.
        meter_home = Path(env['CODEX_HOME']) if env.get('CODEX_HOME') else Path.home() / '.codex'
        if not meter_home.is_absolute():meter_home = work / meter_home
        meter_home = meter_home.resolve()
    process = None
    process_id = None
    stop = None
    error = None
    pending_line = b''
    meter = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0)
    observed = False
    terminal_observed = False
    terminal_meter = dict(meter)
    live_meter = SessionUsage(meter_home, work, session=intent.get('session') if attempt and intent.get('context_mode') != 'new_context' else None)
    cleanup = None
    thread_id = None
    try:
        with (record / 'native.jsonl').open('wb') as log, (record / 'native.stderr').open('wb') as err:
            # Submission happens here, after runner/watchdog startup. Recheck
            # all shared limits; this fresh intent alone is not missing usage.
            latest = usage(root)
            limits = control_budget.snapshot(root, settings)
            stop = ('wall_limit' if limits['seconds_remaining'] <= 0 else
                    'usage_unknown' if any(item != step for item in latest['unknown_steps']) else
                    'token_limit' if latest['observed_tokens'] >= limits['max_tokens'] else None)
            stop = stop or control_budget.node_admission(root, job, ignore_step=step, intent=intent)
            stop = stop or control_budget.stop_node(root, job, intent, limits, meter)
            stop = stop or search.stop_reason(root, job, search_intent, limits, meter)
            if stop:
                write(record / 'usage.json', dict(input_tokens=0, cached_input_tokens=0, output_tokens=0))
                write(record / 'native-outcome.json', dict(returncode=None, stop_reason=stop,
                    native_started=False, usage=usage(root), thread_id=None,
                    limitation='Budget stopped the original intent before native submission.'))
                return
            if settings.get('resume_policy') is not None:
                continuation.validate_task(root, step)
            control_budget.write_node_hint(root,job,intent,limits,meter,observed=observed)
            next_hint=time.monotonic()+5
            hint_dirty=False
            process = subprocess.Popen(args, cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=err, env=env, start_new_session=True)
            process_id = runtime.process_identity(process.pid, execution.identity(root, step, attempt))
            write(record / "native-process.json", process_id)
            process.stdin.write(prompt.encode())
            process.stdin.close()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map() or process.poll() is None:
                    for key, _ in selector.select(1):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        log.write(chunk)
                        log.flush()
                        pending_line += chunk
                        if len(pending_line) > 64 * 1024 * 1024:
                            raise ValueError('Native event exceeds transport byte budget')
                        while b'\n' in pending_line:
                            line, pending_line = pending_line.split(b'\n', 1)
                            try:
                                event = json.loads(line)
                            except ValueError:
                                continue
                            if not isinstance(event, dict):
                                continue
                            if event.get('type') == 'thread.started':
                                thread_id = event.get('thread_id')
                                live_meter.bind_thread(thread_id)
                            current = _usage_event(event)
                            if current is not None:
                                # exec turn.completed usage belongs to this turn.
                                for key in terminal_meter:
                                    terminal_meter[key] += current[key]
                                terminal_observed = True
                                observed = True
                                hint_dirty=True
                    observation = live_meter.poll()
                    projected = {key: max(terminal_meter[key], observation['tokens'][key]) for key in meter}
                    if projected != meter:
                        hint_dirty = True
                    meter = projected
                    observed = observed or observation['has_observation']
                    if observed:
                        write(record / 'usage.json', meter)
                    write(record / 'usage-observation.json', observation)
                    # Pause is a next-node barrier. Accepted work can finish and
                    # seal; it must not become an unknown submission on resume.
                    limits = control_budget.snapshot(root, settings)
                    if limits['seconds_remaining'] <= 0:
                        stop = 'wall_limit'
                    elif usage(root)['observed_tokens'] >= limits['max_tokens']:
                        stop = 'token_limit'
                    stop = stop or control_budget.exploration_stop(root, job, limits)
                    stop = stop or control_budget.stop_node(root, job, intent, limits, meter)
                    stop = stop or search.stop_reason(root, job, search_intent, limits, meter)
                    if stop or hint_dirty or time.monotonic()>=next_hint:
                        control_budget.write_node_hint(root,job,intent,limits,meter,observed=observed)
                        next_hint=time.monotonic()+5
                        hint_dirty=False
                    if stop:
                        break
    except BaseException as exc:
        error = exc
        stop = 'native_error_unknown'
    finally:
        if process is not None:
            try:
                if process_id is not None and runtime.process_matches(process_id, process_id['task_sha256']):
                    os.killpg(process_id['pgid'], signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if process_id is not None and runtime.process_matches(process_id, process_id['task_sha256']):
                    os.killpg(process_id['pgid'], signal.SIGKILL)
                process.wait(timeout=5)
            if process_id is not None:
                cleanup = runtime.cleanup_owned_group(process_id)
                if cleanup == 'cleanup_unknown':
                    stop = 'cleanup_unknown'
            if job.get('experiment_mode')=='local' and job['role']=='W':
                from . import local_experiments
                try:managed_cleanup=local_experiments.cleanup(root,job)
                except (OSError,ValueError,KeyError,TypeError):managed_cleanup='cleanup_unknown'
                if managed_cleanup=='cleanup_unknown':
                    cleanup='cleanup_unknown';stop='cleanup_unknown'
            if process.stdout is not None:
                process.stdout.close()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
    if process is not None:
        observation = live_meter.poll()
        observed = observed or observation['has_observation']
        for key in meter:
            meter[key] = max(meter[key], observation['tokens'][key], terminal_meter[key])
        observation.update(live_coverage=observation['coverage'], live_reason=observation['reason'],
                           live_tokens=dict(observation['tokens']))
        if terminal_observed:
            mismatch = any(terminal_meter[key] < meter[key] for key in meter)
            if mismatch or live_meter.fault:
                observation.update(coverage='unknown', reason=live_meter.fault or 'terminal_usage_below_live_observation')
                stop = stop or 'native_usage_unreconciled'
            else:
                observation.update(coverage='terminal', reason=None, source='turn.completed',
                                   reconciliation=('matched' if observation['tokens'] == terminal_meter else 'terminal_covers_live')
                                       if observation['has_observation'] else 'terminal_fallback',
                                   unreported_usage=None)
        else:
            observation.update(coverage='unknown', reason=live_meter.fault or 'terminal_usage_unreported')
        observation['tokens'] = dict(meter)
        if observed:
            write(record / 'usage.json', meter)
        write(record / 'usage-observation.json', observation)
    outcome = dict(returncode=process.returncode if process else None,
          stop_reason=stop, usage=usage(root), thread_id=thread_id, cleanup=cleanup,
          metering=live_meter.snapshot() if process is None else observation,
          limitation='Observed token metadata only; running requests and reporting delay are unmeasured.')
    if attempt and intent.get('context_mode') != 'new_context' and thread_id != intent['session']['thread_id']:
        stop = outcome['stop_reason'] = 'native_thread_changed'
    if settings.get('resume_policy') is not None and process is not None:
        outcome['execution_processes'] = {name: digest(record / name) for name in ('runner-process.json', 'native-process.json')}
    if intent.get('budget_slice') is not None:
        try:
            outcome['budget_slice'] = control_budget.node_report(root, job, intent, meter)
            outcome['budget_slice']['usage_observed'] = observed
        except ValueError:
            stop = outcome['stop_reason'] = 'node_slice_meter_unknown'
            outcome['budget_slice'] = dict(status='unknown')
    if search_intent.get('search_slice') is not None:
        try:
            outcome['search_slice'] = search.report(root, job, search_intent, meter)
            if intent.get('budget_slice') is not None:outcome['search_slice'] = outcome['budget_slice']
        except ValueError:
            stop = outcome['stop_reason'] = 'w_slice_meter_unknown'
            outcome['search_slice'] = dict(status='unknown')
    if error is not None:
        write(record / 'native-outcome.json', outcome)
        raise error
    if stop or process.returncode != 0 or not terminal_observed:
        write(record / 'native-outcome.json', outcome)
        raise RuntimeError('Native work is not a verified terminal result; preserved without replay')
    raw = record / 'science-output.json'
    if pending.is_symlink() or (pending.exists() and not pending.is_file()):
        outcome['output_status'] = 'unsafe'
        write(record / 'native-outcome.json', outcome)
        raise ValueError('Native science output is missing or not a regular file')
    if not pending.exists():
        outcome['output_status'] = 'missing'
        write(record / 'native-outcome.json', outcome)
        raise OutputRepairRequired('missing_output', 'Return the required final scientific JSON; the completed work and checkpoints are already retained.')
    os.replace(pending, raw)
    outcome['raw_sha256'] = digest(raw)
    write(record / 'native-outcome.json', outcome)
    return outcome
