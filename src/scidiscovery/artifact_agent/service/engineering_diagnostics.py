"""Bounded engineering facts, separate from scientific output contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import traceback
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError


def redact(value: str) -> str:
    from .local_workspace import _SECRET
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


def atomic_json(path: Path, value: dict, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("engineering record path must not be a symlink")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, *, max_bytes: int = 128 * 1024) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("engineering record is not a regular file")
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("engineering record exceeds its byte bound")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("engineering record must be an object")
    return value


class EngineeringDiagnostics:
    def __init__(self, root: Path):
        self.root = Path(root)

    def capture(self, error: Exception, *, scope: str, layer: str, action: str) -> dict:
        facts = exception_facts(error, layer=layer, action=action)
        reference = "diag_" + uuid.uuid4().hex
        try:
            sections = ["summary", "traceback"]
            current, seen = error, set()
            logs = {}
            while current is not None and id(current) not in seen and len(seen) < 8:
                seen.add(id(current))
                for name in ("stdout", "stderr"):
                    raw = getattr(current, name, None)
                    if isinstance(raw, bytes) and raw and name not in logs:
                        logs[name] = raw[:8 * 1024 * 1024]
                current = current.__cause__ or current.__context__
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.root.is_symlink():
                raise ValueError("engineering diagnostic root must not be a symlink")
            for name, raw in logs.items():
                fd = os.open(self.root / (reference + "." + name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                sections.append(name)
            atomic_json(self.root / (reference + ".json"), {
                "scope": scope, "created_at": datetime.now(timezone.utc).isoformat(),
                "public": facts, "traceback": "".join(traceback.format_exception(error))[-65536:], "sections": sections,
                # Validation exception text may echo arbitrary rejected input. The
                # private traceback stays intact; public frames use safe facts.
                "public_traceback": self._public_traceback(error, facts),
            })
            facts["reference"] = reference
            facts["available_sections"] = sections
        except Exception as recording_error:
            facts["recording_error"] = exception_facts(recording_error, layer="diagnostic_storage", action="record")
        error.engineering = facts
        return facts

    @staticmethod
    def _public_traceback(error, facts):
        frames, seen = [], set()
        current = error
        while current is not None and id(current) not in seen and len(seen) < 8:
            seen.add(id(current))
            frames.append(type(current).__name__ + "\n")
            frames.extend(traceback.format_tb(current.__traceback__))
            current = current.__cause__ or current.__context__
        return redact("".join(frames)[-49152:] + "\n" + json.dumps(facts, ensure_ascii=False))

    def read(self, reference: str, *, scopes: tuple[str, ...], offset: int = 0, max_bytes: int = 16384, section="summary") -> dict:
        if not re.fullmatch(r"diag_[0-9a-f]{32}", reference):
            raise ValueError("invalid engineering diagnostic reference")
        record = read_json(self.root / (reference + ".json"), max_bytes=512 * 1024)
        if record.get("scope") not in scopes:
            raise ValueError("engineering diagnostic belongs to another instance or session")
        if section == "summary":
            raw = json.dumps({"created_at": record["created_at"], **record["public"]}, ensure_ascii=False).encode()
        elif section == "traceback":
            raw = redact(record.get("public_traceback", record["traceback"])).encode()
        elif section in {"stdout", "stderr"} and section in record.get("sections", ()):
            fd = os.open(self.root / (reference + "." + section), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("diagnostic log is not a regular file")
                content = stream.read(8 * 1024 * 1024)
            raw = redact(content.decode("utf-8", errors="replace")).encode()
        else:
            raise ValueError("diagnostic section is unavailable")
        return {"reference": reference, "section": section, "available_sections": record.get("sections", ["summary", "traceback"]),
                "offset": offset, "total_bytes": len(raw),
                "text": raw[offset:offset + max_bytes].decode("utf-8", errors="replace"),
                "next_offset": offset + max_bytes if offset + max_bytes < len(raw) else None}
