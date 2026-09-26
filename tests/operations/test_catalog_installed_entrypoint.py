from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("core_version, curve_version, missing, accepted", [
    ("2.0", "3.0", None, True),
    ("1.0", "3.0", None, False),
    ("2.0", "2.0", None, False),
    ("2.0", "3.0", "scid-fixture-curve", False),
])
def test_installer_validates_staged_distribution_dependencies(
    tmp_path, core_version, curve_version, missing, accepted,
):
    """Exercise the real installer guard using metadata, without building wheels."""
    stage = tmp_path / "stage"
    stage.mkdir()
    for name, version, requires in (
        ("scidiscovery", core_version, ()),
        ("scid-fixture-curve", curve_version, ("scidiscovery>=2",)),
        ("scid-fixture-tcad", "1.0", ("scidiscovery>=2", "scid-fixture-curve>=3")),
    ):
        if name == missing:
            continue
        metadata = stage / f"{name.replace('-', '_')}-{version}.dist-info"
        metadata.mkdir()
        lines = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
        lines.extend(f"Requires-Dist: {requirement}" for requirement in requires)
        (metadata / "METADATA").write_text("\n".join(lines) + "\n", encoding="utf-8")
    installer = Path(__file__).resolve().parents[2] / "deploy/install.sh"
    checked = subprocess.run([
        "bash", "-c",
        'source "$1"; SELECTED_PLUGIN_DISTRIBUTIONS=(scid-fixture-curve scid-fixture-tcad); validate_distribution_cohort "$2"',
        "bash", str(installer), str(stage),
    ], env={**os.environ, "SCID_PYTHON": sys.executable}, capture_output=True,
        text=True, timeout=30)
    assert (checked.returncode == 0) is accepted, checked.stderr
    if accepted:
        assert "staged distribution cohort: pass" in checked.stdout
    elif missing:
        assert f"missing staged distribution: {missing}" in checked.stderr
    else:
        assert "incompatible staged distribution cohort" in checked.stderr


_INSTALLED_CURVE_TOOL_PROBE = r'''
import hashlib
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
import curve_score
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(curve_score.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
image = Image.new("RGB", (12, 12), "white")
ImageDraw.Draw(image).line([(1, 9), (9, 1)], fill="#ff0000", width=1)
stream = io.BytesIO()
image.save(stream, format="PNG")
class Context:
    def __init__(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="installed-figure-"))
        self.source = self.workspace / "source.png"
        self.source.write_bytes(stream.getvalue())
        self.remaining_seconds = 30
        self.events = []
    def input_path(self, name):
        assert name == "paper_source"
        return self.source
    def input_media_type(self, name):
        assert name == "paper_source"
        return "image/png"
    def input_ref(self, name):
        assert name == "paper_source"
        return ArtifactRef(
            artifact_id="installed_source",
            sha256=hashlib.sha256(stream.getvalue()).hexdigest(),
            kind="paper_source",
            schema_id="opaque",
        )
    def record_activity(self, event): self.events.append(event)

tools = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("science.evidence.extract.figure.v3")
    )
}
assert "worker_curve_figure_preview" in tools
tool = tools["worker_curve_figure_inspect_source"]
assert set(tool.input_model.model_json_schema()["properties"]) == {"name", "source_page"}
context = Context()
result = tool.contextual_handler(
    tool.input_model(),
    context,
)
assert len(result["images"]) == 1
assert "candidate_overlay" not in result["images"][0]
assert Path(result["images"][0]["local_path"]).is_file()
assert Path(result["images"][0]["local_path"]).stat().st_mode & 0o222 == 0
assert context.events == ["deterministic_analysis_completed"]
'''


