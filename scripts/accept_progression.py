"""One bounded real B6 journey: installed daemon/UI, user selection, native Root.

Run: python scripts/accept_progression.py --candidate <prepared-upgrade-candidate>
Reuse an existing instance via probe_root_host_live.py prepare-upgrade first.
This is a foreground supervisor: keep this terminal open. No TCAD or production
state is used. Select/create the exact instance and confirm its frozen loop budget
using the printed UI URL. The foreground supervisor detects confirmation; no
continue command grants permission or refreshes the budget.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import json
import hashlib
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

try:
    from scripts import run_tests as guard
    from scripts.probe_root_host_live import Host, write, host_resources, preflight
except ModuleNotFoundError:
    import run_tests as guard
    from probe_root_host_live import Host, write, host_resources, preflight


def require_existing_instance(root):
    """Validate fresh compatible state; only the user page selects/creates instances."""
    if not (root / 'candidate.json').is_file():
        raise ValueError('Prepare an upgrade candidate from the previous acceptance state '
                         'with probe_root_host_live.py prepare-upgrade first.')
    database = root / 'state/database/scheduler-bindings.sqlite3'
    if not database.is_file():
        raise ValueError('Candidate has no instance database; prepare an upgrade candidate first.')
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] != 9:
            raise ValueError('acceptance_requires_control_schema_9_fresh_state; preserve_old_evidence')
        db.execute('SELECT 1 FROM scheduler_instances LIMIT 1')


def validate_candidate(root, case):
    require_existing_instance(root)
    if not case.get('freeze_identity'):
        raise ValueError('frozen_acceptance_case_required; prepare_with_accept_b6')
    if case['freeze_identity'].get('control_schema') != 9:
        raise ValueError('frozen_control_schema_mismatch')
    candidate = json.loads((root / 'candidate.json').read_text())
    if case['freeze_identity']['candidate_source_commit'] != candidate.get('head'):
        raise ValueError('candidate_source_revision_mismatch')
    if case['candidate_digest'] != guard_digest(candidate):
        raise ValueError('prepared_candidate_changed')
    if case['agent_settings_digest'] != guard_digest(json.loads((root / 'agent-settings.json').read_text())):
        raise ValueError('frozen_agent_settings_changed')
    limits=case['effective_settings']['progression']
    if candidate.get('profile') != dict(model=limits['root_model'], model_reasoning_effort=limits['root_reasoning_effort']):
        raise ValueError('candidate_root_profile_mismatch')


def platform_identity():
    """Freeze CLI version and executable bytes; this command requests no model."""
    executable = shutil.which('codex')
    if not executable:
        raise ValueError('codex_executable_missing')
    executable = Path(executable).resolve()
    version = subprocess.check_output([str(executable), '--version'], text=True, timeout=5).strip()
    if not version:
        raise ValueError('codex_version_missing')
    with executable.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(version=version, executable_sha256=checksum)


def guard_digest(value):
    try:
        from scripts.b6_evidence import digest
    except ModuleNotFoundError:
        from b6_evidence import digest
    return digest(value)


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def wait_state(root, case, *, session=None, allow_managed=False):
    """Read-only model-before-wait boundary; never repairs control ownership."""
    with closing(sqlite3.connect((root/'state/database/scheduler-bindings.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        instance=db.execute('SELECT instance_id FROM scheduler_instances WHERE name=?',(case['instance'],)).fetchone()
        row=db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?',(instance[0],)).fetchone() if instance else None
        binding=db.execute("SELECT object_id FROM scheduler_bindings WHERE instance=? AND namespace='artifact' AND name='acceptance.objective'",(instance[0],)).fetchone() if instance else None
        if not row or not binding:
            raise ValueError('wait_resume_exact_instance_objective_required')
        row=dict(row);checkpoint=json.loads(row['checkpoint_json'])
        if (row['state'] not in {'active','paused'} or row['mode']!='interactive' or row['host_json']
                or checkpoint.get('started_at') is not None
                or checkpoint.get('fault_class') or checkpoint.get('phase') in {'prepared','running','submitted_unknown'}
                or checkpoint.get('admissions') or checkpoint.get('admissions_ref')
                or db.execute('SELECT 1 FROM scheduler_dispatch_intents LIMIT 1').fetchone()
                or (json.loads(row['config_json']) and json.loads(row['config_json']).get('effective')!=case['effective_settings'])):
            raise ValueError('wait_resume_requires_unspent_known_bootstrap')
        if session and (row['requested_by'] not in session or row['owner_session'] not in {*session,None}):
            raise ValueError('wait_resume_bootstrap_owner_changed')
    for name in ('runs','executions'):
        with closing(sqlite3.connect((root/f'state/database/{name}.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute(f'SELECT 1 FROM {name} LIMIT 1').fetchone():
                raise ValueError('wait_resume_has_accepted_work')
    try:
        from scripts.acceptance_native_cases import case_objective
    except ModuleNotFoundError:
        from acceptance_native_cases import case_objective
    text=case_objective(case).encode('utf-8');expected=hashlib.sha256(text).hexdigest()
    with closing(sqlite3.connect((root/'state/database/artifact_agent.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
        original=db.execute('SELECT payload_sha256,size_bytes FROM artifact_envelopes WHERE artifact_id=?',(binding[0],)).fetchone()
    if not original or tuple(original)!=(expected,len(text)):
        raise ValueError('wait_resume_objective_bytes_changed')
    payload=root/'state/artifacts/sha256'/expected[:2]/expected[2:]
    with payload.open('rb') as stream:
        if stream.read(len(text)+1)!=text:
            raise ValueError('wait_resume_objective_bytes_changed')
    if not allow_managed and (checkpoint.get('current_loop_id') or checkpoint.get('loop_authorizations')):
        raise ValueError('wait_resume_loop_authorized_during_read')
    return dict(instance_id=instance[0],artifact_id=binding[0],sha256=expected,owner_session=row['owner_session'],requested_by=row['requested_by'])


def wait_source(root,case,evidence):
    validate_candidate(root,case)
    if case.get('scenario')!='autonomous' or evidence.resolve().parent!=root or evidence.is_symlink():
        raise ValueError('wait_resume_requires_exact_autonomous_evidence')
    summary=json.loads((evidence/'summary.json').read_text());resource=json.loads((evidence/'resource.json').read_text())
    usage=json.loads((evidence/'usage.json').read_text())
    if (summary.get('status')!='failed' or summary.get('failure_type')!='TimeoutError'
            or summary.get('diagnostic')!='instance_wait_timeout' or summary.get('rpc_error')
            or resource.get('stop_reason')!='exited' or resource.get('returncode')!=1
            or (root/'model-submission-started').exists() or (evidence/'loop-authorization.json').exists()
            or json.loads((evidence/'started-threads.json').read_text())!=[]
            or usage.get('threads')!={} or usage.get('items')!=[]):
        raise ValueError('wait_resume_requires_confirmed_model_before_timeout')
    identity=json.loads((evidence/'thread.json').read_text())
    if not identity.get('thread_id') or identity.get('thread_id')!=identity.get('session_id'):
        raise ValueError('wait_resume_actual_identity_required')
    state=wait_state(root,case)
    return dict(identity=identity,bootstrap=state)


def wait_link(root,case,path,*,before_model=False):
    record=json.loads(path.read_text())
    output=Path(record['output']);prior=Path(record['prior_evidence'])
    if (record.get('kind')!='confirmed_pre_model_wait_timeout' or record.get('native_session_policy')!='new_thread_start; old_identity_is_evidence_only'
            or record.get('case_digest')!=guard_digest(case)
            or output.parent!=root or not output.name.startswith('wait-resume-') or prior.parent!=root
            or type(record.get('human_wait_seconds')) is not int or record['human_wait_seconds']<=0
            or record.get('human_poll_seconds')!=case['effective_settings']['progression']['poll_seconds']):
        raise ValueError('wait_resume_link_mismatch')
    for name,value in record['prior_files'].items():
        if not Path(name).resolve().is_relative_to(root.parent) or Path(name).is_symlink() or file_hash(Path(name))!=value:
            raise ValueError('wait_resume_original_evidence_changed')
    if record['source']['identity']!=json.loads((prior/'thread.json').read_text()):
        raise ValueError('wait_resume_actual_identity_changed')
    if before_model:
        observed=wait_source(root,case,prior)
        if observed!=record['source']:
            raise ValueError('wait_resume_source_changed')
        try:
            from scripts.accept_b6 import harness_digest
        except ModuleNotFoundError:
            from accept_b6 import harness_digest
        if harness_digest()!=record['runner_digest']:
            raise ValueError('wait_resume_harness_changed')
    return record


OBJECTIVE = """请自主完成这个有限研究目标并保留不能判断的部分。
这是合成材料而非物理实验：无量纲观测 (x,y) 为 (0,1),(1,3),(2,5)。
研究问题是：这些观测支持怎样的关系，能否区分线性机制 y=2x+1 与非线性机制
y=2x+1+c*x*(x-1)*(x-2)（c 未知），若不能，什么新观测能够区分？
请完成至少两个有科学意义的完整任务；第二项必须根据第一项的封存结果与限制选取，
不要事先固定操作链。最终交付可追溯的结论及小表格附件；不能把样本内吻合写成机制确认。
没有误差条、重复测量、区间外观测或 c 的先验，不要补造。预算最多三个完整任务；
本次不使用 TCAD、网络、外部作业或独立审查，不必为验收强制使用助手。
"""


class Journey(Host):
    def await_loop_authorization(self, value, *, objective_name, text):
        """Bootstrap through the actual native MCP coordinates, without a model turn."""
        case = self.case_config
        validate_candidate(self.root, case)
        expected = case['instance']
        recovering=getattr(self,'wait_resume',None)
        poll_seconds=recovering['human_poll_seconds'] if recovering else case['poll_seconds']
        self.status('awaiting_user', management_url=value['management_url'], model_requests=0,
            expected_instance=expected, next_step='select_existing_instance' if recovering else 'select_or_create_instance')
        print(('请在管理页选择已建实例 ' if recovering else '请在管理页选择或创建实例 ') + expected + '：' + value['management_url'], flush=True)
        while value.get('state') == 'unbound':
            self.pump(); time.sleep(poll_seconds); value = self.current_instance()
        if value.get('state') != 'active' or value.get('name') != expected:
            raise RuntimeError('wrong_existing_instance')
        database = self.root / 'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            self.instance = db.execute('SELECT instance_id FROM scheduler_instances WHERE name=?', (expected,)).fetchone()[0]
        if recovering:
            if self.instance!=recovering['source']['bootstrap']['instance_id']:
                raise RuntimeError('wait_resume_instance_changed')
        else:
            self.require_bootstrap_boundary(value)
        scheduling = self.call('progression_status', {})
        if (scheduling.get('loop') or {}).get('managed') and not recovering:
            raise RuntimeError('case_requires_unspent_loop; never_reset_existing_budget')
        if recovering:
            original=self.call('artifact_catalog',dict(name=objective_name,view='content'))
            if not original.get('complete') or original.get('text')!=text:
                raise RuntimeError('wait_resume_objective_bytes_changed')
        else:
            self.call('artifact_ingest_text', dict(name=objective_name, text=text, on_conflict='reject'))
        # Ingest claims ordinary interactive ownership. Only the user's page
        # pauses it; a client-side check cannot safely authorize a later pause.
        current=self.current_instance()
        if current.get('name') != expected:
            raise RuntimeError('selected_instance_changed')
        if not recovering:
            self.require_bootstrap_boundary(current, owned=True)
        self.bootstrap_session=urlsplit(current['management_url']).path.rsplit('/',1)[-1]
        if recovering:
            self.require_bootstrap_owner()
            if (scheduling.get('loop') or {}).get('managed'):
                self.confirm_loop(scheduling,objective_name)
                return current
            if self.wait_bootstrap_or_confirm_loop(objective_name):
                return current
        self.status('awaiting_user', management_url=value['management_url'], model_requests=0,
            expected_instance=expected, objective_name=objective_name,
            next_step='pause_bootstrap_then_confirm_loop_budget', frozen_limits=case['effective_settings']['progression'])
        print('目标已绑定为 ' + objective_name + '。请在同一管理页依次：'
              '1. 明确暂停本次无模型 bootstrap 交互调度；'
              '2. 刷新页面，核对该目标与冻结预算，明确确认新研究 loop。'
              '等待不调用模型：' + value['management_url'], flush=True)
        if recovering:
            print('仅复用已建实例和目标；若页面显示原交互会话，请由用户明确接管，再暂停并授额。',flush=True)
        while True:
            value = self.current_instance()
            if value.get('state') != 'active' or value.get('name') != expected:
                raise RuntimeError('selected_instance_changed')
            self.require_bootstrap_owner()
            self.pump()
            value = self.current_instance()
            if value.get('state') != 'active' or value.get('name') != expected:
                raise RuntimeError('selected_instance_changed')
            self.require_bootstrap_owner()
            scheduling = self.call('progression_status', {})
            if scheduling.get('reason') == 'user_stopped':
                raise RuntimeError('user_stop')
            loop = scheduling.get('loop') or {}
            if loop.get('managed'):
                self.confirm_loop(scheduling, objective_name)
                return value
            if recovering:
                if self.wait_bootstrap_or_confirm_loop(objective_name):
                    return value
            time.sleep(poll_seconds)

    def wait_bootstrap_or_confirm_loop(self,objective_name):
        sessions={self.bootstrap_session,self.wait_resume['source']['bootstrap']['requested_by']}
        try:
            wait_state(self.root,self.case_config,session=sessions)
        except ValueError as error:
            if str(error)!='wait_resume_loop_authorized_during_read':
                raise
            refreshed=self.call('progression_status',{})
            if not (refreshed.get('loop') or {}).get('managed'):
                raise
            wait_state(self.root,self.case_config,session=sessions,allow_managed=True)
            self.require_bootstrap_owner()
            self.confirm_loop(refreshed,objective_name)
            return True
        return False

    def require_bootstrap_owner(self):
        database=self.root/'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
            row=db.execute('SELECT owner_session,requested_by FROM scheduler_progression WHERE instance_id=?',
                (self.instance,)).fetchone()
        sessions={self.bootstrap_session}
        if getattr(self,'wait_resume',None):
            sessions.add(self.wait_resume['source']['bootstrap']['requested_by'])
        if not row or row[0] not in {*sessions,None} or row[1] not in sessions:
            raise RuntimeError('bootstrap_owner_changed')

    def require_bootstrap_boundary(self, value, *, owned=False):
        database = self.root / 'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory=sqlite3.Row
            result=db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (self.instance,)).fetchone()
        if result:
            row=dict(result);checkpoint=json.loads(row['checkpoint_json'])
            session=urlsplit(value['management_url']).path.rsplit('/',1)[-1]
            if (row['host_json'] or checkpoint.get('started_at') is not None or checkpoint.get('current_loop_id')
                    or checkpoint.get('fault_class') == 'outcome_unknown' or checkpoint.get('phase') in {'prepared','running'}
                    or checkpoint.get('admissions') or checkpoint.get('admissions_ref')
                    or (owned and (row['state'] != 'active' or row['owner_session'] != session or row['requested_by'] != session))
                    or not owned):
                raise RuntimeError('bootstrap_requires_quiescent_unspent_candidate')
        elif owned:
            raise RuntimeError('bootstrap_ownership_missing')
        for name,terminal in [('runs',"'completed','failed'"),('executions',"'succeeded','failed','cancelled','collected','abandoned'")]:
            path=self.root/f'state/database/{name}.sqlite3'
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                if db.execute(f'SELECT 1 FROM {name} WHERE state NOT IN ({terminal}) LIMIT 1').fetchone():
                    raise RuntimeError('bootstrap_requires_resolved_work')

    def confirm_loop(self, scheduling, objective_name):
        """Read both public projection and exact frozen control config before submission."""
        loop = scheduling.get('loop') or {}
        if (loop.get('authority') != 'explicit_management_ui_budget_confirmation'
                or loop.get('limits') != self.case_config['effective_settings']['progression']
                or scheduling.get('objective_name') != objective_name):
            raise RuntimeError('loop_authorization_mismatch')
        database = self.root / 'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            row = dict(db.execute('SELECT * FROM scheduler_progression WHERE instance_id=?', (self.instance,)).fetchone())
            binding = db.execute("SELECT object_id FROM scheduler_bindings WHERE instance=? AND namespace='artifact' AND name=?",
                (self.instance, objective_name)).fetchone()
        if (json.loads(row['config_json'])['effective'] != self.case_config['effective_settings']
                or not binding or json.loads(row['objective_ref_json'])['artifact_id'] != binding[0]
                or row['host_json'] or row['state'] != 'paused' or row['reason'] != 'loop_authorized'
                or row['owner_session'] is not None or row['requested_by'] != self.bootstrap_session
                or json.loads(row['checkpoint_json']).get('current_loop_id') != loop.get('id')):
            raise RuntimeError('frozen_loop_config_or_goal_changed')
        identity = {key: loop[key] for key in ('id', 'authorized_at', 'deadline_at')}
        if getattr(self, 'loop_identity', identity) != identity:
            raise RuntimeError('loop_identity_changed; never_replenish_acceptance_budget')
        remaining = min(datetime.fromisoformat(loop['deadline_at']).timestamp() - time.time(),
            scheduling['budget']['effective_remaining_seconds'], self.resources['execution_timeout_seconds'])
        if remaining <= 0:
            raise RuntimeError('authorized_loop_budget_exhausted')
        self.loop_identity = identity
        self.phase = 'execution'
        deadline = time.monotonic() + remaining
        self.phase_deadline = min(getattr(self, '_authorized_deadline', deadline), deadline)
        self._authorized_deadline = self.phase_deadline
        write(self.logdir.parent / 'loop-authorization.json', dict(**identity, objective_name=objective_name,
            limits=loop['limits'], effective_settings_digest=guard_digest(self.case_config['effective_settings']),
            model_requests=0))
        if not hasattr(self, 'execution_started_at'):
            self.execution_started_at = time.monotonic()

    def wait_for_accepted_tasks(self, status):
        """Drain accepted work under the existing execution deadline; no model call."""
        while not (status.get('closeout') or {}).get('accepted_tasks_terminal', False):
            write(self.logdir.parent / 'summary.json', dict(status='accepted_tasks_not_quiescent',
                progression=status, b6_passed=False))
            if time.monotonic() >= self.phase_deadline:
                raise RuntimeError('accepted_tasks_not_quiescent')
            self.pump()
            time.sleep(2)
            status = self.call('progression_status', {})
            write(self.logdir.parent / 'progression.json', status)
        return status

    def call(self, name, arguments):
        reply = self.rpc('mcpServer/tool/call', dict(threadId=self.thread, server='scidiscovery',
            tool='scid_call', arguments=dict(name=name, arguments=arguments),
            _meta={'x-codex-turn-metadata': dict(session_id=self.platform_session, thread_id=self.thread)}))
        if reply.get('isError'):
            raise RuntimeError(f'public_tool_failed:{name}')
        value = reply.get('structuredContent')
        if not isinstance(value, dict):
            value = json.loads(reply['content'][0]['text'])
        return value

    def run_journey(self):
        value = self.initialize_host(check_native=False)
        self.await_loop_authorization(value, objective_name='acceptance.objective', text=self.case_config['text'])
        self.status('scientific_turn')
        (self.root / 'model-submission-started').touch(exist_ok=False)
        self.turn('请先确认 instance_current，复用所选实例已有原始材料和封存结果，不重复已完成且未变化的工作。'
            '复用 acceptance.objective 的原文与管理页已确认 loop，按公开合同启动后台目标。'
            '本轮只完成目标原文绑定及后台启动，科学任务交给后台 Root 自主选择。'
            '原文不构成审查或执行例外授权，不新增审批或资格门。\n\n' + self.case_config['text'])
        previous = None
        while True:
            self.pump()
            status = self.call('progression_status', {})
            if status != previous:
                write(self.logdir.parent / 'progression.json', status)
                print(json.dumps({key: status.get(key) for key in ('state', 'reason', 'report')},
                    ensure_ascii=False), flush=True)
                previous = status
            if status.get('reason') == 'goal_completed' or status.get('state') in {'paused', 'stopped'}:
                status = self.wait_for_accepted_tasks(status)
                break
            if status.get('reason') in {'not_started', 'user_question'}:
                raise RuntimeError('goal_not_started_or_requires_answer')
            time.sleep(2)
        # One final native reader audits sealed results and the existing UI,
        # without manufacturing scientific outputs or scheduling another task.
        self.turn('只读验收：回读本实例本次目标的准确 run_list/run_status 封存结果。'
            '核对是否至少两个完整科学任务、第二项是否实际使用第一项封存证据、'
            '原件与表格附件是否能从管理页访问，区分已证明关系与不能判断机制。'
            '回读 progression_status 的 Root/Worker/helper 用量与缺测。'
            '不得创建新任务或修补结果，不得根据完成聊天代替封存结果。简短报告通过、失败、缺测。')
        write(self.logdir.parent / 'summary.json', dict(
            status='sealed_audit_required', progression=status,
            observed_native_journey=True, b6_passed=False,
            unverified=['independent audit of scientific lineage and attachments',
                'native pause/resume/reconnect/stop/restart', 'native helper survival',
                'manual versus autonomous cost/quality comparison', 'controlled external execution'],
            root_audit='fixture-logs/events.log'))
        self.status('root_returned_requires_sealed_audit')


def child(root, scenario='science', case_file=None, wait_resume_path=None):
    case = json.loads(case_file.read_text()) if case_file else {}
    validate_candidate(root, case)
    if scenario != 'managed' and platform_identity() != case['freeze_identity']['platform']:
        raise ValueError('frozen_codex_platform_changed')
    journey_type = Journey
    if scenario == 'recovery':
        try:
            from scripts.accept_progression_recovery import RecoveryJourney
        except ModuleNotFoundError:
            from accept_progression_recovery import RecoveryJourney
        journey_type = RecoveryJourney
    elif scenario == 'managed':
        try:
            from scripts.acceptance_managed import ManagedJourney
        except ModuleNotFoundError:
            from acceptance_managed import ManagedJourney
        journey_type = ManagedJourney
    elif scenario != 'science':
        try:
            from scripts.acceptance_native_cases import NativeCaseJourney
        except ModuleNotFoundError:
            from acceptance_native_cases import NativeCaseJourney
        journey_type = NativeCaseJourney
    host = journey_type(root, json.loads(guard.DEFAULT_CONFIG.read_text())['limits'])
    host.case_config = case
    if wait_resume_path:
        host.wait_resume=wait_link(root,case,wait_resume_path,before_model=True)
        host.resources=dict(host.resources,instance_wait_timeout_seconds=host.wait_resume['human_wait_seconds'])
    try:
        host.run_journey()
    except BaseException as error:
        write(host.logdir.parent / 'summary.json', dict(status='failed', b6_passed=False,
            failure_type=type(error).__name__, diagnostic=str(error), rpc_error=host.last_rpc_error,
            checks=getattr(host, 'case_checks', {})))
        host.status('failed',failure_type=type(error).__name__,diagnostic=str(error),model_requests=0 if not (root/'model-submission-started').exists() else 'not_observed')
        raise
    finally:
        if hasattr(host, 'execution_started_at'):
            write(host.logdir.parent / 'execution-time.json', dict(
                elapsed_seconds=time.monotonic()-host.execution_started_at,
                source='foreground_supervisor_after_loop_confirmation', human_wait_included=False))
        write(host.logdir.parent / 'started-threads.json', sorted(host.started_threads))
        host.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--scenario', choices=('science', 'recovery', 'authority', 'helper', 'helper-crash', 'manual', 'autonomous', 'managed'), default='science',
        help='recovery exercises native Root control against existing results; no new scientific tasks')
    parser.add_argument('--case-file', type=Path, help='frozen acceptance case from accept_b6.py')
    parser.add_argument('--retry-startup', action='store_true',
        help='retry after fixing startup only when no model submission was attempted')
    parser.add_argument('--resume-wait',type=Path,help='sealed confirmed pre-model wait recovery link from accept_b6 resume-wait')
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--lock-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.candidate.resolve()
    if args.case_file is None:
        parser.error('this scenario requires --case-file from accept_b6.py')
    if args.case_file and json.loads(args.case_file.read_text()).get('scenario', 'managed') != args.scenario:
        parser.error('case scenario mismatch')
    if args.child:
        fd = int(os.environ['SCID_HOST_PROBE_LOCK_FD'])
        expected = (Path('/tmp') / f'scid-tests-{os.getuid()}.lock').stat()
        actual = os.fstat(fd)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise RuntimeError('supervision_required')
        child(root, args.scenario, args.case_file,args.resume_wait)
        return 0
    os.umask(0o077)
    try:
        case=json.loads(args.case_file.read_text())
        validate_candidate(root,case)
        recovery=wait_link(root,case,args.resume_wait,before_model=True) if args.resume_wait else None
    except (ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    prerequisites = preflight() if args.scenario != 'managed' else {'blockers': []}
    write(root / 'startup-check.json', prerequisites)
    if prerequisites['blockers']:
        if args.resume_wait:
            write(root/'progress.json',dict(state='wait_resume_failed',blockers=prerequisites['blockers'],model_requests=0))
        print(json.dumps(prerequisites), flush=True)
        return 2
    if list(root.glob('journey-*')) and not recovery and not (args.retry_startup and not (root / 'model-submission-started').exists()):
        parser.error('candidate already attempted; inspect its summary/state before any explicit recovery')
    output = Path(recovery['output']) if recovery else root / ('journey-' + str(time.time_ns()))
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
    resources=host_resources(root)
    if recovery:
        resources=dict(resources,instance_wait_timeout_seconds=recovery['human_wait_seconds'])
    limits['timeout_seconds'] = sum(resources[key] for key in
        ('startup_timeout_seconds', 'instance_wait_timeout_seconds', 'execution_timeout_seconds'))
    environment = dict(os.environ, SCID_TEST_LOG_DIR=str(output / 'fixture-logs'),
        SCID_TEST_LOG_BYTES=str(limits['log_bytes']), PYTHONDONTWRITEBYTECODE='1')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                'TOKIO_WORKER_THREADS', 'RAYON_NUM_THREADS'):
        environment[key] = '1'
    with guard.serial_lock(args.lock_fd) as lock:
        output.mkdir()
        (output / 'fixture-logs').mkdir()
        environment['SCID_HOST_PROBE_LOCK_FD'] = str(lock.fileno())
        # The resource guard owns the child tree; a small relay streams only the
        # user-facing progress while detailed native output stays in private logs.
        import threading
        stop = threading.Event()
        def relay():
            offset = 0
            while not stop.wait(.2):
                path = output / 'pytest.log'
                if path.exists():
                    with path.open() as stream:
                        stream.seek(offset)
                        chunk = stream.read()
                        offset = stream.tell()
                    if chunk:
                        print(chunk, end='', flush=True)
        thread = threading.Thread(target=relay, daemon=True)
        thread.start()
        try:
            result = guard.run_one([sys.executable, str(Path(__file__).resolve()), '--child',
                '--candidate', str(root), '--scenario', args.scenario,
                *(['--case-file', str(args.case_file.resolve())] if args.case_file else []),
                *(['--resume-wait',str(args.resume_wait.resolve())] if recovery else [])], environment, limits, output, lock.fileno())
        finally:
            stop.set()
            thread.join(timeout=1)
    write(output / 'resource.json', result)
    if not (output / 'summary.json').exists():
        write(output / 'summary.json', dict(status='incomplete', b6_passed=False, resource=result))
    if result['returncode']!=0 or result['stop_reason']!='exited':
        write(root/'progress.json',dict(state='failed',evidence=str(output),resource=result,
            diagnostic=json.loads((output/'summary.json').read_text()).get('diagnostic','supervisor_failed'),
            model_requests=0 if not (root/'model-submission-started').exists() else 'not_observed'))
    print('验收记录：' + str(output), flush=True)
    return 0 if result['returncode'] == 0 and result['stop_reason'] == 'exited' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BlockingIOError:
        print('serial_lock_busy: another serial task is running; no journey was started.',file=sys.stderr)
        raise SystemExit(75)
