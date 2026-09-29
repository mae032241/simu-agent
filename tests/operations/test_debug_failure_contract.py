"""Real Worker error transport retains safe pre-submit causes and uncertainty."""
import json

import pytest

from scidiscovery.artifact_agent.interfaces.mcp import rpc_error
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_experiment_continuation import continuation


@pytest.mark.parametrize("failure", ["wall", "attempts", "prepare"])
def test_diagnostic_failure_is_actionable_without_leaking_control_details(tmp_path, monkeypatch, failure):
    f = continuation(tmp_path, monkeypatch)
    service = f.coordinator.worker_services["tcad_artifact:tcad.development_debug"]
    ledger_path = next((service.exchange_root / "budgets").glob("*.json"))
    ledger = json.loads(ledger_path.read_bytes())
    if failure == "wall":
        ledger["reserved_wall_seconds"] = ledger["debug_policy"]["total_wall_seconds"]
    elif failure == "attempts":
        ledger["debug_policy"]["max_runs"] = len(ledger["reservations"])
    else:
        def unavailable(**_):
            raise TimeoutError("private /control/socket credential=fixture-secret")
        monkeypatch.setattr(service.adapter, "prepare", unavailable)
    ledger_path.write_text(json.dumps(ledger))
    with pytest.raises(DiagnosticError) as caught:
        f.worker.call_tool("worker_experiment_debug", {"implementation": f.alias, "name": "new-diagnostic", "mode": "preflight"})
    wire = json.dumps(rpc_error(1, caught.value))
    expected = {"wall": "tcad_debug_wall_budget_exhausted", "attempts": "tcad_debug_attempts_exhausted",
                "prepare": "tcad_debug_prepare_failed"}[failure]
    assert expected in wire and "runtime_failure\", \"phase" not in wire
    assert "/control/socket" not in wire and "fixture-secret" not in wire
    assert caught.value.details[0]["repairable"] is False
    after = json.loads(ledger_path.read_bytes())
    assert "new-diagnostic" not in after["reservations"]
