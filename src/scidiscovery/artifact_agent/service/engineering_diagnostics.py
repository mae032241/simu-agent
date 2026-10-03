"""Bounded engineering facts, separate from scientific output contracts."""
from __future__ import annotations

import json
import hashlib
import fcntl
import time
import os
from pathlib import Path
import re
import stat
import subprocess
import traceback
from datetime import datetime, timezone
from ...plugin_runtime.diagnostics import redact, exception_facts
from ...plugin_runtime.workspace import atomic_json, read_json


def diagnostic_locator(engineering: object) -> dict:
    """Expose only a bounded opaque handle; bodies require a scoped explicit read."""
    if not isinstance(engineering, dict):
        return {}
    reference = engineering.get("reference")
    if not isinstance(reference, str) or not re.fullmatch(r"diag_[0-9a-f]{32}", reference):
        return {}
    sections = engineering.get("available_sections", ())
    return {"reference": reference, "available_sections": [name for name in
        ("summary", "traceback", "stdout", "stderr")
        if isinstance(sections, (list, tuple)) and name in sections]}


class EngineeringDiagnostics:
    def __init__(self, root: Path, *, settings=None):
        from ...agent_execution_settings import DiagnosticsSettings
        self.root = Path(root)
        self.settings = settings or DiagnosticsSettings()
        self._configured_settings = settings

    def prune(self):
        """Apply configured retention during the daemon's existing maintenance pass."""
        if not self.root.exists():
            return
        if self.root.is_symlink():
            raise ValueError("engineering diagnostic root must not be a symlink")
        fd = os.open(self.root / ".retention.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._prune()

    def _prune(self):
        # Capture callers in other processes share the daemon's configured policy.
        # Otherwise a default-configured reader/writer could undo an increased limit.
        from ...agent_execution_settings import DiagnosticsSettings
        policy_path = self.root / ".retention.json"
        stored = read_json(policy_path, max_bytes=4096) if policy_path.exists() else None
        if self._configured_settings is None:
            self.settings = DiagnosticsSettings.model_validate(stored or {})
        elif stored != self.settings.model_dump():
            atomic_json(policy_path, self.settings.model_dump())
        # Only expendable diagnostics are removed. CAS and Run evidence are elsewhere.
        groups = {}
        for entry in self.root.iterdir():
            if not re.fullmatch(r"diag_[0-9a-f]{32}\.(json|stdout|stderr)", entry.name) or entry.is_symlink():
                continue
            try:
                info = entry.stat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                groups.setdefault(entry.stem, []).append((entry, info))
        cutoff = time.time() - self.settings.retention_seconds
        retained, total = 0, 0
        for files in sorted(groups.values(), key=lambda files: max(info.st_mtime for _, info in files), reverse=True):
            size = sum(info.st_size for _, info in files)
            if (max(info.st_mtime for _, info in files) >= cutoff
                    and retained < self.settings.max_records and total + size <= self.settings.max_total_bytes):
                retained += 1
                total += size
                continue
            for path, _ in files:
                path.unlink(missing_ok=True)

    def capture(self, error: Exception, *, scope: str, layer: str, action: str) -> dict:
        facts = exception_facts(error, layer=layer, action=action)
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
            trace = "".join(traceback.format_exception(error))[-65536:]
            # Exact repeated failures reuse a bounded slot; the scope is part of identity.
            signature = json.dumps([scope, layer, action, facts["causes"], trace,
                {name: hashlib.sha256(raw).hexdigest() for name, raw in logs.items()}], sort_keys=True, ensure_ascii=False)
            reference = "diag_" + hashlib.sha256(signature.encode()).hexdigest()[:32]
            lock_fd = os.open(self.root / ".retention.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(lock_fd, "r+b") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                self._prune()
                for name, raw in logs.items():
                    fd = os.open(self.root / (reference + "." + name), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(raw[:min(8 * 1024 * 1024, self.settings.max_total_bytes // 4)])
                    sections.append(name)
                atomic_json(self.root / (reference + ".json"), {
                    "scope": scope, "created_at": datetime.now(timezone.utc).isoformat(),
                    "public": facts, "traceback": trace, "sections": sections,
                    "public_traceback": self._public_traceback(error, facts),
                })
                self._prune()
                if (self.root / (reference + ".json")).is_file():
                    facts["reference"] = reference
                    facts["available_sections"] = sections
                else:
                    facts["retention"] = "trace_exceeded_storage_budget"
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
            # Source lines may contain literals and quoted paths; neither is
            # needed to locate the failing function in a public diagnostic.
            frames.extend('  File [host-path], line ' + str(frame.lineno) + ', in ' + frame.name + '\n'
                for frame in traceback.extract_tb(current.__traceback__))
            current = current.__cause__ or current.__context__
        return redact("".join(frames)[-49152:] + "\n" + json.dumps(facts, ensure_ascii=False))

    def read(self, reference: str, *, scopes: tuple[str, ...], offset: int = 0, max_bytes: int = 16384, section="summary") -> dict:
        if not re.fullmatch(r"diag_[0-9a-f]{32}", reference):
            raise ValueError("invalid engineering diagnostic reference")
        if not (self.root / (reference + ".json")).exists():
            raise ValueError("engineering diagnostic expired or unavailable; sealed scientific evidence is unaffected")
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
