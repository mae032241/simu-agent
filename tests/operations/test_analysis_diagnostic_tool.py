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
