"""TCAD result analysis with optional, same-Run raw-output curve scoring."""
from __future__ import annotations
from scidiscovery.operations.spec import InputDerivationSpec

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
    CHECKPOINT_DESCRIPTION,
    DIAGNOSTIC_GUIDANCE, DiagnosticComparisonSpec,
    run_diagnostic_tool,
)
from curve_score.science_operations import BASE_TOOLS, Components, validate_analysis_report
from curve_score.analysis_files import GUIDANCE as ANALYSIS_FILES_GUIDANCE
from scidiscovery.plugin_runtime.calculations import analysis_evidence_aliases
from scidiscovery.plugin_runtime.evidence import read_evidence_records
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import Identifier, canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
from scidiscovery.artifact_agent.schema.layered_diagnosis import CaseMappingBasis, LayeredDiagnosisReport
from scidiscovery.plugin_runtime.calculations import CalculationResult as CalculationRecord
from scidiscovery.plugin_runtime.diagnostics import RunCheckerError
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
from .project_packager import DeckReviewReport, ExecutionPackage, TCADRuntimeManifest
from .analysis_bindings import source_bindings, JSON_PORTS


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
    def reject(port, message):
        raise OperationInvocationError("guard_rejected", port=port, message=message)

    if parameters:
        reject(None, "TCAD analysis declares no operation parameters.")
    grouped: dict[str, list[Any]] = {}
    for item in inputs:
        grouped.setdefault(item.port_name, []).append(item.artifact)
    if any(len(grouped.get(name, ())) != 1 for name in ("execution_package", "runtime_manifest")):
        reject(None, "Bind exactly one execution_package and runtime_manifest.")
    package, manifest = (grouped[name][0] for name in ("execution_package", "runtime_manifest"))
    if package.ref not in manifest.parent_refs:
        reject("runtime_manifest", "runtime_manifest must have the exact execution_package parent.")
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
        reject("diagnostics", "diagnostics must be text/plain tcad_log with the same execution_id and parent refs as runtime_manifest.")
    outputs = grouped.get("solver_outputs", ())
    recovered = grouped.get('prior_analysis_manifest', ())
    execution = grouped.get('execution_result', ())
    if execution and (package.ref not in execution[0].parent_refs or manifest.ref not in execution[0].parent_refs):
        reject("execution_result", "execution_result must have the exact execution_package and runtime_manifest parents.")
    if recovered and (not execution or recovered[0].handoff_verdict is None
            or execution[0].ref not in recovered[0].parent_refs or package.ref not in recovered[0].parent_refs
            or dict(recovered[0].labels).get('operation_output_port') != 'recovery_manifest_output'):
        reject("recovery_manifest", "recovery_manifest must be a sealed recovery_manifest_output with the exact execution_result and execution_package parents.")
    direct = [output for output in outputs if output.parent_refs == manifest.parent_refs]
    for output in outputs:
        if output in direct:
            continue
        if not recovered or output.ref not in recovered[0].parent_refs:
            reject("solver_outputs", "Each solver output must share runtime_manifest parents or be an exact parent of the exact prior-analysis receipt.")
    if not all(
        package.ref in audit.parent_refs and manifest.ref in audit.parent_refs
        and all(output.ref in audit.parent_refs for output in direct)
        for audit in grouped.get("runtime_attestation", ())
    ):
        reject("runtime_attestation", "runtime_attestation must cover the exact execution_package, runtime_manifest and direct solver outputs.")
    return True


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
    from scidiscovery.operations.input_validation import ValidationSources
    package = parse_bound_json(ExecutionPackage, context.read_input("execution_package"))
    plan = package.project.execution_plan or parse_bound_json(ExperimentPortfolio, context.read_input("experiment_plan"))
    history = None
    for index, source in enumerate(request.request.sources):
        aliases = [source.input_alias]
        basis = source.case_mapping_basis
        field = "input_alias"
        try:
            descriptors = {source.input_alias: context.source_descriptor(source.input_alias)}
            if basis:
                for j, item in enumerate(basis.evidence_refs):
                    field = f"case_mapping_basis.evidence_refs[{j}].input_alias"
                    context.read_evidence(item.input_alias)
                    aliases.append(item.input_alias)
                    descriptors[item.input_alias] = context.source_descriptor(item.input_alias)
        except ValueError as error:
            raise DiagnosticError("mapping source is unavailable", details=(contract_diagnostic(
                "source_unavailable", phase="tool_execution", affected_action="tool_call",
                repairable=True, path=f"$.request.sources[{index}].{field}",
                message="The source or mapping evidence alias is not available in this Run."),)) from error
        declaration = next((o for o in package.project.expected_outputs
            if o.name == descriptors[source.input_alias].output_name), None)
        if (basis is None and getattr(source, "case_key", None) is not None
                and descriptors[source.input_alias].port_name in {"solver_outputs", "tool_evidence"}
                and (declaration is None or declaration.case_key is None)):
            if history is None:
                # These single-item ports have their compiled port names as aliases.
                # Only read historical premises when a selected case actually needs them.
                mapped = context.prior_source_bindings
                all_descriptors = dict(descriptors)
                for alias in set(mapped.values()) | JSON_PORTS:
                    try:
                        all_descriptors[alias] = context.source_descriptor(alias)
                    except ValueError:
                        continue  # Optional port is not bound.
                contents = {alias: context.read_input(alias) for alias, descriptor in all_descriptors.items()
                    if descriptor.port_name in JSON_PORTS}
                history = source_bindings(ValidationSources(contents, all_descriptors))
            known = history["sources"].get(source.input_alias, {})
            for item in (known.get("case_mapping_basis") or {}).get("evidence_refs", ()):
                context.read_evidence(item["input_alias"])
                descriptors[item["input_alias"]] = context.source_descriptor(item["input_alias"])
        else:
            known = {}
        try:
            resolve_case_mapping(plan, package, descriptors, source, known=known)
        except SemanticRuleViolation as error:
            detail = error.details[0]
            raise DiagnosticError("case mapping is not established", details=(contract_diagnostic(
                "case_mapping_invalid", phase="tool_execution", affected_action="tool_call",
                repairable=True, path=f"$.request.sources[{index}]" + detail["path"][1:],
                message=detail["message"]),)) from error


