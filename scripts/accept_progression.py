"""One bounded real B6 journey: installed daemon/UI, user selection, native Root.

Run: python scripts/accept_progression.py --candidate <prepared-upgrade-candidate>
Reuse an existing instance via probe_root_host_live.py prepare-upgrade first.
This is a foreground supervisor: keep this terminal open. No TCAD or production
state is used. Select the instance using the printed UI URL; no continue command.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

try:
    from scripts import run_tests as guard
    from scripts.probe_root_host_live import Host, write, host_resources, preflight
except ModuleNotFoundError:
    import run_tests as guard
    from probe_root_host_live import Host, write, host_resources, preflight


def require_existing_instance(root):
    """Validate availability only; instance selection stays in the user page."""
    if not (root / 'candidate.json').is_file():
        raise ValueError('Prepare an upgrade candidate from the previous acceptance state '
                         'with probe_root_host_live.py prepare-upgrade first.')
    database = root / 'state/database/scheduler-bindings.sqlite3'
    if not database.is_file():
        raise ValueError('Candidate has no instance database; prepare an upgrade candidate first.')
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if not db.execute('SELECT 1 FROM scheduler_instances LIMIT 1').fetchone():
            raise ValueError('Candidate contains no existing instance; use prepare-upgrade '
                             'to retain the previous acceptance evidence instead of creating empty state.')


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
        self.status('awaiting_user', management_url=value['management_url'])
        print('请选择已有验收实例：' + value['management_url'], flush=True)
        while value.get('state') == 'unbound':
            self.pump()
            time.sleep(1)
            value = self.current_instance()
        if value.get('state') != 'active':
            raise RuntimeError('instance_not_selected')
        self.status('scientific_turn')
        (self.root / 'model-submission-started').touch(exist_ok=False)
        self.turn('请先确认 instance_current，复用所选实例已有原始材料和封存结果，不重复已完成且未变化的工作。'
            '冻结下方本轮目标原文为 source_text，按公开合同启动后台目标。'
            '本轮只完成目标原文绑定及后台启动，科学任务交给后台 Root 自主选择。'
            '原文不构成审查或执行例外授权，不新增审批或资格门。\n\n' + OBJECTIVE)
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


def child(root, scenario='science'):
    require_existing_instance(root)
    settings = json.loads((root / 'agent-settings.json').read_text())
    # Preserve configured token/resource policy. The native usage counter includes
    # cached input; a separate tiny fixture cap would stop the two-task journey
    # before it can test scientific continuation. Only bound this fixture's scope.
    settings.setdefault('progression', {}).update(
        max_tasks=3, max_rounds=8, max_elapsed_seconds=1200, max_attempts=1)
    write(root / 'agent-settings.json', settings)
    journey_type = Journey
    if scenario == 'recovery':
        try:
            from scripts.accept_progression_recovery import RecoveryJourney
        except ModuleNotFoundError:
            from accept_progression_recovery import RecoveryJourney
        journey_type = RecoveryJourney
    host = journey_type(root, json.loads(guard.DEFAULT_CONFIG.read_text())['limits'])
    try:
        host.run_journey()
    except BaseException as error:
        write(host.logdir.parent / 'summary.json', dict(status='failed', b6_passed=False,
            failure_type=type(error).__name__, diagnostic=str(error), rpc_error=host.last_rpc_error))
        raise
    finally:
        host.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--scenario', choices=('science', 'recovery'), default='science',
        help='recovery exercises native Root control against existing results; no new scientific tasks')
    parser.add_argument('--retry-startup', action='store_true',
        help='retry after fixing startup only when no model submission was attempted')
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.candidate.resolve()
    if args.child:
        fd = int(os.environ['SCID_HOST_PROBE_LOCK_FD'])
        expected = (Path('/tmp') / f'scid-tests-{os.getuid()}.lock').stat()
        actual = os.fstat(fd)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise RuntimeError('supervision_required')
        child(root, args.scenario)
        return 0
    os.umask(0o077)
    try:
        require_existing_instance(root)
    except (ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    prerequisites = preflight()
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
    with (Path('/tmp') / f'scid-tests-{os.getuid()}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
                '--candidate', str(root), '--scenario', args.scenario], environment, limits, output, lock.fileno(), limit_address_space=False)
        finally:
            stop.set()
            thread.join(timeout=1)
    write(output / 'resource.json', result)
    if not (output / 'summary.json').exists():
        write(output / 'summary.json', dict(status='incomplete', b6_passed=False, resource=result))
    print('验收记录：' + str(output), flush=True)
    return 0 if result['returncode'] == 0 and result['stop_reason'] == 'exited' else 1


if __name__ == '__main__':
    raise SystemExit(main())
