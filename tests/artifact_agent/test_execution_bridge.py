from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema import LocalFileDescriptor, LocalIdentityRef
from scidiscovery.artifact_agent.service import (
    ExecutionApprovalError,
    ExecutionServiceError,
    ExecutionStateConflict,
    SchedulerNameConflict,
)
from tcad_artifact.execution_control import (
    TCADExecutionFacade,
    TCADExecutionPolicy,
    ToolProfile,
)
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    ProjectExpectedOutput,
    ProjectResourceLimits,
    package_deck_project_json,
)


class LocalTCADAdapter:
    def __init__(self, runner: TCADExecutionFacade) -> None:
        self.runner = runner

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        assert preparation_profile == "tcad.deck-project.v1"
        packaged = package_deck_project_json(
            Path(payload.local_path).read_bytes(),
            output_root=exchange_directory / "prepared",
        )
        return LocalFileDescriptor.model_validate(
            packaged.job_spec_file.model_dump(mode="python"), strict=True
        )

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]:
        value = self.runner.tcad_submit(submission=submission)
        return value["run_id"], value["state"]

    def status(self, external_run_id: str) -> str:
        return self.runner.tcad_status(run_id=external_run_id)["state"]

    def cancel(self, external_run_id: str) -> str:
        return self.runner.tcad_cancel(run_id=external_run_id)["state"]

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]:
        value = self.runner.tcad_collect(run_id=external_run_id)
        return tuple(
            LocalFileDescriptor.model_validate(item, strict=True)
            for item in value["outputs"]
        )


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _root(tmp_path: Path) -> tuple[RootMCPRouter, object]:
    project = tmp_path / "project"
    project.mkdir()
    draft = DeckProjectDraft(
        tool_profile="shell_smoke",
        files=(
            DeckFile(
                relative_path="run.sh",
                content="printf '0 1\\n1 2\\n' > curve.plt\n",
            ),
        ),
        entrypoint="run.sh",
        expected_outputs=(
            ProjectExpectedOutput(
                name="curve",
                relative_path="curve.plt",
                media_type="text/plain",
                max_bytes=1024,
            ),
        ),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=10,
            cpu_time_seconds=10,
            max_memory_bytes=256 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=8,
        ),
    )
    (project / "deck-project.json").write_text(
        _canonical(draft.model_dump(mode="json")), encoding="utf-8"
    )
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    runner = TCADExecutionFacade(
        policy=TCADExecutionPolicy(
            allowed_input_roots=(str(runtime.state_root / "execution-exchange"),),
            tools=(ToolProfile(profile_id="shell_smoke", executable="/bin/sh"),),
        ),
        state_root=tmp_path / "tcad-state",
    )
    bridge = ExecutionBridge(
        runtime.executions,
        adapters={"tcad": LocalTCADAdapter(runner)},
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance="test",
            execution_bridge=bridge,
        )
    )
    return root, runtime


def _approve(runtime: object, launch: dict[str, object]) -> None:
    approval_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="approval", name=str(launch["name"])
    )
    status = runtime.approvals.status(approval_id)
    token = parse_qs(urlparse(str(status.review_path)).query)["token"][0]
    review = runtime.approvals.review(approval_id, access_token=token)
    runtime.approvals.record_ui_decision(
        approval_id=approval_id,
        access_token=token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="authorize_execution",
        rationale="",
        decided_by=LocalIdentityRef(identity_id="test_user", display_name="Test user"),
        ui_session_id="test_session",
    )


