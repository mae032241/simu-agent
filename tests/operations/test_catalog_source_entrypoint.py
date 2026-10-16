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


def test_source_core_discovery_caches_catalog_without_domain_operations(source_catalog):
    source_catalog()
    import scidiscovery.builtin_plugin as builtin_plugin
    from scidiscovery.operations.catalog import compile_installed_catalog

    assert not hasattr(builtin_plugin, "ARCHITECTURE_TEST_PLUGIN")
    catalog = compile_installed_catalog()
    assert compile_installed_catalog() is catalog
    assert not any("parameter" in item for item in catalog.operation_ids())


def test_curve_scores_without_importing_figure(tmp_path):
    """Keep the optional-plugin import boundary in a fresh source process."""
    from tests.operations.test_m2_curve_analysis_boundary import _inputs

    payloads = {key: value.decode() for key, value in _inputs().items()
                if key in {"curve_bundle", "curve_contract", "experiment_plan"}}
    repository = Path(__file__).resolve().parents[2]
    bootstrap = "import sys; sys.path[:0] = " + repr([
        str(repository / "src"), str(repository / "plugins/curve_score"),
    ]) + "\n"
    probe = r'''
import importlib.abc
import json
class NoFigure(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("curve_figure_evidence"):
            raise AssertionError("scoring imported the optional figure plugin")
sys.meta_path.insert(0, NoFigure())
import curve_score.transform_adapter as adapter
outputs = adapter.score_curve_bundle_outputs({key: value.encode() for key, value in payloads.items()})
assert set(outputs) == {"metric_report", "merged_curve_bundle", "score_audit", "comparison_plot"}
assert json.loads(outputs["metric_report"][0])["aggregate_status"] == "fail"
assert outputs["comparison_plot"][0].startswith(b"\x89PNG")
assert not any(name.startswith("curve_figure_evidence") for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-I", "-c", bootstrap + "payloads = " + repr(payloads) + probe],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_source_figure_tool_preserves_image_and_worker_contracts(source_catalog, tmp_path):
    source_catalog("curve_score", "tcad_artifact", "curve_figure_evidence")
    import hashlib
    import io
    from pathlib import Path

    from PIL import Image, ImageDraw
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.catalog import compile_installed_catalog
    from scidiscovery.operations.tooling import operation_worker_tools

    catalog = compile_installed_catalog()
    for operation_id in ("science.evidence.audit.v1", "science.evidence.audit.intake.v1",
                         "science.figure.evidence.audit.v2"):
        assert catalog.operation(operation_id).spec.decision_fields == ("checks",)
    for identity in catalog.operation_ids():
        operation = catalog.operation(identity)
        if operation.spec.executor.kind == "agent" and operation.spec.executor.native_tools.shell != "none":
            tools = {tool.name: tool for tool in operation_worker_tools(operation)}
            assert "worker_publish_files" in tools and "worker_materialize_input" in tools
            assert set(tools["worker_publish_files"].input_model.model_json_schema()["properties"]) == {"files", "source_aliases"}
    image = Image.new("RGB", (12, 12), "white")
    ImageDraw.Draw(image).line([(1, 9), (9, 1)], fill="#ff0000", width=1)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    class Context:
        def __init__(self):
            self.workspace = tmp_path
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
                artifact_id="source_fixture",
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


def test_source_third_party_plugin_completes_a_local_run(source_catalog, tmp_path):
    source_catalog("blind_csv")
    import json
    import subprocess
    import sys
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 uses the declared conditional dependency.
        import tomli as tomllib
    from pathlib import Path

    from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
        LocalWorkerMCPRouter,
    )
    from scidiscovery.artifact_agent.interfaces.mcp_root import (
        RootMCPRouter,
        RootToolFacade,
    )
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.operations.tooling import operation_agent_type
    from scidiscovery.platforms import initialize_platform

    root = tmp_path
    project = root / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Source Local probe\n", encoding="utf-8")
    runtime = open_runtime(
        project_root=project,
        state_root=root / "state",
        worker_backend="local",
    )
    catalog = runtime.operation_catalog
    compiled = catalog.operation("blind.csv.observe.v1")
    instance = runtime.scheduler_bindings.create_instance(
        name="source_local",
        title="Source Local probe",
        objective="Complete one source pure-MCP Operation through Local.",
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
        idempotency_key="source:local:source",
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
        worker_backend="local",
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

    author_run = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name="observation")
    # Distinct declared test coordinates exercise the same attach/identity gate as
    # platform Workers; the fixture is not a live platform execution.
    author_identity = ("source-author-session", "source-author-thread")
    runtime.runs.worker_connections.attach(run_id=author_run,
        platform_session=author_identity[0], thread_id=author_identity[1])
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        run_id=author_run, trusted_caller=author_identity,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    assert Path(opened["start_here_path"]).is_file()
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
    Path(opened["output_directory"], "result.json").write_text(result)
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    status = root_router.call_tool("run_status", {"name": "observation", "intent": "status"})
    assert status["state"] == "completed"
    assert "backend" not in status  # Control-only identity is not a scientific field.
    assert status["output_artifact_name"] == "observation.output"
    assert "payload" not in status and "numeric_means" not in status

    # Complete scientific originals remain readable by the plugin's declared Worker.
    # Root binds the exact sealed output; its status response does not carry that data.
    review = catalog.operation("blind.csv.review.v1")
    consumer = root_router.call_tool("operation_invoke", {
        "name": "read_observation", "operation_id": review.spec.operation_id,
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]},
                   {"port": "csv_observation", "artifact_names": [status["output_artifact_name"]]}],
        "instruction": "Read the exact completed observation and retain its limitations.",
    })
    assert consumer["result"]["state"] == "queued"
    reader_run = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name="read_observation")
    reader_identity = ("source-reader-session", "source-reader-thread")
    runtime.runs.worker_connections.attach(run_id=reader_run,
        platform_session=reader_identity[0], thread_id=reader_identity[1])
    reader = LocalWorkerMCPRouter(runtime.runs, operation_id=review.spec.operation_id,
        operation_digest=review.digest, run_id=reader_run, trusted_caller=reader_identity)
    reader_opened = reader.call_tool("worker_open_assignment", {})
    reader_assignment = json.loads(Path(reader_opened["assignment_path"]).read_bytes())
    source_name = next(item.source_name for item in runtime.runs.status(reader._run_id).inputs
        if item.port_name == "csv_observation")
    bound = next(item for item in reader_assignment["inputs"] if item["source_name"] == source_name)
    workspace = Path(reader_opened["assignment_path"]).parent
    readback = subprocess.run([sys.executable, "-I", str(workspace / "tools/read_input.py"),
        bound["source_name"], "--full", "--budget", "8192"],
        cwd=workspace, capture_output=True, text=True, timeout=5)
    assert readback.returncode == 0, readback.stderr
    assert "\n[read_input: end;" in readback.stdout
    sealed_payload = readback.stdout.rsplit("\n[read_input: ", 1)[0]
    assert sealed_payload.encode() == canonical_json(json.loads(result)["payload"])
    assert json.loads(sealed_payload)["structure"]["numeric_means"] == {"value": 2.0}
    assert json.loads(sealed_payload)["limitations"] == ["Two rows do not establish causality."]


def test_source_broken_plugin_retains_its_diagnostic(source_catalog):
    source_catalog('broken')
    from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

    with pytest.raises(CatalogCompileError) as caught:
        compile_installed_catalog()
    assert caught.value.reason_code == 'component_implementation_error'
    assert caught.value.plugin_id == 'broken'
    assert caught.value.field == 'broken_transform'


def test_source_invalid_unicode_plugin_retains_its_diagnostic(source_catalog):
    source_catalog('invalid_unicode')
    from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

    with pytest.raises(CatalogCompileError) as caught:
        compile_installed_catalog()
    assert caught.value.reason_code == 'component_resource_digest_invalid'
    assert caught.value.plugin_id == 'invalid_unicode'
    assert caught.value.field == 'invalid_resource'
