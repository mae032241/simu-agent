"""Bounded redacted error facts and declared failure categories; no diagnostic store."""
from __future__ import annotations
import re
import subprocess
from pydantic import ValidationError

__all__ = ["redact", "exception_facts", "RunOutputError", "RunCheckerError"]

def redact(value: str) -> str:
    from .workspace import _SECRET
    value = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", "[redacted private key]", value)
    value = re.sub(r"Command ['\"].*(?:timed out|returned non-zero exit status|died with)", "Command [redacted argv] failed:", value)
    value = _SECRET.sub(b"[redacted]", value.encode("utf-8", errors="replace")).decode("utf-8")
    value = re.sub(r"(?i)\b(password|secret|token|credential|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+", r"\1=[redacted]", value)
    value = re.sub(r"(?<![\w])(?:/[\w.~-]+){2,}[^\s\"']*|[A-Za-z]:\\[^\s\"']+", "[host-path]", value)
    return value


def exception_facts(error: Exception, *, layer: str, action: str) -> dict:
    chain, seen, upstreams = [], set(), []
    current = error
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        upstream = getattr(current, "engineering", None)
        if isinstance(upstream, dict):
            upstreams.append(upstream)
        # Subprocess exception strings contain argv; expose the action, not argv.
        message = (f"Subprocess exceeded {current.timeout} seconds."
                   if isinstance(current, subprocess.TimeoutExpired) else
                   f"Subprocess exited with code {current.returncode}."
                   if isinstance(current, subprocess.CalledProcessError) else
                   "Declared field validation failed; see the contract diagnostic locations."
                   if isinstance(current, ValidationError) else str(current))
        item = {"type": type(current).__name__, "message": redact(message)[:2048]}
        for field in ("timeout", "returncode", "errno", "elapsed_seconds"):
            value = getattr(current, field, None)
            if isinstance(value, (int, float)):
                item[field] = value
        if getattr(current, "timeout_kind", None):
            item["timeout_kind"] = str(current.timeout_kind)[:80]
        chain.append(item)
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    for upstream in upstreams:
        if not isinstance(upstream.get("causes"), list):
            continue
        for cause in upstream["causes"][:8]:
            if not isinstance(cause, dict):
                continue
            item = {key: redact(str(cause.get(key, "")))[:2048] for key in ("type", "message")}
            for key in ("timeout", "returncode", "elapsed_seconds"):
                if isinstance(cause.get(key), (int, float)):
                    item[key] = cause[key]
            if cause.get("timeout_kind"):
                item["timeout_kind"] = redact(str(cause["timeout_kind"]))[:80]
            if item not in chain:
                chain.append(item)
    return {"layer": layer, "action": action,
            **({"origin_layer": redact(str(upstreams[-1].get("origin_layer", upstreams[-1].get("layer", "unknown"))))[:80]} if upstreams else {}),
            "causes": chain[:12],
            "category": "timeout" if any("timeout" in x or x["type"] == "TimeoutError" for x in chain) else "runtime_failure"}


class RunOutputError(RuntimeError):
    def __init__(
        self, message: str, *, details: tuple[dict[str, str], ...] = (), recorded: bool = False,
    ) -> None:
        super().__init__(message)
        self.details = details
        self.recorded = recorded


class RunCheckerError(RuntimeError):
    """Control integrity or checker failure, never a request to rewrite output."""

    def __init__(self, message: str, *, category: str = "checker_failure") -> None:
        super().__init__(message)
        self.category = category if category in {"checker_failure", "integrity_failure", "admission_defect", "tool_timeout"} else "checker_failure"
