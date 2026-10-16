"""Control-owned waiting for the original managed execution, not a native retry."""
from pathlib import Path
import time

from . import budget, contracts as c, execution, experiments as e, checkpoint

POLL_SECONDS = 1.
NAME = 'execution-wait.json'


class ExecutionWaiting(Exception):
    def __init__(self, reason='managed_execution_running'):
        self.reason=reason
        super().__init__(reason)


def _config(root,job,accepted):
    number=accepted['native_attempt']['number']
    path=execution.record(root,job['step'],number)/'experiment-config.json'
    config=c.read(c.regular(path))
    records=e.Records(config)
    if (config['execution_interface']!=accepted['interface'] or config['scope']!=accepted['scope']
            or records.accepted(accepted['call_id'])!=accepted):
        raise e.IntegrityError('Waiting execution differs from its frozen host owner')
    return path,config


def validate(root,job,record):
    value=c.read(c.regular(record/NAME,limit=None))
    if (value['job_sha256']!=c.digest(root/'jobs'/f'{job["step"]:03d}.json')
            or value['checkpoint_sha256']!=c.digest(c.regular(record/'checkpoint.json'))
            or value['outcome_sha256']!=c.digest(c.regular(record/'native-outcome.json'))):
        raise e.IntegrityError('Execution waiting checkpoint changed')
    checkpoint.validate(root,job,record)
    if not isinstance(value['calls'],list) or not value['calls']:
        raise e.IntegrityError('Execution waiting requires original calls')
    seen=set()
    for item in value['calls']:
        for key in ('accepted','submission','config'):
            if e.proof(item[key]['path'])!=item[key]:raise e.IntegrityError('Waiting execution original changed')
        accepted=c.read(Path(item['accepted']['path']))
        path,config=_config(root,job,accepted)
        if (str(path)!=item['config']['path'] or accepted['call_id'] in seen
                or e.Records(config).external(accepted['call_id'])!=item['external_run_id']):
            raise e.IntegrityError('Waiting execution identity changed')
        seen.add(accepted['call_id'])
    return value


def before_seal(root,job,record):
    """Only a real accepted/running observation can suspend a successful W turn."""
    if job['role']!='W':return
    outcome=c.read(c.regular(record/'native-outcome.json'))
    raw=record/'science-output.json'
    if outcome.get('output_status')=='missing' or not raw.is_file() or raw.is_symlink():return
    if (type(outcome.get('returncode')) is not int or outcome.get('returncode')!=0 or outcome.get('stop_reason') or outcome.get('usage',{}).get('unknown_steps')!=[]
            or outcome.get('raw_sha256')!=c.digest(c.regular(record/'science-output.json'))):return
    if (record/NAME).exists():
        validate(root,job,record)
        raise ExecutionWaiting()
    root=Path(root)
    records=e.Records(dict(record_dir=str(c.workspace(root,job['step'])/'work/lineage')))
    calls=[]
    for directory in records.calls():
        accepted=c.read(c.regular(directory/'accepted.json'))
        path,config=_config(root,job,accepted)
        external=e.Records(config).external(directory.name)
        if external is None:continue
        observed=directory/'execution-observation.json'
        if observed.exists():
            e.verify_observation(c.read(observed),lambda item:Path(item['path']),interface=config['execution_interface'])
            continue
        if not config['execution_interface']['capabilities']['query']:continue
        adapter=e.load(config)
        details=adapter.status_details(directory.name)
        if details.get('state') not in {'running','succeeded','failed'}:continue
        # A terminal first seen after this native turn also needs W consumption.
        if details['state']!='running':e.record_observation(config,adapter,directory.name)
        calls.append(dict(accepted=e.proof(directory/'accepted.json'),submission=e.proof(directory/'submission.json'),
            config=e.proof(path),external_run_id=external,observed_state=details['state']))
    if not calls:return
    from . import worker_delivery
    worker_delivery.writers_stopped(root,job,record)
    checkpoint.capture(root,job,record)
    value=dict(job_sha256=c.digest(root/'jobs'/f'{job["step"]:03d}.json'),
        checkpoint_sha256=c.digest(record/'checkpoint.json'),outcome_sha256=c.digest(record/'native-outcome.json'),calls=calls)
    c.write(record/NAME,value);(record/NAME).chmod(0o400)
    raise ExecutionWaiting()


