"""Exercise the published three-tool boundary, not just its internal handlers."""
import json
import hashlib
import tomllib
import multiprocessing
import sqlite3
import os
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
from blind_csv_plugin.plugin import PLUGIN as BLIND_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter, GATEWAY_TOOLS
from scidiscovery.platforms.codex import initialize, validate_installation_profile
from scidiscovery.operations.tooling import operation_agent_type
from scidiscovery.operations.spec import ComponentRef
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from test_local_worker_contracts import _system, _invoke
from test_instance_archive import archive_system, save_archive, restore_archive


def rpc(gateway, name, arguments=None, *, child=None, profile=None, session="parent"):
    profile = profile or {"model": "gpt-5.6-sol", "reasoning_effort": "medium"}
    return gateway.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": name, "arguments": arguments or {}, "_meta": {"x-codex-turn-metadata": {
            "session_id": session, "thread_id": child or session,
            "thread_source": "subagent" if child else "user",
            "model": profile["model"], "reasoning_effort": profile["reasoning_effort"],
        }}}})


def result(reply):
    assert "error" not in reply, reply
    return reply["result"]["structuredContent"]


def call(gateway, name, arguments=None, **context):
    return rpc(gateway, "scid_call", {"name": name, "arguments": arguments or {}}, **context)


def queued(tmp_path, backend="local"):
    plugin = BLIND_PLUGIN
    catalog, runtime, instance, root = _system(tmp_path, worker_backend=backend, blind_plugin=plugin)
    _invoke(root)
    gateway = UnifiedMCPRouter(root, worker_backend=backend)
    status = root.facade.run_status(name="observation")
    profile = status["execution_profile"]["profile"]
    return catalog, runtime, root, gateway, profile


def separate_proxy_gateway(root, proxy_id):
    """Same durable services, independent initially unbound proxy facade/router."""
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
    source = root.facade
    return UnifiedMCPRouter(RootMCPRouter(RootToolFacade(
        source.artifacts, source.intake, runs=source.runs, approvals=source.approvals,
        executions=source.executions, bindings=source.bindings, instance=None,
        session_key=proxy_id, operation_catalog=source._operation_catalog,
        instance_management_secret=source.instance_management_secret,
        creation_lock=source._create_lock, execution_bridge=source.execution_bridge,
        approval_base_url=source.approval_base_url)))


def test_wrong_worker_handle_can_be_corrected_only_before_assignment_open(tmp_path):
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    _, runtime, root, gateway, profile = queued(tmp_path)
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "wrong-handle"}))
    old = gateway.connections.resolve(platform_session="parent", thread_id="wrong-handle")
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "native-child"}))
    # Simulate a cached old request that resolved the binding before correction.
    with pytest.raises(RunStateConflict, match="binding changed"):
        runtime.runs.reopen(operation_id=old.operation_id, operation_digest=old.operation_digest,
            run_id=old.run_id, trusted_caller=("parent", "wrong-handle"))
    assert runtime.runs.status(old.run_id).state == "queued"
    assert "error" in call(gateway, "worker_open_assignment", child="wrong-handle", profile=profile)
    assert result(call(gateway, "worker_open_assignment", child="native-child", profile=profile))["state"] == "opened"
    assert "error" in call(gateway, "worker_attach", {"name": "observation", "thread_id": "third-child"})
    assert gateway.connections.resolve(platform_session="parent", thread_id="native-child").run_id == old.run_id


def test_codex_optional_source_preserves_worker_scope_and_attachment(tmp_path):
    _, runtime, root, gateway, profile = queued(tmp_path)

    def invoke(name, arguments=None, **metadata):
        meta = {"session_id": "parent", "thread_id": "parent", **profile, **metadata}
        return gateway.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "scid_call", "arguments": {"name": name, "arguments": arguments or {}},
            "_meta": {"x-codex-turn-metadata": meta}}})

    assert result(invoke("instance_current"))
    child = {"thread_id": "child", "parent_thread_id": "parent", "subagent_kind": "thread_spawn"}
    assert result(invoke("worker_identity", **child))["thread_id"] == "child"
    assert "No live parent task authorizes this helper" in invoke("worker_open_assignment", **child)["error"]["message"]
    assert "error" in invoke("instance_current", **child)
    result(invoke("worker_attach", {"name": "observation", "thread_id": "child"}))
    assert result(invoke("worker_open_assignment", **child))["state"] == "opened"
    # Neither omitting optional markers nor explicit privilege claims bypasses the binding.
    assert result(invoke("worker_open_assignment", thread_id="child"))["state"] == "opened"
    for metadata in (
        {**child, "session_id": "other-parent"},
        {**child, "thread_source": "user"},
        {"thread_source": "subagent"},
        {"parent_thread_id": "other-parent"},
        {"subagent_kind": "thread_spawn"},
        {"session_id": None},
        {"thread_id": "invalid/thread"},
    ):
        assert "error" in invoke("instance_current", **metadata)
    assert "error" in invoke("worker_open_assignment", **{**child, "session_id": "other-parent"})


