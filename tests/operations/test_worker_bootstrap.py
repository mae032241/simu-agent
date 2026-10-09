"""Actual unified MCP bootstrap, without Root identity/attach relay."""
import json

import pytest

from tests.operations.test_unified_mcp import queued, call, result, separate_proxy_gateway


def setup(tmp_path):
    from tests.operations.test_local_worker_contracts import _system, _invoke
    _, runtime, instance, initial_root = _system(tmp_path)
    initial_root.facade.instance_management_secret = b"bootstrap-test-secret"
    gateway = separate_proxy_gateway(initial_root, "root-proxy")
    root = gateway.root
    runtime.scheduler_bindings.bind_session(session_key=root.facade.session_key,
        instance_id=instance.instance_id)
    _invoke(root)
    profile = root.facade.run_status(name="observation")["execution_profile"]["profile"]
    reply = result(call(gateway, "run_status", {"name": "observation", "intent": "navigation"}))
    return runtime, root, gateway, profile, reply["dispatch"]["bootstrap"]


def open_child(gateway, profile, bootstrap, *, child="child", parent="parent", session="parent"):
    worker_gateway = separate_proxy_gateway(gateway.root, "worker-proxy")
    assert worker_gateway.facade.session_key != gateway.facade.session_key
    assert worker_gateway.facade.instance is None
    assert worker_gateway.facade.bindings.session_instance(session_key="worker-proxy") is None
    reply = worker_gateway.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "scid_call", "arguments": bootstrap,
        "_meta": {"x-codex-turn-metadata": {"session_id": session, "thread_id": child,
            "parent_thread_id": parent, "thread_source": "subagent", **profile}}}})
    assert worker_gateway.facade.instance is None
    assert worker_gateway.facade.bindings.session_instance(session_key="worker-proxy") is None
    return reply


def native_profile(profile):
    return dict(model=profile["model"], reasoning_effort=profile["reasoning_effort"])


def test_bootstrap_opens_and_replays_without_root_attach(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    opened = result(open_child(gateway, native_profile(profile), bootstrap))
    assert opened["state"] == "opened"
    bound = gateway.connections.resolve(platform_session="parent", thread_id="child")
    assert bound.state == "running"
    result(open_child(gateway, native_profile(profile), bootstrap))
    # Another child cannot steal an accepted task.
    assert "error" in open_child(gateway, native_profile(profile), bootstrap, child="other")
    assert gateway.connections.resolve(platform_session="parent", thread_id="child").run_id == bound.run_id


@pytest.mark.parametrize("change", ["tamper", "parent", "session", "model", "effort", "missing_parent"])
def test_invalid_bootstrap_never_claims_or_fails_queued_task(tmp_path, change):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    profile = native_profile(profile)
    options = {}
    if change == "tamper":
        bootstrap["arguments"]["dispatch_token"] += "x"
    elif change in {"parent", "session"}:
        options[change] = "other"
    elif change == "missing_parent":
        options["parent"] = None
    elif change == "model":
        profile["model"] = "wrong-model"
    else:
        profile["reasoning_effort"] = "wrong-effort"
    assert "error" in open_child(gateway, profile, bootstrap, **options)
    assert root.facade.run_status(name="observation")["state"] == "queued"
    with runtime.runs._connect() as db:
        assert db.execute("SELECT count(*) FROM worker_connections").fetchone()[0] == 0


def test_signed_bootstrap_cannot_replace_unopened_connection(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "first"}))
    assert "error" in open_child(gateway, native_profile(profile), bootstrap)
    assert gateway.connections.resolve(platform_session="parent", thread_id="first").state == "queued"


