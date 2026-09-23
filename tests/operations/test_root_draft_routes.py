"""Exercise draft routing through the existing Root and local Worker surfaces."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput, RootToolError
from tests.operations.test_l2_run_invariants import _envelope, _invoke, _system, _worker


def _request(name: str, **extra):
    return {
        "name": name,
        "operation_id": "blind.csv.observe.v1",
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
        "instruction": "Make one bounded observation.",
        **extra,
    }


def test_producer_inputs_projects_frozen_ports_with_paging_and_instance_name_boundary(tmp_path, monkeypatch):
    catalog, runtime, instance, source, root = _system(tmp_path)
    _invoke(root, "observation")
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(_envelope())
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    run_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="run", name="observation")
    before_run = runtime.runs.status(run_id)
    before_bindings = runtime.scheduler_bindings.list(
        instance=instance.instance_id, namespace="artifact")

    projection = root.call_tool("artifact_catalog", {
        "name": "observation.output", "view": "producer_inputs"})
    assert projection["producer"] == {
        "kind": "run", "operation_id": before_run.operation_id,
        "operation_version": before_run.operation_version,
        "operation_digest": before_run.operation_digest,
        "availability": "current", "unavailable_reason": None}
    assert projection["producer_input_count"] == 1 and projection["next_offset"] is None
    assert projection["producer_inputs"] == [{
        "port_name": "source_table", "item_index": 1,
        "artifact_ref": source.ref.model_dump(mode="json"),
        "artifact_name": "source_csv", "source_name": "source_table",
        "current_access_name": "source_csv", "kind": source.ref.kind,
        "schema": source.ref.schema_id}]
    assert root.call_tool("artifact_catalog", {"name": "observation.output",
        "view": "producer_inputs", "parent_offset": 1})["producer_inputs"] == []
    with pytest.raises(RootToolError, match="producer_input_count"):
        root.call_tool("artifact_catalog", {"name": "observation.output",
            "view": "producer_inputs", "parent_offset": 2})
    assert runtime.runs.status(run_id) == before_run
    assert runtime.scheduler_bindings.list(
        instance=instance.instance_id, namespace="artifact") == before_bindings

    original_find = runtime.scheduler_bindings.find_name
    monkeypatch.setattr(runtime.scheduler_bindings, "find_name", lambda **values:
        None if values["object_id"] == source.artifact_id else original_find(**values))
    unbound = root.call_tool("artifact_catalog", {
        "name": "observation.output", "view": "producer_inputs"})
    assert unbound["producer_inputs"][0]["artifact_name"] == "source_csv"
    assert unbound["producer_inputs"][0]["current_access_name"] is None
    monkeypatch.setattr(runtime.scheduler_bindings, "find_name", original_find)

    output_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name="observation.output")
    other = runtime.scheduler_bindings.create_instance(
        name="other", title="Other", objective="Cross-instance read boundary")
    runtime.scheduler_bindings.bind(
        instance=other.instance_id, namespace="artifact", name="local_alias",
        object_id=output_id)
    runtime.scheduler_bindings.bind(
        instance=other.instance_id, namespace="artifact", name="local_source",
        object_id=source.artifact_id)
    root.facade.instance = other.instance_id
    cross = root.call_tool("artifact_catalog", {
        "name": "local_alias", "view": "producer_inputs"})
    assert cross["producer"]["availability"] == "cross_instance"
    assert cross["producer"]["unavailable_reason"] == "cross_instance"
    assert cross["producer_inputs"][0]["artifact_name"] is None
    assert cross["producer_inputs"][0]["source_name"] is None
    assert cross["producer_inputs"][0]["current_access_name"] == "local_source"


def test_producer_inputs_imported_artifact_is_explicitly_unavailable(tmp_path):
    _, _, _, source, root = _system(tmp_path)
    projection = root.call_tool("artifact_catalog", {
        "name": "source_csv", "view": "producer_inputs"})
    assert projection["subject"]["artifact_ref"] == source.ref.model_dump(mode="json")
    assert projection["producer"]["availability"] == "unavailable"
    assert projection["producer"]["unavailable_reason"] == "producer_unavailable"
    assert projection["producer_inputs"] == []
    assert projection["parents_fallback"] == {
        "tool": "artifact_catalog", "name": "source_csv", "view": "parents"}


def test_root_projects_exact_bindings_and_ordered_parent_metadata_without_payload_reads(tmp_path, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    _, runtime, root, request, artifacts, register = system
    # Two parents with the same schema must stay separate and ordered.
    second = register('another_plan', runtime.artifacts.read(artifacts['plan'].ref), artifacts['plan'].schema_id)
    register('many_parents', b'{}', 'opaque', parents=(artifacts['plan'].ref, second.ref))
    monkeypatch.setattr(runtime.artifacts, 'read', lambda *a: pytest.fail('metadata query read scientific payload'))
    parents = root.call_tool('artifact_catalog', {'name': 'many_parents', 'view': 'detail'})
    assert [p['artifact_name'] for p in parents['parents']] == parents['parent_artifact_names']
    assert [p['schema'] for p in parents['parents']] == [artifacts['plan'].schema_id] * 2
    first = root.call_tool('artifact_catalog', {'name': 'many_parents', 'view': 'parents', 'parent_limit': 1})
    second_page = root.call_tool('artifact_catalog', {'name': 'many_parents', 'view': 'parents',
        'parent_limit': 1, 'parent_offset': first['next_offset']})
    assert first['parents'] + second_page['parents'] == parents['parents']
    assert first['parent_count'] == 2 and second_page['next_offset'] is None
    assert 'parent_artifact_names' not in first
    with pytest.raises(RootToolError, match='parent_offset'):
        root.call_tool('artifact_catalog', {'name': 'many_parents', 'view': 'parents', 'parent_offset': 3})
    before = runtime.runs.status(worker._run_id)
    status = root.call_tool('run_status', {'name': 'analysis', 'view': 'detail', 'output_paths': []})
    expected = {}
    for item in before.inputs:
        expected.setdefault(item.port_name, []).append(item.artifact_name)
    assert status['bound_inputs'] == [dict(port=p, artifact_names=n) for p, n in expected.items()]
    assert runtime.runs.status(worker._run_id) == before
    assert all('bound_inputs' not in item for item in root.call_tool('run_list', {})['runs'])
    original_find = runtime.scheduler_bindings.find_name
    monkeypatch.setattr(runtime.scheduler_bindings, 'find_name', lambda **kw:
        None if kw['object_id'] == second.artifact_id else original_find(**kw))
    missing = root.call_tool('artifact_catalog', {'name': 'many_parents', 'view': 'detail'})['parents'][1]
    assert missing == dict(artifact_name=None, schema=None, kind=None, producer=None)
    original_list = runtime.scheduler_bindings.list
    monkeypatch.setattr(runtime.scheduler_bindings, 'list', lambda **kw:
        tuple(b for b in original_list(**kw) if b.name != before.inputs[0].artifact_name))
    assert root.call_tool('run_status', {'name': 'analysis', 'view': 'detail', 'output_paths': []})['bound_inputs'][0]['artifact_names'] == [None]


def _failed_source(catalog, runtime, root):
    _invoke(root, "draft_source")
    opened = _worker(catalog, runtime).call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope("PRIVATE_UNACCEPTED_DRAFT")
    )
    status = root.call_tool("run_status", {"name": "draft_source"})
    return root.call_tool("run_record_failure", {
        "name": "draft_source", "reason": "agent exited",
        "expected_state": "running",
        "expected_last_activity_at": status["last_activity_at"],
    })


def test_root_draft_source_handoff_is_not_scientific_output(tmp_path):
    catalog, runtime, _, _, root = _system(tmp_path)
    status = _failed_source(catalog, runtime, root)
    assert "sealed_output" not in status
    assert status["recovery"]["delivery_preserved"]
    assert status["recovery"]["draft_available"]
    assert "PRIVATE_UNACCEPTED_DRAFT" not in json.dumps(status)
    assert "PRIVATE_UNACCEPTED_DRAFT" not in json.dumps(root.call_tool("run_list", {}))
    request = _request("draft_successor", draft_from="draft_source")
    assert root.call_tool("operation_preflight", request)["admissible"]
    result = root.call_tool("operation_invoke", request)["result"]
    assert result["draft_from"] == "draft_source"
    assert "sealed_output" not in result
    opened = _worker(catalog, runtime).call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text())
    assert assignment["recovery_draft"]["scientific_evidence"] is False
    assert "PRIVATE_UNACCEPTED_DRAFT" in Path(
        opened["workspace_path"], "recovery-draft/result.json"
    ).read_text()


@pytest.mark.parametrize("extra, reason", [
    ({"draft_from": "missing", "resume_from": "missing"}, "recovery_sources_mutually_exclusive"),
    ({"draft_from": "missing"}, "draft_source_unavailable"),
])
def test_root_draft_rejection_creates_no_run(tmp_path, extra, reason):
    _, _, _, _, root = _system(tmp_path)
    request = _request("rejected_draft", **extra)
    assert root.call_tool("operation_preflight", request)["reason_code"] == reason
    with pytest.raises(RootToolError, match=reason):
        root.call_tool("operation_invoke", request)
    assert root.call_tool("run_list", {}) == {"runs": [], "next_before": None}


def test_root_draft_fingerprint_binds_controlled_digest(tmp_path, monkeypatch):
    catalog, runtime, _, _, root = _system(tmp_path)
    _failed_source(catalog, runtime, root)
    request = OperationCallInput.model_validate(_request("new_run", draft_from="draft_source"))
    values = request.model_dump()
    values["inputs"] = request.inputs
    bound, _ = root.facade._configured_operation_call(values)
    first = root.facade._prepare_local_run(
        bound, "reject", resume_from=None, draft_from="draft_source"
    )
    monkeypatch.setattr(runtime.runs, "validate_draft_source", lambda *a, **kw: "f" * 64)
    second = root.facade._prepare_local_run(
        bound, "reject", resume_from=None, draft_from="draft_source"
    )
    assert first[0:2] == second[0:2]
    assert first[2] != second[2]
    assert first[3] != second[3]


def test_root_draft_rejects_foreign_instance_even_with_local_alias(tmp_path):
    catalog, runtime, instance, _, root = _system(tmp_path)
    _failed_source(catalog, runtime, root)
    source_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="run", name="draft_source"
    )
    other = runtime.scheduler_bindings.create_instance(
        name="other_instance", title="Other instance", objective="Isolation test"
    )
    source_artifact_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name="source_csv"
    )
    runtime.scheduler_bindings.bind(
        instance=other.instance_id, namespace="artifact", name="source_csv",
        object_id=source_artifact_id,
    )
    runtime.scheduler_bindings.bind(
        instance=other.instance_id, namespace="run", name="foreign_source",
        object_id=source_id,
    )
    root.facade.instance = other.instance_id
    request = _request("foreign_successor", draft_from="foreign_source", max_attempts=100)
    assert root.call_tool("operation_preflight", request)["reason_code"] == "draft_source_unavailable"
    with pytest.raises(RootToolError, match="draft_source_unavailable"):
        root.call_tool("operation_invoke", request)
    with pytest.raises(Exception, match="unknown run name"):
        runtime.scheduler_bindings.resolve(
            instance=other.instance_id, namespace="run", name="foreign_successor"
        )


@pytest.mark.parametrize("route", ["draft_from", "resume_from"])
def test_scheduler_attempt_budget_extends_frozen_chain_and_replays_idempotently(tmp_path, route):
    catalog, runtime, instance, _, root = _system(tmp_path)
    _failed_source(catalog, runtime, root)
    source_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="run", name="draft_source")
    original = runtime.runs.status(source_id)

    def fail_next(request):
        assert root.call_tool("operation_preflight", request)["admissible"]
        root.call_tool("operation_invoke", request)
        worker = _worker(catalog, runtime)
        opened = worker.call_tool("worker_open_assignment", {})
        Path(opened["output_directory"], "result.json").write_bytes(_envelope())
        value = runtime.runs.status(worker._run_id)
        runtime.runs.record_failure(value.run_id, reason="bounded fixture interruption",
            expected_state=value.state, expected_last_activity_at=value.last_activity_at)
        return runtime.runs.status(worker._run_id)

    fail_next(_request("second", **{route: "draft_source"}))
    request = _request("third", **{route: "second"})
    rejection = root.call_tool("operation_preflight", request)
    assert rejection["reason_code"] == "recovery_attempt_limit_reached", rejection
    detail = rejection["diagnostics"][0]
    assert detail["path"] == "$.max_attempts"
    assert "2 Runs used, limit 2" in detail["message"]
    assert root.call_tool("run_status", {"name": "second"})["recovery"]["attempt_budget"] == dict(used=2, limit=2)
    request["max_attempts"] = 4
    third = fail_next(request)
    assert third.recovery_policy["scheduler_max_attempts"] == 4
    fourth_request = _request("fourth", **{route: "third"})
    fourth = fail_next(fourth_request)
    assert fourth.recovery_policy["max_attempts"] == 4
    assert runtime.runs.status(source_id) == original  # No old policy, request or draft mutation.
    assert root.call_tool("run_status", {"name": "fourth"})["recovery"]["attempt_budget"] == dict(used=4, limit=4)
    assert root.call_tool("operation_preflight", _request("fifth", **{route: "fourth"}))["reason_code"] == "recovery_attempt_limit_reached"
    before = root.call_tool("run_list", {})
    assert root.call_tool("operation_preflight", fourth_request)["admissible"]
    root.call_tool("operation_invoke", fourth_request)
    assert root.call_tool("run_list", {}) == before
    changed = {**fourth_request, "max_attempts": 5}
    assert root.call_tool("operation_preflight", changed)["reason_code"] == "semantic_name_conflict"
    changed.update(on_conflict="create_revision")
    assert root.call_tool("operation_preflight", changed)["admissible"]


def test_schedule_rechecks_attempt_budget_after_another_run_consumes_it(tmp_path):
    from scidiscovery.artifact_agent.service.run_records import RunAttemptLimit
    catalog, runtime, instance, _, root = _system(tmp_path)
    _failed_source(catalog, runtime, root)
    request = OperationCallInput.model_validate(_request("stale", draft_from="draft_source", max_attempts=2))
    values = request.model_dump(); values["inputs"] = request.inputs
    bound, _ = root.facade._configured_operation_call(values)
    assert root.call_tool("operation_preflight", request.model_dump())["admissible"]
    root.call_tool("operation_invoke", _request("winner", draft_from="draft_source"))
    source_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace="run", name="draft_source")
    with pytest.raises(RunAttemptLimit, match="2 Runs used, limit 2"):
        runtime.runs.schedule(bound, instance_id=instance.instance_id,
            output_binding_name="stale", output_logical_name="stale", output_revision=1,
            output_binding_fingerprint="a" * 64, draft_from=source_id, max_attempts=2)
    assert len(root.call_tool("run_list", {})["runs"]) == 2


@pytest.mark.parametrize("value", [0, -1, True, "3", 1.5])
def test_scheduler_attempt_budget_is_a_positive_integer(value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        OperationCallInput.model_validate(_request("invalid", max_attempts=value))


def test_attempt_budget_mcp_contract_and_non_agent_applicability(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    catalog, _, _, _, root = _system(tmp_path)
    router = MCPRouter(root, name='root_fixture')
    schema = router.handle(dict(jsonrpc='2.0',id=1,method='tools/list'))['result']['tools']
    for name in ['operation_preflight', 'operation_invoke']:
        contract = next(t for t in schema if t['name'] == name)['inputSchema']
        assert contract['properties']['max_attempts']['anyOf'][0] == dict(type='integer',minimum=1)
        assert 'max_attempts' not in contract.get('required', [])
    items = root.call_tool('operation_catalog', {'scope':'all', 'operation_id':'blind.csv.observe.v1', 'view':'detail'})['operations']
    assert next(i for i in items if i['operation_id'] == 'blind.csv.observe.v1')['default_max_attempts'] == 2
    operation = next(catalog.operation(key) for key in catalog.operation_ids()
        if catalog.operation(key).spec.executor.kind != 'agent')
    request = _request('non_agent', operation_id=operation.spec.operation_id, max_attempts=3)
    result = root.call_tool('operation_preflight', request)
    assert result['reason_code'] == 'attempt_limit_not_applicable'
