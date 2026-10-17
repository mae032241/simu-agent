"""Progress survives the complete-task Worker path and reaches UI observations."""
import json

import pytest


def test_progress_projection_keeps_bounds_and_does_not_invent_measurements():
    from scidiscovery.plugin_runtime.experiment import progress_summary
    assert progress_summary(None) == {}
    assert progress_summary({"elapsed_seconds": float('nan')}) == {}
    original = {"private_binding": "unrelated", "log_tails": [
        {"source": "solver_log", "tail": "token=hidden /private/solver/run.log exe_abc123 " + "x" * 5000}
        for _ in range(20)]}
    result = progress_summary(original)
    assert "elapsed_seconds" not in result and "private_binding" not in result
    assert result["log_count"] == 20 and len(result["log_activity"]) == 2
    assert all("last_line" not in x for x in result["log_activity"])
    preview = progress_summary(original, include_log_text=True)
    assert all(x["last_line_truncated"] for x in preview["log_activity"])
    assert all(x not in json.dumps(preview) for x in ("hidden", "/private", "exe_abc123"))
    raw = json.dumps(result)
    assert len(raw) < 1500
    assert all(x not in raw for x in ("hidden", "/private", "exe_abc123"))
