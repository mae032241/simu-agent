"""TCAD result analysis with optional, same-Run raw-output curve scoring."""
from __future__ import annotations

from scidiscovery.operations.input_validation import BoundSourceError, parse_bound_json

import json
import hashlib
import csv
from typing import Annotated, Any, Literal, Mapping

from pydantic import Field, ValidationError

from curve_score.analysis_tool import (
    ALGORITHM_VERSION, MAX_POINTS, AnalysisScoreInput, AnalysisSource, CSVSource, ScoreRequest,
    ScoreLimitError, UnsupportedSourceError, csv_series, parse_score_request,
    evaluate_analysis_request, admit_raw_lines, check_deadline, run_score_tool,
)
from curve_score.schema import CurveBundle
from curve_score.diagnostic_tool import (
    DIAGNOSTIC_GUIDANCE, DiagnosticComparisonSpec,
    run_diagnostic_tool,
)
from curve_score.science_operations import BASE_TOOLS, Components, validate_analysis_report
from curve_score.analysis_files import GUIDANCE as ANALYSIS_FILES_GUIDANCE
from scidiscovery.artifact_agent.service.analysis_artifacts import analysis_calculations
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import Identifier, canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
from scidiscovery.artifact_agent.schema.layered_diagnosis import CaseMappingBasis, LayeredDiagnosisReport
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
from scidiscovery.operation_contract import SemanticRuleViolation, declared_violation, validation_diagnostics
from scidiscovery.operations.input_validation import OperationInvocationError
from scidiscovery.operation_declaration import (
    OPERATION_AGENT_PREAMBLE, scientific_agent_operation, scientific_semantic_contract,
)
from scidiscovery.operations.spec import (
    CallableComponent, ComponentRef, ComponentSpec, InputPortSpec, OutputPortSpec, InputValidationSpec, CollectionSpec,
)
from scidiscovery.operations.tooling import WorkerToolDefinition

from .curve_normalizer import SProcessLogSourceSpec, SProcessPointLimitError, SProcessSeriesSpec, normalize_sprocess_log
from .plx_normalizer import SProcessPLXSourceSpec, normalize_sprocess_plx
from .project_packager import ReviewedDeckPackage, TCADRuntimeManifest


class TCADSourceIdentity(AnalysisSource):
    output_name: Identifier | None = None
    experiment_key: Identifier | None = None
    case_mapping_basis: CaseMappingBasis | None = None


class TCADCSVSource(CSVSource, TCADSourceIdentity):
    pass


class SProcessSource(SProcessSeriesSpec, TCADSourceIdentity):
    # The existing series declaration owns axes and point relationships.
    max_points: Literal[MAX_POINTS] = MAX_POINTS
    min_points: Annotated[int, Field(ge=2, le=MAX_POINTS)] = 2


class SProcessPLXSource(SProcessSource):
    format: Literal["sprocess_plx"]
    dataset_name: Annotated[str, Field(min_length=1, max_length=256)]


class SProcessLogSource(SProcessSource):
    format: Literal["sprocess_log"]


class TCADScoreRequest(ScoreRequest):
    sources: Annotated[
        tuple[Annotated[TCADCSVSource | SProcessPLXSource | SProcessLogSource,
                        Field(discriminator="format")], ...],
        Field(min_length=1, max_length=40),
    ]


class TCADScoreInput(AnalysisScoreInput):
    request: TCADScoreRequest


