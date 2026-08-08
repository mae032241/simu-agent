from __future__ import annotations

import json
import threading
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_worker_proxy import (
    PROXY_ID_FIELD,
    WORKER_ID_FIELD,
    _AutomaticLeaseKeeper,
)


def _response(state: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "test",
        "result": {"structuredContent": {"state": state}},
    }


def test_proxy_renews_claim_without_agent_authored_heartbeat() -> None:
    called = threading.Event()

    def forward(socket_path: Path, raw: bytes, *, timeout: float):
        assert socket_path == Path("/tmp/worker.sock")
        assert timeout == 1.0
        request = json.loads(raw)
        assert request[WORKER_ID_FIELD] == "tcad_deck_author"
        assert request[PROXY_ID_FIELD] == "pxy_test"
        assert request["params"] == {
            "name": "worker_heartbeat",
            "arguments": {},
        }
        called.set()
        return _response("claimed")

    keeper = _AutomaticLeaseKeeper(
        socket_path=Path("/tmp/worker.sock"),
        worker_id="tcad_deck_author",
        proxy_id="pxy_test",
        timeout=1.0,
        interval=0.01,
        forward=forward,
    )
    keeper.observe(
        {"method": "tools/call", "params": {"name": "worker_claim_task"}},
        _response("claimed"),
    )
    assert called.wait(0.5)
    keeper.observe(
        {"method": "tools/call", "params": {"name": "worker_finalize"}},
        _response("completed"),
    )
    assert keeper._stop.is_set()


def test_proxy_does_not_start_for_failed_claim() -> None:
    keeper = _AutomaticLeaseKeeper(
        socket_path=Path("/tmp/worker.sock"),
        worker_id="critic",
        proxy_id="pxy_test",
        timeout=1.0,
        interval=1.0,
    )
    keeper.observe(
        {"method": "tools/call", "params": {"name": "worker_claim_task"}},
        {"jsonrpc": "2.0", "id": "test", "error": {"code": -32000}},
    )
    assert keeper._thread is None
