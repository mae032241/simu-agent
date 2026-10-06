"""Instruction installation and entry seams; no model or production services."""
import json
from pathlib import Path
import stat
import sys
import tomllib

import pytest

from scidiscovery.platforms import initialize_platform, PlatformConflictError
from scidiscovery.platforms import codex, common
from scidiscovery.platforms.scheduler_prompt import load_common_prompt, load_scheduler_prompt


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


def install(project, **kwargs):
    return initialize_platform("codex", project, control_socket=project.parent / "control.sock", **kwargs)


def snapshot(project):
    return {str(p.relative_to(project)): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
            for p in project.rglob("*") if p.is_file()}


def test_legacy_upgrade_preserves_user_bytes_and_top_level_config(tmp_path):
    project = tmp_path / "project"
    (project / ".codex").mkdir(parents=True)
    prefix, suffix = b"User before  \r\n\r\n", b"\r\n\r\nUser after\t\r\n"
    agents = project / "AGENTS.md"
    agents.write_bytes(prefix + codex.PROMPT_BEGIN.encode() + b"\nOld scheduler\n" + codex.PROMPT_END.encode() + suffix)
    agents.chmod(0o640)
    config = project / ".codex/config.toml"
    user_config = b"# User config  \r\n[tui]\nshow_tooltips = false\n"
    config.write_bytes(user_config)
    install(project)
    text = agents.read_bytes()
    assert text.startswith(prefix) and text.endswith(suffix)
    assert stat.S_IMODE(agents.stat().st_mode) == 0o640
    assert codex.PROMPT_BEGIN.encode() not in text
    assert load_common_prompt().strip().encode() in text
    assert b"interactive research scheduler" not in text
    parsed = tomllib.loads(config.read_text())
    assert parsed["developer_instructions"] == load_scheduler_prompt().replace("{{SCHEDULER_GUIDE_ROOT}}", str(project / ".codex/scidiscovery-guides"))
    assert user_config in config.read_bytes()
    assert config.read_text().startswith(codex.ROOT_BEGIN)
    before = snapshot(project)
    assert not install(project).changed
    assert snapshot(project) == before


def test_quotes_and_multiline_root_template_round_trip(tmp_path, monkeypatch):
    prompt = 'Root only. "quoted" \\path\nNext line 中文\n'
    monkeypatch.setattr(codex, "load_scheduler_prompt", lambda: prompt)
    project = tmp_path / "project"
    install(project)
    assert tomllib.loads((project / ".codex/config.toml").read_text())["developer_instructions"] == prompt
    assert not install(project).changed


@pytest.mark.parametrize("location", ["project", "global", "ancestor", "profile"])
def test_user_developer_scope_conflict_preserves_every_file(tmp_path, isolated_home, location):
    project = tmp_path / "parent/project"
    (project / ".codex").mkdir(parents=True)
    if location == "project":
        path = project / ".codex/config.toml"
    elif location == "ancestor":
        path = project.parent / ".codex/config.toml"
        path.parent.mkdir()
    else:
        path = isolated_home / "config.toml"
    source = ('[profiles.custom]\n' if location == "profile" else '') + 'developer_instructions = "User scope is not known"\n'
    path.write_text(source)
    (project / "AGENTS.md").write_text("User scientific preferences\n")
    before = snapshot(project)
    with pytest.raises(PlatformConflictError, match="scope cannot be inferred"):
        install(project)
    assert snapshot(project) == before and path.read_text() == source


@pytest.mark.parametrize("bad", [
    codex.PROMPT_BEGIN + "\n",
    codex.PROMPT_END + codex.PROMPT_BEGIN,
    codex.PROMPT_BEGIN + codex.PROMPT_END + codex.COMMON_BEGIN + codex.COMMON_END,
])
def test_ambiguous_or_broken_project_blocks_fail_before_writes(tmp_path, bad):
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text(bad)
    before = snapshot(project)
    with pytest.raises(PlatformConflictError, match="managed.*(block|markers)"):
        install(project)
    assert snapshot(project) == before


