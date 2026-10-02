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
        self.status('awaiting_user', management_url=value['management_url'], model_requests=0,
            expected_instance=expected, next_step='select_or_create_instance')
        print('请在管理页选择或创建实例 ' + expected + '：' + value['management_url'], flush=True)
        while value.get('state') == 'unbound':
            self.pump(); time.sleep(case['poll_seconds']); value = self.current_instance()
        if value.get('state') != 'active' or value.get('name') != expected:
            raise RuntimeError('wrong_existing_instance')
        database = self.root / 'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            self.instance = db.execute('SELECT instance_id FROM scheduler_instances WHERE name=?', (expected,)).fetchone()[0]
        self.require_bootstrap_boundary(value)
        scheduling = self.call('progression_status', {})
        if (scheduling.get('loop') or {}).get('managed'):
            raise RuntimeError('case_requires_unspent_loop; never_reset_existing_budget')
        self.call('artifact_ingest_text', dict(name=objective_name, text=text, on_conflict='reject'))
        # Ingest claims ordinary interactive ownership. Only the user's page
        # pauses it; a client-side check cannot safely authorize a later pause.
        current=self.current_instance()
        if current.get('name') != expected:
            raise RuntimeError('selected_instance_changed')
        self.require_bootstrap_boundary(current, owned=True)
        self.bootstrap_session=urlsplit(current['management_url']).path.rsplit('/',1)[-1]
        self.status('awaiting_user', management_url=value['management_url'], model_requests=0,
            expected_instance=expected, objective_name=objective_name,
            next_step='pause_bootstrap_then_confirm_loop_budget', frozen_limits=case['effective_settings']['progression'])
        print('目标已绑定为 ' + objective_name + '。请在同一管理页依次：'
              '1. 明确暂停本次无模型 bootstrap 交互调度；'
              '2. 刷新页面，核对该目标与冻结预算，明确确认新研究 loop。'
              '等待不调用模型：' + value['management_url'], flush=True)
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
            time.sleep(case['poll_seconds'])

    def require_bootstrap_owner(self):
        database=self.root/'state/database/scheduler-bindings.sqlite3'
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
            row=db.execute('SELECT owner_session,requested_by FROM scheduler_progression WHERE instance_id=?',
                (self.instance,)).fetchone()
        if not row or row[0] not in {None,self.bootstrap_session} or row[1] != self.bootstrap_session:
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


def child(root, scenario='science', case_file=None):
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
    try:
        host.run_journey()
    except BaseException as error:
        write(host.logdir.parent / 'summary.json', dict(status='failed', b6_passed=False,
            failure_type=type(error).__name__, diagnostic=str(error), rpc_error=host.last_rpc_error,
            checks=getattr(host, 'case_checks', {})))
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
        child(root, args.scenario, args.case_file)
        return 0
    os.umask(0o077)
    try:
        validate_candidate(root, json.loads(args.case_file.read_text()))
    except (ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    prerequisites = preflight() if args.scenario != 'managed' else {'blockers': []}
    write(root / 'startup-check.json', prerequisites)
    if prerequisites['blockers']:
        print(json.dumps(prerequisites), flush=True)
        return 2
    if list(root.glob('journey-*')) and not (args.retry_startup and not (root / 'model-submission-started').exists()):
        parser.error('candidate already attempted; inspect its summary/state before any explicit recovery')
    output = root / ('journey-' + str(time.time_ns()))
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
    limits['timeout_seconds'] = sum(host_resources(root)[key] for key in
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
                *(['--case-file', str(args.case_file.resolve())] if args.case_file else [])], environment, limits, output, lock.fileno(), limit_address_space=False)
        finally:
            stop.set()
            thread.join(timeout=1)
    write(output / 'resource.json', result)
    if not (output / 'summary.json').exists():
        write(output / 'summary.json', dict(status='incomplete', b6_passed=False, resource=result))
    print('验收记录：' + str(output), flush=True)
    return 0 if result['returncode'] == 0 and result['stop_reason'] == 'exited' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BlockingIOError:
        print('serial_lock_busy: another serial task is running; no journey was started.',file=sys.stderr)
        raise SystemExit(75)