def tcad_score_tool(request: TCADScoreInput, context: OperationToolContext) -> dict[str, Any]:
    _check_score_sources(request, context)
    return run_score_tool(request, context, evaluate_tcad_request)


class TCADDiagnosticRequest(TCADScoreRequest):
    comparison_spec: DiagnosticComparisonSpec


class TCADDiagnosticInput(TCADScoreInput):
    request: TCADDiagnosticRequest
    checkpoint_alias: Annotated[str | None, Field(min_length=1, description=CHECKPOINT_DESCRIPTION)] = None


def tcad_diagnostic_tool(request: TCADDiagnosticInput, context: OperationToolContext) -> dict[str, Any]:
    _check_score_sources(request, context)
    return run_diagnostic_tool(request, context, parse_bundle=parse_tcad_sources)


def _identity_context(sources: Mapping[str, bytes], *, admitting: bool = False):
    """Read admitted evidence for output comparisons, without re-admitting it."""
    descriptors = getattr(sources, "binding_descriptors", None)
    if descriptors is None or set(descriptors) != set(sources):
        raise RunCheckerError("TCAD analysis requires exact input binding descriptors")
    package = parse_bound_json(ExecutionPackage, sources["execution_package"],
        admission_port="execution_package" if admitting else None)
    plan = package.project.execution_plan or parse_bound_json(ExperimentPortfolio, sources["experiment_plan"],
        admission_port="experiment_plan" if admitting else None)
    manifest = parse_bound_json(TCADRuntimeManifest, sources["runtime_manifest"],
        admission_port="runtime_manifest" if admitting else None)
    expected = {output.name: output for output in package.project.expected_outputs}
    known = {alias: expected.get(descriptor.output_name) for alias, descriptor in descriptors.items()
             if descriptor.port_name in {"solver_outputs", "tool_evidence"} and descriptor.output_name}
    return plan, package, manifest, descriptors, known


