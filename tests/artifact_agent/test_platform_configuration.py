from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
from scidiscovery.artifact_agent.interfaces.mcp_worker import WORKER_TOOLS
from scidiscovery.platforms import initialize_platform
from scidiscovery.platforms.roles import DOMAIN_ROLE_PATHS, load_roles


def test_source_domain_roles_take_precedence_over_installed_entry_points() -> None:
    repository = Path(__file__).resolve().parents[2]
    assert len(load_roles()) == 9
    assert set(DOMAIN_ROLE_PATHS) == {
        "tcad_deck_author",
        "tcad_deck_reviewer",
        "tcad_deck_reviser",
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
    assert len(roles) == 9
    for path in roles:
        role = tomllib.loads(path.read_text(encoding="utf-8"))
        assert role["web_search"] == "live"
        assert role["tools"]["view_image"] is True
        assert role["tools"]["web_search"]["context_size"] == "high"
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


def test_claude_roles_use_the_same_identity_free_worker_surface(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")

    initialize_platform(
        "claude",
        project,
        python_executable=Path(sys.executable),
        control_socket=tmp_path / "control.sock",
        worker_socket=tmp_path / "worker.sock",
    )

    role_paths = sorted((project / ".claude" / "agents").glob("*.md"))
    assert len(role_paths) == 9
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in role_paths)
    for tool in WORKER_TOOLS:
        assert f"mcp__scidiscovery__{tool.name}" in rendered
    lowered = rendered.lower()
    for forbidden in (
        "artifact id",
        "dispatch handle",
        "dispatch_handle",
        "hashes",
        "session token",
        "session_token",
        "task ids",
    ):
        assert forbidden not in lowered
