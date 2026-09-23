"""Development attempts must remain repairable without a scientific handoff."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.workspace import WorkspaceProtocolError
from tcad_artifact.operation_workspace import _write
from scidiscovery.artifact_agent.service.local_workspace import WorkspaceError, write_control_workspace_file
from tests.operations.test_l4_local_tcad import (
    _system, _invoke, _ImmediateDebugAdapter, LocalWorkerMCPRouter, LocalTCADDebugService,
)


def test_development_failures_are_recorded_once_and_recover_without_handoff(tmp_path):
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    _invoke(root, "process", "tcad.deck.author.initial.v1", [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ])
    operation = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs, operation_id=operation.spec.operation_id, operation_digest=operation.digest,
        tool_services={"tcad_artifact:tcad.development_debug": LocalTCADDebugService(
            adapter=_ImmediateDebugAdapter(), exchange_root=tmp_path / "debug",
        )},
    )
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(str(opened["workspace_path"]))
    deck = workspace / "deck"
    (deck / "handoff.json").unlink()
    (deck / "files/main.cmd").write_text("set case_smoke 1\n", encoding="utf-8")
    (deck / "files/initialize.cmd").write_text("set case_smoke 1\n", encoding="utf-8")
    declarations_path = deck / "declarations.json"
    declarations = json.loads(declarations_path.read_bytes())
    declarations.update({
        "entrypoint": "main.cmd", "development_initialization_entrypoint": "initialize.cmd",
        "case_anchors": [{"experiment_key": "entrypoint_smoke", "case_key": "smoke",
                          "relative_path": "absent.cmd", "locator": "set case_smoke 1"}],
        "raw_outputs": [{"name": "profile", "relative_path": "profile.tdr",
                         "media_type": "application/octet-stream"}],
    })
    assert "expected_outputs" not in json.loads((deck / "project.json").read_bytes())
    contract = json.loads((deck / "contract/materialization-spec.json").read_bytes())
    assert contract["raw_output_fields"] == ["name", "relative_path", "media_type"]
    assert contract["control_generated_output_fields"] == ["capture", "max_bytes"]
    errors = []
    reports = []
    for name, path, locator in (("a", "absent.cmd", "set case_smoke 1"),
                                ("b", "main.cmd", "absent locator")):
        declarations["case_anchors"][0].update(relative_path=path, locator=locator)
        declarations_path.write_bytes(canonical_json(declarations))
        result = worker.call_tool("worker_tcad_debug_run", {"run_name": name, "mode": "preflight"})
        assert result["state"] == "rejected", result
        errors.append(result["diagnostics"])
        reports.append((deck / "reports/materialization.json").read_bytes())
    assert errors[0] != errors[1]
    assert reports[0] != reports[1]
    status = runtime.runs.status(worker._run_id)
    events = runtime.runs.diagnostic_events(status)["events"]
    rejections = [event for event in events if event["activity"] == "output_rejected"]
    assert len(rejections) == 2
    assert all(event["diagnostic"]["details"] for event in rejections)
    declarations["case_anchors"][0]["locator"] = "set case_smoke 1"
    declarations_path.write_bytes(canonical_json(declarations))
    result = worker.call_tool("worker_tcad_debug_run", {"run_name": "fixed", "mode": "preflight"})
    assert result["state"] == "succeeded", result
    assert json.loads((deck / "reports/materialization.json").read_bytes())["status"] == "pass"
    envelope = json.loads(Path(str(opened["output_directory"]), "result.json").read_bytes())
    assert envelope["handoff"]["verdict"] == "inconclusive"
    assert envelope["payload"]["expected_outputs"][0]["name"] == "solver_log"
    generated = envelope["payload"]["expected_outputs"][1]
    assert generated["name"] == "profile" and generated["capture"] == "workspace_file"
    assert generated["max_bytes"] > 0
    # Candidate transport fields never replace the required authored final handoff.
    assert worker.call_tool("worker_submit_result", {})["state"] == "rejected"
    (deck / "handoff.json").write_text('{"verdict":"pass","summary":""}', encoding="utf-8")
    assert worker.call_tool("worker_submit_result", {})["state"] == "rejected"
    (deck / "handoff.json").write_bytes(canonical_json({"verdict": "pass", "summary": "Ready for review."}))
    # Finalization still requires qualified initialization.
    assert worker.call_tool("worker_submit_result", {})["diagnostics"][0]["type"] == "tcad_initialization_missing"
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "init", "mode": "initialization"})["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_derived_replacement_preserves_immutable_and_symlink_guards(tmp_path):
    path = tmp_path / "report.json"
    _write(path, b"first", editable=False)
    with pytest.raises(WorkspaceProtocolError, match="immutable"):
        _write(path, b"second", editable=False)
    write_control_workspace_file(tmp_path, Path("report.json"), b"second", replace=True, mode=0o400)
    assert path.read_bytes() == b"second"
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(WorkspaceError, match="destination"):
        write_control_workspace_file(tmp_path, Path("link.json"), b"third", replace=True, mode=0o400)
    assert path.read_bytes() == b"second"


@pytest.mark.parametrize("field,value", [("capture", "workspace_file"), ("max_bytes", 1024)])
def test_raw_output_declarations_reject_control_generated_fields(field, value):
    from pydantic import ValidationError
    from tcad_artifact.project_materializer import DeclaredRawOutput
    with pytest.raises(ValidationError, match="extra_forbidden"):
        DeclaredRawOutput.model_validate({
            "name": "profile", "relative_path": "profile.tdr",
            "media_type": "application/octet-stream", field: value,
        })


def test_failed_report_write_preserves_original_materialization_error(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tcad_artifact import operation_workspace as module
    from tcad_artifact.project_materializer import ProjectMaterializationError

    deck = tmp_path / "deck"
    (deck / "files").mkdir(parents=True)
    (deck / "project.json").write_text("{}")
    (deck / "declarations.json").write_text("{}")
    original = ({"path": "$.deck.declarations", "message": "Unique source error A", "type": "source_error"},)
    class Failure(ProjectMaterializationError):
        def __init__(self):
            self.report = object()
        @property
        def details(self):
            return original
    def fail_materialization(**kwargs):
        raise Failure()
    def fail_write(*args, **kwargs):
        raise WorkspaceError("control workspace destination is invalid")
    monkeypatch.setattr(module, "materialize_deck_project", fail_materialization)
    monkeypatch.setattr(module, "_input", lambda *args: b"{}")
    monkeypatch.setattr(module, "report_json", lambda report: b"{}")
    monkeypatch.setattr(module, "write_control_workspace_file", fail_write)
    request = SimpleNamespace(operation_id="tcad.deck.author.initial.v1", workspace=tmp_path,
                              final_submission=False, output_limit_bytes=100000, input_paths={"experiment_plan": tmp_path / "unused"})
    with pytest.raises(WorkspaceProtocolError) as caught:
        module.finalize_workspace(request)
    assert caught.value.details[:1] == original
    assert caught.value.details[1]["type"] == "materialization_report_write_failed"