def test_clean_installed_core_compiles_only_the_single_plugin_group(installed_probe) -> None:
    output = installed_probe(
        "core",
        r'''
import importlib
from importlib.metadata import entry_points
import scidiscovery.builtin_plugin as builtin_plugin
from scidiscovery.operations.catalog import (
    PLUGIN_ENTRY_POINT_GROUP,
    compile_installed_catalog,
)

assert not hasattr(builtin_plugin, "ARCHITECTURE_TEST_PLUGIN")
for module_name in (
    "architecture_operation_test_plugin",
    "scidiscovery.artifact_agent.service.agent_dispatch",
    "scidiscovery.platforms.codex_worker",
):
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError(f"core-only install exposed {module_name}")

selected = tuple(sorted(
    entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP),
    key=lambda item: item.name,
))
assert [(item.name, item.value) for item in selected] == [
    ("builtin", "scidiscovery.builtin_plugin:CORE_PLUGIN"),
    ("general_science", "scidiscovery.general_science_plugin:PLUGIN"),
]
catalog = compile_installed_catalog()
assert compile_installed_catalog() is catalog
try:
    import scidiscovery.artifact_agent.schema.device_parameters  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("core-only install exposed the TCAD parameter schema")
assert not any("parameter" in item for item in catalog.operation_ids())
print("\n".join(catalog.operation_ids()))
''',
    )
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    assert output.splitlines() == list(compile_catalog((CORE_PLUGIN, PLUGIN)).operation_ids())


def test_curve_wheel_scores_without_installing_figure(installed_probe):
    from tests.operations.test_m2_curve_analysis_boundary import _inputs

    payloads = {key: value.decode() for key, value in _inputs().items()
                if key in {"curve_bundle", "curve_contract", "experiment_plan"}}
    installed_probe("curve", "payloads = " + repr(payloads) + r'''
from importlib.metadata import distribution, PackageNotFoundError
from importlib.util import find_spec
from pathlib import Path
import json
import sys
import curve_score
import curve_score.transform_adapter as adapter
assert find_spec("curve_figure_evidence") is None
assert find_spec("curve_score.figure_evidence_normalizer") is None
assert not tuple(Path(curve_score.__file__).parent.glob("figure*.py"))
try:
    distribution("scidiscovery-curve-figure-evidence")
except PackageNotFoundError:
    pass
else:
    raise AssertionError("figure wheel must not be installed for this smoke")
outputs = adapter.score_curve_bundle_outputs({key: value.encode() for key, value in payloads.items()})
assert set(outputs) == {"metric_report", "merged_curve_bundle", "score_audit", "comparison_plot"}
assert json.loads(outputs["metric_report"][0])["aggregate_status"] == "fail"
assert outputs["comparison_plot"][0].startswith(b"\x89PNG")
assert not any(name.startswith("curve_figure_evidence") for name in sys.modules)
assert Path(adapter.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
''')


def test_installed_figure_tool_executes_packaged_image_dependencies(installed_probe):
    installed_probe("all_domains", _INSTALLED_CURVE_TOOL_PROBE)


def test_installed_tcad_resolves_its_declared_curve_dependency(installed_probe):
    installed_probe("tcad_resolved", r'''
from importlib.metadata import distribution
from scidiscovery.operations.catalog import compile_installed_catalog
assert distribution("scidiscovery-curve-score").version
catalog = compile_installed_catalog()
assert catalog.operation("tcad.study.execute")
assert catalog.operation("scidiscovery.curve-score.v1")
''')


