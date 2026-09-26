"""Original user text through the actual Root router and immutable runtime."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter, parse_rpc_line
from scidiscovery.artifact_agent.interfaces.mcp_gateway import GATEWAY_TOOLS, UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    ROOT_TOOLS,
    RootMCPRouter,
    RootToolError,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.service.intake import UnsafeSourcePathError
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameConflict
from scidiscovery.platforms.codex import SCHEDULER_TOOLS, _proxy_server_toml


def _root(runtime, instance_id):
    return RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance_id,
            operation_catalog=runtime.operation_catalog,
        )
    )


@pytest.fixture
def ingress(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        actor_id="actual_scheduler_service",
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="user_text_ingress",
        title="User text ingress",
        objective="Preserve original user text as an immutable input.",
    )
    return runtime, instance.instance_id, _root(runtime, instance.instance_id)


def _envelope(runtime, instance_id, name):
    artifact_id = runtime.scheduler_bindings.resolve(
        instance=instance_id, namespace="artifact", name=name
    )
    return runtime.artifacts.get_by_id(artifact_id)


def _wire(root, arguments):
    request = parse_rpc_line(json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "artifact_ingest_text", "arguments": arguments},
    }))
    return MCPRouter(root, name="user-text-ingress").handle(request)


def test_text_schema_and_generated_scheduler_tools_share_root_declaration(ingress):
    _, _, root = ingress
    tools = root.list_tools()
    schema = next(tool["inputSchema"] for tool in tools
                  if tool["name"] == "artifact_ingest_text")
    assert set(schema["properties"]) == {"name", "text", "on_conflict"}
    assert set(schema["required"]) == {"name", "text"}
    assert schema["properties"]["text"]["type"] == "string"
    assert schema["properties"]["text"]["minLength"] == 1
    assert schema["properties"]["text"]["maxLength"] == 8192
    assert schema["additionalProperties"] is False
    assert schema["properties"]["on_conflict"]["default"] == "reject"

    declared_names = tuple(tool.name for tool in ROOT_TOOLS if tool.surface == "research")
    assert tuple(tool["name"] for tool in tools) == declared_names
    assert SCHEDULER_TOOLS == GATEWAY_TOOLS
    gateway = UnifiedMCPRouter(root)
    # The logical text-ingress contract remains reachable through the new public help.
    described = gateway.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "scid_describe", "arguments": {"name": "artifact_ingest_text"},
        "_meta": {"x-codex-turn-metadata": {
            "session_id": "ingress-root", "thread_id": "ingress-root", "thread_source": "user"}}}})
    assert described["result"]["structuredContent"]["inputSchema"] == schema
    generated = tomllib.loads(_proxy_server_toml(
        python=Path(sys.executable),
        socket_path=Path("/tmp/user-text-ingress.sock"),
        python_path=None,
    ))
    assert generated["mcp_servers"]["scidiscovery"]["enabled_tools"] == list(GATEWAY_TOOLS)


def test_original_unicode_and_whitespace_are_frozen_without_project_files_or_runs(ingress):
    runtime, instance_id, root = ingress
    before_files = tuple(sorted(runtime.project_root.rglob("*")))
    before_current = root.call_tool("scientific_current", {})
    texts = (
        " ",
        " \t\r\n ",
        " \t用户原话\r\n第二行 🧪\ne\u0301 与 é\r\n",
        "a" * 8192,
        "🧪" * 8192,
    )
    for index, text in enumerate(texts):
        name = f"original_{index}"
        response = _wire(root, {"name": name, "text": text})
        assert "error" not in response, response
        bound = response["result"]["structuredContent"]
        assert bound == {"name": name, "logical_name": name, "revision": 1, "state": "bound"}
        envelope = _envelope(runtime, instance_id, name)
        assert runtime.artifacts.read(envelope.ref) == text.encode("utf-8")
        assert envelope.size_bytes == len(text.encode("utf-8"))
        assert envelope.kind == "source_text"
        assert envelope.schema_id == "opaque"
        assert envelope.payload_schema_version == 1
        assert envelope.media_type == "text/plain; charset=utf-8"
        assert envelope.labels == {"source_origin": "user_via_scheduler"}
        assert envelope.creator == runtime.actor
        assert envelope.creator.actor_type == "service"
        assert envelope.parent_refs == ()
        metadata = root.call_tool("artifact_catalog", {"name": name, "view": "detail"})
        assert "labels" not in metadata  # Exact metadata remains control-owned.
    assert _envelope(runtime, instance_id, "original_4").size_bytes == 32768
    assert tuple(sorted(runtime.project_root.rglob("*"))) == before_files
    assert runtime.runs.list(instance_id=instance_id) == ()
    assert runtime.scheduler_bindings.list(instance=instance_id, namespace="run") == ()
    assert root.call_tool("scientific_current", {}) == before_current


def test_invalid_text_is_rejected_at_text_without_registration(ingress):
    runtime, instance_id, root = ingress
    invalid = (
        ("", "string_too_short", "Minimum length is 1."),
        ("a" * 8193, "string_too_long", "Maximum length is 8192."),
        ("🧪" * 8193, "string_too_long", "Maximum length is 8192."),
        ("\ud800", "value_error", "UTF-8"),
        ("\udc00", "value_error", "UTF-8"),
        ("原话\ud800", "value_error", "UTF-8"),
        (None, "string_type", "Expected a string."),
        (1, "string_type", "Expected a string."),
        (True, "string_type", "Expected a string."),
        (["text"], "string_type", "Expected a string."),
    )
    before_files = tuple(sorted(runtime.project_root.rglob("*")))
    before_artifacts = runtime.artifacts.list_artifacts()
    for text, error_type, message in invalid:
        response = _wire(root, {"name": "invalid", "text": text})
        assert "error" in response, response
        detail, = response["error"]["data"]["diagnostics"]
        assert detail["path"] == "$.text"
        assert detail["type"] == error_type
        assert detail["code"] == "invalid_arguments"
        assert message in detail["message"]
    # Python callers must not gain coercions absent from the JSON contract.
    with pytest.raises(RootToolError) as caught:
        root.call_tool("artifact_ingest_text", {"name": "invalid", "text": b"text"})
    assert caught.value.details[0]["path"] == "$.text"
    assert caught.value.details[0]["type"] == "string_type"
    assert runtime.artifacts.list_artifacts() == before_artifacts
    assert runtime.scheduler_bindings.list(instance=instance_id, namespace="artifact") == ()
    assert runtime.runs.list(instance_id=instance_id) == ()
    assert tuple(sorted(runtime.project_root.rglob("*"))) == before_files


def test_text_replay_revision_and_restart_keep_original_bytes(ingress):
    runtime, instance_id, root = ingress
    original = " 原始说明 e\u0301\r\n"
    request = {"name": "user_note", "text": original}
    first = root.call_tool("artifact_ingest_text", request)
    first_envelope = _envelope(runtime, instance_id, first["name"])
    assert root.call_tool("artifact_ingest_text", request) == first
    assert len(runtime.artifacts.list_artifacts()) == 1
    revised_text = " 原始说明 é\r\n"
    with pytest.raises(SchedulerNameConflict):
        root.call_tool("artifact_ingest_text", {**request, "text": revised_text})
    assert len(runtime.artifacts.list_artifacts()) == 1
    revision_request = {
        **request, "text": revised_text, "on_conflict": "create_revision"
    }
    revision = root.call_tool("artifact_ingest_text", revision_request)
    assert revision["revision"] == 2
    assert revision["logical_name"] == first["logical_name"]
    assert revision["name"] != first["name"]
    assert _envelope(runtime, instance_id, revision["name"]).ref != first_envelope.ref
    assert root.call_tool("artifact_ingest_text", revision_request) == revision
    assert len(runtime.artifacts.list_artifacts()) == 2

    restarted = open_runtime(
        project_root=runtime.project_root,
        state_root=runtime.state_root,
        actor_id=runtime.actor.actor_id,
    )
    new_root = _root(restarted, instance_id)
    assert new_root.call_tool("artifact_ingest_text", request) == first
    assert new_root.call_tool("artifact_ingest_text", revision_request) == revision
    assert restarted.artifacts.read(first_envelope.ref) == original.encode("utf-8")
    assert restarted.artifacts.read(
        _envelope(restarted, instance_id, revision["name"]).ref
    ) == revised_text.encode("utf-8")
    assert len(restarted.artifacts.list_artifacts()) == 2


def test_original_file_ingress_remains_distinct_and_path_checked(ingress):
    runtime, instance_id, root = ingress
    payload = b"file bytes\r\n"
    (runtime.project_root / "source.txt").write_bytes(payload)
    request = {"name": "file_source", "relative_path": "source.txt"}
    first = root.call_tool("artifact_ingest_file", request)
    assert root.call_tool("artifact_ingest_file", request) == first
    envelope = _envelope(runtime, instance_id, first["name"])
    assert runtime.artifacts.read(envelope.ref) == payload
    assert envelope.kind == "source_file"
    assert envelope.schema_id == "opaque"
    assert envelope.media_type == "text/plain"
    assert envelope.labels == {"source_path": "source.txt"}
    assert envelope.creator == runtime.actor
    with pytest.raises(SchedulerNameConflict):
        root.call_tool("artifact_ingest_text", {
            "name": first["name"], "text": payload.decode("utf-8")
        })
    with pytest.raises(UnsafeSourcePathError):
        root.call_tool("artifact_ingest_file", {
            "name": "outside", "relative_path": "../outside.txt"
        })
    assert len(runtime.artifacts.list_artifacts()) == 1


def test_text_ingress_requires_an_instance_and_rejects_forged_metadata(ingress):
    runtime, instance_id, root = ingress
    unbound = _root(runtime, None)
    with pytest.raises(RootToolError, match="no research instance"):
        unbound.call_tool("artifact_ingest_text", {"name": "note", "text": "说明"})
    for field, value in (
        ("creator", {"actor_id": "user", "actor_type": "human"}),
        ("source_origin", "human_approved"),
        ("media_type", "application/json"),
    ):
        with pytest.raises(RootToolError) as caught:
            root.call_tool("artifact_ingest_text", {
                "name": "note", "text": "说明", field: value
            })
        assert caught.value.details[0]["type"] == "extra_forbidden"
    assert runtime.artifacts.list_artifacts() == ()
    assert runtime.scheduler_bindings.list(instance=instance_id, namespace="artifact") == ()
