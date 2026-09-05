from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import l3_live_review_probe, l4_live_tcad_agent_probe


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_compiled_codex_worker.py"
SPEC = importlib.util.spec_from_file_location("compiled_worker_launcher", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def _project(tmp_path: Path, *, disagree: bool = False) -> tuple[Path, str, str]:
    project = tmp_path / "project"
    agents = project / ".codex/agents"
    agents.mkdir(parents=True)
    agent_type = "op_fixture_0123456789ab"
    server = "scid_worker_fixture_0123456789ab"
    operation_id = "wrong" if disagree else "fixture.operation.v1"
    state_root = (project.parent / "state").resolve()
    local_workspace_root = (project / ".scidiscovery-runs").resolve()
    parent_args = [
        "-m",
        "scidiscovery.artifact_agent.interfaces.mcp_local_worker",
        "--state-root",
        str(state_root),
        "--local-workspace-root",
        str(local_workspace_root),
        "--operation-id",
        operation_id,
    ]
    profile_args = [*parent_args]
    profile_args[-1] = "fixture.operation.v1"
    (project / ".codex/config.toml").write_text(
        "\n".join(
            (
                "[mcp_servers.scidiscovery]",
                'command = "root-command"',
                'args = ["root"]',
                'enabled_tools = ["instance_current"]',
                "",
                f"[mcp_servers.{server}]",
                'command = "worker-command"',
                f"args = {json.dumps(parent_args)}",
                'enabled_tools = ["worker_open_assignment", "worker_submit_result"]',
                'default_tools_approval_mode = "approve"',
                f'env = {{ SCIDISCOVERY_ROLE = "{agent_type}" }}',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (agents / f"{agent_type}.toml").write_text(
        "\n".join(
            (
                f'name = "{agent_type}"',
                'model = "gpt-5.6-sol"',
                'developer_instructions = "bounded role"',
                'web_search = "disabled"',
                "[features]",
                "shell_tool = true",
                "unified_exec = true",
                "[tools]",
                "view_image = false",
                f"[mcp_servers.{server}]",
                'command = "worker-command"',
                f"args = {json.dumps(profile_args)}",
                'enabled_tools = ["worker_open_assignment", "worker_submit_result"]',
                'default_tools_approval_mode = "approve"',
                f'env = {{ SCIDISCOVERY_ROLE = "{agent_type}" }}',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return project, agent_type, server


def test_launcher_projects_one_worker_without_native_command_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, agent_type, server = _project(tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/usr/bin/codex")

    command, selected = launcher.build_command(project, agent_type)
    rendered = "\n".join(command)

    assert selected == server
    assert command[:6] == [
        "/usr/bin/codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
        "workspace-write",
    ]
    assert str((project / ".scidiscovery-runs/workspaces").resolve()) in command
    assert f"mcp_servers.{server}.enabled=true" in command
    assert f"mcp_servers.{server}.required=true" in command
    assert 'mcp_servers.scidiscovery.command="/bin/false"' in command
    assert "mcp_servers.scidiscovery.enabled=false" in command
    assert "hooks." not in rendered
    assert "audit" not in rendered
    assert "run_id" not in rendered and "artifact_name" not in rendered


def test_external_sandbox_debug_mode_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, agent_type, _ = _project(tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/usr/bin/codex")

    command, _ = launcher.build_command(
        project, agent_type, externally_sandboxed_debug=True
    )

    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert "--sandbox" not in command
    assert "--dangerously-bypass-hook-trust" not in command


def test_launcher_rejects_parent_role_worker_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, agent_type, _ = _project(tmp_path, disagree=True)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/usr/bin/codex")

    with pytest.raises(ValueError, match="disagree on args"):
        launcher.build_command(project, agent_type)


def test_receipt_publication_is_atomic_and_never_overwrites(tmp_path: Path) -> None:
    receipt = tmp_path / "receipts/current.json"
    launcher._write_exclusive(receipt, {"schema_version": 1})

    assert json.loads(receipt.read_text("utf-8")) == {"schema_version": 1}
    with pytest.raises(FileExistsError):
        launcher._write_exclusive(receipt, {"schema_version": 2})


def test_receipt_binds_identity_memory_and_static_worker_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, agent_type, server = _project(tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/usr/bin/codex")
    command, _, projection = launcher.build_launch_plan(
        project, agent_type, externally_sandboxed_debug=True
    )
    receipt_path = tmp_path / "receipts/current.json"
    receipt_path.parent.mkdir()
    receipt = {
        "agent_type": agent_type,
        "aggregate_memory_limit_mib": 4096,
        "command_projection_sha256": launcher._canonical_digest(command),
        "completed_at": "2026-09-02T00:00:03Z",
        "exit_code": 0,
        "externally_sandboxed_debug": True,
        "invocation_id": "1" * 32,
        "launch_projection": projection,
        "launch_projection_sha256": launcher._canonical_digest(projection),
        "memory_limit_exceeded": False,
        "peak_process_tree_rss_kib": 12345,
        "profile_sha256": projection["profile_sha256"],
        "schema_version": 1,
        "started_at": "2026-09-02T00:00:00Z",
        "target_worker_server": server,
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    assert launcher.verify_receipt(
        receipt_path=receipt_path,
        project_root=project,
        agent_type=agent_type,
        expected_target_server=server,
        allowed_worker_tools={"worker_open_assignment", "worker_submit_result"},
        required_worker_tools={"worker_open_assignment", "worker_submit_result"},
        run_started_at="2026-09-02T00:00:01Z",
        run_completed_at="2026-09-02T00:00:02Z",
        expected_memory_limit_mib=4096,
        expected_external_sandbox_debug=True,
    ) == "1" * 32

    receipt["memory_limit_exceeded"] = True
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="does not bind"):
        launcher.verify_receipt(
            receipt_path=receipt_path,
            project_root=project,
            agent_type=agent_type,
            expected_target_server=server,
            allowed_worker_tools={"worker_open_assignment", "worker_submit_result"},
            required_worker_tools={"worker_open_assignment", "worker_submit_result"},
            run_started_at="2026-09-02T00:00:01Z",
            run_completed_at="2026-09-02T00:00:02Z",
            expected_memory_limit_mib=4096,
            expected_external_sandbox_debug=True,
        )


def test_process_tree_memory_budget_stops_a_large_grandchild() -> None:
    child = "import time; payload = bytearray(48 * 1024 * 1024); time.sleep(30)"
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "time.sleep(30)"
    )

    exit_code, peak_rss_kib, exceeded = launcher._run_process_group(
        [sys.executable, "-c", parent],
        dict(os.environ),
        aggregate_memory_limit_mib=32,
        sample_interval_seconds=0.02,
    )

    assert exit_code == 86
    assert exceeded is True
    assert peak_rss_kib > 32 * 1024


def test_process_group_cleans_an_observed_detached_child(tmp_path: Path) -> None:
    pid_path = tmp_path / "detached.pid"
    child = "import time; time.sleep(30)"
    parent = (
        "import pathlib, subprocess, sys, time; "
        f"child = subprocess.Popen([sys.executable, '-c', {child!r}], start_new_session=True); "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid)); "
        "time.sleep(0.3)"
    )

    exit_code, _, exceeded = launcher._run_process_group(
        [sys.executable, "-c", parent],
        dict(os.environ),
        aggregate_memory_limit_mib=128,
        sample_interval_seconds=0.02,
    )

    assert exit_code == 0
    assert exceeded is False
    status = Path(f"/proc/{int(pid_path.read_text('utf-8'))}/status")
    if status.exists():
        state = next(
            line for line in status.read_text("utf-8").splitlines() if line.startswith("State:")
        )
        assert "Z" in state


def test_cli_writes_a_memory_receipt_without_native_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, agent_type, _ = _project(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_codex = fake_bin / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text("{}\n", encoding="utf-8")
    environment = dict(
        os.environ,
        CODEX_HOME=str(codex_home),
        PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(project),
            "--agent-type",
            agent_type,
            "--memory-limit-mib",
            "1024",
            "--receipt-name",
            "fixture",
        ],
        env=environment,
        check=False,
    )

    assert completed.returncode == 0
    receipt = json.loads(
        (tmp_path / "launch-receipts/fixture.json").read_text("utf-8")
    )
    assert receipt["aggregate_memory_limit_mib"] == 1024
    assert receipt["memory_limit_exceeded"] is False
    assert "native_workspace_audit" not in receipt
    assert "worker_tool_calls" not in receipt


def test_fresh_live_probes_freeze_four_gibibyte_serial_dispatch(tmp_path: Path) -> None:
    l3_root = tmp_path / "l3"
    l3_live_review_probe.prepare(l3_root)
    l3 = json.loads((l3_root / "author-dispatch.json").read_text("utf-8"))
    assert l3["launcher_command"][l3["launcher_command"].index("--memory-limit-mib") + 1] == "4096"

    l4_root = tmp_path / "l4"
    l4_live_tcad_agent_probe.prepare(l4_root)
    l4 = json.loads((l4_root / "author-dispatch.json").read_text("utf-8"))
    assert l4["launcher_command"][l4["launcher_command"].index("--memory-limit-mib") + 1] == "4096"
    assert l4["required_worker_calls"] == [
        "worker_open_assignment",
        "worker_tcad_debug_run",
        "worker_submit_result",
    ]
