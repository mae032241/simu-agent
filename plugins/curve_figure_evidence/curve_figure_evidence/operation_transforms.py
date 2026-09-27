"""Normalize an explicitly saved and independently reviewed figure family."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.spec import CallableComponent, ComponentRef, ComponentSpec
from scidiscovery.operations.transforms import (
    group_inputs, object_schema, single_input, transform_operation, transform_output,
)
from .figure_evidence import FigureEvidenceManifest, FigureEvidenceValidationReport
from .figure_science_operations import (AUDIT_INPUTS, BUNDLE_OPERATION, FAMILY_VALIDATION, _input as science_input)
from .figure_family import figure_audit_parentage, selected_family_files
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from .figure_family import figure_records
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
    manifest_raw = single_input(values, "figure_manifest")
    report_raw = single_input(values, "validation_report")
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


def figure_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    if not figure_audit_parentage(inputs, parameters):
        return False
    grouped = group_inputs(inputs)
    if len(grouped.get("evidence_audit", ())) != 1:
        return False
    audit = grouped["evidence_audit"][0].artifact
    labels = dict(audit.labels)
    expected = {item.artifact.ref for item in inputs if item.port_name != "evidence_audit"}
    return bool(labels.get("operation_id") == "science.figure.evidence.audit.v2"
        and labels.get("operation_output_port") == "evidence_audit"
        and expected <= set(audit.parent_refs) and audit.handoff_verdict == "pass")


def bundle_selected_figure(values):
    proof = figure_records(single_input(values, "figure_provenance"))
    # Admission has already checked exact Artifact identities. Transform inputs carry bytes.
    by_digest = {hashlib.sha256(raw).hexdigest(): raw for raw in values["figure_family"]}
    files_by_ref = {ArtifactRef.model_validate(record["artifact_ref"]): by_digest[record["artifact_ref"]["sha256"]]
        for record in proof}
    source_refs = {ArtifactRef.model_validate(record["source_ref"]) for record in proof}
    if len(source_refs) != 1:
        raise ValueError("figure family source is ambiguous")
    files = selected_family_files(proof, files_by_ref, source_refs.pop())
    def contents(prefix):
        return tuple(raw for name, (raw, _) in sorted(files.items()) if name.startswith(prefix + "/"))
    if not contents("curve_tables"):
        raise ValueError("unresolved figure family cannot produce a quantitative curve bundle")
    return bundle_figure_evidence({"figure_manifest": contents("figure_manifest"),
        "validation_report": contents("validation_reports"), "curve_tables": contents("curve_tables")})


BUNDLE_SELECTED_FIGURE = CallableComponent("transform", bundle_selected_figure)
FIGURE_PARENTAGE = CallableComponent("guard", figure_parentage)
FIGURE_AUDIT_SCHEMA = object_schema("scidiscovery.figure-evidence-curve-normalization-audit.v1")
FIGURE_COMPONENT_SPECS = (
    ComponentSpec("bundle_selected_figure", "transform", "curve_figure_evidence.operation_transforms:BUNDLE_SELECTED_FIGURE"),
    ComponentSpec("figure_parentage", "guard", "curve_figure_evidence.operation_transforms:FIGURE_PARENTAGE"),
    ComponentSpec("figure_audit_schema", "resource", "curve_figure_evidence.operation_transforms:FIGURE_AUDIT_SCHEMA"),
)
FIGURE_OPERATIONS = (
    transform_operation(BUNDLE_OPERATION, ComponentRef("bundle_selected_figure"),
        "Normalize the complete selected and independently audited figure family into a quantitative evidence library.",
        (*AUDIT_INPUTS, science_input("evidence_audit", "Exact passing independent audit of the selected Intake and family.",
            "scidiscovery.evidence-audit.v1", resource="evidence_audit_schema", usage="prior_signal", max_item_bytes=32*1024)),
        (
            transform_output("curve_bundle", "curve_bundle", "scidiscovery.curve-bundle.v1", ComponentRef("curve_bundle_schema", plugin_id="curve_score"),
                ComponentRef("curve_bundle_validator", plugin_id="curve_score"), codec=ComponentRef("json_codec", plugin_id="general_science"), max_bytes=256*1024*1024),
            transform_output("normalization_audit", "figure_evidence_curve_normalization_audit", "scidiscovery.figure-evidence-curve-normalization-audit.v1",
                ComponentRef("figure_audit_schema"), ComponentRef("audit_validator", plugin_id="curve_score"), codec=ComponentRef("json_codec", plugin_id="general_science"), max_bytes=16*1024*1024),
        ), guards=(ComponentRef("figure_parentage"),), max_input_bytes=355*1024*1024,
        applies_when="The exact selected figure family and its independent audit are available.",
        not_for="Selecting scientific targets, interpreting mechanisms, or executing a solver.",
    ).model_copy(update={"input_validation": FAMILY_VALIDATION}),
)
