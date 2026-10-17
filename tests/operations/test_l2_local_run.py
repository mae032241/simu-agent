from __future__ import annotations

from dataclasses import fields

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext


def test_operation_tool_context_contains_no_control_authority() -> None:
    names = {item.name for item in fields(OperationToolContext)}
    assert not names.intersection(
        {"run", "task", "task_id", "session", "session_token", "proxy", "worker_id", "database", "current"}
    )
