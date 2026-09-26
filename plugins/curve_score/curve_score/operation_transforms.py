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
from .transform_adapter import (
    CURVE_SCORE_OPERATION,
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
REFERENCE_COVERAGE = CallableComponent("transform", reference_coverage)
OBJECTIVE_COVERAGE = CallableComponent("transform", objective_coverage)
SCORE_PARENTAGE = CallableComponent("guard", score_parentage)
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


CURVE_BUNDLE_SCHEMA = _schema(CurveBundle, "scidiscovery.curve-bundle.v1")
CURVE_CONTRACT_SCHEMA = _schema(
    CurveExperimentContract, "scidiscovery.curve-experiment-contract.v1"
)
METRIC_REPORT_SCHEMA = _schema(
    CurveConsistencyReport, "scidiscovery.curve-consistency-report.v1"
)
REFERENCE_COVERAGE_SCHEMA = _schema(
    CurveReferenceCoverageReport, "scidiscovery.curve-reference-coverage.v1"
)
OBJECTIVE_COVERAGE_SCHEMA = _schema(
    ObjectiveCoverageReport, "scidiscovery.objective-coverage.v1"
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


# Algorithms above remain available to complete analysis tools. These are the
# scientific types consumed by the figure adapter and analysis input declaration.
COMPONENT_SPECS = (
    ComponentSpec("audit_validator", "validator", "curve_score.operation_transforms:AUDIT_VALIDATOR", public=True),
    ComponentSpec("curve_bundle_schema", "resource", "curve_score.operation_transforms:CURVE_BUNDLE_SCHEMA", public=True),
    ComponentSpec("curve_bundle_validator", "validator", "curve_score.operation_transforms:CURVE_BUNDLE_VALIDATOR", public=True),
    ComponentSpec("metric_report_schema", "resource", "curve_score.operation_transforms:METRIC_REPORT_SCHEMA"),
)
OPERATIONS = ()

__all__ = ["COMPONENT_SPECS", "OPERATIONS"]