def analysis_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    if parameters:
        return False
    grouped: dict[str, list[Any]] = {}
    for item in inputs:
        grouped.setdefault(item.port_name, []).append(item.artifact)
    if any(len(grouped.get(name, ())) != 1 for name in (
        "experiment_plan", "experiment_review", "reviewed_package", "runtime_manifest"
    )):
        return False
    plan, review, package, manifest = (grouped[name][0] for name in (
        "experiment_plan", "experiment_review", "reviewed_package", "runtime_manifest"
    ))
    if not (
        plan.ref in review.parent_refs and review.handoff_verdict == "pass"
        and dict(review.labels).get("operation_id") == "science.object.review.v1"
        and dict(review.labels).get("operation_output_port") == "scientific_review"
        and plan.ref in package.parent_refs and package.ref in manifest.parent_refs
    ):
        return False
    diagnostics = grouped.get("diagnostics", ())
    manifest_labels = dict(manifest.labels)
    if any(
        diagnostic.parent_refs != manifest.parent_refs
        or dict(diagnostic.labels).get("logical_name") != "tcad_log"
        or not manifest_labels.get("execution_id")
        or dict(diagnostic.labels).get("execution_id") != manifest_labels["execution_id"]
        or diagnostic.media_type.split(";", 1)[0] != "text/plain"
        for diagnostic in diagnostics
    ):
        return False
    outputs = grouped.get("solver_outputs", ())
    recovered = grouped.get('recovery_manifest', ())
    execution = grouped.get('execution_result', ())
    if execution and (package.ref not in execution[0].parent_refs or manifest.ref not in execution[0].parent_refs):
        return False
    if recovered and (not execution or recovered[0].handoff_verdict is None
            or execution[0].ref not in recovered[0].parent_refs or package.ref not in recovered[0].parent_refs
            or dict(recovered[0].labels).get('operation_output_port') != 'recovery_manifest_output'):
        return False
    direct = [output for output in outputs if output.parent_refs == manifest.parent_refs]
    for output in outputs:
        if output in direct:
            continue
        if not recovered or output.ref not in recovered[0].parent_refs:
            return False
    return all(
        package.ref in audit.parent_refs and manifest.ref in audit.parent_refs
        and all(output.ref in audit.parent_refs for output in direct)
        for audit in grouped.get("runtime_attestation", ())
    )


def _source_aliases(request: TCADScoreRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys(mapping.input_alias for mapping in request.sources))


def parse_tcad_sources(request: TCADScoreRequest, sources: Mapping[str, bytes], *, deadline: float | None = None) -> CurveBundle:
    """Parse bound bytes without an experiment-time comparison contract."""
    aliases = _source_aliases(request)
    series = []
    for mapping in request.sources:
        check_deadline(deadline)
        raw = sources[mapping.input_alias]
        if len(raw) > 32 * 1024 * 1024:
            raise ScoreLimitError("source_byte_limit")
        admit_raw_lines(raw)
        if isinstance(mapping, TCADCSVSource):
            series.append(csv_series(mapping, raw, deadline=deadline))
        else:
            if isinstance(mapping, SProcessPLXSource):
                # The selected physical quantity is explicit, even for a single dataset.
                bundle, _ = normalize_sprocess_plx(raw, SProcessPLXSourceSpec(
                    series=mapping, dataset_name=mapping.dataset_name,
                    max_input_bytes=32 * 1024 * 1024,
                ), source_name=mapping.input_alias)
            else:
                bundle, _ = normalize_sprocess_log(raw, SProcessLogSourceSpec(
                    expected_series=(mapping,), max_input_bytes=32 * 1024 * 1024,
                ))
            series.extend(bundle.series)
        check_deadline(deadline)
        if sum(len(item.points) for item in series) > MAX_POINTS:
            raise ScoreLimitError("source_point_limit")
    return CurveBundle(
        source_profile="tcad.analysis.raw.v1",
        source_digests=tuple(dict.fromkeys(hashlib.sha256(sources[name]).hexdigest() for name in aliases)),
        series=tuple(series),
    )


def evaluate_tcad_request(*, record_key: str, request: dict[str, Any], sources: Mapping[str, bytes], deadline: float | None = None, validated_request: TCADScoreRequest | None = None) -> CalculationRecord:
    try:
        parsed = validated_request or parse_score_request(TCADScoreRequest, request)
    except ValidationError as error:
        return CalculationRecord(record_key=record_key, request=request, input_digests={},
            algorithm_version=ALGORITHM_VERSION, status="unavailable", reason_code="invalid_arguments",
            diagnostics=validation_diagnostics(error, schema=TCADScoreRequest.model_json_schema())[:8])
    digests = {}
    try:
        check_deadline(deadline)
        aliases = _source_aliases(parsed)
        digests = {name: hashlib.sha256(sources[name]).hexdigest() for name in aliases if name in sources}
        if any(name not in sources for name in aliases):
            return CalculationRecord(record_key=record_key, request=parsed.raw_request, input_digests=digests,
                algorithm_version=ALGORITHM_VERSION, status="unavailable", reason_code="bound_source_missing")
        bundle = parse_tcad_sources(parsed, sources, deadline=deadline)
    except TimeoutError:
        return CalculationRecord(record_key=record_key, request=request, input_digests=digests,
            algorithm_version=ALGORITHM_VERSION, status="error", reason_code="calculation_time_budget")
    except ScoreLimitError as error:
        return CalculationRecord(record_key=record_key, request=parsed.raw_request, input_digests=digests,
            algorithm_version=ALGORITHM_VERSION, status="error", reason_code=str(error))
    except SProcessPointLimitError:
        return CalculationRecord(record_key=record_key, request=parsed.raw_request, input_digests=digests,
            algorithm_version=ALGORITHM_VERSION, status="error", reason_code="source_point_limit")
    except UnsupportedSourceError as error:
        return CalculationRecord(
            record_key=record_key, request=request, input_digests=digests,
            algorithm_version=ALGORITHM_VERSION, status="unsupported",
            reason_code=str(error),
        )
    except (ValueError, csv.Error):
        return CalculationRecord(
            record_key=record_key, request=request, input_digests=digests,
            algorithm_version=ALGORITHM_VERSION, status="unavailable", reason_code="tcad_source_data_invalid",
        )
    return evaluate_analysis_request(record_key=record_key, request=parsed.raw_request, sources=sources,
        bundle=bundle, deadline=deadline, validated_request=parsed)