@pytest.mark.process_e2e
def test_optional_source_proxy_daemon_does_not_register_worker_as_scheduler(tmp_path):
    from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
    from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
    _, runtime, root, gateway, profile = queued(tmp_path)
    socket = tmp_path / "control.sock"
    def serve():
        UnixSocketDaemon(socket, RootBrokerRouter(lambda _: gateway,
            client_bindings=runtime.scheduler_bindings,
            instance_maintenance=runtime.instance_maintenance)).serve_forever()
    process = multiprocessing.get_context("fork").Process(target=serve)
    process.start()
    def request(name, arguments=None, *, worker=False, **updates):
        meta = {"session_id": "transport-parent",
                "thread_id": "transport-child" if worker else "transport-parent", **profile, **updates}
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "scid_call", "arguments": {"name": name, "arguments": arguments or {}},
            "_meta": {"x-codex-turn-metadata": meta}}}
        reply = subprocess.run([sys.executable, "-m", "scidiscovery.artifact_agent.interfaces.mcp_proxy",
            "--socket", str(socket)], input=json.dumps(message)+'\n', text=True, capture_output=True,
            timeout=10, env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
        assert reply.returncode == 0, reply.stderr
        return json.loads(reply.stdout)
    def clients():
        with sqlite3.connect(runtime.scheduler_bindings.client_database_path) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='scheduler_clients'").fetchone():
                return 0  # The client registry is created lazily on its first Root.
            return db.execute("SELECT COUNT(*) FROM scheduler_clients").fetchone()[0]
    try:
        deadline = time.monotonic()+5
        while not socket.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert socket.exists()
        before = clients()
        identity = result(request("worker_identity", worker=True))
        assert identity["thread_id"] == "transport-child"
        assert clients() == before
        result(request("worker_attach", {"name": "observation", "thread_id": identity["thread_id"]}))
        registered = clients()
        assert registered == before + 1
        assert result(request("worker_open_assignment", worker=True))["state"] == "opened"
        assert "error" in request("instance_current", worker=True)
        assert "error" in request("instance_current", worker=True, thread_source="user")
        assert clients() == registered
    finally:
        process.terminate(); process.join(3)
        if process.is_alive():
            process.kill(); process.join()


@pytest.mark.parametrize("backend", ["local"])
@pytest.mark.parametrize("binding_clock", ["forward", "equal", "backward"])
def test_gateway_scopes_actual_worker_lifecycle_and_sealed_result(tmp_path, backend, monkeypatch, binding_clock):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.service import runs as run_module, worker_connections
    # Binding order must follow accepted attachments, not wall time or random IDs.
    ids = iter(("f" * 32, "0" * 32))
    monkeypatch.setattr(run_module, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=next(ids))))
    second = {"forward": "02", "equal": "01", "backward": "00"}[binding_clock]
    binding_time = ["2026-09-29T00:00:01.000000Z"]
    monkeypatch.setattr(worker_connections, "timestamp", lambda: binding_time[0])
    catalog, runtime, root, gateway, profile = queued(tmp_path, backend)
    listed = gateway.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert [t["name"] for t in listed["result"]["tools"]] == list(GATEWAY_TOOLS)
    assert {item["name"] for item in listed["result"]["tools"]} == {"scid_catalog", "scid_describe", "scid_call"}
    for index, name in enumerate(GATEWAY_TOOLS):
        gateway_contract = result(rpc(gateway, "scid_describe", {"name": name}))
        assert gateway_contract["name"] == name
        assert gateway_contract["inputSchema"] == listed["result"]["tools"][index]["inputSchema"]
        if name == "scid_catalog":
            fields = gateway_contract["inputSchema"]["properties"]
            assert "summary = IDs + exact purposes" in fields["view"]["description"]
            assert "index/facets/matches = structural navigation" in fields["view"]["description"]
            assert "omit for P1 structural dimensions/counts" in fields["dimension"]["description"]
            assert "consequence, executor_kind, input_schema" in fields["where"]["description"]
            assert "AND keys, OR values" in fields["where"]["description"]
        for view in ("invoke", "full"):
            assert result(rpc(gateway, "scid_describe", {"name": name, "view": view})) == gateway_contract
    assert "inputSchema" not in json.dumps(result(rpc(gateway, "scid_catalog")))
    summary = result(rpc(gateway, "scid_catalog"))
    index = result(rpc(gateway, "scid_catalog", {"view": "index"}))
    assert {item["operation_id"] for item in index["operations"]} == {
        item["operation_id"] for item in summary["operations"]}
    assert index["complete"] and index["visible_total"] == len(index["operations"])
    assert index["describe"] == {"tool": "scid_describe", "name": "<selected operation_id>", "view": "invoke"}
    assert all("describe" not in item for item in index["operations"])
    facets = result(rpc(gateway, "scid_catalog", {"view": "facets"}))
    assert {item["name"] for item in facets["dimensions"]} == {
        "consequence", "executor_kind", "input_schema"}
    consequence = facets["dimensions"][0]["name"]
    value = result(rpc(gateway, "scid_catalog", {"view": "facets", "dimension": consequence}))
    if value["facets"]:
        matches = result(rpc(gateway, "scid_catalog", {"view": "matches", "where": {
            consequence: value["facets"][0]["value"]}}))
        assert matches["matched_total"] > 0 and matches["coverage"] == "filtered_subset"
    absent_schema = result(rpc(gateway, "scid_catalog", {"view": "matches", "where": {
        "input_schema": "schema.not.in.current.catalog"}}))
    assert absent_schema["matched_total"] == 0 and absent_schema["complete"]
    assert absent_schema["fallback"]["view"] == "index"
    if consequence == "consequence" and value["complete"] and not any(
        item["value"] == "external" for item in value["facets"]
    ):
        absent = result(rpc(gateway, "scid_catalog", {"view": "matches", "where": {
            "consequence": "external"}}))
        assert absent["matched_total"] == 0 and absent["complete"]
        assert absent["fallback"]["view"] == "index"
    invalid_field = rpc(gateway, "scid_catalog", {"view": "matches", "where": {"x" * 10000: "x"}})
    assert "unsupported P1 filter field" in invalid_field["error"]["message"]
    assert len(json.dumps(invalid_field)) < 1000
    assert result(rpc(gateway, "scid_describe", {"name": "operation_invoke"}))["inputSchema"]
    operation_id = "blind.csv.observe.v1"
    full_contract = result(rpc(gateway, "scid_describe", {"name": operation_id, "view": "full"}))
    invoke_contract = result(rpc(gateway, "scid_describe", {
        "name": operation_id, "view": "invoke"}))
    full_item = full_contract["operations"][0]
    invoke_item = invoke_contract["operations"][0]
    assert full_contract["view"] == "detail" and invoke_contract["view"] == "invoke"
    assert 'operation_digest' not in invoke_item and 'operation_digest' not in full_item
    assert invoke_item['operation_id'] == full_item['operation_id'] == operation_id
    assert invoke_item['inputs'] == full_item['inputs']
    assert invoke_item["contract_view_version"] == "invoke.scientific.v3"
    assert result(rpc(gateway, "scid_describe", {"name": operation_id})) == invoke_contract
    assert invoke_item["revision_policy"]["max_revisions"] == (
        catalog.operation(operation_id).spec.review.max_revisions
        if catalog.operation(operation_id).spec.review else 0
    )
    assert "revision_policy" not in full_item
    assert "native_shell" in full_item and "native_shell" not in invoke_item
    for view in ("invoke", "full"):
        assert result(rpc(gateway, "scid_describe", {"name": "operation_invoke", "view": view})) == result(
            rpc(gateway, "scid_describe", {"name": "operation_invoke"}))
    child = {"child": "child-1", "profile": profile}
    assert [x['name'] for x in result(rpc(gateway, "scid_catalog", **child))['entries']] == ['worker_identity', 'worker_open_assignment']
    assert "navigation views are available only for Root" in rpc(
        gateway, "scid_catalog", {"view": "index"}, **child)["error"]["message"]
    for view in ("invoke", "full"):
        assert result(rpc(gateway, "scid_describe", {"name": "worker_identity", "view": view}, **child)) == result(
            rpc(gateway, "scid_describe", {"name": "worker_identity"}, **child))
    identity = result(call(gateway, "worker_identity", **child))
    assert identity == {"thread_id": "child-1", "model": profile['model'],
                        "reasoning_effort": profile['reasoning_effort']}
    assert "awaiting scheduler attachment" in call(gateway, "worker_open_assignment", **child)["error"]["message"]
    assert "error" in call(gateway, "worker_identity", {"thread_id": "child-2"}, **child)
    assert "error" in call(gateway, "worker_identity")
    assert "error" in call(gateway, "worker_open_assignment")
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": identity['thread_id']}))
    names = {x["name"] for x in result(rpc(gateway, "scid_catalog", **child))["entries"]}
    assert "worker_csv_summarize" in names and "operation_invoke" not in names
    for view in ("invoke", "full"):
        assert result(rpc(gateway, "scid_describe", {"name": "worker_csv_summarize", "view": view}, **child)) == result(
            rpc(gateway, "scid_describe", {"name": "worker_csv_summarize"}, **child))
    assert "navigation views are available only for Root" in rpc(
        gateway, "scid_catalog", {"view": "matches", "where": {"consequence": "scientific"}},
        **child)["error"]["message"]
    for name in ("operation_invoke", "worker_attach", "worker_tcad_debug_run"):
        assert "error" in call(gateway, name, **child)
        assert "error" in rpc(gateway, "scid_describe", {"name": name}, **child)
    other_session = dict(child="child-1", profile=profile, session="other-parent")
    assert [x["name"] for x in result(rpc(gateway, "scid_catalog", **other_session))["entries"]] == ["worker_identity", "worker_open_assignment"]
    assert "error" in call(gateway, "worker_open_assignment", **other_session)
    opened = result(call(gateway, "worker_open_assignment", **child))
    structure = result(call(gateway, "worker_csv_summarize", **child))
    content = json.dumps({"schema_version": 1, "handoff": {"verdict": "pass", "summary": "Bounded result."},
        "payload": {"schema_probe": CSV_SCHEMA_PROBE, "structure": structure,
                    "interpretation": "The mean is two.", "limitations": ["Two rows do not establish causality."]}})
    Path(opened["output_directory"], "result.json").write_text(content)
    assert result(call(gateway, "worker_submit_result", **child))["state"] == "completed"
    assert result(call(gateway, "run_status", {"name": "observation"}))["state"] == "completed"
    assert "error" in call(gateway, "worker_csv_summarize", **child)
    # Reuse is a new exact Run, not reopening or modifying the sealed output.
    _invoke(root, name="second")
    binding_time[0] = f"2026-09-29T00:00:{second}.000000Z"
    result(call(gateway, "worker_attach", {"name": "second", "thread_id": "child-1"}))
    reopened = result(call(gateway, "worker_open_assignment", **child))
    assert reopened.get("state") == "opened", reopened
    assert reopened["workspace_path"] != opened["workspace_path"]
    if backend == "local":
        assert "reading_guidance" not in opened
        assert set(reopened['reading_guidance']['reuse_if_retained']) == {'role_instructions','tool_contracts','output_schema'}
        assert reopened['reading_guidance']['read'] == []
        assert reopened['reading_guidance']['inputs']
        assert all(item['status'] == 'unchanged' for item in reopened['reading_guidance']['inputs'])
        # Reconstructing the gateway keeps the derived cue: no in-memory reuse ledger.
        restarted=UnifiedMCPRouter(root)
        again=result(call(restarted,'worker_open_assignment',**child))
        assert again['reading_guidance']==reopened['reading_guidance']
        # Simulate a control-owned dynamic schema refresh in the current workspace.
        schema_path=Path(reopened['workspace_path'])/'schema/result.schema.json'
        schema_path.chmod(0o600)
        schema=json.loads(schema_path.read_text());schema['description']='updated tool evidence'
        schema_path.write_text(json.dumps(schema))
        refreshed=result(call(restarted,'worker_open_assignment',**child))
        assert refreshed['reading_guidance']['read']==['output_schema']
        assert set(refreshed['reading_guidance']['reuse_if_retained'])=={'role_instructions','tool_contracts'}
        assignment_path=Path(reopened['assignment_path']);assignment_path.chmod(0o600)
        current=json.loads(assignment_path.read_text())
        current['tool_contracts']={**current['tool_contracts'],'fixture_changed':{'description':'changed contract'}}
        assignment_path.write_text(json.dumps(current))
        changed=result(call(restarted,'worker_open_assignment',**child))
        assert changed['reading_guidance']['reuse_if_retained']==['role_instructions']
        assert set(changed['reading_guidance']['read'])=={'tool_contracts','output_schema'}
        Path(opened['assignment_path']).unlink()
        unavailable=result(call(restarted,'worker_open_assignment',**child))
        assert unavailable['reading_guidance']['reuse_if_retained']==[]
        assert len(unavailable['reading_guidance']['read'])==3
        assert all(item['status'] == 'unknown' for item in unavailable['reading_guidance']['inputs'])
    second_run = gateway.connections.resolve(platform_session="parent", thread_id="child-1")
    last = result(call(gateway, "run_status", {"name": "second"}))
    result(call(gateway, "run_record_failure", {"name": "second", "reason": "End fixture task",
        "expected_state": "running", "expected_last_activity_at": last["last_activity_at"]}))
    assert UnifiedMCPRouter(root).connections.resolve(
        platform_session="parent", thread_id="child-1").run_id == second_run.run_id


