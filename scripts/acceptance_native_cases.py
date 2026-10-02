"""Serial native acceptance cases. Scientific content is always authored by Workers."""
import json
import sys
import time

try:
    from scripts.accept_progression_recovery import RecoveryJourney
    from scripts.b6_evidence import rows, run_snapshot, participants, sealed_outputs, read, write, verify_prior_turns, usage_report, budget_assessment
except ModuleNotFoundError:
    from accept_progression_recovery import RecoveryJourney
    from b6_evidence import rows, run_snapshot, participants, sealed_outputs, read, write, verify_prior_turns, usage_report, budget_assessment


AUTHORITY_OBJECTIVE='只读旧实例一个小页封存成果，保留限制并通过 progression_report 简短交接。禁止创建科研任务、助手或外部作业。'


def recorded_control_call(root, writer, name, arguments):
    """Replay a recorded transport identity at the control socket, without a model.

    This is control-boundary fault injection, NOT a resumed native MCP session.
    A resumed native thread may create a new proxy with no instance binding.
    """
    from scidiscovery.artifact_agent.interfaces.mcp_proxy import SCHEDULER_PROXY_FIELD
    from scidiscovery.plugin_runtime.transport import forward_request
    identity=json.loads(writer['host_json'])
    if identity['platform_session']!=identity['thread_id']:
        raise ValueError('recorded_writer_is_not_root')
    bound=rows(root,'scheduler-bindings',
        'SELECT instance_id FROM scheduler_sessions WHERE session_key=?',(writer['owner_session'],))
    if bound!=[{'instance_id':writer['instance_id']}]:
        raise ValueError('recorded_writer_binding_changed')
    request=dict(jsonrpc='2.0',id='authority-replay',method='tools/call',
        params=dict(name='scid_call',arguments=dict(name=name,arguments=arguments),
            _meta={'x-codex-turn-metadata':dict(session_id=identity['platform_session'],thread_id=identity['thread_id'])}))
    request[SCHEDULER_PROXY_FIELD]=writer['owner_session']
    return forward_request(root/'control.sock',json.dumps(request).encode(),timeout=10)


def check_stale_writer(root, writer, output):
    """Require active new ownership, retained read binding and the exact denial."""
    current=rows(root,'scheduler-bindings','SELECT * FROM scheduler_progression WHERE instance_id=?',
        (writer['instance_id'],))[0]
    if (current['state']!='active' or current['mode']!='interactive' or current['host_json']
            or current['owner_session']==writer['owner_session']):
        raise RuntimeError('takeover_not_established')
    read_reply=recorded_control_call(root,writer,'instance_current',{})
    result=read_reply.get('result',{}) if read_reply else {}
    value=result.get('structuredContent')
    if value is None and not result.get('isError') and result.get('content'):
        value=json.loads(result['content'][0]['text'])
    if not isinstance(value,dict) or value.get('state')!='active':
        raise RuntimeError('old_writer_read_binding_unavailable')
    before=rows(root,'scheduler-bindings','SELECT * FROM scheduler_bindings WHERE instance=? ORDER BY namespace,name',
        (writer['instance_id'],))
    reply=recorded_control_call(root,writer,'artifact_ingest_text',
        dict(name='acceptance.stale-write',text='must be rejected',on_conflict='reject'))
    write(output/'stale-write-reply.json',reply)
    error=(reply or {}).get('error',{})
    denied=(error.get('code')==-32000 and error.get('message')==
        'SchedulerInstanceConflict: Scheduling is paused or owned by another session; use an explicit control command.')
    after=rows(root,'scheduler-bindings','SELECT * FROM scheduler_bindings WHERE instance=? ORDER BY namespace,name',
        (writer['instance_id'],))
    if after!=before:
        raise RuntimeError('stale_write_changed_bindings')
    return 'passed' if denied else 'not_observed' if error else 'failed'


