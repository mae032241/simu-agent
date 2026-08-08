from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_worker import WorkerMCPRouter
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema import LocalFileDescriptor, LocalIdentityRef
from tcad_artifact.execution_control import (
    ArchiveEntry,
    ExpectedOutput,
    FileDescriptor,
    ResourceLimits,
    TCADExecutionFacade,
    TCADExecutionPolicy,
    TCADJobSpec,
    ToolProfile,
)


def test_approved_execution_result_can_drive_next_scientific_task(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    script = b"printf '0 1\\n1 2\\n' > curve.plt\n"
    archive = project / "job.tar"
    with tarfile.open(archive, "w") as bundle:
        member = tarfile.TarInfo("run.sh")
        member.size = len(script)
        bundle.addfile(member, io.BytesIO(script))
    job = TCADJobSpec(
        tool_profile="fixture",
        input_archive=_descriptor("input_archive", archive, "application/x-tar"),
        archive_entries=(
            ArchiveEntry(
                relative_path="run.sh",
                sha256=hashlib.sha256(script).hexdigest(),
                size_bytes=len(script),
            ),
        ),
        arguments=("run.sh",),
        expected_outputs=(
            ExpectedOutput(
                name="curve",
                relative_path="curve.plt",
                media_type="text/plain",
                max_bytes=1024,
            ),
        ),
        limits=ResourceLimits(
            wall_time_seconds=10,
            cpu_time_seconds=10,
            max_memory_bytes=256 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=8,
        ),
    )
    job_path = project / "job.json"
    job_path.write_bytes(_canonical(job.model_dump(mode="python")))

    state = tmp_path / "scid-state"
    runtime = open_runtime(
        project_root=project,
        state_root=state,
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    tcad = TCADExecutionFacade(
        policy=TCADExecutionPolicy(
            allowed_input_roots=(str(project), str(state / "execution-exchange")),
            tools=(ToolProfile(profile_id="fixture", executable="/bin/sh"),),
        ),
        state_root=tmp_path / "tcad-state",
    )

    class PreparedJobAdapter:
        def prepare(self, payload, *, preparation_profile, exchange_directory):
            assert preparation_profile == "tcad.job-spec.v1"
            return payload

        def submit(self, submission):
            value = tcad.tcad_submit(submission=submission)
            return value["run_id"], value["state"]

        def status(self, external_run_id):
            return tcad.tcad_status(run_id=external_run_id)["state"]

        def collect(self, external_run_id):
            return tuple(
                LocalFileDescriptor.model_validate(item, strict=True)
                for item in tcad.tcad_collect(run_id=external_run_id)["outputs"]
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
            execution_bridge=ExecutionBridge(
                runtime.executions, adapters={"tcad": PreparedJobAdapter()}
            ),
        )
    )
    payload = root.call_tool(
        "artifact_ingest_file",
        {"name": "fixture_job", "relative_path": "job.json", "media_type": "application/json"},
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "tcad",
            "preparation_profile": "tcad.job-spec.v1",
            "payload_name": payload["name"],
        },
    )
    approval = root.call_tool(
        "execution_approval_request_create",
        {"name": execution["name"]},
    )
    approval_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="approval", name=approval["name"]
    )
    approval_status = runtime.approvals.status(approval_id)
    token = parse_qs(urlparse(approval_status.review_path).query)["token"][0]
    review = runtime.approvals.review(approval_id, access_token=token)
    runtime.approvals.record_ui_decision(
        approval_id=approval_id,
        access_token=token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="authorize_execution",
        rationale="",
        decided_by=LocalIdentityRef(identity_id="fixture_user", display_name="Fixture user"),
        ui_session_id="fixture_session",
    )
    root.call_tool(
        "execution_start", {"name": execution["name"]},
    )

    deadline = time.monotonic() + 5
    while True:
        result = root.call_tool(
            "execution_sync", {"name": execution["name"]}
        )
        if result["state"] == "collected":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    task = root.call_tool(
        "task_schedule",
        {
            "name": "fixture_diagnosis",
            "role": "diagnostician",
            "instruction": "Assess the terminal result and state one next action.",
            "inputs": [
                {
                    "source_name": "simulation_result",
                    "artifact_name": result["result_artifact_name"],
                },
            ],
        },
    )
    root.call_tool(
        "task_prepare_dispatch", {"name": task["name"], "ttl_seconds": 60}
    )
    worker = WorkerMCPRouter(runtime.tasks, worker_id="diagnostician")
    worker.call_tool("worker_claim_task", {})
    worker.call_tool(
        "worker_finalize",
        {
            "content": {
                "schema_version": 1,
                "handoff": {
                    "verdict": "pass",
                    "summary": "The fixture result is ready for inspection.",
                    "next_actions": ["inspect_curve"],
                },
                "payload": {
                    "study_kind": "engineering",
                    "experiment_key": "shell_fixture",
                    "plan_key": "validate_shell_fixture",
                    "summary": "The engineering fixture execution completed and produced its declared output.",
                    "evidence": [
                        {
                            "source_key": "simulation_result",
                            "source_type": "runtime_output",
                            "title": "Collected fixture result",
                            "locator": "execution result manifest",
                        }
                    ],
                    "gates": {
                    "evidence_identity": {
                        "status": "pass",
                        "summary": "The collected result is bound to this fixture.",
                        "evidence_keys": ["simulation_result"],
                    },
                    "implementation_fidelity": {
                        "status": "pass",
                        "summary": "The declared shell command was executed.",
                        "evidence_keys": ["simulation_result"],
                    },
                    "numerical_validity": {
                        "status": "pass",
                        "summary": "The engineering process completed successfully.",
                        "evidence_keys": ["simulation_result"],
                    },
                    "control_equivalence": {
                        "status": "not_applicable",
                        "summary": "The engineering fixture has no scientific comparison.",
                    },
                    "observation": {
                        "status": "pass",
                        "summary": "The declared output was collected.",
                        "evidence_keys": ["simulation_result"],
                    },
                    "physical_interpretation": {
                        "status": "not_applicable",
                        "summary": "The shell fixture contains no physical model.",
                    },
                    },
                    "overall_verdict": "pass",
                    "claim_allowed": False,
                    "remaining_contradiction": "No scientific contradiction is tested by this fixture.",
                    "recommended_task_mode": "stop",
                    "next_action": "Inspect the curve only if a downstream fixture requires it.",
                },
            },
        },
    )
    assert root.call_tool("task_status", {"name": task["name"]})["state"] == "completed"
    assert root.call_tool(
        "execution_status", {"name": execution["name"]}
    )["state"] == "collected"


def _descriptor(name: str, path: Path, media_type: str) -> FileDescriptor:
    raw = path.read_bytes()
    return FileDescriptor(
        name=name,
        local_path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        media_type=media_type,
    )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