@pytest.mark.parametrize("old_schema", ["no_bindings", "no_sequence"])
def test_pre_gateway_archive_restores_without_fabricated_bindings(archive_system, old_schema):
    runtime, archives, instance_id, _ = archive_system
    with runtime.runs._connect() as connection:
        connection.execute("DROP TABLE worker_connections" if old_schema == "no_bindings" else
                           "ALTER TABLE worker_connections DROP COLUMN attachment_sequence")
    save_archive(archives, instance_id)
    runtime.runs._initialize()
    restore_archive(archives, instance_id)
    with runtime.runs._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM worker_connections").fetchone()[0] == 0
        assert "attachment_sequence" in {row[1] for row in connection.execute("PRAGMA table_info(worker_connections)")}


def test_legacy_binding_migration_preserves_identity_and_rejects_ambiguous_order(tmp_path):
    from scidiscovery.artifact_agent.service.run_records import RunStateConflict
    _, runtime, root, gateway, profile = queued(tmp_path)
    child = {"child": "child-1", "profile": profile}
    ids = []
    for name in ("observation", "second"):
        if name == "second":
            _invoke(root, name=name)
        result(call(gateway, "worker_attach", {"name": name, "thread_id": "child-1"}))
        ids.append(gateway.connections.resolve(platform_session="parent", thread_id="child-1").run_id)
        result(call(gateway, "worker_open_assignment", **child))
        if name == "observation":
            last = result(call(gateway, "run_status", {"name": name}))
            result(call(gateway, "run_record_failure", {"name": name, "reason": "End fixture task",
                "expected_state": "running", "expected_last_activity_at": last["last_activity_at"]}))
    with runtime.runs._connect() as connection:
        connection.execute("ALTER TABLE worker_connections DROP COLUMN attachment_sequence")
        connection.execute("UPDATE worker_connections SET attached_at='2026-09-29T00:00:00Z'")
    runtime.runs._initialize()
    connections = UnifiedMCPRouter(root).connections
    assert connections.resolve(platform_session="parent", thread_id="child-1").run_id == ids[1]
    with runtime.runs._connect() as connection:
        assert {row[0] for row in connection.execute("SELECT attachment_sequence FROM worker_connections")} == {0}
    assert connections.previous_run(run_id=ids[1], platform_session="parent", thread_id="child-1") is None
    last = result(call(gateway, "run_status", {"name": "second"}))
    result(call(gateway, "run_record_failure", {"name": "second", "reason": "End fixture task",
        "expected_state": "running", "expected_last_activity_at": last["last_activity_at"]}))
    with pytest.raises(RunStateConflict, match="ambiguous"):
        connections.resolve(platform_session="parent", thread_id="child-1")


