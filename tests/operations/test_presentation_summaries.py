"""Post-seal model calls cannot become another submission/review gate."""
import fcntl
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from scidiscovery.agent_execution_settings import PresentationSettings
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.presentation_summaries import (
    SummaryStore, SummaryWorker, fragments, store_for, validate_copy,
)
from tests.operations.test_experiment_continuation import continuation, submit


def test_sealing_queues_once_without_worker_review_and_helper_failure_keeps_original(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch, presentation=True)
    stage = f.worker.call_tool("worker_experiment_stage", {"stage": "design", "conclusion": "Compare the exact measured target.",
        "limitations": ["Boundary remains uncertain."]})
    f.worker.call_tool("worker_experiment_stage", {"stage": "design", "conclusion": "Compare the exact measured target.",
        "limitations": ["Boundary remains uncertain."]})
    record = next(r for r in f.runs.tool_evidence(f.run_id) if r["alias"] == stage["reference"])
    ref = ArtifactRef.model_validate(record["artifact_ref"])
    original = f.runtime.artifacts.read(ref)
    store = store_for(f.runs)
    with store.connect() as db:
        rows = db.execute("SELECT * FROM display_summaries WHERE source_ref=?", (ref.model_dump_json(),)).fetchall()
    assert len(rows) == 1 and rows[0]["state"] == "queued"
    assert json.loads(rows[0]["profile"])["model"] == "gpt-6-luna"
    assert store.read("unrelated-instance", ref) is None
    def broken(*_):
        raise RuntimeError("backend unavailable")
    worker = SummaryWorker(f.runs, project_root=f.runtime.project_root, invoke=broken)
    for _ in range(20):
        if not worker.process_one():
            break
    assert store.read(f.instance.instance_id, ref)["state"] == "failed"
    assert f.runtime.artifacts.read(ref) == original and f.runs.status(f.run_id).state == "running"
    # No helper result, form field, approval, or owner confirmation is required.
    assert submit(f, [], outcome="inconclusive")["state"] == "completed"
    output = f.runs.status(f.run_id).output_ref
    assert store.read(f.instance.instance_id, output)["state"] == "queued"
    def generate(source, profile, settings, stop):
        assert settings.codex_home == str(f.runtime.project_root / ".scidiscovery-ui" / "display-codex")
        return {"items": [{"source": source["fragments"][0]["source"],
            "title": "<未定结论>", "summary": "边界仍不确定。"}]}, {"input_tokens": 120}
    assert SummaryWorker(f.runs, project_root=f.runtime.project_root, invoke=generate).process_one()
    copy = store.read(f.instance.instance_id, output)
    assert copy["state"] == "ready" and copy["usage"]["input_tokens"] == 120
    from scidiscovery.artifact_agent.approval_ui.workbench_render import _display_copy
    html = _display_copy({"key": "run:fixture", "display_copy": copy})
    assert "&lt;未定结论&gt;" in html and "自动导读" in html
    assert f.runs.status(f.run_id).output_ref == output


def test_summary_is_source_bound_and_cached_without_new_model_calls(tmp_path):
    payload = {"summary": "No fit established.", "limitations": ["Missing reference."],
               "metadata": {"tool_schema": "Must not be included."}, "value": 3.5}
    source = fragments(payload, max_bytes=1024)
    assert {i["source"] for i in source["fragments"]} == {"/summary", "/limitations/0"}
    assert "tool_schema" not in json.dumps(source)
    assert "3.5" not in json.dumps(source)
    value = {"items": [{"source": "/summary", "title": "拟合未成立", "summary": "尚未建立拟合。"}]}
    assert validate_copy(value, source) == value["items"]
    with pytest.raises(ValueError):
        validate_copy({"items": [{**value["items"][0], "source": "/invented"}]}, source)
    store = SummaryStore(tmp_path / "workbench.sqlite3")
    ref = ArtifactRef(artifact_id="original", sha256="a"*64, kind="fixture", schema_id="fixture.v1")
    settings, profile = PresentationSettings().model_dump(), {"model": "small", "reasoning_effort": "low"}
    key = store.enqueue("one", ref, settings, profile)
    assert store.enqueue("one", ref, settings, profile) == key
    assert store.claim()["cache_key"] == key
    store.finish(key, items=value["items"], usage={"input_tokens": 123, "output_tokens": 12})
    assert store.claim() is None
    assert store.read("one", ref)["usage"]["input_tokens"] == 123
    assert store.read("one", ref.model_copy(update={"sha256": "b"*64})) is None


