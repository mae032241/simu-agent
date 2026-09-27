from __future__ import annotations

import sys
import tomllib
from importlib.util import find_spec
from pathlib import Path

import pytest

from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_SCORE_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_SCIENCE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_gateway import GATEWAY_TOOLS
from scidiscovery.artifact_agent.interfaces.cli import build_parser
from scidiscovery.artifact_agent.service.hardened_workspace import (
    HardenedWorkerBackend,
)
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.operations.catalog import compile_catalog, compile_installed_catalog
from scidiscovery.operations.tooling import (
    operation_agent_type,
    operation_local_worker_tool_names,
    operation_worker_tool_names,
)
from scidiscovery.platforms import PlatformConflictError, initialize_platform
from scidiscovery.platforms.codex import _operation_toml, validate_installation_profile
from scidiscovery.platforms.scheduler_prompt import load_scheduler_guides


def test_control_daemon_passes_backend_choice_to_the_only_root_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scidiscovery.artifact_agent.interfaces import mcp_daemon

    captured: dict[str, object] = {}

    def fake_build_root_router(**values: object) -> object:
        captured.update(values)
        return object()

    class FakeDaemon:
        def __init__(self, _socket, router, **_values):
            self.router = router

        def serve_forever(self) -> None:
            self.router._router("sch_" + "0" * 32)

    monkeypatch.setattr(mcp_daemon, "build_root_router", fake_build_root_router)
    monkeypatch.setattr(mcp_daemon, "UnixSocketDaemon", FakeDaemon)
    monkeypatch.setattr(
        mcp_daemon,
        "compile_installed_catalog",
        lambda: compile_catalog((CORE_PLUGIN, GENERAL_SCIENCE_PLUGIN)),
    )
    secret = tmp_path / "approval.key"
    secret.write_bytes(b"x" * 32)
    runtime = tmp_path / "run"
    runtime.mkdir()
    local_workspace_root = tmp_path / "worker-workspaces"

    assert mcp_daemon.main(
        [
            "--project-root", str(tmp_path),
            "--state-root", str(tmp_path / "state"),
            "--socket", str(tmp_path / "control.sock"),
            "--approval-secret-file", str(secret),
            "--worker-backend", "local",
            "--local-workspace-root", str(local_workspace_root),
            "--runtime-summary", str(runtime / "summary.json"),
        ]
    ) == 0
    assert captured["worker_backend"] == "local"
    assert captured["unified"] is True
    assert captured["local_workspace_root"] == local_workspace_root


def test_approval_ui_cli_accepts_the_deployed_worker_backend() -> None:
    args = build_parser().parse_args(
        ["serve-approval-ui", "--worker-backend", "hardened"]
    )
    assert args.worker_backend == "hardened"


def test_hardened_runtime_does_not_create_a_local_run_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="hardened",
    )
    assert not (project / ".scidiscovery-runs").exists()


def test_legacy_role_discovery_module_is_absent() -> None:
    assert find_spec("scidiscovery.platforms.roles") is None


