"""Common scientific file publication; control owns immutable registration."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from .operations.tooling import WorkerToolDefinition
from .operation_contract import DiagnosticError, contract_diagnostic
from .plugin_runtime.workspace import WorkspaceError


class AttachmentFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=1024,
        description="Regular file below scratch/, relative to this workspace. No symlinks. Keep output/ for result.json.")
    purpose: str = Field(min_length=1, max_length=1024,
        description="Scientific meaning or intended use of this file; publication alone does not validate it.")


class PublishFiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: Annotated[tuple[AttachmentFile, ...], Field(min_length=1, max_length=64)]
    source_aliases: Annotated[tuple[str, ...], Field(min_length=1, max_length=128,
        description="Exact bound input or already published evidence aliases used to prepare these files.")]


def publish_files(request, context):
    try:
        return context.publish_files(request)
    except (ValueError, OSError, TimeoutError, WorkspaceError) as error:
        raise DiagnosticError("Scientific files could not be published", details=(contract_diagnostic(
            "attachment_publication_failed", phase="tool_execution", affected_action="tool_call",
            repairable=True, path="$.files", message=str(error)[:1024]),)) from error


PUBLISH_FILES_TOOL = WorkerToolDefinition(name="worker_publish_files",
    description="Publish task-authored CSV/JSON/images/scripts or other scientific files from scratch/. Supply paths, purpose and source aliases only. Control streams bytes, infers media types, assigns immutable references and retains files for downstream reading and UI download. The frozen attachments settings govern size, total and count budgets. Identical retries reuse receipts; changed bytes produce new references. Does not attest execution, validate science or authorize a solver.",
    input_model=PublishFiles, capability="scientific.publish_files", contextual_handler=publish_files,
    evidence_ports=("attachments", "recovery_manifest_output"))


class InputFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_name: str = Field(min_length=1, max_length=128,
        description="Exact input source_name or an already authorized evidence reference.")


def materialize_input(request, context):
    try:
        context.input_ref(request.source_name)  # Reject paths and undeclared sources.
    except ValueError as error:
        raise DiagnosticError("Unknown input source_name; choose an exact source_name from the assignment.") from error
    path = context.input_path(request.source_name)
    return {"source_name": request.source_name, "relative_path": str(path.relative_to(context.workspace)),
            "size_bytes": path.stat().st_size, "state": "available",
            "reading": "Use native file tools for PDFs, images or large tables; read bounded sections. This call returns no file contents."}


INPUT_TOOL = WorkerToolDefinition(name="worker_materialize_input",
    description="Make an exact bound input or authorized evidence reference available as a native file using streamed copying. Returns its local path, never bulk contents.",
    input_model=InputFileRequest, capability="material.input", contextual_handler=materialize_input)
