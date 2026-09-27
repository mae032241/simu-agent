"""Transport fixtures do not establish live B0a capability."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import probe_root_host_live as live


@pytest.mark.process_e2e
def test_cli_loads_generated_override_keys(tmp_path):
    executable = shutil.which("codex")
    if executable is None:
        pytest.skip("Codex unavailable")
    config = {"mcp_servers": {"scid_probe_fixture": {"command": "/fixture/not-executed", "enabled": False}}}
    # mcp list reads configuration only; it must not connect to the fixture.
    result = subprocess.run([executable, *live.config_flags(config), "mcp", "list", "--json"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20, check=True)
    servers = json.loads(result.stdout)
    fixture = next(v for v in servers if v["name"] == "scid_probe_fixture")
    assert fixture["enabled"] is False
    assert "unrecognized configuration" not in result.stderr


@pytest.mark.parametrize("failure,verify_only,resume,worker_completed,custom_task", [(v, False, False, False, None) for v in
    ("config", "tools", "rpc_error", "tool_error", "no_url", "wrong_origin", "not_selected", "turn", None)]
    + [(None, True, False, False, None), (None, False, True, False, None), ("resume_identity", False, True, False, None),
       ("worker_identity", False, True, False, None), (None, False, True, True, None),
       (None, False, False, False, "Frozen candidate acceptance task"),
       (None, False, True, True, "Explicit next acceptance task")])
@pytest.mark.process_e2e
def test_host_never_uses_model_for_bootstrap_or_failed_prechecks(tmp_path, monkeypatch, failure, verify_only, resume, worker_completed, custom_task):
    project = tmp_path / "project"
    (project / ".codex").mkdir(parents=True)
    (project / ".codex/config.toml").write_text('[agents]\nenabled = true\n')
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("SCID_TEST_LOG_DIR", str(logs))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "unused-personal"))
    live.write(tmp_path / "candidate.json", {"python": sys.executable, "project": str(project), "profile": {},
                                           **({"task": custom_task} if custom_task is not None else {})})
    fake = tmp_path / "fake-codex"
    requests = tmp_path / "requests.jsonl"
    if resume:
        original = tmp_path / "live/fixture-logs"
        original.mkdir(parents=True)
        live.write(original.parent / "thread.json", {"thread_id": "root-from-peer", "session_id": "root-from-peer"})
        (original / "events.log").write_text(json.dumps({"params": {"item": {
            "type": "subAgentActivity", "kind": "started", "agentThreadId": "existing-worker"}}}) + '\n')
        if worker_completed:
            with (original / "events.log").open("a") as stream:
                stream.write(json.dumps({"params": {"item": {"type": "subAgentActivity",
                    "kind": "completed", "agentThreadId": "existing-worker"}}}) + '\n')
    fake.write_text(f"#!{sys.executable}\n" + f'''
import json, sys
from pathlib import Path
failure={failure!r}
instance_reads=0
for line in sys.stdin:
    msg=json.loads(line)
    with Path({str(requests)!r}).open('a') as stream: stream.write(json.dumps(msg)+'\\n')
    if 'id' not in msg: continue
    method=msg['method']
    if method == 'initialize': result={{}}
    elif method == 'config/read': result={{'config': {{}} if failure=='config' else {{'agents':{{'enabled':True}}}}}}
    elif method == 'thread/start': result={{'thread':{{'id':'root-from-peer','sessionId':'root-from-peer'}}}}
    elif method == 'thread/resume':
        thread=msg['params']['threadId']
        result={{'thread':{{'id':'wrong' if failure=='resume_identity' else thread,
            'sessionId':'wrong' if failure=='worker_identity' and thread=='existing-worker' else 'root-from-peer'}}}}
    elif method == 'mcpServerStatus/list': result={{'data':[] if failure=='tools' else [{{'name':'scidiscovery','tools':{{k:{{}} for k in ('scid_catalog','scid_describe','scid_call')}}}}], 'nextCursor':None}}
    elif method == 'mcpServer/tool/call':
        metadata=msg['params'].get('_meta', {{}}).get('x-codex-turn-metadata', {{}})
        if metadata != {{'session_id':'root-from-peer','thread_id':'root-from-peer'}}:
            print(json.dumps({{'id':msg['id'], 'error':{{'code':-32000,'message':'trusted platform session/thread metadata is required'}}}}),flush=True)
            continue
        if failure=='rpc_error':
            print(json.dumps({{'id':msg['id'],'error':{{'code':-32000,'message':'trusted platform session/thread metadata is required: private-detail'}}}}),flush=True)
            continue
        instance_reads+=1
        url='http://127.0.0.1:12345/sessions/sch_'+'a'*32+'?capability=fixture'
        if failure=='wrong_origin': url=url.replace('12345','54321')
        result={{'isError':failure=='tool_error','content':[], 'structuredContent':{{'state':'unbound' if instance_reads==1 or failure=='not_selected' else 'active', 'management_url':'' if failure=='no_url' else url}}}}
    elif method == 'turn/start': result={{'turn':{{'id':'scientific-turn'}}}}
    else: raise RuntimeError('unexpected method '+method)
    print(json.dumps({{'id':msg['id'],'result':result}}),flush=True)
    if method=='turn/start':
        for total in (10,25):
            print(json.dumps({{'method':'thread/tokenUsage/updated','params':{{'threadId':'root-from-peer','tokenUsage':{{'total':{{'inputTokens':total}}}}}}}}),flush=True)
        print(json.dumps({{'method':'turn/completed','params':{{'threadId':'root-from-peer','turn':{{'id':'scientific-turn','status':'failed' if failure=='turn' else 'completed'}}}}}}),flush=True)
''')
    fake.chmod(0o700)
    monkeypatch.setattr(live.shutil, "which", lambda name: str(fake))
    monkeypatch.setattr(live, "probe_native_code_mode", lambda *args: {"status": "passed"})
    monkeypatch.setattr(live.Host, "start_services", lambda self: setattr(self, "ui_url", "http://127.0.0.1:12345"))
    host = live.Host(tmp_path, json.loads(live.guard.DEFAULT_CONFIG.read_text())["limits"])
    original_status = host.status
    states = []
    def status(state, **details):
        states.append(state)
        if state == "awaiting_user":
            calls = [json.loads(line) for line in requests.read_text().splitlines()]
            assert not any(v.get("method") == "turn/start" for v in calls)
            assert details["management_url"].startswith("http://127.0.0.1:12345/sessions/")
            (logs.parent / "continue").touch()
        original_status(state, **details)
    monkeypatch.setattr(host, "status", status)
    try:
        if failure:
            with pytest.raises(RuntimeError): host.run(resume=resume)
        elif verify_only:
            host.initialize_host()
        else:
            host.run(resume=resume, task=custom_task if resume else None)
    finally:
        host.close()
    calls = [json.loads(line) for line in requests.read_text().splitlines()]
    from scidiscovery.artifact_agent.interfaces.mcp_platform_context import platform_context
    for call in calls:
        if call.get("method") == "mcpServer/tool/call":
            context = platform_context({"params": call["params"]})
            assert not context.worker
            assert context.session == context.thread == "root-from-peer"
    assert sum(v.get("method") == "turn/start" for v in calls) == (1 if failure in (None,"turn") and not verify_only else 0)
    if failure not in (None,"turn","not_selected","worker_identity"):
        assert "awaiting_user" not in states
    assert all(p.poll() is not None for p in host.children)
    usage = json.loads((logs.parent / "usage.json").read_text())
    assert not usage["b0a_passed"]
    if failure in (None,"turn") and not verify_only:
        assert usage["threads"]["root-from-peer"]["inputTokens"] == 25
        if not resume:
            prompt = next(v['params']['input'][0]['text'] for v in calls if v.get('method') == 'turn/start')
            assert prompt == (live.TASK if custom_task is None else custom_task)
    assert not list(tmp_path.rglob("auth.json"))
    if resume:
        assert not any(v.get("method") == "thread/start" for v in calls)
        if failure is None:
            resumed = [v['params']['threadId'] for v in calls if v.get('method') == 'thread/resume']
            assert resumed == (['root-from-peer'] if worker_completed else ['root-from-peer', 'existing-worker'])
            prompt = next(v['params']['input'][0]['text'] for v in calls if v.get('method') == 'turn/start')
            assert prompt == (custom_task if custom_task is not None else live.RESUME_TASK)
            assert prompt != live.TASK

    if failure == "rpc_error":
        assert host.last_rpc_error == {"method": "mcpServer/tool/call", "code": -32000,
                                       "diagnostic": "platform_identity_metadata_missing"}
        assert "private-detail" in (logs / "rpc-errors.log").read_text()
        assert "private-detail" not in json.dumps(host.last_rpc_error)


def test_native_failure_stops_before_services_or_models(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("SCID_TEST_LOG_DIR", str(logs))
    live.write(tmp_path / "candidate.json", {"python": sys.executable, "project": str(tmp_path), "profile": {}})
    def unavailable(*args):
        raise RuntimeError("native_code_mode_stdout_closed")
    monkeypatch.setattr(live, "probe_native_code_mode", unavailable)
    monkeypatch.setattr(live.Host, "start_services", lambda self: pytest.fail("launched after native failure"))
    host = live.Host(tmp_path, json.loads(live.guard.DEFAULT_CONFIG.read_text())["limits"])
    try:
        with pytest.raises(RuntimeError, match="native_code_mode_stdout_closed"):
            host.initialize_host()
    finally:
        host.close()


def test_selection_wait_does_not_consume_execution_budget(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("SCID_TEST_LOG_DIR", str(logs))
    live.write(tmp_path / "candidate.json", {"python": sys.executable, "project": str(tmp_path), "profile": {}})
    now = [0.0]
    monkeypatch.setattr(live.time, "monotonic", lambda: now[0])
    host = live.Host(tmp_path, json.loads(live.guard.DEFAULT_CONFIG.read_text())["limits"])
    try:
        now[0] = 10
        host.status("awaiting_user")
        now[0] += host.resources["instance_wait_timeout_seconds"] - 1
        host.status("scientific_turn")
        deadline = host.phase_deadline
        assert deadline - now[0] == host.resources["execution_timeout_seconds"]
        now[0] += 1
        host.status("scientific_turn")
        assert host.phase_deadline == deadline
        now[0] = deadline
        with pytest.raises(TimeoutError, match="execution_timeout"):
            host.pump()
    finally:
        host.close()
    assert not host.children and not host.usage