def test_codex_profile_rejects_config_for_a_plugin_outside_the_catalog(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(Exception, match="not present in the compiled catalog"):
        initialize_platform(
            "codex",
            project,
            control_socket=tmp_path / "control.sock",
            runtime_plugin_configs={"not_installed": tmp_path / "unused.json"},
        )


def test_codex_profile_contains_root_and_compiled_operation_boundaries(
    tmp_path: Path,
) -> None:
    assert LocalTrustedBackend.backend_version == "2"
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
    config_root = project / ".codex"
    local_workspace_root = project / ".scidiscovery-runs"

    initialize_platform(
        "codex",
        project,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        codex_config_root=config_root,
        local_workspace_root=local_workspace_root,
    )
    config = tomllib.loads(
        (config_root / "config.toml").read_text(encoding="utf-8")
    )
    catalog = compile_installed_catalog()
    operations = tuple(
        catalog.operation(operation_id)
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
        and LocalTrustedBackend.supports_operation(
            catalog.operation(operation_id)
        )
    )
    worker_server_names = set(config["mcp_servers"]) - {"scidiscovery"}
    assert worker_server_names == set()
    assert config["mcp_servers"]["scidiscovery"]["args"] == [
        "-m",
        "scidiscovery.artifact_agent.interfaces.mcp_proxy",
        "--socket",
        str(tmp_path / "control.sock"),
    ]
    assert config["mcp_servers"]["scidiscovery"]["env"] == {
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
        "SCIDISCOVERY_PRINCIPAL": "service",
    }
    assert config["mcp_servers"]["scidiscovery"]["enabled_tools"] == list(GATEWAY_TOOLS)
    all_roles = sorted((config_root / "agents").glob("*.toml"))
    operation_roles = tuple(path for path in all_roles if path.stem.startswith("op_"))
    assert {path.stem for path in operation_roles} == {
        operation_agent_type(compiled) for compiled in operations
    }
    assert operation_roles == tuple(all_roles)
    for compiled in operations:
        agent_type = operation_agent_type(compiled)
        role = tomllib.loads(
            (config_root / "agents" / f"{agent_type}.toml").read_text(
                encoding="utf-8"
            )
        )
        assert "model" not in role and "model_reasoning_effort" not in role
        assert role["web_search"] == compiled.spec.executor.native_tools.web_search
        assert "default_permissions" not in role
        assert "permissions" not in role
        assert role["features"]["shell_tool"] is (compiled.spec.executor.native_tools.shell != "none")
        assert role["features"]["unified_exec"] is (compiled.spec.executor.native_tools.shell != "none")
        assert role["tools"]["view_image"] is compiled.spec.executor.native_tools.view_image
        assert not role.get("mcp_servers")
        assert "scid_call" in role["developer_instructions"]
        assert "tools/read_input.py" in role["developer_instructions"]
        assert "role_instructions_sha256" not in role["developer_instructions"]
        assert "--repeat" in role["developer_instructions"]
        assert "workspace/.read-input" in role["developer_instructions"]
        assert "task and input changes" in role["developer_instructions"]
        assert "Project scheduler instructions apply to the parent, not you" in role[
            "developer_instructions"
        ]
        assert "trusted-local prompt boundary" in role["developer_instructions"]
        instructions = role["developer_instructions"]
        assert "exact Codex-discovered Skills relevant to this subtask" in instructions
        assert "Keep Skills read-only" in instructions
        assert "Set TMPDIR and XDG_CACHE_HOME" in instructions
        assert "workspace/scratch" in instructions
        assert "PYTHONDONTWRITEBYTECODE=1" in instructions
        assert "on each script call" in instructions
        assert "they grant no extra inputs or permissions" in instructions
        assert "sole filesystem root" not in instructions
        assert "skills" not in role
        assert "the only permitted chat" in role["developer_instructions"]
        assert "已完成受控提交。" in role["developer_instructions"]
    scheduler_prompt = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "normal work requires no guide files" in scheduler_prompt
    assert 'surface="execution"' in scheduler_prompt
    assert "{{SCHEDULER_GUIDE_ROOT}}" not in scheduler_prompt
    guide_root = config_root / "scidiscovery-guides"
    for name, content in load_scheduler_guides().items():
        assert (guide_root / name).read_text() == content
        assert content.strip() not in scheduler_prompt


def test_codex_hardened_profile_remains_explicitly_compilable(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
    catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_SCIENCE_PLUGIN, BLIND_CSV_PLUGIN)
    )
    for compiled in (
        catalog.operation(operation_id)
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
        and HardenedWorkerBackend.supports_operation(
            catalog.operation(operation_id)
        )
    ):
        profile = tomllib.loads(
            _operation_toml(
                compiled,
                    python=Path(sys.executable),
                    python_path=Path(__file__).resolve().parents[2] / "src",
                    state_root=tmp_path / "state",
                    worker_backend="hardened",
            )
        )
        assert not profile.get("mcp_servers")
        assert "scid_call" in profile["developer_instructions"]
        assert "skills, apps or plugins" in profile["developer_instructions"]
        assert "Set TMPDIR and XDG_CACHE_HOME" not in profile["developer_instructions"]
    report = initialize_platform(
        "codex",
        project,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        worker_backend="hardened",
        codex_config_root=project / ".codex",
        operation_catalog=catalog,
    )
    assert report.changed
    assert validate_installation_profile(
        project,
        workspace=project / "workspace",
        python_path=Path(__file__).resolve().parents[2] / "src",
        worker_backend="hardened",
        operation_catalog=catalog,
    )[1] > 0
    with pytest.raises(PlatformConflictError):
        validate_installation_profile(
            project,
            workspace=project / "workspace",
            python_path=Path(__file__).resolve().parents[2] / "src",
            worker_backend="local",
            operation_catalog=catalog,
        )


