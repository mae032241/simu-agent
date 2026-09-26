"""Prepare optional native collaboration without creating another scientific Run."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .operations.tooling import WorkerToolDefinition


class HelperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$", description="Scientific subtask name, also used as the native task name.")
    action: Literal["prepare", "release"] = "prepare"
    task: str = Field(default="", max_length=16384, description="Bounded scientific question, investigation, code change or already authorized local validation.")
    materials: list[str] = Field(default_factory=list, max_length=16,
        description="Select relevant input source_name aliases or task workspace paths for the helper's initial navigation. No materials are expanded by default; unknown references remain gaps. The helper can investigate further within the parent's existing permissions.")


def call_helper(request, context):
    return context.require_service("worker.connections").helper_request(context.run_id, request)


HELPER_TOOL = WorkerToolDefinition(
    name="worker_helper", capability="run.internal_helper", owner_only=True,
    description=("Prepare an optional native helper subtask, then use the returned native dispatch instructions with fresh context. "
        "The helper inherits this task's workspace, Skills and allowed tools; you wait for the native completion notification, "
        "verify and integrate its findings or files, and remain responsible for final delivery. "
        "Use existing deterministic tools for simple counts, slopes or ranges; delegate a complete subproblem when independent investigation or context relief is useful. "
        "For findings that affect your conclusion, explain adoption and its limits, or reasons for rejecting important suggestions, "
        "in the existing analysis_method, evidence or stage narrative; no helper IDs or separate adoption form are needed. "
        "Release ends the named helper's Run tool access; use native stop/close for its thread. Release does not assert termination. "
        "No Root handoff, extra approval, formal review receipt or helper-result polling is required."),
    input_model=HelperRequest, contextual_handler=call_helper,
    required_services=("worker.connections",),
)