def test_clean_installed_pure_mcp_plugin_completes_a_hardened_run(
    installed_probe,
) -> None:
    installed_probe(
        "blind_csv",
        r'''
import os
# Select the fixture's explicit no-shell reviewer before catalog imports/cache.
os.environ["SCID_TEST_HARDENED_CSV_PLUGIN"] = "1"
import json
import sys
import tempfile
import tomllib
from pathlib import Path

import blind_csv_plugin
from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import (
    HardenedWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.tooling import (
    operation_agent_type,
    operation_worker_server_name,
)
from scidiscovery.platforms import initialize_platform

assert Path(blind_csv_plugin.__file__).resolve().is_relative_to(
    Path(sys.prefix).resolve()
)
root = Path(tempfile.mkdtemp(prefix="installed-hardened-"))
project = root / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed Hardened probe\n", encoding="utf-8")
runtime = open_runtime(
    project_root=project,
    state_root=root / "state",
    worker_backend="hardened",
)
catalog = runtime.operation_catalog
compiled = catalog.operation("blind.csv.observe.v1")
instance = runtime.scheduler_bindings.create_instance(
    name="installed_hardened",
    title="Installed Hardened probe",
    objective="Complete one installed pure-MCP Operation through Hardened.",
)
raw = b"sample,value\na,1\nb,3\n"
source = runtime.artifacts.register(
    raw,
    ArtifactRegistration(
        kind="blind_csv_input",
        schema_id="blind.opaque.v1",
        payload_schema_version=1,
        media_type="text/csv",
        creator=runtime.actor,
    ),
    idempotency_key="installed:hardened:source",
)
runtime.scheduler_bindings.bind(
    instance=instance.instance_id,
    namespace="artifact",
    name="source_csv",
    object_id=source.artifact_id,
)
root_router = RootMCPRouter(
    RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )
)
invoked = root_router.call_tool(
    "operation_invoke",
    {
        "name": "observation",
        "operation_id": compiled.spec.operation_id,
        "inputs": [
            {"port": "source_table", "artifact_names": ["source_csv"]}
        ],
        "instruction": "Make one bounded observation from the exact CSV.",
    },
)
assert invoked["result"]["state"] == "queued"

initialize_platform(
    "codex",
    project,
    python_executable=Path(sys.executable),
    control_socket=root / "control.sock",
    state_root=runtime.state_root,
    worker_backend="hardened",
    operation_catalog=catalog,
)
profile = tomllib.loads(
    project.joinpath(
        ".codex/agents", f"{operation_agent_type(compiled)}.toml"
    ).read_text(encoding="utf-8")
)
assert not profile.get("mcp_servers")
assert profile["features"]["shell_tool"] is False
assert profile["features"]["unified_exec"] is False
assert profile["tools"]["view_image"] is False
platform_config = tomllib.loads((project / ".codex/config.toml").read_text())
assert set(platform_config["mcp_servers"]) == {"scidiscovery"}
server = platform_config["mcp_servers"]["scidiscovery"]
assert set(server["enabled_tools"]) == {"scid_catalog", "scid_describe", "scid_call"}

worker = HardenedWorkerMCPRouter(
    runtime.runs,
    operation_id=compiled.spec.operation_id,
    operation_digest=compiled.digest,
)
opened = worker.call_tool("worker_open_assignment", {})
assert opened["write_protocol"] == "server_file_tools"
assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
assignment_tools = tuple(sorted(assignment["tools"]))
router_tools = tuple(sorted(item["name"] for item in worker.list_tools()))
assert assignment_tools == router_tools
structure = worker.call_tool("worker_csv_summarize", {})
assert structure["numeric_means"] == {"value": 2.0}
result = canonical_json(
    {
        "schema_version": 1,
        "handoff": {"verdict": "pass", "summary": "Bounded result."},
        "payload": {
            "schema_probe": CSV_SCHEMA_PROBE,
            "structure": structure,
            "interpretation": "The bounded arithmetic mean is two.",
            "limitations": ["Two rows do not establish causality."],
        },
    }
).decode("utf-8")
worker.call_tool(
    "worker_file_write_begin",
    {"relative_path": "output/result.json", "operation": "create"},
)
worker.call_tool("worker_file_write_chunk", {"content": result})
worker.call_tool("worker_file_write_commit", {})
assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
status = root_router.call_tool("run_status", {"name": "observation", "intent": "full"})
assert status["state"] == "completed"
assert "backend" not in status  # Control-only identity is not a scientific field.
assert status["output_artifact_name"] == "observation.output"
''',
    )


def test_installed_component_import_failure_has_a_stable_reason_code(
    installed_probe,
) -> None:
    installed_probe(
        "broken",
        r'''
from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

try:
    compile_installed_catalog()
except CatalogCompileError as error:
    assert error.reason_code == "component_implementation_error", error
    assert error.plugin_id == "broken", error
    assert error.field == "broken_transform", error
else:
    raise AssertionError("the installed broken plugin unexpectedly compiled")
''',
    )


def test_installed_invalid_unicode_resource_has_a_stable_reason_code(
    installed_probe,
) -> None:
    installed_probe(
        "invalid_unicode",
        r'''
from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

try:
    compile_installed_catalog()
except CatalogCompileError as error:
    assert error.reason_code == "component_resource_digest_invalid", error
    assert error.plugin_id == "invalid_unicode", error
    assert error.field == "invalid_resource", error
else:
    raise AssertionError("the installed invalid-unicode plugin unexpectedly compiled")
''',
    )
