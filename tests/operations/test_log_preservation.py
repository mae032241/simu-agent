from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from scidiscovery.artifact_agent.service import local_pdf_tool
from tcad_artifact import worker, remote_runner_py36
from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge, _sanitize_log


def _descriptor(name, path, media):
    raw = path.read_bytes()
    return LocalFileDescriptor(name=name, local_path=str(path), media_type=media,
                               size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("purpose", ["development_debug", "production"])
def test_middle_error_survives_collection_and_is_located_before_excerpt(tmp_path, remote, purpose):
    work = tmp_path / "work"
    work.mkdir()
    # The error is near the end of stdout, then becomes the middle of a
    # combined stdout + solver log. Head/tail summarization used to lose it.
    raw = b"Checking syntax of main.cmd:\n" + b"startup banner\n" * 1000
    raw += b'Error: invalid command name "broken_output"\n(file "main.cmd" line 18)\n'
    solver = b"routine solver detail\n" * 1000
    (tmp_path / "worker.log").write_bytes(raw)
    (work / "main.log").write_bytes(solver)
    (work / "additional.err").write_bytes(b"ADDITIONAL DIAGNOSTIC")
    job = {"execution_purpose": purpose, "arguments": ["main.cmd"]}
    if remote:
        remote_runner_py36._augment_development_debug_log(str(tmp_path), job)
    else:
        worker._augment_development_debug_log(tmp_path, job)
    assert (tmp_path / "worker.log").read_bytes() == raw
    complete = (tmp_path / "diagnostic.log").read_bytes()
    assert raw in complete and solver in complete
    assert b"ADDITIONAL DIAGNOSTIC" in complete
    assert "broken_output" not in _sanitize_log(complete)
    manifest = tmp_path / "output_manifest.json"
    manifest.write_text(json.dumps({"terminal_state": "failed", "exit_code": 1, "error": "", "outputs": []}))
    adapter = SimpleNamespace(collect=lambda _: (
        _descriptor("tcad_log", tmp_path / "diagnostic.log", "text/plain"),
        _descriptor("tcad_manifest", manifest, "application/json"),
    ))
    result = TCADDevelopmentDebugBridge(adapter).collect("fixture")
    assert result.diagnostic_layer == "parser"
    assert "broken_output" in result.source_diagnostic.message
    full = next(item.content for item in result.files if item.name == "debug.log.txt")
    assert b"broken_output" in full
    assert b"bounded diagnostic omission" not in full
    assert len(result.log_excerpt) < 8400


@pytest.mark.parametrize("remote", [False, True])
def test_oversize_log_is_not_replaced_by_an_excerpt(tmp_path, remote):
    (tmp_path / "work").mkdir()
    raw = b"x" * (256 * 1024 + 1)
    (tmp_path / "worker.log").write_bytes(raw)
    (tmp_path / "work/main.log").write_text("tail")
    job = {"execution_purpose": "development_debug", "arguments": ["main.cmd"]}
    with pytest.raises(ValueError, match="capture limit; original file retained"):
        if remote:
            remote_runner_py36._augment_development_debug_log(str(tmp_path), job)
        else:
            worker._augment_development_debug_log(tmp_path, job)
    assert (tmp_path / "worker.log").read_bytes() == raw
    assert not (tmp_path / "diagnostic.log").exists()


def test_pdf_stderr_file_keeps_error_outside_display_tail(tmp_path, monkeypatch):
    raw = b"FIRST ACTIONABLE ERROR\n" + b"trailing noise\n" * 1000
    monkeypatch.setattr(local_pdf_tool.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout=b"", stderr=raw))
    context = SimpleNamespace(workspace=tmp_path, remaining_seconds=60,
                              input_media_type=lambda _: "application/pdf",
                              input_path=lambda _: tmp_path / "input.pdf")
    parsed = SimpleNamespace(name="paper", first_page=1, last_page=None)
    with pytest.raises(ValueError, match="stderr log"):
        local_pdf_tool.extract_pdf_text_local(parsed, context)
    logs = tuple((tmp_path / ".operation-tools/pdf").glob("stderr_*.log"))
    assert len(logs) == 1 and logs[0].read_bytes() == raw


