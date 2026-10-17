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
from tests.operations.test_result_analysis_tool import score_inputs, limited_report


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
