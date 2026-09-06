"""Deterministic figure materialization, normalization, and family guards."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.spec import CallableComponent, ComponentSpec, ComponentRef
from curve_score.operation_transforms import (
    _group, _input, _model_validator, _object_schema, _one, _operation,
    _output, _png, _ref, _schema,
)
from .figure_evidence import (FigureEvidenceManifest, FigureEvidenceValidationReport,
    AutomaticFigureEvidenceManifest, AutomaticFigureEvidenceValidationReport)
from .figure_digitization import build_automatic_figure_bundle
from .figure_digitization_contract import FigureMeasurementRequest
from .figure_science_operations import FIGURE_FAMILY_REQUIREMENT
from .figure_evidence_normalizer import (
    FIGURE_EVIDENCE_BUNDLE_PROFILE_V2, normalize_figure_evidence,
)


def bundle_figure_evidence_outputs(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    fixed = {"figure_manifest", "validation_report"}
    table_inputs = {name for name in inputs if name.startswith("curve_table__")}
    if (
        not fixed.issubset(inputs)
        or not table_inputs
        or "curve_table__" in table_inputs
        or set(inputs) != fixed | table_inputs
    ):
        raise ValueError(
            "figure evidence bundling requires figure_manifest, validation_report, "
            "and curve_table__<panel_key>__<series_key> inputs"
        )
    bundle, audits = normalize_figure_evidence(
        manifest_content=inputs["figure_manifest"],
        validation_report_content=inputs["validation_report"],
        curve_tables={name: inputs[name] for name in table_inputs},
        profile=FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
    )
    return {
        "curve_bundle": (bundle.canonical_json(),),
        "normalization_audit": (
            canonical_json(
                {
                    "schema_version": 1,
                    "profile": FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
                    "series": [item.as_dict() for item in audits],
                }
            ),
        ),
    }


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
    if set(values) != {"paper_source", "figure_intent"}:
        raise ValueError("figure materialization requires one source and one intent")
    files = build_automatic_figure_bundle(
        _one(values, "paper_source"), _one(values, "figure_intent")
    )

    def items(prefix: str) -> tuple[bytes, ...]:
        return tuple(
            content
            for name, (content, _) in sorted(files.items())
            if name.startswith(prefix + "/")
        )

    result = {
        "figure_request": items("figure_request"),
        "figure_manifest": items("figure_manifest"),
        "source_panels": items("source_panels"),
        "audit_overlays": items("audit_overlays"),
        "curve_tables": items("curve_tables"),
        "validation_report": items("validation_reports"),
    }
    if len(result["figure_manifest"]) != 1 or len(result["validation_report"]) != 1:
        raise ValueError("figure materialization did not produce its singular records")
    return result


def figure_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    grouped = _group(inputs)
    if not grouped.get("curve_tables"):
        # Faithful unresolved Intake/audit results do not create a quantitative library.
        return False
    required = {
        "paper_source", "figure_intent", "figure_request", "scientific_intake", "evidence_audit",
        "figure_manifest", "validation_report", "source_panels",
        "audit_overlays", "curve_tables",
    }
    if not required <= set(grouped) or any(
        len(grouped[name]) != 1
        for name in (
            "paper_source", "figure_intent", "figure_request", "scientific_intake",
            "evidence_audit", "figure_manifest", "validation_report",
            "source_panels", "audit_overlays",
        )
    ):
        return False
    source = grouped["paper_source"][0]
    intent = grouped["figure_intent"][0]
    request = grouped["figure_request"][0]
    intake = grouped["scientific_intake"][0]
    audit = grouped["evidence_audit"][0]
    family = (
        request,
        grouped["figure_manifest"][0],
        grouped["validation_report"][0],
        *grouped["source_panels"],
        *grouped["audit_overlays"],
        *grouped["curve_tables"],
    )
    request_labels = dict(request.artifact.labels)
    if (
        set(request.artifact.parent_refs) != {source.artifact.ref, intent.artifact.ref}
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
        or set(item.artifact.parent_refs) != {source.artifact.ref, intent.artifact.ref}
        for item in family
    ):
        return False
    family_refs = tuple(item.artifact.ref for item in family)
    expected_intake_parents = {
        source.artifact.ref, intent.artifact.ref, *family_refs
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


BUNDLE_FIGURE_EVIDENCE = CallableComponent("transform", bundle_figure_evidence)


MATERIALIZE_FIGURE_EVIDENCE = CallableComponent(
    "transform", materialize_figure_evidence
)


FIGURE_PARENTAGE = CallableComponent("guard", figure_parentage)
FIGURE_MEASUREMENT_VALIDATOR = CallableComponent("validator", _model_validator(FigureMeasurementRequest))


FIGURE_MANIFEST_VALIDATOR = CallableComponent(
    "validator", _model_validator(AutomaticFigureEvidenceManifest)
)


FIGURE_REPORT_VALIDATOR = CallableComponent(
    "validator", _model_validator(AutomaticFigureEvidenceValidationReport)
)


PNG_VALIDATOR = CallableComponent("validator", _png)


FIGURE_MANIFEST_SCHEMA = _schema(
    AutomaticFigureEvidenceManifest, "scidiscovery.figure-evidence-manifest.v2"
)


FIGURE_REPORT_SCHEMA = _schema(
    AutomaticFigureEvidenceValidationReport,
    "scidiscovery.figure-evidence-validation-report.v2",
)


FIGURE_AUDIT_SCHEMA = _object_schema(
    "scidiscovery.figure-evidence-curve-normalization-audit.v1"
)


FIGURE_COMPONENT_SPECS = (
    ComponentSpec("figure_measurement_validator", "validator",
        "curve_figure_evidence.operation_transforms:FIGURE_MEASUREMENT_VALIDATOR"),
    ComponentSpec(
        "materialize_figure_evidence",
        "transform",
        "curve_figure_evidence.operation_transforms:MATERIALIZE_FIGURE_EVIDENCE",
        resources=(ComponentRef("detector_contract"),),
    ),
    ComponentSpec(
        "bundle_figure_evidence",
        "transform",
        "curve_figure_evidence.operation_transforms:BUNDLE_FIGURE_EVIDENCE",
    ),
    ComponentSpec(
        "figure_parentage",
        "guard",
        "curve_figure_evidence.operation_transforms:FIGURE_PARENTAGE",
    ),
    ComponentSpec(
        "figure_manifest_schema",
        "resource",
        "curve_figure_evidence.operation_transforms:FIGURE_MANIFEST_SCHEMA",
    ),
    ComponentSpec(
        "figure_report_schema",
        "resource",
        "curve_figure_evidence.operation_transforms:FIGURE_REPORT_SCHEMA",
    ),
    ComponentSpec(
        "figure_audit_schema",
        "resource",
        "curve_figure_evidence.operation_transforms:FIGURE_AUDIT_SCHEMA",
    ),
    ComponentSpec(
        "figure_manifest_validator",
        "validator",
        "curve_figure_evidence.operation_transforms:FIGURE_MANIFEST_VALIDATOR",
    ),
    ComponentSpec(
        "figure_report_validator",
        "validator",
        "curve_figure_evidence.operation_transforms:FIGURE_REPORT_VALIDATOR",
    ),
    ComponentSpec(
        "figure_png_validator",
        "validator",
        "curve_figure_evidence.operation_transforms:PNG_VALIDATOR",
    ),
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
                "figure_intent",
                "scidiscovery.figure-extraction-intent.v2",
                "figure_intent_schema",
                max_bytes=1024 * 1024,
                usage="evidence_inventory",
            ),
        ),
        (
            _output("figure_request", "figure_measurement_request",
                "scidiscovery.curve-figure-digitization-request.v3", "figure_request_schema",
                "figure_measurement_validator", max_bytes=1024 * 1024),
            _output(
                "figure_manifest",
                "figure_evidence_manifest",
                "scidiscovery.figure-evidence-manifest.v2",
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
                min_items=0,
                max_bytes=16 * 1024 * 1024,
                media_type="image/png",
            ),
            _output(
                "audit_overlays",
                "figure_audit_overlay",
                "opaque",
                _ref("opaque_schema", plugin_id="general_science"),
                "figure_png_validator",
                min_items=0,
                max_bytes=16 * 1024 * 1024,
                media_type="image/png",
            ),
            _output(
                "curve_tables",
                "digitized_curve_table",
                "opaque",
                _ref("opaque_schema", plugin_id="general_science"),
                _ref("nonempty_validator"),
                min_items=0,
                max_items=32,
                max_bytes=8 * 1024 * 1024,
                media_type="text/csv",
            ),
            _output(
                "validation_report",
                "figure_evidence_validation_report",
                "scidiscovery.figure-evidence-validation-report.v2",
                "figure_report_schema",
                "figure_report_validator",
                max_bytes=1024 * 1024,
            ),
        ),
        max_input_bytes=33 * 1024 * 1024,
        max_output_bytes=291 * 1024 * 1024,
    ),
    _operation(
        FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
        "bundle_figure_evidence",
        "Normalize exact validated figure tables into one canonical evidence library.",
        (
            _input("paper_source", "opaque", _ref("opaque_schema", plugin_id="general_science"), max_bytes=32 * 1024 * 1024, usage="evidence_inventory", media_types=("application/pdf", "image/png", "image/jpeg", "image/webp")),
            _input("figure_intent", "scidiscovery.figure-extraction-intent.v2", "figure_intent_schema", max_bytes=1024 * 1024, usage="evidence_inventory"),
            _input("figure_request", "scidiscovery.curve-figure-digitization-request.v3", "figure_request_schema", max_bytes=1024 * 1024, usage="evidence_inventory"),
            _input("scientific_intake", "scidiscovery.scientific-intake.v1", _ref("scientific_intake_schema", plugin_id="general_science"), usage="prior_signal", max_bytes=64 * 1024),
            _input("evidence_audit", "scidiscovery.evidence-audit.v1", _ref("evidence_audit_schema", plugin_id="general_science"), usage="prior_signal", max_bytes=32 * 1024),
            _input("figure_manifest", "scidiscovery.figure-evidence-manifest.v2", "figure_manifest_schema", usage="evidence_inventory"),
            _input("validation_report", "scidiscovery.figure-evidence-validation-report.v2", "figure_report_schema", usage="evidence_inventory"),
            _input("source_panels", "opaque", _ref("opaque_schema", plugin_id="general_science"), min_items=0, max_bytes=16 * 1024 * 1024, usage="evidence_inventory", media_types=("image/png",)),
            _input("audit_overlays", "opaque", _ref("opaque_schema", plugin_id="general_science"), min_items=0, max_bytes=16 * 1024 * 1024, usage="evidence_inventory", media_types=("image/png",)),
            _input("curve_tables", "opaque", _ref("opaque_schema", plugin_id="general_science"), min_items=0, max_items=32, usage="evidence_inventory", media_types=("text/csv",)),
        ),
        (
            _output("curve_bundle", "curve_bundle", "scidiscovery.curve-bundle.v1", _ref("curve_bundle_schema", plugin_id="curve_score"), _ref("curve_bundle_validator", plugin_id="curve_score"), max_bytes=256 * 1024 * 1024),
            _output("normalization_audit", "figure_evidence_curve_normalization_audit", "scidiscovery.figure-evidence-curve-normalization-audit.v1", "figure_audit_schema", _ref("audit_validator", plugin_id="curve_score"), max_bytes=16 * 1024 * 1024),
        ),
        guards=("figure_parentage",),
    ).model_copy(update={"complete_transform_family": FIGURE_FAMILY_REQUIREMENT}),
)