def _check_score_sources(request: TCADScoreInput, context: OperationToolContext) -> None:
    from scidiscovery.operation_contract import DiagnosticError, contract_diagnostic
    plan = parse_bound_json(ExperimentPortfolio, context.read_input("experiment_plan"))
    package = parse_bound_json(ReviewedDeckPackage, context.read_input("reviewed_package"))
    for index, source in enumerate(request.request.sources):
        aliases = [source.input_alias]
        basis = source.case_mapping_basis
        try:
            if basis:
                for item in basis.evidence_refs:
                    # A locator is a scientific claim; this read proves availability.
                    context.read_evidence(item.input_alias)
                    aliases.append(item.input_alias)
            descriptors = {alias:context.source_descriptor(alias) for alias in aliases}
        except ValueError as error:
            raise DiagnosticError("mapping source is unavailable", details=(contract_diagnostic(
                "source_unavailable", phase="tool_execution", affected_action="tool_call",
                repairable=True, path=f"$.request.sources[{index}]",
                message="The source or mapping evidence alias is not available in this Run."),)) from error
        try:
            resolve_case_mapping(plan, package, descriptors, source)
        except SemanticRuleViolation as error:
            raise DiagnosticError("case mapping is not established", details=(contract_diagnostic(
                "case_mapping_invalid", phase="tool_execution", affected_action="tool_call",
                repairable=True, path=f"$.request.sources[{index}].case_mapping_basis",
                message=str(error)),)) from error


def tcad_score_tool(request: TCADScoreInput, context: OperationToolContext) -> dict[str, Any]:
    _check_score_sources(request, context)
    return run_score_tool(request, context, evaluate_tcad_request)


class TCADDiagnosticRequest(TCADScoreRequest):
    comparison_spec: DiagnosticComparisonSpec


class TCADDiagnosticInput(TCADScoreInput):
    request: TCADDiagnosticRequest


def tcad_diagnostic_tool(request: TCADDiagnosticInput, context: OperationToolContext) -> dict[str, Any]:
    _check_score_sources(request, context)
    return run_diagnostic_tool(request, context, parse_bundle=parse_tcad_sources)


def _identity_context(sources: Mapping[str, bytes], *, admitting: bool = False):
    """Read admitted evidence for output comparisons, without re-admitting it."""
    descriptors = getattr(sources, "binding_descriptors", None)
    if descriptors is None or set(descriptors) != set(sources):
        raise RunCheckerError("TCAD analysis requires exact input binding descriptors")
    plan = parse_bound_json(ExperimentPortfolio, sources["experiment_plan"],
        admission_port="experiment_plan" if admitting else None)
    package = parse_bound_json(ReviewedDeckPackage, sources["reviewed_package"],
        admission_port="reviewed_package" if admitting else None)
    manifest = parse_bound_json(TCADRuntimeManifest, sources["runtime_manifest"],
        admission_port="runtime_manifest" if admitting else None)
    expected = {output.name: output for output in package.project.expected_outputs}
    known = {alias: expected.get(descriptor.output_name) for alias, descriptor in descriptors.items()
             if descriptor.port_name in {"solver_outputs", "tool_evidence"} and descriptor.output_name}
    return plan, package, manifest, descriptors, known


