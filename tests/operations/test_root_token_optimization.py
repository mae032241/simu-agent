"""Omission-aware Root reads, frozen dispatch, and lossless invoke compression."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_root_run_routes import RootRunRoutes
from scidiscovery.artifact_agent.interfaces.mcp_response_views import operation_invoke_contract
from tests.operations.test_unified_mcp import call, result


PAYLOAD = {"summary": "sealed", "limitations": ["exact"], "large": "文" * 12000}
PROFILE = {"profile": {"model": "frozen-model", "reasoning_effort": "high"},
           "sources": {"model": "operation_default"}}


class ReadFixture(RootRunRoutes):
    session_key = None

    def __init__(self, state="running"):
        self.value = SimpleNamespace(state=state, operation_id="fixture.v1", operation_version="1",
            operation_digest="a" * 64, agent_type="frozen-worker", execution_profile=deepcopy(PROFILE),
            deadline_at="frozen-deadline", last_activity_at="activity", run_id="private-id",
            output_binding_name="run.output", output_ref=SimpleNamespace(kind="science", schema_id="report.v1"),
            reason="UNSEALED_SCIENCE" * 300, inputs=[], backend_id="test",
            signal=SimpleNamespace(model_dump=lambda **_: {"verdict": "accept"}))
        self.bindings = SimpleNamespace(list=lambda **kwargs: (
            [SimpleNamespace(name="run", object_id="private-id")] if kwargs["namespace"] == "run" else []))
        self.artifacts = SimpleNamespace(read=Mock(return_value=json.dumps(PAYLOAD).encode()))
        self.runs = SimpleNamespace(status=Mock(return_value=self.value), recovery_available=Mock(return_value=False),
            diagnostic_events=Mock(return_value={"events": [{"diagnostic": {"message": "exact saved error"}}], "next_after": None}),
            evidence_output_refs=Mock(return_value=[]))
        self._operation_catalog = SimpleNamespace(operation=lambda _: SimpleNamespace(
            spec=SimpleNamespace(version="1"), digest="a" * 64))
        self.engineering_diagnostics = SimpleNamespace(capture=Mock())
        self.detail_reads = Mock()

    def _instance_id(self):
        return "fixture"

    def _resolve(self, namespace, name):
        return "private-id"

    def _run_status_value(self, name, value):
        self.detail_reads()
        return {"name": name, "state": value.state, "reason": value.reason,
            "diagnostic_summary": {"failure": "exact saved error"},
            "recovery": {"coverage": "long"}, "tool_timing": ["long"]}


@pytest.mark.parametrize("state", ["queued", "running", "completed", "failed", "timed_out", "cancelled", "future_active"])
def test_default_is_short_for_every_state_without_diagnostic_or_payload_assembly(state):
    facade = ReadFixture(state)
    direct = facade.run_status(name="run")
    routed = RootMCPRouter(facade).call_tool("run_status", {"name": "run"})
    assert direct == routed
    assert direct["execution_profile"] == {"profile": PROFILE["profile"]}
    assert direct["agent_type"] == "frozen-worker" and direct["deadline_at"] == "frozen-deadline"
    assert not {"reason", "diagnostic_summary", "recovery", "tool_timing", "scheduler_signal", "sealed_output"} & direct.keys()
    assert len(json.dumps(direct, ensure_ascii=False).encode()) <= 1024
    facade.detail_reads.assert_not_called()
    facade.artifacts.read.assert_not_called()
    facade.runs.diagnostic_events.assert_not_called()


@pytest.mark.parametrize("state", ["queued", "running", "future_active"])
@pytest.mark.parametrize("arguments", [
    {"view": "detail", "diagnostic_after": 0},
    {"view": "detail", "response_profile": "compat", "include_full_output": True},
    {"response_profile": "decision", "output_paths": ["/summary"]},
    {"response_profile": "navigation", "output_mode": "index"},
])
def test_active_status_and_list_gate_before_content_assembly(state, arguments):
    facade = ReadFixture(state)
    gateway = UnifiedMCPRouter(RootMCPRouter(facade), worker_backend="local")
    direct = facade.run_status(name="run", **arguments)
    assert result(call(gateway, "run_status", {"name": "run", **arguments})) == direct
    listing = facade.run_list(state=None, limit=20, view="detail")
    assert result(call(gateway, "run_list", {"view": "detail"})) == listing
    assert "UNSEALED_SCIENCE" not in json.dumps([direct, listing])
    facade.detail_reads.assert_not_called()
    facade.artifacts.read.assert_not_called()
    facade.runs.diagnostic_events.assert_not_called()


@pytest.mark.parametrize("paths", [None, []])
@pytest.mark.parametrize("enabled", [None, False, True])
def test_full_output_positive_opt_in_only(paths, enabled):
    facade = ReadFixture("completed")
    request = {"view": "detail", "response_profile": "compat", "output_paths": paths}
    if enabled is not None:
        request["include_full_output"] = enabled
    gateway = UnifiedMCPRouter(RootMCPRouter(facade), worker_backend="local")
    if enabled and paths == []:
        with pytest.raises(RootToolError, match="include_full_output"):
            facade.run_status(name="run", **request)
        assert "include_full_output" in call(gateway, "run_status", {"name": "run", **request})["error"]["message"]
        facade.runs.status.assert_not_called()
    else:
        direct = facade.run_status(name="run", **request)
        assert direct == result(call(gateway, "run_status", {"name": "run", **request}))
        assert direct["sealed_output"] == ({"artifact_name": "run.output", "kind": "science", "schema": "report.v1", "payload": PAYLOAD} if enabled else None)
        if not enabled:
            facade.artifacts.read.assert_not_called()


@pytest.mark.parametrize("arguments", [
    {"include_full_output": 1}, {"include_full_output": "true"},
    {"include_full_output": True},
    {"include_full_output": True, "view": "detail", "output_mode": "index"},
    {"include_full_output": True, "response_profile": "decision", "output_paths": ["/summary"]},
    {"include_full_output": True, "view": "detail", "output_paths": ["/summary"]},
    {"response_profile": "decision", "output_paths": [""]},
    {"response_profile": "decision", "output_paths": ["/summary", ""]},
    {"response_profile": "compat", "output_paths": ["/summary", ""]},
    {"response_profile": "poll", "output_paths": ["/summary"]},
    {"output_paths": ["/summary"]},
])
def test_invalid_requests_reject_before_state_read_at_both_entries(arguments):
    facade = ReadFixture("completed")
    with pytest.raises(RootToolError) as direct:
        facade.run_status(name="run", **arguments)
    gateway = UnifiedMCPRouter(RootMCPRouter(facade), worker_backend="local")
    error = call(gateway, "run_status", {"name": "run", **arguments})["error"]
    if direct.value.details:
        assert error["data"]["diagnostics"] == list(direct.value.details)
    else:
        assert str(direct.value) in error["message"]
    facade.runs.status.assert_not_called()
    facade.artifacts.read.assert_not_called()


def test_large_scalar_historical_output_and_failed_diagnostics_remain_readable():
    facade = ReadFixture("completed")
    facade._operation_catalog.operation = Mock(side_effect=KeyError("retired"))
    selection = facade.run_status(name="run", response_profile="decision", output_paths=["/large"])
    assert selection["selected_output"]["items"][0]["status"] == "omitted"
    index = facade.run_status(name="run", response_profile="navigation", output_mode="index", output_paths=["/large"])
    assert index["output_index"]["next_offset"] is None and not index["output_index"]["children"]
    full = facade.run_status(name="run", view="detail", include_full_output=True)
    assert full["sealed_output_status"] == "historical" and full["sealed_output"]["payload"] == PAYLOAD
    facade.value.state = "failed"
    facade.artifacts.read.reset_mock()
    failed = facade.run_status(name="run", view="detail", include_full_output=True, diagnostic_after=0)
    assert failed["sealed_output"] is None and failed["reason"] == facade.value.reason
    assert failed["diagnostic_events"]["events"][0]["diagnostic"]["message"] == "exact saved error"
    facade.artifacts.read.assert_not_called()


def test_mixed_list_gates_each_item_and_retains_terminal_details():
    facade = ReadFixture()
    active = facade.value
    failed = deepcopy(active)
    failed.state = "failed"
    facade.bindings.list = lambda **_: [SimpleNamespace(name="active", object_id="active"), SimpleNamespace(name="failed", object_id="failed")]
    facade.runs.status.side_effect = lambda identity: active if identity == "active" else failed
    gateway = UnifiedMCPRouter(RootMCPRouter(facade), worker_backend="local")
    for listing in (facade.run_list(state=None, limit=20, view="detail"), result(call(gateway, "run_list", {"view": "detail"}))):
        assert "reason" not in listing["runs"][0]
        assert listing["runs"][1]["reason"] == failed.reason
        assert listing["runs"][1]["diagnostic_summary"] == {"failure": "exact saved error"}


def expand_contract(value):
    expanded = deepcopy(value)
    defaults = expanded.pop("defaults", {})
    for collection in ("inputs", "outputs"):
        expanded[collection] = [{**defaults.get(collection, {}), **port} for port in expanded.get(collection, [])]
    for key in ("defaults_rule", "contract_view_version", "full"):
        expanded.pop(key, None)
    return expanded


def test_compact_contract_round_trip_preserves_unknown_constraints_and_optional_ports():
    port = {"name": "required", "schema": "s.v1", "description": "scientific binding semantics",
        "min_items": 1, "max_items": 1, "required_non_null_fields": [], "usage": "claim_evidence",
        "exposure": "full", "require_current": True, "media_types": ["application/json"], "max_item_bytes": 4096}
    declaration = {"operation_id": "fixture.v1", "inputs": [port,
        {**port, "name": "progress", "min_items": 0, "future_constraint": {"exact": True}},
        {**port, "name": "objective"}], "outputs": [], "future_admission": {"all": ["a", "b"]}}
    original = deepcopy(declaration)
    legacy = operation_invoke_contract(declaration, revision_policy={}, representation="legacy")
    compact = operation_invoke_contract(declaration, revision_policy={})
    assert expand_contract(compact) == legacy and declaration == original
    assert compact["inputs"][1]["min_items"] == 0
    assert len(json.dumps(compact)) < len(json.dumps(legacy))
    changed = deepcopy(declaration)
    changed["inputs"][0]["max_item_bytes"] = 8192
    assert expand_contract(operation_invoke_contract(changed, revision_policy={})) == operation_invoke_contract(changed, revision_policy={}, representation="legacy")


def test_lost_receipt_recovers_original_dispatch_after_settings_change(tmp_path):
    from scidiscovery.agent_execution_settings import parse_settings
    from tests.operations.test_l2_run_invariants import _system, _invoke
    _, runtime, _, _, root = _system(tmp_path)
    created = _invoke(root, "observation")["result"]
    repeated = _invoke(root, "observation")["result"]
    frozen = ("agent_type", "execution_profile", "deadline_at", "operation_id", "operation_version", "operation_digest")
    assert all(repeated[key] == created[key] for key in frozen)
    runtime.runs.agent_settings = parse_settings({"defaults": {"model": "different-model", "reasoning_effort": "low"}})
    recovered = root.facade.run_status(name="observation", view="detail")
    assert all(recovered[key] == created[key] for key in frozen)
    assert recovered["execution_profile"]["profile"]["model"] != "different-model"
    gateway = UnifiedMCPRouter(root, worker_backend="local")
    profile = recovered["execution_profile"]["profile"]
    result(call(gateway, "worker_attach", {"name": "observation", "thread_id": "recovered-child"}))
    opened = result(call(gateway, "worker_open_assignment", child="recovered-child", profile=profile))
    assert opened["state"] == "opened"


def test_compiled_catalog_contracts_expand_without_loss_or_identity_changes():
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import scheduler_operation_view
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import operation_detail, operation_revision_policy
    from tests.operations.test_l4_local_tcad import CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
    from tests.operations.test_l2_run_invariants import BLIND_CSV_PLUGIN
    catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, BLIND_CSV_PLUGIN))
    digest = catalog.digest()
    compact_bytes = legacy_bytes = 0
    kinds = set()
    for identity in catalog.operation_ids():
        compiled = catalog.operation(identity)
        source = operation_detail(scheduler_operation_view(compiled.spec).model_dump(mode="json", by_alias=True))
        source["operation_digest"] = compiled.digest
        revision = operation_revision_policy(compiled.spec)
        legacy = operation_invoke_contract(source, revision_policy=revision, representation="legacy")
        compact = operation_invoke_contract(source, revision_policy=revision)
        assert expand_contract(compact) == legacy, identity
        assert compact["operation_digest"] == compiled.digest
        kinds.add(compiled.spec.executor.kind)
        legacy_bytes += len(json.dumps(legacy, ensure_ascii=False, separators=(",", ":")).encode())
        compact_bytes += len(json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode())
    assert {"agent", "transform", "approval", "effect"} <= kinds
    assert catalog.digest() == digest
    assert compact_bytes < legacy_bytes
    print(f"compiled invoke contracts: legacy={legacy_bytes} compact={compact_bytes} bytes; operations={len(catalog.operation_ids())}")


def test_summary_catalog_keeps_exact_purpose_and_rejects_stale_or_legacy_cursors():
    from tests.operations.test_mcp_response_views import router
    entries = [{"operation_id": f"operation{index}", "purpose": "界限" * 90 + "禁止越界",
        "operation_digest": str(index) * 64} for index in range(3)]
    root = router(operation_catalog=lambda **arguments: {"scope": arguments["scope"], "operations": entries})
    first = root.call_tool("operation_catalog", {"limit": 1})
    assert first["operations"] == [{"operation_id": entries[0]["operation_id"], "purpose": entries[0]["purpose"]}]
    assert first["returned"] == 1 and not first["complete"]
    for before in ("operation0",):
        with pytest.raises(RootToolError, match="restart_query"):
            root.call_tool("operation_catalog", {"before": before})
    with pytest.raises(RootToolError, match="cursor_query_mismatch"):
        root.call_tool("operation_catalog", {"scope": "support", "before": first["next_before"]})
    entries[1]["operation_digest"] = "changed"
    with pytest.raises(RootToolError, match="catalog_changed"):
        root.call_tool("operation_catalog", {"before": first["next_before"]})