@pytest.mark.parametrize("legacy", [False, True])
def test_archive_restores_nonempty_worker_binding_order(tmp_path, legacy):
    from test_instance_archive_continuation import _local_archive_system, InstanceArchive
    _, runtime, instance, root = _local_archive_system(tmp_path)
    _invoke(root)
    gateway = UnifiedMCPRouter(root)
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "child-1"}))
    bound = gateway.connections.resolve(platform_session="parent", thread_id="child-1")
    result(call(gateway, "worker_open_assignment", child="child-1", profile=bound.execution_profile['profile']))
    last = result(call(gateway, "run_status", {"name": "observation"}))
    result(call(gateway, "run_record_failure", {"name": "observation", "reason": "End fixture task",
        "expected_state": "running", "expected_last_activity_at": last["last_activity_at"]}))
    if legacy:
        with runtime.runs._connect() as connection:
            connection.execute("ALTER TABLE worker_connections DROP COLUMN attachment_sequence")
    root.call_tool("progression_command", {"command": "pause"})
    archive = InstanceArchive(runtime)
    save_archive(archive, instance.instance_id)
    runtime.runs._initialize()
    restore_archive(archive, instance.instance_id)
    restored = UnifiedMCPRouter(root).connections.resolve(platform_session="parent", thread_id="child-1")
    assert restored.run_id == bound.run_id and restored.state == 'failed'
    with runtime.runs._connect() as connection:
        row = connection.execute("SELECT attachment_sequence FROM worker_connections WHERE run_id=?", (bound.run_id,)).fetchone()
        assert row[0] == (0 if legacy else 1)


