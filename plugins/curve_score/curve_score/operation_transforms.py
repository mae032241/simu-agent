"""Compiled Operation wrappers for retained deterministic curve capabilities."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ValidationError

from .schema import (
    CurveBundle,
    CurveConsistencyReport,
    CurveExperimentContract,
    CurveReferenceCoverageReport,
)
from .figure_evidence import (
    FigureEvidenceManifest,
    FigureEvidenceValidationReport,
)
from .figure_digitization import build_digitized_figure_bundle
from .objective import (
    ObjectiveCoverageReport,
)
from scidiscovery.operations.spec import (
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
)
from scidiscovery.operation_contract import SemanticRuleViolation
from .figure_evidence_normalizer import FIGURE_EVIDENCE_BUNDLE_PROFILE_V2
from .transform_adapter import (
    CURVE_SCORE_OPERATION,
    bundle_figure_evidence_outputs,
    curve_reference_coverage_outputs,
    objective_coverage_outputs,
    score_curve_bundle_outputs,
)


CURVE_REFERENCE_COVERAGE_OPERATION = "scidiscovery.curve-reference-coverage.v1"
OBJECTIVE_COVERAGE_OPERATION = "scidiscovery.objective-coverage.v1"


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _object_schema(schema_id: str) -> str:
    return json.dumps(
        {"$id": schema_id, "type": "object"},
        separators=(",", ":"),
        sort_keys=True,
    )


def _model_validator(model: type[BaseModel]) -> Callable[[bytes], None]:
    def validate(raw: bytes) -> None:
        try:
            model.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise SemanticRuleViolation(str(error)) from error

    return validate


def _json_object(raw: bytes) -> None:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("curve operation audit must be a JSON object")


def _png(raw: bytes) -> None:
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("curve comparison plot is not a PNG")


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"curve operation input {name} must contain one item")
    return items[0]


def _reference_inputs(raw_items: tuple[bytes, ...]) -> dict[str, bytes]:
    ordered = sorted((hashlib.sha256(raw).hexdigest(), raw) for raw in raw_items)
    digests = tuple(item[0] for item in ordered)
    if len(digests) != len(set(digests)):
        raise ValueError("reference curve bundles must have unique content")
    for _, raw in ordered:
        CurveBundle.model_validate_json(raw, strict=True)
    return {
        f"reference_curve__{index:03d}": raw
        for index, (_, raw) in enumerate(ordered, start=1)
    }


def score_curve_bundle(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    inputs = {
        "curve_bundle": _one(values, "curve_bundle"),
        "experiment_plan": _one(values, "experiment_plan"),
        "curve_contract": _one(values, "curve_contract"),
        **_reference_inputs(values.get("reference_bundles", ())),
    }
    return score_curve_bundle_outputs(inputs)


def bundle_figure_evidence(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    manifest_raw = _one(values, "figure_manifest")
    report_raw = _one(values, "validation_report")
    manifest = FigureEvidenceManifest.model_validate_json(manifest_raw, strict=True)
    report = FigureEvidenceValidationReport.model_validate_json(report_raw, strict=True)
    by_identity = {(item.panel_key, item.series_key): item for item in report.series}
    ordered = tuple(
        (panel.panel_key, series.series_key)
        for panel in manifest.panels
        for series in panel.series
    )
    tables = values.get("curve_tables", ())
    if len(tables) != len(ordered):
        raise ValueError("curve table collection differs from the figure manifest")
    inputs = {"figure_manifest": manifest_raw, "validation_report": report_raw}
    for identity, raw in zip(ordered, tables, strict=True):
        try:
            validation = by_identity[identity]
        except KeyError as error:
            raise ValueError("figure validation report omits a manifest series") from error
        if validation.csv_sha256 != hashlib.sha256(raw).hexdigest():
            raise ValueError("curve table order or digest differs from validation")
        panel_key, series_key = identity
        inputs[f"curve_table__{panel_key}__{series_key}"] = raw
    return bundle_figure_evidence_outputs(inputs)


def materialize_figure_evidence(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    if set(values) != {"paper_source", "figure_request"}:
        raise ValueError("figure materialization requires one source and one request")
    files, _ = build_digitized_figure_bundle(
        _one(values, "paper_source"), _one(values, "figure_request")
    )

    def items(prefix: str) -> tuple[bytes, ...]:
        return tuple(
            content
            for name, (content, _) in sorted(files.items())
            if name.startswith(prefix + "/")
        )

    result = {
        "figure_manifest": items("figure_manifest"),
        "source_panels": items("source_panels"),
        "audit_overlays": items("audit_overlays"),
        "curve_tables": items("curve_tables"),
        "validation_report": items("validation_reports"),
    }
    if len(result["figure_manifest"]) != 1 or len(result["validation_report"]) != 1:
        raise ValueError("figure materialization did not produce its singular records")
    return result


def reference_coverage(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    inputs = {
        "experiment_plan": _one(values, "experiment_plan"),
        "curve_contract": _one(values, "curve_contract"),
        **_reference_inputs(values.get("reference_bundles", ())),
    }
    return curve_reference_coverage_outputs(inputs)


def objective_coverage(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    inputs = {
        "objective": _one(values, "objective"),
        "experiment_plan": _one(values, "experiment_plan"),
        **_reference_inputs(values.get("reference_bundles", ())),
    }
    for index, raw in enumerate(values.get("curve_contracts", ()), start=1):
        inputs[f"curve_contract__{index:03d}"] = raw
    return objective_coverage_outputs(inputs)


def _group(inputs: tuple[Any, ...]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for item in inputs:
        grouped.setdefault(item.port_name, []).append(item)
    return grouped


def score_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    grouped = _group(inputs)
    bundle = grouped["curve_bundle"][0]
    return all(
        grouped[name][0].artifact.ref in bundle.artifact.parent_refs
        for name in ("curve_contract", "experiment_plan")
    )


def figure_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    grouped = _group(inputs)
    required = {
        "paper_source", "figure_request", "scientific_intake", "evidence_audit",
        "figure_manifest", "validation_report", "source_panels",
        "audit_overlays", "curve_tables",
    }
    if not required <= set(grouped) or any(
        len(grouped[name]) != 1
        for name in (
            "paper_source", "figure_request", "scientific_intake",
            "evidence_audit", "figure_manifest", "validation_report",
            "source_panels", "audit_overlays",
        )
    ):
        return False
    source = grouped["paper_source"][0]
    request = grouped["figure_request"][0]
    intake = grouped["scientific_intake"][0]
    audit = grouped["evidence_audit"][0]
    family = (
        grouped["figure_manifest"][0],
        grouped["validation_report"][0],
        *grouped["source_panels"],
        *grouped["audit_overlays"],
        *grouped["curve_tables"],
    )
    request_labels = dict(request.artifact.labels)
    if (
        source.artifact.ref not in request.artifact.parent_refs
        or not request_labels.get("operation_invocation_fingerprint")
        or request_labels.get("operation_output_port") != "figure_request"
    ):
        return False
    fingerprints = {
        dict(item.artifact.labels).get("operation_invocation_fingerprint")
        for item in family
    }
    if len(fingerprints) != 1 or None in fingerprints:
        return False
    if any(
        dict(item.artifact.labels).get("operation_id")
        != "science.figure.evidence.materialize.v1"
        or item.artifact.parent_refs != (source.artifact.ref, request.artifact.ref)
        for item in family
    ):
        return False
    family_refs = tuple(item.artifact.ref for item in family)
    expected_intake_parents = {
        source.artifact.ref, request.artifact.ref, *family_refs
    }
    intake_labels = dict(intake.artifact.labels)
    audit_labels = dict(audit.artifact.labels)
    return bool(
        intake_labels.get("operation_output_port") == "scientific_intake"
        and expected_intake_parents <= set(intake.artifact.parent_refs)
        and audit_labels.get("operation_id") == "science.figure.evidence.audit.v1"
        and audit_labels.get("operation_output_port") == "evidence_audit"
        and {intake.artifact.ref, *expected_intake_parents}
        <= set(audit.artifact.parent_refs)
        and audit.artifact.handoff_verdict == "pass"
    )


def objective_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    grouped = _group(inputs)
    plan = grouped["experiment_plan"][0]
    return bool(
        grouped["objective"][0].artifact.ref in plan.artifact.parent_refs
        and all(
            plan.artifact.ref in item.artifact.parent_refs
            for item in grouped.get("curve_contracts", ())
        )
    )


SCORE_CURVE_BUNDLE = CallableComponent("transform", score_curve_bundle)
BUNDLE_FIGURE_EVIDENCE = CallableComponent("transform", bundle_figure_evidence)
MATERIALIZE_FIGURE_EVIDENCE = CallableComponent(
    "transform", materialize_figure_evidence
)
REFERENCE_COVERAGE = CallableComponent("transform", reference_coverage)
OBJECTIVE_COVERAGE = CallableComponent("transform", objective_coverage)
SCORE_PARENTAGE = CallableComponent("guard", score_parentage)
FIGURE_PARENTAGE = CallableComponent("guard", figure_parentage)
OBJECTIVE_PARENTAGE = CallableComponent("guard", objective_parentage)
CURVE_BUNDLE_VALIDATOR = CallableComponent("validator", _model_validator(CurveBundle))
CURVE_CONTRACT_VALIDATOR = CallableComponent(
    "validator", _model_validator(CurveExperimentContract)
)
METRIC_REPORT_VALIDATOR = CallableComponent(
    "validator", _model_validator(CurveConsistencyReport)
)
REFERENCE_COVERAGE_VALIDATOR = CallableComponent(
    "validator", _model_validator(CurveReferenceCoverageReport)
)
OBJECTIVE_COVERAGE_VALIDATOR = CallableComponent(
    "validator", _model_validator(ObjectiveCoverageReport)
)
AUDIT_VALIDATOR = CallableComponent("validator", _json_object)
PLOT_VALIDATOR = CallableComponent("validator", _png)
FIGURE_MANIFEST_VALIDATOR = CallableComponent(
    "validator", _model_validator(FigureEvidenceManifest)
)
FIGURE_REPORT_VALIDATOR = CallableComponent(
    "validator", _model_validator(FigureEvidenceValidationReport)
)
PNG_VALIDATOR = CallableComponent("validator", _png)


CURVE_BUNDLE_SCHEMA = _schema(CurveBundle, "scidiscovery.curve-bundle.v1")
CURVE_CONTRACT_SCHEMA = _schema(
    CurveExperimentContract, "scidiscovery.curve-experiment-contract.v1"
)
METRIC_REPORT_SCHEMA = _schema(
    CurveConsistencyReport, "scidiscovery.curve-consistency-report.v1"
)
FIGURE_MANIFEST_SCHEMA = _schema(
    FigureEvidenceManifest, "scidiscovery.figure-evidence-manifest.v1"
)
FIGURE_REPORT_SCHEMA = _schema(
    FigureEvidenceValidationReport,
    "scidiscovery.figure-evidence-validation-report.v1",
)
REFERENCE_COVERAGE_SCHEMA = _schema(
    CurveReferenceCoverageReport, "scidiscovery.curve-reference-coverage.v1"
)
OBJECTIVE_COVERAGE_SCHEMA = _schema(
    ObjectiveCoverageReport, "scidiscovery.objective-coverage.v1"
)
FIGURE_AUDIT_SCHEMA = _object_schema(
    "scidiscovery.figure-evidence-curve-normalization-audit.v1"
)
SCORE_AUDIT_SCHEMA = _object_schema("scidiscovery.curve-score-audit.v1")
PLOT_SCHEMA = json.dumps(
    {
        "$id": "scidiscovery.curve-comparison-plot.v1",
        "contentEncoding": "base64",
        "type": "string",
    },
    separators=(",", ":"),
    sort_keys=True,
)


def _ref(name: str, *, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)


def _input(
    name: str,
    schema: str,
    resource: str | ComponentRef,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 32 * 1024 * 1024,
    usage: str = "claim_evidence",
    media_types: tuple[str, ...] = ("application/json",),
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Exact immutable curve operation input: {name}.",
        schema=schema,
        media_types=media_types,
        codec=_ref(
            "json_codec" if media_types == ("application/json",) else "opaque_codec",
            plugin_id="general_science",
        ),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        usage=usage,
        exposure="full",
    )


def _review_input(
    name: str, *, min_items: int = 1, max_items: int = 1
) -> InputPortSpec:
    return _input(
        name,
        "scidiscovery.scientific-review.v1",
        _ref("scientific_review_schema", plugin_id="general_science"),
        min_items=min_items,
        max_items=max_items,
        max_bytes=64 * 1024,
        usage="prior_signal",
    )


def _output(
    name: str,
    kind: str,
    schema: str,
    resource: str | ComponentRef,
    validator: str | ComponentRef,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 32 * 1024 * 1024,
    media_type: str = "application/json",
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=f"Deterministic curve operation output: {name}.",
        schema=schema,
        media_types=(media_type,),
        codec=_ref(
            "json_codec" if media_type == "application/json" else "opaque_codec",
            plugin_id="general_science",
        ),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        kind=kind,
        validator=validator if isinstance(validator, ComponentRef) else _ref(validator),
    )


def _operation(
    operation_id: str,
    component: str,
    purpose: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    *,
    guards: tuple[str, ...] = (),
    max_input_bytes: int = 1024 * 1024 * 1024,
    max_output_bytes: int = 512 * 1024 * 1024,
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="support",
        description=OperationDescription(
            purpose=purpose,
            applies_when="The exact declared immutable curve inputs are available.",
            not_for="Selecting scientific targets, interpreting mechanisms, or executing a solver.",
        ),
        executor=ExecutorRef(kind="transform", component=_ref(component)),
        inputs=inputs,
        outputs=outputs,
        consequence="scientific",
        guards=tuple(_ref(name) for name in guards),
        limits=LimitsSpec(
            timeout_seconds=300,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_files=sum(item.max_items for item in outputs),
        ),
    )


COMPONENT_SPECS = (
    *tuple(
        ComponentSpec(name, "transform", f"curve_score.operation_transforms:{attribute}")
        for name, attribute in (
            ("score_curve_bundle", "SCORE_CURVE_BUNDLE"),
            ("reference_coverage", "REFERENCE_COVERAGE"),
            ("objective_coverage", "OBJECTIVE_COVERAGE"),
        )
    ),
    *tuple(
        ComponentSpec(name, "guard", f"curve_score.operation_transforms:{attribute}")
        for name, attribute in (
            ("score_parentage", "SCORE_PARENTAGE"),
            ("objective_parentage", "OBJECTIVE_PARENTAGE"),
        )
    ),
    *tuple(
        ComponentSpec(
            name,
            "validator",
            f"curve_score.operation_transforms:{attribute}",
            resources=(
                (ComponentRef("curve_contract_semantic_contract"),)
                if name == "curve_contract_validator"
                else ()
            ),
            public=name in {
                "curve_bundle_validator",
                "curve_contract_validator",
                "audit_validator",
            },
        )
        for name, attribute in (
            ("curve_bundle_validator", "CURVE_BUNDLE_VALIDATOR"),
            ("curve_contract_validator", "CURVE_CONTRACT_VALIDATOR"),
            ("metric_report_validator", "METRIC_REPORT_VALIDATOR"),
            ("reference_coverage_validator", "REFERENCE_COVERAGE_VALIDATOR"),
            ("objective_coverage_validator", "OBJECTIVE_COVERAGE_VALIDATOR"),
            ("audit_validator", "AUDIT_VALIDATOR"),
            ("plot_validator", "PLOT_VALIDATOR"),
        )
    ),
    *tuple(
        ComponentSpec(
            name,
            "resource",
            f"curve_score.operation_transforms:{attribute}",
            public=name
            in {
                "curve_bundle_schema",
                "curve_contract_schema",
            },
        )
        for name, attribute in (
            ("curve_bundle_schema", "CURVE_BUNDLE_SCHEMA"),
            ("curve_contract_schema", "CURVE_CONTRACT_SCHEMA"),
            ("metric_report_schema", "METRIC_REPORT_SCHEMA"),
            ("reference_coverage_schema", "REFERENCE_COVERAGE_SCHEMA"),
            ("objective_coverage_schema", "OBJECTIVE_COVERAGE_SCHEMA"),
            ("score_audit_schema", "SCORE_AUDIT_SCHEMA"),
            ("plot_schema", "PLOT_SCHEMA"),
        )
    ),
)

FIGURE_COMPONENT_SPECS = (
    ComponentSpec(
        "materialize_figure_evidence",
        "transform",
        "curve_score.operation_transforms:MATERIALIZE_FIGURE_EVIDENCE",
    ),
    ComponentSpec(
        "bundle_figure_evidence",
        "transform",
        "curve_score.operation_transforms:BUNDLE_FIGURE_EVIDENCE",
    ),
    ComponentSpec(
        "figure_parentage",
        "guard",
        "curve_score.operation_transforms:FIGURE_PARENTAGE",
    ),
    ComponentSpec(
        "figure_manifest_schema",
        "resource",
        "curve_score.operation_transforms:FIGURE_MANIFEST_SCHEMA",
    ),
    ComponentSpec(
        "figure_report_schema",
        "resource",
        "curve_score.operation_transforms:FIGURE_REPORT_SCHEMA",
    ),
    ComponentSpec(
        "figure_audit_schema",
        "resource",
        "curve_score.operation_transforms:FIGURE_AUDIT_SCHEMA",
    ),
    ComponentSpec(
        "figure_manifest_validator",
        "validator",
        "curve_score.operation_transforms:FIGURE_MANIFEST_VALIDATOR",
    ),
    ComponentSpec(
        "figure_report_validator",
        "validator",
        "curve_score.operation_transforms:FIGURE_REPORT_VALIDATOR",
    ),
    ComponentSpec(
        "figure_png_validator",
        "validator",
        "curve_score.operation_transforms:PNG_VALIDATOR",
    ),
)


_REFERENCE_INPUT = _input(
    "reference_bundles",
    "scidiscovery.curve-bundle.v1",
    "curve_bundle_schema",
    min_items=0,
    max_items=256,
    max_bytes=32 * 1024 * 1024,
    usage="evidence_inventory",
)


FIGURE_OPERATIONS = (
    _operation(
        "science.figure.evidence.materialize.v1",
        "materialize_figure_evidence",
        "Deterministically recover and digitize one exact typed paper figure.",
        (
            _input(
                "paper_source",
                "opaque",
                _ref("opaque_schema", plugin_id="general_science"),
                max_bytes=32 * 1024 * 1024,
                usage="evidence_inventory",
                media_types=("application/pdf", "image/png", "image/jpeg", "image/webp"),
            ),
            _input(
                "figure_request",
                "scidiscovery.curve-figure-digitization-request.v2",
                "figure_request_schema",
                max_bytes=1024 * 1024,
                usage="evidence_inventory",
            ),
        ),
        (
            _output(
                "figure_manifest",
                "figure_evidence_manifest",
                "scidiscovery.figure-evidence-manifest.v1",
                "figure_manifest_schema",
                "figure_manifest_validator",
                max_bytes=1024 * 1024,
            ),
            _output(
                "source_panels",
                "figure_source_panel",
                "opaque",
                _ref("opaque_schema", plugin_id="general_science"),
                "figure_png_validator",
                max_bytes=16 * 1024 * 1024,
                media_type="image/png",
            ),
            _output(
                "audit_overlays",
                "figure_audit_overlay",
                "opaque",
                _ref("opaque_schema", plugin_id="general_science"),
                "figure_png_validator",
                max_bytes=16 * 1024 * 1024,
                media_type="image/png",
            ),
            _output(
                "curve_tables",
                "digitized_curve_table",
                "opaque",
                _ref("opaque_schema", plugin_id="general_science"),
                _ref("nonempty_validator"),
                min_items=1,
                max_items=32,
                max_bytes=8 * 1024 * 1024,
                media_type="text/csv",
            ),
            _output(
                "validation_report",
                "figure_evidence_validation_report",
                "scidiscovery.figure-evidence-validation-report.v1",
                "figure_report_schema",
                "figure_report_validator",
                max_bytes=1024 * 1024,
            ),
        ),
        max_input_bytes=33 * 1024 * 1024,
        max_output_bytes=290 * 1024 * 1024,
    ),
    _operation(
        FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
        "bundle_figure_evidence",
        "Normalize exact validated figure tables into one canonical evidence library.",
        (
            _input("paper_source", "opaque", _ref("opaque_schema", plugin_id="general_science"), max_bytes=32 * 1024 * 1024, usage="evidence_inventory", media_types=("application/pdf", "image/png", "image/jpeg", "image/webp")),
            _input("figure_request", "scidiscovery.curve-figure-digitization-request.v2", "figure_request_schema", max_bytes=1024 * 1024, usage="evidence_inventory"),
            _input("scientific_intake", "scidiscovery.scientific-intake.v1", _ref("scientific_intake_schema", plugin_id="general_science"), usage="prior_signal", max_bytes=64 * 1024),
            _input("evidence_audit", "scidiscovery.evidence-audit.v1", _ref("evidence_audit_schema", plugin_id="general_science"), usage="prior_signal", max_bytes=32 * 1024),
            _input("figure_manifest", "scidiscovery.figure-evidence-manifest.v1", "figure_manifest_schema", usage="evidence_inventory"),
            _input("validation_report", "scidiscovery.figure-evidence-validation-report.v1", "figure_report_schema", usage="evidence_inventory"),
            _input("source_panels", "opaque", _ref("opaque_schema", plugin_id="general_science"), max_bytes=16 * 1024 * 1024, usage="evidence_inventory", media_types=("image/png",)),
            _input("audit_overlays", "opaque", _ref("opaque_schema", plugin_id="general_science"), max_bytes=16 * 1024 * 1024, usage="evidence_inventory", media_types=("image/png",)),
            _input("curve_tables", "opaque", _ref("opaque_schema", plugin_id="general_science"), min_items=1, max_items=32, usage="evidence_inventory", media_types=("text/csv",)),
        ),
        (
            _output("curve_bundle", "curve_bundle", "scidiscovery.curve-bundle.v1", _ref("curve_bundle_schema", plugin_id="curve_score"), _ref("curve_bundle_validator", plugin_id="curve_score"), max_bytes=256 * 1024 * 1024),
            _output("normalization_audit", "figure_evidence_curve_normalization_audit", "scidiscovery.figure-evidence-curve-normalization-audit.v1", "figure_audit_schema", _ref("audit_validator", plugin_id="curve_score"), max_bytes=16 * 1024 * 1024),
        ),
        guards=("figure_parentage",),
    ),
)


OPERATIONS = (
    _operation(
        CURVE_SCORE_OPERATION,
        "score_curve_bundle",
        "Score one canonical solver curve bundle against its pre-registered experiment plan.",
        (
            _input("curve_bundle", "scidiscovery.curve-bundle.v1", "curve_bundle_schema", usage="prior_signal", max_bytes=256 * 1024 * 1024),
            _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", plugin_id="general_science")),
            _review_input("experiment_review"),
            _input(
                "curve_contract",
                "scidiscovery.curve-experiment-contract.v1",
                "curve_contract_schema",
                usage="prior_signal",
            ),
            _review_input("curve_contract_review"),
            _REFERENCE_INPUT,
        ),
        (
            _output("metric_report", "metric_report", "scidiscovery.curve-consistency-report.v1", "metric_report_schema", "metric_report_validator"),
            _output("merged_curve_bundle", "curve_bundle", "scidiscovery.curve-bundle.v1", "curve_bundle_schema", "curve_bundle_validator", max_bytes=256 * 1024 * 1024),
            _output("score_audit", "curve_score_audit", "scidiscovery.curve-score-audit.v1", "score_audit_schema", "audit_validator", max_bytes=16 * 1024 * 1024),
            _output("comparison_plot", "curve_comparison_plot", "scidiscovery.curve-comparison-plot.v1", "plot_schema", "plot_validator", max_bytes=16 * 1024 * 1024, media_type="image/png"),
        ),
        guards=("score_parentage",),
    ),
    _operation(
        CURVE_REFERENCE_COVERAGE_OPERATION,
        "reference_coverage",
        "Verify that one experiment plan explicitly disposes every supplied reference series.",
        (
            _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", plugin_id="general_science")),
            _review_input("experiment_review"),
            _input(
                "curve_contract",
                "scidiscovery.curve-experiment-contract.v1",
                "curve_contract_schema",
                usage="prior_signal",
            ),
            _review_input("curve_contract_review"),
            _REFERENCE_INPUT.model_copy(update={"min_items": 1}),
        ),
        (
            _output("coverage_report", "curve_reference_coverage", "scidiscovery.curve-reference-coverage.v1", "reference_coverage_schema", "reference_coverage_validator"),
        ),
    ),
    _operation(
        OBJECTIVE_COVERAGE_OPERATION,
        "objective_coverage",
        "Verify exact objective coverage by one experiment plan and its reference libraries.",
        (
            _input(
                "objective",
                "scidiscovery.research-objective.v1",
                _ref("research_objective_schema", plugin_id="general_science"),
                usage="prior_signal",
            ),
            _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", plugin_id="general_science")),
            _review_input("experiment_review"),
            _input(
                "curve_contracts",
                "scidiscovery.curve-experiment-contract.v1",
                "curve_contract_schema",
                min_items=0,
                max_items=16,
                usage="prior_signal",
            ),
            _review_input("curve_contract_reviews", min_items=0, max_items=16),
            _REFERENCE_INPUT,
        ),
        (
            _output("coverage_report", "objective_coverage", "scidiscovery.objective-coverage.v1", "objective_coverage_schema", "objective_coverage_validator"),
        ),
        guards=("objective_parentage",),
    ),
)


__all__ = [
    "COMPONENT_SPECS",
    "FIGURE_COMPONENT_SPECS",
    "FIGURE_OPERATIONS",
    "OPERATIONS",
]
