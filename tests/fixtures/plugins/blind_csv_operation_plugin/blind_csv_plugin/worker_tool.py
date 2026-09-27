"""One deterministic domain tool registered by the blind CSV plugin."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.operations.tooling import WorkerToolDefinition

from .contracts import summarize_csv


class SummarizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def summarize(request: BaseModel, context: OperationToolContext) -> dict[str, object]:
    if not isinstance(request, SummarizeRequest):
        raise ValueError("wrong blind CSV request type")
    return summarize_csv(context.read_input("source_table")).model_dump(mode="json")


CSV_SUMMARY_TOOL = WorkerToolDefinition(
    name="worker_csv_summarize",
    description="Summarize the exact bound CSV without scientific interpretation.",
    input_model=SummarizeRequest,
    capability="analysis.csv",
    contextual_handler=summarize,
)


__all__ = ["CSV_SUMMARY_TOOL", "SummarizeRequest"]