def test_summary_workers_are_serial_and_do_not_repeat_interrupted_calls(tmp_path):
    store = SummaryStore(tmp_path / "ui/workbench.sqlite3")
    ref = ArtifactRef(artifact_id="original", sha256="a"*64, kind="fixture", schema_id="fixture.v1")
    store.enqueue("one", ref, PresentationSettings().model_dump(), {"model": "small"})
    runs = SimpleNamespace(database_path=tmp_path / "database/runs.sqlite3",
        agent_settings=SimpleNamespace(presentation=PresentationSettings(enabled=True)))
    worker = SummaryWorker(runs, project_root=tmp_path, invoke=lambda *_: pytest.fail("repeated uncertain model request"))
    with store.path.with_suffix(".summary.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert worker.process_one() is False
        assert store.claim() is not None
    assert worker.process_one() is False
    assert store.read("one", ref)["error_code"] == "interrupted"


def test_manual_retry_is_instance_scoped_and_old_clicks_cannot_start_another_attempt(tmp_path):
    store = SummaryStore(tmp_path / "workbench.sqlite3")
    ref = ArtifactRef(artifact_id="original", sha256="a"*64, kind="fixture", schema_id="fixture.v1")
    settings, profile = PresentationSettings().model_dump(), {"model": "small"}
    key = store.enqueue("one", ref, settings, profile)
    assert not store.retry("one", key, 0)  # Already queued.
    store.claim()
    assert not store.retry("one", key, 0)  # Running cannot be duplicated.
    store.finish(key, error="backend_unavailable")
    with pytest.raises(ValueError):
        store.retry("other-instance", key, 0)
    assert store.retry("one", key, 0)
    assert not store.retry("one", key, 0)
    claimed = store.claim()
    assert json.loads(claimed["source_ref"]) == ref.model_dump()
    assert claimed["retry_generation"] == 1
    store.finish(key, error="backend_unavailable")
    assert not store.retry("one", key, 0)  # Delayed duplicate after another failure.
    assert store.read("one", ref)["retry"]["generation"] == 1
    newer = store.enqueue("one", ref, settings, {"model": "updated-small"})
    assert not store.retry("one", key, 1)  # Superseded configuration.
    assert store.claim()["cache_key"] == newer


@pytest.mark.process_e2e
def test_manual_retry_http_requires_access_and_requeues_stage_and_final_copy(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from scidiscovery.artifact_agent.approval_ui.access import access_cookie
    from tests.operations.test_experiment_ui_trajectory import model_for
    from tests.operations.test_instance_browser_http import _request
    f = continuation(tmp_path, monkeypatch, presentation=True)
    stage = f.worker.call_tool("worker_experiment_stage", {"stage": "design", "conclusion": "Boundary remains uncertain."})
    record = next(r for r in f.runs.tool_evidence(f.run_id) if r["alias"] == stage["reference"])
    stage_ref = ArtifactRef.model_validate(record["artifact_ref"])
    assert submit(f, [], outcome="inconclusive")["state"] == "completed"
    output = f.runs.status(f.run_id).output_ref
    originals = [f.runtime.artifacts.read(ref) for ref in (stage_ref, output)]
    store = store_for(f.runs)
    while job := store.claim():
        store.finish(job["cache_key"], error="backend_unavailable")
    model = model_for(f)
    model.presentation_summaries = store
    ui = ApprovalUI(f.runtime.approvals, bindings=f.runtime.scheduler_bindings,
        read_model=model, instance_management_secret=b"summary-retry-fixture" * 3)
    base = ui.start()
    instance = f.instance.instance_id
    cookie = access_cookie(instance, ui.browser_access.issue(instance, maintenance=True))
    read_only = access_cookie(instance, ui.browser_access.issue(instance))
    page = f"/instance/{instance}/nodes/run%3Acontinuation"
    endpoint = f"/instance/{instance}/display-summary/retry"
    try:
        assert _request(base, "GET", page, cookie=read_only)[0] == 200
        assert b"data-summary-retry" not in _request(base, "GET", page, cookie=read_only)[2]
        status, _, body = _request(base, "GET", page, cookie=cookie)
        assert status == 200 and body.count(b"data-summary-retry") == 2
        for ref in (stage_ref, output):
            retry = store.read(instance, ref)["retry"]
            form = {"csrf": ui.session_id, "node_key": "run:continuation", **retry}
            if ref == stage_ref:
                form["stage_reference"] = stage["reference"]
            assert _request(base, "POST", endpoint, form=form)[0] == 403
            assert _request(base, "POST", endpoint, form=form, cookie=read_only)[0] == 403
            assert _request(base, "POST", endpoint, form={**form, "csrf": "wrong"}, cookie=cookie)[0] == 403
            assert _request(base, "POST", endpoint, form={**form, "cache_key": "foreign"}, cookie=cookie)[0] == 409
            with monkeypatch.context() as disabled:
                disabled.setattr(ui.bindings, "agent_settings", lambda _: {"settings": {"presentation": {"enabled": False}}})
                assert _request(base, "POST", endpoint, form=form, cookie=cookie)[0] == 409
            monkeypatch.setattr(ui, "_cache_writable", lambda _: False)
            assert _request(base, "POST", endpoint, form=form, cookie=cookie)[0] == 409
            monkeypatch.setattr(ui, "_cache_writable", lambda _: True)
            assert _request(base, "POST", endpoint, form=form, cookie=cookie)[0] == 303
            assert _request(base, "POST", endpoint, form=form, cookie=cookie)[0] == 303
            assert store.read(instance, ref)["state"] == "queued"
        assert b"data-summary-retry" not in _request(base, "GET", page, cookie=cookie)[2]
        with store.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM display_summaries WHERE retry_generation=1").fetchone()[0] == 2
        assert [f.runtime.artifacts.read(ref) for ref in (stage_ref, output)] == originals
        assert f.runs.status(f.run_id).state == "completed"
    finally:
        ui.stop()


@pytest.mark.process_e2e
def test_codex_adapter_uses_bounded_fresh_context_and_records_usage(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import presentation_summary_runner as runner
    from scidiscovery.artifact_agent.service.presentation_summary_runner import invoke_codex
    bounded = runner.run_bounded
    def observe(*args, **kwargs):
        result = bounded(*args, **kwargs)
        assert result.returncode == 0, result.stderr.decode()
        return result
    monkeypatch.setattr(runner, "run_bounded", observe)
    cli = tmp_path / "fake_codex.py"
    cli.write_text('''import json, sys
from pathlib import Path
assert "--ephemeral" in sys.argv and "--ignore-user-config" in sys.argv
assert sys.argv[sys.argv.index("--model")+1] == "configured-small"
text = sys.stdin.read()
assert "parent history" not in text
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"items":[{
"source":"/summary","title":"测试摘要","summary":"保留不确定性。"}]}))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":120,"cached_input_tokens":10,"output_tokens":20}}))
''')
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2] / "src"))
    value, usage = invoke_codex({"fragments": [{"source": "/summary", "text": "Uncertain."}], "source_excerpt_omitted": False},
        {"model": "configured-small", "reasoning_effort": "low"},
        PresentationSettings(command=[sys.executable, str(cli)]), threading.Event())
    assert value["items"][0]["title"] == "测试摘要"
    assert usage["input_tokens"] == 120 and usage["output_tokens"] == 20
    assert usage["model"] == "configured-small" and usage["input_bytes"] < 16384


