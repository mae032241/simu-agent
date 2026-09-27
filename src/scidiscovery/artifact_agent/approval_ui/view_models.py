"""Bounded JSON presentation values; these are not scientific contracts."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from ..schema.approval import parse_json_pointer


MAX_PAYLOAD_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024


class NodePage(TypedDict):
    items: list[dict[str, Any]]
    next_cursor: str | None


def gap(code: str, *, source_pointer: str = "", **details: Any) -> dict[str, Any]:
    return {"code": code, "source_pointer": source_pointer, **details}


def json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8"))


def bounded_record(value: Any, *, maximum: int = MAX_PAYLOAD_BYTES) -> dict[str, Any]:
    """Preserve small records exactly; never silently truncate a formal result."""

    try:
        size = json_size(value)
    except (ValueError, RecursionError):
        return {"payload_state": "unrenderable", "gaps": [gap("record_not_json_safe")]}
    if size > maximum:
        return {"payload_state": "too_large", "gaps": [gap("record_too_large", size_bytes=size)]}
    return {"payload_state": "available", "payload": value, "gaps": []}


def select_json(value: Any, pointer: str, *, after: int, limit: int) -> dict[str, Any]:
    """Select an exact pointer, or page its direct children if it is too large."""
    tokens = parse_json_pointer(pointer)
    try:
        for token in tokens:
            if isinstance(value, dict):
                value = value[token]
            elif isinstance(value, list) and token.isascii() and token.isdecimal() and (token == "0" or not token.startswith("0")):
                value = value[int(token)]
            else:
                raise KeyError(token)
    except (KeyError, IndexError):
        return {"payload_state": "missing", "gaps": [gap("pointer_missing", source_pointer=pointer)]}
    result = bounded_record(value)
    if result["payload_state"] != "too_large" or not isinstance(value, (dict, list)):
        return result
    keys = list(value) if isinstance(value, dict) else range(len(value))
    children, used_bytes = [], 0
    for key in keys[after:after + limit]:
        child = value[key]
        escaped = str(key).replace("~", "~0").replace("/", "~1")
        item = {"json_pointer": pointer + "/" + escaped,
                "type": "object" if isinstance(child, dict) else "array" if isinstance(child, list) else "value"}
        if len(item["json_pointer"]) > 4096:
            item = {"position": after + len(children), "gap": "child_pointer_too_long"}
        preview = bounded_record(child, maximum=1024)
        if preview["payload_state"] == "available":
            item["value"] = child
        used_bytes += json_size(item)
        if children and used_bytes > MAX_PAYLOAD_BYTES:
            break
        children.append(item)
    return {"payload_state": "navigation", "navigation": {
        "items": children, "child_count": len(value),
        "next_after": after + len(children) if after + len(children) < len(value) else None},
        "gaps": [gap("selected_value_too_large", source_pointer=pointer)]}
