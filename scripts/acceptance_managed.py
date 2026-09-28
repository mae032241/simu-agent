"""Owned transient user services; no production unit or instance binding changes.

Called under the same guard as native cases. Detached units additionally have a
hard memory limit and RuntimeMaxSec, so supervisor death cannot leave them alive.
"""
import socket
import subprocess
import time
import uuid
from urllib.request import urlopen

try:
    from scripts.probe_root_host_live import Host
    from scripts.b6_evidence import control_rows, run_snapshot, sealed_outputs, write
except ModuleNotFoundError:
    from probe_root_host_live import Host
    from b6_evidence import control_rows, run_snapshot, sealed_outputs, write


def command(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=15)


class Unit:
    stdin = stdout = None

    def __init__(self, name, args):
        self.name, self.args = name, args

    def properties(self):
        value = command(['systemctl','--user','show',self.name,'--property=ActiveState,MainPID,MemoryPeak,MemoryCurrent,Result'])
        if value.returncode:
            raise RuntimeError('owned_unit_query_failed')
        return dict(line.split('=',1) for line in value.stdout.splitlines() if '=' in line)

    def poll(self):
        return None if self.properties().get('ActiveState') in {'active','activating'} else 1

    def terminate(self):
        value = command(['systemctl','--user','stop',self.name])
        if value.returncode:
            raise RuntimeError('owned_unit_stop_unconfirmed')

    kill = terminate

    def wait(self, timeout=10):
        deadline = time.monotonic()+timeout
        while self.poll() is None:
            if time.monotonic()>deadline:
                raise subprocess.TimeoutExpired(self.name,timeout)
            time.sleep(.1)


class ManagedJourney(Host):
    def launch(self, args, name, pipe=False):
        if pipe:
            raise ValueError('managed_case_has_no_model_client')
        unit = Unit('scid-b6-'+uuid.uuid4().hex+'.service',args)
        self.children.append(unit)  # Cleanup also covers ambiguous launcher outcomes.
        log = self.logdir/(name+'.log')
        budget = self.case_config['managed']
        argv = ['systemd-run','--user','--quiet','--unit='+unit.name,'--service-type=exec',
            '--property=WorkingDirectory='+self.config['project'],
            '--property=MemoryMax='+str(budget['per_service_memory_bytes']),
            '--property=RuntimeMaxSec='+str(budget['runtime_seconds']),
            '--property=KillMode=control-group','--property=StandardOutput=append:'+str(log),
            '--property=StandardError=append:'+str(log),
            '--property=UnsetEnvironment=PYTHONPATH CODEX_SESSION_ID CODEX_THREAD_ID SCIDISCOVERY_ROLE_DIR',
            '--setenv=PYTHONNOUSERSITE=1',
            '--setenv=SCID_AGENT_SETTINGS_FILE='+str(self.root/'agent-settings.json')]
        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','TOKIO_WORKER_THREADS','RAYON_NUM_THREADS'):
            argv.append('--setenv='+key+'=1')
        value=command([*argv,'--',*args])
        if value.returncode:
            raise RuntimeError('owned_unit_launch_failed:'+value.stderr[-500:])
        return unit

    def close(self):
        errors=[]
        self.save_usage()
        self.events.close()
        # Try every owned unit even if one stop fails. RuntimeMaxSec remains the
        # fallback after supervisor failure; never address arbitrary unit names.
        for unit in reversed(self.children):
            try:
                unit.terminate()
            except Exception as error:
                errors.append(dict(unit=unit.name,diagnostic=type(error).__name__))
        write(self.logdir.parent/'managed-cleanup.json',dict(errors=errors))
        if errors:
            raise RuntimeError('managed_cleanup_unconfirmed')

    def health(self):
        if any(child.poll() is not None for child in self.children):
            raise RuntimeError('owned_service_not_active')
        with urlopen(self.ui_url,timeout=5) as reply:
            if reply.status != 200:
                raise RuntimeError('managed_ui_unhealthy')
        with socket.socket(socket.AF_UNIX) as probe:
            probe.settimeout(5)
            probe.connect(str(self.root/'control.sock'))

    def run_journey(self):
        self.case_checks={}
        probe=command(['systemctl','--user','list-units','--no-legend','--no-pager','--type=service'])
        if probe.returncode:
            self.case_checks['terminal_independence']='blocked'
            write(self.logdir.parent/'summary.json',dict(status='blocked',checks=self.case_checks,
                diagnostic='user_systemd_unavailable',b6_passed=False))
            return
        control=control_rows(self.root)
        if any(v['host_json'] or v['state'] in {'active','pending'} for v in control):
            raise ValueError('managed_case_requires_quiescent_state')
        before=run_snapshot(self.root)
        if any(v['state'] not in {'completed','failed'} for v in before):
            raise ValueError('managed_case_has_active_workers')
        sealed_before=sealed_outputs(self.root,[v for v in before if v['state']=='completed'])
        self.start_services()
        self.health()
        # Each systemd-run launcher has exited; services belong to user systemd,
        # independent of this terminal. No model turn is scheduled in this case.
        self.case_checks['terminal_independence']='passed'
        initial=[v.properties() for v in self.children]
        for unit in self.children[1:]:  # Restart daemon, retain the UI's assigned port.
            if command(['systemctl','--user','restart',unit.name]).returncode:
                raise RuntimeError('owned_unit_restart_failed')
        deadline=time.monotonic()+self.case_config['stage_timeout_seconds']
        while True:
            try:
                self.health()
                break
            except (RuntimeError,OSError):
                if time.monotonic()>deadline:raise
                time.sleep(.2)
        final=[v.properties() for v in self.children]
        self.case_checks['service_restart']='passed' if all(a['MainPID']!=b['MainPID'] for a,b in zip(initial[1:],final[1:])) else 'failed'
        self.case_checks['state_preserved']='passed' if (before==run_snapshot(self.root)
            and sealed_before==sealed_outputs(self.root,[v for v in before if v['state']=='completed'])) else 'failed'
        write(self.logdir.parent/'managed-units.json',dict(before=initial,after=final,
            limits=self.case_config['managed'],scope='idle installed daemon/UI; native model descendants not exercised'))
        write(self.logdir.parent/'summary.json',dict(status='evidence_ready',checks=self.case_checks,b6_passed=False))