@pytest.mark.process_e2e
def test_available_codex_launcher_can_start_under_display_memory_limit(monkeypatch):
    from shutil import which
    from scidiscovery.artifact_agent.service import presentation_summary_runner as runner
    codex = which("codex")
    if codex is None:
        pytest.skip("Codex CLI is not installed on this host")
    monkeypatch.setenv("SCID_CODEX_EXECUTABLE", codex)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2] / "src"))
    result = runner.run_bounded([sys.executable, "-m", runner.__name__, "2147483648", *runner.resolve_command(["codex"]), "exec", "--help"],
        input=b"", timeout=10, max_output_bytes=32768)
    assert result.returncode == 0, result.stderr.decode()
    assert b"--output-schema" in result.stdout and b"--ignore-user-config" in result.stdout


def test_display_command_respects_custom_configuration_and_reports_missing_launcher(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.presentation_summary_runner import resolve_command
    monkeypatch.setenv("SCID_CODEX_EXECUTABLE", str(tmp_path / "missing-codex"))
    monkeypatch.setenv("PATH", str(tmp_path))
    assert resolve_command([sys.executable, "custom.py"]) == [sys.executable, "custom.py"]
    with pytest.raises(RuntimeError, match="display_launcher_unavailable"):
        resolve_command(["codex"])
    cli = tmp_path / "codex"
    cli.write_text("#!/usr/bin/env node\n")
    cli.chmod(0o750)
    monkeypatch.setenv("SCID_CODEX_EXECUTABLE", str(cli))
    with pytest.raises(RuntimeError, match="display_interpreter_unavailable"):
        resolve_command(["codex"])


def test_display_home_seeds_login_once_without_research_history(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.presentation_summary_runner import display_environment
    original = tmp_path / "interactive"
    original.mkdir()
    (original / "auth.json").write_text('{"test_credential":"initial"}')
    (original / "config.toml").write_text("# user tools must not be loaded")
    (original / "requirements.toml").write_text("# managed restrictions")
    (original / "sessions").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(original))
    helper = tmp_path / "display"
    assert display_environment(str(helper))["CODEX_HOME"] == str(helper)
    assert (helper / "auth.json").read_bytes() == (original / "auth.json").read_bytes()
    assert helper.stat().st_mode & 0o777 == 0o700
    assert (helper / "auth.json").stat().st_mode & 0o777 == 0o600
    assert (helper / ".gitignore").read_text() == "*\n"
    assert not (helper / "sessions").exists() and not (helper / "config.toml").exists()
    (helper / "auth.json").write_text('{"test_credential":"refreshed"}')
    (original / "requirements.toml").write_text("# updated managed restrictions")
    display_environment(str(helper))
    assert "refreshed" in (helper / "auth.json").read_text()
    assert "initial" in (original / "auth.json").read_text()
    assert "updated" in (helper / "requirements.toml").read_text()
    with pytest.raises(ValueError, match="separate_absolute"):
        display_environment(str(original))


@pytest.mark.process_e2e
def test_default_display_command_uses_pinned_launcher_and_adjacent_node(tmp_path, monkeypatch):
    from shutil import which
    from scidiscovery.artifact_agent.service.presentation_summary_runner import invoke_codex
    node = which("node")
    if node is None:
        pytest.skip("Node is not installed on this host")
    binary = tmp_path / "user-node-bin"
    binary.mkdir()
    (binary / "node").symlink_to(node)
    cli = binary / "codex"
    cli.write_text('''#!/usr/bin/env node
const fs = require('fs');
fs.readFileSync(0);
fs.writeFileSync(process.argv[process.argv.indexOf('--output-last-message')+1], JSON.stringify({items:[
{source:'/summary',title:'Uncertain result',summary:'No solver was run.'}]}));
console.log(JSON.stringify({type:'turn.completed',usage:{input_tokens:123,output_tokens:12}}));
''')
    cli.chmod(0o750)
    monkeypatch.setenv("SCID_CODEX_EXECUTABLE", str(cli))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2] / "src"))
    value, usage = invoke_codex({"fragments": [{"source": "/summary", "text": "No solver was run."}],
        "source_excerpt_omitted": False}, {"model": "configured-small"}, PresentationSettings(), threading.Event())
    assert value["items"][0]["title"] == "Uncertain result"
    assert usage["input_tokens"] == 123