def _recovery_records(sources):
    records = []
    for alias in ('prior_analysis_manifest', 'tool_recovery_manifest'):
        if alias in sources:
            records.extend(read_evidence_records(sources[alias]))
    return records


def _recovered_record(descriptor, sources):
    return next((r for r in _recovery_records(sources) if r['artifact_ref'] == descriptor.artifact_ref.model_dump(mode='json')), None)


def validate_analysis_inputs(sources: Mapping[str, bytes]) -> None:
    """Deterministic input premises, invoked only before a Run is created."""
    from scidiscovery.operations.input_validation import prior_analysis_sources
    prior_analysis_sources(sources)
    plan, package, manifest, descriptors, _ = _identity_context(sources, admitting=True)
    records = {record.name: record for record in manifest.outputs}
    expected = {output.name: output for output in package.project.expected_outputs}
    cases = {(proposal.experiment_key, case.case_key) for proposal in plan.proposals for case in proposal.cases}
    for output in expected.values():
        if output.case_key is not None and (output.experiment_key, output.case_key) not in cases:
            raise OperationInvocationError("input_package_case_unknown", port="execution_package", field="expected_outputs")
    for descriptor in descriptors.values():
        if descriptor.port_name not in {"solver_outputs", "tool_evidence"}:
            continue
        recovered = _recovered_record(descriptor, sources)
        if recovered is not None:
            original = descriptors.get('execution_result')
            declaration = expected.get(recovered['metadata'].get('output_name'))
            generated = records.get(recovered['metadata'].get('output_name'))
            if generated is not None and not (
                package.project.collect_generated_outputs
                and generated.name == "generated_" + hashlib.sha256(generated.relative_path.encode("utf-8")).hexdigest()
            ):
                generated = None
            if recovered['metadata'].get('output_name') is None:
                if (original is None or recovered['source_ref'] != original.artifact_ref.model_dump(mode='json')
                        or descriptor.output_name is not None or recovered['size_bytes'] != descriptor.size_bytes
                        or recovered['media_type'] != descriptor.media_type):
                    raise OperationInvocationError('input_recovery_origin_mismatch', port='recovery_manifest')
                continue
            if original is None or recovered['source_ref'] != original.artifact_ref.model_dump(mode='json') or (declaration is None and generated is None):
                raise OperationInvocationError('input_recovery_origin_mismatch', port='recovery_manifest')
            expected_path = declaration.relative_path if declaration is not None else generated.relative_path
            expected_name = declaration.name if declaration is not None else generated.name
            expected_case = (declaration.experiment_key, declaration.case_key) if declaration is not None else (None, None)
            if expected_path != recovered['metadata'].get('declared_path') or (declaration is None and expected_path != recovered['metadata'].get('relative_path')) or expected_name != descriptor.output_name or recovered['size_bytes'] != descriptor.size_bytes or recovered['media_type'] != descriptor.media_type or (declaration is None and (descriptor.sha256 != generated.sha256 or descriptor.size_bytes != generated.size_bytes)) or expected_case != (recovered['metadata'].get('experiment_key'), recovered['metadata'].get('case_key')):
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
        if declaration is None and not (
            package.project.collect_generated_outputs
            and record.name == "generated_" + hashlib.sha256(record.relative_path.encode("utf-8")).hexdigest()
        ):
            raise OperationInvocationError("input_project_output_mismatch", port="runtime_manifest", field="outputs")