def _recovery_records(sources):
    records = []
    for alias in ('recovery_manifest', 'tool_recovery_manifest'):
        if alias in sources:
            value = json.loads(sources[alias])
            if value.get('schema_version') != 1 or not isinstance(value.get('records'), list) or len(value['records']) > 32:
                raise ValueError('recovery manifest shape')
            records.extend(value['records'])
    return records


def _recovered_record(descriptor, sources):
    return next((r for r in _recovery_records(sources) if r['artifact_ref'] == descriptor.artifact_ref.model_dump(mode='json')), None)


def validate_analysis_inputs(sources: Mapping[str, bytes]) -> None:
    """Deterministic input premises, invoked only before a Run is created."""
    from scidiscovery.operations.input_validation import prior_analysis_sources
    prior_analysis_sources(sources)
    for port, model in (("experiment_plan", ExperimentPortfolio), ("experiment_review", ScientificReview)):
        parsed = parse_bound_json(model, sources[port], admission_port=port)
        if port == "experiment_review":
            if parsed.review_target != "experiment_portfolio":
                raise OperationInvocationError("input_review_target_mismatch", port=port, field="/review_target")
            if parsed.verdict != "pass":
                raise OperationInvocationError("input_review_verdict_mismatch", port=port, field="/verdict")
    plan, package, manifest, descriptors, _ = _identity_context(sources, admitting=True)
    records = {record.name: record for record in manifest.outputs}
    expected = {output.name: output for output in package.project.expected_outputs}
    cases = {(proposal.experiment_key, case.case_key) for proposal in plan.proposals for case in proposal.cases}
    for output in expected.values():
        if output.case_key is not None and (output.experiment_key, output.case_key) not in cases:
            raise OperationInvocationError("input_package_case_unknown", port="reviewed_package", field="expected_outputs")
    for descriptor in descriptors.values():
        if descriptor.port_name not in {"solver_outputs", "tool_evidence"}:
            continue
        recovered = _recovered_record(descriptor, sources)
        if recovered is not None:
            original = descriptors.get('execution_result')
            declaration = expected.get(recovered['metadata'].get('output_name'))
            if recovered['metadata'].get('output_name') is None:
                if (original is None or recovered['source_ref'] != original.artifact_ref.model_dump(mode='json')
                        or descriptor.output_name is not None or recovered['size_bytes'] != descriptor.size_bytes
                        or recovered['media_type'] != descriptor.media_type):
                    raise OperationInvocationError('input_recovery_origin_mismatch', port='recovery_manifest')
                continue
            if original is None or recovered['source_ref'] != original.artifact_ref.model_dump(mode='json') or declaration is None:
                raise OperationInvocationError('input_recovery_origin_mismatch', port='recovery_manifest')
            if declaration.relative_path != recovered['metadata'].get('declared_path') or declaration.name != descriptor.output_name or recovered['size_bytes'] != descriptor.size_bytes or recovered['media_type'] != descriptor.media_type or (declaration.experiment_key, declaration.case_key) != (recovered['metadata'].get('experiment_key'), recovered['metadata'].get('case_key')):
                raise OperationInvocationError('input_recovery_output_mismatch', port='recovery_manifest')
            continue
        record = records.get(descriptor.output_name)
        if record is None or (record.media_type, record.size_bytes, record.sha256) != (
            descriptor.media_type, descriptor.size_bytes, descriptor.sha256
        ):
            raise OperationInvocationError("input_manifest_output_mismatch", port="solver_outputs")
        declaration = expected.get(record.name)
        if declaration is not None and (declaration.relative_path != record.relative_path
                or declaration.media_type != record.media_type):
            raise OperationInvocationError("input_project_output_mismatch", port="runtime_manifest", field="outputs")


