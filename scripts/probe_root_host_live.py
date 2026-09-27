"""Isolated B0a candidate and bounded real-host probe (never a production service).

Run prepare under Codex; run start in an ordinary host terminal. Read progress.json
and latest-root-message.txt, select the instance in the UI, then run continue.
Startup, human selection and execution have separate configured time budgets.
Resume reuses actual platform threads and existing state; it never renews a Run
deadline. Resource stop still does not prove independent Worker life.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import selectors
import shlex
import shutil
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

HOST_RESOURCES = Path(__file__).with_name("root_host_resources.json")

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


def turn_params(thread: str, prompt: str) -> dict:
    return {"threadId": thread, "input": [{"type": "text", "text": prompt}]}



def require_config(expected: dict, actual: dict):
    for key, value in expected.items():
        if key not in actual:
            raise RuntimeError("effective_config_missing:" + key)
        if isinstance(value, dict):
            require_config(value, actual[key])
        elif value != actual[key]:
            raise RuntimeError("effective_config_mismatch:" + key)


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


def prepare(root: Path):
    build = root / "build"
    build.mkdir()
    installed = create_environments(guard.ROOT, build)["core"]
    project = installed.workdir
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("SCIDISCOVERY_ROLE_DIR", None)
    environment["PYTHONNOUSERSITE"] = "1"
    _run_logged([str(installed.python), "-m", "scidiscovery.artifact_agent.interfaces.cli",
        "--project-root", str(project), "--state-root", str(root / "state"), "init", "codex",
        "--python", str(installed.python), "--control-socket", str(root / "control.sock")],
        cwd=project, env=environment, timeout=120)
    # Freeze the normal host's chosen model settings; never read/copy auth files.
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
    manifest = {str(p.relative_to(build)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (build / "wheelhouse").glob("*.whl")}
    write(root / "candidate.json", {"python": str(installed.python), "project": str(project),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=guard.ROOT, text=True).strip(),
        "wheels": manifest, "profile": profile, "scope": "core only; no TCAD",
        "b0a_passed": False})


class Host:
    def __init__(self, root: Path, limits: dict):
        self.root, self.limits = root, limits
        self.selector = selectors.DefaultSelector()
        self.children, self.streams = [], []
        self.buffer, self.counter, self.responses = b"", 0, {}
        self.done, self.usage, self.items = {}, {}, []
        self.started_threads = set()
        self.thread = None
        self.platform_session = None
        self.last_rpc_error = None
        self.resources = json.loads(HOST_RESOURCES.read_text())
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

    def pump(self):
        if time.monotonic() >= self.phase_deadline:
            raise TimeoutError(self.phase + "_timeout")
        if (self.root / "stop").exists():
            raise RuntimeError("user_stop")
        if any(p.poll() is not None for p in self.children):
            raise RuntimeError("owned_process_exited")
        if not self.selector.select(.1):
            return
        data = os.read(self.app.stdout.fileno(), 65536)
        if not data:
            raise RuntimeError("app_server_closed")
        self.buffer += data
        if len(self.buffer) > self.limits["log_bytes"]:
            raise RuntimeError("protocol_message_limit")
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            message = json.loads(line)
            method, params = message.get("method"), message.get("params", {})
            if method and "id" in message:
                raise RuntimeError("unexpected_server_request:" + method)
            if "id" in message:
                self.responses[message["id"]] = message
                continue
            if method in ("thread/tokenUsage/updated", "item/completed", "turn/started", "turn/completed", "thread/started", "error"):
                self.events.write(json.dumps(message, ensure_ascii=False) + "\n")
                self.events.flush()
            if method == "turn/started":
                self.started_threads.add(params["threadId"])
            elif method == "thread/tokenUsage/updated":
                # Each notification is cumulative: replace, never sum snapshots.
                self.usage[params["threadId"]] = params["tokenUsage"]["total"]
                self.save_usage()
            elif method == "turn/completed":
                self.done[(params["threadId"], params["turn"]["id"])] = params["turn"]
            elif method == "item/completed":
                item = params.get("item", {})
                self.items.append({"thread": params.get("threadId"), "type": item.get("type"),
                    "bytes": len(line), "tool": item.get("tool"), "status": item.get("status")})
                if params.get("threadId") == self.thread and item.get("type") == "agentMessage":
                    (self.root / "latest-root-message.txt").write_text(item.get("text", ""))

    def rpc(self, method, params):
        self.counter += 1
        key = self.counter
        self.app.stdin.write((json.dumps({"id": key, "method": method, "params": params}) + "\n").encode())
        self.app.stdin.flush()
        deadline = time.monotonic() + 30
        while key not in self.responses:
            if time.monotonic() > deadline:
                raise TimeoutError("rpc_timeout:" + method)
            self.pump()
        reply = self.responses.pop(key)
        if "error" in reply:
            error = reply["error"]
            self.last_rpc_error = {"method": method, "code": error.get("code"),
                                   "diagnostic": rpc_diagnostic(error)}
            # Private, bounded evidence retains the cause; public output contains
            # only method/code/category, never raw server text or request params.
            with (self.logdir / "rpc-errors.log").open("a") as stream:
                stream.write(json.dumps({"method": method, "error": error}, ensure_ascii=False) + "\n")
            raise RuntimeError(method + ":" + self.last_rpc_error["diagnostic"])
        return reply["result"]

    def turn(self, prompt):
        result = self.rpc("turn/start", turn_params(self.thread, prompt))
        key = (self.thread, result["turn"]["id"])
        while key not in self.done:
            self.pump()
        if self.done[key]["status"] != "completed":
            raise RuntimeError("root_turn_failed")

    def start_services(self):
        root, python = self.root, self.config["python"]
        base = [python, "-m", "scidiscovery.artifact_agent.interfaces.cli", "--project-root", self.config["project"],
                "--state-root", str(root / "state"), "--approval-secret-file", str(root / "approval-secret")]
        self.launch(base + ["serve-approval-ui", "--port", "0", "--worker-backend", "local",
            "--local-workspace-root", str(Path(self.config["project"]) / ".scidiscovery-runs")], "ui")
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
            "--runtime-summary", str(root / "runtime-summary.json")], "daemon")
        deadline = time.monotonic() + 20
        while not (root / "control.sock").exists():
            if time.monotonic() > deadline or any(p.poll() is not None for p in self.children):
                raise RuntimeError("daemon_startup")
            time.sleep(.1)
    def initialize_host(self, resume=False):
        probe_native_code_mode(self.logdir, json.loads(HOST_RESOURCES.read_text()))
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
        self.selector.register(self.app.stdout, selectors.EVENT_READ)
        self.rpc("initialize", {"clientInfo": {"name": "scid_b0a_live", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
        self.app.stdin.write(b'{"method":"initialized","params":{}}\n')
        self.app.stdin.flush()
        effective = self.rpc("config/read", {"cwd": self.config["project"], "includeLayers": False})["config"]
        require_config(config, effective)
        params = thread_start_params(self.config["project"])
        params["ephemeral"] = False
        params.update({"model": self.config["profile"]["model"]} if "model" in self.config["profile"] else {})
        if "model_reasoning_effort" in self.config["profile"]:
            params["config"] = {"model_reasoning_effort": self.config["profile"]["model_reasoning_effort"]}
        prior = json.loads((root / "live/thread.json").read_text()) if resume else None
        result = self.rpc("thread/resume", {"threadId": prior["thread_id"],
            "cwd": self.config["project"], "excludeTurns": True}) if resume else self.rpc("thread/start", params)
        if not result["thread"].get("id") or not result["thread"].get("sessionId"):
            raise RuntimeError("actual_platform_identity_missing")
        self.thread = result["thread"]["id"]
        self.platform_session = result["thread"]["sessionId"]
        if prior and (self.thread != prior["thread_id"] or self.platform_session != prior["session_id"]):
            raise RuntimeError("resumed_platform_identity_changed")
        if self.thread != self.platform_session:
            raise RuntimeError("probe_requires_actual_root_thread")
        write(self.logdir.parent / "thread.json", {"thread_id": self.thread, "session_id": result["thread"].get("sessionId")})
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
            "code_mode_execution": "native_arithmetic_passed", "b0a_passed": False})
        return value

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

    def run(self, resume=False):
        self.await_instance(self.initialize_host(resume=resume))
        self.status("resuming_workers" if resume else "scientific_turn", resumed=resume)
        if resume:
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
        self.turn(TASK)
        self.status("root_returned_requires_sealed_audit")

    def save_usage(self):
        write(self.logdir.parent / "usage.json", {"root_thread": self.thread, "threads": self.usage,
            "items": self.items, "coverage": "received host notifications only; child coverage requires audit",
            "b0a_passed": False})

    def close(self):
        self.save_usage()
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
        self.selector.close()


def supervised(root, action):
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())["limits"]
    resources = json.loads(HOST_RESOURCES.read_text())
    if action in ("live", "resume", "lifecycle", "lifecycle-resume"):
        limits["timeout_seconds"] = sum(resources[key] for key in
            ("startup_timeout_seconds", "instance_wait_timeout_seconds", "execution_timeout_seconds"))
    output = root / (action if action not in ("check", "verify", "native", "resume", "lifecycle", "lifecycle-resume") else f"{action}-{time.time_ns()}")
    with (Path("/tmp") / f"scid-tests-{os.getuid()}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
        if action in ("resume", "lifecycle", "lifecycle-resume"):
            (root / "stop").unlink(missing_ok=True)
        if action in ("live", "resume", "lifecycle", "lifecycle-resume"):
            write(root / "progress.json", {"state": "starting", "evidence": str(output), "b0a_passed": False})
        environment = dict(os.environ)
        environment.update(SCID_HOST_PROBE_LOCK_FD=str(lock.fileno()), SCID_TEST_LOG_DIR=str(output / "fixture-logs"),
                           SCID_TEST_LOG_BYTES=str(limits["log_bytes"]), PYTHONDONTWRITEBYTECODE="1")
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "TOKIO_WORKER_THREADS", "RAYON_NUM_THREADS"):
            environment[key] = "1"
        result = guard.run_one([sys.executable, str(Path(__file__).resolve()), "_" + action,
                              "--candidate", str(root)], environment, limits, output, lock.fileno(),
                              limit_address_space=json.loads(HOST_RESOURCES.read_text())["limit_address_space"]
                              if action in ("verify", "live", "native", "resume", "lifecycle", "lifecycle-resume") else True)
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
    parser.add_argument("action", choices=("prepare", "check", "verify", "native", "stop", "start", "resume", "lifecycle", "lifecycle-resume", "continue", "supervise", "supervise-resume", "supervise-lifecycle", "supervise-lifecycle-resume", "_prepare", "_live", "_resume", "_lifecycle", "_lifecycle-resume", "_check", "_verify", "_native"))
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    root = args.candidate.resolve()
    os.umask(0o077)
    if args.action == "prepare":
        if len(os.fsencode(root / "control.sock")) >= 104:
            parser.error("candidate path too long for Unix socket; use a short persistent workspace path")
        root.mkdir(parents=True, exist_ok=False)
        return supervised(root, "prepare")
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
    if args.action in ("start", "resume", "lifecycle", "lifecycle-resume"):
        result = preflight()
        if result["blockers"]:
            print(json.dumps(result))
            return 2
        resuming = args.action in ("resume", "lifecycle", "lifecycle-resume")
        if resuming and not all((root / p).exists() for p in
                ("live/thread.json", "live/fixture-logs/events.log", "state/database/runs.sqlite3")):
            parser.error("resume requires the original thread evidence and control state; do not recreate them")
        if (root / "live").exists() and not resuming:
            parser.error("this candidate has already run; inspect evidence, do not replay")
        # Explicit resume reconciles existing work, never replays the original prompt.
        launch_log = root / (f"{args.action}-launch-{time.time_ns()}.log" if resuming else "launch.log")
        launched_at = time.time_ns()
        with launch_log.open("xb") as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                "supervise-" + args.action if resuming else "supervise", "--candidate", str(root)],
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
                    print("After selecting an instance, run: " + shlex.join([sys.executable, str(Path(__file__).resolve()),
                          "continue", "--candidate", str(root)]), flush=True)
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
    if args.action in ("supervise", "supervise-resume", "supervise-lifecycle", "supervise-lifecycle-resume"):
        return supervised(root, args.action.removeprefix("supervise-") if "-" in args.action else "live")
    descriptor = int(os.environ["SCID_HOST_PROBE_LOCK_FD"])
    info, expected = os.fstat(descriptor), (Path("/tmp") / f"scid-tests-{os.getuid()}.lock").stat()
    if (info.st_dev, info.st_ino) != (expected.st_dev, expected.st_ino):
        raise RuntimeError("supervision_required")
    if args.action == "_prepare":
        prepare(root)
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
            if args.action == "_check":
                host.start_services()
                host.status("services_checked_without_model_turn")
            elif args.action == "_verify":
                host.initialize_host()
                host.status("host_checked_without_model_turn", model_requests=0)
            else:
                host.run(resume=args.action == "_resume")
        except BaseException as error:
            if args.action == "_verify":
                write(host.logdir.parent / "host-check.json", {"status": "failed", "model_requests": 0,
                    "diagnostic": str(error), "rpc_error": host.last_rpc_error, "b0a_passed": False})
            host.status("failed", failure_type=type(error).__name__, diagnostic=str(error))
            raise
        finally:
            host.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
