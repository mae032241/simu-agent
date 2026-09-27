"""Unix-socket daemon for the execution-only TCAD dispatcher."""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path

from scidiscovery.plugin_runtime.transport import MCPRouter
from scidiscovery.plugin_runtime.transport import UnixSocketDaemon

from .execution_control import TCADExecutionFacade, TCADExecutionPolicy, TCADExecutionRouter


def build_execution_router(
    *,
    state_root: Path,
    policy_path: Path,
) -> MCPRouter:
    state = state_root.expanduser().absolute()
    state.mkdir(parents=True, exist_ok=True)
    if state.is_symlink() or not state.is_dir():
        raise ValueError("TCAD control state root must be a non-symlink directory")
    policy = TCADExecutionPolicy.model_validate_json(_read_regular(policy_path), strict=True)
    return MCPRouter(
        TCADExecutionRouter(TCADExecutionFacade(policy=policy, state_root=state)),
        name="tcad-control",
    )


def _read_regular(path: Path) -> bytes:
    source = path.expanduser().absolute()
    metadata = os.lstat(source)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"configuration must be a regular non-symlink file: {source}")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise ValueError(f"configuration must not be group/world writable: {source}")
    return source.read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tcad-control-daemon")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    args = parser.parse_args(argv)
    router = build_execution_router(
        state_root=args.state_root,
        policy_path=args.policy,
    )
    UnixSocketDaemon(args.socket, router, socket_mode=0o660).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_execution_router", "main"]
