"""Read-only workbench boundaries, using isolated control stores."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.approval_ui.read_model import (
    InstanceReadModel, ReadModelNotFound, ReadModelScopeError,
)
from scidiscovery.artifact_agent.approval_ui.view_models import MAX_PAYLOAD_BYTES, MAX_RESPONSE_BYTES, json_size
from scidiscovery.artifact_agent.schema.approval import approval_options_template
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ActorRef
from scidiscovery.artifact_agent.schema.run_signal import SchedulerSignal
from scidiscovery.artifact_agent.service.approvals import ApprovalService
from scidiscovery.artifact_agent.service.artifacts import ArtifactService
from scidiscovery.artifact_agent.service.executions import ExecutionService
from scidiscovery.artifact_agent.service.run_records import RunNotFound
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from scidiscovery.artifact_agent.storage import CASObjectMissingError


class Runs:
    def __init__(self):
        self.records = {}
        self.diagnostic_reads = []

    def status(self, run_id):
        try:
            return self.records[run_id]
        except KeyError as error:
            raise RunNotFound("missing test Run") from error

    def active_ids(self, *, instance_id, limit):
        return tuple(value.run_id for value in self.records.values()
                     if value.instance_id == instance_id and value.state in {"queued", "running"})[:limit]

    def diagnostic_events(self, value, *, after, limit):
        self.diagnostic_reads.append((value.run_id, after, limit))
        events = [{"event_id": i, "activity": "tool_failed",
                   "diagnostic": {"code": "fixture_failure", "field_path": "/inputs/0"}}
                  for i in range(1, 6) if i > after]
        return {"events": events[:limit], "next_after": events[limit - 1]["event_id"] if len(events) > limit else None}


@pytest.fixture
def system(tmp_path):
    actor = ActorRef(actor_id="fixture", actor_type="service")
    artifacts = ArtifactService.open(cas_root=tmp_path / "cas", database_path=tmp_path / "artifacts.sqlite3")
    bindings = SchedulerBindingService(tmp_path / "bindings.sqlite3")
    approvals = ApprovalService(artifacts=artifacts, database_path=tmp_path / "approvals.sqlite3",
                                service_actor=actor, receipt_secret=b"x" * 32)
    executions = ExecutionService(artifacts=artifacts, approvals=approvals,
                                  database_path=tmp_path / "executions.sqlite3",
                                  exchange_root=tmp_path / "exchange", service_actor=actor)
    runs = Runs()
    model = InstanceReadModel(artifacts=artifacts, bindings=bindings, runs=runs,
                             approvals=approvals, executions=executions, operation_catalog=None)
    a = bindings.create_instance(name="one", title="One", objective="Management description, not a scientific objective")
    b = bindings.create_instance(name="two", title="Two", objective="Separate instance")
    return SimpleNamespace(actor=actor, artifacts=artifacts, bindings=bindings, approvals=approvals,
                           executions=executions, runs=runs, model=model, a=a.instance_id, b=b.instance_id)


def artifact(system, name, payload=None, *, parents=(), supersedes=None, instance=None, raw=None, media_type="application/json"):
    envelope = system.artifacts.register(
        canonical_json({"value": name} if payload is None else payload) if raw is None else raw,
        ArtifactRegistration(kind="fixture", schema_id="plugin.retired-fixture.v1",
                             payload_schema_version=1, media_type=media_type,
                             creator=system.actor, parent_refs=parents, supersedes_ref=supersedes),
        idempotency_key=name,
    )
    if instance:
        bind(system, instance, "artifact", name, envelope.artifact_id)
    return envelope


def bind(system, instance, namespace, name, object_id):
    return system.bindings.bind(instance=instance, namespace=namespace, name=name, object_id=object_id)


def run(system, name, *, state="completed", inputs=(), output=None, instance=None):
    instance = instance or system.a
    value = SimpleNamespace(run_id=name, instance_id=instance, operation_id="retired.operation",
        operation_version="old", operation_digest="a" * 64, state=state, reason=None,
        created_at="2020-01-01T00:00:00Z", started_at="2020-01-01T00:00:00Z", deadline_at="2020-01-02T00:00:00Z",
        completed_at=None if state != "completed" else "2020-01-01T00:00:01Z", last_activity_at=None,
        draft_from_run_id=None, recovery_draft=None, inputs=inputs, output_ref=output,
        signal=SchedulerSignal(verdict="inconclusive", summary="Sealed partial result") if state == "completed" else None)
    system.runs.records[name] = value
    bind(system, instance, "run", name, name)
    return value


def approval(system, name, subjects, *, instance=None, kind="run_request", now=None, expires_at=None):
    launch = system.approvals.create_request(approval_id=name, kind=kind, subject_refs=subjects,
        question="Authorize the frozen objects?", options=approval_options_template("run_request"),
        requested_by=system.actor, idempotency_key=name, now=now, expires_at=expires_at)
    bind(system, instance or system.a, "approval", name, name)
    return launch


def test_two_instances_never_gain_scope_from_scientific_payload_refs(system):
    secret = artifact(system, "secret", instance=system.b)
    public = artifact(system, "public", {"pretend_ref": secret.ref.model_dump(mode="json")}, instance=system.a)
    assert system.model.artifact(system.a, public.artifact_id)["payload"]["pretend_ref"]["artifact_id"] == secret.artifact_id
    with pytest.raises(ReadModelScopeError):
        system.model.artifact(system.a, secret.artifact_id)
    with pytest.raises(ReadModelNotFound):
        system.model.node(system.a, "artifact:secret")
    assert {item["name"] for item in system.model.nodes(system.a)["items"]} == {"public"}


def test_exact_parent_and_superseded_records_remain_readable(system):
    original = artifact(system, "original", {"target": "original target"})
    old = artifact(system, "old_plan", parents=(original.ref,))
    revised = artifact(system, "revised_plan", supersedes=old.ref, instance=system.a)
    newer = artifact(system, "unrelated_new_objective", {"target": "new target"}, instance=system.a)
    assert system.model.artifact(system.a, original.artifact_id)["payload"] == {"target": "original target"}
    assert system.model.artifact_reference(system.a, old.artifact_id) == old.ref
    assert system.model.artifact(system.a, revised.artifact_id)["supersedes"]["artifact_id"] == old.artifact_id
    assert newer.schema_id == original.schema_id


def test_list_and_overview_never_read_artifact_payloads(system, monkeypatch):
    source = artifact(system, "input", instance=system.a)
    launch = approval(system, "pending", (source.ref,))
    execution_id = system.executions.create(executor="fixture", preparation_profile="fixture", payload_ref=source.ref)
    bind(system, system.a, "execution", "execution", execution_id)
    run(system, "old_running", state="running", inputs=(SimpleNamespace(port_name="objective", artifact_name="input", artifact_ref=source.ref),))
    # Newer history cannot hide a still-running task.
    for i in range(105):
        bind(system, system.a, "artifact", f"history_{i}", source.artifact_id)
    monkeypatch.setattr(system.artifacts, "read", lambda *_: pytest.fail("payload read during metadata polling"))
    assert len(system.model.nodes(system.a)["items"]) == 30
    view = system.model.overview(system.a)
    assert {item["key"] for item in view["active_tasks"]} == {"run:old_running", "approval:pending", "execution:execution"}
    assert view["objective_refs"][0]["artifact_id"] == source.artifact_id
    assert launch.access_token not in str(view)
    assert json_size(view) <= MAX_RESPONSE_BYTES


def test_binding_cursor_has_no_duplicates_and_is_instance_scoped(system):
    source = artifact(system, "source")
    for i in range(35):
        bind(system, system.a, "artifact", f"item_{i:03d}", source.artifact_id)
    first = system.model.nodes(system.a)
    second = system.model.nodes(system.a, cursor=first["next_cursor"])
    assert len(first["items"]) == 30 and len(second["items"]) == 5
    assert len({item["key"] for item in first["items"] + second["items"]}) == 35
    assert second["next_cursor"] is None
    with pytest.raises(ValueError):
        system.model.nodes(system.b, cursor=first["next_cursor"])
    for limit in (0, 101, True):
        with pytest.raises(ValueError):
            system.model.nodes(system.a, limit=limit)


def test_historical_result_does_not_revalidate_or_claim_current_qualification(system):
    result = artifact(system, "historical", {"conclusion": "Old sealed conclusion", "limitations": ["Known gap"]})
    run(system, "old_run", output=result.ref)
    class UnavailableCatalog:
        def operation(self, _):
            pytest.fail("historical display must not load the new operation contract")
    system.model.operation_catalog = UnavailableCatalog()
    view = system.model.node(system.a, "run:old_run", diagnostic_after=1, diagnostic_limit=2)
    assert view["sealed_output"]["payload"] == {"conclusion": "Old sealed conclusion", "limitations": ["Known gap"]}
    assert view["sealed_output"]["source"]["json_pointer"] == ""
    assert view["qualification"]["state"] == "not_evaluated"
    assert view["signal"]["verdict"] == "inconclusive"
    assert system.runs.diagnostic_reads == [("old_run", 1, 2)]
    assert view["diagnostics"]["next_after"] == 3
    assert [e["event_id"] for e in view["diagnostics"]["events"]] == [2, 3]


def test_run_binding_cannot_override_recorded_instance(system):
    run(system, "other_run", instance=system.b)
    bind(system, system.a, "run", "forged", "other_run")
    with pytest.raises(ReadModelScopeError):
        system.model.node(system.a, "run:forged")


def test_approval_context_follows_only_frozen_subjects(system):
    original = artifact(system, "original_goal", {"goal": "frozen"})
    plan = artifact(system, "frozen_plan", parents=(original.ref,))
    launch = approval(system, "review", (plan.ref,))
    newer = artifact(system, "new_goal", {"goal": "new"}, instance=system.a)
    review = system.approvals.review("review", access_token=launch.access_token)
    view = system.model.approval_context(system.a, review)
    assert {item["artifact_id"] for item in view["artifacts"]} == {plan.artifact_id, original.artifact_id}
    assert newer.artifact_id not in str(view)
    assert launch.access_token not in str(view)
    forged_request = review.request.model_copy(update={"subject_refs": (newer.ref,)})
    with pytest.raises(ReadModelScopeError):
        system.model.approval_context(system.a, replace(review, request=forged_request))
    with pytest.raises(ReadModelScopeError):
        system.model.approval_context(system.b, review)


def test_big_and_opaque_payloads_keep_original_without_loading_bytes(system, monkeypatch):
    big = artifact(system, "big", raw=b"x" * (MAX_PAYLOAD_BYTES + 1), media_type="text/plain", instance=system.a)
    opaque = artifact(system, "opaque", raw=b"<script>x</script>", media_type="application/octet-stream", instance=system.a)
    monkeypatch.setattr(system.artifacts, "read", lambda *_: pytest.fail("unbounded or opaque read"))
    assert system.model.artifact(system.a, big.artifact_id)["payload_state"] == "too_large"
    view = system.model.artifact(system.a, opaque.artifact_id)
    assert view["payload_state"] == "metadata_only"
    assert view["original"]["ref"] == opaque.ref.model_dump(mode="json")


def test_missing_invalid_and_null_payloads_are_distinct(system, monkeypatch):
    null = artifact(system, "null", raw=b"null", instance=system.a)
    invalid = artifact(system, "invalid", raw=b"{invalid", instance=system.a)
    missing = artifact(system, "missing", instance=system.a)
    original_read = system.artifacts.read
    def read(ref):
        if ref == missing.ref:
            raise CASObjectMissingError("fixture original absent")
        return original_read(ref)
    monkeypatch.setattr(system.artifacts, "read", read)
    view = system.model.artifact(system.a, null.artifact_id)
    assert view["payload_state"] == "available" and view["payload"] is None
    assert system.model.artifact(system.a, invalid.artifact_id)["payload_state"] == "invalid"
    view = system.model.artifact(system.a, missing.artifact_id)
    assert view["payload_state"] == "missing" and "payload" not in view
    assert view["gaps"][0]["code"] == "source_missing"


def test_active_approval_query_excludes_expired_retired_and_other_instance(system):
    source = artifact(system, "subject")
    old = datetime.now(timezone.utc) - timedelta(days=2)
    approval(system, "expired", (source.ref,), now=old, expires_at=(old + timedelta(days=1)).isoformat().replace("+00:00", "Z"))
    approval(system, "retired", (source.ref,), kind="instance_creation")
    approval(system, "other", (source.ref,), instance=system.b)
    approval(system, "pending", (source.ref,))
    ids = system.approvals.active_ids(instance_id=system.a, scheduler_database_path=system.bindings.database_path)
    assert ids == ("pending",)


def test_execution_context_reads_original_control_refs_without_request_validator(system, monkeypatch):
    source = artifact(system, "payload")
    execution_id = system.executions.create(executor="fixture", preparation_profile="fixture", payload_ref=source.ref)
    bind(system, system.a, "execution", "execution", execution_id)
    monkeypatch.setattr(system.executions, "request", lambda *_: pytest.fail("request revalidation during history read"))
    assert system.model.artifact_reference(system.a, source.artifact_id) == source.ref
    view = system.model.node(system.a, "execution:execution")
    assert view["state"] == "created"
    assert {item["artifact_id"] for item in view["inputs"]} >= {source.artifact_id}
    assert system.executions.active_ids(instance_id=system.b, scheduler_database_path=system.bindings.database_path) == ()


def test_incomplete_run_never_presents_draft_as_sealed_output(system):
    value = run(system, "failed_run", state="failed")
    value.recovery_draft = {"recovery_pending": True, "payload": "private workspace draft"}
    view = system.model.node(system.a, "run:failed_run")
    assert "sealed_output" not in view
    assert "private workspace draft" not in str(view)
    assert view["record"]["payload"]["recovery"]["recovery_pending"] is True
    assert view["record"]["payload"]["recovery"]["draft_available"] is None


def test_large_historical_json_supports_exact_pointer_and_bounded_navigation(system):
    payload = {"summary": "Exact sealed summary", "parameters": [{"value": i} for i in range(6000)], "a/b": {"~value": None}}
    source = artifact(system, "large_report", payload, instance=system.a)
    assert source.size_bytes > MAX_PAYLOAD_BYTES
    assert system.model.artifact(system.a, source.artifact_id)["payload_state"] == "too_large"
    selected = system.model.artifact(system.a, source.artifact_id, pointer="/summary")
    assert selected["payload"] == "Exact sealed summary"
    assert selected["source"]["json_pointer"] == "/summary"
    navigation = system.model.artifact(system.a, source.artifact_id, pointer="/parameters", child_limit=2)
    assert navigation["payload_state"] == "navigation"
    assert navigation["navigation"]["next_after"] == 2
    assert navigation["navigation"]["items"][0]["json_pointer"] == "/parameters/0"
    next_page = system.model.artifact(system.a, source.artifact_id, pointer="/parameters", child_after=2, child_limit=2)
    assert next_page["navigation"]["items"][0]["value"] == {"value": 2}
    assert system.model.artifact(system.a, source.artifact_id, pointer="/a~1b/~0value")["payload"] is None
    absent = system.model.artifact(system.a, source.artifact_id, pointer="/parameters/01")
    assert absent["payload_state"] == "missing" and "payload" not in absent
    assert json_size(navigation) < MAX_RESPONSE_BYTES