@pytest.mark.live_platform
def test_live_lightweight_display_copy_on_synthetic_text(monkeypatch, tmp_path):
    import os
    from shutil import which
    from scidiscovery.agent_execution_settings import AgentSettings
    from scidiscovery.artifact_agent.service.presentation_summary_runner import invoke_codex
    if os.environ.get("SCID_LIVE_UI_SUMMARY") != "1":
        pytest.skip("explicit opt-in required for a real model call")
    monkeypatch.setenv("SCID_CODEX_EXECUTABLE", which("codex") or "codex")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2] / "src"))
    settings = PresentationSettings(codex_home=str(tmp_path / "codex-home"), memory_limit_bytes=int(os.environ.get(
        "SCID_LIVE_UI_MEMORY_BYTES", PresentationSettings().memory_limit_bytes)))
    source = fragments({"summary": "合成验证：实验尚未执行，边界条件存在不确定性。"}, max_bytes=2048)
    try:
        value, usage = invoke_codex(source, AgentSettings().helpers.profiles["lightweight"].model_dump(),
            settings, threading.Event())
    except Exception as exc:
        diagnostic = Path(os.environ.get("SCID_LIVE_UI_DIAGNOSTIC", str(tmp_path / "display-helper-diagnostic.json")))
        diagnostic.touch(mode=0o600)
        diagnostic.write_text(json.dumps({key: (getattr(exc, key, None) or b"").decode("utf-8", errors="replace")
            for key in ("stdout", "stderr")}))
        pytest.fail(f"{exc}; diagnostic: {diagnostic}", pytrace=False)
    assert validate_copy(value, source)
    Path(os.environ.get("SCID_LIVE_UI_USAGE", str(tmp_path / "display-usage.json"))).write_text(json.dumps(usage))
    print("display_summary_usage=" + json.dumps(usage, ensure_ascii=False))


def test_default_display_policy_does_not_queue_or_claim_model_work(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.presentation_summaries import enqueue
    assert not PresentationSettings().enabled
    f = continuation(tmp_path, monkeypatch)
    assert not f.runs.agent_settings.presentation.enabled
    ref = f.runs.status(f.old_id).output_ref
    monkeypatch.setattr(f.runs.scheduler_bindings, "agent_settings",
        lambda _: {"settings": {"presentation": {"enabled": True}}})
    assert enqueue(f.runs, f.runs.status(f.run_id), ref) is None
    store = store_for(f.runs)
    key = store.enqueue(f.instance.instance_id, ref,
        PresentationSettings(enabled=True).model_dump(), {"model": "small"})
    worker = SummaryWorker(f.runs, project_root=tmp_path,
        invoke=lambda *_: pytest.fail("disabled display must not start a model"))
    assert worker.process_one() is False
    assert store.read(f.instance.instance_id, ref)["state"] == "queued"