def resolve_case_mapping(plan, package, descriptors, reference):
    """Check source identity and explicit scientific mapping, without inventing it."""
    alias = reference.input_alias if hasattr(reference, "input_alias") else reference["input_alias"]
    values = reference.model_dump(mode="json") if hasattr(reference, "model_dump") else reference
    if alias not in descriptors:
        raise declared_violation("analysis source is not a bound input")
    descriptor = descriptors[alias]
    if descriptor.port_name not in {"solver_outputs", "tool_evidence"} or descriptor.output_name is None:
        if values.get("output_name") is not None:
            raise declared_violation("non-solver evidence cannot claim a registered solver output identity")
        return
    if values.get("output_name") is not None and values["output_name"] != descriptor.output_name:
        raise declared_violation("analysis output name differs from exact bound output")
    if values.get("case_key") is not None:
        declaration = next((o for o in package.project.expected_outputs if o.name == descriptor.output_name), None)
        experiment_key = values.get("experiment_key")
        if experiment_key is None and declaration is not None:
            experiment_key = declaration.experiment_key
        pair = (experiment_key, values["case_key"])
        cases = {(p.experiment_key, c.case_key) for p in plan.proposals for c in p.cases}
        if pair not in cases:
            raise declared_violation("analysis case is not present in the bound plan")
        basis = values.get("case_mapping_basis")
        if declaration is not None and declaration.case_key is not None:
            if pair != (declaration.experiment_key, declaration.case_key):
                raise declared_violation("analysis case differs from explicit project output case")
        elif not basis or basis.get("kind") != "evidence" or not basis.get("evidence_refs"):
            raise declared_violation("undeclared case mapping requires explicit source evidence")
        if basis:
            for item in basis.get("evidence_refs", ()):
                if item["input_alias"] not in descriptors:
                    raise declared_violation("case mapping basis references an unbound source")
        return pair


def analysis_context(payload: dict[str, Any], sources: Mapping[str, bytes], handoff: dict[str, Any]) -> None:
    del handoff
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(payload), strict=True)
    plan, package, manifest, descriptors, known = _identity_context(sources)
    if report.study_kind != plan.study_kind or not any(
        validation.plan_key == report.plan_key and validation.experiment_key == report.experiment_key
        for validation in plan.validation_plans
    ):
        raise declared_violation("analysis does not identify the exact bound plan")
    references = {reference.source_key: reference for reference in report.source_references}
    if len(references) != len(report.source_references):
        raise declared_violation("analysis source references must be unique")
    evidence_keys = {evidence.source_key for evidence in report.evidence}
    if set(references) - evidence_keys:
        raise declared_violation("analysis source reference lacks matching evidence")
    for reference in references.values():
        resolve_case_mapping(plan, package, descriptors, reference)
    records = {record.record_key: record for record in report.calculation_records}
    for evidence in report.evidence:
        if evidence.locator.startswith("calculation_records:"):
            if evidence.locator.split(":", 1)[1] not in records:
                raise declared_violation("calculation evidence references an unknown record")
            continue
        reference = references.get(evidence.source_key)
        alias = reference.input_alias if reference is not None else evidence.locator.split(":", 1)[0]
        if alias not in descriptors or not (
            evidence.locator == alias or evidence.locator.startswith(alias + ":")
        ):
            raise declared_violation("TCAD evidence requires a bound input alias with an optional local locator", path="$.evidence")
    calculations = analysis_calculations(report, sources)
    for record in calculations:
        from scidiscovery.artifact_agent.service.tool_evidence import calculation_sources
        calculation_sources(record, sources)
    validate_analysis_report(report, plan, calculations=calculations)

