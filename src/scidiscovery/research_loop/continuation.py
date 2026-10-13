"""Explicit finite continuation of a known local failure, never a fresh replay."""
import json
import hashlib
import os
import time
from itertools import islice
from pathlib import Path
import uuid

from . import budget, contracts as c, execution, native, runtime
from .output_repair import OutputRepairRequired


class ResumeUnavailable(ValueError):
    pass


def policy(value, launcher):
    if (not isinstance(value, dict) or set(value) not in ({'max_attempts', 'protocol', 'usage_scope'},
            {'max_attempts', 'protocol', 'usage_scope', 'output_repair'})
            or type(value['max_attempts']) is not int or not 1 <= value['max_attempts'] <= 2
            or value['protocol'] != 'codex_exec_resume' or value['usage_scope'] != 'turn'
            or ('output_repair' in value and type(value['output_repair']) is not bool)):
        raise ValueError('Resume requires explicit finite attempts and qualified turn-scoped launcher protocol')
    if not launcher or not Path(launcher[0]).is_absolute() or not Path(launcher[0]).is_file():
        raise ValueError('Resume requires an exact frozen executable, never PATH selection')
    files = []
    for argument in launcher:
        path = Path(argument).absolute()
        if path.is_file():
            original = c.regular(path.resolve())
            files.append(dict(invoked_path=str(path), path=str(original), sha256=c.digest(original)))
    if not files:raise ValueError('Resume-capable launcher originals must be frozen')
    return dict(value, launcher_files=files)


def validate_launcher(root):
    limits = c.settings(root).get('resume_policy')
    if limits is None:raise ResumeUnavailable('worker_resume_unsupported')
    for proof in limits['launcher_files']:
        if (Path(proof['invoked_path']).resolve() != Path(proof['path'])
                or c.digest(c.regular(Path(proof['path']))) != proof['sha256']):
            raise ValueError('Frozen resume launcher changed')
    return limits



def validate_task(root, step):
    job = c.read(c.regular(root / 'jobs' / f'{step:03d}.json'))
    c._validate_inputs(root, c.workspace(root, step), job)
    schema = c.read(c.regular(execution.origin(root, step) / 'science-result.schema.json', limit=c.MAX_RESULT_BYTES))
    if schema != c.result_schema(job['role'], job.get('handoff_protocol', 1)):
        raise ValueError('Original native output schema changed')
    return job

def session(root, step, record):
    outcome = c.read(c.regular(record / 'native-outcome.json'))
    thread = outcome.get('thread_id')
    try:
        if str(uuid.UUID(thread)) != thread:raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ResumeUnavailable('worker_resume_thread_unavailable')
    found = False
    with c.regular(record / 'native.jsonl').open('rb') as stream:
        for _ in range(256):
            line = stream.readline(65537)
            if not line:break
            if len(line) > 65536:raise ResumeUnavailable('worker_resume_thread_unavailable')
            event = json.loads(line)
            if event.get('type') == 'thread.started':
                if event.get('thread_id') != thread:raise ValueError('Native thread identity changed')
                found = True
                break
    if not found:raise ResumeUnavailable('worker_resume_thread_unavailable')
    home = root / 'native-homes' / f'{step:03d}'
    if home.resolve() != home:raise ValueError('Original native home changed')
    matches = []
    for visited, path in enumerate(islice((home / 'sessions').rglob('*.jsonl'), 257), 1):
        if visited > 256:raise ResumeUnavailable('worker_resume_session_capacity')
        if path.resolve() != path:raise ValueError('Native session original changed')
        with c.regular(path).open('rb') as stream:line = stream.readline(65537)
        if len(line) > 65536:raise ResumeUnavailable('worker_resume_session_unavailable')
        event = json.loads(line)
        if event.get('type') == 'session_meta' and event.get('payload', {}).get('id') == thread:
            if event['payload'].get('cwd') != str(c.workspace(root, step)):
                raise ValueError('Native session workspace changed')
            matches.append(dict(path=str(path), header_sha256=hashlib.sha256(line).hexdigest()))
    if len(matches) != 1:raise ResumeUnavailable('worker_resume_session_unavailable')
    return dict(thread_id=thread, home=str(home), workspace=str(c.workspace(root, step)), **matches[0])