def test_durable_binding_reconnects_exact_run_and_rejects_other_thread(tmp_path):
    _, runtime, root, gateway, profile = queued(tmp_path)
    child = {"child": "child-1", "profile": profile}
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "child-1"}))
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "child-1"}))
    assert "error" in call(gateway, "worker_attach", {"name": "observation", "thread_id": "parent"})
    assert "error" not in rpc(
        gateway, "scid_catalog", child="child-1",
        profile={**profile, "model": profile["model"].upper()},
    )
    first = result(call(gateway, "worker_open_assignment", **child))
    assert "error" in call(gateway, "worker_attach", {"name": "observation", "thread_id": "child-2"})
    new_gateway = UnifiedMCPRouter(root)
    second = result(call(new_gateway, "worker_open_assignment", **child))
    assert first["workspace_path"] == second["workspace_path"]
    # No caller-supplied role/run can override the transport's binding.
    assert "error" in rpc(new_gateway, "scid_call", {"name":"worker_open_assignment", "role":"root"}, **child)
    assert "error" in new_gateway.handle({"jsonrpc":"2.0", "id":1, "method":"tools/call",
        "params":{"name":"scid_call", "arguments":{"name":"instance_current"}}})


@pytest.mark.parametrize("profile_override", (
    {"model": "wrong-model"},
    {"reasoning_effort": "low"},
))
def test_irreparable_attached_profile_mismatch_fails_run_and_releases_slot(
    tmp_path, profile_override,
):
    _, runtime, root, gateway, profile = queued(tmp_path)
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "child-1"}))

    rejected = rpc(
        gateway, "scid_catalog", child="child-1",
        profile={**profile, **profile_override},
    )
    assert "Worker platform model/effort do not match" in rejected["error"]["message"]
    failed = root.facade.run_status(name="observation", intent='navigation')
    assert failed["state"] == "failed"
    assert "expected=" not in failed["reason"] and "observed=" not in failed["reason"]
    value = runtime.runs.status(runtime.scheduler_bindings.resolve(instance=root.facade.instance, namespace="run", name="observation"))
    assert runtime.runs.diagnostic_summary(value)["failure"]["category"] == "worker_profile_mismatch"
    diagnostic_page = root.call_tool(
        "run_status", {'name': "observation", 'diagnostic_after': 0, 'diagnostic_limit': 10, "intent": 'status'}
    )
    assert diagnostic_page["diagnostic_events"]["events"][-1]["diagnostic"]["code"] == "worker_profile_mismatch"
    with runtime.runs._connect() as connection:
        stored = connection.execute(
            "SELECT diagnostic_json FROM run_activity WHERE activity='framework_failure'"
        ).fetchone()
    assert json.loads(stored[0])["category"] == "worker_profile_mismatch"

    _invoke(root, "observation_after_profile_rejection")
    assert root.facade.run_status(name="observation_after_profile_rejection")["state"] == "queued"
    with runtime.runs._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM worker_connections").fetchone()[0] == 1