def test_complete_debug_log_is_published_with_the_gap(tmp_path, monkeypatch):
    from dataclasses import replace
    import test_l4_local_tcad as fixture
    from tcad_artifact.debug_contract import CollectedTCADDebugFile

    worker_router, adapter, opened = fixture._budget_case(tmp_path)
    raw = b"detail\n" * 30000 + b"ACTIONABLE MIDDLE ERROR\n" + b"detail\n" * 30000
    collect = adapter.collect
    monkeypatch.setattr(adapter, "collect", lambda value: replace(
        collect(value), log_excerpt="short display", files=(
            CollectedTCADDebugFile(name="debug.log.txt", media_type="text/plain", content=raw),
        ),
    ))
    result = worker_router.call_tool("worker_tcad_debug_run", {"run_name": "full", "mode": "preflight"})
    assert result["log_excerpt"] == "short display"
    assert result["log_excerpt_is_complete"] is False
    log = Path(opened["workspace_path"]) / result["log_relative_path"]
    assert log.read_bytes() == raw
    fixture._write_gap(opened)
    assert worker_router.call_tool("worker_submit_result", {})["state"] == "completed"
    payload = json.loads(Path(opened["output_directory"], "result.json").read_bytes())["payload"]
    saved = next(item for item in payload["attempt_files"] if item["relative_path"] == "reports/log-full.txt")
    assert saved["content"].encode() == raw


@pytest.mark.parametrize("returncode", [0, 1])
def test_command_transport_error_retains_stderr_instead_of_only_message(tmp_path, returncode):
    from tcad_artifact.command_adapter import CommandAdapterConfig, CommandTCADExecutorAdapter
    raw = b"FIRST ERROR\n" + b"trailing detail\n" * 1000
    script=tmp_path/'broken_transport.py'
    script.write_text('import sys,json\nassert json.load(sys.stdin)["operation"]=="capabilities"\n'
        f'sys.stderr.buffer.write({raw!r})\n'
        'print(\'{"schema_version":1,"operation":"capabilities","ok":false,"error":"protocol failure"}\')\n'
        f'raise SystemExit({returncode})\n')
    adapter = CommandTCADExecutorAdapter(CommandAdapterConfig(executable=sys.executable,arguments=(str(script),)), local_result_root=tmp_path)
    with pytest.raises(RuntimeError):
        adapter.capabilities()
    assert next((tmp_path / "logs").glob("*.stderr.log")).read_bytes() == raw
    assert b"protocol failure" in next((tmp_path / "logs").glob("*.stdout.log")).read_bytes()


def test_missing_capture_does_not_qualify_successful_process():
    from tcad_artifact.debug_adapter import _earliest_diagnostic
    layer, summary = _earliest_diagnostic(terminal="succeeded", exit_code=0,
        error="diagnostic collection failed: limit", log="", output_count=1)
    assert layer == "output_contract" and "incomplete" in summary


@pytest.mark.parametrize("remote", [False, True])
def test_real_worker_process_keeps_stderr_and_separate_diagnostic_file(tmp_path, remote):
    work = tmp_path / "work"
    work.mkdir()
    (work / "main.cmd").write_text('echo STDOUT_MARKER\necho STDERR_FAILURE >&2\necho SOLVER_DETAIL > main.log\nexit 1\n')
    job = {"executable": "/bin/sh", "arguments": ["main.cmd"], "environment": {},
           "execution_purpose": "production", "expected_outputs": [],
           "limits": {"cpu_time_seconds": 5, "wall_time_seconds": 5,
                      "max_memory_bytes": 128 * 1024 * 1024, "max_output_bytes": 1024 * 1024}}
    (tmp_path / ("runtime.json" if remote else "job.json")).write_text(json.dumps(job))
    if remote:
        cmd = [sys.executable, "-c", "import runpy,sys; raise SystemExit(runpy.run_path(sys.argv[1])['_run_worker']({},sys.argv[2]))", remote_runner_py36.__file__, str(tmp_path)]
    else:
        cmd = [sys.executable, worker.__file__, str(tmp_path)]
    result = subprocess.run(cmd, capture_output=True, timeout=15)
    assert result.returncode == 1, result.stderr
    raw = (tmp_path / "worker.log").read_bytes()
    assert b"STDOUT_MARKER" in raw and b"STDERR_FAILURE" in raw
    assert b"SOLVER_DETAIL" not in raw
    full = (tmp_path / "diagnostic.log").read_bytes()
    assert raw in full and b"SOLVER_DETAIL" in full
    assert json.loads((tmp_path / "output_manifest.json").read_bytes())["exit_code"] == 1
