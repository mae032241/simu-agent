from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
import time
from pathlib import Path

from scidiscovery.artifact_agent.schema import LocalFileDescriptor
from tcad_artifact.command_adapter import (
    CommandAdapterConfig,
    CommandTCADExecutorAdapter,
)
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


def _reviewed_payload(draft: DeckProjectDraft) -> bytes:
    locator = draft.files[0].content.strip().splitlines()[0]
    project = draft.model_copy(
        update={
            "realization_manifest": (
                RealizationRequirement(
                    requirement_key="fixture_entrypoint",
                    category="numerical_protocol",
                    requirement="Run the fixture entrypoint.",
                    evidence_class="test_fixture",
                    evidence_source="command adapter test",
                    evidence_locator="entrypoint",
                    rationale="This requirement qualifies the transport fixture.",
                    implementation_status="implemented",
                    relative_path=draft.files[0].relative_path,
                    locator=locator,
                    verification_mode="static_review",
                ),
            )
        }
    )
    review = DeckReviewReport(
        verdict="pass",
        summary="The fixture entrypoint is review-complete.",
        rationale="The only declared requirement has exact static coverage.",
        physical_fidelity="pass",
        implementation_fidelity="pass",
        syntax_fidelity="pass",
        numerical_protocol_fidelity="pass",
        requirement_reviews=(
            DeckRequirementReview(
                requirement_key="fixture_entrypoint",
                status="pass",
                rationale="The entrypoint locator is present.",
            ),
        ),
        execution_ready=True,
    )
    reviewed = ReviewedDeckPackage(project=project, review=review)
    return json.dumps(
        reviewed.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_bounded_command_adapter_prepares_and_collects_verified_outputs(
    tmp_path: Path,
) -> None:
    transport = tmp_path / "transport.py"
    transport.write_text(
        """
import hashlib
import json
import os
from pathlib import Path
import sys

request = json.load(sys.stdin)
operation = request["operation"]
payload = request["payload"]
if operation == "prepare":
    result = {"submission": payload["job_spec"]}
elif operation == "submit":
    result = {"run_id": "run_fixture", "state": "accepted"}
elif operation == "status":
    result = {"state": "succeeded"}
elif operation == "collect":
    root = Path(payload["local_result_root"]) / payload["run_id"]
    root.mkdir(parents=True, exist_ok=True)
    path = root / "curve.plt"
    raw = b"0 1\\n1 2\\n"
    path.write_bytes(raw)
    result = {"outputs": [{
        "name": "curve",
        "local_path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "media_type": "text/plain"
    }]}
else:
    raise SystemExit(64)
json.dump({"schema_version": 1, "operation": operation, "ok": True, "payload": result}, sys.stdout, sort_keys=True, separators=(",", ":"))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = CommandAdapterConfig(
        executable=sys.executable,
        arguments=(str(transport),),
        operation_timeout_seconds=5,
    )
    adapter = CommandTCADExecutorAdapter(
        config,
        local_result_root=tmp_path / "results",
    )
    exchange = tmp_path / "exe_0123456789abcdef0123456789abcdef"
    exchange.mkdir()
    draft = DeckProjectDraft(
        tool_profile="shell_smoke",
        files=(DeckFile(relative_path="run.sh", content="printf curve\n"),),
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
            max_memory_bytes=1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=4,
        ),
    )
    raw = _reviewed_payload(draft)
    payload_path = exchange / "payload.bin"
    payload_path.write_bytes(raw)
    payload = LocalFileDescriptor(
        name="execution_payload",
        local_path=str(payload_path),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        media_type="application/json",
    )

    submission = adapter.prepare(
        payload,
        preparation_profile="tcad.reviewed-deck-package.v1",
        exchange_directory=exchange,
    )
    run_id, state = adapter.submit(submission)
    assert (run_id, state) == ("run_fixture", "accepted")
    assert adapter.status(run_id) == "succeeded"
    outputs = adapter.collect(run_id)
    assert len(outputs) == 1
    assert Path(outputs[0].local_path).read_text() == "0 1\n1 2\n"


def test_command_adapter_reaches_dependency_free_runner_end_to_end(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    remote_exchange = tmp_path / "remote-exchange"
    remote_state = tmp_path / "remote-state"
    remote_exchange.mkdir()
    remote_state.mkdir()
    runner_config = tmp_path / "runner.json"
    runner_config.write_text(
        json.dumps(
            {
                "exchange_root": str(remote_exchange),
                "state_root": str(remote_state),
                "result_root": str(remote_state / "runs"),
                "max_concurrent_runs": 1,
                "max_transfer_bytes": 8 * 1024 * 1024,
                "tools": [
                    {
                        "profile_id": "shell-smoke",
                        "executable": "/bin/sh",
                        "arguments": [],
                        "environment": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    runner = (
        project_root
        / "plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"
    )
    ssh_shim = tmp_path / "ssh-shim"
    ssh_shim.write_text(
        "#!/bin/sh\nexec "
        + " ".join(
            shlex.quote(value)
            for value in (
                sys.executable,
                str(runner),
                "--config",
                str(runner_config),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    ssh_shim.chmod(0o750)
    transport_config = tmp_path / "transport.json"
    transport_config.write_text(
        json.dumps(
            {
                "connect_timeout_seconds": 1,
                "destination": "da@test-vm",
                "max_transfer_bytes": 8 * 1024 * 1024,
                "operation_timeout_seconds": 10,
                "port": 22,
                "remote_config": "/remote/config.json",
                "remote_exchange_root": str(remote_exchange),
                "remote_helper": "/remote/runner",
                "ssh_executable": str(ssh_shim),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    local_result_root = tmp_path / "executor-results"
    adapter = CommandTCADExecutorAdapter(
        CommandAdapterConfig(
            executable=sys.executable,
            arguments=(
                "-m",
                "tcad_artifact.ssh_transport",
                "--config",
                str(transport_config),
            ),
            environment={
                "PYTHONPATH": os.pathsep.join(
                    (
                        str(project_root / "src"),
                        str(project_root / "plugins/tcad_artifact"),
                    )
                ),
                "SCIDISCOVERY_TCAD_RESULT_ROOT": str(
                    local_result_root
                ),
            },
            operation_timeout_seconds=10,
        ),
        local_result_root=local_result_root,
    )
    exchange = tmp_path / "execution-exchange"
    exchange.mkdir()
    draft = DeckProjectDraft(
        tool_profile="shell-smoke",
        files=(
            DeckFile(
                relative_path="run.sh",
                content="printf 'curve\\n' > curve.plt\n",
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
            max_memory_bytes=128 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=4,
        ),
    )
    raw = _reviewed_payload(draft)
    payload_path = exchange / "payload.json"
    payload_path.write_bytes(raw)
    payload = LocalFileDescriptor(
        name="execution_payload",
        local_path=str(payload_path),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        media_type="application/json",
    )

    submission = adapter.prepare(
        payload,
        preparation_profile="tcad.reviewed-deck-package.v1",
        exchange_directory=exchange,
    )
    run_id, state = adapter.submit(submission)
    assert state == "accepted"
    deadline = time.monotonic() + 5
    while adapter.status(run_id) != "succeeded":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    outputs = adapter.collect(run_id)
    curve = next(item for item in outputs if item.name == "curve")
    assert Path(curve.local_path).read_text(encoding="utf-8") == "curve\n"