def seal_or_repair(root, step):
    """Try the original seal first; only a frozen opt-in can accept a repair turn."""
    try:
        return c.seal_result(root, step)
    except OutputRepairRequired:
        if not (c.settings(root).get('resume_policy') or {}).get('output_repair', False):
            raise
        return start(root, step)


def output_request(root, step, record, *, source_attempt=None, verify_task=True):
    """Recompute a repair binding from verified original final-response bytes."""
    job = validate_task(root, step) if verify_task else c.read(c.regular(root / 'jobs' / f'{step:03d}.json'))
    outcome = c.read(c.regular(record / 'native-outcome.json'))
    if (type(outcome.get('returncode')) is not int or outcome['returncode'] != 0
            or outcome.get('stop_reason') or outcome['usage']['unknown_steps']):
        raise ValueError('Output repair requires a known completed original turn')
    raw = record / 'science-output.json'
    if outcome.get('output_status') == 'missing':
        if raw.exists() or raw.is_symlink() or (record / 'result.pending.json').exists() or (record / 'result.pending.json').is_symlink():
            raise ValueError('Missing final output identity changed')
        error = OutputRepairRequired('missing_output', 'Return the required final scientific JSON; the completed work and checkpoints are already retained.')
    else:
        if c.digest(c.regular(raw, limit=c.MAX_RESULT_BYTES)) != outcome.get('raw_sha256'):
            raise ValueError('Original final output changed before repair')
        try:
            c.science_payload(raw, job['role'], job.get('handoff_protocol', 1))
        except OutputRepairRequired as failure:
            error = failure
        else:
            raise ValueError('A valid final response does not authorize an output repair')
    if source_attempt is None:
        source_attempt = len(execution.records(root, step)) - 1
    return dict(**error.request(), source_attempt=source_attempt,
                outcome_sha256=c.digest(record / 'native-outcome.json'), raw_sha256=outcome.get('raw_sha256'))


def validate_repair(root, step, intent, *, prior_record=None, verify_task=True):
    request = intent.get('output_repair')
    if request is None:
        return
    if not validate_launcher(root).get('output_repair', False):
        raise ValueError('Output repair is not authorized by the frozen policy')
    prior = prior_record if prior_record is not None else execution.records(root, step)[intent['attempt'] - 1]
    expected = output_request(root, step, prior, source_attempt=intent['attempt'] - 1, verify_task=verify_task)
    if request != expected:
        raise ValueError('Accepted output repair differs from its original response failure')


def validate_repair_chain(root, step, chain):
    """Terminal execution checks every repair source without replaying projections."""
    for number, record in enumerate(chain[1:], 1):
        intent = c.read(c.regular(record / 'native-intent.json'))
        if intent.get('output_repair') is not None:
            # execution.records already verified task/attempt/previous identities.
            # Avoid terminal -> scientific projection -> terminal recursion.
            validate_repair(root, step, intent, prior_record=chain[number - 1], verify_task=False)


