#!/usr/bin/env python3
"""Launch one compiled Operation in an isolated, memory-bounded Codex process.

This is an M7 debug harness, not a second production Worker runtime. Scientific
acceptance remains owned by the Run service and its sealed output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.compiled_worker_process_guard import (
        run_process_group as _run_process_group,
    )
except ModuleNotFoundError:  # Direct execution puts scripts/ on sys.path.
    from compiled_worker_process_guard import run_process_group as _run_process_group


_MESSAGE = (
    "完成已经为该 Operation 排队的受控 assignment；严格遵循编译角色，只使用该 "
    "Operation 的 Worker MCP 与获授权的原生能力，并通过受控提交结束。"
)
_RECEIPT_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_RECEIPT_FIELDS = {
    "agent_type",
    "aggregate_memory_limit_mib",
    "command_projection_sha256",
    "completed_at",
    "exit_code",
    "externally_sandboxed_debug",
    "invocation_id",
    "launch_projection",
    "launch_projection_sha256",
    "memory_limit_exceeded",
    "peak_process_tree_rss_kib",
    "profile_sha256",
    "schema_version",
    "started_at",
    "target_worker_server",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _toml_scalar(value: str) -> Any:
    return tomllib.loads(f"value={value}")["value"]


def _trusted_root(project_root: Path) -> Path:
    for candidate in (project_root, *project_root.parents):
        if (candidate / ".git").exists():
            return candidate
    return project_root


def _inside_codex_outer_sandbox() -> bool:
    try:
        return b"codex-linux-sandbox" in Path("/proc/1/cmdline").read_bytes()
    except OSError:
        return False


def _local_workspace_root(target: dict[str, Any]) -> Path:
    args = target.get("args")
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise ValueError("Operation Worker args are invalid")
    if args.count("--local-workspace-root") != 1:
        raise ValueError("local Operation Worker must declare one workspace root")
    index = args.index("--local-workspace-root")
    if index + 1 >= len(args):
        raise ValueError("local Operation Worker workspace root is missing")
    workspace_root = Path(args[index + 1])
    if not workspace_root.is_absolute():
        raise ValueError("local Operation Worker workspace root must be absolute")
    return (workspace_root / "workspaces").resolve()


def _load_launch_snapshot(project_root: Path, agent_type: str) -> dict[str, Any]:
    project_root = project_root.resolve()
    profile_path = project_root / ".codex/agents" / f"{agent_type}.toml"
    config = tomllib.loads((project_root / ".codex/config.toml").read_text("utf-8"))
    profile_bytes = profile_path.read_bytes()
    profile = tomllib.loads(profile_bytes.decode("utf-8"))
    if profile.get("name") != agent_type:
        raise ValueError("generated profile name does not match agent_type")
    features = profile.get("features")
    tools = profile.get("tools")
    if (
        profile.get("web_search") != "disabled"
        or not isinstance(features, dict)
        or set(features) != {"shell_tool", "unified_exec"}
        or type(features.get("shell_tool")) is not bool
        or features.get("unified_exec") is not features.get("shell_tool")
        or not isinstance(tools, dict)
        or set(tools) != {"view_image"}
        or type(tools.get("view_image")) is not bool
    ):
        raise ValueError("generated Operation profile has unsupported native tools")
    role_servers = profile.get("mcp_servers", {})
    if len(role_servers) != 1:
        raise ValueError("generated Operation profile must declare one Worker MCP")
    target_server, target = next(iter(role_servers.items()))
    parent_servers = config.get("mcp_servers", {})
    inherited = parent_servers.get(target_server)
    if inherited is None:
        raise ValueError("project config does not register the Operation Worker MCP")
    for key in ("command", "args", "enabled_tools", "env"):
        if inherited.get(key) != target.get(key):
            raise ValueError(f"parent and role Worker MCP disagree on {key}")
    codex = shutil.which("codex")
    if codex is None:
        raise ValueError("codex executable is unavailable")
    return {
        "agent_type": agent_type,
        "codex": codex,
        "parent_servers": parent_servers,
        "profile": profile,
        "profile_bytes": profile_bytes,
        "target": target,
        "target_server": target_server,
        "trusted_root": _trusted_root(project_root),
        "workspace_root": _local_workspace_root(target),
    }


def _launch_overrides(snapshot: dict[str, Any]) -> list[tuple[str, str]]:
    profile = snapshot["profile"]
    target_server = snapshot["target_server"]
    target = snapshot["target"]
    overrides = [
        ("developer_instructions", _toml_value(profile["developer_instructions"])),
        ("approval_policy", '"never"'),
        (
            f"projects.{_toml_value(str(snapshot['trusted_root']))}.trust_level",
            '"trusted"',
        ),
        ("model_reasoning_effort", _toml_value(snapshot["dispatch_reasoning_effort"])),
        ("agents.enabled", "false"),
        ("features.apps", "false"),
        ("web_search", _toml_value(profile["web_search"])),
    ]
    overrides.extend(
        (f"features.{key}", _toml_value(value))
        for key, value in profile["features"].items()
    )
    overrides.extend(
        (f"tools.{key}", _toml_value(value))
        for key, value in profile["tools"].items()
    )
    for server_name in snapshot["parent_servers"]:
        if server_name != target_server:
            overrides.extend(
                (
                    (f"mcp_servers.{server_name}.command", '"/bin/false"'),
                    (f"mcp_servers.{server_name}.enabled", "false"),
                )
            )
    prefix = f"mcp_servers.{target_server}"
    overrides.extend(
        (f"{prefix}.{key}", _toml_value(target[key]))
        for key in ("command", "args", "enabled_tools", "default_tools_approval_mode")
    )
    overrides.extend(
        (f"{prefix}.env.{key}", _toml_value(value))
        for key, value in target.get("env", {}).items()
    )
    overrides.extend(((f"{prefix}.enabled", "true"), (f"{prefix}.required", "true")))
    keys = [key for key, _ in overrides]
    if len(keys) != len(set(keys)):
        raise ValueError("launch overrides contain duplicate keys")
    return overrides


def _build_command_from_snapshot(
    snapshot: dict[str, Any], *, externally_sandboxed_debug: bool
) -> list[str]:
    command = [snapshot["codex"], "exec", "--ephemeral", "--ignore-user-config"]
    if externally_sandboxed_debug:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend(("--sandbox", "workspace-write"))
    command.extend(
        (
            "-C",
            str(snapshot["workspace_root"]),
            "-m",
            str(snapshot["dispatch_model"]),
        )
    )
    for key, value in _launch_overrides(snapshot):
        command.extend(("-c", f"{key}={value}"))
    command.append(_MESSAGE)
    return command


def _launch_projection(
    snapshot: dict[str, Any], command: list[str], *, externally_sandboxed_debug: bool
) -> dict[str, Any]:
    if command != _build_command_from_snapshot(
        snapshot, externally_sandboxed_debug=externally_sandboxed_debug
    ):
        raise ValueError("actual Codex command differs from the immutable launch plan")
    disabled = sorted(
        name for name in snapshot["parent_servers"] if name != snapshot["target_server"]
    )
    prefix = f"mcp_servers.{snapshot['target_server']}"
    overrides = dict(_launch_overrides(snapshot))
    return {
        "agent_type": snapshot["agent_type"],
        "all_non_target_parent_servers_disabled": all(
            _toml_scalar(overrides[f"mcp_servers.{name}.enabled"]) is False
            and _toml_scalar(overrides[f"mcp_servers.{name}.command"]) == "/bin/false"
            for name in disabled
        ),
        "command_projection_sha256": _canonical_digest(command),
        "developer_instructions_sha256": hashlib.sha256(
            profile_instruction.encode("utf-8")
        ).hexdigest()
        if isinstance((profile_instruction := snapshot["profile"]["developer_instructions"]), str)
        else "",
        "externally_sandboxed_debug": externally_sandboxed_debug,
        "model": snapshot["dispatch_model"],
        "reasoning_effort": snapshot["dispatch_reasoning_effort"],
        "native_capabilities": {
            **snapshot["profile"]["features"],
            **snapshot["profile"]["tools"],
        },
        "profile_sha256": hashlib.sha256(snapshot["profile_bytes"]).hexdigest(),
        "sandbox_mode": "outer_debug" if externally_sandboxed_debug else "workspace-write",
        "schema_version": 1,
        "target_worker_config_sha256": _canonical_digest(snapshot["target"]),
        "target_worker_server": snapshot["target_server"],
        "target_worker_tools": _toml_scalar(overrides[f"{prefix}.enabled_tools"]),
        "web_search": snapshot["profile"]["web_search"],
        "workspace_root_sha256": hashlib.sha256(
            str(snapshot["workspace_root"]).encode("utf-8")
        ).hexdigest(),
    }


def build_launch_plan(
    project_root: Path,
    agent_type: str,
    *,
    externally_sandboxed_debug: bool = False,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[list[str], str, dict[str, Any]]:
    snapshot = _load_launch_snapshot(project_root, agent_type)
    snapshot["dispatch_model"] = model or snapshot["profile"].get("model")
    snapshot["dispatch_reasoning_effort"] = reasoning_effort or snapshot["profile"].get("model_reasoning_effort", "medium")
    if not snapshot["dispatch_model"] or ("model" not in snapshot["profile"] and (model is None or reasoning_effort is None)):
        raise ValueError("dynamic Operation roles require model and reasoning_effort from the queued Run execution_profile")
    command = _build_command_from_snapshot(
        snapshot, externally_sandboxed_debug=externally_sandboxed_debug
    )
    return (
        command,
        snapshot["target_server"],
        _launch_projection(
            snapshot, command, externally_sandboxed_debug=externally_sandboxed_debug
        ),
    )


def build_command(
    project_root: Path,
    agent_type: str,
    *,
    externally_sandboxed_debug: bool = False,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[list[str], str]:
    command, server, _ = build_launch_plan(
        project_root,
        agent_type,
        model=model, reasoning_effort=reasoning_effort,
        externally_sandboxed_debug=externally_sandboxed_debug,
    )
    return command, server


def verify_receipt(
    *,
    receipt_path: Path,
    project_root: Path,
    agent_type: str,
    expected_target_server: str,
    allowed_worker_tools: set[str],
    required_worker_tools: set[str],
    run_started_at: str,
    run_completed_at: str,
    expected_memory_limit_mib: int,
    expected_external_sandbox_debug: bool,
) -> str:
    """Verify debug-process identity and memory bounds around a completed Run."""

    receipt = json.loads(receipt_path.read_text("utf-8"))
    profile_path = project_root / ".codex/agents" / f"{agent_type}.toml"
    profile = tomllib.loads(profile_path.read_text("utf-8"))
    target = profile.get("mcp_servers", {}).get(expected_target_server)
    projection = receipt.get("launch_projection") if isinstance(receipt, dict) else None
    projected_tools = (
        projection.get("target_worker_tools") if isinstance(projection, dict) else None
    )
    invocation_id = receipt.get("invocation_id") if isinstance(receipt, dict) else None
    started = receipt.get("started_at") if isinstance(receipt, dict) else None
    completed = receipt.get("completed_at") if isinstance(receipt, dict) else None
    valid = (
        isinstance(receipt, dict)
        and set(receipt) == _RECEIPT_FIELDS
        and type(receipt.get("schema_version")) is int
        and receipt.get("schema_version") == 1
        and receipt.get("agent_type") == agent_type
        and receipt.get("target_worker_server") == expected_target_server
        and target is not None
        and receipt.get("profile_sha256") == hashlib.sha256(profile_path.read_bytes()).hexdigest()
        and receipt.get("command_projection_sha256")
        == (projection.get("command_projection_sha256") if isinstance(projection, dict) else None)
        and receipt.get("launch_projection_sha256") == _canonical_digest(projection)
        and isinstance(projection, dict)
        and projection.get("agent_type") == agent_type
        and projection.get("all_non_target_parent_servers_disabled") is True
        and projection.get("target_worker_server") == expected_target_server
        and projection.get("target_worker_config_sha256") == _canonical_digest(target)
        and set(projected_tools or ()) == allowed_worker_tools
        and required_worker_tools.issubset(set(projected_tools or ()))
        and projection.get("web_search") == "disabled"
        and type(receipt.get("exit_code")) is int
        and receipt.get("exit_code") == 0
        and type(receipt.get("aggregate_memory_limit_mib")) is int
        and receipt.get("aggregate_memory_limit_mib") == expected_memory_limit_mib
        and receipt.get("memory_limit_exceeded") is False
        and type(receipt.get("peak_process_tree_rss_kib")) is int
        and 0 <= receipt["peak_process_tree_rss_kib"] <= expected_memory_limit_mib * 1024
        and receipt.get("externally_sandboxed_debug") is expected_external_sandbox_debug
        and isinstance(invocation_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", invocation_id) is not None
        and isinstance(started, str)
        and isinstance(completed, str)
        and _instant(started) <= _instant(run_started_at)
        and _instant(run_completed_at) <= _instant(completed)
    )
    if not valid:
        raise ValueError("launcher receipt does not bind the completed Run")
    return invocation_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--agent-type", required=True)
    parser.add_argument("--model", help="Requested model from the queued Run execution_profile")
    parser.add_argument("--reasoning-effort", help="Requested effort from the same Run snapshot")
    parser.add_argument("--memory-limit-mib", type=int, default=4096)
    parser.add_argument("--externally-sandboxed-debug", action="store_true")
    parser.add_argument("--receipt-name")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.memory_limit_mib <= 8192:
        parser.error("memory limit must be between 1024 and 8192 MiB")
    if args.externally_sandboxed_debug and not _inside_codex_outer_sandbox():
        parser.error("externally-sandboxed debug mode requires a Codex outer sandbox")
    if args.receipt_name is not None and _RECEIPT_NAME.fullmatch(args.receipt_name) is None:
        parser.error("receipt name must be a bounded lowercase identifier")
    if not args.dry_run and args.receipt_name is None:
        parser.error("a launcher receipt is required for a controlled Worker run")
    receipt_path = (
        None
        if args.receipt_name is None
        else args.project_root.resolve().parent
        / "launch-receipts"
        / f"{args.receipt_name}.json"
    )
    if receipt_path is not None and receipt_path.exists():
        parser.error("launcher receipt already exists")
    try:
        command, server, projection = build_launch_plan(
            args.project_root,
            args.agent_type,
            model=args.model, reasoning_effort=args.reasoning_effort,
            externally_sandboxed_debug=args.externally_sandboxed_debug,
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        parser.error(str(error))
    if args.dry_run:
        print(
            json.dumps(
                {
                    "agent_type": args.agent_type,
                    "aggregate_memory_limit_mib": args.memory_limit_mib,
                    "target_worker_server": server,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    source_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth_source = source_home / "auth.json"
    if not auth_source.is_file():
        parser.error("ChatGPT authentication file is unavailable")
    workspace_root = Path(command[command.index("-C") + 1])
    workspace_root.mkdir(parents=True, exist_ok=True)
    invocation_id = uuid.uuid4().hex
    started_at = _now()
    return_code = 1
    peak_rss_kib = 0
    memory_exceeded = False
    try:
        with tempfile.TemporaryDirectory(prefix="scid-codex-worker-") as runtime_home:
            auth_target = Path(runtime_home) / "auth.json"
            shutil.copyfile(auth_source, auth_target)
            auth_target.chmod(0o600)
            return_code, peak_rss_kib, memory_exceeded = _run_process_group(
                command,
                dict(os.environ, CODEX_HOME=runtime_home),
                aggregate_memory_limit_mib=args.memory_limit_mib,
            )
    finally:
        if receipt_path is not None:
            _write_exclusive(
                receipt_path,
                {
                    "agent_type": args.agent_type,
                    "aggregate_memory_limit_mib": args.memory_limit_mib,
                    "command_projection_sha256": _canonical_digest(command),
                    "completed_at": _now(),
                    "exit_code": return_code,
                    "externally_sandboxed_debug": args.externally_sandboxed_debug,
                    "invocation_id": invocation_id,
                    "launch_projection": projection,
                    "launch_projection_sha256": _canonical_digest(projection),
                    "memory_limit_exceeded": memory_exceeded,
                    "peak_process_tree_rss_kib": peak_rss_kib,
                    "profile_sha256": projection["profile_sha256"],
                    "schema_version": 1,
                    "started_at": started_at,
                    "target_worker_server": server,
                },
            )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
