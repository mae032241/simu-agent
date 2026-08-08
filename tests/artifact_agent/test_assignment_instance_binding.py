from __future__ import annotations

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.interfaces.mcp_worker import (
    WORKER_TOOLS,
    WorkerMCPRouter,
    WorkerToolError,
)
from scidiscovery.artifact_agent.interfaces.mcp_worker_daemon import (
    WorkerBrokerRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_worker_proxy import (
    PROXY_ID_FIELD,
    WORKER_ID_FIELD,
    bind_worker_identity,
)
from scidiscovery.artifact_agent.runtime import open_runtime


def _runtime(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance="test",
        )
    )
    return runtime, root


def _queue(root: RootMCPRouter, name: str, instruction: str) -> str:
    root.call_tool(
        "task_schedule",
        {
            "name": name,
            "role": "critic",
            "instruction": instruction,
            "inputs": [],
            "max_attempts": 2,
        },
    )
    assert root.call_tool(
        "task_prepare_dispatch",
        {"name": name, "ttl_seconds": 60},
    ) == {"task_name": name, "agent_type": "critic"}
    return name


def test_worker_tool_contract_contains_no_control_identity() -> None:
    rendered = json.dumps(
        [tool.schema() for tool in WORKER_TOOLS],
        sort_keys=True,
    ).lower()
    for forbidden in (
        "artifact_id",
        "dispatch_handle",
        "hash",
        "instance_id",
        "proxy_id",
        "session_token",
        "task_id",
    ):
        assert forbidden not in rendered


def test_two_same_role_proxies_atomically_bind_distinct_instances(
    tmp_path: Path,
) -> None:
    runtime, root = _runtime(tmp_path)
    task_names = {
        _queue(root, "candidate_a", "Review candidate A."),
        _queue(root, "candidate_b", "Review candidate B."),
    }
    workers = (
        WorkerMCPRouter(runtime.tasks, worker_id="critic", proxy_id="pxy_a"),
        WorkerMCPRouter(runtime.tasks, worker_id="critic", proxy_id="pxy_b"),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = tuple(pool.map(lambda worker: worker.call_tool("worker_claim_task", {}), workers))

    assert claims == ({"state": "claimed"}, {"state": "claimed"})
    assert {
        worker.call_tool("worker_get_assignment", {})["instruction"]
        for worker in workers
    } == {"Review candidate A.", "Review candidate B."}
    assert {
        root.call_tool("task_status", {"name": task_name})["state"]
        for task_name in task_names
    } == {"claimed"}
    task_ids = {
        runtime.scheduler_bindings.resolve(
            instance="test", namespace="task", name=task_name
        )
        for task_name in task_names
    }
    with sqlite3.connect(runtime.tasks.database_path) as connection:
        rows = connection.execute(
            """
            SELECT task_id, state, proxy_id, session_id
            FROM assignment_instances ORDER BY created_at
            """
        ).fetchall()
    assert len(rows) == 2
    assert {row[0] for row in rows} == task_ids
    assert {row[1] for row in rows} == {"bound"}
    assert {row[2] for row in rows} == {"pxy_a", "pxy_b"}
    assert len({row[3] for row in rows}) == 2


def test_proxy_can_open_only_one_assignment(tmp_path: Path) -> None:
    runtime, root = _runtime(tmp_path)
    _queue(root, "candidate_a", "Review candidate A.")
    _queue(root, "candidate_b", "Review candidate B.")
    worker = WorkerMCPRouter(
        runtime.tasks,
        worker_id="critic",
        proxy_id="pxy_single",
    )
    worker.call_tool("worker_claim_task", {})
    with pytest.raises(WorkerToolError, match="already owns"):
        worker.call_tool("worker_claim_task", {})


def test_wrong_role_cannot_consume_another_role_queue(tmp_path: Path) -> None:
    runtime, root = _runtime(tmp_path)
    task_name = _queue(root, "candidate_a", "Review candidate A.")
    worker = WorkerMCPRouter(
        runtime.tasks,
        worker_id="ideator",
        proxy_id="pxy_wrong_role",
    )
    with pytest.raises(Exception, match="no queued assignment"):
        worker.call_tool("worker_claim_task", {})
    assert root.call_tool("task_status", {"name": task_name})["state"] == "dispatched"


def test_proxy_transport_binding_cannot_be_supplied_by_model() -> None:
    request = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
    bound = json.loads(bind_worker_identity(request, "critic", "pxy_transport"))
    assert bound[WORKER_ID_FIELD] == "critic"
    assert bound[PROXY_ID_FIELD] == "pxy_transport"

    forged = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            PROXY_ID_FIELD: "pxy_forged",
        }
    ).encode()
    with pytest.raises(ValueError, match="transport-managed"):
        bind_worker_identity(forged, "critic", "pxy_transport")


def test_broker_keeps_assignment_bound_across_identity_free_tool_calls(
    tmp_path: Path,
) -> None:
    runtime, root = _runtime(tmp_path)
    _queue(root, "broker_candidate", "Review one broker-bound candidate.")
    broker = WorkerBrokerRouter(runtime)

    def call(proxy_id: str, name: str, arguments: dict | None = None) -> dict:
        response = broker.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
                WORKER_ID_FIELD: "critic",
                PROXY_ID_FIELD: proxy_id,
            }
        )
        assert response is not None
        return response

    claimed = call("pxy_broker", "worker_claim_task")
    assert claimed["result"]["structuredContent"] == {"state": "claimed"}
    assignment = call("pxy_broker", "worker_get_assignment")
    assert assignment["result"]["structuredContent"]["instruction"] == (
        "Review one broker-bound candidate."
    )

    unbound = call("pxy_other", "worker_get_assignment")
    assert unbound["error"]["message"] == "worker_claim_task must be called first"


def test_separate_control_and_worker_runtimes_share_instance_binding(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = tmp_path / "state"
    task_secret = os.urandom(32)
    approval_secret = os.urandom(32)
    control = open_runtime(
        project_root=project,
        state_root=state,
        task_token_secret=task_secret,
        approval_receipt_secret=approval_secret,
    )
    worker_runtime = open_runtime(
        project_root=project,
        state_root=state,
        task_token_secret=task_secret,
    )
    root = RootMCPRouter(
        RootToolFacade(
            control.artifacts,
            control.intake,
            tasks=control.tasks,
            approvals=control.approvals,
            executions=control.executions,
            bindings=control.scheduler_bindings,
            instance="test",
        )
    )
    task_name = _queue(root, "cross_service", "Review one cross-service candidate.")
    worker = WorkerMCPRouter(
        worker_runtime.tasks,
        worker_id="critic",
        proxy_id="pxy_cross_service",
    )

    assert worker.call_tool("worker_claim_task", {}) == {"state": "claimed"}
    assert worker.call_tool("worker_get_assignment", {})["instruction"] == (
        "Review one cross-service candidate."
    )
    assert root.call_tool("task_status", {"name": task_name})["state"] == "claimed"
