"""Prepare optional native collaboration without creating another scientific Run."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .operations.tooling import WorkerToolDefinition


class HelperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$", description="Scientific subtask name, also used as the native task name.")
    action: Literal["prepare", "release"] = "prepare"
    profile: Literal["inherit", "lightweight"] | None = Field(default=None,
        description="Optional helper model profile; omission uses configured default. inherit matches the parent; lightweight uses the configured smaller model. Both keep the same permitted tools.")
    task: str = Field(default="", max_length=16384, description="Bounded scientific question, investigation, code change or already authorized local validation.")
    materials: list[str] = Field(default_factory=list, max_length=16,
        description="Select relevant input source_name aliases or task workspace paths for the helper's initial navigation. No materials are expanded by default; unknown references remain gaps. The helper can investigate further within the parent's existing permissions.")


def call_helper(request, context):
    return context.require_service("worker.connections").helper_request(context.run_id, request)


HELPER_TOOL = WorkerToolDefinition(
    name="worker_helper", capability="run.internal_helper", owner_only=True,
    description=("Prepare a native helper subtask, then use the returned native dispatch instructions with fresh context. "
        "Choose inherit for parent-level model capability or lightweight for bounded work suited to the configured smaller model. "
        "Use the returned frozen model/reasoning_effort when spawning; never guess or silently upgrade. "
        "The helper inherits this task's workspace, Skills and allowed tools; you wait for the native completion notification, "
        "verify and integrate its findings or files, and remain responsible for final delivery. "
        "Use existing deterministic tools for simple counts, slopes or ranges; delegate a complete subproblem when independent investigation or context relief is useful. "
        "Bulk original reading is delegated by default under the startup material_division policy; small materials and the owner's task/constraint/form contracts remain directly readable. "
        "For a reading subtask, specify one decision question, exact source aliases or paths and the relevant original goal and constraints. "
        "Group related materials for that question rather than dispatching per file; reuse sufficient exact-source reports when context and scope still apply, except for independent analysis. "
        "Ask for supporting and contrary evidence, exact original aliases and pointers/line locators with short quotes, inspected scope, omissions/unread ranges and uncertainty. "
        "A prepares its own reading helper over originals; do not reuse W's filtered report as independent analysis. "
        "Reports guide original reading and retain attributed author claims; they do not replace evidence, verify science or grant authority. "
        "For findings that affect your conclusion, explain adoption and its limits, or reasons for rejecting important suggestions, "
        "in the existing analysis_method, evidence or stage narrative; no helper IDs or separate adoption form are needed. "
        "Release ends the named helper's Run tool access; use native stop/close for its thread. Release does not assert termination. "
        "No Root handoff, extra approval, formal review receipt or helper-result polling is required."),
    input_model=HelperRequest, contextual_handler=call_helper,
    required_services=("worker.connections",),
)
