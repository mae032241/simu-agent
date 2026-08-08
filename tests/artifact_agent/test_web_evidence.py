from __future__ import annotations

import os
from email.message import Message
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_worker import WorkerMCPRouter
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.web_fetch import (
    FetchedWebEvidence,
    WebFetchError,
    fetch_web_evidence,
)


def _routers(tmp_path: Path) -> tuple[RootMCPRouter, object]:
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    return (
        RootMCPRouter(
            RootToolFacade(
                runtime.artifacts,
                runtime.intake,
                tasks=runtime.tasks,
                approvals=runtime.approvals,
                executions=runtime.executions,
                bindings=runtime.scheduler_bindings,
                instance="test",
            )
        ),
        runtime,
    )


def _claim(root: RootMCPRouter, runtime: object) -> tuple[str, WorkerMCPRouter]:
    task_name = "web_evidence"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "evidence_extractor",
            "instruction": "Freeze and cite one public source.",
            "inputs": [],
        },
    )
    root.call_tool(
        "task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60}
    )
    worker = WorkerMCPRouter(runtime.tasks, worker_id="evidence_extractor")
    worker.call_tool("worker_claim_task", {})
    return task_name, worker


def _intake(foundation: dict[str, object]) -> dict[str, object]:
    item_key = foundation["items"][0]["item_key"]
    return {
        "problem_frame": {
            "title": foundation["title"],
            "scientific_question": "What source-backed value is available?",
            "objective": foundation["objective"],
            "current_contradiction": "The required value is not yet source-bound.",
            "scope": "The supplied public source only.",
            "foundation_item_keys": [item_key],
            "observables": [
                {
                    "observable_key": "reported_value",
                    "description": "The source-backed reported value.",
                    "role": "target",
                    "foundation_item_keys": [item_key],
                    "acceptance_relevance": "The value must be traceable before use.",
                }
            ],
            "claim_boundary": {
                "allowed_claim": "The source reports the extracted value.",
                "required_conditions": ["The web evidence snapshot is frozen."],
            },
            "stop_conditions": ["The source binding is validated."],
        },
        "scientific_foundation": foundation,
    }


def test_public_fetch_rejects_private_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scidiscovery.artifact_agent.web_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(WebFetchError, match="public addresses"):
        fetch_web_evidence("https://example.test/source")


def test_public_fetch_rejects_invalid_port() -> None:
    with pytest.raises(WebFetchError, match="invalid port"):
        fetch_web_evidence("https://example.test:not-a-port/source")


def test_public_html_fetch_is_bounded_and_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "scidiscovery.artifact_agent.web_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    headers = Message()
    headers["Content-Type"] = "text/html; charset=utf-8"

    class Response:
        status = 200

        def __init__(self) -> None:
            self.headers = headers

        def read(self, size: int) -> bytes:
            return b"<html><style>hidden</style><body>Paper fact</body></html>"

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr(
        "scidiscovery.artifact_agent.web_fetch.urllib.request.build_opener",
        lambda *args: Opener(),
    )
    fetched = fetch_web_evidence("https://EXAMPLE.test/source#fragment")
    assert fetched.original_url == "https://example.test/source"
    assert fetched.text == "Paper fact"
    assert fetched.media_type == "text/html; charset=utf-8"


def test_worker_freezes_web_source_and_binds_it_to_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, runtime = _routers(tmp_path)
    task_name, worker = _claim(root, runtime)
    monkeypatch.setattr(
        "scidiscovery.artifact_agent.interfaces.mcp_worker.fetch_web_evidence",
        lambda url, max_chars: FetchedWebEvidence(
            original_url=url,
            final_url=url,
            accessed_at="2026-08-03T12:00:00.000000Z",
            http_status=200,
            media_type="text/html; charset=utf-8",
            body=b"<html><body>DA=1.05e-12</body></html>",
            text="DA=1.05e-12",
            text_truncated=False,
        ),
    )
    fetched = worker.call_tool(
        "worker_fetch_web_evidence",
        {"url": "https://example.org/paper"},
    )
    assert fetched["source_key"] == "web_1"
    assert "artifact" not in str(fetched).lower()
    worker.call_tool(
        "worker_finalize",
        {
            "content": {
                "schema_version": 1,
                "handoff": {"verdict": "pass", "summary": "Evidence frozen."},
                "payload": _intake({
                "title": "One sourced diffusion coefficient",
                "objective": "Freeze one public coefficient for review.",
                "summary": "One source-backed coefficient was extracted.",
                "evidence": [
                    {
                        "source_key": "web_1",
                        "source_type": "web_snapshot",
                        "title": "Example paper",
                        "locator": "body text",
                        "excerpt": "DA=1.05e-12",
                    }
                ],
                "items": [
                    {
                        "item_key": "da_value",
                        "item_type": "parameter",
                        "statement": "DA is reported as 1.05e-12 cm2/s.",
                        "epistemic_status": "paper_fact",
                        "value": 1.05e-12,
                        "unit": "cm^2/s",
                        "scope": "Reported diffusion coefficient in the cited source.",
                        "evidence_keys": ["web_1"],
                    }
                ],
                }),
            },
        },
    )
    sources = root.call_tool("task_evidence_sources", {"name": task_name})
    assert sources["sources"][0]["source_label"] == "web_1"
    output_name = root.call_tool("task_status", {"name": task_name})["output_artifact_name"]
    output_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="artifact", name=output_name
    )
    output = runtime.artifacts.get_by_id(output_id)
    source_id = runtime.scheduler_bindings.resolve(
        instance="test",
        namespace="artifact",
        name=sources["sources"][0]["artifact_name"],
    )
    assert any(
        parent.artifact_id == source_id
        for parent in output.parent_refs
    )


def test_unfrozen_web_source_cannot_be_finalized(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    _, worker = _claim(root, runtime)
    rejected = worker.call_tool(
        "worker_finalize",
        {
            "content": {
                "schema_version": 1,
                "handoff": {"verdict": "pass", "summary": "Should fail."},
                "payload": _intake({
                    "title": "Unsupported foundation",
                    "objective": "Demonstrate rejection of an unfrozen source.",
                    "summary": "Unsupported web statement.",
                    "evidence": [
                        {
                            "source_key": "web_1",
                            "source_type": "web_snapshot",
                            "title": "Unknown source",
                            "locator": "unknown",
                        }
                    ],
                    "items": [
                        {
                            "item_key": "unsupported",
                            "item_type": "fact",
                            "statement": "An unsupported web fact.",
                            "epistemic_status": "paper_fact",
                            "scope": "Unspecified scope.",
                            "evidence_keys": ["web_1"],
                        }
                    ],
                }),
            },
        },
    )
    assert rejected["state"] == "rejected"
    assert rejected["errors"][0]["path"] == (
        "$.payload.scientific_foundation.evidence[0].source_key"
    )