@pytest.mark.parametrize("backend", ["local"])
def test_generated_install_has_one_mcp_and_no_worker_service_copies(tmp_path, backend):
    catalog, runtime, root, _, _ = queued(tmp_path, backend)
    project = tmp_path / "project"
    initialize(project, control_socket=tmp_path / "control.sock", state_root=tmp_path / "state",
        operation_catalog=catalog, worker_backend=backend)

    # Upgrade must remove the old managed registrations, including role copies.
    config_path = project / ".codex/config.toml"
    config_path.write_text(config_path.read_text().replace("# END SCIDISCOVERY MANAGED MCP",
        '[mcp_servers.scid_worker_retired]\ncommand = "unused"\n# END SCIDISCOVERY MANAGED MCP'))
    role_path = next((project / ".codex/agents").glob("*.toml"))
    role_path.write_text(role_path.read_text() + '\n[mcp_servers.scid_worker_retired]\ncommand = "unused"\n')
    initialize(project, control_socket=tmp_path / "control.sock", state_root=tmp_path / "state",
        operation_catalog=catalog, worker_backend=backend)

    config = tomllib.loads((project / ".codex/config.toml").read_text())
    assert set(config["mcp_servers"]) == {"scidiscovery"}
    assert config["mcp_servers"]["scidiscovery"]["enabled_tools"] == list(GATEWAY_TOOLS)
    for path in (project / ".codex/agents").glob("*.toml"):
        role = tomllib.loads(path.read_text())
        assert not role.get("mcp_servers")
        assert "scid_call" in role["developer_instructions"]
        compiled = next(catalog.operation(key) for key in catalog.operation_ids()
            if operation_agent_type(catalog.operation(key)) == role["name"])
        assert role["features"]["shell_tool"] is (backend == "local" and compiled.spec.executor.native_tools.shell != "none")
    workspace = project / "research"
    workspace.mkdir()
    validate_installation_profile(project, workspace=workspace,
        python_path=Path(__file__).resolve().parents[2] / "src", state_root=tmp_path / "state",
        operation_catalog=catalog, worker_backend=backend)


