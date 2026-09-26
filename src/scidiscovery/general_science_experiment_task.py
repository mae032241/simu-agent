"""A complete scientific experiment, with immutable stage evidence in one Run."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .artifact_agent.schema.common import canonical_json
from .artifact_agent.service.result_materialization import materialize_summary_handoff
from .general_science_agent_operations import BASE_TOOLS, _input
from .operation_declaration import schema_resource, scientific_agent_operation, semantic_contract
from .operations.spec import (CallableComponent, CollectionSpec, ComponentRef,
    ComponentSpec, InputPortSpec, OutputPortSpec, SemanticRuleSpec, WorkspaceContract)
from .operations.tooling import WorkerToolDefinition
from .operations.workspace import WorkspaceProtocolError
from .operation_contract import SemanticRuleViolation


class ExperimentReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    summary: str = Field(min_length=1, max_length=8192)
    outcome: Literal["completed", "inconclusive", "blocked"]
    limitations: tuple[str, ...] = Field(default=(), max_length=32)
    remaining_question: str = Field(max_length=8192)
    adopted_stages: tuple[str, ...] = Field(default=(), max_length=32)


class StageSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    stage: Literal["design", "implementation", "debug", "execution", "validity"]
    conclusion: str = Field(min_length=1, max_length=16384)
    limitations: tuple[str, ...] = Field(default=(), max_length=32)
    remaining_question: str = Field(default="", max_length=8192,
        description="Unresolved question or blocker, when there is one.")
    materials: tuple[str, ...] = Field(default=(), max_length=32,
        description="Exact current input or previously sealed stage aliases.")


def submit_stage(request, context):
    record = context.accept_evidence(raw=canonical_json(request.model_dump(mode="json")),
        media_type="application/json", derived_from=("research_objective", *request.materials),
        metadata={"kind": "experiment_stage", "stage": request.stage})
    return {"stage": request.stage, "reference": record["alias"], "state": "sealed"}


class ExecuteExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["capabilities", "start", "advance", "collect", "status", "read", "export", "cancel"]
    name: str = Field(default="experiment", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
    implementation: str | None = Field(default=None, max_length=128,
        description="Sealed implementation reference; required for start.")
    output_name: str | None = Field(default=None, max_length=256)
    offset: int = Field(default=0, ge=0)


def execute(request, context):
    return context.require_service("experiment.execution").command(context, request)


def validate_report(raw):
    ExperimentReport.model_validate_json(raw, strict=True)


def validate_completion(payload, sources, handoff):
    report = ExperimentReport.model_validate_json(canonical_json(payload), strict=True)
    records = {item["alias"]: item for item in json.loads(sources.tool_snapshot or b"{}").get("records", ())}
    if any(alias not in records for alias in report.adopted_stages):
        raise SemanticRuleViolation("Adopted stages must identify sealed materials of this task.")
    selected = [records[alias] for alias in report.adopted_stages]
    if report.outcome != "completed":
        return
    implementations = {item["alias"] for item in selected if item["metadata"].get("kind") == "experiment_implementation"}
    executions = {item["alias"] for item in selected if item["metadata"].get("kind") == "experiment_execution"
        and item["metadata"].get("implementation") in implementations}
    validity = [item for item in selected if item["metadata"].get("kind") == "experiment_stage"
        and item["metadata"].get("stage") == "validity"
        and executions.intersection(item["metadata"].get("derived_from", ()))]
    if not implementations or not executions or not validity:
        raise SemanticRuleViolation("A completed experiment must adopt a sealed implementation, its collected execution, and a validity assessment citing that execution. Otherwise report blocked or inconclusive.")


def finalize(request):
    value = json.loads((request.workspace / "output/result.json").read_bytes())
    if request.output_schema_id == "scidiscovery.experiment-review.v1":
        from .general_science_experiment_review import ExperimentReview
        review = ExperimentReview.model_validate_json(canonical_json(value["payload"]), strict=True)
        materialize_summary_handoff(value, review.verdict)
        return canonical_json(value)
    report = ExperimentReport.model_validate_json(canonical_json(value["payload"]), strict=True)
    evidence = request.binding_descriptors
    if any(alias not in evidence for alias in report.adopted_stages):
        raise WorkspaceProtocolError("Adopted stages must name sealed material available in this task.")
    materialize_summary_handoff(value, {"completed": "pass", "inconclusive": "inconclusive",
        "blocked": "blocked"}[report.outcome])
    return canonical_json(value)


PROMPT = """Own this complete experiment: design, implement, debug when useful,
execute through the controlled experiment tools, collect, and judge validity.
Use the research objective and exact supplied scientific materials. Explain
limitations instead of inventing missing evidence or claiming unavailable execution.
Keep normal corrections in this task. Ask for a scientific decision only when
the research direction must change. Submit useful stage conclusions with
worker_experiment_stage, citing sealed materials and noting unresolved questions.
Include execution interpretation when useful: executor facts do not supply your
scientific conclusion. Rework seals a new version; retain the exact versions you
adopt in the final report. Stage sealing is neither review nor final completion.
Formal execution is available only through worker_experiment_execute. A started
or successful solver is not by itself a valid scientific result. Read the collected
facts and deliver an ExperimentReport with the adopted sealed stage references.
Independent review is optional unless an applicable declared policy requires it;
no fixed preflight, initialization or reviewer checklist is a submission condition.
"""
SCHEMA = schema_resource(ExperimentReport, "scidiscovery.experiment-report.v1")
CONTRACT = semantic_contract(SemanticRuleSpec("experiment.sealed_material",
    "Adopted stages must identify this task's sealed materials. Completed requires an implementation, its collected execution, and a validity assessment citing that execution. Finish or cancel outstanding execution and diagnostics before final delivery. Design and debug stage submissions are optional. Otherwise report blocked or inconclusive; scientific validity belongs to the author."))
PROTOCOL = "scidiscovery.complete-experiment.v1"
WORKSPACE = WorkspaceContract()
AGENT = CallableComponent("agent", lambda: None)
VALIDATOR = CallableComponent("validator", validate_report)
COMPLETION_VALIDATOR = CallableComponent("validator", validate_completion)
FINALIZER = CallableComponent("workspace_finalizer", finalize)
STAGE_TOOL = WorkerToolDefinition(name="worker_experiment_stage",
    description="Seal a stage conclusion and its exact scientific materials in this experiment. Continue working after sealing.",
    input_model=StageSubmission, capability="experiment.stage", contextual_handler=submit_stage, owner_only=True,
    evidence_ports=("tool_evidence", "recovery_manifest_output"))
EXECUTE_TOOL = WorkerToolDefinition(name="worker_experiment_execute",
    description="Request, advance, collect or cancel this experiment's formal execution; status and capabilities are read-only. Read text or export exact collected scientific files into scratch for local analysis. Uses configured authorization and the original scientific budget.",
    input_model=ExecuteExperiment, capability="experiment.execute", contextual_handler=execute,
    optional_services=("experiment.execution",), evidence_ports=("tool_evidence", "recovery_manifest_output"))

_REF = ComponentRef
COMPONENTS = (
    ComponentSpec("experiment_task_protocol", "resource", __name__ + ":PROTOCOL", public=True),
    ComponentSpec("experiment_task_agent", "agent", __name__ + ":AGENT"),
    ComponentSpec("experiment_task_prompt", "resource", __name__ + ":PROMPT"),
    ComponentSpec("experiment_task_schema", "resource", __name__ + ":SCHEMA", public=True),
    ComponentSpec("experiment_task_contract", "resource", __name__ + ":CONTRACT"),
    ComponentSpec("experiment_task_validator", "validator", __name__ + ":VALIDATOR",
        resources=(_REF("experiment_task_contract"),)),
    ComponentSpec("experiment_completion_validator", "validator", __name__ + ":COMPLETION_VALIDATOR",
        resources=(_REF("experiment_task_contract"),)),
    ComponentSpec("experiment_task_finalizer", "workspace_finalizer", __name__ + ":FINALIZER"),
    ComponentSpec("experiment_task_workspace", "workspace", __name__ + ":WORKSPACE",
        resources=(_REF("experiment_task_finalizer"),)),
    ComponentSpec("experiment_stage_tool", "worker_tool", __name__ + ":STAGE_TOOL"),
    ComponentSpec("experiment_execute_tool", "worker_tool", __name__ + ":EXECUTE_TOOL"),
)
OPERATION = scientific_agent_operation(
    "science.experiment.v1", "Complete a bounded experiment from scientific design through execution and validity judgment.",
    "A research question and exact supporting scientific materials are available.",
    "Unbounded research or claims without retained observations.",
    agent=_REF("experiment_task_agent"), prompt=_REF("experiment_task_prompt"),
    workspace=_REF("experiment_task_workspace"),
    tools=BASE_TOOLS + (_REF("experiment_stage_tool"), _REF("experiment_execute_tool")),
    inputs=(
        _input("research_objective", "Exact scientific objective and constraints.", "scidiscovery.research-objective.v1"),
        _input("scientific_materials", "Exact hypothesis, evidence, parameters or feedback needed for this experiment.", "*",
            media_types=("*/*",), min_items=0, max_items=16, exposure="on_demand", usage="evidence_inventory"),
        InputPortSpec(name="prior_experiment", description="Optional exact previous experiment whose feedback this task addresses.",
            schema="scidiscovery.experiment-report.v1", media_types=("application/json",), codec=_REF("json_codec"),
            schema_resource=_REF("experiment_task_schema"), min_items=0, exposure="on_demand", usage="prior_signal"),
        InputPortSpec(name="scientific_files", description="Exact scientific binary materials, including simulation grids.",
            schema="opaque", media_types=("application/octet-stream",), codec=_REF("opaque_codec"),
            schema_resource=_REF("opaque_schema"), min_items=0, max_items=16, max_item_bytes=2_000_000_000,
            exposure="file_reference", usage="claim_evidence"),
    ),
    outputs=(
        OutputPortSpec(name="experiment", description="Complete experiment conclusion and adopted sealed stages.",
            schema="scidiscovery.experiment-report.v1", media_types=("application/json",), codec=_REF("json_codec"),
            schema_resource=_REF("experiment_task_schema"), kind="experiment_report", max_item_bytes=65536,
            validator=_REF("experiment_task_validator"), validator_rule_id="experiment.sealed_material",
            context_validator=_REF("experiment_completion_validator"), context_rule_id="experiment.sealed_material",
            context_sources=("tool_evidence",),
            semantic_contract=_REF("experiment_task_contract")),
        OutputPortSpec(name="tool_evidence", description="Sealed stages, implementations and execution observations.",
            schema="opaque", media_types=("application/json", "application/octet-stream", "text/plain", "text/csv"),
            codec=_REF("opaque_codec"), schema_resource=_REF("opaque_schema"), kind="experiment_material",
            min_items=0, max_items=64, max_item_bytes=32*1024*1024, collection=CollectionSpec(128*1024*1024)),
        OutputPortSpec(name="recovery_manifest_output", description="Control-retained provenance of sealed materials.",
            schema="scidiscovery.tool-evidence-manifest.v1", media_types=("application/json",), codec=_REF("json_codec"),
            schema_resource=_REF("tool_evidence_schema"), kind="tool_evidence_manifest", min_items=0, max_items=1,
            agent_visible=False,
            max_item_bytes=1024*1024, collection=CollectionSpec(1024*1024)),
    ), timeout=7200, max_input_bytes=32_100_000_000, max_output_bytes=130*1024*1024,
    max_files=66, max_attempts=2,
)
OPERATION = OPERATION.model_copy(update={"executor": OPERATION.executor.model_copy(update={
    "capability": _REF("experiment_task_protocol")})})
