#!/usr/bin/env python3
"""Materialize the explicitly selected TCAD runtime configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from tcad_artifact.execution_control import migrate_execution_policy_json


def _replace(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def configure(
    *,
    policy: Path,
    plugin_config: Path,
    state_root: Path,
    socket_path: Path,
    command_config: Path | None,
) -> None:
    if policy.exists():
        content, migrated = migrate_execution_policy_json(policy.read_bytes())
        if migrated:
            _replace(policy, content)
    else:
        payload = {
            "allowed_input_roots": [
                str(state_root.joinpath("execution-exchange").absolute())
            ],
            "max_concurrent_runs": 1,
            "tools": [{
                "arguments": [],
                "environment": {},
                "executable": str(Path("/bin/true").resolve()),
                "profile_id": "deployment_smoke",
                "public_arguments": [],
                "public_release_label": "Deployment smoke capability",
                "release_evidence": "deployment smoke executable",
                "solver_kind": "deterministic_tool",
            }],
        }
        _replace(
            policy,
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
        )
    transport = (
        {"transport": "command", "command_config_path": str(command_config)}
        if command_config is not None
        else {"transport": "socket", "socket_path": str(socket_path)}
    )
    _replace(
        plugin_config,
        json.dumps(transport, sort_keys=True, separators=(",", ":")).encode(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--plugin-config", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--command-config", type=Path)
    values = parser.parse_args(argv)
    configure(
        policy=values.policy,
        plugin_config=values.plugin_config,
        state_root=values.state_root,
        socket_path=values.socket,
        command_config=values.command_config,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