def test_exact_execution_request_approval_drives_automatic_bridge(tmp_path: Path) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "deck_project",
            "relative_path": "deck-project.json",
            "media_type": "application/json",
        },
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.deck-project.v1",
            "payload_name": payload["name"],
        },
    )
    execution_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="execution", name=execution["name"]
    )
    payload_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="artifact", name=payload["name"]
    )
    request_ref, payload_ref = runtime.executions.approval_subject_refs(execution_id)
    request = runtime.artifacts.get_by_id(request_ref.artifact_id)
    request_payload = json.loads(runtime.artifacts.read(request.ref))
    assert request_payload["executor"] == "tcad"
    assert request_payload["preparation_profile"] == "tcad.deck-project.v1"

    approval = root.call_tool(
        "execution_approval_request_create", {"name": execution["name"]}
    )
    approval_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="approval", name=approval["name"]
    )
    approval_status = runtime.approvals.status(approval_id)
    review = runtime.approvals.review(
        approval_id,
        access_token=parse_qs(urlparse(approval_status.review_path).query)["token"][0],
    )
    assert review.request.subject_refs == (
        request.ref,
        runtime.artifacts.get_by_id(payload_id).ref,
    )
    assert json.loads(review.subjects[1][1])["tool_profile"] == "shell_smoke"
    _approve(runtime, approval)

    started = root.call_tool(
        "execution_start", {"name": execution["name"]},
    )
    assert started["state"] == "submitted"

    deadline = time.monotonic() + 5
    while True:
        synced = root.call_tool(
            "execution_sync", {"name": execution["name"]}
        )
        if synced["state"] == "collected":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert synced["result_artifact_name"] == "fixture_execution.result"
    listed = root.call_tool("execution_list", {"state": "collected", "limit": 1})
    assert listed["executions"][0]["name"] == execution["name"]
    outputs = root.call_tool(
        "execution_outputs", {"name": execution["name"]}
    )
    assert [(item["output_label"], item["media_type"]) for item in outputs["outputs"]] == [
        ("curve", "text/plain"),
        ("tcad_log", "text/plain; charset=utf-8"),
        ("tcad_manifest", "application/json"),
    ]
    assert all(
        item["artifact_name"].startswith("fixture_execution.output.")
        for item in outputs["outputs"]
    )


def test_abandoned_approved_execution_can_never_start(tmp_path: Path) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "deck_project", "relative_path": "deck-project.json", "media_type": "application/json"},
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.deck-project.v1",
            "payload_name": payload["name"],
        },
    )
    approval = root.call_tool(
        "execution_approval_request_create", {"name": execution["name"]}
    )
    _approve(runtime, approval)

    abandoned = root.call_tool(
        "execution_abandon", {"name": execution["name"]}
    )
    assert abandoned["state"] == "abandoned"
    assert root.call_tool(
        "execution_abandon", {"name": execution["name"]}
    )["state"] == "abandoned"
    with pytest.raises(ExecutionStateConflict, match="not authorizable"):
        root.call_tool(
            "execution_start",
            {"name": execution["name"]},
        )


def test_submitted_execution_can_be_cancelled_and_collected(tmp_path: Path) -> None:
    root, runtime = _root(tmp_path)
    project_file = runtime.project_root / "deck-project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["files"][0]["content"] = "sleep 30\n"
    project_file.write_text(_canonical(project), encoding="utf-8")
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "deck_project", "relative_path": "deck-project.json", "media_type": "application/json"},
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.deck-project.v1",
            "payload_name": payload["name"],
        },
    )
    approval = root.call_tool(
        "execution_approval_request_create", {"name": execution["name"]}
    )
    _approve(runtime, approval)
    root.call_tool(
        "execution_start", {"name": execution["name"]},
    )
    cancelled = root.call_tool(
        "execution_cancel", {"name": execution["name"]}
    )
    assert cancelled["state"] in {"cancelling", "cancelled"}
    deadline = time.monotonic() + 5
    while True:
        synced = root.call_tool(
            "execution_sync", {"name": execution["name"]}
        )
        if synced["state"] == "collected":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    outputs = root.call_tool(
        "execution_outputs", {"name": execution["name"]}
    )
    assert any(item["output_label"] == "tcad_log" for item in outputs["outputs"])
    assert all("artifact_name" in item and "name" not in item for item in outputs["outputs"])


def test_payload_approval_cannot_authorize_execution_request(tmp_path: Path) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "deck_project", "relative_path": "deck-project.json", "media_type": "application/json"},
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.deck-project.v1",
            "payload_name": payload["name"],
        },
    )
    wrong = root.call_tool(
        "approval_request_create",
        {
            "name": "wrong_execution_approval",
            "kind": "execution_authorization",
            "subject_names": [payload["name"]],
            "question": "Wrong subject",
            "options": [
                {
                    "option_key": "authorize_execution",
                    "label": "Authorize",
                    "description": "Wrong approval subject.",
                },
                {
                    "option_key": "revise_execution",
                    "label": "Revise",
                    "description": "Revise.",
                },
            ],
        },
    )
    wrong_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="approval", name=wrong["name"]
    )
    runtime.scheduler_bindings.bind(
        instance="test",
        namespace="approval",
        name="fixture_execution.approval",
        object_id=wrong_id,
    )
    _approve(runtime, wrong)

    with pytest.raises(ExecutionApprovalError, match="exact request and payload"):
        root.call_tool(
            "execution_start",
            {"name": execution["name"]},
        )


