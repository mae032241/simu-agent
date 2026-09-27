"""One offline wheel environment; bounded regression, no solver or test matrix."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

repository = Path.cwd()
evidence = Path(__file__).parent
root = Path(tempfile.mkdtemp(prefix="scid-registration-installed-"))
sys.path.insert(0, str(repository))
from tests.operations.conftest import _supply_runtime_dependencies, _copy_runtime_distribution


def run(command, **kwargs):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=65, **kwargs)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}:\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}")
    return result.stdout


release = root / "source"
run([sys.executable, str(repository / "scripts/build_git_release.py"), "--source", str(repository), "--output", str(release)])
wheelhouse = root / "wheels"
wheelhouse.mkdir()
for source in (release, release / "plugins/tcad_artifact", release / "plugins/curve_score",
               release / "plugins/curve_figure_evidence"):
    run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheelhouse), str(source)])
environment = root / "venv"
venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
_supply_runtime_dependencies(environment)
site = environment / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
for package in ("pytest", "pluggy", "iniconfig", "packaging", "pygments"):
    _copy_runtime_distribution(package, site)
python = str(environment / "bin/python")
run([python, "-m", "pip", "install", "--no-index", "--no-deps", *map(str, wheelhouse.glob("*.whl"))])
clean = {**os.environ, "PYTHONNOUSERSITE": "1"}
clean.pop("PYTHONPATH", None)
clean.pop("SCIDISCOVERY_ROLE_DIR", None)
probe = r'''
import sys, tempfile
from pathlib import Path
import scidiscovery, tcad_artifact, curve_score
for module in (scidiscovery, tcad_artifact, curve_score):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix))
assert 'include-system-site-packages = false' in (Path(sys.prefix)/'pyvenv.cfg').read_text()
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.interfaces.mcp_root import root_tools_for_backend
catalog = compile_installed_catalog()
assert catalog.operation('science.experiment.design.v1')
tools = {tool.name: tool.schema()['inputSchema'] for tool in root_tools_for_backend('local')}
assert tools['run_status']['properties']['diagnostic_limit']['maximum'] == 100
assert 'before' in tools['run_list']['properties']
sys.path.append(REPOSITORY)
from tests.operations import test_registration_diagnostics_repair as repair
import pytest
for derive in (False, True):
    with tempfile.TemporaryDirectory() as directory:
        repair.test_prose_and_baseline_labels_survive_submit_materialize_and_review(
            Path(directory), repair.experiment_case.__wrapped__(), derive)
with tempfile.TemporaryDirectory() as directory:
    repair.test_materialized_variable_keeps_editable_intent_location(
        Path(directory), repair.experiment_case.__wrapped__())
for failure in ('workspace', 'workspace_restart', 'evidence', 'expired'):
    with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as patch:
        repair.test_failed_reuse_open_belongs_to_selected_run(Path(directory), patch, failure)
for test in (
    repair.test_expired_and_terminal_calls_keep_diagnostics_without_changing_state,
    repair.test_agent_reuse_keeps_entire_open_call_on_new_run,
    repair.test_mcp_pages_all_saved_errors_and_runs_with_instance_isolation,
    repair.test_publication_source_failure_names_exact_argument_and_is_recoverable,
):
    with tempfile.TemporaryDirectory() as directory:
        test(Path(directory))
print('installed catalog, schemas, design/review, late errors, reuse, history, source correction: pass')
'''.replace("REPOSITORY", repr(str(repository)))
print(run([python, "-c", probe], env=clean).strip())
(evidence / "installed-smoke.json").write_text(json.dumps({"status": "pass", "root": str(root),
    "wheels": [path.name for path in wheelhouse.glob("*.whl")],
    "boundary": "wheel imports and MCP router; no live Agent, daemon, VM or solver"}, indent=2) + "\n")
