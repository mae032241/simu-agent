"""Optional same-Run residual localization using the existing curve renderer."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Annotated, Callable, Literal

from pydantic import Field

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.artifact_agent.service.analysis_artifacts import publish_analysis_file, retain_calculation
from scidiscovery.artifact_agent.service.local_workspace import WorkspaceError, write_control_workspace_file
from scidiscovery.operation_contract import contract_diagnostic
from scidiscovery.operations.spec import CollectionSpec, ComponentRef, OutputPortSpec
from scidiscovery.operations.tooling import WorkerToolDefinition
from .analysis import localize_curve_error
from .analysis_tool import (
    AnalysisCurveComparison, AnalysisCurveComparisonSpec, AnalysisScoreInput,
    AnalysisScoreRequest, ScoreLimitError, UnsupportedSourceError, _aliases,
    bundle_from_sources, check_deadline, evaluate_analysis_request,
)
from .schema import CurveConsistencyReport, CurveOperatorSpec

ALGORITHM_VERSION = "analysis-curve-diagnostics.v2"
PLOT_PORT = "tool_evidence"
MAX_DETAILS_BYTES = 4 * 1024 * 1024
MAX_PLOTS = 32


class ResidualOperator(CurveOperatorSpec):
    kind: Literal["residual_rms", "residual_max_abs", "mean_signed_difference"]


class DiagnosticComparison(AnalysisCurveComparison):
    # The bounded diagnostic grid is independent of the short report record.
    evaluation_points: Annotated[int, Field(ge=2, le=257)] = 257
    operators: Annotated[tuple[ResidualOperator, ...], Field(min_length=1, max_length=1)]


class DiagnosticComparisonSpec(AnalysisCurveComparisonSpec):
    comparisons: Annotated[tuple[DiagnosticComparison, ...], Field(min_length=1, max_length=1)]


class DiagnosticRequest(AnalysisScoreRequest):
    comparison_spec: DiagnosticComparisonSpec


class DiagnosticInput(AnalysisScoreInput):
    request: DiagnosticRequest


DIAGNOSTIC_PLOT_OUTPUT = OutputPortSpec(
    name=PLOT_PORT, description="Optional tool-owned calculation records, details, images and declared analysis files.",
    kind="tool_evidence", schema="opaque", media_types=("application/json", "image/png", "text/plain", "text/csv"),
    codec=ComponentRef("opaque_codec", plugin_id="general_science"),
    schema_resource=ComponentRef("opaque_schema", plugin_id="general_science"),
    semantic_contract=ComponentRef("diagnosis_semantic_contract", plugin_id="curve_score"),
    min_items=0, max_items=MAX_PLOTS, max_item_bytes=16 * 1024 * 1024,
    collection=CollectionSpec(max_total_bytes=64 * 1024 * 1024),
)

DIAGNOSTIC_GUIDANCE = """
Choose methods for the current uncertainty. If a scalar cannot explain a discrepancy,
consider {diagnostic_tool} for local residuals, contributions and overlay/residual
images; read its exact contract before calling. No new curve contract/review or
mandatory diagnostic stage is required. Full traces and segments remain at returned
details aliases/paths. Use native view_image when helpful: previews are read-only,
task-local, and their evidence is sealed with the Run. A residual segment boundary
is not a gradient change point or physical interface. Crossing/width metrics remain
available through scoring. Distinguish exploration from preregistered tests, record
method changes, and choose a justified next step or bounded stopping reason.
Unavailable diagnostics allow limited conclusions; never substitute another metric
for an unsupported statistic. Calculation citation rules below apply to both tools.
"""


def record_metric_report(record: CalculationRecord) -> CurveConsistencyReport:
    result = record.result
    if record.algorithm_version in {"analysis-curve-diagnostics.v1", ALGORITHM_VERSION}:
        result = result["metric_report"]
    return CurveConsistencyReport.model_validate_json(canonical_json(result), strict=True)


def _publish_plot(context: OperationToolContext, name: str, raw: bytes, sources: tuple[str, ...]) -> dict:
    if PLOT_PORT not in context.output_collections:
        raise ValueError("diagnostic plot output is not declared")
    if len(raw) > 1024 * 1024:
        raise ScoreLimitError("diagnostic_plot_bytes")
    accepted = context.accept_evidence(raw=raw, media_type="image/png", derived_from=sources,
        metadata={"kind": "curve_diagnostic", "algorithm_version": ALGORITHM_VERSION, "plot_item": name})
    path = write_control_workspace_file(
        context.workspace, Path(".operation-tools/curve-diagnostics") / name, raw,
        replace=False, mode=0o400, create_parents=True,
    )
    return {"path": str(path), "plot_item": name, "evidence_alias": accepted["alias"],
            "sha256": hashlib.sha256(raw).hexdigest()}


def run_diagnostic_tool(
    request: AnalysisScoreInput, context: OperationToolContext, *,
    parse_bundle: Callable = bundle_from_sources,
) -> dict:
    """Read current evidence, compute one diagnostic and seal the normal receipt.

    TCAD supplies only its existing raw parser; localization and output handling
    are identical for both operations.
    """
    deadline = time.monotonic() + context.remaining_seconds / 2
    sources, images, diagnostics, details = {}, [], (), None
    base = dict(record_key=request.record_key, request=request.request.raw_request,
                input_digests={}, algorithm_version=ALGORITHM_VERSION)
    try:
        for alias in _aliases(request.request):
            check_deadline(deadline)
            try:
                sources[alias] = context.read_evidence(alias)
            except (KeyError, ValueError):
                raise ValueError("bound_source_missing") from None
        base["input_digests"] = {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}
        bundle = parse_bundle(request.request, sources, deadline=deadline)
        score = evaluate_analysis_request(
            record_key=request.record_key, request=request.request.raw_request,
            sources=sources, bundle=bundle, validated_request=request.request, deadline=deadline,
        )
        if score.status != "computed":
            record = score.model_copy(update={"algorithm_version": ALGORITHM_VERSION})
        else:
            metric = record_metric_report(score)
            artifacts = localize_curve_error(
                bundle, request.request.comparison_spec, metric,
                comparison_key=request.request.comparison_spec.comparisons[0].comparison_key,
                check_budget=lambda: check_deadline(deadline),
            )
            localization = artifacts.report.model_dump(mode="json")
            # Content-addressed filenames allow repeated calls without overwriting
            # another diagnostic. Scientific records contain no workspace paths.
            plots = []
            for item, (_, raw) in zip(localization["analyses"], artifacts.plots, strict=True):
                name = f"curve_{hashlib.sha256(raw).hexdigest()}.png"
                item["plot_item"] = name
                plots.append((name, raw))
            raw_details = canonical_json({"metric_report": score.result, "localization": localization})
            if len(raw_details) > MAX_DETAILS_BYTES:
                raise ScoreLimitError("diagnostic_details_byte_limit")
            details = publish_analysis_file(context, raw_details, media_type="application/json",
                kind="calculation_details", sources=tuple(sources), suffix=".json",
                metadata={"record_key": request.record_key, "algorithm_version": ALGORITHM_VERSION})
            for name, raw in plots:
                check_deadline(deadline)
                images.append(_publish_plot(context, name, raw, tuple(sources)))
            record = CalculationRecord(**base, status="computed", result={
                "metric_report": score.result,
                "details_alias": details["evidence_alias"],
                "images": [{k: v for k, v in image.items() if k != "path"} for image in images],
            })
        check_deadline(deadline)
    except (TimeoutError, ScoreLimitError, UnsupportedSourceError, ValueError, OSError, WorkspaceError) as error:
        status = "error" if isinstance(error, (TimeoutError, ScoreLimitError, OSError, WorkspaceError)) else "unavailable"
        reason = ("calculation_time_budget" if isinstance(error, TimeoutError)
                  else str(error) if isinstance(error, ScoreLimitError)
                  else "diagnostic_plot_write_failed" if isinstance(error, (OSError, WorkspaceError))
                  else "diagnostic_unavailable")
        record = CalculationRecord(**base, status=status, reason_code=reason)
        diagnostics = (contract_diagnostic(reason, phase="tool_execution",
            affected_action="tool_call", message=str(error)[:1000] or reason),)
        images = []
        details = None
    response = record.model_dump(mode="json", exclude={"attempt", "diagnostics"})
    if record.status != "computed" and not diagnostics:
        diagnostics = (contract_diagnostic(record.reason_code or record.status,
            phase="tool_execution", affected_action="tool_call",
            message="The diagnostic is unavailable; retain the reason and submit any supported finite analysis."),)
    finished = context.finish_attempt(
        result_status=record.status, reason_code=record.reason_code,
        response=response, diagnostics=diagnostics,
    )
    if finished is not None:
        attempt, attempt_diagnostics = finished
        response.update(attempt=attempt, diagnostics=list(attempt_diagnostics))
    return {"record": retain_calculation(context, response, summary=True), "images": images, "details": details}


DIAGNOSTIC_TOOL = WorkerToolDefinition(
    name="worker_curve_diagnose",
    description="Optionally localize one residual comparison using bound curves or explicit CSV columns. Returns compact metrics; read record.calculation_path for the complete record. Cite record.calculation_ref; record and receipt are retained automatically. Full details (<=4 MiB) and overlay/residual images have saved evidence aliases and task-local paths. One operator, 2-257 samples; no curve contract or additional Run.",
    input_model=DiagnosticInput, capability="analysis.curve_diagnose",
    contextual_handler=run_diagnostic_tool, record_attempts=True,
    evidence_ports=("tool_evidence", "recovery_manifest_output"),
)
