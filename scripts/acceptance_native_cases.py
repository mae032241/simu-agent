"""Serial native acceptance cases. Scientific content is always authored by Workers."""
import json
import sys
import time

try:
    from scripts.accept_progression_recovery import RecoveryJourney
    from scripts.b6_evidence import rows, run_snapshot, participants, sealed_outputs, read, write
except ModuleNotFoundError:
    from accept_progression_recovery import RecoveryJourney
    from b6_evidence import rows, run_snapshot, participants, sealed_outputs, read, write


def verify_prior_turns(rpc, references):
    """No new model work until the interrupted acceptance's exact turns ended."""
    evidence=[]
    for reference in references:
        thread=rpc('thread/read',dict(threadId=reference['thread_id'],includeTurns=True))['thread']
        turn=next((v for v in thread.get('turns',[]) if v['id']==reference['turn_id']),None)
        if thread.get('id')!=reference['thread_id'] or turn is None:
            raise RuntimeError('prior_native_turn_not_found')
        evidence.append(dict(**reference,status=turn['status']))
        if turn['status'] not in {'completed','failed','interrupted'}:
            raise RuntimeError('prior_native_turn_not_terminal; do_not_start_another_case')
    return evidence


class NativeCaseJourney(RecoveryJourney):
    def run_journey(self):
        self.control_attempted = False
        try:
            self.run_case()
        finally:
            original_failure = sys.exc_info()[0] is not None
            if self.control_attempted:
                try:
                    result = self.call('progression_command', dict(command='pause'))
                    write(self.logdir.parent/'closeout-pause.json', result)
                    self.wait_row(lambda r:r['state'] in {'paused','stopped'} and not r['host_json'],
                        'closeout-released',timeout=self.case_config['stage_timeout_seconds'])
                except Exception as error:
                    write(self.logdir.parent/'closeout-pause.json', dict(status='unconfirmed', diagnostic=type(error).__name__))
                    if not original_failure:
                        raise RuntimeError('background_closeout_unconfirmed') from error

    def run_case(self):
        case = self.case_config
        checks = {}
        self.case_checks = checks
        value = self.initialize_host(check_native=False)
        prior=self.root/'prior-native-turns.json'
        if prior.exists():
            write(self.logdir.parent/'prior-native-terminal.json',
                verify_prior_turns(self.rpc,read(prior)))
        self.status('awaiting_user', management_url=value['management_url'])
        print('请选择已有实例 ' + case['instance'] + '：' + value['management_url'], flush=True)
        while value.get('state')=='unbound':
            self.pump(); time.sleep(case['poll_seconds']); value=self.current_instance()
        if value.get('state')!='active' or value.get('name')!=case['instance']:
            raise RuntimeError('wrong_existing_instance')
        self.instance=rows(self.root,'scheduler-bindings','SELECT instance_id FROM scheduler_instances WHERE name=?',(value['name'],))[0]['instance_id']
        original=self.row()
        if original['state']!='idle':
            raise RuntimeError('case_requires_pre_progression_snapshot; do_not_reset_existing_budget')
        self.before_runs=run_snapshot(self.root)
        write(self.logdir.parent/'before-runs.json',self.before_runs)
        self.status('scientific_turn',scenario=case['scenario'])
        (self.root/'model-submission-started').touch(exist_ok=False)
        if case['scenario']=='authority':
            return self.authority()
        objective=case['text']
        common=('这是隔离验收中的科学任务。使用既有完整任务合同，不拆成 Root 子步骤。'
            '科学内容必须来自 Worker 封存结果。只派发一个负责人，不运行 TCAD、网络或外部作业。'
            '负责人可以使用本任务明确要求的助手；否则不使用助手。不要人为睡眠。\n'+objective)
        if case['scenario']=='autonomous':
            self.call('artifact_ingest_text',dict(name='acceptance.objective',text=common,on_conflict='reject'))
            self.control_attempted=True
            self.call('progression_command',dict(command='start',mode='background',objective_name='acceptance.objective'))
        else:
            self.root_host.start_turn('请确认当前实例，冻结以下原文并完成完整任务，等待负责人封存后回读，最终简短报告。\n'+common)
        baseline={item['run_id'] for item in self.before_runs}
        injected=None
        while True:
            self.pump()
            current=[v for v in run_snapshot(self.root) if v['run_id'] not in baseline]
            if len(current)>case['max_observed_runs']:
                raise RuntimeError('acceptance_run_scope_exceeded')
            workers,helpers=participants(self.root,[v['run_id'] for v in current])
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
                control=self.row()
                if control['state'] in {'paused','stopped'} and all_sealed:
                    break
                if control.get('reason') in {'host_fault','root_turn_failed','budget_exhausted','resource_limit','submission_unknown'}:
                    raise RuntimeError('background_stopped:'+control['reason'])
            elif self.root_host.completion:
                if self.root_host.completion['status']!='completed':
                    raise RuntimeError('reader_root_not_completed')
                if all_sealed:break
                if not current:raise RuntimeError('no_scientific_task_created')
            time.sleep(case['poll_seconds'])
        evidence=sealed_outputs(self.root,current)
        write(self.logdir.parent/'sealed-evidence.json',evidence)
        write(self.logdir.parent/'participants.json',dict(workers=workers,helpers=helpers))
        checks['sealed_delivery']='passed' if len(current)==1 else 'failed'
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
        self.call('artifact_ingest_text',dict(name='acceptance.authority',text='只读旧实例一个小页封存成果，保留限制并通过 progression_report 简短交接。禁止创建科研任务、助手或外部作业。',on_conflict='reject'))
        self.control_attempted=True
        self.call('progression_command',dict(command='start',mode='background',objective_name='acceptance.authority'))
        active=self.wait_row(lambda r:bool(r.get('host_json')) and r['state']=='active','old-writer',timeout=self.case_config['stage_timeout_seconds'])
        old=json.loads(active['host_json'])
        self.call('progression_command',dict(command='takeover'))
        self.wait_row(lambda r:r['mode']=='interactive' and not r['host_json'],'taken-over',timeout=self.case_config['stage_timeout_seconds'])
        self.case_checks['takeover']='passed'
        # A real client resumes only the recorded thread to query its original MCP
        # route. No model turn, fabricated scheduler key or direct broker request.
        thread=self.rpc('thread/resume',dict(threadId=old['thread_id'],excludeTurns=True))['thread']
        if (thread['id'],thread.get('sessionId')) != (old['thread_id'],old['platform_session']):
            raise RuntimeError('old_writer_native_identity_changed')
        reply=self.rpc('mcpServer/tool/call',dict(threadId=old['thread_id'],server='scidiscovery',tool='scid_call',
            arguments=dict(name='artifact_ingest_text',arguments=dict(name='acceptance.stale-write',text='must be rejected',on_conflict='reject')),
            _meta={'x-codex-turn-metadata':dict(session_id=old['platform_session'],thread_id=old['thread_id'])}))
        write(self.logdir.parent/'stale-write-reply.json',reply)
        # An unbound/transport/schema error is not proof of ownership enforcement.
        raw=json.dumps(reply)
        denied=bool(reply.get('isError')) and 'Scheduling is paused or owned by another session' in raw
        self.case_checks['stale_write_rejected']='passed' if denied else 'not_observed' if reply.get('isError') else 'failed'
        if run_snapshot(self.root)!=self.before_runs:raise RuntimeError('authority_test_created_science')
        self.call('progression_command',dict(command='stop'))
        self.control_attempted=False
        write(self.logdir.parent/'summary.json',dict(status='evidence_ready',checks=self.case_checks,b6_passed=False))
