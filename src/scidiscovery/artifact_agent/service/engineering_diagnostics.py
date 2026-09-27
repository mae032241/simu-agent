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
from ...plugin_runtime.diagnostics import redact, exception_facts
from ...plugin_runtime.workspace import atomic_json, read_json


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
