import pytest

from scidiscovery.platforms import initialize_platform, PlatformConflictError
from scidiscovery.platforms import scheduler_prompt


def test_missing_packaged_guide_fails_before_profile_generation(tmp_path, monkeypatch):
    role = tmp_path / "roles/scheduler.md"
    role.parent.mkdir()
    role.write_text(scheduler_prompt.load_scheduler_prompt())
    monkeypatch.setattr(scheduler_prompt, "_scheduler_prompt_path", lambda: role)
    with pytest.raises(FileNotFoundError):
        scheduler_prompt.load_scheduler_guides()


def test_guide_installation_is_dry_run_safe_and_idempotent(tmp_path):
    project = tmp_path / "project"
    guide = project / ".codex/scidiscovery-guides/dispatch.md"
    kwargs = dict(control_socket=tmp_path / "control.sock")
    preview = initialize_platform("codex", project, dry_run=True, **kwargs)
    assert guide in preview.changed
    assert not project.exists()
    initialize_platform("codex", project, **kwargs)
    prompt = project / "AGENTS.md"
    original = prompt.read_text()
    for name, content in scheduler_prompt.load_scheduler_guides().items():
        assert (project / ".codex/scidiscovery-guides" / name).read_text() == content
    assert not initialize_platform("codex", project, **kwargs).changed
    guide.write_text("User-owned instructions\n")
    with pytest.raises(PlatformConflictError, match="user-owned file"):
        initialize_platform("codex", project, **kwargs)
    assert prompt.read_text() == original
