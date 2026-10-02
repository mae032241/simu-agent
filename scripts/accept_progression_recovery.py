"""Native control acceptance, reusing sealed science without dispatching work.

Run via accept_progression.py --scenario recovery against a prepared state copy.
This establishes Root lifecycle only; it does not qualify Worker/helper survival.
"""
import json
import sys
import time

try:
    from scripts.accept_progression import Journey, write
    from scripts.b6_evidence import read, verify_prior_turns, control_rows, run_snapshot
except ModuleNotFoundError:
    from accept_progression import Journey, write
    from b6_evidence import read, verify_prior_turns, control_rows, run_snapshot


OBJECTIVE = """本轮是后台控制恢复验收，复用已有封存成果，不重新进行科学计算。
先读取一个小页 run_list，选取所选旧实例已有封存结果的决策字段，
通过 progression_report 交付简短交接，保留原结果的限制；完成这项交接后设置 completed=true。
不得新建 Run、派发 Worker 或助手、执行外部任务、改变原科学产物或增加预算。
控制验收会主动暂停、恢复、重启服务及交互接管；恢复后先回读现状，不重复已完成动作。
不要人为睡眠等待测试。本轮是单独的控制验收目标。
"""
INGEST_ARGUMENTS = dict(name='acceptance.root-recovery.objective', text=OBJECTIVE, on_conflict='reject')
CLOSEOUT_ARGUMENTS = dict(name='acceptance.root-closeout.objective', on_conflict='reject', text='''
本轮只验收后台 Root 自然完成与控制收尾。读取已有 a6.tcad.audit 的最终决策字段，
用 progression_report(completed=true) 简短交接并结束本回合，保留原结果的限制。
不得新建科学任务、派发 Worker/助手、执行外部任务或改变科学产物、配置及预算。
不做新的计算，不重复审批，不等待额外指令。''')

STOP_REASONS = {'goal_completed', 'host_fault', 'budget_exhausted', 'resource_limit',
    'submission_unknown', 'root_turn_failed', 'attempt_budget_exhausted', 'task_admission_unknown'}


def closeout_diagnostic(error, stage, reason=None):
    """Keep bounded codes only; exception text can contain private RPC content."""
    known = {'app_server_closed', 'host_connection_unusable', 'rpc_timeout',
        'protocol_message_limit', 'protocol_invalid_json', 'protocol_invalid_message',
        'owned_process_exited', 'user_stop', 'public_tool_failed',
        'acceptance_session_budget_exhausted', 'acceptance_final_budget_unconfirmed'}
    candidate = getattr(error, 'code', None)
    if candidate is None and error.args and isinstance(error.args[0], str):
        candidate = error.args[0].split(':', 1)[0]
    code = candidate if candidate in known else 'timeout' if isinstance(error, TimeoutError) else 'unclassified_error'
    return dict(error_type=type(error).__name__, stage=stage, error_code=code,
        stop_reason=reason if reason in STOP_REASONS | {'user_paused', 'user_stopped', 'host_active'} else None)


def running_turn(row):
    checkpoint = json.loads(row['checkpoint_json'])
    return row['state'] == 'active' and row['host_json'] is not None and checkpoint.get('phase') == 'running' and bool(checkpoint.get('turn_id'))


def naturally_completed(row):
    checkpoint=json.loads(row['checkpoint_json'])
    return (checkpoint.get('phase')=='idle' and checkpoint.get('turn_id') is None
        and checkpoint.get('native_completion')=='completed'
        and bool((checkpoint.get('report') or {}).get('completed')))


def recovery_matches(before, after):
    """A new native Root must not stand in for recovery of the original thread."""
    old = json.loads(before['host_json'])
    new = json.loads(after['host_json'] or 'null')
    first, second = map(json.loads, (before['checkpoint_json'], after['checkpoint_json']))
    return (new is not None and new['thread_id'] == old['thread_id']
        and new.get('platform_session') == old['platform_session']
        and before['objective_ref_json'] == after['objective_ref_json']
        and before['config_json'] == after['config_json']
        and first['started_at'] == second['started_at']
        and second.get('rounds', 0) >= first.get('rounds', 0)
        and second.get('attempts', 0) >= first.get('attempts', 0)
        and all(key in second.get('usage_records', {}) and all(
            second['usage_records'][key]['counted_tokens'][counter] >= value['counted_tokens'][counter]
            for counter in ('input_tokens', 'output_tokens'))
            for key, value in first.get('usage_records', {}).items()))