def test_codex_installation_profile_probe_uses_the_compiled_catalog(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
    module_path = Path(__file__).resolve().parents[2] / "src"
    initialize_platform(
        "codex",
        project,
        python_executable=Path(sys.executable),
        python_path=module_path,
        control_socket=tmp_path / "control.sock",
        codex_config_root=project / ".codex",
    )

    catalog = compile_installed_catalog()
    operation_count = len({operation_agent_type(catalog.operation(operation_id))
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
        and LocalTrustedBackend.supports_operation(catalog.operation(operation_id))})
    assert validate_installation_profile(
        project, workspace=project / "workspace", python_path=module_path
    ) == (1, operation_count)
    (project / ".codex/scidiscovery-guides/dispatch.md").unlink()
    with pytest.raises(PlatformConflictError, match="scheduler guide is missing or stale"):
        validate_installation_profile(
            project, workspace=project / "workspace", python_path=module_path
        )


def test_codex_framework_profile_is_available_above_nested_workspace(
    tmp_path: Path,
) -> None:
    framework = tmp_path / "scidiscovery-agent"
    workspace = framework / "workspace" / "paper-task"
    workspace.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text(
        "# Paper task\n\nProject-specific scientific constraints.\n",
        encoding="utf-8",
    )

    initialize_platform(
        "codex",
        framework,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        codex_config_root=framework / ".codex",
    )

    assert (framework / ".codex/config.toml").is_file()
    catalog = compile_installed_catalog()
    operation_count = len({operation_agent_type(catalog.operation(operation_id))
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
        and LocalTrustedBackend.supports_operation(catalog.operation(operation_id))})
    assert len(tuple((framework / ".codex/agents").glob("*.toml"))) == operation_count
    assert "<!-- BEGIN SCIDISCOVERY SCHEDULER -->" in (
        framework / "AGENTS.md"
    ).read_text(encoding="utf-8")
    assert not (workspace / ".codex").exists()
    assert "Project-specific scientific constraints." in (
        workspace / "AGENTS.md"
    ).read_text(encoding="utf-8")

def test_external_workspace_validation_rejects_unified_socket_drift(
    tmp_path: Path,
) -> None:
    framework = tmp_path / "framework"
    workspace = tmp_path / "workspace"
    framework.mkdir()
    workspace.mkdir()
    local_workspace_root = workspace / ".scidiscovery-runs"
    common = {
        "python_executable": Path(sys.executable),
        "control_socket": tmp_path / "control.sock",
        "state_root": tmp_path / "state",
        "local_workspace_root": local_workspace_root,
    }
    initialize_platform("codex", framework, **common)
    initialize_platform("codex", workspace, **common)
    validate_installation_profile(
        framework,
        workspace=workspace,
        python_path=Path(__file__).resolve().parents[2] / "src",
        state_root=tmp_path / "state",
        local_workspace_root=local_workspace_root,
    )
    external_config = workspace / ".codex/config.toml"
    external_config.write_text(
        external_config.read_text(encoding="utf-8").replace(
            str(tmp_path / "control.sock"), str(tmp_path / "wrong-control.sock")
        ),
        encoding="utf-8",
    )
    with pytest.raises(PlatformConflictError, match="external workspace"):
        validate_installation_profile(
            framework,
            workspace=workspace,
            python_path=Path(__file__).resolve().parents[2] / "src",
            state_root=tmp_path / "state",
            local_workspace_root=local_workspace_root,
        )


def test_platform_initializers_remove_only_retired_managed_roles(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
    codex_agents = project / ".codex" / "agents"
    codex_agents.mkdir(parents=True)
    retired_codex = codex_agents / "tcad_deck_reviser.toml"
    retired_codex.write_text(
        "# Generated by SciDiscovery. Re-run `scid init codex` to update.\n",
        encoding="utf-8",
    )
    custom_codex = codex_agents / "local_helper.toml"
    custom_codex.write_text("name = \"local_helper\"\n", encoding="utf-8")

    preview = initialize_platform(
        "codex",
        project,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        codex_config_root=project / ".codex",
        dry_run=True,
    )
    assert retired_codex in preview.changed
    assert retired_codex.exists()
    initialize_platform(
        "codex",
        project,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        codex_config_root=project / ".codex",
    )
    assert not retired_codex.exists()
    assert custom_codex.read_text(encoding="utf-8") == 'name = "local_helper"\n'

def test_platform_initializer_rejects_non_codex_platforms(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for platform in ("claude", "both"):
        with pytest.raises(ValueError, match="unsupported platform"):
            initialize_platform(
                platform,
                project,
                python_executable=Path(sys.executable),
                control_socket=tmp_path / "control.sock",
            )
