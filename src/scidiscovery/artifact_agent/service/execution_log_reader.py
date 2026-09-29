"""Bounded diagnostic tail navigation; cursors never select an execution."""
from __future__ import annotations

import base64
import hashlib
import json

from ...operation_contract import DiagnosticError, contract_diagnostic
from ...plugin_runtime.diagnostics import redact


def invalid(message):
    return DiagnosticError(message, details=(contract_diagnostic("execution_log_cursor_invalid",
        phase="tool_execution", affected_action="tool_call", repairable=True, message=message),))


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def log_page(execution_id, log_index, log, *, direction, cursor, max_bytes):
    if direction not in {"tail", "before", "after"}:
        raise invalid("Choose tail, before or after.")
    if (direction == "tail") != (cursor is None):
        raise invalid("tail starts at the newest page without a cursor; before/after require the returned cursor.")
    raw = redact(log.get("tail", "")).encode("utf-8")
    scope = _digest(f"{execution_id}:{log_index}".encode())
    identity = {key:log.get(key) for key in ("source", "stream_id", "start_byte", "size_bytes", "updated_at")}
    identity["source"] = _digest(str(identity["source"]).encode())
    snapshot = _digest(json.dumps(identity, sort_keys=True).encode() + raw)
    previous = None
    if cursor is not None:
        try:
            if len(cursor) > 2048:
                raise ValueError()
            previous = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
            assert previous['scope'] == scope and previous['v'] == 1
            assert type(previous['position']) is int and previous['position'] >= 0
            assert isinstance(previous['identity'], dict)
            assert all(isinstance(previous[key], str) and len(previous[key]) == 64 for key in ('snapshot', 'prefix'))
        except (ValueError, KeyError, TypeError, AssertionError):
            raise invalid("Cursor is invalid or belongs to another execution/log; start with tail.") from None
    gap = None
    if previous is not None and previous['snapshot'] != snapshot:
        # Only a stable source window plus exact prefix permits incremental reads.
        # Do not infer continuity by matching repeated solver lines in sliding tails.
        old = previous['identity']
        stable = (identity.get('stream_id') is not None
            and old.get('stream_id') == identity['stream_id']
            and identity.get('start_byte') is not None
            and old.get('start_byte') == identity['start_byte'])
        position = previous['position']
        if direction != 'after' or not stable or position > len(raw) or _digest(raw[:position]) != previous['prefix']:
            gap = 'snapshot_replaced'
            previous = None
    if previous is not None and previous['position'] > len(raw):
        raise invalid("Cursor exceeds the current snapshot; start with tail.")
    if previous is None or direction == 'before':
        end = len(raw) if previous is None else previous['position']
        start = max(0, end - max_bytes)
        while start < end and raw[start] & 0xC0 == 0x80:
            start += 1
    else:
        start = previous['position']
        end = min(len(raw), start + max_bytes)
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
    try:
        text = raw[start:end].decode('utf-8')
    except UnicodeDecodeError:
        raise invalid("Cursor is not at a text boundary; start with tail.") from None

    def token(position):
        data = {'v':1, 'scope':scope, 'snapshot':snapshot, 'position':position,
            'prefix':_digest(raw[:position]), 'identity':identity}
        # Source identities remain hashed inside the cursor, never paths/bindings.
        return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).decode().rstrip('=')

    return {'text':text, 'direction':direction, 'gap':gap,
        'before':token(start) if start else None, 'after':token(end),
        'has_more':end < len(raw) if direction == 'after' and not gap else start > 0,
        'cached_bytes':len(raw), 'source':redact(log.get('source', '')),
        'source_size_bytes':log.get('size_bytes'), 'source_truncated':bool(log.get('truncated'))}
