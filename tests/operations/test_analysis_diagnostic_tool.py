"""Same-Run diagnostic access, images, receipts and optional failure paths."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from curve_score.analysis import analyze_curve_error
from curve_score.diagnostic_tool import DiagnosticInput
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.tooling import operation_native_tool_instruction
from tests.operations import test_m2_curve_analysis_boundary as curve
from tests.operations.test_analysis_claim_scope import generic_worker, mcp_call, submit
from tests.operations.test_result_analysis_tool import score_inputs, limited_report
from tests.operations.test_tcad_result_analysis import (
    analysis_system, analysis_report, open_analysis, raw_request,
)


def request_for_diagnostic(request):
    request = deepcopy(request)
    comparison = request["comparison_spec"]["comparisons"][0]
    comparison["operators"] = [comparison["operators"][0]]
    comparison["evaluation_points"] = 65
    request["comparison_spec"]["comparisons"] = [comparison]
    return request


@pytest.mark.parametrize("domain", ["generic", "tcad"])
def test_diagnostic_runs_and_seals_with_readable_image_without_contract(tmp_path, monkeypatch, domain):
    if domain == "generic":
        worker, opened = generic_worker(tmp_path)
        request = request_for_diagnostic(score_inputs()[1])
        name = "worker_curve_diagnose"
        report = limited_report()
    else:
        worker, opened = open_analysis(analysis_system(tmp_path))
        request = request_for_diagnostic(raw_request())
        request["comparison_spec"]["comparisons"][0]["evaluation_points"] = 257
        name = "worker_tcad_curve_diagnose"
        report = analysis_report()
    before = set(Path(opened["output_directory"]).rglob("*.png"))
    # Diagnosis is a tool, not a premature submission of an unfinished report.
    original_validate = worker.runs.validate_candidate
    monkeypatch.setattr(worker.runs, "validate_candidate", lambda *a, **k: pytest.fail("tool validated unfinished scientific output"))
    response = mcp_call(worker, name, dict(record_key="local_diagnostic", request=request))
    assert "error" not in response, json.dumps(response, indent=2)
    value = response["result"]["structuredContent"]
    record = value["record"]
    assert record["status"] == "computed", value
    assert record["attempt"]["manifest_alias"] == "tool_recovery_manifest"
    assert record["attempt"]["attempt_key"]
    localization = json.loads(Path(value["details"]["path"]).read_text())["localization"]["analyses"][0]
    assert len(localization["residual_trace"]) == request["comparison_spec"]["comparisons"][0]["evaluation_points"]
    assert localization["segments"] and value["images"]
    image = value["images"][0]
    path = Path(image["path"])
    assert path.is_relative_to(Path(opened["output_directory"]).parent)
    assert path not in before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == localization["plot_sha256"] == image["sha256"]
    with Image.open(path) as picture:
        assert picture.size == (1200, 800) and picture.format == "PNG"
    assert worker.compiled.spec.executor.native_tools.view_image
    assert "native view_image for declared task-local images" in operation_native_tool_instruction(worker.compiled)
    report["source_references"] = []
    report["calculation_records"] = [record]
    monkeypatch.setattr(worker.runs, "validate_candidate", original_validate)
    monkeypatch.setattr("curve_score.diagnostic_tool.localize_curve_error", lambda *a, **k: pytest.fail("submission reran diagnosis"))
    result = submit(worker, opened, report)
    assert result["state"] == "completed", result
    status = worker.runs.status(worker._run_id)
    # Numeric localization and the registered PNG survive the local preview.
    assert status.output_ref is not None
    sealed = json.loads(worker.runs.artifacts.read(status.output_ref))
    assert sealed["calculation_records"][0] == record
    evidence = next(item for item in worker.runs.tool_evidence(status.run_id) if item["alias"] == image["evidence_alias"])
    assert evidence["artifact_ref"]["sha256"] == image["sha256"]
    assert evidence["metadata"]["derived_from"] == [item["input_alias"] for item in request["sources"]]
    parents = worker.runs.artifacts.catalog(worker.runs.source_descriptor(status, image["evidence_alias"]).artifact_ref).parent_refs
    assert all(worker.runs.source_descriptor(status, alias).artifact_ref in parents
               for alias in evidence["metadata"]["derived_from"])


def test_diagnostic_receipt_tampering_is_rejected_without_recomputation(tmp_path):
    worker, opened = generic_worker(tmp_path)
    value = worker.call_tool("worker_curve_diagnose", dict(
        record_key="detail", request=request_for_diagnostic(score_inputs()[1])))
    record = value["record"]
    assert record["status"] == "computed", value
    record["result"]["metric_report"]["comparisons"][0]["metrics"][0]["value"] += 1
    report = limited_report()
    report["source_references"] = []
    report["calculation_records"] = [record]
    assert submit(worker, opened, report)["state"] == "rejected"


def test_budget_failure_still_allows_partial_analysis(tmp_path, monkeypatch):
    worker, opened = generic_worker(tmp_path)
    def expired(*args, **kwargs):
        raise TimeoutError("calculation_time_budget")
    monkeypatch.setattr("curve_score.diagnostic_tool.localize_curve_error", expired)
    value = worker.call_tool("worker_curve_diagnose", dict(
        record_key="limited", request=request_for_diagnostic(score_inputs()[1])))
    assert value["record"]["status"] == "error"
    assert value["record"]["reason_code"] == "calculation_time_budget"
    assert not value["images"]
    report = limited_report()
    report["source_references"] = []
    report["calculation_records"] = [value["record"]]
    assert submit(worker, opened, report)["state"] == "completed"


def test_diagnostic_schema_exposes_actual_bounds_and_residual_operators():
    request = request_for_diagnostic(score_inputs()[1])
    request["comparison_spec"]["comparisons"][0]["evaluation_points"] = 258
    with pytest.raises(ValidationError):
        DiagnosticInput.model_validate_json(canonical_json(dict(record_key="too_large", request=request)))
    request["comparison_spec"]["comparisons"][0]["evaluation_points"] = 257
    request["comparison_spec"]["comparisons"][0]["operators"][0]["kind"] = "width_shift"
    with pytest.raises(ValidationError):
        DiagnosticInput.model_validate_json(canonical_json(dict(record_key="unsupported", request=request)))
    schema = DiagnosticInput.model_json_schema()
    assert schema["$defs"]["DiagnosticComparison"]["properties"]["evaluation_points"]["maximum"] == 257


def test_localization_reuses_legacy_segments_and_plot_algorithm(tmp_path):
    old = analyze_curve_error(curve._plan(), curve._contract(),
        curve.evaluate_curve_consistency(curve._bundle(), curve._contract().comparison_spec,
            validation_plan_sha256=curve.canonical_sha256(curve._plan().validation_plans[0]),
            covered_validation_check_keys=tuple(check.check_key for check in curve._plan().validation_plans[0].numerical.checks)),
        curve._bundle())
    from curve_score.analysis import localize_curve_error
    from curve_score.schema import evaluate_curve_consistency
    bundle, spec = curve._bundle(), curve._contract().comparison_spec
    standalone = evaluate_curve_consistency(bundle, spec)
    new = localize_curve_error(bundle, spec, standalone)
    assert new.report == old.report
    assert new.plots == old.plots


def test_all_analysis_roles_receive_image_permission_and_precomputed_image_port(tmp_path):
    catalog = analysis_system(tmp_path)[0]
    for name in ("science.result.diagnose.v1", "tcad.result.analyze.v1", "science.result.diagnose.curve-error.v1"):
        compiled = catalog.operation(name)
        assert compiled.spec.executor.native_tools.view_image
        instruction = operation_native_tool_instruction(compiled)
        forbidden = instruction.split("Forbidden", 1)[-1] if "Forbidden" in instruction else ""
        assert "native view_image" not in forbidden
    precomputed = catalog.operation("science.result.diagnose.curve-error.v1")
    port = next(port for port in precomputed.spec.inputs if port.name == "curve_analysis_plots")
    assert port.min_items == 0 and port.media_types == ("image/png",)


def test_derived_evidence_keeps_current_source_and_execution_recovery_boundaries(tmp_path):
    worker, _ = generic_worker(tmp_path)
    args = dict(tool_name="worker_curve_diagnose", allowed_ports=("tool_evidence", "recovery_manifest_output"),
                raw=b"fixture", media_type="image/png", metadata={})
    with pytest.raises(ValueError, match="bound execution result"):
        worker.runs.accept_tool_evidence(worker._run_id, source_alias="curve_bundle", **args)
    with pytest.raises(ValueError):
        worker.runs.accept_tool_evidence(worker._run_id, derived_from=("unbound_source",), **args)
    with pytest.raises(ValueError, match="capability"):
        worker.runs.accept_tool_evidence(worker._run_id, **{**args, "allowed_ports": ()}, derived_from=("curve_bundle",))


def test_tcad_diagnostic_preserves_case_mapping_rejection(tmp_path):
    worker, _ = open_analysis(analysis_system(tmp_path))
    request = request_for_diagnostic(raw_request())
    request["sources"][0]["case_key"] = "not_the_bound_case"
    response = mcp_call(worker, "worker_tcad_curve_diagnose", dict(record_key="bad_mapping", request=request))
    assert "error" in response
    assert response["error"]["data"]["diagnostics"][0]["code"] == "case_mapping_invalid"
