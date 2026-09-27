"""Registered deterministic table-summary Worker tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.operations.tooling import WorkerToolDefinition

from .analysis import summarize_csv


class TableSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _summarize(
    request: BaseModel, context: OperationToolContext
) -> dict[str, object]:
    if not isinstance(request, TableSummaryRequest):
        raise ValueError("table summary request has the wrong type")
    summary = summarize_csv(context.read_input("observation_table"))
    context.record_activity("deterministic_analysis_completed")
    return summary.model_dump(mode="json")


TABLE_SUMMARY_TOOL = WorkerToolDefinition(
    name="worker_table_summarize",
    description="Summarize the exact bound CSV structure and numeric columns.",
    input_model=TableSummaryRequest,
    capability="analysis.table",
    contextual_handler=_summarize,
)


__all__ = ["TABLE_SUMMARY_TOOL", "TableSummaryRequest"]
