"""Isolated B0a candidate and bounded real-host probe (never a production service).

Run prepare under Codex; run start in an ordinary host terminal. Read progress.json
and latest-root-message.txt, select the instance in the UI, then run continue.
Startup, human selection and execution have separate configured time budgets.
prepare-upgrade copies stopped candidate state with --from-candidate, reusing the
program from --installed-candidate. Keep that installation for the candidate's life.
Resume reuses actual platform threads and existing state; it never renews a Run
deadline. Resource stop still does not prove independent Worker life.
An explicit next task uses resume --task-file after prior work terminates. It is
frozen in the new evidence directory. Candidate host-resources.json may override
host time budgets; test_resources.json still owns memory protection.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import tomllib
from urllib.parse import urlsplit, parse_qs


try:
    from scripts import run_tests as guard
    from scripts.probe_native_code_mode import probe as probe_native_code_mode
    from scripts.installed_candidates import create_environments, _run_logged
    from scripts.probe_root_host import preflight, thread_start_params, rpc_diagnostic, config_flags
except ModuleNotFoundError:
    import run_tests as guard
    from probe_native_code_mode import probe as probe_native_code_mode
    from installed_candidates import create_environments, _run_logged
    from probe_root_host import preflight, thread_start_params, rpc_diagnostic, config_flags

from scidiscovery.platforms.codex_app_server import AppServer, HostLimits
from scidiscovery.platforms.codex_root_host import CodexRootHost, RootIdentity, turn_params

HOST_RESOURCES = Path(__file__).with_name("root_host_resources.json")


def control_socket_ready(path):
    """A leftover socket inode is not evidence of a listening control service."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(.2)
            connection.connect(str(path))
        return True
    except OSError:
        return False


def host_resources(root):
    override = root / "host-resources.json"
    return json.loads((override if override.exists() else HOST_RESOURCES).read_text())


def continuation_task(root, path):
    """An explicit new task requires a completed prior turn and no in-flight work."""
    progress = json.loads((root / "progress.json").read_text())
    if progress.get("state") != "root_returned_requires_sealed_audit":
        raise ValueError("new task requires a completed prior Root turn; use plain resume for recovery")
    for name, table, terminal in (
        ("runs", "runs", "'completed','failed'"),
        ("executions", "executions", "'succeeded','failed','cancelled','collected','abandoned'"),
    ):
        db = sqlite3.connect((root / f"state/database/{name}.sqlite3").as_uri() + "?mode=ro", uri=True)
        try:
            if db.execute(f"SELECT 1 FROM {table} WHERE state NOT IN ({terminal}) LIMIT 1").fetchone():
                raise ValueError("unfinished work requires recovery before a new acceptance task")
        finally:
            db.close()
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536 or not raw.strip():
        raise ValueError("acceptance task must contain 1..65536 UTF-8 bytes")
    return raw.decode("utf-8")

TASK = """用户已在管理页选择实例。请先通过 instance_current 确认绑定。
目标：验证一次真实完整任务的原生 Worker 派发、受控交付及 Root 封存回读。
原始科学材料（合成数据，不是真实物理实验）：x,y 的三组值为 (0,1),(1,3),(2,5)，
x 与 y 无量纲；仅说明这三个观测点，不包含误差、重复实验或区间外信息。
请冻结这段原始材料，按合同调用 science.evidence.extract.v1 完成一次有限的证据提取，
绑定原始用户上下文；完整派发一个真实原生 Worker，采用返回的角色/模型/推理配置且不带父历史，
使用真实平台坐标 attach，等待并回读 sealed run_status。科学结论应区分三点的线性关系与未获支持的外推。
本例不需要独立审查或助手；不得为验收制造更多科研任务，也不要调用 TCAD、网页或正式服务。
纯只读合同查询若因参数错误失败，可依据错误信息修正后重试一次；保留该失败记录。
服务不可用、身份或权限失败，以及任务创建、派发、提交或交付失败时，停止并报告确切失败层。
不得重试结果不确定的写操作，不靠直接写库/补造回执修复；不得自动增加重试预算。
最后报告任务状态、封存结论和限制；聊天完成消息不能代替封存回读。"""

