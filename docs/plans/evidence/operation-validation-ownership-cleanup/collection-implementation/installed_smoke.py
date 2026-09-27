"""One offline wheel environment for the exact collection change; no test matrix."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import venv

repository = Path.cwd()
root = Path(tempfile.mkdtemp(prefix="scid-collection-installed-"))
evidence = Path(__file__).parent
sys.path.insert(0, str(repository))
from tests.operations.conftest import _supply_runtime_dependencies
from tests.operations.test_baseline_effect_lifecycle import test_installed_no_effect_execution_requires_exact_ui_decision


def run(command, **kwargs):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=65, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed ({result.returncode}):\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}")
    return result.stdout


release = root / "source"
run([sys.executable, str(repository / "scripts/build_git_release.py"), "--source", str(repository), "--output", str(release)])
fixture = root / "architecture"
shutil.copytree(repository / "tests/fixtures/plugins/architecture_operation_plugin", fixture,
    ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"))
wheelhouse = root / "wheels"
wheelhouse.mkdir()
for source in (release, release / "plugins/tcad_artifact", release / "plugins/curve_score", fixture):
    run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheelhouse), str(source)])
environment = root / "venv"
venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
_supply_runtime_dependencies(environment)
python = str(environment / "bin/python")
run([python, "-m", "pip", "install", "--no-index", "--no-deps", *map(str, wheelhouse.glob("*.whl"))])
clean = {**os.environ, "PYTHONNOUSERSITE": "1"}
clean.pop("PYTHONPATH", None)
clean.pop("SCIDISCOVERY_ROLE_DIR", None)
prefix = '''
from pathlib import Path as _Path
import sys as _sys
import scidiscovery as _scid
assert _Path(_scid.__file__).resolve().is_relative_to(_Path(_sys.prefix))
assert "include-system-site-packages = false" in (_Path(_sys.prefix)/"pyvenv.cfg").read_text()
'''


def probe(_name, source):
    return run([python, "-c", textwrap.dedent(prefix + source)], env=clean)


probe("installed", '''
from scidiscovery.artifact_agent.interfaces.mcp_root import root_tools_for_backend
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.service.execution_collection import CollectionContext
from tcad_artifact.command_adapter import CommandAdapterConfig
from tcad_artifact import debug_collection
catalog = compile_installed_catalog()
assert catalog.operation("tcad.deck.author.initial.v1")
tools = {tool.name: tool.schema() for tool in root_tools_for_backend("local")}
assert "execution_collect" in tools and "diagnostic_read" in tools
assert tools["execution_collect"]["inputSchema"]["properties"]["total_seconds"]["default"] == 600
old = CommandAdapterConfig(executable=_sys.executable, operation_timeout_seconds=30)
assert old.query_timeout_seconds == 5
assert CollectionContext.for_seconds(600).file_timeout_seconds == 120
assert CollectionContext.for_seconds(600).idle_timeout_seconds == 30
print("installed catalog, Root schemas, private debug entry and old configuration: pass")
''')
test_installed_no_effect_execution_requires_exact_ui_decision(probe)
print(run([python, str(evidence/'installed_collection_probe.py')], env=clean).strip())
(evidence / "installed-smoke.json").write_text(json.dumps({"status":"pass", "root":str(root),
    "wheels":[path.name for path in wheelhouse.glob("*.whl")],
    "checks":["source-independent imports", "installed catalog and Root schemas", "old configuration defaults",
              "exact UI decision", "real collector process and semantic outputs",
              "installed stdio/proxy/daemon with reopened TCAD command adapter and no checkpoint seed"]}, indent=2)+"\n")
print("installed wheel collection smoke: pass", root)
