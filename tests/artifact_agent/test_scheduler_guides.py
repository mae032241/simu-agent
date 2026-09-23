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
    assert 'scid_describe(name=..., view="invoke")' in original
    results = project / ".codex/scidiscovery-guides/results.md"
    inputs = project / ".codex/scidiscovery-guides/inputs.md"
    domain = project / ".codex/scidiscovery-guides/domain-analysis.md"
    for profile in ("poll", "navigation", "decision"):
        assert f'response_profile="{profile}"' in results.read_text()
    assert 'artifact_catalog(view="producer_inputs")' in inputs.read_text()
    assert "parents_fallback" in inputs.read_text()
    assert "never print raw `parents`" in original
    assert "Never print raw `parents`" in inputs.read_text()
    assert "same-Run tool evidence are complementary" in inputs.read_text()
    assert "assignment source_name" in inputs.read_text()
    assert "transport `isError`" in results.read_text()
    research = project / ".codex/scidiscovery-guides/research.md"
    assert "plot-only" in research.read_text()
    assert "which possible result" in research.read_text()
    assert "Keep three things separate" in results.read_text()
    assert "never commands or catalog" in results.read_text()
    assert 'artifact_catalog(view="producer_inputs")' in domain.read_text()
    assert not initialize_platform("codex", project, **kwargs).changed
    guide.write_text("User-owned instructions\n")
    with pytest.raises(PlatformConflictError, match="user-owned file"):
        initialize_platform("codex", project, **kwargs)
    assert prompt.read_text() == original
