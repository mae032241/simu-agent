import json
import sys
import tempfile
from pathlib import Path
import pytest

root_path = Path(sys.argv[1])
sys.path[:0] = [str(root_path / part) for part in (
    "src", ".", "plugins/tcad_artifact", "plugins/curve_score", "plugins/curve_figure_evidence",
    "tests/fixtures/plugins/blind_csv_operation_plugin",
)]
from scidiscovery.operations import catalog as catalog_module
from tests.conftest import _SOURCE_FULL_PLUGINS
from tests.operations.test_l5_hardened_run_backend import _system
from scidiscovery.artifact_agent.service.hardened_workspace import HardenedWorkerBackend
from scidiscovery.general_science_plugin import PLUGIN
from scidiscovery.operations.spec import OPERATION_ABI_VERSION

with tempfile.TemporaryDirectory(prefix="scid-r3-baseline-") as work, pytest.MonkeyPatch.context() as patch:
    patch.setattr(catalog_module, "entry_points", lambda: _SOURCE_FULL_PLUGINS)
    catalog_module.compile_installed_catalog.cache_clear()
    catalog, runtime, instance, router = _system(Path(work))
    result = router.call_tool("operation_preflight", {
        "name": "independent_probe", "operation_id": "blind.csv.observe.v1",
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
        "instruction": "Isolated engineering preflight only.",
    })
    output = {
        "source": str(root_path), "ABI": OPERATION_ABI_VERSION,
        "general_component_count": len(PLUGIN.components),
        "execution_context_public": any(x.component_id == "execution_context_schema" and x.public for x in PLUGIN.components),
        "hardened_author_requirements": HardenedWorkerBackend.unsupported_requirements(catalog.operation("blind.csv.observe.v1")),
        "hardened_reviewer_requirements": HardenedWorkerBackend.unsupported_requirements(catalog.operation("blind.csv.review.v1")),
        "actual_root_preflight": result,
        "created_runs": router.call_tool("run_list", {})["runs"],
    }
    print(json.dumps(output, indent=2))