class NativeCaseJourney(RecoveryJourney):
    def observe_background(self, control, current):
        """Bounded external observations on the existing acceptance poll loop."""
        if control.get('instance_id') != self.instance or control.get('mode') != 'background':
            raise RuntimeError('background_observation_scope_mismatch')
        checkpoint = json.loads(control.get('checkpoint_json') or '{}')
        host = json.loads(control.get('host_json') or 'null')
        owner = {key:host.get(key) for key in ('platform_session', 'thread_id')} if isinstance(host, dict) else None
        admitted = {v['run_id'] for v in checkpoint.get('admissions', {}).values() if v.get('run_id')}
        snapshot = dict(version=1, source='external_acceptance_observation', instance_id=self.instance,
            objective_ref=json.loads(control.get('objective_ref_json') or 'null'), owner=owner,
            mode=control['mode'], state=control.get('state'), reason=control.get('reason'),
            phase=checkpoint.get('phase'), runtime_status=checkpoint.get('runtime_status'),
            turn_id=checkpoint.get('turn_id'), rounds=checkpoint.get('rounds'),
            native_completion=checkpoint.get('native_completion'),
            report_completed=(checkpoint.get('report') or {}).get('completed') is True,
            runs=[dict(run_id=v['run_id'], state=v['state'], admitted=v['run_id'] in admitted,
                output_ref=json.loads(v['output_ref_json']) if v.get('output_ref_json') else None)
                for v in sorted(current, key=lambda v:v['run_id'])])
        if snapshot == getattr(self, '_last_background_snapshot', None) or getattr(self, '_background_truncated', False):
            return False
        path = self.logdir.parent/'background-observations.jsonl'
        max_records = self.case_config['max_observed_runs']*(self.case_config['progression']['max_rounds']+2)*4
        max_bytes = min(self.limits['log_bytes'], self.resources['protocol_frame_bytes'])
        count = getattr(self, '_background_records', 0)
        encoded = (json.dumps(dict(snapshot, elapsed_seconds=time.monotonic()-self.case_started_at),
            ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n').encode()
        size = path.stat().st_size if path.exists() else 0
        if count >= max_records or size+len(encoded) > max_bytes:
            self._background_truncated = True
            write(self.logdir.parent/'background-observation-coverage.json', dict(status='partial',
                reason='record_limit' if count >= max_records else 'byte_limit', records=count, bytes=size,
                max_records=max_records, max_bytes=max_bytes, scope='external acceptance polling; no native tool trace'))
            return False
        with path.open('ab') as stream:
            stream.write(encoded)
        self._background_records = count+1
        self._last_background_snapshot = snapshot
        return True

    def check_case_budget(self, workers, helpers, *, final=False):
        budget = self.case_config.get('budget')
        now = time.monotonic()
        if not budget or (not final and now < getattr(self, '_next_budget_sample', 0)):
            return
        self._next_budget_sample = now + budget['sample_seconds']
        self.save_usage()
        write(self.logdir.parent/'started-threads.json', sorted(self.started_threads))
        control = self.row() if self.case_config['scenario'] == 'autonomous' else None
        usage = usage_report(self.logdir.parent, workers, helpers, control)
        observation = budget_assessment(usage, budget['session'], now - self.case_started_at)
        write(self.logdir.parent/('budget-final.json' if final else 'budget-observation.json'), observation)
        self.case_checks['budget'] = observation['status']
        if observation['reached']:
            raise RuntimeError('acceptance_session_budget_exhausted:'+','.join(observation['reached']))
        if final and observation['status'] != 'passed':
            raise RuntimeError('acceptance_final_budget_unconfirmed')

    def run_journey(self):
        self.control_attempted = False
        try:
            self.run_case()
        finally:
            original_failure = sys.exc_info()[0] is not None
            stage, reason = 'control_read', None
            try:
                if self.control_attempted:
                    control = self.row()
                    reason = control.get('reason')
                    write(self.logdir.parent/'terminal-control.json', control)
                    # Already stopped by control: wait for release without replacing
                    # budget_exhausted/host_fault/goal_completed with user_paused.
                    stage = 'pause'
                    if control['state'] not in {'paused', 'stopped'}:
                        result = self.call('progression_command', dict(command='pause'))
                    else:
                        result = dict(status='already_stopped', reason=control.get('reason'))
                    write(self.logdir.parent/'closeout-pause.json', result)
                    stage = 'writer_release'
                    self.wait_row(lambda r:r['state'] in {'paused','stopped'} and not r['host_json'],
                        'closeout-released',timeout=self.case_config['stage_timeout_seconds'],cleanup=True)
                if hasattr(self, 'case_started_at'):
                    stage = 'sealed_evidence'
                    before = {v['run_id'] for v in self.before_runs}
                    current = [v for v in run_snapshot(self.root) if v['run_id'] not in before]
                    workers, helpers = participants(self.root, [v['run_id'] for v in current])
                    if current and all(v['state'] == 'completed' for v in current):
                        write(self.logdir.parent/'sealed-evidence.json', sealed_outputs(self.root, current))
                        write(self.logdir.parent/'participants.json', dict(workers=workers, helpers=helpers))
                        self.case_checks['sealed_delivery'] = 'passed' if self.case_config.get('multi_task') or len(current) == 1 else 'failed'
            except Exception as error:
                self.record_closeout_error('closeout-error', error, stage, reason)
                if not original_failure:
                    raise RuntimeError('background_closeout_unconfirmed') from error
            finally:
                if hasattr(self, 'case_started_at'):
                    active_failure = sys.exc_info()[0] is not None or original_failure
                    try:
                        current = [v for v in run_snapshot(self.root) if v['run_id'] not in {b['run_id'] for b in self.before_runs}]
                        workers, helpers = participants(self.root, [v['run_id'] for v in current])
                        self.check_case_budget(workers, helpers, final=True)
                    except Exception as error:
                        self.record_closeout_error('budget-final-error', error, 'budget_final', reason)
                        if not active_failure:
                            raise

    def background_finished(self, control, all_sealed):
        reason = control.get('reason')
        if reason in {'host_fault','root_turn_failed','budget_exhausted','resource_limit','submission_unknown'}:
            raise RuntimeError('background_stopped:'+reason)
        if control['state'] not in {'paused','stopped'}:
            return False
        if reason != 'goal_completed':
            raise RuntimeError('background_stopped:'+str(reason))
        checkpoint = json.loads(control.get('checkpoint_json') or '{}')
        if checkpoint.get('native_completion') != 'completed' or checkpoint.get('turn_id'):
            raise RuntimeError('background_native_completion_unconfirmed')
        self.case_checks['native_completion'] = 'passed'
        if not all_sealed:
            raise RuntimeError('background_completed_without_sealed_delivery')
        return True

    def run_case(self):
        case = self.case_config
        checks = {}
        self.case_checks = checks
        value = self.initialize_host(check_native=False)
        prior=self.root/'prior-native-turns.json'
        if prior.exists():
            write(self.logdir.parent/'prior-native-terminal.json',
                verify_prior_turns(self.rpc,read(prior)))
        objective=case['text']
        scope = ('根据上一项完整任务的封存结论选择下一项，每次只派发一个负责人。无需为了数量重复无价值的任务。'
                 if case.get('multi_task') else '只派发一个负责人。')
        common=('这是隔离验收中的科学任务。使用既有完整任务合同，不拆成 Root 子步骤。'
            '科学内容必须来自 Worker 封存结果。'+scope+'不运行 TCAD、网络或外部作业。'
            '负责人可以使用本任务明确要求的助手；否则不使用助手。不要人为睡眠。\n'+objective)
        if case['scenario']=='authority':
            common=AUTHORITY_OBJECTIVE
        objective_name='acceptance.authority' if case['scenario']=='authority' else 'acceptance.objective'
        self.await_loop_authorization(value, objective_name=objective_name, text=common)
        self.before_runs=run_snapshot(self.root)
        write(self.logdir.parent/'before-runs.json',self.before_runs)
        self.status('scientific_turn',scenario=case['scenario'])
        self.case_started_at = time.monotonic()
        (self.root/'model-submission-started').touch(exist_ok=False)
        if case['scenario']=='authority':
            return self.authority()
        if case['scenario']=='autonomous':
            self.control_attempted=True
            self.call('progression_command',dict(command='start',mode='background',objective_name='acceptance.objective'))
        else:
            self.control_attempted=True
            self.call('progression_command',dict(command='start',mode='interactive'))
            self.root_host.start_turn('请确认当前实例，复用 acceptance.objective 原文及已确认 loop 完成完整任务，等待负责人封存后回读，最终简短报告。\n'+common)
        baseline={item['run_id'] for item in self.before_runs}
        injected=None
        while True:
            self.pump()
            current=[v for v in run_snapshot(self.root) if v['run_id'] not in baseline]
            if len(current)>case['max_observed_runs']:
                raise RuntimeError('acceptance_run_scope_exceeded')
            control = self.row() if case['scenario']=='autonomous' else None
            if control is not None:
                self.observe_background(control, current)
            workers,helpers=participants(self.root,[v['run_id'] for v in current])
            self.check_case_budget(workers, helpers)
            if case['scenario']=='helper-crash' and injected is None:
                for helper in helpers:
                    if helper['thread_id'] and helper['admitted_at'] and not helper['released_at']:
                        native=self.rpc('thread/read',dict(threadId=helper['thread_id'],includeTurns=True))['thread']
                        if native.get('id')==helper['thread_id'] and any(t['status']=='inProgress' for t in native.get('turns',[])):
                            injected=dict(threads=[v['thread_id'] for v in [*workers,*helpers] if v['thread_id']],
                                helper_thread=helper['thread_id'], turn_ids=[t['id'] for t in native['turns'] if t['status']=='inProgress'])
                            self.crash_daemon()
                            checks['fault_injected']='passed'
                            write(self.logdir.parent/'fault-participants.json',injected)
                            break
            if any(v['state'] in {'failed','timed_out','cancelled'} for v in current):
                checks['sealed_delivery']='failed'
                raise RuntimeError('accepted_worker_failed')
            all_sealed=bool(current) and all(v['state']=='completed' for v in current)
            if case['scenario']=='autonomous':
                if self.background_finished(control, all_sealed):
                    self.check_case_budget(workers, helpers, final=True)
                    break
            elif self.root_host.completion:
                if self.root_host.completion['status']!='completed':
                    raise RuntimeError('reader_root_not_completed')
                if all_sealed:
                    checks['native_completion']='passed'
                    self.check_case_budget(workers, helpers, final=True)
                    break
                if not current:raise RuntimeError('no_scientific_task_created')
            time.sleep(case['poll_seconds'])
        evidence=sealed_outputs(self.root,current)
        write(self.logdir.parent/'sealed-evidence.json',evidence)
        write(self.logdir.parent/'participants.json',dict(workers=workers,helpers=helpers))
        checks['sealed_delivery']='passed' if (bool(current) if case.get('multi_task') else len(current)==1) else 'failed'
        if case.get('multi_task'):
            # A correct early stop is useful science, but is not an observation
            # of a multi-task stagnation trigger. Human review must distinguish it.
            checks['scientific_correction']='not_observed'
        if case['scenario'].startswith('helper'):
            observed=[]
            for helper in helpers:
                if helper['thread_id']:
                    native=self.rpc('thread/read',dict(threadId=helper['thread_id'],includeTurns=True))['thread']
                    turns=native.get('turns',[])
                    terminal=(native.get('id')==helper['thread_id'] and bool(turns)
                        and all(t['status'] in {'completed','failed','interrupted'} for t in turns))
                    observed.append(dict(thread_id=helper['thread_id'],terminal=terminal,
                        completed=any(t['status']=='completed' for t in turns),
                        turns={t['id']:t['status'] for t in turns}))
            checks['helper_terminal']='passed' if observed and all(v['terminal'] and v['completed'] for v in observed) else 'not_observed'
            checks['owner_integration']='not_observed'  # Requires sealed scientific-content review.
            write(self.logdir.parent/'helper-native-status.json',observed)
            if case['scenario']=='helper-crash':
                after=[v['thread_id'] for v in [*workers,*helpers] if v['thread_id']]
                same = injected and sorted(injected['threads'])==sorted(after)
                exact = next((v for v in observed if injected and v['thread_id']==injected['helper_thread']), None)
                survived = exact and all(exact['turns'].get(t)=='completed' for t in injected['turn_ids'])
                checks['same_participants']='passed' if same and survived else 'failed' if injected else 'not_observed'
        else:
            checks['quality']='not_observed'
        self.save_usage()
        write(self.logdir.parent/'summary.json',dict(status='evidence_ready',checks=checks,b6_passed=False))

    def crash_daemon(self):
        daemon=next(p for p in self.children if 'scidiscovery.artifact_agent.interfaces.mcp_daemon' in p.args)
        command=daemon.args
        daemon.kill();daemon.wait(timeout=5);self.children.remove(daemon)
        self.launch(command,'daemon-after-crash')

    def authority(self):
        self.control_attempted=True
        self.call('progression_command',dict(command='start',mode='background',objective_name='acceptance.authority'))
        active=self.wait_row(lambda r:bool(r.get('host_json')) and r['state']=='active','old-writer',timeout=self.case_config['stage_timeout_seconds'])
        self.call('progression_command',dict(command='takeover'))
        self.wait_row(lambda r:r['mode']=='interactive' and not r['host_json'],'taken-over',timeout=self.case_config['stage_timeout_seconds'])
        self.case_checks['takeover']='passed'
        self.case_checks['stale_write_rejected']=check_stale_writer(self.root,active,self.logdir.parent)
        write(self.logdir.parent/'authority-scope.json',dict(takeover='native_host',
            stale_write='recorded_transport_replay_at_control_socket',native_connection_reuse='not_verified'))
        if run_snapshot(self.root)!=self.before_runs:raise RuntimeError('authority_test_created_science')
        self.call('progression_command',dict(command='stop'))
        self.control_attempted=False
        write(self.logdir.parent/'summary.json',dict(status='evidence_ready',checks=self.case_checks,b6_passed=False))