PROMPT = OPERATION_AGENT_PREAMBLE + """Analyze this exact TCAD execution in one Run.
Optionally use worker_tcad_inspect_outputs and worker_tcad_accept_output with the bound execution_result to inspect and collect original terminal products. These tools cannot run a solver or edit files. Missing services or ambiguous correspondence permit a limited report. State mapping reasons; a successful collection is not scientific success. Tool-returned evidence aliases and the updated schema/result.schema.json may be used in source_references and scoring in this same Run. Tool evidence includes recovered original files and identified analysis derivatives; it does not change startup inputs. Up to 32 evidence files, 32 MiB each, 256 MiB total, 120s I/O within the Run budget. A declaration/source correction goes back to author; do not alter the scientific task. Old aggregate 97 does not establish solver success: use explicit solver status when present and cite actual step evidence and uncertainty when absent.
Return LayeredDiagnosisReport in the declared RoleResultEnvelope. Read bound raw
files and logs; scoring is optional. The diagnostics port contains controlled runner
logs; solver_outputs contains manifest-declared products. Diagnostics may support
execution diagnosis but must not be represented as registered solver products. A failed/cancelled execution or missing
outputs may yield invalid_study or limited inconclusive analysis. Preserve the
plan's scientific tests, deferred goals, method changes and conclusion limits.
For every raw evidence item, locator is its input alias, optionally followed by
":" and a position within that source (for example a log line range). Source identity
comes from the bound input; source_references is optional for additional scientific
case correspondence. Explicit output_name and experiment_key/case_key must agree
with the bound project. If a case is not
declared, you may propose case_mapping_basis(kind=evidence, evidence_refs of exact
input_alias/locator, rationale) where you first make that scientific mapping.
Calculation evidence cites the returned record; do not duplicate its source mapping
in source_references. Cite the plan/source/log correspondence and explain the conditional
conclusion; this does not independently establish scientific sufficiency. Original
declared cases cannot be overridden. Global logs need no single case mapping.
Do not infer case from filenames or matching bytes. A calculation evidence item
uses the returned calculation_ref as locator and a scientific source_key of your
choice. Unsupported/error records are limits,
not evidence of success. Never claim an unbound output was read.
Optionally call worker_tcad_curve_score with record_key and request containing
comparison_spec and sources. Each source mapping supplies input_alias, format,
series_key, case_key, role, x_axis and y_axis. PLX mappings additionally require
explicit dataset_name; output_name and experiment_key need not repeat an identity
already declared by the bound project. Log mappings use format sprocess_log. CSV mappings use format csv
and explicit x_column/y_column. Formats sprocess_plx and sprocess_log use the
existing TCAD parsers; no curve contract or prebound bundle is needed. Cite the
returned calculation_ref as an evidence locator; control saves the full record,
attempt and diagnostics. Do not copy them into calculation_records. For a rejected
request, cite tool_recovery_manifest and explain its actual error; it does not
establish an unsupported data format or require a manually written calculation record.
Use current input aliases for new calls. assignment.json prior_source_bindings
maps old aliases for reference; it never adds old aliases to the current namespace.
For historical calculations, bind prior_analysis and its own manifest. If that
manifest is also the original recovery_manifest, bind it once there; otherwise
use prior_analysis_manifest and recovery_manifest separately. Cite the saved
calculation file's current alias; control handles the historical receipt.
Preserved files from a failed Run remain engineering history, not a new computation.
Match each operator
validation_check_key to the exact selected plan check; document any changed method
and resulting conclusion limits in analysis_method and method_changes. Submission verifies
the controlled calculation receipt and exact output references; it does not rerun scoring.
Do not use unavailable quantitative comparisons as successful objective evidence.
""" + DIAGNOSTIC_GUIDANCE.format(diagnostic_tool="worker_tcad_curve_diagnose") + ANALYSIS_FILES_GUIDANCE
SEMANTIC_CONTRACT = scientific_semantic_contract(
    "tcad.result_analysis", "Scoring is optional and occurs after execution.",
    context_constraint="The report must identify the bound plan and use exact input aliases for solver claims. Calculation records must match their controlled receipts or exact sealed historical records; no repeated source mapping or scoring is required at submission. Missing products and failed execution limit claims, not submission of a limited report.",
)
DIAGNOSIS_AGENT = Components.diagnosis_agent
DIAGNOSIS_VALIDATOR = Components.diagnosis_validator
GUARD = CallableComponent("guard", analysis_parentage)
CONTEXT = CallableComponent("validator", analysis_context)
INPUT_VALIDATOR = CallableComponent("validator", validate_analysis_inputs)
TOOL = WorkerToolDefinition(
    name="worker_tcad_curve_score", description="Optionally parse bound TCAD PLX/log and explicit CSV columns, then score in this analysis Run. Cite calculation_ref; control saves the record and receipt.",
    input_model=TCADScoreInput, capability="tcad.analysis.curve_score", contextual_handler=tcad_score_tool, record_attempts=True,
    evidence_ports=("tool_evidence", "recovery_manifest_output"),
)
DIAGNOSTIC_TOOL = WorkerToolDefinition(
    name="worker_tcad_curve_diagnose",
    description="Optionally localize one residual comparison from bound PLX/log/CSV sources. Cite record.calculation_ref; full details (<=4 MiB) and images have saved evidence aliases and task-local paths. One operator, 2-257 samples; no curve contract or additional Run.",
    input_model=TCADDiagnosticInput, capability="tcad.analysis.curve_diagnose",
    contextual_handler=tcad_diagnostic_tool, record_attempts=True,
    evidence_ports=("tool_evidence", "recovery_manifest_output"),
)


def _ref(name: str, plugin: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin)