def test_unconfigured_executor_is_rejected_before_execution_is_registered(
    tmp_path: Path,
) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "deck_project", "relative_path": "deck-project.json", "media_type": "application/json"},
    )

    with pytest.raises(ExecutionServiceError, match="no execution adapter"):
        root.call_tool(
            "execution_request_create",
            {
                "name": "missing_execution",
                "executor": "missing",
                "preparation_profile": "tcad.deck-project.v1",
                "payload_name": payload["name"],
            },
        )

    with runtime.executions._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM executions").fetchone()[0] == 0


def test_terminal_result_collection_can_be_retried(tmp_path: Path) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "deck_project", "relative_path": "deck-project.json", "media_type": "application/json"},
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.deck-project.v1",
            "payload_name": payload["name"],
        },
    )
    approval = root.call_tool(
        "execution_approval_request_create", {"name": execution["name"]}
    )
    _approve(runtime, approval)
    root.call_tool(
        "execution_start", {"name": execution["name"]},
    )

    adapter = root.facade.execution_bridge.adapters["tcad"]
    original_collect = adapter.collect
    attempts = 0

    def fail_once(external_run_id: str):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient collection failure")
        return original_collect(external_run_id)

    adapter.collect = fail_once
    deadline = time.monotonic() + 5
    while True:
        try:
            root.call_tool(
                "execution_sync", {"name": execution["name"]}
            )
        except RuntimeError as error:
            assert str(error) == "transient collection failure"
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    execution_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="execution", name=execution["name"]
    )
    assert runtime.executions.status(execution_id).state in {
        "succeeded",
        "failed",
        "cancelled",
    }
    assert root.call_tool(
        "execution_sync", {"name": execution["name"]}
    )["state"] == "collected"


def test_authorized_execution_can_retry_after_prepare_failure(tmp_path: Path) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "deck_project", "relative_path": "deck-project.json", "media_type": "application/json"},
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.deck-project.v1",
            "payload_name": payload["name"],
        },
    )
    approval = root.call_tool(
        "execution_approval_request_create", {"name": execution["name"]}
    )
    _approve(runtime, approval)
    adapter = root.facade.execution_bridge.adapters["tcad"]
    original_prepare = adapter.prepare
    attempts = 0

    def fail_once(payload, *, preparation_profile, exchange_directory):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient preparation failure")
        return original_prepare(
            payload,
            preparation_profile=preparation_profile,
            exchange_directory=exchange_directory,
        )

    adapter.prepare = fail_once
    with pytest.raises(RuntimeError, match="transient preparation failure"):
        root.call_tool(
            "execution_start",
            {"name": execution["name"]},
        )
    execution_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="execution", name=execution["name"]
    )
    assert runtime.executions.status(execution_id).state == "authorized"
    assert root.call_tool(
        "execution_start",
        {"name": execution["name"]},
    )["state"] == "submitted"


def test_execution_request_change_requires_new_control_owned_revision(
    tmp_path: Path,
) -> None:
    root, runtime = _root(tmp_path)
    payload = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "deck_project",
            "relative_path": "deck-project.json",
            "media_type": "application/json",
        },
    )
    arguments = {
        "name": "baseline_execution",
        "executor": "tcad",
        "preparation_profile": "tcad.deck-project.v1",
        "payload_name": payload["name"],
    }
    first = root.call_tool("execution_request_create", arguments)
    assert root.call_tool("execution_request_create", arguments)["name"] == first["name"]

    project_file = runtime.project_root / "deck-project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    project["files"][0]["content"] = "printf 'revised\\n' > curve.plt\n"
    project_file.write_text(_canonical(project), encoding="utf-8")
    revised_payload = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "deck_project",
            "relative_path": "deck-project.json",
            "media_type": "application/json",
            "on_conflict": "create_revision",
        },
    )
    changed = {**arguments, "payload_name": revised_payload["name"]}
    with pytest.raises(SchedulerNameConflict, match="explicit revision"):
        root.call_tool("execution_request_create", changed)
    revised = root.call_tool(
        "execution_request_create",
        {**changed, "on_conflict": "create_revision"},
    )
    assert revised["name"] == "baseline_execution.rev2"
    assert revised["logical_name"] == "baseline_execution"
    assert revised["revision"] == 2
