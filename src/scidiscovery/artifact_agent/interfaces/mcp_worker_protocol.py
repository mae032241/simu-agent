"""Worker MCP input protocol and the single built-in tool projection."""

from __future__ import annotations

from ...operation_contract import DiagnosticError

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...operations.lifecycle import AGENT_LIFECYCLE_PROTOCOL, AgentLifecycleInput, AgentHistoryInput
from ...operations.tooling import WorkerToolDefinition
from ..service.local_pdf_tool import extract_pdf_text_local

class WorkerToolError(DiagnosticError):
    pass

class WorkerToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

class NamedInput(WorkerToolInput):
    name: str = Field(min_length=1, max_length=256)

class PdfInput(NamedInput):
    first_page: int = Field(default=1, ge=1, le=100000)
    last_page: int | None = Field(default=None, ge=1, le=100000)
    max_chars: int = Field(default=131072, ge=1, le=524288)

@dataclass(frozen=True)
class WorkerTool:
    name: str
    description: str
    input_model: type[BaseModel]
    owner_only: bool = False

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }

LIFECYCLE_WORKER_TOOLS = tuple(
    WorkerTool(item.name, item.description, AgentHistoryInput if item.name == "worker_read_history" else AgentLifecycleInput, item.owner_only)
    for item in AGENT_LIFECYCLE_PROTOCOL.tools
)

REGISTERABLE_WORKER_TOOLS = (
    WorkerTool("worker_extract_pdf_text", "Freeze a bounded PDF page range and return its exact local read-only path for native inspection.", PdfInput),
)

# Only lifecycle tools are intrinsic. Every other tool reaches a Worker through
# an exact OperationSpec component reference.
WORKER_TOOLS = LIFECYCLE_WORKER_TOOLS

_TOOL_CAPABILITY = {
    "worker_extract_pdf_text": "input.extract_pdf_text",
}

def _builtin_tool_component(name: str) -> WorkerToolDefinition:
    tool = next(item for item in REGISTERABLE_WORKER_TOOLS if item.name == name)
    return WorkerToolDefinition(
        name=tool.name,
        description=tool.description,
        input_model=tool.input_model,
        capability=_TOOL_CAPABILITY[name],
        local_contextual_handler=extract_pdf_text_local,
    )



EXTRACT_PDF_TEXT_TOOL = _builtin_tool_component("worker_extract_pdf_text")
