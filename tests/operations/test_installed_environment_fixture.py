"""Installed-wheel fixtures should not create unused virtual environments."""

from pathlib import Path

import pytest

from tests.operations import conftest as fixtures


def test_installed_environments_create_only_requested_runtime(tmp_path_factory, monkeypatch):
    created = []
    commands = []

    class FakeBuilder:
        def __init__(self, **_kwargs):
            pass

        def create(self, path):
            created.append(Path(path).name)
            (Path(path) / "bin").mkdir(parents=True)

    def fake_run(command, **_kwargs):
        commands.append(command)
        if "--wheel-dir" in command:
            wheelhouse = Path(command[command.index("--wheel-dir") + 1])
            for name in (
                "scidiscovery-0", "tcad_artifact-0", "scidiscovery_curve_score-0",
                "scidiscovery_curve_figure_evidence-0", "scidiscovery_table_observation-0",
                "scidiscovery_blind_csv_test_plugin-0",
                "scidiscovery_architecture_operation_test_plugin-0",
                "scidiscovery_m7_effect_test_plugin-0",
                "scidiscovery_broken_operation_test_plugin-0",
                "scidiscovery_invalid_unicode_operation_test_plugin-0",
            ):
                (wheelhouse / f"{name}-py3-none-any.whl").touch()

    monkeypatch.setattr(fixtures.venv, "EnvBuilder", FakeBuilder)
    monkeypatch.setattr(fixtures.subprocess, "run", fake_run)
    monkeypatch.setattr(fixtures, "_supply_runtime_dependencies", lambda _root: None)

    environments = fixtures.installed_environments.__wrapped__(tmp_path_factory)
    assert created == []
    assert environments["full"] is environments["full"]
    assert created == ["full"]
    tcad = environments["tcad_resolved"]
    assert created == ["full", "tcad_resolved"]
    tcad_installs = [command for command in commands
                     if command[0] == str(tcad.python) and "install" in command]
    assert len(tcad_installs) == 2
    assert "--no-deps" in tcad_installs[0]
    assert "--find-links" in tcad_installs[1]
    for unused in ("core_no_yaml", "producer_family"):
        with pytest.raises(KeyError):
            environments[unused]
    assert created == ["full", "tcad_resolved"]
