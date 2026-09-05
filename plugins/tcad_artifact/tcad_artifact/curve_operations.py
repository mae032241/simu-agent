"""TCAD-owned adapters from attested solver output to canonical curve bundles."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from curve_score.schema import (
    CurveBundle,
    CurveComparisonSpec,
    CurveExperimentContract,
    CurveInterval,
    validate_curve_experiment_contract,
)
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
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

from .curve_normalizer import (
    SProcessLogSourceSpec,
    SProcessSeriesSpec,
    normalize_sprocess_log,
    source_spec_from_comparison_spec,
)
from .plx_normalizer import (
    PLX_NORMALIZER_PROFILE,
    SProcessPLXSourceSpec,
    normalize_sprocess_plx,
)
from .project_packager import RuntimeAttestation, TCADRuntimeManifest


SPROCESS_LOG_BUNDLE_PROFILE = "tcad.curve-bundle.sprocess-log.v1"
SPROCESS_PLX_BUNDLE_PROFILE = "tcad.curve-bundle.sprocess-plx.v1"
_PLX_MEDIA_TYPE = "application/x-synopsys-plx"


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"TCAD curve input {name} must contain exactly one item")
    return items[0]


def _optional(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes | None:
    items = values.get(name, ())
    if len(items) > 1:
        raise ValueError(f"TCAD curve input {name} accepts at most one item")
    return items[0] if items else None


def _bound_contract(
    values: Mapping[str, tuple[bytes, ...]],
) -> tuple[ExperimentPortfolio, CurveExperimentContract, CurveComparisonSpec]:
    plan = ExperimentPortfolio.model_validate_json(
        _one(values, "experiment_plan"), strict=True
    )
    contract = CurveExperimentContract.model_validate_json(
        _one(values, "curve_contract"), strict=True
    )
    validate_curve_experiment_contract(contract, plan)
    return plan, contract, contract.comparison_spec


def _passing_attestation(values: Mapping[str, tuple[bytes, ...]]) -> RuntimeAttestation:
    attestation = RuntimeAttestation.model_validate_json(
        _one(values, "runtime_attestation"), strict=True
    )
    if attestation.verdict != "pass":
        raise ValueError("TCAD curve normalization requires a passing attestation")
    return attestation


def bundle_sprocess_plx(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    _, _, spec = _bound_contract(values)
    _passing_attestation(values)
    manifest = TCADRuntimeManifest.model_validate_json(
        _one(values, "runtime_manifest"), strict=True
    )
    if manifest.terminal_state != "succeeded" or manifest.exit_code != 0:
        raise ValueError("PLX bundling requires a successful runtime manifest")
    compared = {
        series
        for comparison in spec.comparisons
        for series in (comparison.reference_series, comparison.candidate_series)
    }
    declarations = tuple(
        item
        for item in spec.series_declarations
        if item.source == "solver_output" and item.series_key in compared
    )
    required = {item.series_key for item in declarations}
    records = tuple(
        item
        for item in manifest.outputs
        if item.output_class == "solver_native" and item.name in required
    )
    if {item.name for item in records} != required or len(records) != len(required):
        raise ValueError("runtime manifest omits a compared solver curve")
    payloads = values.get("solver_outputs", ())
    if len(payloads) != len(records):
        raise ValueError("PLX collection differs from the runtime manifest")
    payload_by_name: dict[str, bytes] = {}
    for record, raw in zip(records, payloads, strict=True):
        if record.media_type != _PLX_MEDIA_TYPE:
            raise ValueError("compared solver output is not a declared PLX")
        if record.size_bytes != len(raw) or record.sha256 != hashlib.sha256(raw).hexdigest():
            raise ValueError("PLX bytes differ from the runtime manifest")
        payload_by_name[record.name] = raw

    bundles: list[CurveBundle] = []
    audits: list[dict[str, object]] = []
    for declaration in declarations:
        source_name = declaration.series_key
        bundle, audit = normalize_sprocess_plx(
            payload_by_name[source_name],
            SProcessPLXSourceSpec(
                series=SProcessSeriesSpec(
                    series_key=declaration.series_key,
                    case_key=declaration.case_key,
                    role=declaration.role,
                    x_axis=declaration.x_axis,
                    y_axis=declaration.y_axis,
                    min_points=declaration.min_points,
                    max_points=declaration.max_points,
                ),
                required_intervals=_required_intervals(spec, declaration.series_key),
            ),
            source_name=source_name,
        )
        bundles.append(
            bundle.model_copy(
                update={
                    "series": tuple(
                        item.model_copy(
                            update={"scientific_role": declaration.scientific_role}
                        )
                        for item in bundle.series
                    )
                }
            )
        )
        audits.append({"source_name": source_name, **audit.model_dump(mode="json")})
    merged = CurveBundle(
        source_profile=PLX_NORMALIZER_PROFILE,
        source_digests=tuple(
            sorted({digest for bundle in bundles for digest in bundle.source_digests})
        ),
        series=tuple(series for bundle in bundles for series in bundle.series),
    )
    audit_raw = canonical_json(
        {
            "schema_version": 1,
            "comparison_spec_sha256": canonical_sha256(spec),
            "solver_normalizations": audits,
        }
    )
    return {"curve_bundle": (merged.canonical_json(),), "normalization_audit": (audit_raw,)}


def bundle_sprocess_log(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    _, _, spec = _bound_contract(values)
    _passing_attestation(values)
    raw_source_spec = _optional(values, "source_spec")
    source_spec = (
        SProcessLogSourceSpec.model_validate_json(raw_source_spec, strict=True)
        if raw_source_spec is not None
        else source_spec_from_comparison_spec(spec)
    )
    bundle, audit = normalize_sprocess_log(
        _one(values, "solver_output"), source_spec
    )
    roles = {
        item.series_key: item.scientific_role
        for item in spec.series_declarations
        if item.source == "solver_output"
    }
    bundle = bundle.model_copy(
        update={
            "series": tuple(
                item.model_copy(update={"scientific_role": roles[item.series_key]})
                for item in bundle.series
            )
        }
    )
    return {
        "curve_bundle": (bundle.canonical_json(),),
        "normalization_audit": (audit.canonical_json(),),
    }


def _required_intervals(
    spec: CurveComparisonSpec, series_key: str
) -> tuple[CurveInterval, ...]:
    declared = sorted(
        (item.domain.start, item.domain.stop)
        for item in spec.comparisons
        if series_key in {item.reference_series, item.candidate_series}
    )
    merged: list[CurveInterval] = []
    for start, stop in declared:
        if merged and start <= merged[-1].stop:
            merged[-1] = CurveInterval(start=merged[-1].start, stop=max(stop, merged[-1].stop))
        else:
            merged.append(CurveInterval(start=start, stop=stop))
    return tuple(merged)


def plx_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    if parameters:
        return False
    grouped: dict[str, list[Any]] = {}
    for item in inputs:
        grouped.setdefault(item.port_name, []).append(item)
    manifest = grouped["runtime_manifest"][0]
    attestation = grouped["runtime_attestation"][0]
    outputs = grouped.get("solver_outputs", [])
    return bool(
        outputs
        and all(item.artifact.parent_refs == manifest.artifact.parent_refs for item in outputs)
        and manifest.artifact.ref in attestation.artifact.parent_refs
        and all(item.artifact.ref in attestation.artifact.parent_refs for item in outputs)
    )


def log_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    if parameters:
        return False
    grouped = {item.port_name: item for item in inputs}
    return grouped["solver_output"].artifact.ref in grouped[
        "runtime_attestation"
    ].artifact.parent_refs


def _json_object(raw: bytes) -> None:
    if not isinstance(json.loads(raw), dict):
        raise ValueError("TCAD curve audit must be a JSON object")


PLX_TRANSFORM = CallableComponent("transform", bundle_sprocess_plx)
LOG_TRANSFORM = CallableComponent("transform", bundle_sprocess_log)
PLX_GUARD = CallableComponent("guard", plx_parentage)
LOG_GUARD = CallableComponent("guard", log_parentage)
AUDIT_VALIDATOR = CallableComponent("validator", _json_object)
SOURCE_SPEC_SCHEMA = _schema(SProcessLogSourceSpec, "tcad.sprocess-log-source.v1")
AUDIT_SCHEMA = json.dumps(
    {"$id": "tcad.curve-normalization-audit.v1", "type": "object"},
    separators=(",", ":"),
    sort_keys=True,
)


def _ref(name: str, *, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)


def _input(
    name: str,
    schema: str,
    resource: ComponentRef,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 64 * 1024 * 1024,
    usage: str = "prior_signal",
    media_types: tuple[str, ...] = ("application/json",),
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Exact TCAD curve adapter input: {name}.",
        schema=schema,
        media_types=media_types,
        codec=_ref(
            "json_codec" if media_types == ("application/json",) else "opaque_codec",
            plugin_id="general_science",
        ),
        schema_resource=resource,
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        exposure="full",
        usage=usage,
    )


def _output(name: str, kind: str, schema: str, resource: ComponentRef, validator: ComponentRef, *, max_bytes: int) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=f"Deterministic TCAD curve adapter output: {name}.",
        schema=schema,
        media_types=("application/json",),
        codec=_ref("json_codec", plugin_id="general_science"),
        schema_resource=resource,
        max_item_bytes=max_bytes,
        kind=kind,
        validator=validator,
    )


_COMMON_INPUTS = (
    _input("runtime_attestation", "tcad.runtime-attestation.v1", _ref("runtime_attestation_schema")),
    _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", plugin_id="general_science")),
    _input("experiment_review", "scidiscovery.scientific-review.v1", _ref("scientific_review_schema", plugin_id="general_science")),
    _input("curve_contract", "scidiscovery.curve-experiment-contract.v1", _ref("curve_contract_schema", plugin_id="curve_score")),
    _input("curve_contract_review", "scidiscovery.scientific-review.v1", _ref("scientific_review_schema", plugin_id="general_science")),
)
_OUTPUTS = (
    _output("curve_bundle", "curve_bundle", "scidiscovery.curve-bundle.v1", _ref("curve_bundle_schema", plugin_id="curve_score"), _ref("curve_bundle_validator", plugin_id="curve_score"), max_bytes=256 * 1024 * 1024),
    _output("normalization_audit", "curve_normalization_audit", "tcad.curve-normalization-audit.v1", _ref("curve_normalization_audit_schema"), _ref("curve_normalization_audit_validator"), max_bytes=16 * 1024 * 1024),
)


def _operation(operation_id: str, component: str, purpose: str, inputs: tuple[InputPortSpec, ...], guard: str) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="support",
        description=OperationDescription(
            purpose=purpose,
            applies_when="Attested TCAD solver output and an exact curve contract are bound.",
            not_for="Selecting scientific comparisons, scoring curves, or interpreting results.",
        ),
        executor=ExecutorRef(kind="transform", component=_ref(component)),
        inputs=inputs,
        outputs=_OUTPUTS,
        consequence="scientific",
        guards=(_ref(guard),),
        limits=LimitsSpec(
            timeout_seconds=300,
            max_input_bytes=512 * 1024 * 1024,
            max_output_bytes=272 * 1024 * 1024,
            max_files=2,
        ),
    )


COMPONENT_SPECS = (
    ComponentSpec("curve_bundle_sprocess_plx", "transform", "tcad_artifact.curve_operations:PLX_TRANSFORM", configuration_identity="tcad-sprocess-plx:v1"),
    ComponentSpec("curve_bundle_sprocess_log", "transform", "tcad_artifact.curve_operations:LOG_TRANSFORM", configuration_identity="tcad-sprocess-log:v1"),
    ComponentSpec("curve_plx_parentage", "guard", "tcad_artifact.curve_operations:PLX_GUARD", configuration_identity="tcad-curve-plx-parentage:v1"),
    ComponentSpec("curve_log_parentage", "guard", "tcad_artifact.curve_operations:LOG_GUARD", configuration_identity="tcad-curve-log-parentage:v1"),
    ComponentSpec("curve_normalization_audit_validator", "validator", "tcad_artifact.curve_operations:AUDIT_VALIDATOR"),
    ComponentSpec("sprocess_log_source_schema", "resource", "tcad_artifact.curve_operations:SOURCE_SPEC_SCHEMA"),
    ComponentSpec("curve_normalization_audit_schema", "resource", "tcad_artifact.curve_operations:AUDIT_SCHEMA"),
)

OPERATIONS = (
    _operation(
        SPROCESS_PLX_BUNDLE_PROFILE,
        "curve_bundle_sprocess_plx",
        "Normalize exact manifest-bound SProcess PLX outputs into a canonical curve bundle.",
        (
            # Generic execution outputs are intentionally registered as opaque;
            # this adapter owns the domain parse and validates the manifest bytes.
            _input("runtime_manifest", "opaque", _ref("opaque_schema", plugin_id="general_science")),
            *_COMMON_INPUTS,
            _input("solver_outputs", "opaque", _ref("opaque_schema", plugin_id="general_science"), min_items=1, max_items=256, max_bytes=64 * 1024 * 1024, usage="evidence_inventory", media_types=(_PLX_MEDIA_TYPE,)),
        ),
        "curve_plx_parentage",
    ),
    _operation(
        SPROCESS_LOG_BUNDLE_PROFILE,
        "curve_bundle_sprocess_log",
        "Normalize one exact attested SProcess log into a canonical curve bundle.",
        (
            _input("solver_output", "opaque", _ref("opaque_schema", plugin_id="general_science"), max_bytes=256 * 1024 * 1024, usage="evidence_inventory", media_types=("text/plain",)),
            *_COMMON_INPUTS,
            _input("source_spec", "tcad.sprocess-log-source.v1", _ref("sprocess_log_source_schema"), min_items=0),
        ),
        "curve_log_parentage",
    ),
)


__all__ = ["COMPONENT_SPECS", "OPERATIONS"]
