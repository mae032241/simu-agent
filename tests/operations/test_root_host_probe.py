"""Prerequisites, fake stdio, and offline CLI schema checks; no model turns."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess

import jsonschema
import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/probe_root_host.py"
SPEC = importlib.util.spec_from_file_location("root_host_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.fixture(autouse=True)
def restore_umask():
    previous = os.umask(0o077)
    os.umask(previous)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.parametrize("mode,blocked", [(0o000, True), (0o755, True), (0o700, False)])
def test_daemon_directory_is_inspected_without_chmod(tmp_path, mode, blocked):
    directory = tmp_path / "daemon"
    directory.mkdir(mode=mode)
    try:
        actual_mode = directory.stat().st_mode
        assert probe.daemon_directory_check(directory, os.getuid())["blocked"] is blocked
        assert directory.stat().st_mode == actual_mode
    finally:
        directory.chmod(0o700)


def test_daemon_directory_rejects_links_wrong_owner_and_files(tmp_path):
    directory = tmp_path / "daemon"
    directory.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(directory)
    file = tmp_path / "file"
    file.touch(mode=0o700)
    assert probe.daemon_directory_check(link, os.getuid())["blocked"]
    assert probe.daemon_directory_check(directory, os.getuid() + 1)["blocked"]
    assert probe.daemon_directory_check(file, os.getuid())["blocked"]
    assert probe.daemon_directory_check(tmp_path / "absent", os.getuid())["status"] == "absent"


def test_blocked_environment_never_launches_process(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "preflight", lambda: {
        "status": "blocked", "blockers": ["native_daemon_directory_blocked"],
        "model_requests": 0, "b0a_passed": False})
    monkeypatch.setattr(probe.guard, "run_one", lambda *a: pytest.fail("blocked host launched"))
    output = tmp_path / "evidence"
    assert probe.main(["--initialize", "--output", str(output)]) == 2
    result = json.loads((output / "preflight.json").read_text())
    assert result["model_requests"] == 0 and not result["b0a_passed"]
    assert not (output / "resource.json").exists()


def test_readiness_alone_never_claims_b0a_or_launches(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/unexecuted/codex")
    monkeypatch.setattr(probe, "daemon_directory_check", lambda *a: {"status": "compatible", "blocked": False})
    monkeypatch.setattr(probe.guard, "run_one", lambda *a: pytest.fail("preflight launched"))
    output = tmp_path / "evidence"
    assert probe.main(["--output", str(output)]) == 0
    result = json.loads((output / "preflight.json").read_text())
    assert result["status"] == "ready_for_initialize"
    assert result["model_requests"] == result["worker_dispatches"] == 0
    assert result["b0a_passed"] is False
    with pytest.raises(FileExistsError):
        probe.main(["--output", str(output)])


@pytest.mark.process_e2e
@pytest.mark.parametrize("outcome,permissions", [
    ("ready",False), ("requirements_error",False), ("identity_missing",False),
    ("ready",True), ("network_mismatch",True), ("resume_identity_changed",True),
])
def test_protocol_probe_uses_no_model_and_cleans_workspace(tmp_path, monkeypatch, outcome, permissions):
    """A fake local stdio peer proves protocol handling, never live Codex ability."""
    command = tmp_path / "fake-codex"
    received = tmp_path / "requests.jsonl"
    command.write_text(f"#!{sys.executable}\n" + f'''
import json, sys
from pathlib import Path
for line in sys.stdin:
    msg = json.loads(line)
    with Path({str(received)!r}).open('a') as stream:
        stream.write(json.dumps(msg) + '\\n')
    if 'id' not in msg:
        continue
    if msg['method'] == 'initialize':
        reply = {{'id': msg['id'], 'result': {{'userAgent':'fixture-codex/1'}}}}
    elif {outcome!r} == 'requirements_error':
        reply = {{'id': msg['id'], 'error': {{'code': -32603,
            'message': 'failed to load workspace requirements: private-details'}}}}
    else:
        thread = {{'id': 'fixture-thread', 'sessionId': 'fixture-session'}}
        if {outcome!r} == 'identity_missing': thread.pop('id')
        if {outcome!r} == 'resume_identity_changed' and msg['method'] == 'thread/resume': thread['id'] = 'wrong'
        params = msg['params']
        network = params.get('config',{{}}).get('sandbox_workspace_write',{{}}).get('network_access',False)
        if {outcome!r} == 'network_mismatch' and msg['method'] == 'thread/resume': network = not network
        reply = {{'id': msg['id'], 'result': {{'thread': thread, 'approvalPolicy':params['approvalPolicy'],
            'sandbox':{{'type':'workspaceWrite', 'networkAccess':network, 'writableRoots':[]}}}}}}
    print(json.dumps(reply), flush=True)
''')
    command.chmod(0o700)
    monkeypatch.setattr(probe.shutil, "which", lambda _: str(command))
    monkeypatch.setattr(probe, "preflight", lambda: {
        "blockers": [], "model_requests": 0, "worker_dispatches": 0, "b0a_passed": False})
    output = tmp_path / "evidence"
    output.mkdir()
    limits = json.loads(probe.guard.DEFAULT_CONFIG.read_text())["limits"]
    rc = probe._protocol_probe(output, limits, permissions=permissions)
    result = json.loads((output / "protocol.json").read_text())
    assert rc == (0 if outcome == "ready" else 1)
    requests = [json.loads(line) for line in received.read_text().splitlines()]
    assert [item["method"] for item in requests] == ["initialize", "initialized", "thread/start"] + (["thread/resume"] if permissions else [])
    assert requests[-1]["params"]["sandbox"] == "workspace-write"
    assert requests[-1]["params"]["approvalPolicy"] == "never"
    assert not list(output.glob("workspace-*"))
    assert not result["b0a_passed"] and result["model_requests"] == 0
    assert "private-details" not in (output / "protocol.json").read_text()
    if outcome == "requirements_error":
        assert result["diagnostic"] == "workspace_requirements_unavailable"
    if permissions:
        assert result["r0a_protocol_passed"] is (outcome == "ready")
        assert requests[-1]["params"]["config"] == probe.RootPermissions().thread()["config"]
        trace = json.loads((output / "permissions-protocol.json").read_text())
        assert [item["method"] for item in trace] == ['initialize','thread/start','thread/resume']
        if outcome == 'ready':
            assert result['native_user_agent'] == 'fixture-codex/1'
            assert result['same_thread_resumed']
        else:
            assert result['diagnostic'] in {'root_permissions_mismatch','resumed_platform_identity_changed'}


@pytest.mark.parametrize("code,message,expected", [
    (-32600, "unknown variant `workspaceWrite`: private-details", "request_schema_mismatch"),
    (-32602, "invalid params: private-details", "request_rejected"),
    (-32600, "thread/start.example requires experimentalApi capability", "experimental_capability_required"),
    (-32603, "failed to load workspace requirements: private-details", "workspace_requirements_unavailable"),
    (-32603, "unrecognized private-details", "rpc_failure"),
])
def test_rpc_diagnostic_retains_category_without_private_text(code, message, expected):
    assert probe.rpc_diagnostic({"code": code, "message": message}) == expected


@pytest.mark.process_e2e
def test_thread_start_matches_installed_cli_schema(tmp_path):
    """Validate against the real CLI's export, not the fake peer's assumptions."""
    executable = probe.shutil.which("codex")
    if executable is None:
        pytest.skip("Codex unavailable; actual host contract remains unverified")
    schema_dir = tmp_path / "schema"
    with (tmp_path / "schema-export.log").open("wb") as log:
        subprocess.run([executable, "app-server", "generate-json-schema", "--out", str(schema_dir)],
            stdout=log, stderr=subprocess.STDOUT, timeout=30, check=True)
    schema = json.loads((schema_dir / "v2/ThreadStartParams.json").read_text())
    request = probe.thread_start_params(str(tmp_path / "workspace"))
    jsonschema.Draft7Validator(schema).validate(request)
    # Negative control reproduces the old probe's protocol mismatch.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft7Validator(schema).validate({**request, "sandbox": "workspaceWrite"})

    from scripts.probe_root_host_live import turn_params
    turn_schema = json.loads((schema_dir / "v2/TurnStartParams.json").read_text())
    jsonschema.Draft7Validator(turn_schema).validate(turn_params("fixture-thread", "Bounded task"))
    resume_schema = json.loads((schema_dir / "v2/ThreadResumeParams.json").read_text())
    jsonschema.Draft7Validator(resume_schema).validate({
        "threadId": "fixture-thread", "cwd": str(tmp_path / "workspace"), "excludeTurns": True})
    jsonschema.Draft7Validator(resume_schema).validate({"threadId": "fixture-worker", "excludeTurns": True})
    # The pinned background Root policy uses only fields this CLI declares.
    from scidiscovery.platforms.codex_root_host import RootPermissions
    from scidiscovery.platforms.codex_app_server import HostError
    assert RootPermissions().turn()["sandboxPolicy"] == {"type": "workspaceWrite", "networkAccess": True}
    config_schema = json.loads((schema_dir / "codex_app_server_protocol.v2.schemas.json").read_text())["definitions"]
    assert config_schema["Config"]["properties"]["sandbox_workspace_write"]["anyOf"][0]["$ref"].endswith("/SandboxWorkspaceWrite")
    workspace = config_schema["SandboxWorkspaceWrite"]["properties"]
    for pinned in (RootPermissions(), RootPermissions(network_access=False), RootPermissions("never", "read-only", False)):
        jsonschema.Draft7Validator(schema).validate({"cwd": str(tmp_path), "ephemeral": False, **pinned.thread()})
        jsonschema.Draft7Validator(resume_schema).validate({"threadId": "fixture-thread", **pinned.thread()})
        jsonschema.Draft7Validator(turn_schema).validate({**turn_params("fixture-thread", "Bounded task"), **pinned.turn()})
        assert set(pinned.thread().get("config", {}).get("sandbox_workspace_write", {})) <= set(workspace)
    for invalid in (dict(sandbox="read-only"), dict(approval_policy="on-request"), dict(network_access=1)):
        with pytest.raises(HostError, match="root_permissions_unsupported"):
            RootPermissions(**invalid)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft7Validator(turn_schema).validate({**turn_params("fixture-thread", "Bounded task"),
            "sandboxPolicy": {"type": "workspace-write"}})
