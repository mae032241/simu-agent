"""Prepare optional native collaboration without creating another scientific Run."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .operations.tooling import WorkerToolDefinition


class HelperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$", description="Scientific subtask name, also used as the native task name.")
    action: Literal["prepare", "release"] = "prepare"
    profile: Literal["inherit", "lightweight"] | None = Field(default=None,
        description="Optional helper model profile; omission uses configured default. inherit matches the parent; lightweight requires an explicitly configured smaller model; use inherit when uncertain. Both keep the same permitted tools.")
    task: str = Field(default="", max_length=16384, description="Bounded scientific question, investigation, code change or already authorized local validation.")
    materials: list[str] = Field(default_factory=list, max_length=16,
        description="Select relevant input source_name aliases or task workspace paths for the helper's initial navigation. No materials are expanded by default; unknown references remain gaps. The helper can investigate further within the parent's existing permissions.")


def call_helper(request, context):
    return context.require_service("worker.connections").helper_request(context.run_id, request)


HELPER_TOOL = WorkerToolDefinition(
    name="worker_helper", capability="run.internal_helper", owner_only=True,
    description=("Prepare one bounded helper question with exact materials and relevant goal/constraints. "
        "Then dispatch with the returned frozen model/reasoning_effort and fresh context; no guessed identities or upgrades. "
        "Omit profile for the configured default; inherit matches the parent, lightweight requires configuration. "
        "The helper reads its own assignment and reporting rules, sharing the parent's workspace and permissions. "
        "Wait for native completion, verify originals supporting adopted claims and consequential counterevidence, and integrate findings and limitations. "
        "Reports are navigation, not verified evidence; you remain responsible. Independent analysis uses its own helper. "
        "Group related materials into one question; use deterministic tools for trivial computations. "
        "Release revokes Run tool access, not native execution; use native stop/close to terminate. "
        "This creates no Root task, approval or formal review; no helper-result polling is needed."),
    input_model=HelperRequest, contextual_handler=call_helper,
    required_services=("worker.connections",),
)