def resolve_case_mapping(plan, package, descriptors, reference, *, known=None, path="$"):
    """Check explicit output claims against one shared conditional binding view."""
    values = reference.model_dump(mode="json") if hasattr(reference, "model_dump") else reference
    alias = values["input_alias"]
    known = known or {}
    def fail(message, field):
        raise declared_violation(message, path=path + "." + field)
    if alias not in descriptors:
        fail("analysis source is not a bound input", "input_alias")
    descriptor = descriptors[alias]
    if descriptor.port_name not in {"solver_outputs", "tool_evidence"} or descriptor.output_name is None:
        if values.get("output_name") is not None:
            fail("non-solver evidence cannot claim a registered solver output identity", "output_name")
        return
    if values.get("output_name") is not None and values["output_name"] != descriptor.output_name:
        fail("analysis output name differs from exact bound output", "output_name")
    if values.get("case_key") is None:
        return
    declaration = next((o for o in package.project.expected_outputs if o.name == descriptor.output_name), None)
    experiment_key = values.get("experiment_key")
    if experiment_key is None:
        experiment_key = declaration.experiment_key if declaration and declaration.case_key is not None else known.get("experiment_key")
    pair = (experiment_key, values["case_key"])
    cases = {(p.experiment_key, c.case_key) for p in plan.proposals for c in p.cases}
    if pair not in cases:
        fail("analysis case is not present in the bound plan", "case_key" if experiment_key else "experiment_key")
    basis = values.get("case_mapping_basis")
    if declaration is not None and declaration.case_key is not None:
        if pair != (declaration.experiment_key, declaration.case_key):
            fail("analysis case differs from explicit project output case", "case_key")
    else:
        if basis is None and pair == (known.get("experiment_key"), known.get("case_key")):
            basis = known.get("case_mapping_basis")
        if not basis or basis.get("kind") != "evidence" or not basis.get("evidence_refs"):
            fail("undeclared case mapping requires explicit source evidence", "case_mapping_basis")
    if basis:
        for index, item in enumerate(basis.get("evidence_refs", ())):
            if item["input_alias"] not in descriptors:
                fail("case mapping basis references an unbound source", f"case_mapping_basis.evidence_refs[{index}].input_alias")
    return pair


def analysis_context(payload: dict[str, Any], sources: Mapping[str, bytes], handoff: dict[str, Any]) -> None:
    del handoff
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(payload), strict=True)
    plan, package, manifest, descriptors, _ = _identity_context(sources)
    if report.study_kind != plan.study_kind:
        raise declared_violation("analysis study kind differs from the bound plan", path="$.study_kind")
    if not any(validation.plan_key == report.plan_key and validation.experiment_key == report.experiment_key
            for validation in plan.validation_plans):
        raise declared_violation("analysis does not identify the exact bound plan", path="$.plan_key")
    view = source_bindings(sources)
    references = {}
    for index, reference in enumerate(report.source_references):
        if reference.source_key in references and reference != references[reference.source_key]:
            raise declared_violation("analysis source key has conflicting source mappings", path=f"$.source_references[{index}].source_key")
        references[reference.source_key] = reference
        resolve_case_mapping(plan, package, descriptors, reference,
            known=view["sources"].get(reference.input_alias), path=f"$.source_references[{index}]")
    aliases = analysis_evidence_aliases(report.evidence, report.source_references, descriptors)
    for index, evidence in enumerate(report.evidence):
        alias = aliases[evidence.source_key]
        if alias not in descriptors:
            raise declared_violation("TCAD evidence requires a bound input alias with an optional local locator", path=f"$.evidence[{index}].locator")
    from scidiscovery.operation_contract import validate_evidence_source_aliases
    validate_evidence_source_aliases(payload,
        set(sources) | set(references) | {item.source_key for item in report.evidence})
    calculations = sources.verified_calculations(report)
    validate_analysis_report(report, plan, calculations=calculations)


