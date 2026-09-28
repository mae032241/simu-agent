"""Check B0a host prerequisites and optionally initialize a bounded Codex thread.

This engineering probe never sends turn/start, dispatches Workers, binds an
instance, or proves autonomous research. It uses the current user's credentials
through Codex itself; credentials are never copied into the evidence directory.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time
import tomllib

# Engineering scripts use their matching checkout/release adapter; scientific
# candidate subprocesses still use their explicitly installed interpreter.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scidiscovery.platforms.codex_app_server import AppServer, HostLimits, config_flags, rpc_diagnostic

try:
    from scripts import run_tests as guard
except ModuleNotFoundError:
    import run_tests as guard


def daemon_directory_check(path: Path, uid: int) -> dict:
    """Inspect without modifying a native daemon directory or following links."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"status": "absent", "blocked": False}
    except OSError:
        return {"status": "inaccessible", "blocked": True}
    mode = stat.S_IMODE(info.st_mode)
    valid = stat.S_ISDIR(info.st_mode) and info.st_uid == uid and mode == 0o700
    return {"status": "compatible" if valid else "incompatible",
            "blocked": not valid, "owned": info.st_uid == uid, "mode": oct(mode)}


def preflight() -> dict:
    native = daemon_directory_check(Path("/tmp") / f"codex-daemon-{os.getuid()}", os.getuid())
    executable = shutil.which("codex")
    blockers = []
    if not executable:
        blockers.append("codex_executable_missing")
    if native["blocked"]:
        blockers.append("native_daemon_directory_blocked")
    return {"phase": "environment", "status": "blocked" if blockers else "ready_for_initialize",
            "blockers": blockers, "native_daemon_directory": native,
            "codex_available": executable is not None, "model_requests": 0,
            "worker_dispatches": 0, "b0a_passed": False}


def thread_start_params(workspace: str) -> dict:
    return {"cwd": workspace, "ephemeral": True,
            "approvalPolicy": "never", "sandbox": "workspace-write"}


def _protocol_probe(output: Path, limits: dict) -> int:
    """Child of the existing resource supervisor; no model turn is permitted."""
    # Check again after waiting for the serial lock, before starting Codex.
    result = preflight()
    if result["blockers"]:
        (output / "protocol.json").write_text(json.dumps(result, indent=2) + "\n")
        return 2
    deadline = time.monotonic() + limits["timeout_seconds"]
    result.update(phase="protocol", status="failed", completed_methods=[])
    connection = None
    workspace = None
    try:
        workspace = tempfile.TemporaryDirectory(prefix="workspace-", dir=output)
        scratch = workspace.name
        # Do not load the real research project's MCP servers or prompts.
        # User-configured MCP servers are disabled for this protocol-only probe.
        personal = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        config_path = personal / "config.toml"
        config_paths = [config_path, *(parent / ".codex/config.toml" for parent in Path(scratch).parents)]
        servers = set()
        for path in config_paths:
            if path.exists():
                servers.update(tomllib.loads(path.read_text()).get("mcp_servers", {}))
        overrides = []
        for name in sorted(servers):
            overrides.extend(config_flags({"mcp_servers": {name: {"enabled": False}}}))
        command = [shutil.which("codex"), "app-server", "--stdio", *overrides]
        environment = dict(os.environ)
        for key in ("CODEX_SESSION_ID", "CODEX_THREAD_ID", "SCIDISCOVERY_ROLE_DIR"):
            environment.pop(key, None)
        logs = output / "fixture-logs"
        logs.mkdir(exist_ok=True)
        with (logs / "app-server.log").open("wb") as error_log:
            def checkpoint():
                if time.monotonic() >= deadline:
                    raise TimeoutError("protocol_timeout")

            def observe(message):
                if message.get("method") == "scid/rpcError":
                    error = message["params"]["error"]
                    result["rpc_error_code"] = error.get("code")
                    result["diagnostic"] = rpc_diagnostic(error)

            connection = AppServer.launch(command, cwd=Path(scratch), environment=environment,
                stderr=error_log, limits=HostLimits(rpc_timeout_seconds=limits["timeout_seconds"],
                    termination_grace_seconds=limits["termination_grace_seconds"],
                    frame_bytes=limits["log_bytes"]), on_event=observe, checkpoint=checkpoint)

            def rpc(method, params):
                result["last_method"] = method
                reply = connection.rpc(method, params)
                result["completed_methods"].append(method)
                return reply

            rpc("initialize", {"clientInfo": {"name": "scid_root_host_probe", "version": "0.1.0"}})
            connection.notify("initialized", {})
            reply = rpc("thread/start", thread_start_params(scratch))
            thread = reply["thread"]
            result.update(status="initialized_without_model_turn",
                actual_thread_id_present=bool(thread.get("id")),
                actual_session_id_present=bool(thread.get("sessionId")))
            if not thread.get("id"):
                raise RuntimeError("thread_identity_missing")
    except Exception as error:
        result.update(status="failed", failure_type=type(error).__name__)
    finally:
        if connection is not None:
            connection.close()
        if workspace is not None:
            workspace.cleanup()
        (output / "protocol.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0 if result["status"] == "initialized_without_model_turn" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new private result directory")
    parser.add_argument("--initialize", action="store_true", help="also start a thread, without any model request")
    parser.add_argument("--protocol-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    limits = json.loads(guard.DEFAULT_CONFIG.read_text())["limits"]
    if args.protocol_child:
        # Only the supervisor may launch this child, with its still-held serial lock.
        descriptor = int(os.environ["SCID_HOST_PROBE_LOCK_FD"])
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError("supervision_required")
        return _protocol_probe(output, limits)
    os.umask(0o077)
    output.mkdir(parents=True, exist_ok=False)
    result = preflight()
    (output / "preflight.json").write_text(json.dumps(result, indent=2) + "\n")
    if result["blockers"] or not args.initialize:
        print(json.dumps(result))
        return 2 if result["blockers"] else 0
    with (Path("/tmp") / f"scid-tests-{os.getuid()}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            (output / "resource.json").write_text(json.dumps({"stop_reason": "serial_lock_busy"}) + "\n")
            print("serial_lock_busy: no process or model started")
            return 2
        environment = dict(os.environ)
        environment["SCID_HOST_PROBE_LOCK_FD"] = str(lock.fileno())
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "TOKIO_WORKER_THREADS", "RAYON_NUM_THREADS"):
            environment[key] = "1"
        (output / "fixture-logs").mkdir()
        command = [sys.executable, str(Path(__file__).resolve()), "--protocol-child", "--output", str(output)]
        measured = guard.run_one(command, environment, limits, output, lock.fileno())
        (output / "resource.json").write_text(json.dumps(measured, indent=2) + "\n")
        protocol_path = output / "protocol.json"
        protocol = json.loads(protocol_path.read_text()) if protocol_path.exists() else None
        print(json.dumps({"resource": measured, "protocol": protocol}))
        return 0 if measured["returncode"] == 0 and measured["stop_reason"] == "exited" else 1


if __name__ == "__main__":
    raise SystemExit(main())
