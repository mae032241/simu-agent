from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
from scidiscovery.platforms import initialize_platform
from scidiscovery.platforms.roles import DOMAIN_ROLE_PATHS, load_roles


def test_source_domain_roles_take_precedence_over_installed_entry_points() -> None:
    repository = Path(__file__).resolve().parents[2]
    assert len(load_roles()) == 8
    assert set(DOMAIN_ROLE_PATHS) == {
        "tcad_deck_author",
        "tcad_deck_reviewer",
    }
    assert all(path.is_relative_to(repository / "plugins") for path in DOMAIN_ROLE_PATHS.values())


def test_codex_profile_contains_only_current_socket_boundaries(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
    config_root = project / ".codex"

    initialize_platform(
        "codex",
        project,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        worker_socket=tmp_path / "worker.sock",
        worker_workspace_root=tmp_path / "state" / "workspaces",
        codex_config_root=config_root,
    )
    config = tomllib.loads(
        (config_root / "config.toml").read_text(encoding="utf-8")
    )
    assert set(config["mcp_servers"]) == {"scidiscovery"}
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
    assert config["mcp_servers"]["scidiscovery"]["enabled_tools"] == [
        tool.name for tool in ROOT_TOOLS
    ]
    roles = sorted((config_root / "agents").glob("*.toml"))
    assert len(roles) == 8
    for path in roles:
        role = tomllib.loads(path.read_text(encoding="utf-8"))
        assert role["web_search"] == "live"
        assert role["tools"]["view_image"] is True
        assert role["tools"]["web_search"]["context_size"] == "high"
        permission_name = f"scidiscovery-{path.stem.replace('_', '-')}"
        assert role["default_permissions"] == permission_name
        assert "sandbox_mode" not in role
        profile = role["permissions"][permission_name]
        assert profile["extends"] == ":read-only"
        assert profile["workspace_roots"] == {
            str(tmp_path / "state" / "workspaces"): True
        }
        assert "filesystem" not in profile
        assert set(role["mcp_servers"]) == {"scidiscovery"}
        server = role["mcp_servers"]["scidiscovery"]
        assert server["args"][0:2] == [
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_proxy",
        ]
        assert "--socket" in server["args"]
        assert "--worker-id" in server["args"]
        assert server["env"]["PYTHONNOUSERSITE"] == "1"
        assert server["env"]["PYTHONPATH"] == str(
            Path(__file__).resolve().parents[2] / "src"
        )
        assert {
            "worker_begin_result_upload",
            "worker_append_result_upload",
            "worker_commit_result_upload",
            "worker_get_assignment",
            "worker_list_inputs",
            "worker_read_input",
            "worker_stage_input",
            "worker_read_table",
            "worker_profile_input",
        }.isdisjoint(server["enabled_tools"])
        assert {
            "worker_file_write_begin",
            "worker_file_write_chunk",
            "worker_file_write_commit",
            "worker_file_apply_patch",
            "worker_file_json_patch",
        }.issubset(server["enabled_tools"])
        if path.stem != "tcad_deck_author":
            assert "worker_tcad_debug_run" not in server["enabled_tools"]
        rendered = path.read_text(encoding="utf-8")
        assert "secret" not in rendered.lower()
        assert "state-root" not in rendered
        prompt = role["developer_instructions"].lower()
        for forbidden in (
            "artifact id",
            "dispatch handle",
            "dispatch_handle",
            "hashes",
            "session token",
            "session_token",
            "task ids",
        ):
            assert forbidden not in prompt


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
        worker_socket=tmp_path / "worker.sock",
        codex_config_root=framework / ".codex",
    )

    assert (framework / ".codex/config.toml").is_file()
    assert len(tuple((framework / ".codex/agents").glob("*.toml"))) == 8
    assert "<!-- BEGIN SCIDISCOVERY SCHEDULER -->" in (
        framework / "AGENTS.md"
    ).read_text(encoding="utf-8")
    assert not (workspace / ".codex").exists()
    assert "Project-specific scientific constraints." in (
        workspace / "AGENTS.md"
    ).read_text(encoding="utf-8")


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
        worker_socket=tmp_path / "worker.sock",
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
        worker_socket=tmp_path / "worker.sock",
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
                worker_socket=tmp_path / "worker.sock",
            )