def start(root, step):
    limits = validate_launcher(root)
    if (execution.origin(root, step) / 'result-identity.json').exists():
        return c.validate(c.workspace(root, step))
    paths = execution.records(root, step)
    if runtime.node_state(root, step) == 'running' or (len(paths) > 1 and runtime.node_state(root, step) == 'unknown'):
        return native.wait_native(root, step)  # An accepted attempt is collected before cap checks.
    last = paths[-1]
    outcome = c.read(c.regular(last / 'native-outcome.json'))
    repair = None
    if outcome.get('returncode') == 0 and not outcome.get('stop_reason'):
        try:
            return c.seal_result(root, step)
        except OutputRepairRequired:
            if not limits.get('output_repair', False):
                raise
            repair = output_request(root, step, last)
    closeout = budget.closeout_state(root)['begin']
    job = c.read(c.regular(root / 'jobs' / f'{step:03d}.json'))
    if (root / 'pause.request').exists() or (closeout is not None and
            (repair is None or job.get('purpose') != 'closeout')):
        raise ResumeUnavailable('worker_resume_paused_or_closeout')
    from . import correction
    if correction.gate(root, step - 1) is not None:
        raise ResumeUnavailable('worker_resume_correction_paused')
    if len(paths) - 1 >= limits['max_attempts']:raise ResumeUnavailable('worker_resume_limit')
    settings = c.settings(root)
    for later in range(step + 1, settings['max_steps'] + 1):
        if (execution.origin(root, later) / 'native-intent.json').exists():
            raise ResumeUnavailable('worker_resume_successor_present')
    original_intent = c.read(c.regular(paths[0] / 'native-intent.json'))
    if original_intent.get('task_sha256') != c.digest(root / 'jobs' / f'{step:03d}.json'):
        raise ValueError('Original native task identity changed')
    validate_task(root, step)
    outcome = c.read(c.regular(last / 'native-outcome.json'))
    if (type(outcome.get('returncode')) is not int or (outcome['returncode'] == 0 and repair is None)
            or outcome.get('stop_reason') or outcome.get('cleanup') != 'observed_group_cleaned'):
        raise ResumeUnavailable('worker_resume_terminal_ineligible')
    meter = c.read(c.regular(last / 'usage.json'))
    if native._usage_event(dict(type='turn.completed', usage=meter)) != meter:
        raise ResumeUnavailable('worker_resume_usage_unknown')
    for name in ('runner-process.json', 'native-process.json'):
        if c.digest(c.regular(last / name)) != outcome.get('execution_processes', {}).get(name):
            raise ValueError('Original execution process receipt changed')
        identity = c.read(c.regular(last / name))
        if (identity.get('task_sha256') != execution.identity(root, step)
                or identity.get('boot_id') != budget.clock_stamp()['boot_id']
                or any(type(identity.get(key)) is not int or identity[key] <= 0
                       for key in ('pid', 'start_ticks', 'pgid', 'sid', 'ppid'))):
            raise ValueError('Original execution process identity is invalid')
        # The durable terminal receipt can precede its runner's lock release.
        # Collect that exact local process; never launch alongside it.
        if name == 'runner-process.json' and repair is not None:
            until = time.monotonic() + 5
            while runtime.process_matches(identity, execution.identity(root, step)) and time.monotonic() < until:
                time.sleep(.05)
        if runtime.process_matches(identity, execution.identity(root, step)):
            raise ResumeUnavailable('worker_resume_original_running')
    report = outcome.get('budget_slice')
    if not isinstance(report, dict) or not report.get('usage_observed'):
        raise ResumeUnavailable('worker_resume_usage_unknown')
    session_ref = session(root, step, last)
    number = len(paths)
    budget.transition(root, 'advance', 'explicit_worker_continuation')
    anchor = budget.accept_continuation(root, job, paths)
    record = execution.origin(root, step) / 'continuations' / f'{number:03d}'
    record.mkdir(parents=True, exist_ok=True)
    intent = dict(step=step, attempt=number, task_sha256=c.digest(root / 'jobs' / f'{step:03d}.json'),
                  root_intent_sha256=c.digest(paths[0] / 'native-intent.json'), previous=execution.proof(last),
                  session=session_ref, budget_slice=anchor,
                  **(dict(output_repair=repair) if repair is not None else {}))
    with (record / 'native-intent.json').open('x') as stream:
        json.dump(intent, stream);stream.flush();os.fsync(stream.fileno())
    runtime.start(root, step, number)
    return native.wait_native(root, step)