@pytest.mark.process_e2e
@pytest.mark.parametrize("attachment", ["explicit", "bootstrap"])
def test_real_proxy_daemon_preserves_scope_and_worker_does_not_register_client(tmp_path, attachment):
    from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
    from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
    _, runtime, instance, root = _system(tmp_path)
    profile = {"model": "gpt-5.6-sol", "reasoning_effort": "medium"}
    root.facade.instance_management_secret = hashlib.sha256(b"transport-bootstrap-secret").digest()
    root.facade.approval_base_url = "http://127.0.0.1:8765"
    socket = tmp_path / "control.sock"
    def serve():
        UnixSocketDaemon(socket, RootBrokerRouter(lambda proxy_id: separate_proxy_gateway(root, proxy_id),
            client_bindings=runtime.scheduler_bindings,
            instance_maintenance=runtime.instance_maintenance)).serve_forever()
    process = multiprocessing.get_context("fork").Process(target=serve)
    process.start()
    root_proxy = None
    def request(name, arguments, *, worker=False):
        meta = {"session_id":"transport-parent", "thread_id":"transport-child" if worker else "transport-parent",
                "thread_source":"subagent" if worker else "user", "model":profile["model"],
                "reasoning_effort":profile["reasoning_effort"]}
        if worker:
            meta["parent_thread_id"] = "transport-parent"
        message = {"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{
            "name":name, "arguments":arguments, "_meta":{"x-codex-turn-metadata":meta}}}
        if worker:
            reply = subprocess.run([sys.executable,"-m","scidiscovery.artifact_agent.interfaces.mcp_proxy",
                "--socket",str(socket)], input=json.dumps(message)+'\n', text=True, capture_output=True,
                timeout=10, env=dict(os.environ,PYTHONPATH=os.pathsep.join(sys.path)))
            assert reply.returncode == 0, reply.stderr
            return json.loads(reply.stdout)
        root_proxy.stdin.write(json.dumps(message)+'\n')
        root_proxy.stdin.flush()
        assert select.select([root_proxy.stdout], [], [], 10)[0], "Root proxy response timed out"
        return json.loads(root_proxy.stdout.readline())
    try:
        deadline = time.monotonic()+5
        while not socket.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert socket.exists()
        # The real Root stdio process retains one proxy identity across calls.
        # Every Worker subprocess gets a different unbound facade in the broker.
        root_proxy = subprocess.Popen([sys.executable, "-m", "scidiscovery.artifact_agent.interfaces.mcp_proxy",
            "--socket", str(socket)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
        current = result(request("scid_call", {"name": "instance_current"}))
        assert current["state"] == "unbound"
        assert current["management_url"].startswith(root.facade.approval_base_url + "/sessions/")
        clients = runtime.scheduler_bindings.clients()
        assert len(clients) == 1
        scheduler_proxy = clients[0]["session_key"]
        # Only the test's management action binds Root. The builder never picks
        # an instance for any proxy or registers a Worker as a scheduler.
        runtime.scheduler_bindings.bind_session(session_key=scheduler_proxy, instance_id=instance.instance_id)
        result(request("scid_call", {"name": "operation_invoke", "arguments": {
            "name": "observation", "operation_id": "blind.csv.observe.v1",
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": "Make one bounded observation from the exact CSV."}}))
        queued_reply = result(request("scid_call", {"name": "run_status", "arguments": {
            "name": "observation", "intent": "status"}}))
        profile = queued_reply["execution_profile"]["profile"]
        # Run the installer's real shell check against this daemon and stdio proxy.
        project = Path(__file__).resolve().parents[2]
        install_root = tmp_path / "install"
        install_root.mkdir()
        (install_root / "site").symlink_to(project / "src", target_is_directory=True)
        installed_probe = subprocess.run([
            "bash", "-c", 'source "$1"; probe_mcp scidiscovery.artifact_agent.interfaces.mcp_proxy "$2" "" root',
            "bash", str(project / "deploy/install.sh"), str(socket),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=15,
            env=dict(os.environ, SCID_INSTALL_ROOT=str(install_root), SCID_PYTHON=sys.executable))
        assert installed_probe.returncode == 0, installed_probe.stderr
        assert "MCP tool probe: pass (root, 3)" in installed_probe.stdout
        context_probe = subprocess.run([
            "bash", "-c", 'source "$1"; probe_root_context_contract scidiscovery.artifact_agent.interfaces.mcp_proxy "$2"',
            "bash", str(project / "deploy/install.sh"), str(socket),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=15,
            env=dict(os.environ, SCID_INSTALL_ROOT=str(install_root), SCID_PYTHON=sys.executable))
        assert context_probe.returncode == 0, context_probe.stderr
        assert "Root context contract probe: pass (blind.csv.observe.v1" in context_probe.stdout
        if attachment == "explicit":
            identity = result(request("scid_call", {"name":"worker_identity"}, worker=True))
            assert identity['thread_id'] == 'transport-child'
            result(request("scid_call", {"name":"worker_attach", "arguments":{
                "name":"observation", "thread_id":identity['thread_id']}}))
            first_open = {"name": "worker_open_assignment"}
        else:
            queued_reply = result(request("scid_call", {"name": "run_status",
                "arguments": {"name": "observation", "intent": "navigation"}}))
            # Exercise legacy compatibility deliberately, not the normal dispatch contract.
            from types import SimpleNamespace
            from scidiscovery.artifact_agent.interfaces.worker_bootstrap import offer
            issuer = separate_proxy_gateway(root, scheduler_proxy).facade
            offer(issuer, SimpleNamespace(session="transport-parent", thread="transport-parent"), queued_reply)
            first_open = queued_reply["dispatch"]["bootstrap"]
        with sqlite3.connect(runtime.scheduler_bindings.client_database_path) as db:
            before = db.execute("SELECT COUNT(*) FROM scheduler_clients").fetchone()[0]
        assert result(request("scid_call", first_open,worker=True))["state"] == "opened"
        with sqlite3.connect(runtime.scheduler_bindings.database_path) as db:
            assert db.execute("SELECT COUNT(*) FROM scheduler_sessions").fetchone()[0] == 1
        run_id=runtime.scheduler_bindings.resolve(instance=root.facade.instance,namespace='run',name='observation')
        opened=runtime.runs.status(run_id)
        process.kill();process.join(5)
        assert not process.is_alive()
        socket.unlink(missing_ok=True)
        process=multiprocessing.get_context('fork').Process(target=serve)
        process.start()
        deadline=time.monotonic()+5
        while not socket.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert socket.exists()
        # The same native caller continues through a fresh broker/Worker router;
        # no model-facing reopen or new Run is needed after the service crash.
        assert result(request('scid_call', {'name':'worker_heartbeat'},worker=True))['state']=='running'
        recovered=runtime.runs.status(run_id)
        assert (recovered.run_id,recovered.deadline_at,recovered.started_at)==(opened.run_id,opened.deadline_at,opened.started_at)
        assert "error" in request("scid_call", {"name":"instance_current"},worker=True)
        with sqlite3.connect(runtime.scheduler_bindings.client_database_path) as db:
            assert db.execute("SELECT COUNT(*) FROM scheduler_clients").fetchone()[0] == before
        # Wrapped instance_close must reach the original active-Run guard without
        # deadlocking while upgrading a broker shared lock to the Root exclusive lock.
        closed = request("scid_call", {"name":"instance_close"})
        assert "active scientific Run" in closed["error"]["message"]
    finally:
        if root_proxy is not None:
            root_proxy.terminate()
            try:
                root_proxy.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                root_proxy.kill(); root_proxy.communicate()
        process.terminate(); process.join(3)
        if process.is_alive():
            process.kill(); process.join()


@pytest.mark.process_e2e
def test_tcad_install_probe_checks_exact_declared_tool_set_through_proxy(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.plugin_runtime.transport import UnixSocketDaemon
    from tcad_artifact.execution_control import TCADExecutionRouter

    project = Path(__file__).resolve().parents[2]
    install_root = tmp_path / "install"
    site = install_root / "site"
    site.mkdir(parents=True)
    (site / "scidiscovery").symlink_to(project / "src/scidiscovery", target_is_directory=True)
    (site / "tcad_artifact").symlink_to(
        project / "plugins/tcad_artifact/tcad_artifact", target_is_directory=True)
    declared = TCADExecutionRouter(SimpleNamespace()).list_tools()
    assert len(declared) > 1
    removed_name = declared[-1]["name"]
    corrupt = multiprocessing.get_context("fork").Value("b", 0)
    socket = tmp_path / "tcad.sock"
    tools = SimpleNamespace(list_tools=lambda: declared[:-1] + [{**declared[-1],
        "name": "unexpected_tcad_tool"}] if corrupt.value else declared)
    process = multiprocessing.get_context("fork").Process(target=lambda: UnixSocketDaemon(
        socket, MCPRouter(tools, name="tcad-control")).serve_forever())
    process.start()
    try:
        deadline = time.monotonic() + 5
        while not socket.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert socket.exists()
        command = ["bash", "-c", 'source "$1"; probe_mcp tcad_artifact.execution_mcp "$2" "" tcad',
            "bash", str(project / "deploy/install.sh"), str(socket)]
        environment = dict(os.environ, SCID_INSTALL_ROOT=str(install_root), SCID_PYTHON=sys.executable)
        passed = subprocess.run(command, cwd=tmp_path, env=environment,
            capture_output=True, text=True, timeout=15)
        assert passed.returncode == 0, passed.stderr
        assert f"MCP tool probe: pass (tcad, {len(declared)})" in passed.stdout
        corrupt.value = 1
        rejected = subprocess.run(command, cwd=tmp_path, env=environment,
            capture_output=True, text=True, timeout=15)
        assert rejected.returncode != 0
        assert removed_name in rejected.stderr
        assert "unexpected_tcad_tool" in rejected.stderr
    finally:
        process.terminate(); process.join(3)
        if process.is_alive():
            process.kill(); process.join()


from tests.operations.test_agent_contract_alignment import experiment_case
