from __future__ import annotations

import pytest


@pytest.mark.process_e2e
def test_no_effect_execution_requires_exact_ui_decision(tmp_path, monkeypatch):
    import sys
    import os
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(sys.path))
    import hashlib
    import http.client
    import os
    import tempfile
    from pathlib import Path
    from urllib.parse import parse_qs, urlencode, urlparse

    from scidiscovery.artifact_agent.approval_ui import ApprovalUI
    from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
    from scidiscovery.artifact_agent.interfaces.mcp_root import (
        RootMCPRouter,
        RootToolError,
        RootToolFacade,
    )
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
    from scidiscovery.artifact_agent.service.executions import ExecutionApprovalError


    def descriptor(name, path, media_type):
        content = path.read_bytes()
        return LocalFileDescriptor(
            name=name,
            local_path=str(path),
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type=media_type,
        )


    class NoEffectAdapter:
        def __init__(self):
            self.exchange = None
            self.submit_count = 0
            self.submissions = {}
            self.last_submission = None

        def supports_preparation_profile(self, profile):
            return profile == "fixture.no-effect.v1"

        def validate_preparation_payload(self, raw, *, preparation_profile):
            assert preparation_profile == "fixture.no-effect.v1"
            assert raw == b"{}"

        def prepare(self, payload, *, preparation_profile, exchange_directory):
            assert preparation_profile == "fixture.no-effect.v1"
            self.exchange = exchange_directory
            return payload

        def submit(self, submission):
            assert Path(submission.local_path).read_bytes() == b"{}"
            existing = self.submissions.get(submission.sha256)
            if existing is not None:
                return existing
            self.submit_count += 1
            result = ("no-effect-run", "accepted")
            self.last_submission = submission
            self.submissions[submission.sha256] = result
            return result

        def lookup_submission(self, submission):
            return self.submissions.get(submission.sha256)

        def status(self, external_run_id):
            assert external_run_id == "no-effect-run"
            return "succeeded"

        def cancel(self, external_run_id):
            assert external_run_id == "no-effect-run"
            return "cancelled"

        def collect(self, external_run_id):
            assert external_run_id == "no-effect-run"
            output = self.exchange / "no-effect-output.txt"
            output.write_text("no external side effect\n", encoding="utf-8")
            return (descriptor("report", output, "text/plain; charset=utf-8"),)


    root_directory = tmp_path
    project = root_directory / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=root_directory / "state",
        approval_receipt_secret=os.urandom(32),
    )
    from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    runtime.runs.operation_catalog = compile_catalog((ARCHITECTURE_TEST_PLUGIN,))
    instance = runtime.scheduler_bindings.create_instance(
        name="r0_effect",
        title="R0 no-effect lifecycle",
        objective="Exercise authorization without an external adapter side effect.",
    )
    adapter = NoEffectAdapter()
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            operation_catalog=runtime.runs.operation_catalog,
            approval_base_url="http://127.0.0.1:8766",
            execution_bridge=ExecutionBridge(
                runtime.executions, adapters={"architecture_fixture:fixture": adapter}
            ),
        )
    )
    def call(name, arguments):
        surface = "execution" if name in {
            "execution_start", "execution_status", "execution_sync", "execution_collect", "execution_outputs",
        } else "research"
        return root.call_tool(name, arguments, surface=surface)

    payload = runtime.artifacts.register(
        b"{}",
        ArtifactRegistration(
            kind="architecture_test_input",
            schema_id="scidiscovery.architecture-test.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="r4d:fixture-input",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="execution_payload",
        object_id=payload.artifact_id,
    )

    try:
        call(
            "execution_request_create",
            {
                "name": "legacy_execution",
                "executor": "architecture_fixture:fixture",
                "preparation_profile": "fixture.no-effect.v1",
                "payload_name": "execution_payload",
            },
        )
    except RootToolError as error:
        assert "interface is not available on research surface: execution_request_create" in str(error)
    else:
        raise AssertionError("legacy execution request entry remained reachable")

    created = call(
        "operation_invoke",
        {
            "name": "no_effect_execution",
            "operation_id": "builtin.test.effect",
            "inputs": [
                {"port": "effect_input", "artifact_names": ["execution_payload"]}
            ],
        },
    )
    assert created["executor_kind"] == "effect"
    created = created["result"]
    assert created["state"] == "created"
    approval = created["approval"]
    assert approval["status"] == "pending"
    try:
        call(
            "execution_approval_request_create", {"name": "no_effect_execution"}
        )
    except RootToolError as error:
        assert "interface is not available on research surface: execution_approval_request_create" in str(error)
    else:
        raise AssertionError("retired execution approval entry remained reachable")
    approval_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="approval",
        name="no_effect_execution.approval",
    )
    launch = runtime.approvals.status(approval_id)
    assert approval["review_url"] == "http://127.0.0.1:8766" + launch.review_path
    query = parse_qs(urlparse(launch.review_path).query)
    token = query["token"][0]
    review = runtime.approvals.review(approval_id, access_token=token)
    execution_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="execution",
        name="no_effect_execution",
    )
    request_ref, payload_ref = runtime.executions.approval_subject_refs(execution_id)
    assert review.request.subject_refs == (request_ref, payload_ref)
    assert tuple(subject.ref for subject, _ in review.subjects) == (
        request_ref,
        payload_ref,
    )
    try:
        call("execution_start", {"name": "no_effect_execution"})
    except ExecutionApprovalError as error:
        assert "not decided" in str(error)
    else:
        raise AssertionError("execution started without an exact UI decision")
    assert adapter.submit_count == 0
    assert call(
        "execution_status", {"name": "no_effect_execution"}
    )["state"] == "created"

    ui = ApprovalUI(runtime.approvals)
    base = ui.start()
    try:
        parsed = urlparse(base)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        form = urlencode({
            "token": token,
            "csrf": review.csrf_token,
            "nonce": review.decision_nonce,
            "selected_option": "authorize_execution",
            "rationale": "",
            "confirm": "confirm",
        })
        connection.request(
            "POST",
            f"/review/{approval_id}/decision",
            body=form,
            headers={
                "Origin": base,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 303
        connection.close()
    finally:
        ui.stop()

    started = call("execution_start", {"name": "no_effect_execution"})
    assert started["state"] == "submitted"
    terminal = call("execution_sync", {"name": "no_effect_execution"})
    assert terminal["state"] == "succeeded"
    # This fixture owns an in-memory adapter. Freeze its completed download and
    # exercise installed background ingestion independently from adapter discovery.
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    from scidiscovery.artifact_agent.service.engineering_diagnostics import atomic_json
    import time
    collector = ExecutionCollection(runtime.executions, plugin_configs={})
    root.facade.execution_collection = collector
    execution_id = root.facade._resolve("execution", "no_effect_execution")
    atomic_json(collector.directory(execution_id) / "outputs.json", {
        "outputs": [item.model_dump(mode="json") for item in adapter.collect("no-effect-run")],
        "collected_at": "2026-09-13T00:00:00Z"})
    try:
        call("execution_collect", {"name": "no_effect_execution", "total_seconds": 10})
        deadline = time.monotonic() + 12
        while call("execution_status", {"name": "no_effect_execution"})["state"] != "collected":
            summary = collector.summary(execution_id)
            assert summary["state"] != "failed", str(summary)
            assert time.monotonic() < deadline, str(summary)
            time.sleep(.05)
    finally:
        collector.close()
    assert call("execution_sync", {"name": "no_effect_execution"})["state"] == "collected"
    assert adapter.submit_count == 1
    assert adapter.submit(adapter.last_submission) == ("no-effect-run", "accepted")
    assert adapter.submit_count == 1
    outputs = call("execution_outputs", {"name": "no_effect_execution"})
    assert outputs["outputs"] == [{
        "output_label": "report",
        "artifact_name": "no_effect_execution.output.report",
        "media_type": "text/plain; charset=utf-8",
        "size_bytes": len(b"no external side effect\n"),
    }]
