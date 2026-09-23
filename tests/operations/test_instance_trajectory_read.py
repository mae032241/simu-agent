"""Exact trajectory relationships and observations, with no solver execution."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.read_model import ReadModelScopeError
from scidiscovery.artifact_agent.approval_ui.view_models import MAX_RESPONSE_BYTES, json_size
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics
from scidiscovery.artifact_agent.service.local_process_observation import RECORD_DIR
from scidiscovery.artifact_agent.service.runs import RunService
from scidiscovery.general_science_views import build_presentation as general_presentation
from tests.operations.test_instance_read_model import system, bind, approval


@pytest.fixture
def trajectory(system, tmp_path):
    service = object.__new__(RunService)
    service.database_path = tmp_path / "runs.sqlite3"
    service._initialize()
    service.backend = SimpleNamespace(open=lambda run_id: SimpleNamespace(root=tmp_path / "workspaces" / run_id))
    service.recovery_status = lambda value: {"draft_available": value.state == "failed", "recovery_pending": value.state == "failed"}
    system.runs = system.model.runs = service
    system.model.engineering_diagnostics = EngineeringDiagnostics(tmp_path / "engineering")
    return system


def artifact(system, name, payload, *, schema="fixture.v1", parents=(), labels=None, instance=None):
    envelope = system.artifacts.register(canonical_json(payload), ArtifactRegistration(
        kind="fixture", schema_id=schema, payload_schema_version=1, media_type="application/json",
        creator=system.actor, parent_refs=parents, labels=labels or {}), idempotency_key=name)
    if instance:
        bind(system, instance, "artifact", name, envelope.artifact_id)
    return envelope


def stored_run(system, name, *, inputs=(), output=None, state="completed", instance=None,
               operation="fixture.operation", digest="a" * 64, resume=None, draft=None):
    instance = instance or system.a
    record = dict(run_id=name, instance_id=instance, operation_id=operation, operation_version="1",
        operation_digest=digest, agent_type="same_reused_agent", instruction="fixture",
        inputs_json=canonical_json([dict(port_name=port, source_name=port, artifact_name=port,
            artifact_ref=ref.model_dump(mode="json"), media_type="application/json", exposure="full", usage="claim_evidence", require_current=False)
            for port, ref in inputs]), backend_id="local", backend_version="1", backend_capabilities_json=b"[]",
        output_binding_name=name + ".output", output_logical_name=name + ".output", output_revision=1,
        output_binding_fingerprint="b" * 64, request_digest="c" * 64, state=state,
        created_at="2020-01-01T00:00:00Z", started_at="2020-01-01T00:00:01Z", deadline_at="2020-01-02T00:00:00Z",
        completed_at="2020-01-01T00:00:02Z" if state in {"completed", "failed"} else None,
        last_activity_at="2020-01-01T00:00:02Z", resume_from_run_id=resume, draft_from_run_id=draft,
        output_ref_json=output.canonical_json() if output else None,
        signal_json=canonical_json({"verdict": "inconclusive", "summary": "Exact sealed partial result"}) if state == "completed" else None)
    with system.runs._connect() as connection:
        connection.execute("INSERT INTO runs (" + ",".join(record) + ") VALUES (" + ",".join("?" for _ in record) + ")", tuple(record.values()))
    bind(system, instance, "run", name, name)
    return system.runs.status(name)


def test_large_diagnostics_keep_exact_pages_and_original_output_link(trajectory):
    s = trajectory
    output = artifact(s, "large.errors.output", {"summary": "Original sealed result"})
    run = stored_run(s, "large_errors", output=output.ref)
    diagnostic = {"category": "output_rejected", "code": "output_rejected", "details": [
        {"schema_version": 1, "code": "output_invalid", "phase": "output_payload",
         "path": f"$.payload.items[{index}]", "message": "原始错误" * 128,
         "affected_action": "submit", "repairable": True}
        for index in range(16)]}
    with s.runs._connect() as connection:
        for _ in range(70):
            s.runs._append_activity(connection, run.run_id, "output_rejected",
                                    "2020-01-01T00:00:03Z", canonical_json(diagnostic))
    expected = s.runs.diagnostic_events(run, limit=100)["events"]
    assert json_size(expected[:50]) > MAX_RESPONSE_BYTES
    collected, after, pages = [], 0, 0
    while True:
        node = s.model.node(s.a, "run:large_errors", diagnostic_after=after)
        assert json_size(node) <= MAX_RESPONSE_BYTES
        assert node["outputs"][0]["artifact_id"] == output.artifact_id
        page = node["diagnostics"]
        assert page["events"]
        collected.extend(page["events"])
        pages += 1
        if page["next_after"] is None:
            break
        assert page["next_after"] > after
        after = page["next_after"]
        assert pages < 70
    assert pages > 1 and collected == expected


@pytest.mark.parametrize("pending", [True, False])
def test_overview_recovers_original_objective_from_one_exact_node_without_payload_reads(trajectory, monkeypatch, pending):
    s = trajectory
    goal = artifact(s, "original.goal", {"statement": "Original"},
                    schema="scidiscovery.research-objective.v1", instance=s.a)
    plan = artifact(s, "original.plan", {}, schema="scidiscovery.experiment-portfolio.v1", parents=(goal.ref,))
    if pending:
        approval(s, "only.pending", (plan.ref,))
    else:
        stored_run(s, "latest_completed", inputs=(("experiment_plan", plan.ref),))
    monkeypatch.setattr(s.artifacts, "read", lambda *_: pytest.fail("overview loaded a scientific payload"))
    view = s.model.overview(s.a)
    assert [ref["artifact_id"] for ref in view["objective_refs"]] == [goal.artifact_id]
    assert view["objective_basis"]["basis"] == ("only_active_task" if pending else "most_recent_run")
    assert not any(item["code"] == "no_objective_in_observed_active_run_bindings" for item in view["gaps"])


def test_overview_does_not_choose_one_objective_across_active_branches(trajectory, monkeypatch):
    s = trajectory
    for name in ("first", "second"):
        goal = artifact(s, name, {"statement": name}, schema="scidiscovery.research-objective.v1")
        approval(s, name, (goal.ref,))
    view = s.model.overview(s.a)
    assert view["objective_refs"] == [] and "objective_basis" not in view
    assert len(view["active_tasks"]) == 2
    original = s.bindings.find_name
    monkeypatch.setattr(s.bindings, "find_name", lambda **kwargs: None
        if kwargs.get("namespace") == "approval" and kwargs.get("object_id") == "second"
        else original(**kwargs))
    incomplete = s.model.overview(s.a)
    assert len(incomplete["active_tasks"]) == 1
    assert incomplete["objective_refs"] == [] and "objective_basis" not in incomplete
    assert any(item["code"] == "active_control_binding_missing" for item in incomplete["gaps"])


def test_oversized_legacy_error_keeps_event_log_and_following_page(trajectory):
    s = trajectory
    run = stored_run(s, "oversized_legacy", state="failed")
    facts = s.model.engineering_diagnostics.capture(RuntimeError("original trace"),
        scope="instance:" + s.a, layer="fixture", action="read")
    with s.runs._connect() as connection:
        s.runs._append_activity(connection, run.run_id, "framework_failure", "2020-01-01T00:00:03Z",
            canonical_json({"engineering": facts, "details": [{"message": "legacy" * MAX_RESPONSE_BYTES}]}))
        s.runs._append_activity(connection, run.run_id, "output_rejected", "2020-01-01T00:00:04Z",
            canonical_json({"details": [{"message": "following original error"}]}))
    first = s.model.node(s.a, "run:oversized_legacy")
    assert json_size(first) <= MAX_RESPONSE_BYTES
    event, = first["diagnostics"]["events"]
    assert event["diagnostic"]["engineering"] == facts
    assert event["diagnostic"]["original_event_id"] == event["event_id"]
    assert first["diagnostics"]["next_after"] == event["event_id"]
    trace = s.model.diagnostics(s.a, facts["reference"], node_key="run:oversized_legacy")
    assert trace.get("gaps") is None
    second = s.model.node(s.a, "run:oversized_legacy", diagnostic_after=event["event_id"])
    assert second["diagnostics"]["events"][0]["diagnostic"]["details"][0]["message"] == "following original error"


def test_overview_accounts_for_its_wrapper_and_keeps_a_precise_node_cursor(trajectory):
    s = trajectory
    s.a = s.bindings.create_instance(name="long_metadata", title="Long metadata", objective="长" * 8192).instance_id
    original = artifact(s, "item_00", {}, instance=s.a)
    for index in range(1, 30):
        bind(s, s.a, "artifact", f"item_{index:02d}", original.artifact_id)
    for index in range(60):
        s.bindings.select_scientific_object(instance=s.a, kind=f"kind_{index:02d}",
            logical_name=f"choice_{index:02d}", artifact_ref=original.ref)
    before = s.model.nodes(s.a)
    overview = s.model.overview(s.a)
    assert json_size(overview) <= MAX_RESPONSE_BYTES
    assert len(overview["nodes"]["items"]) < len(before["items"])
    collected = [item["key"] for item in overview["nodes"]["items"]]
    cursor = overview["nodes"]["next_cursor"]
    while cursor:
        page = s.model.nodes(s.a, cursor=cursor)
        collected.extend(item["key"] for item in page["items"])
        cursor = page["next_cursor"]
    assert len(collected) == 30 and len(set(collected)) == 30


def test_run_and_transform_edges_use_exact_inputs_without_payload_scan(trajectory, monkeypatch):
    s = trajectory
    source = artifact(s, "source", {"value": 1}, instance=s.a)
    output = artifact(s, "transform", {"result": 2}, parents=(source.ref,), labels={
        "operation_id": "fixture.transform", "operation_digest": "d" * 64,
        "operation_version": "1", "transform_profile": "fixture.transform", "operation_output_port": "plan"}, instance=s.a)
    private = artifact(s, "other_child", {"secret": 3}, parents=(source.ref,), instance=s.b)
    stored_run(s, "consumer", inputs=(("plan", output.ref),))
    monkeypatch.setattr(s.artifacts, "read", lambda *_: pytest.fail("metadata must not read payload"))
    metadata = s.model.node_metadata(s.a, "artifact:transform")
    assert metadata["producer"]["kind"] == "transform"
    relationships = s.model._relationships(s.a, s.model._binding(s.a, "artifact:transform"), (output.ref,))
    assert any(link["artifact_ref"] == source.ref.model_dump(mode="json") for link in relationships["predecessors"])
    assert any(link["key"] == "run:consumer" for link in relationships["successors"])
    source_links = s.model._relationships(s.a, s.model._binding(s.a, "artifact:source"), (source.ref,))
    assert private.artifact_id not in str(source_links)


def test_matching_review_requires_exact_subject_port_and_recorded_contract(trajectory):
    s = trajectory
    subject = artifact(s, "plan", {"objective": "exact"}, labels={"operation_id": "fixture.design", "operation_digest": "a" * 64}, instance=s.a)
    other = artifact(s, "other_plan", {"objective": "same text"}, instance=s.a)
    reviewed = artifact(s, "reviewed", {"verdict": "inconclusive"}, parents=(subject.ref,), instance=s.a)
    stored_run(s, "correct_review", operation="fixture.review", inputs=(("review_subject", subject.ref),), output=reviewed.ref)
    stored_run(s, "wrong_port", operation="fixture.review", inputs=(("progress", subject.ref),), output=other.ref)
    stored_run(s, "other_review", operation="fixture.review", inputs=(("review_subject", other.ref),))
    compiled = SimpleNamespace(digest="a" * 64, spec=SimpleNamespace(review=SimpleNamespace(reviewer_operation="fixture.review", reviewer_input_port="review_subject")))
    s.model.operation_catalog = SimpleNamespace(operation=lambda _: compiled)
    view = s.model.node(s.a, "artifact:plan")
    assert [item["key"] for item in view["relationships"]["matching_reviews"]] == ["run:correct_review"]
    assert view["relationships"]["matching_reviews"][0]["recorded_signal"]["verdict"] == "inconclusive"


def test_revision_objective_navigation_ignores_newer_same_schema_feedback(trajectory):
    s = trajectory
    original = artifact(s, "original", {"statement": "original objective"}, schema="scidiscovery.research-objective.v1")
    newer = artifact(s, "newer", {"statement": "feedback objective"}, schema="scidiscovery.research-objective.v1", instance=s.a)
    first = artifact(s, "first_plan", {}, schema="scidiscovery.experiment-portfolio.v1", parents=(original.ref,))
    revised = artifact(s, "revised_plan", {}, schema="scidiscovery.experiment-portfolio.v1", parents=(first.ref, newer.ref), instance=s.a)
    view = s.model.node(s.a, "artifact:revised_plan")
    assert [item["artifact_id"] for item in view["objective_refs"]] == [original.artifact_id]
    context = s.model.node_context(s.a, "artifact:revised_plan")
    assert {item["artifact_id"] for item in context["artifacts"]} == {revised.artifact_id, first.artifact_id, original.artifact_id, newer.artifact_id}


def test_completed_run_prioritizes_exact_runtime_figure_before_wide_inputs(trajectory, monkeypatch):
    s = trajectory
    run_id = "wide_figure"
    operation = "fixture.operation"
    digest = "a" * 64
    labels = {"operation_id": operation, "operation_version": "1",
              "operation_digest": digest, "tool_producer_run": run_id}
    evidence_labels = {"operation_version": "1", "operation_digest": digest,
                       "tool_producer_run": "timed-out-attempt"}
    wide = tuple((f"source_{index:02d}", artifact(
        s, f"wide_{index:02d}", {"value": "wide input " * 2600}).ref)
        for index in range(12))
    image = s.artifacts.register(b"\x89PNG\r\n\x1a\nfixture", ArtifactRegistration(
        kind="tool_evidence", schema_id="opaque", payload_schema_version=1,
        media_type="image/png", creator=s.actor,
        parent_refs=tuple(ref for _, ref in wide),
        labels={**evidence_labels, "operation_output_port": "tool_evidence"}),
        idempotency_key="wide.figure.image")
    unreferenced_records, unreferenced_images = [], []
    for index in range(1, 32):
        saved = s.artifacts.register(b"\x89PNG\r\n\x1a\n" + str(index).encode(), ArtifactRegistration(
            kind="tool_evidence", schema_id="opaque", payload_schema_version=1,
            media_type="image/png", creator=s.actor,
            parent_refs=tuple(ref for _, ref in wide),
            labels={**evidence_labels, "operation_output_port": "tool_evidence"}),
            idempotency_key=f"wide.figure.unreferenced.{index:03d}")
        alias = f"tool_evidence_{index:03d}"
        unreferenced_images.append(saved)
        unreferenced_records.append({"alias": alias,
            "artifact_ref": saved.ref.model_dump(mode="json"), "source_ref": None,
            "media_type": "image/png", "size_bytes": saved.size_bytes,
            "metadata": {"file_name": f"exploratory-{index:03d}.png"},
            "tool_name": "fixture_plot"})
    record = {"alias": "tool_evidence_032", "artifact_ref": image.ref.model_dump(mode="json"),
              "source_ref": None, "media_type": "image/png", "size_bytes": image.size_bytes,
              "metadata": {"file_name": "comparison.png"}, "tool_name": "fixture_plot"}
    bindings = {item["alias"]: {"schema_version": 1, "artifact_ref": item["artifact_ref"],
                                "port_name": "tool_evidence"}
                for item in (*unreferenced_records, record)}
    manifest = artifact(s, "wide.figure.manifest", {
        "records": [*unreferenced_records, record], "bindings": bindings},
        schema="scidiscovery.tool-evidence-manifest.v1",
        parents=tuple(ref for _, ref in wide) + tuple(
            item.ref for item in (*unreferenced_images, image)),
        labels={**labels, "operation_output_port": "recovery_manifest_output"})
    report = artifact(s, "wide.figure.report", {
        "summary": "The nonuniform profile remains visible.", "overall_verdict": "inconclusive",
        "claim_allowed": False, "evidence": [{"source_key": "tool_evidence_032",
            "source_type": "runtime_output", "title": "Nonuniform concentration profile",
            "locator": "tool_evidence_032"}]},
        schema="scidiscovery.layered-diagnosis.v1",
        parents=tuple(ref for _, ref in wide) + (manifest.ref,),
        labels={"operation_id": operation, "operation_version": "1", "operation_digest": digest,
                "operation_output_port": "layered_diagnosis"})
    stored_run(s, run_id, inputs=wide, output=report.ref, operation=operation, digest=digest)
    monkeypatch.setattr(presentation, "entry_points", lambda **_: (
        SimpleNamespace(name="general", load=lambda: general_presentation),))

    context = s.model.node_context(s.a, "run:" + run_id)
    ids = [item["artifact_id"] for item in context["artifacts"]]
    assert ids[:3] == [report.artifact_id, manifest.artifact_id, image.artifact_id]
    assert "operation_id" not in context["artifacts"][2]["family"]
    run_report = context["artifacts"][0]
    assert run_report["family"]["presentation_manifest_scan_complete"] is True
    assert run_report["family"]["presentation_manifest_match_count"] == 1
    assert {"context_byte_limit", "lineage_read_limit"}.issubset(
        {item["code"] for item in context["gaps"]})
    rendered = presentation.build_presentation(tuple(context["artifacts"]),
        focus_artifact_ids=context["focus_artifact_ids"])
    assert rendered["figures"] == [{"artifact_id": image.artifact_id,
        "label": "Nonuniform concentration profile",
        "source": {"artifact_id": report.artifact_id, "json_pointer": "/evidence/0"}}]
    assert not {item.artifact_id for item in unreferenced_images} & {
        figure["artifact_id"] for figure in rendered["figures"]}

    bind(s, s.a, "artifact", "wide.figure.report", report.artifact_id)
    artifact_context = s.model.node_context(s.a, "artifact:wide.figure.report")
    artifact_rendered = presentation.build_presentation(tuple(artifact_context["artifacts"]),
        focus_artifact_ids=artifact_context["focus_artifact_ids"])
    assert artifact_rendered["figures"] == rendered["figures"]
    artifact_report = next(item for item in artifact_context["artifacts"]
        if item["artifact_id"] == report.artifact_id)
    assert artifact_report["family"]["presentation_manifest_scan_complete"] is True
    assert artifact_report["family"]["presentation_manifest_match_count"] == 1

    prior_image = s.artifacts.register(b"\x89PNG\r\n\x1a\nprior", ArtifactRegistration(
        kind="tool_evidence", schema_id="opaque", payload_schema_version=1,
        media_type="image/png", creator=s.actor,
        labels={**evidence_labels, "tool_producer_run": "prior-run",
                "operation_output_port": "tool_evidence"}),
        idempotency_key="wide.figure.prior.image")
    prior_record = {"alias": "tool_evidence_032",
        "artifact_ref": prior_image.ref.model_dump(mode="json"), "source_ref": None,
        "media_type": "image/png", "size_bytes": prior_image.size_bytes,
        "metadata": {"file_name": "prior.png"}, "tool_name": "fixture_plot"}
    prior_manifest = artifact(s, "wide.figure.prior.manifest", {
        "records": [prior_record], "bindings": {"tool_evidence_032": {"schema_version": 1,
            "artifact_ref": prior_record["artifact_ref"], "port_name": "tool_evidence"}}},
        schema="scidiscovery.tool-evidence-manifest.v1", parents=(prior_image.ref,),
        labels={**labels, "tool_producer_run": "prior-run",
                "operation_output_port": "recovery_manifest_output"})
    ambiguous_report = artifact(s, "wide.figure.ambiguous.report", {
        "summary": "Ambiguous saved manifests.", "overall_verdict": "inconclusive",
        "claim_allowed": False, "evidence": [{"source_key": "tool_evidence_032",
            "source_type": "runtime_output", "title": "Must remain hidden",
            "locator": "tool_evidence_032"}]},
        schema="scidiscovery.layered-diagnosis.v1",
        parents=(prior_manifest.ref, prior_image.ref, *(ref for _, ref in wide), manifest.ref),
        labels={"operation_id": operation, "operation_version": "1", "operation_digest": digest,
                "operation_output_port": "layered_diagnosis"})
    bind(s, s.a, "artifact", "wide.figure.ambiguous.report", ambiguous_report.artifact_id)
    ambiguous_context = s.model.node_context(s.a, "artifact:wide.figure.ambiguous.report")
    failed = presentation.build_presentation(tuple(ambiguous_context["artifacts"]),
        focus_artifact_ids=ambiguous_context["focus_artifact_ids"])
    assert failed["figures"] == []
    ambiguous_view = next(item for item in ambiguous_context["artifacts"]
        if item["artifact_id"] == ambiguous_report.artifact_id)
    assert ambiguous_view["family"]["presentation_manifest_match_count"] == 2

    ambiguous = deepcopy(context["artifacts"])
    manifest_view = next(item for item in ambiguous if item["artifact_id"] == manifest.artifact_id)
    cited_record = next(item for item in manifest_view["payload"]["records"]
        if item["alias"] == "tool_evidence_032")
    manifest_view["payload"]["records"].append(deepcopy(cited_record))
    failed = presentation.build_presentation(tuple(ambiguous),
        focus_artifact_ids=context["focus_artifact_ids"])
    assert failed["figures"] == []
    assert any(item["code"] == "runtime_figure_record_ambiguous" for item in failed["gaps"])

    incomplete = tuple(item for item in context["artifacts"] if item["artifact_id"] != image.artifact_id)
    failed = presentation.build_presentation(incomplete,
        focus_artifact_ids=context["focus_artifact_ids"])
    assert failed["figures"] == []
    assert any(item["code"] == "runtime_figure_artifact_missing_or_ambiguous" for item in failed["gaps"])

    recovered_labels = deepcopy(context["artifacts"])
    image_view = next(item for item in recovered_labels if item["artifact_id"] == image.artifact_id)
    image_view["family"]["operation_version"] = "2"
    image_view["family"]["operation_digest"] = "b" * 64
    image_view["family"]["operation_output_port"] = "legacy_tool_evidence"
    recovered = presentation.build_presentation(tuple(recovered_labels),
        focus_artifact_ids=context["focus_artifact_ids"])
    assert recovered["figures"] == rendered["figures"]

    recovered_attempt = deepcopy(context["artifacts"])
    image_view = next(item for item in recovered_attempt if item["artifact_id"] == image.artifact_id)
    image_view["family"]["tool_producer_run"] = "another-prior-attempt"
    recovered = presentation.build_presentation(tuple(recovered_attempt),
        focus_artifact_ids=context["focus_artifact_ids"])
    assert recovered["figures"] == rendered["figures"]


def test_completed_inconclusive_and_selected_nonadmissible_are_distinct(trajectory, monkeypatch):
    s = trajectory
    old = artifact(s, "old", {"summary": "partial"}, labels={"scientific_claim_admissible": "false"}, instance=s.a)
    stored_run(s, "partial", output=old.ref)
    s.bindings.select_scientific_object(instance=s.a, kind="plan", logical_name="old", artifact_ref=old.ref)
    view = s.model.node(s.a, "run:partial")
    assert view["state"] == "completed" and view["signal"]["verdict"] == "inconclusive"
    assert view["recorded_scientific_claim_admissible"] == "false"
    assert view["current_selection"][0]["is_selected"] is True
    monkeypatch.setattr(s.artifacts, "read", lambda *_: pytest.fail("poll read output"))
    overview = s.model.overview(s.a)
    assert overview["selected_node"]["key"] == "artifact:old"
    assert overview["recent_node"] == {"key": "run:partial", "basis": "most_recent_run"}
    assert s.model.node_metadata(s.a, "run:partial")["completed_at"] == "2020-01-01T00:00:02Z"


def test_reused_agent_keeps_original_run_diagnostics_native_observations_and_recovery(trajectory):
    s = trajectory
    old = stored_run(s, "old_failed", state="failed")
    new = stored_run(s, "new_run", state="failed", resume="old_failed")
    with s.runs._connect() as connection:
        connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,?)",
            (old.run_id, "tool_failed", "2020-01-01T00:00:01Z", canonical_json({"category": "fixture", "details": [{"path": "/inputs/0", "message": "original failure"}]})))
    root = s.runs.backend.open(old.run_id).root
    (root / RECORD_DIR).mkdir(parents=True)
    (root / RECORD_DIR / "latest.json").write_text(json.dumps({"state": "finished", "exit_code": 7, "error_count": 1, "recent_errors": [{"exit_code": 7}]}))
    old_view = s.model.node(s.a, "run:old_failed", diagnostic_limit=1)
    new_view = s.model.node(s.a, "run:new_run")
    assert len(old_view["diagnostics"]["events"]) == 1 and new_view["diagnostics"]["events"] == []
    assert old_view["native_execution"]["exit_code"] == 7
    assert new_view["native_execution"]["coverage"] == "unobserved"
    assert "error_count" not in new_view["native_execution"]
    assert old_view["recovery"]["draft_available"] and old_view["recovery"]["recovery_pending"]
    assert any(link["key"] == "run:old_failed" and link["relation"] == "resume_from" for link in new_view["relationships"]["predecessors"])
    assert old.agent_type == new.agent_type


def test_engineering_diagnostics_require_exact_run_association_and_instance(trajectory):
    s = trajectory
    stored_run(s, "owner", state="failed")
    stored_run(s, "unrelated", state="failed")
    facts = s.model.engineering_diagnostics.capture(RuntimeError("fixture error"), scope="instance:" + s.a, layer="fixture", action="read")
    with s.runs._connect() as connection:
        connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES(?,?,?,?)",
            ("owner", "framework_failure", "2020-01-01T00:00:00Z", canonical_json({"engineering": facts})))
    result = s.model.diagnostics(s.a, facts["reference"], node_key="run:owner", max_bytes=16)
    assert result["next_offset"] == 16
    with pytest.raises(ReadModelScopeError):
        s.model.diagnostics(s.a, facts["reference"], node_key="run:unrelated")


def test_execution_diagnostic_does_not_reach_another_execution_in_same_instance(trajectory):
    s = trajectory
    payload = artifact(s, "payload", {})
    first = s.executions.create(executor="fixture", preparation_profile="fixture", payload_ref=payload.ref)
    second = s.executions.create(executor="fixture", preparation_profile="fixture", payload_ref=payload.ref)
    bind(s, s.a, "execution", "one", first)
    bind(s, s.a, "execution", "two", second)
    facts = s.model.engineering_diagnostics.capture(RuntimeError("collector failure"), scope="instance:" + s.a, layer="collection", action="read")
    s.executions.save_observation(first, {"observation_error": facts})
    assert s.model.diagnostics(s.a, facts["reference"], node_key="execution:one")["reference"] == facts["reference"]
    with pytest.raises(ReadModelScopeError):
        s.model.diagnostics(s.a, facts["reference"], node_key="execution:two")


def test_related_runs_match_full_reference_and_scope_and_remain_bounded(trajectory):
    s = trajectory
    source = artifact(s, "source", {})
    stored_run(s, "own", inputs=(("subject", source.ref),))
    stored_run(s, "other", inputs=(("subject", source.ref),), instance=s.b)
    assert [run.run_id for run in s.runs.related_runs(instance_id=s.a, artifact_ref=source.ref)] == ["own"]
    wrong = ArtifactRef(artifact_id=source.artifact_id, sha256="f" * 64, kind=source.kind, schema_id=source.schema_id)
    assert s.runs.related_runs(instance_id=s.a, artifact_ref=wrong) == ()
    assert s.artifacts.registry.linked_children(wrong) == ()
    with pytest.raises(ValueError):
        s.runs.related_runs(instance_id=s.a, artifact_ref=source.ref, limit=102)
