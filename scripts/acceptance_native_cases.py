"""Serial native acceptance cases. Scientific content is always authored by Workers."""
import hashlib
import json
import sys
import time

try:
    from scripts.accept_progression_recovery import RecoveryJourney
    from scripts.b6_evidence import rows, run_snapshot, participants, sealed_outputs, read, write, verify_prior_turns, usage_report, budget_assessment, batch_scientific_facts, BatchMaterialReader, batch_payloads, P6S_PREDICTION_PROTOCOL
except ModuleNotFoundError:
    from accept_progression_recovery import RecoveryJourney
    from b6_evidence import rows, run_snapshot, participants, sealed_outputs, read, write, verify_prior_turns, usage_report, budget_assessment, batch_scientific_facts, BatchMaterialReader, batch_payloads, P6S_PREDICTION_PROTOCOL


AUTHORITY_OBJECTIVE='只读旧实例一个小页封存成果，保留限制并通过 progression_report 简短交接。禁止创建科研任务、助手或外部作业。'
NEUTRAL_CHANGED_CONDITION_QUESTION='请依据此前封存记录说明，是否值得再提高原三个采样点上的参数拟合精度；并判断工况变化后应重新检验哪些结论。'


def case_objective(case):
    scope = ('根据上一项完整任务的封存结论选择下一项，每次只派发一个负责人。无需为了数量重复无价值的任务。'
             if case.get('multi_task') else '只派发一个负责人。')
    return ('这是隔离验收中的科学任务。使用既有完整任务合同，不拆成 Root 子步骤。'
            '科学内容必须来自 Worker 封存结果。'+scope+'不运行 TCAD、网络或外部作业。'
            '负责人可以使用本任务明确要求的助手；否则不使用助手。不要人为睡眠。\n'+case['text']
            + ('\n'+P6S_PREDICTION_PROTOCOL if case.get('batch_delivery') else ''))


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
    def record_batch_closeout(self, control):
        if not getattr(self, 'case_config', {}).get('batch_delivery'):
            return
        result = dict(science_passed=False, reason=control.get('reason'),
            post_model_restart_supported=False)
        try:
            cp = self._batch_scope(control)
            batches = batch_payloads(self.case_config['batch_delivery'])[1:]
            saved, omitted = [], []
            for batch in batches:
                name = 'acceptance.p6s.'+batch['name']
                text = batch['text'] + ('\n'+NEUTRAL_CHANGED_CONDITION_QUESTION if batch['name']=='B_changed_condition' else '')
                ack = self._batch_ack(cp, name, text)
                (saved if ack else omitted).append(dict(name=name, artifact_ref=ack))
            result.update(status='complete' if not omitted else 'omitted', saved=saved, omitted=omitted,
                scope=self._delivery_scope)
        except Exception as error:
            result.update(status='unknown', error=str(error))
        write(self.logdir.parent/'batch-delivery-closeout.json', result)

    def _batch_scope(self, control):
        cp = json.loads(control.get('checkpoint_json') or '{}')
        scope = dict(instance=self.instance, goal=json.loads(control.get('objective_ref_json') or 'null'),
            loop=cp.get('current_loop_id'))
        if (control.get('instance_id') != self.instance or control.get('mode') != 'background'
                or not scope['goal'] or not scope['loop']):
            raise RuntimeError('batch_scope_unconfirmed')
        authorization = self.logdir.parent/'loop-authorization.json'
        if not authorization.exists() or read(authorization)['id'] != scope['loop']:
            raise RuntimeError('batch_loop_authorization_changed')
        objective_name = read(authorization)['objective_name']
        bound = rows(self.root, 'scheduler-bindings',
            "SELECT object_id FROM scheduler_bindings WHERE instance=? AND namespace='artifact' AND name=?",
            (self.instance, objective_name))
        if control.get('objective_name') != objective_name or bound != [{'object_id':scope['goal']['artifact_id']}]:
            raise RuntimeError('batch_authorized_goal_changed')
        if hasattr(self, '_delivery_scope') and self._delivery_scope != scope:
            raise RuntimeError('batch_goal_or_loop_changed')
        self._delivery_scope = scope
        return cp

    def _batch_ack(self, cp, name, text):
        matching = [v for v in cp.get('messages', []) if v.get('name') == name]
        if not matching:
            return None
        if len(matching) != 1 or matching[0].get('fingerprint') != hashlib.sha256(text.encode()).hexdigest():
            raise RuntimeError('batch_ack_conflict')
        ref = matching[0]['artifact_ref']
        reader = BatchMaterialReader(self.root, self.instance, [])
        from scidiscovery.artifact_agent.schema.refs import ArtifactRef
        envelope = reader.verify(ArtifactRef.model_validate(ref))
        if envelope.size_bytes > 65536:
            raise RuntimeError('batch_ack_original_limit')
        raw = (self.root/'state/artifacts/sha256'/ref['sha256'][:2]/ref['sha256'][2:]).read_bytes()
        bound = rows(self.root, 'scheduler-bindings',
            "SELECT object_id FROM scheduler_bindings WHERE instance=? AND namespace='artifact' AND name=?",
            (self.instance, name))
        if (envelope.size_bytes > 65536 or raw != text.encode() or bound != [{'object_id':ref['artifact_id']}]):
            raise RuntimeError('batch_ack_original_mismatch')
        return ref

    def _observe_batch_rotation(self, control, cp):
        host = json.loads(control.get('host_json') or 'null')
        boundary = cp.get('rotation_boundary') or {}
        record = cp.get('usage_records', {}).get((host or {}).get('thread_id'), {})
        # This boundary is written by prepare_host_rotation after terminal-old-
        # writer checks and revocation. A generation change alone is insufficient.
        if (control.get('state') == 'pending' and control.get('owner_session') is None
                and cp.get('phase') == 'prepared' and cp.get('native_action') == 'root_rotation'
                and cp.get('native_completion') == 'completed' and cp.get('turn_id') is None
                and host and host.get('platform_session') == host.get('thread_id')
                and record.get('role') == 'root' and record.get('owner') == self.instance
                and record.get('loop_id') == self._delivery_scope['loop'] and record.get('retired') is True
                and record.get('scheduler_session') and boundary.get('unchecked') == 0
                and boundary.get('unknown') == 0 and boundary.get('checked', -1) >= 0 and not boundary.get('reasons')):
            self._batch_rotation_boundary = dict(old=host, old_session=record['scheduler_session'],
                generation=control['generation'], boundary=boundary, scope=self._delivery_scope)
        prior = getattr(self, '_batch_rotation_boundary', None)
        if (prior and control.get('state') == 'active' and cp.get('native_action') is None
                and host and host.get('platform_session') == host.get('thread_id')
                and host != prior['old'] and control.get('owner_session') != prior['old_session']
                and control.get('generation') == prior['generation']+1
                and record.get('role') == 'root' and record.get('owner') == self.instance
                and record.get('loop_id') == prior['scope']['loop']
                and record.get('scheduler_session') == control.get('owner_session')
                and record.get('scheduler_session')):
            self._batch_rotation_proof = dict(**prior, new=host, new_session=control['owner_session'])

    def deliver_batches(self, control):
        """One bounded poll hook; checkpoint.messages is the sole delivery ack.

        Cached proof is a same-process observation, not a restart ledger. Missing
        prepared-rotation or precommit observation remains unknown on re-entry.
        """
        delivery = self.case_config.get('batch_delivery')
        if delivery is None:
            return
        cp = self._batch_scope(control)
        self._observe_batch_rotation(control, cp)
        batches = batch_payloads(delivery)[1:]
        texts = [v['text'] + ('\n'+NEUTRAL_CHANGED_CONDITION_QUESTION if v['name']=='B_changed_condition' else '') for v in batches]
        names = ['acceptance.p6s.'+v['name'] for v in batches]
        acks = [self._batch_ack(cp, name, text) for name, text in zip(names, texts)]
        if any(acks[i] is not None and acks[i-1] is None for i in range(1,3)):
            raise RuntimeError('batch_ack_order_unknown')
        elapsed = time.monotonic()-self.case_started_at
        index = next((i for i, ack in enumerate(acks) if ack is None), 3)
        observation = dict(scope=self._delivery_scope, saved=[name for name, ack in zip(names, acks) if ack],
            next_batch=batches[index]['name'] if index<3 else None, elapsed_seconds=elapsed,
            science_passed=False, post_model_restart_supported=False,
            releases=getattr(self, '_batch_release_observations', []),
            prediction=getattr(self, '_batch_prediction', None),
            prediction_binding=getattr(self, '_batch_prediction_binding', None), rotation=getattr(self, '_batch_rotation_proof', None))
        if index == 3 or control.get('state') != 'active' or elapsed < (1500,3300,5100)[index]:
            observation['status'] = 'complete' if index==3 else 'waiting'
            observation['reason'] = 'saved' if index==3 else 'control_inactive' if control.get('state')!='active' else 'release_time'
            write(self.logdir.parent/'batch-delivery-observation.json', observation)
            return
        prediction = getattr(self, '_batch_prediction', None)
        facts = batch_scientific_facts(self.root, control, max_runs=int(self.case_config['max_observed_runs']),
            discrimination=acks[0], validation=acks[1], prediction=prediction)
        ready = bool(facts['first_results']) if index==0 else False
        reason = 'first_completed_experiment_unknown' if index==0 else 'adopted_prediction_unknown'
        if index == 1 and not facts['declaration_coverage_complete']:
            reason = 'adopted_prediction_coverage_unknown'
        elif index == 1 and len(facts['declarations']) == 1:
            self._batch_prediction_binding = facts['declarations'][0]
            prediction = self._batch_prediction_binding['artifact_ref']
            self._batch_prediction = prediction
            ready = True
        elif index == 1 and len(facts['declarations']) > 1:
            reason = 'multiple_adopted_predictions_no_declared_replacement'
        if index == 2:
            ready = bool(prediction and facts['comparisons'] and getattr(self, '_batch_rotation_proof', None))
            reason = ('prediction_release_binding_unavailable' if not prediction or not getattr(self, '_batch_prediction_binding', None)
                else 'adopted_comparison_unknown' if not facts['comparisons'] else 'safe_rotation_unknown')
            ready = ready and bool(getattr(self, '_batch_prediction_binding', None))
        observation.update(status='eligible' if ready else 'waiting',
            reason='exact_sealed_proof' if ready else reason, facts=facts,
            prediction=prediction, prediction_binding=getattr(self, '_batch_prediction_binding', None),
            rotation=getattr(self, '_batch_rotation_proof', None))
        if not ready:
            write(self.logdir.parent/'batch-delivery-observation.json', observation)
            return
        if getattr(self, '_batch_submission_unknown', False):
            raise RuntimeError('batch_submission_unknown_do_not_replay')
        # Save intent as an observation before the sole public submission. If the
        # reply is lost, only a read of the authoritative checkpoint can resolve it.
        observation.update(status='submitting', name=names[index])
        write(self.logdir.parent/'batch-delivery-observation.json', observation)
        error = None
        try:
            self.call('progression_message', dict(name=names[index], text=texts[index],
                expected_scope=dict(objective_name=control['objective_name'], loop_id=self._delivery_scope['loop'])))
        except Exception as failure:
            error = failure
        try:
            fresh = self.row()
            fresh_cp = self._batch_scope(fresh)
            ack = self._batch_ack(fresh_cp, names[index], texts[index])
        except Exception as failure:
            self._batch_submission_unknown = True
            observation.update(status='unknown', reason='submission_ack_read_unavailable', error=str(failure))
            write(self.logdir.parent/'batch-delivery-observation.json', observation)
            raise RuntimeError('batch_submission_unknown_do_not_replay') from failure
        if ack is None:
            self._batch_submission_unknown = True
            observation.update(status='unknown', reason='submission_without_exact_ack', error=str(error) if error else None)
            write(self.logdir.parent/'batch-delivery-observation.json', observation)
            raise RuntimeError('batch_submission_unknown_do_not_replay') from error
        observation.update(status='saved', artifact_ref=ack)
        # At most three external proof observations, never a submission authority
        # or restart source; saved status still comes exclusively from control.
        releases = getattr(self, '_batch_release_observations', [])
        releases.append(dict(name=names[index], elapsed_seconds=elapsed, artifact_ref=ack,
            facts=facts, prediction=prediction, prediction_binding=getattr(self, '_batch_prediction_binding', None),
            rotation=getattr(self, '_batch_rotation_proof', None)))
        self._batch_release_observations = releases
        observation['releases'] = releases
        write(self.logdir.parent/'batch-delivery-observation.json', observation)

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
                    # Observation failures must never prevent the existing pause
                    # or writer-release cleanup from running.
                    stage = 'batch_closeout'
                    self.record_batch_closeout(control)
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
        common=case_objective(case)
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
            if control is not None:
                self.deliver_batches(control)
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
