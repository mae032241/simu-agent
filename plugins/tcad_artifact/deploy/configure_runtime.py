#!/usr/bin/env python3
"""Materialize the explicitly selected TCAD runtime configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from tcad_artifact.execution_control import TCADExecutionPolicy
from tcad_artifact.command_adapter import CommandAdapterConfig


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
    # External executors supply their own policy through the adapter. A leftover
    # local-daemon policy is neither their configuration nor their authority.
    if command_config is not None:
        CommandAdapterConfig.model_validate_json(command_config.read_bytes(), strict=True)
    else:
        # Never invent execution authority for a local daemon.
        if not policy.is_file():
            raise ValueError("execution policy is missing; supply the administrator configuration")
        TCADExecutionPolicy.model_validate_json(policy.read_bytes(), strict=True)
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
