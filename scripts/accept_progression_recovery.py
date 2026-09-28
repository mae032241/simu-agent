"""Native control acceptance, reusing sealed science without dispatching work.

Run via accept_progression.py --scenario recovery against a prepared state copy.
This establishes Root lifecycle only; it does not qualify Worker/helper survival.
"""
import json
import sqlite3
import time
from contextlib import closing

try:
    from scripts.accept_progression import Journey, write
except ModuleNotFoundError:
    from accept_progression import Journey, write


OBJECTIVE = """本轮是后台控制恢复验收，复用已有封存成果，不重新进行科学计算。
先读取一个小页 run_list，选取所选旧实例已有封存结果的决策字段，
通过 progression_report 交付简短交接，保留原结果的限制。
不得新建 Run、派发 Worker 或助手、执行外部任务、改变原科学产物或增加预算。
控制验收会主动暂停、恢复、重启服务及交互接管；恢复后先回读现状，不重复已完成动作。
不要人为睡眠等待测试。本轮是单独的控制验收目标。
"""
INGEST_ARGUMENTS = dict(name='acceptance.root-recovery.objective', text=OBJECTIVE, on_conflict='reject')


def running_turn(row):
    checkpoint = json.loads(row['checkpoint_json'])
    return row['state'] == 'active' and row['host_json'] is not None and checkpoint.get('phase') == 'running' and bool(checkpoint.get('turn_id'))


def recovery_matches(before, after):
    """A new native Root must not stand in for recovery of the original thread."""
    old = json.loads(before['host_json'])
    new = json.loads(after['host_json'] or 'null')
    first, second = map(json.loads, (before['checkpoint_json'], after['checkpoint_json']))
    return (new is not None and new['thread_id'] == old['thread_id']
        and before['objective_ref_json'] == after['objective_ref_json']
        and before['config_json'] == after['config_json']
        and first['started_at'] == second['started_at']
        and second.get('rounds', 0) >= first.get('rounds', 0)
        and all(key in second.get('usage_records', {}) and all(
            second['usage_records'][key]['counted_tokens'][counter] >= value['counted_tokens'][counter]
            for counter in ('input_tokens', 'output_tokens'))
            for key, value in first.get('usage_records', {}).items()))


class RecoveryJourney(Journey):
    def row(self):
        path = self.root / 'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            value = db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (self.instance,)).fetchone()
            return dict(value) if value else dict(state='idle', host_json=None)

    def runs_snapshot(self):
        path = self.root / 'state/database/runs.sqlite3'
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            return list(db.execute('SELECT run_id,state,output_ref_json FROM runs ORDER BY run_id'))

    def wait_row(self, predicate, label, *, timeout=90):
        deadline = min(self.phase_deadline, time.monotonic() + timeout)
        while time.monotonic() < deadline:
            self.pump()
            row = self.row()
            if predicate(row):
                write(self.logdir.parent / (label + '.json'), row)
                return row
            if row['reason'] in {'host_fault','budget_exhausted','resource_limit','submission_unknown',
                    'goal_completed','root_turn_failed','attempt_budget_exhausted','task_admission_unknown'}:
                raise RuntimeError(label + ':unexpected_stop:' + row['reason'])
            time.sleep(.2)
        raise TimeoutError(label)

    def run_journey(self):
        self.control_attempted = False
        try:
            self.run_recovery()
        except BaseException:
            if self.control_attempted:
                try:
                    status = self.call('progression_command', dict(command='pause'))
                    write(self.logdir.parent / 'failure-pause.json', status)
                except Exception as error:
                    write(self.logdir.parent / 'failure-pause.json', dict(
                        status='unconfirmed', error_type=type(error).__name__))
            raise

    def run_recovery(self):
        value = self.initialize_host(check_native=False)
        self.status('awaiting_user', management_url=value['management_url'])
        print('请选择已有 b0a-calibration 实例：' + value['management_url'], flush=True)
        while value.get('state') == 'unbound':
            self.pump(); time.sleep(1); value = self.current_instance()
        if value.get('state') != 'active' or value.get('name') != 'b0a-calibration':
            raise RuntimeError('recovery_requires_original_b0a_calibration_instance')
        # Public contracts intentionally hide mechanical IDs. Resolve the exact
        # user-selected name in the supervisor's read-only state, never by recency.
        database = self.root / 'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            self.instance = db.execute('SELECT instance_id FROM scheduler_instances WHERE name=?',
                (value['name'],)).fetchone()[0]
        original = self.row()
        if original['state'] not in {'idle','paused','stopped'} or original['host_json']:
            raise RuntimeError('recovery_requires_quiescent_original_goal')
        if original.get('checkpoint_json') and json.loads(original['checkpoint_json']).get('started_at') is not None:
            raise RuntimeError('use_pre_progression_snapshot; existing_goal_budget_must_not_be_reset')
        write(self.logdir.parent / 'original-control.json', original)
        original_runs = self.runs_snapshot()
        self.status('scientific_turn', scenario='root_control_recovery')
        # The supervisor submits control commands through the native MCP client;
        # it never fabricates a platform identity or writes control databases.
        (self.root / 'model-submission-started').touch(exist_ok=False)
        self.call('artifact_ingest_text', INGEST_ARGUMENTS)
        self.control_attempted = True
        self.call('progression_command', dict(command='start', mode='background', objective_name='acceptance.root-recovery.objective'))
        self.wait_row(running_turn, 'started')
        self.call('progression_command', dict(command='pause'))
        self.wait_row(lambda row: row['state']=='paused' and row['host_json'] is None, 'paused')
        print('已确认原生 Root 暂停并释放；继续恢复及控制服务重启。', flush=True)
        self.call('progression_command', dict(command='resume'))
        resumed = self.wait_row(running_turn, 'resumed')
        # Crash only the daemon owned by this supervisor; retain its state and
        # native thread marker. No process-name kills, DB edits or unknown retries.
        daemon = next(child for child in self.children if 'scidiscovery.artifact_agent.interfaces.mcp_daemon' in child.args)
        command = daemon.args
        daemon.kill(); daemon.wait(timeout=5); self.children.remove(daemon)
        self.launch(command, 'daemon-after-crash')
        recovered = self.wait_row(lambda row: running_turn(row) and
            row['generation'] > resumed['generation'], 'recovered')
        if not recovery_matches(resumed, recovered):
            raise RuntimeError('recovery_identity_or_accounting_changed')
        # Only a successful public call proves the restarted broker is usable.
        status = self.call('progression_status', {})
        write(self.logdir.parent / 'recovered-public.json', status)
        self.call('progression_command', dict(command='takeover'))
        self.wait_row(lambda row: row['mode']=='interactive' and row['host_json'] is None, 'taken-over')
        status = self.call('progression_status', {})
        if not status['can_schedule'] or self.runs_snapshot() != original_runs:
            raise RuntimeError('takeover_or_no_new_science_invariant_failed')
        self.call('progression_command', dict(command='stop'))
        final = self.call('progression_status', {})
        write(self.logdir.parent / 'summary.json', dict(status='root_control_passed',
            b6_passed=False, observed_native_journey=True, scenario='root_control_recovery',
            pause=True, resume=True, daemon_restart=True, exact_root_recovered=True,
            takeover=True, new_runs=0, progression=final,
            unverified=['late old-root write rejection with live native request',
                'Worker/helper crash survival', 'manual/autonomous token comparison',
                'formal deployment rollback', 'complete detached resource coverage']))
        print('原生 Root 控制旅程通过；未创建科学任务，仍不代表 B6 全项通过。', flush=True)
