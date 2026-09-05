"""Worker MCP input protocol and the single built-in tool projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...operations.lifecycle import AGENT_LIFECYCLE_PROTOCOL, AgentLifecycleInput
from ...operations.tooling import WorkerToolDefinition
from ..service.local_pdf_tool import extract_pdf_text_local

class WorkerToolError(RuntimeError):
    pass

class WorkerToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

class NamedInput(WorkerToolInput):
    name: str = Field(min_length=1, max_length=256)

class PdfInput(NamedInput):
    first_page: int = Field(default=1, ge=1, le=100000)
    last_page: int | None = Field(default=None, ge=1, le=100000)
    max_chars: int = Field(default=131072, ge=1, le=524288)

class WorkerFilePathInput(WorkerToolInput):
    relative_path: str = Field(min_length=1, max_length=1024)

class WorkerFileWriteBeginInput(WorkerFilePathInput):
    expected_bytes: int | None = Field(default=None, ge=0, le=64 * 1024 * 1024)
    operation: Literal["create", "patch"] = "create"

class WorkerFileWriteChunkInput(WorkerToolInput):
    content: str = Field(max_length=90000)
    encoding: Literal["utf8", "base64"] = "utf8"

class WorkerFilePatchInput(WorkerFilePathInput):
    patch: str = Field(min_length=1, max_length=65536)

class WorkerJsonPatchOperation(WorkerToolInput):
    op: Literal["test", "add", "replace", "remove"]
    path: str = Field(min_length=1, max_length=1024)
    value: Any | None = None

    @model_validator(mode="after")
    def _value_matches_operation(self) -> WorkerJsonPatchOperation:
        has_value = "value" in self.model_fields_set
        if self.op == "remove" and has_value:
            raise ValueError("remove operation must not declare value")
        if self.op != "remove" and not has_value:
            raise ValueError("test, add, and replace operations require value")
        return self

class WorkerFileJsonPatchInput(WorkerFilePathInput):
    operations: tuple[WorkerJsonPatchOperation, ...] = Field(
        min_length=1, max_length=128
    )
    expected_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def _patch_has_compare_and_swap_guard(self) -> WorkerFileJsonPatchInput:
        if self.expected_digest is None and not any(
            item.op == "test" for item in self.operations
        ):
            raise ValueError(
                "JSON patch requires expected_digest or at least one test operation"
            )
        return self

class WorkerFileMoveInput(WorkerToolInput):
    source_relative_path: str = Field(min_length=1, max_length=1024)
    destination_relative_path: str = Field(min_length=1, max_length=1024)

@dataclass(frozen=True)
class WorkerTool:
    name: str
    description: str
    input_model: type[BaseModel]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }

LIFECYCLE_WORKER_TOOLS = tuple(
    WorkerTool(item.name, item.description, AgentLifecycleInput)
    for item in AGENT_LIFECYCLE_PROTOCOL.tools
)

REGISTERABLE_WORKER_TOOLS = (
    WorkerTool("worker_extract_pdf_text", "Freeze a bounded PDF page range and return its exact local read-only path for native inspection.", PdfInput),
    WorkerTool("worker_file_write_begin", "Begin a bounded new-file creation or chunked Codex patch. Omit expected_bytes for server-counted UTF-8; do not use TextEncoder. Existing files cannot be replaced wholesale.", WorkerFileWriteBeginInput),
    WorkerTool("worker_file_write_chunk", "Append one bounded UTF-8 or base64 chunk. Pass source as ordinary quoted strings or arrays of lines, never a JavaScript template literal containing Tcl ${...}.", WorkerFileWriteChunkInput),
    WorkerTool("worker_file_write_commit", "Atomically publish the complete active create-or-patch operation.", WorkerToolInput),
    WorkerTool("worker_file_apply_patch", "Apply one native Codex `*** Begin Patch`/`*** Update File` patch without hunk line counts, or one legacy standard unified diff, to an existing Run-relative text file; reject stale or ambiguous context atomically, then require a fresh read before another patch.", WorkerFilePatchInput),
    WorkerTool("worker_file_json_patch", "Atomically apply bounded JSON Pointer test/add/replace/remove operations to one existing Run-relative JSON file. Guard the update with the current content digest or a test operation; no textual context matching is used.", WorkerFileJsonPatchInput),
    WorkerTool("worker_file_delete", "Delete one optional Run-relative output file.", WorkerFilePathInput),
    WorkerTool("worker_file_move", "Move one optional Run-relative output file without rewriting its content.", WorkerFileMoveInput),
)

# Only lifecycle tools are intrinsic. Every other tool reaches a Worker through
# an exact OperationSpec component reference.
WORKER_TOOLS = LIFECYCLE_WORKER_TOOLS

_TOOL_CAPABILITY = {
    "worker_extract_pdf_text": "input.extract_pdf_text",
    "worker_file_write_begin": "file.chunked_write",
    "worker_file_write_chunk": "file.chunked_write",
    "worker_file_write_commit": "file.chunked_write",
    "worker_file_apply_patch": "file.unified_patch",
    "worker_file_json_patch": "file.unified_patch",
    "worker_file_delete": "file.move_delete",
    "worker_file_move": "file.move_delete",
}

def _builtin_tool_component(name: str) -> WorkerToolDefinition:
    tool = next(item for item in REGISTERABLE_WORKER_TOOLS if item.name == name)
    return WorkerToolDefinition(
        name=tool.name,
        description=tool.description,
        input_model=tool.input_model,
        capability=_TOOL_CAPABILITY[name],
        local_contextual_handler=(
            extract_pdf_text_local if name == "worker_extract_pdf_text" else None
        ),
    )
FILE_WRITE_BEGIN_TOOL = _builtin_tool_component("worker_file_write_begin")

FILE_WRITE_CHUNK_TOOL = _builtin_tool_component("worker_file_write_chunk")

FILE_WRITE_COMMIT_TOOL = _builtin_tool_component("worker_file_write_commit")

EXTRACT_PDF_TEXT_TOOL = _builtin_tool_component("worker_extract_pdf_text")

FILE_APPLY_PATCH_TOOL = _builtin_tool_component("worker_file_apply_patch")

FILE_JSON_PATCH_TOOL = _builtin_tool_component("worker_file_json_patch")

FILE_DELETE_TOOL = _builtin_tool_component("worker_file_delete")

FILE_MOVE_TOOL = _builtin_tool_component("worker_file_move")
