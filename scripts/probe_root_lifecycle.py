"""One real Worker completes while its app-server client is disconnected.

The app-server and SciDiscovery services remain owned by the resource supervisor.
This establishes neither server-crash survival nor production daemon management.
"""
from datetime import datetime, timezone
from contextlib import closing
import json
import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

try:
    from scripts.probe_root_host_live import Host, write
except ModuleNotFoundError:
    from probe_root_host_live import Host, write


NAME = "evidence.synthetic_xy_lifecycle.v1"
DISPATCH = f"""这是一次客户端断线后的 Worker 生命周期验收，只允许创建一个新任务 {NAME}。
先确认当前实例是 b0a-calibration；若不是，停止。复用精确材料
source.synthetic_xy_three_observations.v1，不重新 ingest；它含无量纲合成三点
(0,1)、(1,3)、(2,5)，没有误差、重复实验或区间外信息。
使用 science.evidence.extract.v1 对这三个点提取证据，区分点上关系与无依据外推；
同一原文同时承担 source_material 和 user_context。沿用当前合同，真实原生派发一个
Worker，使用合同指定模型/推理配置，不带父历史，实际平台身份 attach 后通知其打开
assignment 并完成提交。不要助手、审查、网页、TCAD，不重试不确定的写操作。
特别要求：通知 Worker 开始后，Root 立即结束本回合，不等待 Worker、不轮询结果、
不停止或关闭它。后台宿主负责等待，完成后会另开 Root 回合回读封存结果。
这只是测试调度方式；Worker 的科学合同、提交规则和预算保持原样。"""
READBACK = f"""客户端已重新连接；后台 Worker 应已完成 {NAME}。
只确认 instance_current，并查询此确切任务的 run_status(intent="decision")。
回读封存结论和限制；不创建任务，不联系 Worker，不重新提交、不更改期限。
如果控制层并非 completed 或封存不可用，如实报告失败并停止。"""
RECOVER = f"""恢复上次已创建且已附着的唯一任务 {NAME}，不是新任务。
先确认 instance_current 和此任务的 run_status。宿主已恢复原 Worker 的实际线程。
如果任务仍为 queued/running，仅通知原 Worker 继续其原 assignment 并完成提交；
使用 followup_task 启动原 Worker 的执行回合；send_message 只投递消息，不能唤醒空闲线程，
本次不得用它代替 followup_task。如果平台没有 followup_task，报告不支持并停止。
随后 Root 立即结束回合，不等待、不轮询。不要 operation_invoke、ingest、重新派发、
修改期限或重新 attach。若已完成、超时或失败，如实报告并停止，不创建替代任务。"""


