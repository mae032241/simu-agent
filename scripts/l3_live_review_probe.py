#!/usr/bin/env python3
"""Prepare and verify a persistent direct Agent author-reviewer L3 probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE_PLUGIN = REPOSITORY / "tests/fixtures/plugins/blind_csv_operation_plugin"
for candidate in (REPOSITORY, REPOSITORY / "src", FIXTURE_PLUGIN):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN  # noqa: E402
from scripts import run_compiled_codex_worker as launcher  # noqa: E402
from scidiscovery.artifact_agent.interfaces.mcp_root import (  # noqa: E402
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime  # noqa: E402
from scidiscovery.artifact_agent.schema.artifact import (  # noqa: E402
    ArtifactRegistration,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN  # noqa: E402
from scidiscovery.general_science_plugin import (  # noqa: E402
    PLUGIN as GENERAL_PLUGIN,
)
from scidiscovery.operations.catalog import compile_catalog  # noqa: E402
from scidiscovery.operations.tooling import (  # noqa: E402
    operation_agent_type,
    operation_local_worker_tool_names,
    operation_worker_server_name,
)
from scidiscovery.platforms.codex import initialize  # noqa: E402


RAW = b"sample,value\na,1\nb,3\n"
AUTHOR_OPERATION = "blind.csv.observe.v1"
REVIEW_OPERATION = "blind.csv.review.v1"
LAUNCHER_MEMORY_LIMIT_MIB = 4096
AUTHOR_LAUNCHER_RECEIPT = "author_launcher_receipt"
REVIEW_LAUNCHER_RECEIPT = "reviewer_launcher_receipt"
RECOVERY_LAUNCHER_RECEIPT = "recovery_launcher_receipt"
AUTHOR_INSTRUCTION = "Make one bounded observation from the exact CSV."


def _catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN))


def _runtime(root: Path):
    runtime = open_runtime(
        project_root=root / "project",
        state_root=root / "state",
        worker_backend="local",
    )
    assert runtime.runs is not None
    runtime.runs.operation_catalog = _catalog()
    return runtime


def _root(runtime, instance_id: str):
    return RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance_id,
            operation_catalog=runtime.runs.operation_catalog,
        )
    )


def _control(root: Path) -> dict[str, str]:
    return json.loads((root / "control.json").read_text("utf-8"))


def _write_control(root: Path, value: dict[str, str]) -> None:
    (root / "control.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8"
    )


def _standalone_python_path(root: Path) -> Path:
    target = root / "pythonpath"
    target.mkdir()
    os.symlink(
        REPOSITORY / "src/scidiscovery",
        target / "scidiscovery",
        target_is_directory=True,
    )
    os.symlink(
        FIXTURE_PLUGIN / "blind_csv_plugin",
        target / "blind_csv_plugin",
        target_is_directory=True,
    )
    metadata = target / "scidiscovery_l3_probe-0.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: scidiscovery-l3-probe\nVersion: 0.0\n",
        "utf-8",
    )
    (metadata / "entry_points.txt").write_text(
        "[scidiscovery.plugins]\n"
        "builtin = scidiscovery.builtin_plugin:CORE_PLUGIN\n"
        "general_science = scidiscovery.general_science_plugin:PLUGIN\n"
        "blind_csv = blind_csv_plugin.plugin:PLUGIN\n",
        "utf-8",
    )
    return target


def _write_dispatch(
    root: Path,
    *,
    label: str,
    operation_id: str,
    python_path: Path,
    receipt_name: str | None = None,
) -> None:
    compiled = _catalog().operation(operation_id)
    agent_type = operation_agent_type(compiled)
    runtime = _runtime(root)
    instance_id = _control(root)["instance_id"]
    queued = [runtime.runs.status(run_id) for run_id in runtime.runs.active_ids(instance_id=instance_id, limit=100)]
    queued = [run for run in queued if run.operation_id == operation_id and run.state == "queued"]
    if len(queued) != 1 or queued[0].execution_profile is None:
        raise ValueError("probe dispatch requires one exact queued Run with execution profile")
    profile = queued[0].execution_profile["profile"]
    calls = ["worker_open_assignment"]
    if operation_id == AUTHOR_OPERATION:
        calls.append("worker_csv_summarize")
    calls.append("worker_submit_result")
    if receipt_name is None:
        receipt_name = (
            AUTHOR_LAUNCHER_RECEIPT
            if operation_id == AUTHOR_OPERATION
            else REVIEW_LAUNCHER_RECEIPT
        )
    launcher_command = [
        sys.executable,
        str(REPOSITORY / "scripts/run_compiled_codex_worker.py"),
        "--project-root",
        str(root / "project"),
        "--agent-type",
        agent_type,
        "--model", profile["model"],
        "--reasoning-effort", profile["reasoning_effort"],
        "--memory-limit-mib",
        str(LAUNCHER_MEMORY_LIMIT_MIB),
        "--receipt-name",
        receipt_name,
    ]
    if launcher._inside_codex_outer_sandbox():
        launcher_command.append("--externally-sandboxed-debug")
    (root / f"{label}-dispatch.json").write_text(
        json.dumps(
            {
                "generated_profile": str(
                    root / "project/.codex/agents" / f"{agent_type}.toml"
                ),
                "expected_agent_type": agent_type,
                "launcher_command": launcher_command,
                "required_worker_calls": calls,
                "standalone_python_path": str(python_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )


def _verify_launcher_receipt(
    root: Path,
    *,
    receipt_name: str,
    agent_type: str,
    operation_id: str,
    run: dict[str, object],
    expected_memory_limit_mib: int,
    expected_external_sandbox_debug: bool,
) -> str:
    if not receipt_name or Path(receipt_name).name != receipt_name:
        raise SystemExit("launcher receipt name is invalid")
    compiled = _catalog().operation(operation_id)
    expected_tools = set(operation_local_worker_tool_names(compiled))
    required = {"worker_open_assignment", "worker_submit_result"}
    if operation_id == AUTHOR_OPERATION:
        required.add("worker_csv_summarize")
    try:
        return launcher.verify_receipt(
            receipt_path=root / "launch-receipts" / f"{receipt_name}.json",
            project_root=root / "project",
            agent_type=agent_type,
            expected_target_server=operation_worker_server_name(compiled),
            allowed_worker_tools=expected_tools,
            required_worker_tools=required,
            run_started_at=str(run["started_at"]),
            run_completed_at=str(run["completed_at"]),
            expected_memory_limit_mib=expected_memory_limit_mib,
            expected_external_sandbox_debug=expected_external_sandbox_debug,
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise SystemExit(str(error)) from error


def prepare(root: Path) -> None:
    if root.exists():
        raise SystemExit(f"refusing to overwrite existing probe: {root}")
    (root / "project").mkdir(parents=True)
    (root / "project/AGENTS.md").write_text("# L3 direct review probe\n", "utf-8")
    python_path = _standalone_python_path(root)
    runtime = _runtime(root)
    catalog = runtime.runs.operation_catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="l3_direct_review_probe",
        title="L3 direct review probe",
        objective="Verify a real author and independent reviewer through sealed files.",
    )
    source = runtime.artifacts.register(
        RAW,
        ArtifactRegistration(
            kind="blind_csv_input",
            schema_id="blind.opaque.v1",
            payload_schema_version=1,
            media_type="text/csv",
            creator=runtime.actor,
        ),
        idempotency_key="l3:direct-review:source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="source_csv",
        object_id=source.artifact_id,
    )
    invoked = _root(runtime, instance.instance_id).call_tool(
        "operation_invoke",
        {
            "name": "author",
            "operation_id": AUTHOR_OPERATION,
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": AUTHOR_INSTRUCTION,
        },
    )
    initialize(
        root / "project",
        python_executable=Path(sys.executable),
        python_path=python_path,
        control_socket=root / "unused-control.sock",
        state_root=root / "state",
        operation_catalog=catalog,
    )
    _write_control(
        root,
        {
            "instance_id": instance.instance_id,
            "author_run_name": "author",
            "author_agent_type": invoked["result"]["agent_type"],
            "author_launcher_receipt": AUTHOR_LAUNCHER_RECEIPT,
            "review_launcher_receipt": REVIEW_LAUNCHER_RECEIPT,
            "launcher_externally_sandboxed_debug": launcher._inside_codex_outer_sandbox(),
            "launcher_memory_limit_mib": LAUNCHER_MEMORY_LIMIT_MIB,
        },
    )
    _write_dispatch(
        root,
        label="author",
        operation_id=AUTHOR_OPERATION,
        python_path=python_path,
    )


def simulate_failure_and_queue_recovery(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    router = _root(runtime, control["instance_id"])
    source_name = control["author_run_name"]
    before = router.call_tool("run_status", {"name": source_name})
    if before["state"] != "queued":
        raise SystemExit(f"recovery source is not queued: {before['state']}")
    compiled = runtime.runs.operation_catalog.operation(AUTHOR_OPERATION)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "pythonpath")
    environment["PYTHONNOUSERSITE"] = "1"
    helper = REPOSITORY / "tests/fixtures/m7_recovery_crash_worker.py"
    crashed = subprocess.run(
        [
            sys.executable,
            str(helper),
            "--state-root",
            str(root / "state"),
            "--operation-id",
            compiled.spec.operation_id,
            "--operation-digest",
            compiled.digest,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if crashed.returncode != 73:
        raise SystemExit(
            f"crash Worker returned {crashed.returncode}: {crashed.stderr.strip()}"
        )
    try:
        crash_receipt = json.loads(crashed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit("crash Worker returned an invalid receipt") from error
    marker_sha256 = crash_receipt.get("draft_marker_sha256")
    if (
        crash_receipt.get("domain_tool_called") is not True
        or crash_receipt.get("draft_written") is not True
        or crash_receipt.get("opened_assignment") is not True
        or crash_receipt.get("schema_version") != 1
        or crash_receipt.get("submitted") is not False
        or not isinstance(marker_sha256, str)
        or len(marker_sha256) != 64
    ):
        raise SystemExit("crash Worker receipt is incomplete")
    running = router.call_tool("run_status", {"name": source_name})
    if (
        running["state"] != "running"
        or "worker_csv_summarize"
        not in runtime.runs.successful_tools(
            runtime.scheduler_bindings.resolve(
                instance=control["instance_id"], namespace="run", name=source_name
            )
        )
    ):
        raise SystemExit("crash Worker did not open and use its registered tool")
    failed = router.call_tool(
        "run_record_failure",
        {
            "name": source_name,
            "reason": "M7 fault-injection Worker exited 73 before submit",
            "expected_state": "running",
            "expected_last_activity_at": running["last_activity_at"],
        },
    )
    if failed["state"] != "failed" or not failed["recovery_available"]:
        raise SystemExit("fault-injection Run did not preserve a recovery draft")
    source_run_id = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"], namespace="run", name=source_name
    )
    source_status = runtime.runs.status(source_run_id)
    assert source_status.recovery_draft is not None
    draft_files = source_status.recovery_draft.get("files")
    if not isinstance(draft_files, list) or len(draft_files) != 1:
        raise SystemExit("fault-injection recovery manifest is not bounded")
    draft_sha256 = draft_files[0].get("sha256")
    if not isinstance(draft_sha256, str):
        raise SystemExit("fault-injection recovery draft has no digest")
    draft_registered = any(
        envelope.ref.sha256 == draft_sha256
        for envelope in runtime.artifacts.list_artifacts(limit=10_000)
    )
    if draft_registered:
        raise SystemExit("failed Run draft was registered as an Artifact")
    (root / "failure-evidence.json").write_text(
        json.dumps(
            {
                "accepted_candidate_absent": (
                    source_status.accepted_candidate_digest is None
                ),
                "completion_receipt_absent": (
                    source_status.completion_receipt is None
                ),
                "draft_file_count": len(draft_files),
                "draft_marker_sha256": marker_sha256,
                "draft_registered_as_artifact": draft_registered,
                "output_ref_absent": source_status.output_ref is None,
                "scheduler_signal_absent": source_status.signal is None,
                "schema_version": 1,
                "state": source_status.state,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )
    (root / "crash-worker-receipt.json").write_text(
        json.dumps(
            {**crash_receipt, "exit_code": crashed.returncode},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )

    wrong = runtime.artifacts.register(
        b"sample,value\na,9\n",
        ArtifactRegistration(
            kind="blind_csv_input",
            schema_id="blind.opaque.v1",
            payload_schema_version=1,
            media_type="text/csv",
            creator=runtime.actor,
        ),
        idempotency_key="m7:recovery:wrong-source",
    )
    runtime.scheduler_bindings.bind(
        instance=control["instance_id"],
        namespace="artifact",
        name="wrong_source_csv",
        object_id=wrong.artifact_id,
    )
    before_runs = router.call_tool("run_list", {})
    wrong_preflight = router.call_tool(
        "operation_preflight",
        {
            "name": "wrong_recovery_input",
            "operation_id": AUTHOR_OPERATION,
            "inputs": [
                {"port": "source_table", "artifact_names": ["wrong_source_csv"]}
            ],
            "instruction": AUTHOR_INSTRUCTION,
            "resume_from": source_name,
        },
    )
    if wrong_preflight.get("admissible") is not False:
        raise SystemExit("wrong recovery input passed preflight")
    if router.call_tool("run_list", {}) != before_runs:
        raise SystemExit("rejected recovery preflight changed Run state")
    try:
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="run",
            name="wrong_recovery_input",
        )
    except Exception:
        pass
    else:
        raise SystemExit("rejected recovery preflight created a Run binding")
    correct_request = {
        "name": "author_recovered",
        "operation_id": AUTHOR_OPERATION,
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
        "instruction": AUTHOR_INSTRUCTION,
        "resume_from": source_name,
    }
    correct_preflight = router.call_tool("operation_preflight", correct_request)
    if correct_preflight.get("admissible") is not True:
        raise SystemExit(f"correct recovery preflight failed: {correct_preflight}")
    invoked = router.call_tool("operation_invoke", correct_request)
    if invoked["result"]["state"] != "queued":
        raise SystemExit("recovery Run was not queued")
    (root / "recovery-preflight.json").write_text(
        json.dumps(
            {
                "correct": correct_preflight,
                "rejected_request_created_no_run": True,
                "wrong_input": wrong_preflight,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )
    control.update(
        {
            "recovery_run_name": "author_recovered",
            "recovery_agent_type": invoked["result"]["agent_type"],
            "recovery_launcher_receipt": RECOVERY_LAUNCHER_RECEIPT,
            "recovery_source_run_name": source_name,
        }
    )
    _write_control(root, control)
    _write_dispatch(
        root,
        label="recovery",
        operation_id=AUTHOR_OPERATION,
        python_path=root / "pythonpath",
        receipt_name=RECOVERY_LAUNCHER_RECEIPT,
    )


def status_recovery(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    router = _root(runtime, control["instance_id"])
    source = router.call_tool(
        "run_status", {"name": control["recovery_source_run_name"]}
    )
    recovered = router.call_tool(
        "run_status", {"name": control["recovery_run_name"]}
    )
    if source["state"] != "failed" or recovered["state"] != "completed":
        raise SystemExit("recovery probe has not reached its terminal states")
    source_id = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"],
        namespace="run",
        name=control["recovery_source_run_name"],
    )
    recovered_id = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"],
        namespace="run",
        name=control["recovery_run_name"],
    )
    source_status = runtime.runs.status(source_id)
    recovered_status = runtime.runs.status(recovered_id)
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.row_factory = sqlite3.Row
        source_row = connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (source_id,)
        ).fetchone()
        recovered_row = connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (recovered_id,)
        ).fetchone()
        output_rejected_count = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM run_activity
                WHERE run_id = ? AND activity = 'output_rejected'
                """,
                (recovered_id,),
            ).fetchone()[0]
        )
    if source_row is None or recovered_row is None:
        raise SystemExit("recovery Run rows are unavailable after restart")
    if recovered_row["resume_from_run_id"] != source_id:
        raise SystemExit("recovery Run does not point to the failed source")
    if any(
        source_row[field] != recovered_row[field]
        for field in (
            "operation_id",
            "operation_version",
            "operation_digest",
            "instruction",
            "inputs_json",
        )
    ):
        raise SystemExit("recovery Run changed its Operation, instruction, or inputs")
    if (
        source_status.output_ref is not None
        or source_status.signal is not None
        or source_status.completion_receipt is not None
        or source_status.accepted_candidate_digest is not None
        or source_status.recovery_draft is None
    ):
        raise SystemExit("failed source leaked a scientific result")
    compiled = runtime.runs.operation_catalog.operation(AUTHOR_OPERATION)
    assert compiled.spec.limits is not None
    draft_files = source_status.recovery_draft.get("files")
    if not isinstance(draft_files, list) or len(draft_files) != 1:
        raise SystemExit("recovery draft manifest is unavailable")
    workspace = runtime.runs.backend.open(recovered_id)
    assignment = json.loads(workspace.assignment_path.read_text("utf-8"))
    recovery_assignment = assignment.get("recovery_draft")
    draft_item = draft_files[0]
    recovered_draft_path = Path(workspace.root, "recovery-draft/result.json")
    recovered_draft_bytes = recovered_draft_path.read_bytes()
    failure_evidence = json.loads((root / "failure-evidence.json").read_text("utf-8"))
    crash_receipt = json.loads(
        (root / "crash-worker-receipt.json").read_text("utf-8")
    )
    try:
        recovered_draft = json.loads(recovered_draft_bytes)
        draft_assumptions = recovered_draft["handoff"]["assumptions"]
        draft_marker = draft_assumptions[0]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit("recovery draft has no unique continuation marker") from error
    if (
        not isinstance(draft_marker, str)
        or len(draft_assumptions) != 1
        or hashlib.sha256(draft_marker.encode("utf-8")).hexdigest()
        != failure_evidence.get("draft_marker_sha256")
    ):
        raise SystemExit("recovery draft continuation marker is invalid")
    recovered_draft_matches_manifest = (
        draft_item.get("relative_path") == "result.json"
        and draft_item.get("size_bytes") == len(recovered_draft_bytes)
        and draft_item.get("sha256")
        == hashlib.sha256(recovered_draft_bytes).hexdigest()
    )
    draft_bounded = (
        len(draft_files) <= compiled.spec.limits.max_files
        and len(recovered_draft_bytes) <= compiled.spec.limits.max_output_bytes
    )
    recovery_draft_non_evidence = (
        isinstance(recovery_assignment, dict)
        and recovery_assignment.get("scientific_evidence") is False
        and recovered_draft_path.is_file()
        and not os.access(recovered_draft_path, os.W_OK)
        and recovered_draft_matches_manifest
    )
    if recovered_status.output_ref is None:
        raise SystemExit("completed recovery Run has no sealed output")
    output = runtime.artifacts.verify(recovered_status.output_ref)
    output_payload = json.loads(runtime.artifacts.read(recovered_status.output_ref))
    result_schema = json.loads(
        Path(workspace.root, "schema/result.schema.json").read_text("utf-8")
    )
    try:
        schema_probe = result_schema["properties"]["payload"]["properties"][
            "schema_probe"
        ]["const"]
    except (KeyError, TypeError) as error:
        raise SystemExit("test result Schema has no unique read probe") from error
    source_bytes = runtime.artifacts.read(recovered_status.inputs[0].artifact_ref)
    schema_probe_is_exclusive = (
        isinstance(schema_probe, str)
        and schema_probe.encode("utf-8") not in source_bytes
        and schema_probe.encode("utf-8") not in recovered_draft_bytes
        and schema_probe not in assignment.get("instruction", "")
    )
    exact_input_parents = output.parent_refs == tuple(
        item.artifact_ref for item in recovered_status.inputs
    )
    invocation = _verify_launcher_receipt(
        root,
        receipt_name=control["recovery_launcher_receipt"],
        agent_type=control["recovery_agent_type"],
        operation_id=AUTHOR_OPERATION,
        run=recovered,
        expected_memory_limit_mib=control["launcher_memory_limit_mib"],
        expected_external_sandbox_debug=control[
            "launcher_externally_sandboxed_debug"
        ],
    )
    active = router.call_tool("run_list", {})
    no_active_runs = all(
        item["state"] not in {"queued", "running"} for item in active["runs"]
    )
    before_limit = router.call_tool("run_list", {})
    limit_request = {
        "name": "recovery_attempt_limit_probe",
        "operation_id": AUTHOR_OPERATION,
        "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
        "instruction": AUTHOR_INSTRUCTION,
        "resume_from": control["recovery_source_run_name"],
    }
    limit_preflight = router.call_tool("operation_preflight", limit_request)
    try:
        router.call_tool("operation_invoke", limit_request)
    except Exception:
        limit_invoke_rejected = True
    else:
        limit_invoke_rejected = False
    try:
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="run",
            name=limit_request["name"],
        )
    except Exception:
        limit_binding_absent = True
    else:
        limit_binding_absent = False
    recovery_attempt_limit_enforced = (
        limit_preflight.get("admissible") is False
        and limit_preflight.get("reason_code") == "recovery_source_unavailable"
        and limit_invoke_rejected
        and limit_binding_absent
        and router.call_tool("run_list", {}) == before_limit
    )
    evidence = {
        "crash_worker_called_registered_tool": (
            crash_receipt.get("domain_tool_called") is True
            and "worker_csv_summarize" in runtime.runs.successful_tools(source_id)
        ),
        "crash_worker_exited_before_submit": (
            crash_receipt.get("exit_code") == 73
            and crash_receipt.get("submitted") is False
        ),
        "failed_draft_not_scientific_evidence": (
            failure_evidence.get("draft_registered_as_artifact") is False
            and failure_evidence.get("output_ref_absent") is True
            and recovery_draft_non_evidence
        ),
        "failed_source_remains_failed": source_status.state == "failed",
        "new_run_completed": recovered_status.state == "completed",
        "new_run_revalidated_with_registered_tool": (
            "worker_csv_summarize" in runtime.runs.successful_tools(recovered_id)
        ),
        "new_run_used_recovery_draft": (
            recovered_status.signal is not None
            and draft_marker in recovered_status.signal.assumptions
            and crash_receipt.get("draft_marker_sha256")
            == hashlib.sha256(draft_marker.encode("utf-8")).hexdigest()
        ),
        "new_run_read_output_schema_before_first_submit": (
            schema_probe_is_exclusive
            and output_payload.get("schema_probe") == schema_probe
            and output_rejected_count == 0
        ),
        "new_run_has_distinct_identity": recovered_id != source_id,
        "new_run_resumes_exact_source": (
            recovered_row["resume_from_run_id"] == source_id
        ),
        "no_active_runs_after_restart": no_active_runs,
        "output_has_exact_input_parents": exact_input_parents,
        "recovery_draft_within_file_and_byte_limits": draft_bounded,
        "recovery_launcher_receipt_verified": bool(invocation),
        "recovery_attempt_limit_rejected_without_run": (
            recovery_attempt_limit_enforced
        ),
        "recovery_scope": "root plus one recovery; max_attempts=2 enforced",
        "same_operation_instruction_and_inputs": True,
        "schema_version": 1,
        "wrong_input_preflight_rejected_without_run": True,
    }
    if not all(
        value is True
        for key, value in evidence.items()
        if key not in {"recovery_scope", "schema_version"}
    ):
        raise SystemExit(f"recovery evidence is incomplete: {evidence}")
    (root / "final-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    print(json.dumps(evidence, sort_keys=True))


def queue_review(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    router = _root(runtime, control["instance_id"])
    author = router.call_tool("run_status", {"name": control["author_run_name"]})
    if author["state"] != "completed":
        raise SystemExit(f"author Run is not complete: {author['state']}")
    observation_name = author["output_artifact_name"]
    invoked = router.call_tool(
        "operation_invoke",
        {
            "name": "reviewer",
            "operation_id": REVIEW_OPERATION,
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]},
                {"port": "csv_observation", "artifact_names": [observation_name]},
            ],
            "instruction": "Independently review the exact completed observation.",
        },
    )
    control.update(
        {
            "observation_name": observation_name,
            "review_run_name": "reviewer",
            "review_agent_type": invoked["result"]["agent_type"],
        }
    )
    _write_control(root, control)
    _write_dispatch(
        root,
        label="reviewer",
        operation_id=REVIEW_OPERATION,
        python_path=root / "pythonpath",
    )


