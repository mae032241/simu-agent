"""Bounded reading of an instance-named, immutable scientific original."""
from __future__ import annotations

import base64
import json

from ..schema.common import canonical_sha256
from .mcp_root_shared import RootToolError


def read_original_page(artifacts, envelope, *, name, instance, cursor, page_bytes):
    if (envelope.confidentiality == "approval_only"
            or envelope.schema_id == "scidiscovery.tool-evidence-manifest.v1"):
        raise RootToolError("This object is not a public scientific original.")
    media = envelope.media_type.split(";", 1)[0].strip().lower()
    if not (media.startswith("text/") or media == "application/json" or media.endswith("+json")):
        raise RootToolError("Original is binary; use its scientific presentation or an evidence task.")
    scope = canonical_sha256({"instance": instance, "name": name,
                              "ref": envelope.ref.model_dump(mode="json")})
    offset = 0
    if cursor is not None:
        try:
            value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            offset = value["offset"]
            if (value["scope"] != scope or type(offset) is not int
                    or offset < 0 or offset >= envelope.size_bytes):
                raise ValueError("wrong scope or offset")
        except (ValueError, KeyError, TypeError) as error:
            raise RootToolError("Invalid content_cursor; restart content reading for this exact name.") from error
    with artifacts.open_original(envelope.ref) as source:
        source.seek(offset)
        raw = source.read(page_bytes)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        if error.reason != "unexpected end of data" or offset + len(raw) == envelope.size_bytes:
            raise RootToolError("Original is not valid UTF-8 at the requested page.") from error
        raw = raw[:error.start]
        text = raw.decode("utf-8")
    end = offset + len(raw)
    next_cursor = None if end == envelope.size_bytes else base64.urlsafe_b64encode(
        json.dumps({"scope": scope, "offset": end}, separators=(",", ":")).encode()).decode()
    return {"name": name, "media_type": envelope.media_type, "size_bytes": envelope.size_bytes,
            "text": text, "offset_bytes": offset, "returned_bytes": len(raw),
            "complete": next_cursor is None, "next_cursor": next_cursor}
