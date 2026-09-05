"""Optional compiled Operation for the frozen InGaAs Fig.4 scorer."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal, Mapping, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    PluginDefinition,
    PluginDependency,
)
from .transform_adapter import (
    FIG4_BASELINE_RECOVERY_OPERATION,
    INTERPRETATION_BOUNDARY,
    score_baseline_recovery,
)
from .figure_compilation import COMPONENTS as FIGURE_COMPONENTS, OPERATION as FIGURE_OPERATION


_INPUT_NAMES = (
    "scorer_project",
    "curve_bundle",
    "target_metrics",
    "historical_baseline",
    "candidate_profile",
)


class _StrictResultModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        populate_by_name=True,
        allow_inf_nan=False,
    )


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonnegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class _InputDigests(_StrictResultModel):
    scorer_project: Sha256
    curve_bundle: Sha256
    target_metrics: Sha256
    historical_baseline: Sha256
    candidate_profile: Sha256


class _CrossingTriplet(_StrictResultModel):
    level_1e19: FiniteFloat = Field(alias="1e+19")
    level_1e18: FiniteFloat = Field(alias="1e+18")
    level_1e17: FiniteFloat = Field(alias="1e+17")


class _RecoveryChecks(_StrictResultModel):
    full_rms: bool
    max_abs_residual: bool
    crossings: bool
    lower_width: bool
    target_front_rms: bool
    target_full_rms: bool


class _RawBaselineReproduction(_StrictResultModel):
    rms_decade: NonnegativeFiniteFloat
    max_abs_residual_decade: NonnegativeFiniteFloat
    passed: bool = Field(alias="pass_1e_minus_9_decade")

    @model_validator(mode="after")
    def _check_gate(self) -> Self:
        if self.rms_decade > self.max_abs_residual_decade:
            raise ValueError("raw baseline RMS exceeds its maximum residual")
        if self.passed != (self.max_abs_residual_decade <= 1.0e-9):
            raise ValueError("raw baseline reproduction gate is inconsistent")
        return self


class _CurveMetrics(_StrictResultModel):
    crossings_um: _CrossingTriplet
    width_1e18_to_1e17_nm: FiniteFloat
    target_front_rms_decade: NonnegativeFiniteFloat
    target_full_rms_decade: NonnegativeFiniteFloat


class _BaselineRecovery(_StrictResultModel):
    full_rms_decade: NonnegativeFiniteFloat
    max_abs_residual_decade: NonnegativeFiniteFloat
    crossing_errors_nm: _CrossingTriplet
    lower_width_error_nm: FiniteFloat
    target_front_rms_difference_decade: FiniteFloat
    target_full_rms_difference_decade: FiniteFloat
    checks: _RecoveryChecks
    passed: bool = Field(alias="pass")

    @model_validator(mode="after")
    def _check_gate(self) -> Self:
        if self.full_rms_decade > self.max_abs_residual_decade:
            raise ValueError("baseline recovery RMS exceeds its maximum residual")
        checks = self.checks.model_dump()
        if self.passed != all(checks.values()):
            raise ValueError("baseline recovery gate is inconsistent")
        return self


class _ResidualRegion(_StrictResultModel):
    start_depth_um: FiniteFloat
    end_depth_um: FiniteFloat
    point_count: Annotated[int, Field(ge=1)]
    rms_decade: NonnegativeFiniteFloat
    peak_depth_um: FiniteFloat
    peak_signed_residual_decade: FiniteFloat

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if self.start_depth_um > self.end_depth_um:
            raise ValueError("residual region bounds are reversed")
        if not self.start_depth_um <= self.peak_depth_um <= self.end_depth_um:
            raise ValueError("residual region peak lies outside its bounds")
        if self.rms_decade > abs(self.peak_signed_residual_decade):
            raise ValueError("residual region RMS exceeds its peak residual")
        return self


class _MetricReport(_StrictResultModel):
    schema_version: Literal[1]
    scorer_version: Literal["2.0.0"]
    input_digests: _InputDigests
    raw_baseline_reproduces_frozen_curve_bundle: _RawBaselineReproduction
    baseline_recovery: _BaselineRecovery
    baseline_metrics: _CurveMetrics
    candidate_metrics: _CurveMetrics
    residual_regions_above_0p02_decade: tuple[_ResidualRegion, ...]
    interpretation_boundary: Literal[INTERPRETATION_BOUNDARY]


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"InGaAs scorer input {name} must contain one item")
    return items[0]


def _score(values: Mapping[str, tuple[bytes, ...]]) -> dict[str, tuple[bytes, ...]]:
    inputs = {name: _one(values, name) for name in _INPUT_NAMES}
    return {"metric_report": (canonical_json(score_baseline_recovery(inputs)),)}


def _result_validator(raw: bytes) -> None:
    _MetricReport.model_validate_json(raw, strict=True)


SCORE = CallableComponent("transform", _score)
RESULT_VALIDATOR = CallableComponent("validator", _result_validator)

TARGET_METRICS_SCHEMA = json.dumps(
    {"$id": "ingaas.fig4-target-metrics.v1", "type": "object"},
    separators=(",", ":"),
    sort_keys=True,
)
CURVE_TABLE_SCHEMA = json.dumps(
    {"$id": "ingaas.fig4-frozen-curve-table.v1", "type": "string"},
    separators=(",", ":"),
    sort_keys=True,
)
PLX_SCHEMA = json.dumps(
    {"$id": "ingaas.fig4-zinc-profile-plx.v1", "type": "string"},
    separators=(",", ":"),
    sort_keys=True,
)
RESULT_SCHEMA = _schema(_MetricReport, FIG4_BASELINE_RECOVERY_OPERATION)


def _ref(name: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)


def _input(
    name: str,
    schema: str,
    resource: str | ComponentRef,
    media_type: str,
    *,
    usage: str,
    max_bytes: int,
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Exact immutable InGaAs Fig.4 scorer input: {name}.",
        schema=schema,
        media_types=(media_type,),
        codec=_ref(
            "json_codec" if media_type == "application/json" else "opaque_codec",
            "general_science",
        ),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        max_item_bytes=max_bytes,
        usage=usage,
        exposure="full",
    )


COMPONENTS = (
    ComponentSpec("score", "transform", "ingaas_fig4.plugin:SCORE"),
    ComponentSpec(
        "result_validator", "validator", "ingaas_fig4.plugin:RESULT_VALIDATOR"
    ),
    ComponentSpec(
        "target_metrics_schema", "resource", "ingaas_fig4.plugin:TARGET_METRICS_SCHEMA"
    ),
    ComponentSpec(
        "curve_table_schema", "resource", "ingaas_fig4.plugin:CURVE_TABLE_SCHEMA"
    ),
    ComponentSpec("plx_schema", "resource", "ingaas_fig4.plugin:PLX_SCHEMA"),
    ComponentSpec("result_schema", "resource", "ingaas_fig4.plugin:RESULT_SCHEMA"),
)

OPERATION = OperationSpec(
        operation_id=FIG4_BASELINE_RECOVERY_OPERATION,
    version="1",
    catalog_scope="support",
    description=OperationDescription(
        purpose="Reproduce the frozen InGaAs Fig.4 baseline-recovery gate.",
        applies_when="The exact frozen scorer project and all four declared data inputs are available.",
        not_for="General curve scoring, mechanism attribution, or accepting a physical model.",
    ),
    executor=ExecutorRef(kind="transform", component=_ref("score")),
    inputs=(
        _input(
            "scorer_project", "tcad.deck-project.v1", _ref("project_schema", "tcad_artifact"),
            "application/json", usage="claim_evidence", max_bytes=32 * 1024 * 1024,
        ),
        _input(
            "curve_bundle", "ingaas.fig4-frozen-curve-table.v1", "curve_table_schema",
            "text/csv", usage="evidence_inventory", max_bytes=64 * 1024 * 1024,
        ),
        _input(
            "target_metrics", "ingaas.fig4-target-metrics.v1", "target_metrics_schema",
            "application/json", usage="evidence_inventory", max_bytes=8 * 1024 * 1024,
        ),
        _input(
            "historical_baseline", "ingaas.fig4-zinc-profile-plx.v1", "plx_schema",
            "application/x-synopsys-plx", usage="evidence_inventory",
            max_bytes=64 * 1024 * 1024,
        ),
        _input(
            "candidate_profile", "ingaas.fig4-zinc-profile-plx.v1", "plx_schema",
            "application/x-synopsys-plx", usage="evidence_inventory",
            max_bytes=64 * 1024 * 1024,
        ),
    ),
    outputs=(
        OutputPortSpec(
            name="metric_report",
            description="Frozen deterministic Fig.4 baseline-recovery report.",
            schema=FIG4_BASELINE_RECOVERY_OPERATION,
            media_types=("application/json",),
            codec=_ref("json_codec", "general_science"),
            schema_resource=_ref("result_schema"),
            max_item_bytes=8 * 1024 * 1024,
            kind="metric_report",
            validator=_ref("result_validator"),
        ),
    ),
    consequence="scientific",
    limits=LimitsSpec(
        timeout_seconds=60,
        max_input_bytes=256 * 1024 * 1024,
        max_output_bytes=8 * 1024 * 1024,
        max_files=1,
    ),
)

PLUGIN = PluginDefinition(
    plugin_id="ingaas_fig4",
    version="0.2.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
        PluginDependency("tcad_artifact", "0.2.0"),
        PluginDependency("curve_figure_evidence", "0.1.0"),
    ),
    components=COMPONENTS + FIGURE_COMPONENTS,
    operations=(OPERATION, FIGURE_OPERATION),
)


__all__ = ["PLUGIN"]
