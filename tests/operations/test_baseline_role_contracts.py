from __future__ import annotations

import tomllib
from pathlib import Path


def test_installed_runtime_has_no_legacy_role_contract_loader(installed_probe) -> None:
    installed_probe(
        "full",
        r'''
from importlib.util import find_spec

assert find_spec("scidiscovery.platforms.roles") is None
assert find_spec("scidiscovery.artifact_agent.service.tasks") is None
''',
    )


def test_only_current_scheduler_role_is_distributed() -> None:
    repository = Path(__file__).resolve().parents[2]
    roles = repository / "roles"
    assert {path.name for path in roles.glob("*.md")} == {"scheduler.md"}
    metadata = tomllib.loads((repository / "pyproject.toml").read_text("utf-8"))
    assert metadata["tool"]["setuptools"]["data-files"][
        "share/scidiscovery/roles"
    ] == ["roles/scheduler.md"]
