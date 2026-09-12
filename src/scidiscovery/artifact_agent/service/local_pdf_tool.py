"""Run-local PDF extraction for the trusted local Operation backend."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

from .local_workspace import write_control_workspace_file


def _stderr_record(context: Any, raw: bytes) -> str:
    if len(raw) > 1024 * 1024:
        raise ValueError("PDF stderr exceeds its 1 MiB capture limit")
    path = Path(".operation-tools/pdf") / ("stderr_" + hashlib.sha256(raw).hexdigest() + ".log")
    write_control_workspace_file(context.workspace, path, raw, replace=True, mode=0o400, create_parents=True)
    return str(context.workspace / path)


def extract_pdf_text_local(parsed: Any, context: Any) -> dict[str, Any]:
    """Materialize one bounded excerpt without control or Artifact authority."""

    if context.input_media_type(parsed.name).split(";", 1)[0].strip().lower() != "application/pdf":
        raise ValueError("PDF extraction requires application/pdf")
    if parsed.last_page is not None and parsed.last_page < parsed.first_page:
        raise ValueError("last_page must not precede first_page")
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", str(context.input_path(parsed.name)), "-"],
            check=False,
            capture_output=True,
            timeout=max(1, min(60, context.remaining_seconds)),
        )
    except FileNotFoundError as error:
        raise ValueError("pdftotext is not installed") from error
    except subprocess.TimeoutExpired as error:
        log = _stderr_record(context, error.stderr or b"")
        raise ValueError(f"PDF text extraction timed out; stderr log: {log}") from error
    stderr_log = _stderr_record(context, completed.stderr) if completed.stderr else None
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-2048:]
        raise ValueError(f"PDF text extraction failed; stderr log: {stderr_log}; excerpt: {detail}")
    text = completed.stdout.decode("utf-8", errors="replace")
    if len(text.encode("utf-8")) > 64 * 1024 * 1024:
        raise ValueError("PDF text extraction exceeds its byte limit")
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    if not pages or all(not page for page in pages):
        raise ValueError("PDF text extraction produced no text")
    if parsed.first_page > len(pages):
        raise ValueError("PDF first_page exceeds the extracted page count")
    selected_last = min(parsed.last_page or len(pages), len(pages))
    selected = "\f".join(pages[parsed.first_page - 1 : selected_last])
    raw = selected[: parsed.max_chars].encode("utf-8")
    digest = hashlib.sha256(
        (
            parsed.name
            + f"\0{parsed.first_page}\0{selected_last}\0{parsed.max_chars}\0"
        ).encode("utf-8")
        + raw
    ).hexdigest()
    directory = context.workspace / ".operation-tools" / "pdf"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = directory / f"excerpt_{digest[:20]}.txt"
    if destination.exists():
        if destination.is_symlink() or destination.read_bytes() != raw:
            raise ValueError("existing PDF excerpt differs")
    else:
        temporary = directory / f".{destination.name}.{os.getpid()}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.fchmod(descriptor, 0o400)
        finally:
            os.close(descriptor)
        os.replace(temporary, destination)
    return {
        "name": parsed.name,
        "media_type": "text/plain; charset=utf-8",
        "local_path": str(destination),
        "size_bytes": len(raw),
        "access": "read_only",
        "first_page": parsed.first_page,
        "last_page": selected_last,
        "available_page_count": len(pages),
        "truncated": len(selected) > parsed.max_chars,
        "cache": "run_local",
        "stderr_log": stderr_log,
    }


__all__ = ["extract_pdf_text_local"]