def test_failure_after_config_write_restores_old_files_and_removes_new_roles(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / ".codex").mkdir(parents=True)
    agents = project / "AGENTS.md"
    agents.write_text(codex.PROMPT_BEGIN + "\nOld scheduler\n" + codex.PROMPT_END + "\nUser after\n")
    agents.chmod(0o600)
    (project / ".codex/config.toml").write_text("# Original user config\n")
    before = snapshot(project)
    original_write = common.atomic_write
    def fail_on_agents(path, content):
        if path == agents:
            raise OSError("injected late installation failure")
        original_write(path, content)
    monkeypatch.setattr(common, "atomic_write", fail_on_agents)
    with pytest.raises(OSError, match="injected late"):
        install(project)
    assert snapshot(project) == before
    assert not list(project.rglob("*.tmp"))


def test_persistent_agents_write_denial_restores_config_and_roles(tmp_path):
    project = tmp_path / "project"
    (project / ".codex").mkdir(parents=True)
    agents = project / "AGENTS.md"
    agents.write_text(codex.PROMPT_BEGIN + "\nOld scheduler\n" + codex.PROMPT_END + "\nUser after\n")
    agents.chmod(0o600)
    (project / ".codex/config.toml").write_text("# Original user config\n")
    before = snapshot(project)
    project.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            install(project)
        assert snapshot(project) == before
        assert not list(project.rglob("*.tmp"))
    finally:
        project.chmod(0o700)


def test_persistent_restore_denials_do_not_stop_other_recovery(tmp_path, monkeypatch):
    paths = []
    for name in ("recoverable", "blocked-one", "blocked-two", "unchanged"):
        directory = tmp_path / name
        directory.mkdir()
        path = directory / "managed.txt"
        path.write_text("old\n")
        path.chmod(0o640)
        paths.append(path)
    recoverable, *blocked, unchanged = paths
    original_write = common.atomic_write

    def write_then_deny_recovery(path, content):
        original_write(path, content)
        if path in blocked:
            path.parent.chmod(0o500)

    monkeypatch.setattr(common, "atomic_write", write_then_deny_recovery)
    unchanged.parent.chmod(0o500)
    try:
        with pytest.raises(RuntimeError) as raised:
            common.commit_text_files(
                platform="codex", project_root=tmp_path,
                desired={path: "new\n" for path in paths},
                exclusive=frozenset(), dry_run=False,
            )
        error = raised.value
        assert isinstance(error.original_error, PermissionError)
        assert error.__cause__ is error.original_error
        assert {path for path, _, _ in error.rollback_errors} == set(blocked)
        assert all(isinstance(failure, PermissionError) for _, _, failure in error.rollback_errors)
        assert str(error.original_error) in str(error)
        assert all(str(path) in str(error) for path in blocked)
        assert recoverable.read_text() == unchanged.read_text() == "old\n"
        assert all(path.read_text() == "new\n" for path in blocked)
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o640 for path in paths)
        assert not list(tmp_path.rglob("*.tmp"))
    finally:
        for path in paths:
            path.parent.chmod(0o700)


def test_installed_profile_rejects_missing_root_even_when_common_and_roles_exist(tmp_path):
    project = tmp_path / "project"
    install(project)
    kwargs = dict(workspace=project / "workspace", python_path=Path(__file__).resolve().parents[2] / "src")
    codex.validate_installation_profile(project, **kwargs)
    config = project / ".codex/config.toml"
    config.write_text(codex._without_block(config.read_text(), codex.ROOT_BEGIN, codex.ROOT_END))
    with pytest.raises(PlatformConflictError, match="Root developer"):
        codex.validate_installation_profile(project, **kwargs)


def test_third_party_capabilities_keep_worker_developer_and_explicit_dispatch(tmp_path):
    from blind_csv_plugin.plugin import PLUGIN as THIRD_PARTY
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.tooling import operation_agent_type
    catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, THIRD_PARTY))
    project = tmp_path / "project"
    install(project, operation_catalog=catalog)
    for operation_id in ("blind.csv.observe.v1", "blind.csv.review.v1"):
        compiled = catalog.operation(operation_id)
        role = tomllib.loads((project / ".codex/agents" / (operation_agent_type(compiled) + ".toml")).read_text())
        assert "Start with worker_open_assignment" in role["developer_instructions"]
        assert "interactive research scheduler" not in role["developer_instructions"]
        assert role["tools"]["view_image"] == compiled.spec.executor.native_tools.view_image
        assert "model" not in role and "model_reasoning_effort" not in role
