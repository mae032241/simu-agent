"""Crash-window subprocess used by the minimal Run recovery test."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from scidiscovery.artifact_agent.runtime import open_runtime


def main() -> None:
    mode, project_root, state_root, run_id = sys.argv[1:]
    runtime = open_runtime(project_root=Path(project_root), state_root=Path(state_root))
    status = runtime.runs.status(run_id)
    if mode == "before_discard":
        runtime.runs._finish_failed_workspace = lambda _value: os._exit(71)
    elif mode == "after_move":
        original = runtime.runs.backend.discard

        def discard_then_crash(*args, **kwargs):
            original(*args, **kwargs)
            os._exit(72)

        runtime.runs.backend.discard = discard_then_crash
    else:
        raise ValueError("unknown crash probe mode")
    runtime.runs.record_failure(
        run_id,
        reason=f"subprocess crash probe: {mode}",
        expected_state=status.state,
        expected_last_activity_at=status.last_activity_at,
    )


if __name__ == "__main__":
    main()