class RecoveryJourney(Journey):
    def row(self):
        authorization = self.logdir.parent/'loop-authorization.json'
        loop_id = read(authorization)['id'] if authorization.exists() else None
        values = control_rows(self.root, 'SELECT * FROM scheduler_progression WHERE instance_id=?',
            (self.instance,), accounting=True, loop_id=loop_id, deadline=self.phase_deadline)
        return values[0] if values else dict(state='idle', host_json=None)

    def runs_snapshot(self):
        return [tuple(value[key] for key in ('run_id','state','output_ref_json')) for value in run_snapshot(self.root)]

    def wait_row(self, predicate, label, *, timeout=90, cleanup=False):
        previous_deadline = self.phase_deadline
        deadline = time.monotonic() + timeout
        if cleanup:
            # Only observe release in this bounded grace window. Restore the
            # execution deadline afterwards; no scientific/model budget changes.
            self.phase_deadline = deadline
        else:
            deadline = min(previous_deadline, deadline)
        try:
            while time.monotonic() < deadline:
                self.pump()
                row = self.row()
                if predicate(row):
                    write(self.logdir.parent / (label + '.json'), row)
                    return row
                # Active goal_completed is a delivery event. Cleanup may also
                # observe stops, but only its predicate proves writer release.
                stopped_goal = (row.get('reason')=='goal_completed'
                    and row.get('state') in {'paused','stopped'})
                if not cleanup and (stopped_goal or row.get('reason') in STOP_REASONS - {'goal_completed'}):
                    raise RuntimeError(label + ':unexpected_stop:' + row['reason'])
                time.sleep(.2)
            raise TimeoutError(label)
        finally:
            if cleanup:
                self.phase_deadline = previous_deadline

    def record_closeout_error(self, label, error, stage, reason=None):
        diagnostic = closeout_diagnostic(error, stage, reason)
        try:
            write(self.logdir.parent / (label + '.json'), dict(status='unconfirmed', **diagnostic))
        except Exception:
            # Evidence-storage failure must not replace the primary exception.
            print(json.dumps(dict(diagnostic_write='failed', **diagnostic)), file=sys.stderr, flush=True)

    def run_journey(self):
        self.control_attempted = False
        try:
            self.run_recovery()
        except BaseException:
            if self.control_attempted:
                stage, reason = 'control_read', None
                try:
                    control = self.row()
                    reason = control.get('reason')
                    write(self.logdir.parent / 'failure-control.json', control)
                    stage = 'pause'
                    status = (dict(status='already_stopped', reason=reason) if control['state'] in {'paused','stopped'}
                        else self.call('progression_command', dict(command='pause')))
                    write(self.logdir.parent / 'failure-pause.json', status)
                    # Leave the daemon alive until its native terminal witness
                    # releases the old writer; closing immediately can strand it.
                    stage = 'writer_release'
                    self.wait_row(lambda row: row['state'] in {'paused','stopped'} and not row['host_json'],
                        'failure-released', timeout=getattr(self, 'case_config', {}).get('stage_timeout_seconds',90), cleanup=True)
                except Exception as error:
                    self.record_closeout_error('failure-closeout-error', error, stage, reason)
            raise

    def run_recovery(self):
        value = self.initialize_host(check_native=False)
        prior=self.root/'prior-native-turns.json'
        if prior.exists():
            write(self.logdir.parent/'prior-native-terminal.json', verify_prior_turns(self.rpc,read(prior)))
        closeout_only=self.case_config.get('closeout_only',False)
        arguments=CLOSEOUT_ARGUMENTS if closeout_only else INGEST_ARGUMENTS
        if closeout_only and self.case_config.get('text'):
            arguments = {**arguments, 'text': self.case_config['text']}
        self.await_loop_authorization(value, objective_name=arguments['name'], text=arguments['text'])
        original = self.row()
        if original['state'] not in {'idle','paused','stopped'} or original['host_json']:
            raise RuntimeError('recovery_requires_quiescent_original_goal')
        if original.get('checkpoint_json') and json.loads(original['checkpoint_json']).get('started_at') is not None:
            raise RuntimeError('use_pre_progression_snapshot; existing_goal_budget_must_not_be_reset')
        write(self.logdir.parent / 'original-control.json', original)
        original_runs = self.runs_snapshot()
        self.status('scientific_turn', scenario='root_closeout' if closeout_only else 'root_control_recovery')
        # The supervisor submits control commands through the native MCP client;
        # it never fabricates a platform identity or writes control databases.
        (self.root / 'model-submission-started').touch(exist_ok=False)
        self.control_attempted = True
        self.call('progression_command', dict(command='start', mode='background', objective_name=arguments['name']))
        started=self.wait_row(running_turn, 'started')
        if not closeout_only:
            self.pause_and_restart()
        self.finish_control(original_runs,started if closeout_only else None)

    def pause_and_restart(self):
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

    def finish_control(self,original_runs,started=None):
        # Reconnection alone is not successful progression. Observe the original
        # Root actually finish this read-only goal after the service restart.
        completed=self.wait_row(naturally_completed,'recovered-completed')
        if started is not None:
            identity=json.loads(started['host_json'])
            evidence=verify_prior_turns(self.rpc,[dict(thread_id=identity['thread_id'],
                turn_id=json.loads(started['checkpoint_json'])['turn_id'])])
            write(self.logdir.parent/'native-completed.json',evidence)
            if evidence[0]['status']!='completed' or json.loads(completed['checkpoint_json'])['rounds']!=1:
                raise RuntimeError('closeout_requires_one_naturally_completed_turn')
            # Observe natural release before takeover can cause it itself.
            self.wait_row(lambda row: row['state'] in {'paused','stopped'} and not row['host_json'],
                'closeout-released', timeout=getattr(self,'case_config',{}).get('stage_timeout_seconds',90),
                cleanup=True)
        self.call('progression_command', dict(command='takeover'))
        self.wait_row(lambda row: row['mode']=='interactive' and row['host_json'] is None, 'taken-over')
        status = self.call('progression_status', {})
        if not status['can_schedule'] or self.runs_snapshot() != original_runs:
            raise RuntimeError('takeover_or_no_new_science_invariant_failed')
        self.call('progression_command', dict(command='stop'))
        final = self.call('progression_status', {})
        write(self.logdir.parent / 'summary.json', dict(status='root_control_passed',
            b6_passed=False, observed_native_journey=True, scenario='root_closeout' if started is not None else 'root_control_recovery',
            checks=({'automatic_recovery':'passed'} if started is None else dict(
                natural_completion='passed',takeover='passed',writer_release='passed',state_preserved='passed')),
            pause=started is None, resume=started is None, daemon_restart=started is None, exact_root_recovered=started is None,
            takeover=True, new_runs=0, progression=final,
            unverified=['late old-root write rejection with live native request',
                'Worker/helper crash survival', 'manual/autonomous token comparison',
                'formal deployment rollback', 'complete detached resource coverage']))
        print('原生 Root 控制旅程通过；未创建科学任务，仍不代表 B6 全项通过。', flush=True)
