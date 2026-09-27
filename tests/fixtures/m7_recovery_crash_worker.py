#!/usr/bin/env python3
"""Leave one valid local Worker draft, then simulate a transport crash."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path


def _call(process: subprocess.Popen[str], identifier: int, name: str) -> dict:
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": identifier,
                "method": "tools/call",
                "params": {"name": name, "arguments": {}},
            }
        )
        + "\n"
    )
    process.stdin.flush()
    response = json.loads(process.stdout.readline())
    if "error" in response:
        raise RuntimeError(str(response["error"]))
    return response["result"]["structuredContent"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--operation-digest", required=True)
    args = parser.parse_args(argv)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_local_worker",
            "--state-root",
            str(args.state_root),
            "--operation-id",
            args.operation_id,
            "--operation-digest",
            args.operation_digest,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ),
    )
    try:
        opened = _call(process, 1, "worker_open_assignment")
        structure = _call(process, 2, "worker_csv_summarize")
        draft_marker = "recovery-draft-only:" + secrets.token_hex(16)
        output = Path(opened["output_directory"])
        output.joinpath("result.json").write_text(
            json.dumps(
                {
                    "handoff": {
                        "assumptions": [draft_marker],
                        "summary": "Unsubmitted recovery draft.",
                        "verdict": "pass",
                    },
                    "payload": {
                        "interpretation": "The bounded arithmetic mean is two.",
                        "limitations": ["Two rows do not establish causality."],
                        "structure": structure,
                    },
                    "schema_version": 1,
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        process.stdin.close()
        if process.wait(timeout=10) != 0:
            assert process.stderr is not None
            raise RuntimeError(process.stderr.read())
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
    print(
        json.dumps(
            {
                "domain_tool_called": True,
                "draft_marker_sha256": hashlib.sha256(
                    draft_marker.encode("utf-8")
                ).hexdigest(),
                "draft_written": True,
                "opened_assignment": True,
                "schema_version": 1,
                "submitted": False,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 73


if __name__ == "__main__":
    raise SystemExit(main())