def pending(root):
    """Read-only clock classification; no backend query and no new authority."""
    for path in (Path(root)/'native-evidence').glob('*/**/'+NAME):
        record=path.parent
        step=int(record.relative_to(Path(root)/"native-evidence").parts[0])
        job=c.read(Path(root)/'jobs'/f'{step:03d}.json')
        if execution.record(root,job['step'])!=record:continue
        value=validate(root,job,record)
        for item in value['calls']:
            path=Path(item['accepted']['path']).parent/'execution-observation.json'
            if not path.exists():return True
            accepted=c.read(Path(item['accepted']['path']));_,config=_config(root,job,accepted)
            e.verify_observation(c.read(path),lambda proof:Path(proof['path']),interface=config['execution_interface'])
    return False


def wait_and_wake(root,step):
    """The owning run process monitors without native turns; restart uses the same facts."""
    root=Path(root);job=c.read(root/'jobs'/f'{step:03d}.json');record=execution.record(root,step)
    value=validate(root,job,record)
    while True:
        terminals=[];running=False
        for item in value['calls']:
            accepted=c.read(Path(item['accepted']['path']));_,config=_config(root,job,accepted)
            path=Path(item['accepted']['path']).parent/'execution-observation.json'
            if path.exists():
                e.verify_observation(c.read(path),lambda proof:Path(proof['path']),interface=config['execution_interface'])
            else:
                adapter=e.load(config)
                if not config['execution_interface']['capabilities']['query']:
                    raise ExecutionWaiting('managed_execution_query_unavailable')
                state=adapter.status_details(accepted['call_id']).get('state')
                if state=='running':running=True;continue
                if state not in {'succeeded','failed'}:raise ExecutionWaiting('managed_execution_status_unknown')
                if e.record_observation(config,adapter,accepted['call_id']) is None:
                    raise ExecutionWaiting('managed_execution_terminal_unverified')
            terminals.append(e.proof(path))
        if (root/'pause.request').exists():raise ExecutionWaiting('paused_before_execution_wake')
        if budget.snapshot(root)['seconds_remaining']<=0:raise ExecutionWaiting('managed_execution_wait_deadline')
        if not running:
            from . import continuation
            continuation.wake_start(root,step,terminals)
            return
        budget.transition(root,'waiting','managed_execution_running')
        time.sleep(min(POLL_SECONDS,budget.snapshot(root)['seconds_remaining']))


def wake_packet(root,job,intent):
    """Mount exact retained originals for the original W, with bounded navigation."""
    rows=[];work=c.workspace(root,job['step'])
    for number,proof in enumerate(intent['execution_wake']['observations'],1):
        observed=c.read(Path(proof['path']));directory=Path(proof['path']).parent
        completed=c.read(Path(observed['completed']['path']))
        prefix=f'work/execution-results/{number:03d}'
        c._copy_bound(Path(observed['completed']['path']),work/prefix/'result.json',observed['completed']['sha256'])
        outputs=[]
        for item in observed['outputs']:
            target=prefix+'/outputs/'+item['name']
            c._copy_bound(Path(item['path']),work/target,item['sha256']);outputs.append(dict(name=item['name'],path=target))
        originals=[]
        for index,item in enumerate(observed['proofs'],1):
            target=prefix+f'/originals/{index:03d}'
            c._copy_bound(Path(item['path']),work/target,item['sha256']);originals.append(target)
        rows.append(dict(status=observed['status'],original=prefix+'/result.json',outputs=outputs,native_originals=originals))
    c.write(work/'work/execution-results.json',dict(executions=rows,
        limitation='Original execution facts only; interpret their scientific meaning and limitations. Do not resubmit these executions.'))
