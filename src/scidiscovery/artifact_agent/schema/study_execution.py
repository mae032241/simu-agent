"""Typed case-to-execution planning for multi-step TCAD studies."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel
from .refs import ArtifactRef


class PlannedResourceLimits(SchemaModel):
    wall_time_seconds: Annotated[int, Field(ge=1, le=604800)]
    cpu_time_seconds: Annotated[int, Field(ge=1, le=604800)]
    max_memory_bytes: Annotated[int, Field(ge=1, le=2**50)]
    max_output_bytes: Annotated[int, Field(ge=1, le=2**50)]
    max_processes: Annotated[int, Field(ge=1, le=4096)]


class ExecutionDependency(SchemaModel):
    upstream_unit_key: Identifier
    required_state: Literal["collected"] = "collected"
    require_runtime_qualification: Literal[True] = True


class ExecutionUnit(SchemaModel):
    """One direct solver invocation bound to one study case."""

    unit_key: Identifier
    case_key: Identifier
    solver_kind: Literal["sprocess", "sdevice"]
    reviewed_project_ref: ArtifactRef
    review_ref: ArtifactRef
    solver_capability_ref: ArtifactRef
    resource_limits: PlannedResourceLimits
    dependencies: Annotated[
        tuple[ExecutionDependency, ...], Field(default=(), max_length=256)
    ]
    expected_output_names: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=4096)
    ]

    @model_validator(mode="after")
    def _bindings_are_unambiguous(self) -> ExecutionUnit:
        dependencies = tuple(item.upstream_unit_key for item in self.dependencies)
        if self.unit_key in dependencies:
            raise ValueError("execution unit cannot depend on itself")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("execution unit dependencies must be unique")
        if len(self.expected_output_names) != len(set(self.expected_output_names)):
            raise ValueError("execution unit expected outputs must be unique")
        if self.review_ref.schema_id not in {
            "tcad.deck-review-report.v1",
            "tcad.deck-review-attestation.v1",
        }:
            raise ValueError("execution unit requires a typed deck review reference")
        if self.solver_capability_ref.schema_id != "tcad.solver-capability.v2":
            raise ValueError("execution unit requires a solver capability reference")
        return self


class CaseRealization(SchemaModel):
    """Bind one experiment case to history or an ordered execution chain."""

    case_key: Identifier
    realization_kind: Literal["historical_evidence", "planned_execution"]
    historical_evidence_refs: Annotated[
        tuple[ArtifactRef, ...], Field(default=(), max_length=4096)
    ]
    execution_unit_keys: Annotated[
        tuple[Identifier, ...], Field(default=(), max_length=4096)
    ]

    @model_validator(mode="after")
    def _source_is_exclusive(self) -> CaseRealization:
        if self.realization_kind == "historical_evidence":
            if not self.historical_evidence_refs or self.execution_unit_keys:
                raise ValueError(
                    "historical realization requires evidence and no execution units"
                )
        elif self.historical_evidence_refs or not self.execution_unit_keys:
            raise ValueError(
                "planned realization requires execution units and no historical evidence"
            )
        if len(self.execution_unit_keys) != len(set(self.execution_unit_keys)):
            raise ValueError("case execution units must be unique")
        return self


class StudyExecutionPlan(SchemaModel):
    experiment_plan_ref: ArtifactRef
    case_keys: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=10000)]
    realizations: Annotated[
        tuple[CaseRealization, ...], Field(min_length=1, max_length=10000)
    ]
    execution_units: Annotated[
        tuple[ExecutionUnit, ...], Field(default=(), max_length=10000)
    ]

    @model_validator(mode="after")
    def _topology_is_complete_and_acyclic(self) -> StudyExecutionPlan:
        if len(self.case_keys) != len(set(self.case_keys)):
            raise ValueError("study case keys must be unique")
        by_case = {item.case_key: item for item in self.realizations}
        if len(by_case) != len(self.realizations) or set(by_case) != set(self.case_keys):
            raise ValueError("realizations must cover the exact study cases")
        by_unit = {item.unit_key: item for item in self.execution_units}
        if len(by_unit) != len(self.execution_units):
            raise ValueError("study execution unit keys must be unique")

        planned_keys = {
            key
            for realization in self.realizations
            for key in realization.execution_unit_keys
        }
        if planned_keys != set(by_unit):
            raise ValueError("case realizations must bind every execution unit exactly once")

        for realization in self.realizations:
            position = {
                key: index for index, key in enumerate(realization.execution_unit_keys)
            }
            for key in realization.execution_unit_keys:
                unit = by_unit.get(key)
                if unit is None or unit.case_key != realization.case_key:
                    raise ValueError("execution unit is bound to the wrong study case")
                for dependency in unit.dependencies:
                    upstream = by_unit.get(dependency.upstream_unit_key)
                    if upstream is None:
                        raise ValueError("execution dependency names an unknown unit")
                    if upstream.case_key != unit.case_key:
                        raise ValueError("execution dependency crosses study cases")
                    if position[upstream.unit_key] >= position[unit.unit_key]:
                        raise ValueError(
                            "case execution order must place dependencies first"
                        )
        return self


__all__ = [
    "CaseRealization",
    "ExecutionDependency",
    "ExecutionUnit",
    "PlannedResourceLimits",
    "StudyExecutionPlan",
]
