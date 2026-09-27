"""Read Codex-owned identity metadata, outside model-controlled arguments.

Codex 0.157 shares the root thread's session ID with its descendants and omits
optional thread_source on ordinary Root turns. The identity relation determines
scope; redundant source/parent metadata must not contradict that relation.
"""

from dataclasses import dataclass
import re

from ...operation_contract import DiagnosticError


@dataclass(frozen=True)
class PlatformContext:
    session: str
    thread: str
    worker: bool
    model: str | None
    effort: str | None
    parent_thread: str | None = None
    subagent_kind: str | None = None


def platform_context(request):
    params = request.get("params", {})
    envelope = params.get("_meta", {}) if isinstance(params, dict) else {}
    meta = envelope.get("x-codex-turn-metadata", {}) if isinstance(envelope, dict) else {}
    if not isinstance(meta, dict):
        raise DiagnosticError("trusted platform session/thread metadata is required")
    session, thread = (meta.get(key) for key in ("session_id", "thread_id"))
    def valid_id(value):
        return isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", value)
    if not all(valid_id(value) for value in (session, thread)):
        raise DiagnosticError("trusted platform session/thread metadata is required")
    worker = session != thread
    source = meta.get("thread_source")
    parent = meta.get("parent_thread_id")
    kind = meta.get("subagent_kind")
    if (source not in (None, "user", "subagent")
            or (source is not None and (source == "subagent") != worker)
            or (parent is not None and (not valid_id(parent) or parent == thread))
            or (kind is not None and (not isinstance(kind, str) or not kind))
            or (not worker and (parent is not None or kind is not None))):
        raise DiagnosticError("trusted platform session/thread metadata is required")
    return PlatformContext(session, thread, worker, meta.get("model"), meta.get("reasoning_effort"), parent, kind)