def test_reading_dispatch_does_not_change_control_state(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    before = root.facade.bindings.progression_status(instance_id=root.facade._instance_id(), internal=True)
    result(call(gateway, "run_status", {"name": "observation", "intent": "navigation"}))
    after = root.facade.bindings.progression_status(instance_id=root.facade._instance_id(), internal=True)
    assert before == after


def test_human_pause_rejects_bootstrap_without_consuming_task(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    root.call_tool("progression_command", {"command": "pause"})
    assert "error" in open_child(gateway, native_profile(profile), bootstrap)
    assert root.facade.run_status(name="observation")["state"] == "queued"


def test_stale_generation_rejected_after_resume(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    root.call_tool("progression_command", {"command": "pause"})
    root.call_tool("progression_command", {"command": "resume"})
    assert "error" in open_child(gateway, native_profile(profile), bootstrap)
    assert root.facade.run_status(name="observation")["state"] == "queued"


def test_bootstrap_requires_the_signed_root_proxy_instance_binding(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    run_id = root.facade._resolve("run", "observation")
    other = runtime.scheduler_bindings.create_instance(name="bootstrap_other", title="Other",
        objective="A distinct instance must not inherit dispatch authority.")
    runtime.scheduler_bindings.bind_session(session_key=root.facade.session_key,
        instance_id=other.instance_id)
    assert "error" in open_child(gateway, native_profile(profile), bootstrap)
    assert runtime.runs.status(run_id).state == "queued"
    with runtime.runs._connect() as db:
        assert db.execute("SELECT count(*) FROM worker_connections").fetchone()[0] == 0


def test_without_control_secret_keeps_explicit_attachment(tmp_path):
    _, _, root, gateway, _ = queued(tmp_path)
    root.facade.instance_management_secret = None
    reply = result(call(gateway, "run_status", {"name": "observation", "intent": "navigation"}))
    assert "bootstrap" not in reply["dispatch"]
    assert reply["dispatch"]["attachment"]["tool"] == "worker_attach"


def test_pending_child_can_describe_bootstrap_without_claiming(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    from tests.operations.test_unified_mcp import rpc
    contract = result(rpc(gateway, "scid_describe", {"name": "worker_open_assignment"},
        child="child", profile=profile))
    assert "dispatch_token" in contract["inputSchema"]["properties"]
    assert root.facade.run_status(name="observation")["state"] == "queued"


def test_accepted_owner_bootstrap_replays_after_pause_and_resume(tmp_path):
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    first = result(open_child(gateway, native_profile(profile), bootstrap))
    run_id = gateway.connections.resolve(platform_session="parent", thread_id="child").run_id
    before = runtime.runs.status(run_id)
    root.call_tool("progression_command", {"command": "pause"})
    result(open_child(gateway, native_profile(profile), bootstrap))
    root.call_tool("progression_command", {"command": "resume"})
    result(open_child(gateway, native_profile(profile), bootstrap))
    after = runtime.runs.status(run_id)
    assert (after.run_id, after.started_at, after.deadline_at) == (before.run_id, before.started_at, before.deadline_at)
    assert "error" in open_child(gateway, native_profile(profile), bootstrap, child="other")


def test_new_bootstrap_requires_fresh_thread_and_old_ticket_cannot_open_new_task(tmp_path):
    from tests.operations.test_local_worker_contracts import _invoke
    runtime, root, gateway, profile, bootstrap = setup(tmp_path)
    result(open_child(gateway, native_profile(profile), bootstrap))
    status = gateway.connections.resolve(platform_session="parent", thread_id="child")
    runtime.runs.record_failure(status.run_id, reason="End fixture task", category="fixture",
        expected_state=status.state, expected_last_activity_at=status.last_activity_at)
    assert result(open_child(gateway, native_profile(profile), bootstrap))["state"] == "failed"
    _invoke(root, name="second")
    next_bootstrap = result(call(gateway, "run_status", {"name": "second",
        "intent": "navigation"}))["dispatch"]["bootstrap"]
    assert "error" in open_child(gateway, native_profile(profile), next_bootstrap)
    # Explicit legacy reuse remains supported, but an old ticket never opens it.
    result(call(gateway, "worker_attach", {"name": "second", "thread_id": "child"}))
    assert "error" in open_child(gateway, native_profile(profile), bootstrap)
    assert root.facade.run_status(name="second")["state"] == "queued"
