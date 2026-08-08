from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_proxy import (
    bind_scheduler_proxy,
    forward_request,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema import LocalIdentityRef
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    DeckRequirementReview,
    DeckReviewReport,
    ProjectExpectedOutput,
    ProjectResourceLimits,
    RealizationRequirement,
    ReviewedDeckPackage,
)


@pytest.mark.process_e2e
def test_two_daemons_complete_approved_fixture_execution(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    scid_state = tmp_path / "scid-state"
    tcad_state = tmp_path / "tcad-state"
    control_socket = tmp_path / "control.sock"
    tcad_socket = tmp_path / "tcad.sock"
    task_secret = tmp_path / "task.key"
    approval_secret = tmp_path / "approval.key"
    task_secret.write_bytes(os.urandom(32))
    approval_secret.write_bytes(os.urandom(32))
    task_secret.chmod(0o600)
    approval_secret.chmod(0o600)

    draft = DeckProjectDraft(
        tool_profile="shell_fixture",
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
        realization_manifest=(
            RealizationRequirement(
                requirement_key="fixture_curve",
                category="observable",
                requirement="Produce the declared curve output.",
                evidence_class="test_fixture",
                evidence_source="process execution loop",
                evidence_locator="fixture contract",
                rationale="The process test needs one observable.",
                implementation_status="implemented",
                relative_path="run.sh",
                locator="curve.plt",
                verification_mode="runtime_output",
                expected_output_name="curve",
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
    reviewed = ReviewedDeckPackage(
        project=draft,
        review=DeckReviewReport(
            verdict="pass",
            summary="The process fixture has complete implementation coverage.",
            rationale="The declared curve is produced and collected.",
            physical_fidelity="pass",
            implementation_fidelity="pass",
            syntax_fidelity="pass",
            numerical_protocol_fidelity="pass",
            requirement_reviews=(
                DeckRequirementReview(
                    requirement_key="fixture_curve",
                    status="pass",
                    rationale="The output locator is present in run.sh.",
                ),
            ),
            execution_ready=True,
        ),
    )
    (project / "reviewed-deck-package.json").write_text(
        _canonical(reviewed.model_dump(mode="json")), encoding="utf-8"
    )
    policy = tmp_path / "policy.json"
    policy.write_text(
        _canonical(
            {
                "allowed_input_roots": [str(scid_state / "execution-exchange")],
                "max_concurrent_runs": 1,
                "tools": [
                    {
                        "profile_id": "shell_fixture",
                        "executable": "/bin/sh",
                        "arguments": [],
                        "environment": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    environment = {
        **os.environ,
        "PYTHONPATH": f"{Path.cwd() / 'src'}:{Path.cwd() / 'plugins/tcad_artifact'}",
    }
    runtime = open_runtime(
        project_root=project,
        state_root=scid_state,
        task_token_secret=task_secret.read_bytes(),
        approval_receipt_secret=approval_secret.read_bytes(),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="execution_fixture",
        title="Execution fixture",
        objective="Exercise the approved execution bridge.",
    )
    runtime.scheduler_bindings.bind_session(
        session_key="sch_" + "1" * 32,
        instance_id=instance.instance_id,
    )
    with _daemon(
        [
            sys.executable,
            "-m",
            "tcad_artifact.execution_daemon",
            "--state-root",
            str(tcad_state),
            "--policy",
            str(policy),
            "--socket",
            str(tcad_socket),
        ],
        socket=tcad_socket,
        environment=environment,
    ), _daemon(
        [
            sys.executable,
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_daemon",
            "--project-root",
            str(project),
            "--state-root",
            str(scid_state),
            "--socket",
            str(control_socket),
            "--task-secret-file",
            str(task_secret),
            "--approval-secret-file",
            str(approval_secret),
            "--tcad-socket",
            str(tcad_socket),
        ],
        socket=control_socket,
        environment=environment,
    ):
        source = _call(
            control_socket,
            "artifact_ingest_file",
            {
                "name": "reviewed_deck_package",
                "relative_path": "reviewed-deck-package.json",
                "media_type": "application/json",
            },
        )
        execution = _call(
            control_socket,
            "execution_request_create",
            {
                "name": "fixture_execution",
                "executor": "tcad",
                "preparation_profile": "tcad.reviewed-deck-package.v1",
                "payload_name": source["name"],
            },
        )
        approval = _call(
            control_socket,
            "execution_approval_request_create",
            {"name": execution["name"]},
        )
        instance_id = runtime.scheduler_bindings.select_instance(
            name="execution_fixture"
        ).instance_id
        approval_id = runtime.scheduler_bindings.resolve(
            instance=instance_id, namespace="approval", name=approval["name"]
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
            decided_by=LocalIdentityRef(
                identity_id="fixture_user", display_name="Fixture user"
            ),
            ui_session_id="fixture_session",
        )
        started = _call(
            control_socket,
            "execution_start",
            {"name": execution["name"]},
        )
        assert started["state"] == "submitted"
        deadline = time.monotonic() + 5
        while True:
            status = _call(
                control_socket,
                "execution_sync",
                {"name": execution["name"]},
            )
            if status["state"] == "collected":
                break
            assert time.monotonic() < deadline
            time.sleep(0.02)
        assert status["result_artifact_name"] == "fixture_execution.result"


@pytest.mark.process_e2e
def test_worker_proxy_binds_assignment_without_model_visible_identity(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = tmp_path / "state"
    control_socket = tmp_path / "control.sock"
    worker_socket = tmp_path / "worker.sock"
    task_secret = tmp_path / "task.key"
    approval_secret = tmp_path / "approval.key"
    task_secret.write_bytes(os.urandom(32))
    approval_secret.write_bytes(os.urandom(32))
    task_secret.chmod(0o600)
    approval_secret.chmod(0o600)
    environment = {
        **os.environ,
        "PYTHONPATH": f"{Path.cwd() / 'src'}:{Path.cwd() / 'plugins/tcad_artifact'}",
    }
    runtime = open_runtime(
        project_root=project,
        state_root=state,
        task_token_secret=task_secret.read_bytes(),
        approval_receipt_secret=approval_secret.read_bytes(),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="worker_fixture",
        title="Worker fixture",
        objective="Exercise identity-free worker dispatch.",
    )
    runtime.scheduler_bindings.bind_session(
        session_key="sch_" + "1" * 32,
        instance_id=instance.instance_id,
    )

    with _daemon(
        [
            sys.executable,
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_daemon",
            "--project-root",
            str(project),
            "--state-root",
            str(state),
            "--socket",
            str(control_socket),
            "--task-secret-file",
            str(task_secret),
            "--approval-secret-file",
            str(approval_secret),
        ],
        socket=control_socket,
        environment=environment,
    ), _daemon(
        [
            sys.executable,
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_daemon",
            "--project-root",
            str(project),
            "--state-root",
            str(state),
            "--socket",
            str(worker_socket),
            "--task-secret-file",
            str(task_secret),
        ],
        socket=worker_socket,
        environment=environment,
    ), _worker_proxy(
        worker_socket,
        role="critic",
        environment=environment,
    ) as proxy:
        task = _call(
            control_socket,
            "task_schedule",
            {
                "name": "process_critic",
                "role": "critic",
                "instruction": "Review one process-bound candidate.",
                "max_attempts": 1,
            },
        )
        dispatch = _call(
            control_socket,
            "task_prepare_dispatch",
            {"name": task["name"], "ttl_seconds": 60},
        )
        assert dispatch == {"task_name": "process_critic", "agent_type": "critic"}
        assert proxy.call("worker_claim_task", {}) == {"state": "claimed"}
        assignment = proxy.call("worker_get_assignment", {})
        assert assignment["instruction"] == "Review one process-bound candidate."
        assert "task_id" not in json.dumps(assignment).lower()
        proxy.call(
            "worker_finalize",
            {
                "content": {
                    "schema_version": 1,
                    "handoff": {
                        "verdict": "pass",
                        "summary": "The candidate is internally consistent.",
                    },
                    "payload": {
                        "schema_version": 1,
                        "reviews": [],
                    },
                },
            },
        )
        status = _call(
            control_socket,
            "task_status",
            {"name": task["name"]},
        )
        assert status["state"] == "completed"


@contextmanager
def _daemon(
    command: list[str],
    *,
    socket: Path,
    environment: dict[str, str],
):
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    deadline = time.monotonic() + 5
    while not socket.exists():
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                f"daemon exited early: {stdout.decode()} {stderr.decode()}"
            )
        assert time.monotonic() < deadline
        time.sleep(0.02)
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _call(socket: Path, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    request = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        separators=(",", ":"),
    ).encode()
    response = forward_request(
        socket,
        bind_scheduler_proxy(request, "sch_" + "1" * 32),
        timeout=5,
    )
    if "error" in response:
        raise AssertionError(response["error"])
    return response["result"]["structuredContent"]


class _WorkerProxyClient:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self.request_id = 0

    def call(self, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.request_id += 1
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
            separators=(",", ":"),
        ).encode()
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(request + b"\n")
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        if "error" in response:
            raise AssertionError(response["error"])
        return response["result"]["structuredContent"]


@contextmanager
def _worker_proxy(
    socket: Path,
    *,
    role: str,
    environment: dict[str, str],
):
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_proxy",
            "--socket",
            str(socket),
            "--worker-id",
            role,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        yield _WorkerProxyClient(process)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