def _input(name: str, schema: str, resource: ComponentRef, *, count: int = 1,
           optional: bool = False, max_bytes: int, inventory: bool = False,
           exposure: str = "full") -> InputPortSpec:
    return InputPortSpec(
        name=name, description=f"Exact bound TCAD analysis {name}.", schema=schema,
        media_types=("*/*",) if inventory else ("application/json",),
        codec=_ref("opaque_codec" if inventory else "json_codec", "general_science"),
        schema_resource=_ref("wildcard_schema", "general_science") if inventory else resource, min_items=0 if optional else 1, max_items=count,
        max_item_bytes=max_bytes, exposure=exposure,
        usage="evidence_inventory" if inventory else "prior_signal",
    )


INPUTS = (
    _input("execution_result", "scidiscovery.execution-result", _ref("analysis_execution_schema"), optional=True, max_bytes=2*1024*1024).model_copy(update={"usage":"evidence_inventory"}),
    _input("recovery_manifest", "scidiscovery.tool-evidence-manifest.v1", _ref("analysis_recovery_schema"), optional=True, max_bytes=1024*1024).model_copy(update={"usage":"evidence_inventory"}),
    _input("prior_analysis", "scidiscovery.layered-diagnosis.v1", _ref("diagnosis_schema", "curve_score"), optional=True, max_bytes=128*1024).model_copy(update={"usage":"evidence_inventory", "description":"Optional exact prior analysis. Bind its own same-producer manifest as prior_analysis_manifest, or bind recovery_manifest once when that same manifest proves both roles."}),
    _input("prior_analysis_manifest", "scidiscovery.tool-evidence-manifest.v1", _ref("analysis_recovery_schema"), optional=True, max_bytes=1024*1024).model_copy(update={"usage":"evidence_inventory", "description":"Same-producer direct manifest parent of prior_analysis. A wrong explicit pair is rejected; use recovery_manifest alone when both purposes use the identical artifact. Bind every reused raw source separately."}),
    _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", "general_science"), max_bytes=2*1024*1024).model_copy(update={"usage": "evidence_inventory"}),
    _input("experiment_review", "scidiscovery.scientific-review.v1", _ref("scientific_review_schema", "general_science"), max_bytes=64*1024, exposure="on_demand").model_copy(update={"usage": "evidence_inventory"}),
    _input("reviewed_package", "tcad.reviewed-deck-package.v2", _ref("reviewed_package_schema"), max_bytes=64*1024*1024),
    _input("runtime_manifest", "opaque", _ref("opaque_schema", "general_science"), max_bytes=4*1024*1024),
    _input("runtime_attestation", "tcad.runtime-attestation.v1", _ref("runtime_attestation_schema"), optional=True, max_bytes=4*1024*1024),
    _input("solver_outputs", "*", _ref("opaque_schema", "general_science"), optional=True, count=32, max_bytes=32*1024*1024, inventory=True, exposure="on_demand"),
    _input("diagnostics", "*", _ref("opaque_schema", "general_science"), optional=True, max_bytes=32*1024*1024, inventory=True, exposure="on_demand"),
    _input("reference_material", "*", _ref("opaque_schema", "general_science"), optional=True, count=8, max_bytes=16*1024*1024, inventory=True, exposure="on_demand"),
    _input("current_progress", "*", _ref("opaque_schema", "general_science"), optional=True, count=4, max_bytes=2*1024*1024, inventory=True, exposure="on_demand"),
)
COMPONENT_SPECS = (
    ComponentSpec("analysis_execution_schema", "resource", "tcad_artifact.output_recovery:EXECUTION_SCHEMA"),
    ComponentSpec("analysis_recovery_schema", "resource", "tcad_artifact.output_recovery:RECOVERY_SCHEMA"),
    ComponentSpec("analysis_inspect_tool", "worker_tool", "tcad_artifact.output_recovery:INSPECT_TOOL", configuration_identity="tcad.analysis.inspect.v1"),
    ComponentSpec("analysis_accept_tool", "worker_tool", "tcad_artifact.output_recovery:ACCEPT_TOOL", configuration_identity="tcad.analysis.accept.v1"),
    ComponentSpec("result_analysis_agent", "agent", "tcad_artifact.result_analysis:DIAGNOSIS_AGENT"),
    ComponentSpec("result_analysis_validator", "validator", "tcad_artifact.result_analysis:DIAGNOSIS_VALIDATOR", resources=(_ref("result_analysis_semantic"),)),
    ComponentSpec("result_analysis_prompt", "resource", "tcad_artifact.result_analysis:PROMPT"),
    ComponentSpec("result_analysis_semantic", "resource", "tcad_artifact.result_analysis:SEMANTIC_CONTRACT"),
    ComponentSpec("result_analysis_parentage", "guard", "tcad_artifact.result_analysis:GUARD", configuration_identity="tcad.analysis.exact-parentage.v4"),
    ComponentSpec("result_analysis_input", "validator", "tcad_artifact.result_analysis:INPUT_VALIDATOR", configuration_identity="tcad.analysis.input-binding.v3"),
    ComponentSpec("result_analysis_context", "validator", "tcad_artifact.result_analysis:CONTEXT", resources=(_ref("result_analysis_semantic"),), configuration_identity="tcad.analysis.receipt-integrity.v1"),
    ComponentSpec("result_analysis_score_tool", "worker_tool", "tcad_artifact.result_analysis:TOOL", configuration_identity="tcad.analysis.raw-score.v1"),
    ComponentSpec("result_analysis_diagnostic_tool", "worker_tool", "tcad_artifact.result_analysis:DIAGNOSTIC_TOOL"),
)
OPERATIONS = (scientific_agent_operation(
    "tcad.result.analyze.v1", "Analyze one exact TCAD execution with optional raw-output scoring.",
    "An exact reviewed plan, package and terminal execution manifest exist, including failed runs.",
    "Solver execution, mandatory pre-experiment curve contracts, or changing raw evidence.",
    agent=_ref("result_analysis_agent"), workspace=_ref("workspace", "general_science"),
    prompt=_ref("result_analysis_prompt"), tools=(*BASE_TOOLS, _ref("result_analysis_score_tool"), _ref("result_analysis_diagnostic_tool"), _ref("analysis_files_tool", "curve_score"), _ref("analysis_inspect_tool"), _ref("analysis_accept_tool")),
    native_view_image=True,
    input_validation=InputValidationSpec(validator=_ref("result_analysis_input"),
        rule_id="tcad.result_analysis.input_binding",
        description="Before creating a Run, bind a structurally valid historical plan and its exact completed science.object.review.v1 scientific_review output, with matching plan parent and passing experiment_portfolio verdict; history grants no current authoring or execution authority. Original solver outputs must match manifest names/media/bytes and declared project paths/cases. Recovered solver outputs instead require the explicitly bound sealed recovery_manifest and execution_result, with exact receipt membership, original execution/project, declared output/case, actual path and byte identity. Same-Run registered tool evidence is admitted by the tool, not by submission. Bind the additional controlled tcad_log to diagnostics, not solver_outputs; diagnostics must share the exact execution lineage. Missing execution products permit limited analysis."),
    inputs=INPUTS, outputs=(OutputPortSpec(
        name="layered_diagnosis", description="Sealed bounded result analysis and optional replayable calculations.",
        schema="scidiscovery.layered-diagnosis.v1", media_types=("application/json",),
        codec=_ref("json_codec", "general_science"), schema_resource=_ref("diagnosis_schema", "curve_score"),
        kind="layered_diagnosis", validator=_ref("result_analysis_validator"),
        context_validator=_ref("result_analysis_context"),
        context_sources=tuple(port.name for port in INPUTS if port.exposure != "handoff_only") + ("tool_evidence", "recovery_manifest_output"),
        max_item_bytes=128*1024, semantic_contract=_ref("result_analysis_semantic"),
        validator_rule_id="tcad.result_analysis.payload_consistency",
        context_rule_id="tcad.result_analysis.context_binding",
    ), OutputPortSpec(name='tool_evidence', description='Tool-retained original runtime files, calculation records and declared analysis derivatives.', schema='opaque', media_types=('*/*',), codec=_ref('opaque_codec','general_science'), schema_resource=_ref('opaque_schema','general_science'), kind='tool_evidence', min_items=0, max_items=32, max_item_bytes=32*1024*1024, collection=CollectionSpec(max_total_bytes=256*1024*1024)),
    OutputPortSpec(name='recovery_manifest_output', description='Service-generated immutable evidence receipts and source mappings.', schema='scidiscovery.tool-evidence-manifest.v1',media_types=('application/json',),codec=_ref('json_codec','general_science'),schema_resource=_ref('analysis_recovery_schema'),kind='tool_evidence_manifest',min_items=0,max_items=1,max_item_bytes=1024*1024,collection=CollectionSpec(max_total_bytes=1024*1024))), guards=(_ref("result_analysis_parentage"),), timeout=900, max_attempts=2,
    max_input_bytes=512*1024*1024, max_output_bytes=257*1024*1024+128*1024, max_files=34,
),)
