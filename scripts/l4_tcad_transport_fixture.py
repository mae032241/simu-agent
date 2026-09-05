#!/usr/bin/env python3
"""Deterministic command transport used only by the persistent L4 probe."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _write(root: Path, name: str, content: bytes, media_type: str) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    if path.exists() and path.read_bytes() != content:
        raise RuntimeError("fixture output changed")
    if not path.exists():
        path.write_bytes(content)
    return {
        "schema_version": 1,
        "name": name.replace(".", "_"),
        "local_path": str(path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "media_type": media_type,
    }


def _handle(operation: str, payload: dict[str, object]) -> dict[str, object]:
    if operation == "capabilities":
        path = Path(os.environ["SCID_L4_CAPABILITY_FILE"])
        return {"capabilities": [json.loads(path.read_text("utf-8"))]}
    root = Path(str(payload.get("local_result_root") or os.environ["HOME"]))
    if operation == "prepare":
        raw = _canonical(
            {
                "job_spec": payload["job_spec"],
                "archive": payload["archive"],
            }
        )
        return {
            "submission": _write(
                root / "submissions",
                hashlib.sha256(raw).hexdigest() + ".json",
                raw,
                "application/json",
            )
        }
    if operation == "submit":
        submission = payload["submission"]
        assert isinstance(submission, dict)
        return {"run_id": "l4-" + str(submission["sha256"])[:24], "state": "succeeded"}
    if operation == "status":
        return {"state": "succeeded"}
    if operation == "cancel":
        return {"state": "cancelled"}
    if operation == "collect":
        run_id = str(payload["run_id"])
        output = root / "runs" / run_id
        manifest = _canonical(
            {
                "terminal_state": "succeeded",
                "exit_code": 0,
                "error": "",
                "outputs": ["profile.tdr"],
            }
        )
        log = b"L4 deterministic direct-solver fixture completed.\n"
        profile = b"L4-TDR-FIXTURE\n"
        values = [
            _write(output, "tcad_manifest.json", manifest, "application/json"),
            _write(output, "tcad_log.txt", log, "text/plain; charset=utf-8"),
            _write(output, "profile.tdr", profile, "application/octet-stream"),
        ]
        values[0]["name"] = "tcad_manifest"
        values[1]["name"] = "tcad_log"
        values[2]["name"] = "profile"
        return {"outputs": values}
    raise RuntimeError("unsupported fixture operation")


def main() -> int:
    request = json.loads(__import__("sys").stdin.buffer.read())
    operation = request["operation"]
    try:
        payload = _handle(operation, request["payload"])
        response = {
            "schema_version": 1,
            "operation": operation,
            "ok": True,
            "payload": payload,
        }
    except Exception as error:
        response = {
            "schema_version": 1,
            "operation": operation,
            "ok": False,
            "payload": {"error": type(error).__name__},
        }
    __import__("sys").stdout.buffer.write(_canonical(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