def require_lifecycle_resume(root):
    with closing(sqlite3.connect((root / "state/database/runs.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("""SELECT r.state,r.deadline_at,w.thread_id FROM runs r
            LEFT JOIN worker_connections w ON r.run_id=w.run_id
            WHERE r.output_binding_name=?""", (NAME + ".output",)).fetchall()
    if (len(rows) != 1 or rows[0][0] not in ("queued", "running") or not rows[0][2]
            or datetime.now(timezone.utc) >= datetime.fromisoformat(rows[0][1])):
        raise RuntimeError("lifecycle_resume_requires_active_attached_run_within_deadline")


def require_no_started_lifecycle(root):
    """Only a finalized, pre-thread transport failure permits another attempt."""
    with closing(sqlite3.connect((root / "state/database/runs.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("SELECT 1 FROM runs WHERE output_binding_name=?", (NAME + ".output",)).fetchone():
            raise RuntimeError("lifecycle_run_already_exists")
    for previous in root.glob("lifecycle*"):
        if not previous.is_dir():
            continue
        try:
            usage = json.loads((previous / "usage.json").read_text())
            result = json.loads((previous / "resource.json").read_text())
            empty_events = (previous / "fixture-logs/events.log").stat().st_size == 0
        except (OSError, ValueError):
            raise RuntimeError("lifecycle_previous_attempt_uncertain") from None
        if (usage.get("root_thread") is not None or usage.get("threads") != {}
                or usage.get("items") != [] or not empty_events
                or (previous / "thread.json").exists()
                or result.get("returncode") != 1 or result.get("stop_reason") != "exited"):
            raise RuntimeError("lifecycle_previous_attempt_must_be_reconciled")


class LifecycleHost(Host):
    resume_existing = False

    def launch_app(self, overrides):
        if importlib.util.find_spec("aiohttp") is None:
            raise RuntimeError("lifecycle_requires_host_probe_extra:aiohttp")
        self.app_socket = self.root / f"a{os.getpid()}.sock"
        if self.app_socket.exists():
            raise RuntimeError("lifecycle_socket_already_exists")
        self.server = self.launch([shutil.which("codex"), "app-server",
            "--listen", "unix://" + str(self.app_socket), *overrides], "app-server")
        deadline = time.monotonic() + 20
        while not self.app_socket.exists():
            if self.server.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("lifecycle_app_server_unavailable")
            time.sleep(.1)
        return self.connect_client("client-before")

    def connect_client(self, name):
        return self.launch([sys.executable, str(Path(__file__).with_name("root_host_ws_client.py")),
                            "--socket", str(self.app_socket), "--max-message-bytes",
                            str(self.limits["log_bytes"])], name, True)

    def run_row(self):
        path = self.root / "state/database/runs.sqlite3"
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""SELECT r.run_id, r.state, r.completed_at,
                r.deadline_at, r.output_ref_json, w.thread_id, w.platform_session
                FROM runs r LEFT JOIN worker_connections w ON w.run_id=r.run_id
                WHERE r.output_binding_name=?""", (NAME + ".output",)).fetchall()
        if len(rows) > 1:
            raise RuntimeError("lifecycle_run_ambiguous")
        return dict(rows[0]) if rows else None

    def disconnect_client(self):
        self.connection.close()
        self.children.remove(self.app)
        self.connection = None
        self.root_host = None
        return datetime.now(timezone.utc)

    def wait_disconnected(self, run_id):
        # No model polling, reattach or Worker resume while observing completion.
        while True:
            if (self.root / "stop").exists():
                raise RuntimeError("user_stop")
            if time.monotonic() >= self.phase_deadline:
                raise TimeoutError("execution_timeout")
            if any(child.poll() is not None for child in self.children):
                raise RuntimeError("owned_process_exited_while_disconnected")
            row = self.run_row()
            if not row or row["run_id"] != run_id:
                raise RuntimeError("lifecycle_run_changed")
            if row["state"] == "completed":
                return row
            if row["state"] not in ("queued", "running"):
                raise RuntimeError("lifecycle_worker_not_running:" + row["state"])
            if datetime.now(timezone.utc) >= datetime.fromisoformat(row["deadline_at"]):
                raise TimeoutError("lifecycle_run_deadline")
            time.sleep(1)

    def require_worker_turn_started(self, thread):
        deadline = time.monotonic() + self.resources["worker_wakeup_timeout_seconds"]
        while thread not in self.started_threads:
            if time.monotonic() >= deadline:
                raise RuntimeError("worker_turn_not_started_after_resume")
            self.pump()

    def run(self, resume=False):
        self.await_instance(self.initialize_host(resume=True))
        self.status("scientific_turn", lifecycle=True)
        original = self.run_row()
        if self.resume_existing:
            require_lifecycle_resume(self.root)
            if original["platform_session"] != self.platform_session:
                raise RuntimeError("lifecycle_resume_session_mismatch")
            actual = self.rpc("thread/resume", {"threadId": original["thread_id"], "excludeTurns": True})["thread"]
            if actual.get("id") != original["thread_id"] or actual.get("sessionId") != self.platform_session:
                raise RuntimeError("lifecycle_reconnected_identity_changed")
            self.turn(RECOVER + "\n原 Worker 的实际线程：" + original["thread_id"])
            self.require_worker_turn_started(original["thread_id"])
        else:
            if original is not None:
                raise RuntimeError("lifecycle_run_already_exists")
            self.turn(DISPATCH)
        row = self.run_row()
        if (not row or row["state"] not in ("queued", "running")
                or row["platform_session"] != self.platform_session):
            raise RuntimeError("lifecycle_requires_active_attached_worker_at_root_return")
        if original and (row["run_id"], row["thread_id"]) != (original["run_id"], original["thread_id"]):
            raise RuntimeError("lifecycle_run_changed")
        events = self.logdir / "events.log"
        started = {v["params"]["item"]["agentThreadId"] for v in
                   map(json.loads, events.read_text().splitlines())
                   if v.get("params", {}).get("item", {}).get("type") == "subAgentActivity"
                   and v["params"]["item"].get("kind") == "started"}
        if started != (set() if self.resume_existing else {row["thread_id"]}):
            raise RuntimeError("lifecycle_requires_exactly_one_actual_worker")
        evidence = {"root_return_run_state": row["state"], "resumed_existing_run": self.resume_existing,
                    "server_pid": self.server.pid, "client_pid": self.app.pid,
                    "worker_thread": row["thread_id"], "run_id": row["run_id"],
                    "b0a_passed": False}
        disconnected = self.disconnect_client()
        evidence["client_disconnected_at"] = disconnected.isoformat()
        write(self.logdir.parent / "lifecycle.json", evidence)
        self.status("observing_disconnected_worker")
        completed = self.wait_disconnected(row["run_id"])
        if datetime.fromisoformat(completed["completed_at"]) <= disconnected:
            raise RuntimeError("worker_completed_before_disconnect_observation")
        evidence.update(worker_completed_while_disconnected=True,
                        completed_at=completed["completed_at"])
        write(self.logdir.parent / "lifecycle.json", evidence)
        self.app = self.connect_client("client-after")
        self.reconnect_root()
        # Restore the exact completed Worker for observation only, never a new turn.
        actual = self.rpc("thread/resume", {"threadId": row["thread_id"], "excludeTurns": True})["thread"]
        if actual.get("id") != row["thread_id"] or actual.get("sessionId") != self.platform_session:
            raise RuntimeError("lifecycle_reconnected_identity_changed")
        self.await_instance(self.current_instance())
        self.status("scientific_turn", lifecycle=True, reconnected=True)
        self.turn(READBACK)
        self.status("root_returned_requires_sealed_audit", lifecycle=True)
