from __future__ import annotations

import hashlib
import sys
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from scidiscovery.artifact_agent.service import local_pdf_tool


def _descriptor(name, path, media):
    raw = path.read_bytes()
    return LocalFileDescriptor(name=name, local_path=str(path), media_type=media,
                               size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


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
