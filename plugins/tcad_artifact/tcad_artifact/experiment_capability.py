"""TCAD implementation tools contributed to the generic experiment task."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.operations.experiment import ExperimentCapability
from scidiscovery.plugin_runtime.experiment import ExperimentTools
from scidiscovery.operations.spec import ComponentRef, ComponentSpec
from scidiscovery.operations.tooling import WorkerToolDefinition
from scidiscovery.operation_contract import DiagnosticError, validation_diagnostics

from .execution_control import SolverCapabilitySnapshot
from .project_packager import (ScientificDeckImplementation, DeckProjectDraft, ResolvedProjectInput, ExecutionPackage)


class Implementation(ScientificDeckImplementation):
    """The shared scientific implementation; control supplies execution identity."""
    model_config = ConfigDict(json_schema_extra={**ScientificDeckImplementation.model_config["json_schema_extra"],
        "description":ScientificDeckImplementation.__doc__})
    solver_kind: Literal["sprocess", "sdevice"]


class PrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["schema", "prepare"] = "prepare"
    project_path: str = Field(default="scratch/experiment.json", max_length=1024,
        description="Workspace-relative implementation document using the tool's schema action.")
    method: str | None = Field(default=None, max_length=256,
        description="Choose an advertised solver method only when several match the requested solver.")
    scientific_files: dict[str, str] = Field(default_factory=dict,
        description="Map implementation input-slot names to exact supplied scientific-file aliases.")


def prepare(request, context):
    if request.action == "schema":
        return {"implementation_schema": Implementation.model_json_schema()}
    path = context.workspace / request.project_path
    if path.is_symlink() or not path.resolve().is_relative_to(context.workspace.resolve()):
        raise ValueError("The implementation must be a regular file inside this workspace.")
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("The implementation document is absent or exceeds its size limit.")
    try:
        authored = Implementation.model_validate_json(path.read_bytes(), strict=True)
    except ValidationError as error:
        raise DiagnosticError("The scientific implementation needs correction.",
            details=validation_diagnostics(error, schema=Implementation.model_json_schema())) from error
    service: ExperimentTools = context.require_service("experiment.execution")
    candidates = []
    for item in service.capabilities(context):
        capability = SolverCapabilitySnapshot.model_validate_json(item.content, strict=True)
        if capability.solver_kind == authored.solver_kind and (request.method is None or item.key == request.method):
            candidates.append(capability)
    if len(candidates) != 1:
        raise ValueError("Choose exactly one advertised method matching the implementation solver.")
    capability = candidates[0]
    values = authored.model_dump(mode="json")
    values.update(tool_profile=capability.profile_id, capability_sha256=capability.capability_sha256)
    project = DeckProjectDraft.model_validate_json(canonical_json(values), strict=True)
    slots = {slot.semantic_name: slot for slot in project.input_slots}
    if set(request.scientific_files) != set(slots):
        raise ValueError("Provide one exact scientific-file reference for each implementation input slot.")
    resolved = []
    for name, alias in request.scientific_files.items():
        source = context.source_descriptor(alias)
        slot = slots[name]
        if source.media_type != slot.media_type:
            raise ValueError("A scientific file has a different media type from its implementation slot.")
        resolved.append(ResolvedProjectInput(semantic_name=name, target_relative_path=slot.target_relative_path,
            artifact_ref=source.artifact_ref, media_type=source.media_type, size_bytes=source.size_bytes))
    package = ExecutionPackage(project=project, capability=capability, resolved_inputs=tuple(resolved))
    record = service.seal_implementation(context, payload=canonical_json(package.model_dump(mode="json")),
        scientific_material=canonical_json({"implementation": authored.model_dump(mode="json"),
            "scientific_files": request.scientific_files}),
        sources=("research_objective", *request.scientific_files.values()), private_outputs=("tcad_manifest",))
    return {"state": "sealed", "implementation": record["alias"], "solver": authored.solver_kind,
        "source_files": len(project.files), "scientific_files": len(resolved)}


class DebugInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["run", "cancel"] = "run"
    implementation: str | None = Field(default=None, max_length=128)
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    mode: Literal["preflight", "smoke", "initialization"] = "preflight"
    output_names: list[str] | None = None


def debug(request, context):
    from .debug_contract import TCADDebugSource
    from scidiscovery.plugin_runtime.workspace import write_control_workspace_file
    execution: ExperimentTools = context.require_service("experiment.execution")
    service = context.require_service("tcad.development_debug")
    if request.action == "cancel":
        active = execution.cancel_diagnostics(context, service_name="tcad.development_debug", name=request.name)
        return {"name":request.name, "state":"cancelling" if active else "inactive"}
    if request.implementation is None:
        raise ValueError("Choose a sealed implementation for this diagnostic.")
    sealed = execution.read_implementation(context, request.implementation)
    package_ref = sealed.artifact_ref
    package = ExecutionPackage.model_validate_json(sealed.content, strict=True)
    scientific = json.loads(context.read_evidence(request.implementation))
    aliases = scientific["scientific_files"]
    context.state.update(experiment_project=canonical_json(package.project.model_dump(mode="json")),
        experiment_implementation_ref=package_ref.model_dump(mode="json"),
        experiment_capability=canonical_json(package.capability.model_dump(mode="json")),
        experiment_sources=tuple(TCADDebugSource(source_name=slot.semantic_name,
            artifact_ref=context.source_descriptor(aliases[slot.semantic_name]).artifact_ref,
            media_type=slot.media_type, content=context.input_path(aliases[slot.semantic_name]))
            for slot in package.project.input_slots))
    # Old diagnostic receipts contain executor identities and policy details.
    # Keep that lossless workspace with the service, outside the Agent workspace.
    scoped = execution.diagnostic_context(context, service_name="tcad.development_debug")
    private = scoped.workspace
    response = service.run(scoped, run_name=request.name, mode=request.mode, output_names=request.output_names)
    result = {key: response[key] for key in ("state", "mode", "summary", "exit_code", "missing_outputs") if key in response}
    log = private / "deck/reports" / ("log-" + request.name + ".txt")
    if log.is_file():
        with log.open("rb") as stream:
            raw = stream.read(65537)
        relative = Path("scratch/debug") / request.name / "solver.log"
        write_control_workspace_file(context.workspace, relative, raw[:65536], replace=True, mode=0o400, create_parents=True)
        result.update(log=str(relative), log_truncated=len(raw) > 65536)
    if response.get("state") in {"collected", "succeeded", "failed", "cancelled"}:
        record = context.accept_evidence(raw=canonical_json(result), media_type="application/json",
            derived_from=("research_objective", request.implementation), metadata={"kind": "experiment_debug", "name": request.name})
        result["reference"] = record["alias"]
    return result


PREPARE_TOOL = WorkerToolDefinition(name="worker_experiment_prepare",
    description="Read the TCAD implementation schema or seal an implementation for the current experiment. Control resolves the exact active solver capability and supplied scientific files. No prior author or review task is required.",
    input_model=PrepareInput, capability="experiment.implementation", contextual_handler=prepare,
    required_services=("experiment.execution",), evidence_ports=("tool_evidence", "recovery_manifest_output"))
DEBUG_TOOL = WorkerToolDefinition(name="worker_experiment_debug", description="Run or poll an optional bounded diagnostic of the exact sealed implementation. Diagnostics do not count as formal execution or require a fixed sequence.",
    input_model=DebugInput, capability="experiment.debug", contextual_handler=debug,
    required_services=("experiment.execution", "tcad.development_debug"), evidence_ports=("tool_evidence", "recovery_manifest_output"))
CAPABILITY = ExperimentCapability(tools=(ComponentRef("experiment_prepare_tool"), ComponentRef("experiment_debug_tool")),
    instructions="Use the sentaurus-tcad-code Skill for SProcess or SDevice source. Author the scientific plan and standalone implementation in this workspace. Read worker_experiment_prepare(action=schema), write scratch/experiment.json, prepare it and execute its sealed reference. Scientific-file slots resolve exact supplied originals. No fixed development-mode checklist or prior design Run is required.",
    execution_operation="tcad.experiment.execute.internal", execution_package_schema_version=2)
COMPONENTS = (
    ComponentSpec("experiment_prepare_tool", "worker_tool", __name__ + ":PREPARE_TOOL"),
    ComponentSpec("experiment_debug_tool", "worker_tool", __name__ + ":DEBUG_TOOL"),
    ComponentSpec("experiment_capability", "experiment_capability", __name__ + ":CAPABILITY",
        resources=(ComponentRef("experiment_prepare_tool"), ComponentRef("experiment_debug_tool"), ComponentRef("runtime_factory")),
        extends=ComponentRef("experiment_task_protocol", "general_science")),
)