RESUME_TASK = """本轮恢复原会话并核对已有任务，不是新实验。
控制服务、原 Root 以及尚未收到平台完成通知的 Worker 线程已恢复；实例由用户管理页选择。
平台完成通知不等于封存成功，仍须查询控制层。
先查询 instance_current 和已有任务的 run_status，核对封存结果、状态与期限。
若已完成，只回读 sealed 结果；若原任务仍可执行，通知原 Worker 继续其已有 assignment，
保留已经写出的文件，不重新派发，不重新冻结材料，不再次 operation_invoke。
若任务已超时或原 Worker 无法继续，报告具体原因并停止，不延长期限、不改库、不自动新建任务。
完成后必须回读 sealed run_status。只读查询参数错误可修正一次，结果不确定的写操作不得重试。"""


def write(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def instance_result(reply: dict, ui_url: str) -> dict:
    if reply.get("isError"):
        raise RuntimeError("instance_current_tool_failed")
    value = reply.get("structuredContent")
    if not isinstance(value, dict):
        content = reply.get("content", [])
        if len(content) != 1 or content[0].get("type") != "text":
            raise RuntimeError("instance_current_payload_invalid")
        value = json.loads(content[0]["text"])
    url = value.get("management_url", "")
    parsed, origin = urlsplit(url), urlsplit(ui_url)
    if (parsed.scheme != origin.scheme or parsed.netloc != origin.netloc
            or not re.fullmatch(r"/sessions/sch_[a-f0-9]{32}", parsed.path)
            or not parse_qs(parsed.query).get("capability")):
        raise RuntimeError("instance_management_url_missing_or_wrong_service")
    return value


def prepare(root: Path, *, distribution="core", plugin_configs=None, task=None):
    if distribution not in {"core", "all_domains"}:
        raise ValueError("unsupported acceptance distribution")
    if task is not None and (not isinstance(task, str) or not task.strip()):
        raise ValueError("acceptance task must be nonempty text")
    plugin_configs = {name: str(Path(path).resolve()) for name, path in (plugin_configs or {}).items()}
    plugin_arguments = [argument for name, path in plugin_configs.items()
                        for argument in ("--plugin-config", name + "=" + path)]
    build = root / "build"
    build.mkdir()
    installed = create_environments(guard.ROOT, build)[distribution]
    project = installed.workdir
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("SCIDISCOVERY_ROLE_DIR", None)
    environment["PYTHONNOUSERSITE"] = "1"
    _run_logged([str(installed.python), "-m", "scidiscovery.artifact_agent.interfaces.cli",
        "--project-root", str(project), "--state-root", str(root / "state"), "init", "codex",
        "--python", str(installed.python), "--control-socket", str(root / "control.sock"), *plugin_arguments],
        cwd=project, env=environment, timeout=120)
    # Worker preferences may follow the local client; Root has its own default.
    # Freeze both explicitly; never read/copy auth files.
    config = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    personal = tomllib.loads(config.read_text()) if config.exists() else {}
    profile = {key: personal[key] for key in ("model", "model_reasoning_effort") if key in personal}
    defaults = {"narrative_language": "zh-CN"}
    if "model" in profile:
        defaults["model"] = profile["model"]
    if "model_reasoning_effort" in profile:
        defaults["reasoning_effort"] = profile["model_reasoning_effort"]
    write(root / "agent-settings.json", {"schema_version": 1, "defaults": defaults})
    (root / "approval-secret").write_bytes(os.urandom(32))
    (root / "approval-secret").chmod(0o600)
    manifest = {str(p.relative_to(build)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (build / "wheelhouse").glob("*.whl")}
    from scidiscovery.agent_execution_settings import ProgressionSettings
    root_settings = ProgressionSettings()
    root_profile = {"model": root_settings.root_model, "model_reasoning_effort": root_settings.root_reasoning_effort}
    write(root / "candidate.json", {"python": str(installed.python), "project": str(project),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=guard.ROOT, text=True).strip(),
        "wheels": manifest, "profile": root_profile, "worker_profile": profile, "distribution": distribution,
        "plugin_configs": plugin_configs, "task": TASK if task is None else task,
        "scope": "core only; no TCAD" if distribution == "core" else "core and three domain plugins; task defines live acceptance scope",
        "b0a_passed": False})


class Host:
    def __init__(self, root: Path, limits: dict):
        self.root, self.limits = root, limits
        self.connection = None
        self.root_host = None
        self.children, self.streams = [], []
        self.done, self.usage, self.items = {}, {}, []
        self.started_threads = set()
        self.thread = None
        self.platform_session = None
        self.last_rpc_error = None
        self.resources = host_resources(root)
        self.phase = "startup"
        self.phase_deadline = time.monotonic() + self.resources["startup_timeout_seconds"]
        self.logdir = Path(os.environ["SCID_TEST_LOG_DIR"])
        self.events = (self.logdir / "events.log").open("w")
        self.config = json.loads((root / "candidate.json").read_text())
        self.environment = dict(os.environ)
        for key in ("CODEX_SESSION_ID", "CODEX_THREAD_ID", "SCIDISCOVERY_ROLE_DIR", "PYTHONPATH"):
            self.environment.pop(key, None)
        self.environment.update(PYTHONNOUSERSITE="1", SCID_AGENT_SETTINGS_FILE=str(root / "agent-settings.json"))

    def status(self, state, **details):
        phase = {"awaiting_user": "instance_wait", "resuming_workers": "execution",
                 "scientific_turn": "execution"}.get(state)
        if phase is not None and phase != self.phase:
            self.phase = phase
            self.phase_deadline = time.monotonic() + self.resources[phase + "_timeout_seconds"]
        write(self.root / "progress.json", {"state": state, "b0a_passed": False,
            "evidence": str(self.logdir.parent), **details})

    def launch(self, command, name, pipe=False):
        log = (self.logdir / (name + ".log")).open("wb")
        self.streams.append(log)
        child = subprocess.Popen(command, cwd=self.config["project"], env=self.environment,
            stdin=subprocess.PIPE if pipe else subprocess.DEVNULL,
            stdout=subprocess.PIPE if pipe else log, stderr=log, bufsize=0)
        self.children.append(child)
        return child

    def checkpoint(self):
        if time.monotonic() >= self.phase_deadline:
            raise TimeoutError(self.phase + "_timeout")
        if (self.root / "stop").exists():
            raise RuntimeError("user_stop")
        if any(p.poll() is not None for p in self.children):
            raise RuntimeError("owned_process_exited")

    def pump(self):
        self.checkpoint()
        if self.connection is not None:
            self.connection.poll(.1)

    def observe(self, message):
        method, params = message.get("method"), message.get("params", {})
        if method == "scid/rpcError":
            error = params["error"]
            self.last_rpc_error = {"method": params["method"], "code": error.get("code"),
                                   "diagnostic": rpc_diagnostic(error)}
            with (self.logdir / "rpc-errors.log").open("a") as stream:
                stream.write(json.dumps(params, ensure_ascii=False) + "\n")
            return
        if method in ("thread/tokenUsage/updated", "item/completed", "turn/started", "turn/completed", "thread/started", "error"):
            self.events.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.events.flush()
        if method == "turn/started":
            self.started_threads.add(params["threadId"])
        elif method == "thread/tokenUsage/updated":
            self.usage[params["threadId"]] = params["tokenUsage"]["total"]
            self.save_usage()
        elif method == "turn/completed":
            self.done[(params["threadId"], params["turn"]["id"])] = params["turn"]
        elif method == "item/completed":
            item = params.get("item", {})
            self.items.append({"thread": params.get("threadId"), "type": item.get("type"),
                "bytes": len(json.dumps(message, ensure_ascii=False).encode()),
                "tool": item.get("tool"), "status": item.get("status")})
            if params.get("threadId") == self.thread and item.get("type") == "agentMessage":
                (self.root / "latest-root-message.txt").write_text(item.get("text", ""))

    def rpc(self, method, params):
        return self.connection.rpc(method, params)

    def turn(self, prompt):
        self.root_host.start_turn(prompt)
        result = self.root_host.wait_turn(max(.001, self.phase_deadline - time.monotonic()))
        if result["status"] != "completed":
            raise RuntimeError("root_turn_failed")

    def start_services(self):
        root, python = self.root, self.config["python"]
        plugin_arguments = [argument for name, path in self.config.get("plugin_configs", {}).items()
                            for argument in ("--plugin-config", name + "=" + path)]
        base = [python, "-m", "scidiscovery.artifact_agent.interfaces.cli", "--project-root", self.config["project"],
                "--state-root", str(root / "state"), "--approval-secret-file", str(root / "approval-secret")]
        self.launch(base + ["serve-approval-ui", "--port", "0", "--worker-backend", "local",
            "--local-workspace-root", str(Path(self.config["project"]) / ".scidiscovery-runs"),
            *plugin_arguments], "ui")
        deadline = time.monotonic() + 20
        url = None
        while time.monotonic() < deadline and url is None:
            if self.children[0].poll() is not None:
                raise RuntimeError("ui_exited")
            for line in (self.logdir / "ui.log").read_text().splitlines():
                try:
                    url = json.loads(line).get("approval_ui") or url
                except ValueError:
                    pass
            time.sleep(.1)
        if url is None:
            raise TimeoutError("ui_startup")
        self.ui_url = url
        self.launch([python, "-m", "scidiscovery.artifact_agent.interfaces.mcp_daemon",
            "--project-root", self.config["project"], "--state-root", str(root / "state"),
            "--socket", str(root / "control.sock"), "--approval-secret-file", str(root / "approval-secret"),
            "--approval-base-url", url, "--worker-backend", "local",
            "--local-workspace-root", str(Path(self.config["project"]) / ".scidiscovery-runs"),
            "--runtime-summary", str(root / "runtime-summary.json"), *plugin_arguments], "daemon")
        deadline = time.monotonic() + 20
        while not control_socket_ready(root / "control.sock"):
            if time.monotonic() > deadline or any(p.poll() is not None for p in self.children):
                raise RuntimeError("daemon_startup")
            time.sleep(.1)
    def initialize_host(self, resume=False, *, check_native=True):
        if check_native:
            probe_native_code_mode(self.logdir, self.resources)
        self.start_services()
        root = self.root
        # The exact generated project profile is passed explicitly, avoiding a
        # personal project trust mutation. Disable unrelated inherited MCPs.
        config = tomllib.loads((Path(self.config["project"]) / ".codex/config.toml").read_text())
        personal_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
        personal = tomllib.loads(personal_path.read_text()) if personal_path.exists() else {}
        disabled = {name: {"enabled": False} for name in personal.get("mcp_servers", {})
                    if name != "scidiscovery"}
        overrides = config_flags({"mcp_servers": disabled}) + config_flags(config)
        self.app = self.launch_app(overrides)
        self.attach_connection()
        self.expected_config = config
        self.root_host.initialize(cwd=self.config["project"], expected_config=config)
        params = thread_start_params(self.config["project"])
        params.update({"model": self.config["profile"]["model"]} if "model" in self.config["profile"] else {})
        if "model_reasoning_effort" in self.config["profile"]:
            params["config"] = {"model_reasoning_effort": self.config["profile"]["model_reasoning_effort"]}
        prior = json.loads((root / "live/thread.json").read_text()) if resume else None
        identity = self.root_host.open_root(cwd=self.config["project"],
            prior=RootIdentity(**prior) if prior else None, options=params)
        self.thread, self.platform_session = identity.thread_id, identity.session_id
        write(self.logdir.parent / "thread.json", {"thread_id": self.thread, "session_id": self.platform_session})
        inventory, cursor = [], None
        while True:
            page = self.rpc("mcpServerStatus/list", {"threadId": self.thread, "limit": 20, "cursor": cursor})
            inventory.extend(page["data"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        server = next((v for v in inventory if v["name"] == "scidiscovery"), None)
        required = {"scid_catalog", "scid_describe", "scid_call"}
        if server is None or server.get("toolsError") or not required.issubset(server.get("tools", {})):
            raise RuntimeError("scidiscovery_tools_unavailable")
        self.status("checking_instance_without_model")
        value = self.current_instance()
        write(self.logdir.parent / "host-check.json", {"status": "passed", "model_requests": 0,
            "config_loaded": True, "tools": sorted(required), "instance_state": value.get("state"),
            "code_mode_execution": "native_arithmetic_passed" if check_native else "not_probed", "b0a_passed": False})
        return value

    def attach_connection(self):
        self.connection = AppServer(self.app, limits=HostLimits(
            rpc_timeout_seconds=self.resources.get("rpc_timeout_seconds", 30),
            termination_grace_seconds=self.limits["termination_grace_seconds"],
            frame_bytes=self.resources.get("protocol_frame_bytes", self.limits["log_bytes"])),
            on_event=self.observe, checkpoint=self.checkpoint)
        self.root_host = CodexRootHost(self.connection)

    def reconnect_root(self):
        self.attach_connection()
        self.root_host.initialize(cwd=self.config["project"], expected_config=self.expected_config)
        self.root_host.open_root(cwd=self.config["project"],
            prior=RootIdentity(self.thread, self.platform_session))

    def current_instance(self):
        # Client-initiated MCP calls have no model turn. Adapt only the actual
        # coordinates returned by thread/start; never accept caller-supplied IDs.
        # This carries platform identity, not an instance selection/authorization.
        reply = self.rpc("mcpServer/tool/call", {"threadId": self.thread, "server": "scidiscovery",
            "tool": "scid_call", "arguments": {"name": "instance_current", "arguments": {}},
            "_meta": {"x-codex-turn-metadata": {
                "session_id": self.platform_session, "thread_id": self.thread}}})
        with (self.logdir / "instance-check.log").open("a") as stream:
            stream.write(json.dumps(reply, ensure_ascii=False) + "\n")
        return instance_result(reply, self.ui_url)

    def launch_app(self, overrides):
        return self.launch([shutil.which("codex"), "app-server", "--stdio", *overrides], "app", True)

    def await_instance(self, value):
        if value.get("state") == "unbound":
            (self.root / "latest-root-message.txt").write_text(value["management_url"])
            marker = self.logdir.parent / "continue"
            self.status("awaiting_user", management_url=value["management_url"],
                        message_file=str(self.root / "latest-root-message.txt"))
            while not marker.exists():
                self.pump()
            marker.unlink()
            value = self.current_instance()
        if value.get("state") != "active":
            raise RuntimeError("instance_not_selected")

    def bind_only(self):
        """Wait for user-page selection; never request a model turn."""
        value = self.initialize_host(check_native=False)
        if value.get("state") == "unbound":
            (self.root / "latest-root-message.txt").write_text(value["management_url"])
            self.status("awaiting_user", management_url=value["management_url"], model_requests=0)
            while value.get("state") == "unbound":
                until = time.monotonic() + 1
                while time.monotonic() < until:
                    self.pump()
                value = self.current_instance()
        if value.get("state") != "active":
            raise RuntimeError("instance_not_selected")
        write(self.logdir.parent / "binding.json", dict(instance=value, model_requests=0, worker_dispatches=0))
        self.status("instance_bound_without_model_turn", model_requests=0, worker_dispatches=0)

    def run(self, resume=False, task=None):
        if task is not None and not resume:
            raise ValueError("an explicit continuation requires resume")
        self.await_instance(self.initialize_host(resume=resume))
        self.status("resuming_workers" if resume else "scientific_turn", resumed=resume)
        if resume:
            if task is not None:
                # The supervisor froze this explicit task after checking durable
                # quiescence. Do not replay the original task or restore its workers.
                self.status("scientific_turn", resumed=True, explicit_continuation=True)
                self.turn(task)
                self.status("root_returned_requires_sealed_audit", resumed=True)
                return
            # Platform completion only prevents unnecessary thread restoration;
            # the Root must still verify the control plane's sealed Run result.
            workers, completed = set(), set()
            for line in (self.root / "live/fixture-logs/events.log").read_text().splitlines():
                item = json.loads(line).get("params", {}).get("item", {})
                if item.get("type") != "subAgentActivity":
                    continue
                if item.get("kind") == "started":
                    workers.add(item["agentThreadId"])
                elif item.get("kind") == "completed":
                    completed.add(item["agentThreadId"])
            for thread in sorted(workers - completed):
                restored = self.rpc("thread/resume", {"threadId": thread, "excludeTurns": True})["thread"]
                if restored.get("id") != thread or restored.get("sessionId") != self.platform_session:
                    raise RuntimeError("resumed_worker_identity_changed")
            self.status("scientific_turn", resumed=True)
            self.turn(RESUME_TASK)
            self.status("root_returned_requires_sealed_audit", resumed=True)
            return
        self.turn(self.config.get("task", TASK))
        self.status("root_returned_requires_sealed_audit")

    def save_usage(self):
        write(self.logdir.parent / "usage.json", {"root_thread": self.thread, "threads": self.usage,
            "items": self.items, "coverage": "received host notifications only; child coverage requires audit",
            "b0a_passed": False})

    def close(self):
        self.save_usage()
        if self.connection is not None:
            self.connection.close()
        self.events.close()
        for child in reversed(self.children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(self.children):
            try:
                child.wait(timeout=self.limits["termination_grace_seconds"])
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            for stream in (child.stdin, child.stdout):
                if stream:
                    stream.close()
        for stream in self.streams:
            stream.close()


def supervised(root, action, task_file=None):
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())["limits"]
    resources = host_resources(root)
    if action in ("bind", "live", "resume", "lifecycle", "lifecycle-resume"):
        limits["timeout_seconds"] = sum(resources[key] for key in
            ("startup_timeout_seconds", "instance_wait_timeout_seconds", "execution_timeout_seconds"))
    output = root / (action if action not in ("check", "verify", "native", "resume", "lifecycle", "lifecycle-resume") else f"{action}-{time.time_ns()}")
    with (Path("/tmp") / f"scid-tests-{os.getuid()}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior_evidence = json.loads((root / "progress.json").read_text())["evidence"] if task_file is not None else None
        task = continuation_task(root, task_file) if task_file is not None else None
        if action == "lifecycle":
            try:
                from scripts.probe_root_lifecycle import require_no_started_lifecycle
            except ModuleNotFoundError:
                from probe_root_lifecycle import require_no_started_lifecycle
            require_no_started_lifecycle(root)
        if action == "lifecycle-resume":
            try:
                from scripts.probe_root_lifecycle import require_lifecycle_resume
            except ModuleNotFoundError:
                from probe_root_lifecycle import require_lifecycle_resume
            require_lifecycle_resume(root)
        output.mkdir()
        (output / "fixture-logs").mkdir()
        task_arguments = []
        if task is not None:
            frozen = output / "task.txt"
            frozen.write_text(task)
            write(output / "task-source.json", {"sha256": hashlib.sha256(task.encode()).hexdigest(),
                "source": str(task_file), "prior_evidence": prior_evidence,
                "kind": "explicit_acceptance_continuation"})
            task_arguments = ["--task-file", str(frozen)]
        if action in ("resume", "lifecycle", "lifecycle-resume"):
            (root / "stop").unlink(missing_ok=True)
        if action in ("bind", "live", "resume", "lifecycle", "lifecycle-resume"):
            write(root / "progress.json", {"state": "starting", "evidence": str(output), "b0a_passed": False})
        environment = dict(os.environ)
        environment.update(SCID_HOST_PROBE_LOCK_FD=str(lock.fileno()), SCID_TEST_LOG_DIR=str(output / "fixture-logs"),
                           SCID_TEST_LOG_BYTES=str(limits["log_bytes"]), PYTHONDONTWRITEBYTECODE="1")
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "TOKIO_WORKER_THREADS", "RAYON_NUM_THREADS"):
            environment[key] = "1"
        result = guard.run_one([sys.executable, str(Path(__file__).resolve()), "_" + action,
                              "--candidate", str(root), *task_arguments], environment, limits, output, lock.fileno())
        write(output / "resource.json", result)
        if result["returncode"] != 0 or result["stop_reason"] != "exited":
            previous = json.loads((root / "progress.json").read_text()) if (root / "progress.json").exists() else {}
            write(root / "progress.json", {**previous, "state": "stopped", "resource": result, "b0a_passed": False})
        check = output / "host-check.json"
        print(json.dumps({"evidence": str(output), "resource": result,
            "host_check": json.loads(check.read_text()) if check.exists() else None}), flush=True)
        return 0 if result["returncode"] == 0 and result["stop_reason"] == "exited" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bind", "supervise-bind", "_bind", "prepare", "prepare-upgrade", "check", "verify", "native", "stop", "start", "resume", "lifecycle", "lifecycle-resume", "continue", "supervise", "supervise-resume", "supervise-lifecycle", "supervise-lifecycle-resume", "_prepare", "_prepare-upgrade", "_live", "_resume", "_lifecycle", "_lifecycle-resume", "_check", "_verify", "_native"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--from-candidate", type=Path, help="Stopped candidate whose scientific state is copied")
    parser.add_argument("--installed-candidate", type=Path, help="Candidate providing the new installed program")
    parser.add_argument("--task-file", type=Path, help="Explicit next task after completed work; resume only")
    args = parser.parse_args()
    root = args.candidate.resolve()
    if args.task_file is not None:
        if args.action not in ("resume", "supervise-resume", "_resume"):
            parser.error("--task-file is only supported with resume")
        args.task_file = args.task_file.resolve()
    os.umask(0o077)
    if args.action in ("prepare", "prepare-upgrade"):
        if len(os.fsencode(root / "control.sock")) >= 104:
            parser.error("candidate path too long for Unix socket; use a short persistent workspace path")
        if args.action == "prepare-upgrade":
            if args.from_candidate is None or args.installed_candidate is None:
                parser.error("prepare-upgrade requires --from-candidate and --installed-candidate")
            for path in (args.from_candidate.resolve(), args.installed_candidate.resolve()):
                if root == path or root in path.parents or path in root.parents:
                    parser.error("upgrade candidate must be separate from source and installation")
                if not (path / "candidate.json").is_file():
                    parser.error("source and installation must be prepared candidates")
        root.mkdir(parents=True, exist_ok=False)
        if args.action == "prepare-upgrade":
            write(root / "upgrade-source.json", {"source_candidate": str(args.from_candidate.resolve()),
                "installed_candidate": str(args.installed_candidate.resolve())})
        return supervised(root, args.action)
    if args.action == "native":
        return supervised(root, "native")
    if args.action == "stop":
        (root / "stop").touch(exist_ok=True)
        return 0
    if args.action == "verify":
        result = preflight()
        if result["blockers"]:
            print(json.dumps(result))
            return 2
        return supervised(root, "verify")
    if args.action == "check":
        return supervised(root, "check")
    if args.action == "continue":
        progress = json.loads((root / "progress.json").read_text())
        if progress["state"] != "awaiting_user" or not progress.get("management_url"):
            parser.error("host is not awaiting instance selection")
        (Path(progress["evidence"]) / "continue").touch(exist_ok=False)
        return 0
    if args.action in ("bind", "start", "resume", "lifecycle", "lifecycle-resume"):
        if args.task_file is not None:
            continuation_task(root, args.task_file)
        result = preflight()
        if result["blockers"]:
            print(json.dumps(result))
            return 2
        resuming = args.action in ("resume", "lifecycle", "lifecycle-resume")
        if resuming and not all((root / p).exists() for p in
                ("live/thread.json", "live/fixture-logs/events.log", "state/database/runs.sqlite3")):
            parser.error("resume requires the original thread evidence and control state; do not recreate them")
        if args.action == "bind" and (root / "bind").exists():
            parser.error("binding attempt already exists; inspect progress and evidence")
        if (root / "live").exists() and not resuming:
            parser.error("this candidate has already run; inspect evidence, do not replay")
        # Explicit resume reconciles existing work, never replays the original prompt.
        launch_log = root / (f"{args.action}-launch-{time.time_ns()}.log" if resuming else "launch.log")
        launched_at = time.time_ns()
        with launch_log.open("xb") as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                "supervise-" + args.action if resuming or args.action == "bind" else "supervise", "--candidate", str(root),
                *(["--task-file", str(args.task_file)] if args.task_file is not None else [])],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        print(f"Host started (pid {child.pid}); waiting for Root's instance URL. "
              f"Evidence: {root}. Human selection and execution use separate budgets.", flush=True)
        if resuming:
            print(f"Resuming existing threads and state. Log: {launch_log}", flush=True)
        while child.poll() is None:
            if (root / "progress.json").exists() and (root / "progress.json").stat().st_mtime_ns >= launched_at:
                progress = json.loads((root / "progress.json").read_text())
                if progress["state"] == "awaiting_user":
                    print((root / "latest-root-message.txt").read_text(), flush=True)
                    if args.action == "bind":
                        print("Create/select a clean instance on the page. Selection is detected automatically; no model will run.", flush=True)
                        return 0
                    print("After selecting an instance, run: " + shlex.join([sys.executable, str(Path(__file__).resolve()),
                          "continue", "--candidate", str(root)]), flush=True)
                    return 0
                if args.action == "bind" and progress["state"] == "instance_bound_without_model_turn":
                    print("Instance selected; no model requests. Evidence: " + progress["evidence"], flush=True)
                    return 0
                if resuming and progress["state"] in ("scientific_turn", "root_returned_requires_sealed_audit"):
                    print("Existing instance binding confirmed; resumed scientific turn.", flush=True)
                    return 0
                if progress["state"] in ("failed", "stopped"):
                    print(json.dumps(progress, ensure_ascii=False), flush=True)
                    return 1
            time.sleep(.2)
        print(f"Supervisor exited; inspect {launch_log} and progress.json", flush=True)
        return 1
    if args.action in ("supervise-bind", "supervise", "supervise-resume", "supervise-lifecycle", "supervise-lifecycle-resume"):
        return supervised(root, args.action.removeprefix("supervise-") if "-" in args.action else "live", args.task_file)
    descriptor = int(os.environ["SCID_HOST_PROBE_LOCK_FD"])
    info, expected = os.fstat(descriptor), (Path("/tmp") / f"scid-tests-{os.getuid()}.lock").stat()
    if (info.st_dev, info.st_ino) != (expected.st_dev, expected.st_ino):
        raise RuntimeError("supervision_required")
    if args.action == "_prepare":
        prepare(root)
    elif args.action == "_prepare-upgrade":
        try:
            from scripts.root_host_upgrade import prepare_upgrade
        except ModuleNotFoundError:
            from root_host_upgrade import prepare_upgrade
        prepare_upgrade(root)
    elif args.action == "_native":
        result = probe_native_code_mode(Path(os.environ["SCID_TEST_LOG_DIR"]), json.loads(HOST_RESOURCES.read_text()))
        write(Path(os.environ["SCID_TEST_LOG_DIR"]).parent / "host-check.json", result)
    else:
        host_class = Host
        if args.action in ("_lifecycle", "_lifecycle-resume"):
            try:
                from scripts.probe_root_lifecycle import LifecycleHost
            except ModuleNotFoundError:
                from probe_root_lifecycle import LifecycleHost
            host_class = LifecycleHost
        host = host_class(root, json.loads(guard.DEFAULT_CONFIG.read_text())["limits"])
        host.resume_existing = args.action == "_lifecycle-resume"
        try:
            if args.action == "_bind":
                host.bind_only()
            elif args.action == "_check":
                host.start_services()
                host.status("services_checked_without_model_turn")
            elif args.action == "_verify":
                host.initialize_host()
                host.status("host_checked_without_model_turn", model_requests=0)
            else:
                host.run(resume=args.action == "_resume",
                         task=args.task_file.read_text() if args.task_file is not None else None)
        except BaseException as error:
            if args.action == "_verify":
                write(host.logdir.parent / "host-check.json", {"status": "failed", "model_requests": 0,
                    "diagnostic": str(error), "rpc_error": host.last_rpc_error, "b0a_passed": False})
            host.status("failed", failure_type=type(error).__name__, diagnostic=str(error))
            raise
        finally:
            host.close()
            if args.task_file is not None:
                _run_logged([host.config["python"], str(Path(__file__).with_name("root_host_usage.py")),
                    "--candidate", str(root), "--evidence", str(host.logdir.parent)],
                    cwd=host.config["project"], env=host.environment, timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
