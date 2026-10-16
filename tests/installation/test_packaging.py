"""One opt-in cohort: package metadata, supported entry points and shipped resources.

This does not run scientific tasks or compare source and installed catalogs.
Other historical plugin combinations have no installation acceptance in this lane.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.installed


def test_selected_cohort_packaging(installed_probe, pytestconfig):
    cohort = pytestconfig.getoption("installation_cohort")
    installed_probe("cohort = " + repr(cohort) + r'''
from importlib import import_module, resources
from importlib.metadata import PackageNotFoundError, distribution, entry_points
from pathlib import Path
import subprocess
import sys

import scidiscovery
from PIL import Image
import jsonschema
import pydantic
import cryptography

prefix = Path(sys.prefix).resolve()
assert "include-system-site-packages = false" in (prefix / "pyvenv.cfg").read_text()
for module in (scidiscovery, Image, jsonschema, pydantic, cryptography):
    assert Path(module.__file__).resolve().is_relative_to(prefix), module.__file__
package = distribution("scidiscovery")
assert package.version
for script, target in {
    "scid": "scidiscovery.artifact_agent.interfaces.cli:main",
    "scid-research": "scidiscovery.research_loop.cli:main",
    "scid-experiment": "scidiscovery.research_loop.experiments:main",
}.items():
    matches = [item for item in package.entry_points if item.group == "console_scripts" and item.name == script]
    assert len(matches) == 1, matches
    entry = matches[0]
    assert entry.value == target and callable(entry.load())
    result = subprocess.run([str(prefix / "bin" / script), "--help"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and "usage:" in result.stdout, result.stderr
execution = entry_points().select(group="scidiscovery.execution_interfaces")
assert sorted(entry.name for entry in execution) == ["cov_execution", "local_execution"]
for entry in execution:
    assert entry.load() is not None
plugin_names = {"builtin", "general_science"}
if cohort == "tcad":
    plugin_names |= {"curve_score", "tcad_artifact"}
plugins = entry_points().select(group="scidiscovery.plugins")
assert sorted(entry.name for entry in plugins) == sorted(plugin_names)
for entry in plugins:
    assert entry.load() is not None

root = resources.files("scidiscovery")
assert root.joinpath("default_agent_settings.json").read_bytes()
assert any(item.name.endswith(".sql") for item in resources.files("scidiscovery.artifact_agent.storage").joinpath("migrations").iterdir())
for name in ("style.css", "app.js"):
    assert resources.files("scidiscovery.artifact_agent.approval_ui").joinpath("static", name).read_bytes()
from scidiscovery.platforms.scheduler_prompt import load_common_prompt, load_scheduler_guides, load_scheduler_prompt
assert load_common_prompt() and load_scheduler_prompt()
assert load_scheduler_guides()
assert tuple((prefix / "share/scidiscovery/deploy/systemd").glob("*.in"))

if cohort == "core":
    for name in ("tcad-artifact", "scidiscovery-curve-score", "scidiscovery-curve-figure-evidence"):
        try:
            distribution(name)
        except PackageNotFoundError:
            pass
        else:
            raise AssertionError(f"core unexpectedly included {name}")
    for module in ("scidiscovery.artifact_agent.service.agent_dispatch", "scidiscovery.platforms.codex_worker",
                   "scidiscovery.artifact_agent.schema.device_parameters", "architecture_operation_test_plugin"):
        try:
            import_module(module)
        except ModuleNotFoundError:
            pass
        else:
            raise AssertionError(f"core unexpectedly exposed {module}")
else:
    # One pip install of core + TCAD resolves curve from the same wheelhouse;
    # all_domains --no-deps was never equivalent evidence for this requirement.
    tcad = distribution("tcad-artifact")
    assert distribution("scidiscovery-curve-score").version
    scripts = [entry for entry in tcad.entry_points if entry.group == "console_scripts"]
    assert sorted(entry.name for entry in scripts) == ["scidiscovery-tcad-transport", "tcad-control-daemon", "tcad-control-mcp"]
    for entry in scripts:
        assert callable(entry.load())
        result = subprocess.run([str(prefix / "bin" / entry.name), "--help"],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and "usage:" in result.stdout, result.stderr
    assert any(requirement.startswith("scidiscovery-curve-score") for requirement in tcad.requires or ())
    assert resources.files("tcad_artifact").joinpath("roles/parameter_evidence_extractor.md").read_bytes()
    assert tuple((prefix / "share/tcad-artifact/systemd").glob("*.in"))
    assert tuple((prefix / "share/tcad-artifact/config").glob("*.json"))
''')
