"""Stream one PDF into a bounded local excerpt without artifact authority."""
from __future__ import annotations

import codecs
import hashlib
import math
import subprocess
from pathlib import Path
from typing import Any

from ..plugin_runtime.collection import run_bounded
from ..plugin_runtime.workspace import write_control_workspace_file


_TEXT_BYTES = 64 * 1024 * 1024
_STDERR_BYTES = 1024 * 1024


class _Excerpt:
    def __init__(self, first, last, max_chars):
        self.first, self.last, self.max_chars = first, last, max_chars
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.output_bytes = self.text_bytes = self.selected_chars = self.retained_chars = 0
        self.page = 1
        self.started = self.any_text = False
        self.parts = []

    def _retain(self, text):
        self.selected_chars += len(text)
        kept = text[:max(0, self.max_chars - self.retained_chars)]
        if kept:
            self.parts.append(kept)
            self.retained_chars += len(kept)

    def _text(self, text):
        self.text_bytes += len(text.encode("utf-8"))
        if self.text_bytes > _TEXT_BYTES:
            raise ValueError("PDF text extraction exceeds its byte limit")
        pieces = text.split("\f")
        for index, piece in enumerate(pieces):
            ended = index < len(pieces) - 1
            if piece or ended:
                selected = self.page >= self.first and (self.last is None or self.page <= self.last)
                if not self.started:
                    self.started = True
                    # A delimiter confirms even an empty page; the final
                    # delimiter does not manufacture an additional empty page.
                    if selected and self.page > self.first:
                        self._retain("\f")
                if piece:
                    self.any_text = True
                    if selected:
                        self._retain(piece)
            if ended:
                self.page += 1
                self.started = False

    def feed(self, raw):
        self.output_bytes += len(raw)
        if self.output_bytes > _TEXT_BYTES:
            raise ValueError("PDF text extraction exceeds its byte limit")
        self._text(self.decoder.decode(raw))

    def finish(self):
        self._text(self.decoder.decode(b"", final=True))
        total = self.page - 1 + int(self.started)
        if not total or not self.any_text:
            raise ValueError("PDF text extraction produced no text")
        if self.first > total:
            raise ValueError("PDF first_page exceeds the extracted page count")
        return "".join(self.parts).encode("utf-8"), total


def _stderr_record(context: Any, raw: bytes):
    truncated = len(raw) > _STDERR_BYTES
    raw = raw[:_STDERR_BYTES]
    if not raw:
        return None, truncated
    path = Path(".operation-tools/pdf") / ("stderr_" + hashlib.sha256(raw).hexdigest() + ".log")
    write_control_workspace_file(context.workspace, path, raw, replace=False, mode=0o400, create_parents=True)
    return str(context.workspace / path), truncated


def _failure(context, message, stderr):
    log, truncated = _stderr_record(context, stderr)
    suffix = f"; stderr log: {log}" if log else ""
    if truncated:
        suffix += f"; stderr truncated after {_STDERR_BYTES} bytes"
    return ValueError(message + suffix)


def extract_pdf_text_local(parsed: Any, context: Any) -> dict[str, Any]:
    """Count all streamed pages; retain only the requested range and excerpt.

    The complete stream is needed for the exact document page count. Selection
    occurs as it arrives, without retaining other pages or the complete text.
    Only pdftotext is required, as before; no metadata utility is introduced.
    """
    if context.input_media_type(parsed.name).split(";", 1)[0].strip().lower() != "application/pdf":
        raise ValueError("PDF extraction requires application/pdf")
    if parsed.last_page is not None and parsed.last_page < parsed.first_page:
        raise ValueError("last_page must not precede first_page")
    remaining = context.remaining_seconds
    if not math.isfinite(remaining) or remaining <= 0:
        raise ValueError("PDF text extraction has no finite remaining time")
    timeout = min(60.0, remaining)
    excerpt = _Excerpt(parsed.first_page, parsed.last_page, parsed.max_chars)
    try:
        completed = run_bounded(
            ["pdftotext", "-layout", str(context.input_path(parsed.name)), "-"],
            input=b"", timeout=timeout, sink=excerpt.feed,
            # The shared helper bounds stderr independently of the stdout sink.
            # One extra byte detects overflow without keeping the full stream.
            max_output_bytes=_STDERR_BYTES + 1,
        )
    except FileNotFoundError as error:
        raise ValueError("pdftotext is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise _failure(context, "PDF text extraction timed out", error.stderr or b"") from error
    except ValueError as error:
        # run_bounded kills/reaps the owned process group on a sink failure.
        raise _failure(context, str(error), getattr(error, "stderr", b"")) from error
    if len(completed.stderr) > _STDERR_BYTES:
        raise _failure(context, "PDF stderr exceeds its capture limit", completed.stderr)
    stderr_log, _ = _stderr_record(context, completed.stderr)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-2048:]
        raise _failure(context, f"PDF text extraction failed: {detail}", completed.stderr)
    raw, total = excerpt.finish()
    selected_last = min(parsed.last_page or total, total)
    digest = hashlib.sha256(
        (parsed.name + f"\0{parsed.first_page}\0{selected_last}\0{parsed.max_chars}\0").encode("utf-8") + raw
    ).hexdigest()
    path = Path(".operation-tools/pdf") / f"excerpt_{digest[:20]}.txt"
    destination = write_control_workspace_file(context.workspace, path, raw,
        replace=False, mode=0o400, create_parents=True)
    return {
        "name": parsed.name,
        "media_type": "text/plain; charset=utf-8",
        "local_path": str(destination),
        "size_bytes": len(raw),
        "access": "read_only",
        "first_page": parsed.first_page,
        "last_page": selected_last,
        "available_page_count": total,
        "truncated": excerpt.selected_chars > parsed.max_chars,
        "cache": "run_local",
        "stderr_log": stderr_log,
    }


__all__ = ["extract_pdf_text_local"]