PROMPT = OPERATION_AGENT_PREAMBLE + """Analyze this exact TCAD execution in one Run.
analysis-bindings.json indexes the project and scientific cases; follow its source
pointers for implementation details. The case_parameter_bindings ledger is not a
reading or reporting task. Return LayeredDiagnosisReport in RoleResultEnvelope.
Preserve planned tests, deferred goals, method changes and conclusion limits.

Read actual bound results: diagnostics are runner logs; solver_outputs are exact
manifested generated files or legacy declared products. Logs can explain execution
but cannot substitute for solver products.
Failed/cancelled execution or missing products permits invalid_study or bounded
inconclusive findings, not fabricated success. Old aggregate 97 is not solver success:
use explicit solver status and actual step evidence; state uncertainty when absent.
Use execution_package.project.execution_plan for skeleton execution, or the original bound experiment_plan for the detailed-plan branch, as the exact report scope. When an optional objective_assessment is supplied, it must use the plan’s exact
non-null objective_key; pass, fail, inconclusive, and not_evaluable remain scientific choices. When the
key is null, the assessment remains optional and must not be invented. next_action
remains optional Worker advice, not a scheduling command.

For terminal product recovery, worker_tcad_inspect_outputs and worker_tcad_accept_output
use bound execution_result. Read the selected tool's complete contract before use.
The selected recovery tool contract owns file, byte and I/O limits within the Run
budget. These tools collect originals; they never run a solver or edit files. Explain correspondence; collection is not scientific success.
Missing services or ambiguous correspondence allow limited analysis. New evidence
aliases and the refreshed schema/result.schema.json can be used immediately, without
changing frozen startup inputs. Declaration/source correction belongs to the author.

Cite bound aliases in evidence_keys, or as optional evidence.source_key with local
locators. Local scientific source_keys use source_references.input_alias or an
alias-prefixed locator; do not repeat a binding already established. source_references
is optional. Control fills declared identities and unambiguous prior mappings from
analysis-bindings.json; historical mappings remain conditional claims, not proof.
Do not infer cases from names/equal bytes, override declared cases, or require a case
for global logs. New ambiguous associations require scientific case_mapping_basis
(kind=evidence, exact input_alias/locator evidence_refs and rationale); do not repeat
existing basis tables. Explicit output_name and experiment_key/case_key must agree
with the project. Tool requests retain scientific case/series/axes choices; do not
copy already-known output/experiment/basis or duplicate calculation source mappings.
Never claim unread or unbound products were inspected.

worker_tcad_curve_score is optional. Read its exact contract for PLX, log or CSV
source selection, dataset/column names, axes and comparison_spec; no prebound curve
bundle/contract is needed. Match validation_check_key to the selected plan check;
record changed methods and their limits. Unavailable/error calculations limit the
quantitative claim, never support success. Receipt checks do not rerun calculations.
Use current scientific aliases only. Select the exact prior analysis to reuse its
calculations; control resolves original sources and sealed receipts automatically.
Files preserved from failed tasks remain engineering history, not newly completed
computations.
""" + DIAGNOSTIC_GUIDANCE.format(diagnostic_tool="worker_tcad_curve_diagnose") + ANALYSIS_FILES_GUIDANCE
SEMANTIC_CONTRACT = scientific_semantic_contract(
    "tcad.result_analysis", "Scoring is optional and occurs after execution.",
    context_constraint="The report must identify the exact plan embedded in execution_package or the original bound detailed experiment_plan and use exact input aliases for solver claims. When an optional objective_assessment is supplied, it must use that exact plan’s non-null objective_key; a null key does not require or authorize inventing an assessment identity. A source key must resolve to one bound input or calculation record. Cite the tool-returned calculation_ref; control resolves the registered scientific record and its private receipt. A bound input alias retains its identity even in an optional source mapping. Repeated citations and local locators are allowed; an explicit locator naming another bound input conflicts with that mapping. Calculation records must match their controlled receipts or exact sealed historical records; no repeated source mapping or scoring is required at submission. Missing products and failed execution limit claims, not submission of a limited report.",
)
DIAGNOSIS_AGENT = Components.diagnosis_agent
DIAGNOSIS_VALIDATOR = Components.diagnosis_validator
GUARD = CallableComponent("guard", analysis_parentage)
CONTEXT = CallableComponent("validator", analysis_context)
INPUT_VALIDATOR = CallableComponent("validator", validate_analysis_inputs)
TOOL = WorkerToolDefinition(
    name="worker_tcad_curve_score", description="Optionally parse bound TCAD PLX/log and explicit CSV columns, then score in this analysis Run. Returns compact metrics; read calculation_ref with the evidence reader for the scientific record. Cite calculation_ref; control saves the record and receipt.",
    input_model=TCADScoreInput, capability="tcad.analysis.curve_score", contextual_handler=tcad_score_tool, record_attempts=True,
    evidence_ports=("tool_evidence", "recovery_manifest_output"),
)
DIAGNOSTIC_TOOL = WorkerToolDefinition(
    name="worker_tcad_curve_diagnose",
    description="Optionally localize one residual comparison from bound PLX/log/CSV sources. Returns compact metrics; read record.calculation_ref with the evidence reader for the scientific record. Cite record.calculation_ref; numbers are checkpointed (<=4 MiB) before rendering. Use checkpoint_alias for a plot-only retry with unchanged request and exact sources; rendering failure preserves computed metrics. Full details (<=4 MiB) and images have saved evidence aliases and task-local paths. One operator, 2-257 samples; no curve contract or additional Run.",
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

    _input("prior_analysis", "scidiscovery.layered-diagnosis.v1", _ref("diagnosis_schema", "curve_score"), optional=True, max_bytes=128*1024).model_copy(update={"usage":"evidence_inventory", "description":"Optional exact prior analysis for original calculation reuse."}),
    _input("prior_analysis_manifest", "scidiscovery.tool-evidence-manifest.v1", _ref("tool_evidence_schema", "general_science"), optional=True, max_bytes=1024*1024).model_copy(update={"agent_visible":False,"derivation":InputDerivationSpec(anchor_port="prior_analysis", producer_output_port="recovery_manifest_output")}),
    _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", "general_science"), optional=True, max_bytes=2*1024*1024).model_copy(update={"usage": "evidence_inventory", "description": "Detailed-plan branch only: exact original plan parent of execution_package. Skeleton branch reads execution_package.project.execution_plan directly; omit this port. New analysis plans belong in current_progress."}),
    _input("execution_package", "tcad.execution-package.v2", _ref("execution_package_schema"), max_bytes=64*1024*1024),
    _input("runtime_manifest", "opaque", _ref("opaque_schema", "general_science"), max_bytes=4*1024*1024),
    _input("runtime_attestation", "tcad.runtime-attestation.v1", _ref("runtime_attestation_schema"), optional=True, max_bytes=4*1024*1024),
    _input("solver_outputs", "*", _ref("opaque_schema", "general_science"), optional=True, count=32, max_bytes=32*1024*1024, inventory=True, exposure="on_demand"),
    _input("diagnostics", "*", _ref("opaque_schema", "general_science"), optional=True, max_bytes=32*1024*1024, inventory=True, exposure="on_demand"),
    _input("reference_material", "*", _ref("opaque_schema", "general_science"), optional=True, count=8, max_bytes=16*1024*1024, inventory=True, exposure="on_demand"),
    _input("current_progress", "*", _ref("opaque_schema", "general_science"), optional=True, count=4, max_bytes=2*1024*1024, inventory=True, exposure="on_demand").model_copy(update={"description": "Relevant sealed progress, including any newer retrospective analysis plan and its matching review; these do not replace original execution identity."}),
)
COMPONENT_SPECS = (
    ComponentSpec("analysis_execution_schema", "resource", "tcad_artifact.output_recovery:EXECUTION_SCHEMA"),
    ComponentSpec("analysis_inspect_tool", "worker_tool", "tcad_artifact.output_recovery:INSPECT_TOOL", configuration_identity="tcad.analysis.inspect.v2:retained-list-summary"),
    ComponentSpec("analysis_accept_tool", "worker_tool", "tcad_artifact.output_recovery:ACCEPT_TOOL", configuration_identity="tcad.analysis.accept.v1"),
    ComponentSpec("tcad_analysis_workspace", "workspace", "tcad_artifact.analysis_bindings:WORKSPACE",
        resources=(_ref("tcad_analysis_materializer"), _ref("tcad_analysis_finalizer"), _ref("tcad_analysis_snapshotter"))),
    ComponentSpec("tcad_analysis_materializer", "workspace_materializer", "tcad_artifact.analysis_bindings:MATERIALIZER", configuration_identity="analysis.user-context-origin:v1"),
    ComponentSpec("tcad_analysis_finalizer", "workspace_finalizer", "tcad_artifact.analysis_bindings:FINALIZER"),
    ComponentSpec("tcad_analysis_snapshotter", "workspace_snapshotter", "tcad_artifact.analysis_bindings:SNAPSHOTTER"),
    ComponentSpec("result_analysis_agent", "agent", "tcad_artifact.result_analysis:DIAGNOSIS_AGENT"),
    ComponentSpec("result_analysis_validator", "validator", "tcad_artifact.result_analysis:DIAGNOSIS_VALIDATOR", resources=(_ref("result_analysis_semantic"),)),
    ComponentSpec("result_analysis_prompt", "resource", "tcad_artifact.result_analysis:PROMPT"),
    ComponentSpec("result_analysis_semantic", "resource", "tcad_artifact.result_analysis:SEMANTIC_CONTRACT"),
    ComponentSpec("result_analysis_parentage", "guard", "tcad_artifact.result_analysis:GUARD", configuration_identity="tcad.analysis.exact-parentage.v4"),
    ComponentSpec("result_analysis_input", "validator", "tcad_artifact.result_analysis:INPUT_VALIDATOR", configuration_identity="tcad.analysis.input-binding.v4"),
    ComponentSpec("result_analysis_context", "validator", "tcad_artifact.result_analysis:CONTEXT", resources=(_ref("result_analysis_semantic"),), configuration_identity="tcad.analysis.receipt-integrity.v2"),
    ComponentSpec("result_analysis_score_tool", "worker_tool", "tcad_artifact.result_analysis:TOOL", configuration_identity="analysis.response-summary:v2"),
    ComponentSpec("result_analysis_diagnostic_tool", "worker_tool", "tcad_artifact.result_analysis:DIAGNOSTIC_TOOL", configuration_identity="analysis.diagnostic-checkpoint:v4"),
)
OPERATIONS = (scientific_agent_operation(
    "tcad.result.analyze.v1", "Analyze one exact TCAD execution with optional raw-output scoring.",
    "An exact plan, execution package and terminal execution manifest exist, including failed runs.",
    "Solver execution, mandatory pre-experiment curve contracts, or changing raw evidence.",
    decision_fields=("overall_verdict", "claim_allowed", "summary", "next_action", "remaining_contradiction", "limitations"),
    agent=_ref("result_analysis_agent"), workspace=_ref("tcad_analysis_workspace"),
    prompt=_ref("result_analysis_prompt"), tools=(*BASE_TOOLS, _ref("result_analysis_score_tool"), _ref("result_analysis_diagnostic_tool"), _ref("analysis_files_tool", "curve_score"), _ref("analysis_inspect_tool"), _ref("analysis_accept_tool")),
    native_view_image=True,
    input_validation=InputValidationSpec(validator=_ref("result_analysis_input"),
        rule_id="tcad.result_analysis.input_binding",
        description="Use the exact implementation plan embedded in the execution package, or its bound historical detailed plan. Independent review is optional. Original solver outputs must match manifest names/media/bytes and declared project paths/cases. Recovered solver outputs instead require the automatically derived prior-analysis receipt and execution_result, with exact receipt membership, original execution/project, declared output/case, actual path and byte identity. Same-Run registered tool evidence is admitted by the tool, not by submission. Bind the additional controlled tcad_log to diagnostics, not solver_outputs; diagnostics must share the exact execution lineage. Missing execution products permit limited analysis."),
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
    OutputPortSpec(name='recovery_manifest_output', description='Service-generated immutable evidence receipts and source mappings.', schema='scidiscovery.tool-evidence-manifest.v1',media_types=('application/json',),codec=_ref('json_codec','general_science'),schema_resource=_ref('tool_evidence_schema', 'general_science'),kind='tool_evidence_manifest',min_items=0,max_items=1,max_item_bytes=1024*1024,collection=CollectionSpec(max_total_bytes=1024*1024))), guards=(_ref("result_analysis_parentage"),), timeout=900, max_attempts=2,
    max_input_bytes=512*1024*1024, max_output_bytes=257*1024*1024+128*1024, max_files=34,
).model_copy(update={"version": "2"}),)
