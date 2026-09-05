#!/usr/bin/env python3
"""Emit current R5 metrics while preserving the immutable R5-0 generator."""

from __future__ import annotations

import json
from pathlib import Path

import r5_baseline_metrics as baseline


ROOT_OWNER = "src/scidiscovery/artifact_agent/interfaces/mcp_root.py"
ROOT_SUCCESSORS = (
    ROOT_OWNER,
    "src/scidiscovery/artifact_agent/interfaces/mcp_root_shared.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_root_approval_routes.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_root_execution_routes.py",
)
TASK_OWNER = "src/scidiscovery/artifact_agent/service/tasks.py"
TASK_SUCCESSORS = (
    "src/scidiscovery/artifact_agent/service/runs.py",
    "src/scidiscovery/artifact_agent/service/run_assignment.py",
    "src/scidiscovery/artifact_agent/service/run_current.py",
    "src/scidiscovery/artifact_agent/service/run_outputs.py",
    "src/scidiscovery/artifact_agent/service/run_records.py",
    "src/scidiscovery/artifact_agent/service/local_workspace.py",
    "src/scidiscovery/artifact_agent/service/hardened_workspace.py",
    "src/scidiscovery/artifact_agent/service/hardened_files.py",
    "src/scidiscovery/artifact_agent/service/local_pdf_tool.py",
    "src/scidiscovery/artifact_agent/operation_tool_context.py",
)
WORKER_OWNER = "src/scidiscovery/artifact_agent/interfaces/mcp_worker.py"
WORKER_SUCCESSORS = (
    "src/scidiscovery/artifact_agent/interfaces/mcp_worker_protocol.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_hardened_worker.py",
)
SCHEDULER_OWNER = "src/scidiscovery/scheduler_topology.py"
SCHEDULER_SUCCESSORS = (
    "src/scidiscovery/platforms/scheduler_prompt.py",
)
ROLES_OWNER = "src/scidiscovery/platforms/roles.py"
ROLES_SUCCESSORS = (
    "src/scidiscovery/platforms/codex.py",
)
GENERAL_PLUGIN_OWNER = "src/scidiscovery/general_science_plugin.py"
GENERAL_PLUGIN_SUCCESSORS = (
    GENERAL_PLUGIN_OWNER,
    "src/scidiscovery/general_science_resources.py",
    "src/scidiscovery/general_science_agent_operations.py",
    "src/scidiscovery/general_science_experiment_operations.py",
)
GENERAL_TRANSFORM_OWNER = "src/scidiscovery/general_transform_operations.py"
GENERAL_TRANSFORM_SUCCESSORS = (
    "src/scidiscovery/general_science_components.py",
    "src/scidiscovery/general_science_control_operations.py",
    "src/scidiscovery/general_science_experiment_components.py",
)


def collect_current(repository: Path) -> dict[str, object]:
    baseline.RESPONSIBILITY_SUCCESSORS = {
        **baseline.RESPONSIBILITY_SUCCESSORS,
        ROOT_OWNER: ROOT_SUCCESSORS,
        TASK_OWNER: TASK_SUCCESSORS,
        WORKER_OWNER: WORKER_SUCCESSORS,
        SCHEDULER_OWNER: SCHEDULER_SUCCESSORS,
        ROLES_OWNER: ROLES_SUCCESSORS,
        GENERAL_PLUGIN_OWNER: GENERAL_PLUGIN_SUCCESSORS,
        GENERAL_TRANSFORM_OWNER: GENERAL_TRANSFORM_SUCCESSORS,
    }
    successors = tuple(
        path
        for paths in baseline.RESPONSIBILITY_SUCCESSORS.values()
        for path in paths
    )
    if len(successors) != len(set(successors)):
        raise RuntimeError("responsibility successor paths must be globally unique")
    missing = tuple(path for path in successors if not (repository / path).is_file())
    if missing:
        raise RuntimeError(f"responsibility successor paths do not exist: {missing}")
    metrics = baseline.collect(repository)
    responsibilities = metrics["responsibilities"]
    r0_core = metrics["r0_core"]
    current_lines = {
        owner: responsibilities[owner]["total_lines"]
        for owner in r0_core["paths"]
    }
    r0_core["r5_0_lines"] = current_lines
    r0_core["r5_0_total"] = sum(current_lines.values())
    r0_core["current_aggregation"] = "responsibility_successors"
    return metrics


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    print(json.dumps(collect_current(repository), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