def status(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    router = _root(runtime, control["instance_id"])
    author = router.call_tool("run_status", {"name": control["author_run_name"]})
    review = router.call_tool("run_status", {"name": control["review_run_name"]})
    if author["state"] != "completed" or review["state"] != "completed":
        raise SystemExit("author-reviewer probe is incomplete")
    author_invocation = _verify_launcher_receipt(
        root,
        receipt_name=control["author_launcher_receipt"],
        agent_type=control["author_agent_type"],
        operation_id=AUTHOR_OPERATION,
        run=author,
        expected_memory_limit_mib=control["launcher_memory_limit_mib"],
        expected_external_sandbox_debug=control[
            "launcher_externally_sandboxed_debug"
        ],
    )
    review_invocation = _verify_launcher_receipt(
        root,
        receipt_name=control["review_launcher_receipt"],
        agent_type=control["review_agent_type"],
        operation_id=REVIEW_OPERATION,
        run=review,
        expected_memory_limit_mib=control["launcher_memory_limit_mib"],
        expected_external_sandbox_debug=control[
            "launcher_externally_sandboxed_debug"
        ],
    )
    if author_invocation == review_invocation:
        raise SystemExit("author and reviewer reused one launcher invocation")
    observation_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="artifact",
            name=control["observation_name"],
        )
    ).ref
    review_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="artifact",
            name=review["output_artifact_name"],
        )
    ).ref
    exact = runtime.runs.is_exact_reviewer_output(
        review_ref,
        reviewer_operation=REVIEW_OPERATION,
        reviewer_input_port="csv_observation",
        accepted_verdicts=("pass",),
        subject_ref=observation_ref,
    )
    evidence = {
        "author_state": author["state"],
        "review_state": review["state"],
        "author_agent_type": control["author_agent_type"],
        "review_agent_type": control["review_agent_type"],
        "author_registered_tool_succeeded": "worker_csv_summarize"
        in runtime.runs.successful_tools(
            runtime.scheduler_bindings.resolve(
                instance=control["instance_id"],
                namespace="run",
                name=control["author_run_name"],
            )
        ),
        "review_is_exact_and_passing": exact,
        "review_has_exact_subject_parent": observation_ref
        in runtime.artifacts.get_by_id(review_ref.artifact_id).parent_refs,
        "launcher_receipts_verified": True,
        "distinct_launcher_invocations": True,
        "worker_transport": "independent_codex_exec",
    }
    if not all(
        evidence[key]
        for key in (
            "author_registered_tool_succeeded",
            "review_is_exact_and_passing",
            "review_has_exact_subject_parent",
        )
    ):
        raise SystemExit("author-reviewer evidence is incomplete")
    (root / "final-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    print(json.dumps(evidence, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "queue-review",
            "simulate-failure-and-queue-recovery",
            "status",
            "status-recovery",
        ),
    )
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    {
        "prepare": prepare,
        "queue-review": queue_review,
        "simulate-failure-and-queue-recovery": (
            simulate_failure_and_queue_recovery
        ),
        "status": status,
        "status-recovery": status_recovery,
    }[args.action](root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
