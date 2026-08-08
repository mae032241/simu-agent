from __future__ import annotations

import os
import json
import sqlite3
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_worker import WorkerMCPRouter
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import ApprovalOption, LocalIdentityRef
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.tasks import (
    RoleOutputContract,
    TaskStateConflict,
    _decode_agent_task,
)


class _CompletedProcess:
    returncode = 0
    stdout = b"Figure 4 diffusion profile\n"
    stderr = b""


def _routers(tmp_path: Path) -> tuple[RootMCPRouter, object]:
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
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
        )
    )
    return root, runtime


def _schedule(root: RootMCPRouter, *, dependencies: list[str] | None = None) -> str:
    name = f"task_{len(root.facade.bindings.list(instance='test', namespace='task')) + 1}"
    result = root.call_tool(
        "task_schedule",
        {
            "name": name,
            "role": "critic",
            "instruction": "Review the bounded scientific claim.",
            "inputs": [],
            "dependency_names": dependencies or [],
            "max_attempts": 2,
        },
    )
    assert result["name"] == name
    return name


def _claim(root: RootMCPRouter, runtime: object, task_name: str) -> WorkerMCPRouter:
    root.call_tool(
        "task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60}
    )
    worker = WorkerMCPRouter(runtime.tasks, worker_id="critic")
    assert worker.call_tool("worker_claim_task", {}) == {"state": "claimed"}
    return worker


def _task_id(root: RootMCPRouter, task_name: str) -> str:
    return root.facade.bindings.resolve(
        instance="test", namespace="task", name=task_name
    )


def _critic_output(
    *,
    verdict: str = "pass",
    summary: str = "Bounded review complete.",
    detail: str | None = None,
    assumptions: list[str] | None = None,
    missing_inputs: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "reviews": [],
    }
    if detail is not None:
        payload["global_issues"] = [detail]
    return {
        "schema_version": 1,
        "handoff": {
            "verdict": verdict,
            "summary": summary,
            "assumptions": assumptions or [],
            "missing_inputs": missing_inputs or [],
            "next_actions": next_actions or [],
        },
        "payload": payload,
    }


def _envelope(
    payload: dict[str, object],
    *,
    verdict: str = "pass",
    summary: str = "Role output complete.",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "handoff": {"verdict": verdict, "summary": summary},
        "payload": payload,
    }


def _approve_foundation(runtime: object, reference: object) -> None:
    launch = runtime.approvals.create_request(
        approval_id="foundation_review",
        kind="scientific_foundation",
        subject_refs=(reference,),
        question="Is this exact scientific foundation acceptable?",
        options=(
            ApprovalOption(
                option_id="approve",
                label="Approve",
                description="Approve this exact foundation.",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="revise",
                label="Revise",
                description="Request a scientific revision.",
                requires_rationale=True,
            ),
        ),
        requested_by=runtime.intake.creator,
        idempotency_key="foundation-review",
    )
    token = parse_qs(urlparse(launch.review_path).query)["token"][0]
    review = runtime.approvals.review("foundation_review", access_token=token)
    runtime.approvals.record_ui_decision(
        approval_id="foundation_review",
        access_token=token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="approve",
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="fixture_user", display_name="Fixture user"
        ),
        ui_session_id="fixture_foundation_review",
    )


def test_task_requires_exact_human_approval_for_scientific_foundation(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    foundation = runtime.artifacts.register(
        canonical_json({"objective": "Reproduce one bounded target."}),
        ArtifactRegistration(
            kind="scientific_foundation",
            schema_id="fixture.scientific-foundation",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.intake.creator,
        ),
        idempotency_key="fixture-foundation",
    )
    runtime.scheduler_bindings.bind(
        instance="test",
        namespace="artifact",
        name="scientific_foundation",
        object_id=foundation.artifact_id,
    )
    arguments = {
        "name": "foundation_critic",
        "role": "critic",
        "instruction": "Review the exact approved foundation.",
        "inputs": [
            {
                "source_name": "scientific_foundation",
                "artifact_name": "scientific_foundation",
            }
        ],
    }

    with pytest.raises(Exception, match="exact approved human review"):
        root.call_tool("task_schedule", arguments)

    _approve_foundation(runtime, foundation.ref)
    scheduled = root.call_tool("task_schedule", arguments)
    assert scheduled["name"] == "foundation_critic"


def test_scientific_readiness_exposes_inventory_without_a_fixed_stage(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    foundation = runtime.artifacts.register(
        canonical_json({"objective": "Reproduce one bounded target."}),
        ArtifactRegistration(
            kind="scientific_foundation",
            schema_id="fixture.scientific-foundation",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.intake.creator,
        ),
        idempotency_key="fixture-readiness-foundation",
    )
    runtime.scheduler_bindings.bind(
        instance="test",
        namespace="artifact",
        name="scientific_foundation",
        object_id=foundation.artifact_id,
    )

    blocked = root.call_tool("scientific_readiness", {})
    assert blocked["objects"][0]["qualification"] == "human_review_required"
    assert "scientific_foundation" not in blocked["readiness"]["available_artifacts"]
    assert blocked["available_actions"] == ["evidence_extractor"]
    assert "task_id" not in json.dumps(blocked)
    assert "artifact_id" not in json.dumps(blocked)

    _approve_foundation(runtime, foundation.ref)
    approved = root.call_tool("scientific_readiness", {})
    assert approved["objects"][0]["qualification"] == "qualified"
    assert "scientific_foundation" in approved["readiness"]["available_artifacts"]
    assert "evidence_auditor" in approved["available_actions"]
    assert "ideator" not in approved["available_actions"]


def test_completed_task_exposes_only_bounded_scheduler_signal(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    worker = _claim(root, runtime, task_name)

    worker.call_tool(
        "worker_finalize",
        {
            "content": _critic_output(
                verdict="revise",
                summary="The diffusion-tail parameter has no admitted source.",
                detail="large scientific report",
                assumptions=["The digitized profile is representative."],
                missing_inputs=["ZnVCD activation energy"],
                next_actions=["schedule_evidence_revision"],
            ),
        },
    )

    status = root.call_tool("task_status", {"name": task_name})
    assert status["state"] == "completed"
    assert status["scheduler_signal"] == {
        "schema_version": 1,
        "verdict": "revise",
        "summary": "The diffusion-tail parameter has no admitted source.",
        "assumptions": ["The digitized profile is representative."],
        "missing_inputs": ["ZnVCD activation energy"],
        "next_actions": ["schedule_evidence_revision"],
    }
    assert "full_review" not in str(status)

    output = runtime.artifacts.get_by_id(
        root.facade.bindings.resolve(
            instance="test", namespace="artifact", name=status["output_artifact_name"]
        )
    )
    assert b"large scientific report" in runtime.artifacts.read(output.ref)


def test_lifecycle_events_persist_across_router_restart_and_report_changes(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    first = root.call_tool("lifecycle_events", {})
    assert first["events"] == [
        {
            "object_type": "task",
            "name": task_name,
            "previous_state": None,
            "state": "created",
            "observed_at": first["events"][0]["observed_at"],
        }
    ]
    assert root.call_tool("lifecycle_events", {}) == {"events": []}

    restarted = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance="test",
        )
    )
    assert restarted.call_tool("lifecycle_events", {}) == {"events": []}

    worker = _claim(restarted, runtime, task_name)
    claimed = restarted.call_tool("lifecycle_events", {})
    assert claimed["events"][0]["previous_state"] == "created"
    assert claimed["events"][0]["state"] == "claimed"
    worker.call_tool(
        "worker_finalize",
        {
            "content": _critic_output(),
        },
    )
    completed = restarted.call_tool("lifecycle_events", {})
    assert completed["events"][0]["previous_state"] == "claimed"
    assert completed["events"][0]["state"] == "completed"


def test_cognitive_worker_derives_scheduler_signal_from_output(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    worker = _claim(root, runtime, task_name)

    assert worker.call_tool(
        "worker_finalize",
        {"content": _critic_output(summary="Derived once from the handoff.")},
    ) == {"state": "completed"}
    signal = root.call_tool("task_status", {"name": task_name})["scheduler_signal"]
    assert signal["summary"] == "Derived once from the handoff."


def test_worker_rejects_naked_role_payload(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    worker = _claim(root, runtime, _schedule(root))

    result = worker.call_tool(
        "worker_validate_output",
        {"content": {"schema_version": 1, "reviews": []}},
    )

    assert result["valid"] is False
    assert {item["path"] for item in result["errors"]} >= {"handoff", "payload"}


def test_retired_task_output_contract_cannot_be_dispatched(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    current = runtime.tasks.output_contract("critic")
    runtime.tasks.role_output_contracts["critic"] = RoleOutputContract(
        kind=current.kind,
        format=current.format,
        schema_id="scidiscovery.critic-review.v2",
        validator=current.validator,
        json_schema=current.json_schema,
    )

    with pytest.raises(TaskStateConflict, match="contract is retired"):
        runtime.tasks.prepare_dispatch(_task_id(root, task_name), ttl_seconds=60)


def test_worker_materializes_isolated_json_workspace_and_finalizes_file(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    source_path = runtime.project_root / "scientific-foundation.json"
    source_path.write_text(
        json.dumps({"objective": "Audit the bounded diffusion claim."}),
        encoding="utf-8",
    )
    root.call_tool(
        "artifact_ingest_file",
        {
            "name": "scientific_foundation",
            "relative_path": source_path.name,
            "media_type": "application/json",
        },
    )
    task_name = "workspace_critic"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "critic",
            "instruction": "Review the supplied scientific foundation.",
            "inputs": [
                {
                    "source_name": "scientific_foundation",
                    "artifact_name": "scientific_foundation",
                    "exposure": "full",
                }
            ],
        },
    )
    worker = _claim(root, runtime, task_name)

    workspace = worker.call_tool("worker_materialize_assignment", {})
    root_path = Path(workspace["workspace_path"])
    assignment_path = Path(workspace["assignment_path"])
    output_path = Path(workspace["output_path"])
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))

    assert assignment["role"] == "critic"
    assert assignment["instruction"] == "Review the supplied scientific foundation."
    assert assignment["output"]["relative_path"] == "output/result.json"
    assert assignment["output"]["schema_relative_path"] == "schema/output.schema.json"
    assert assignment["output"]["protocol"] == "scidiscovery.role-result-envelope.v1"
    assert assignment["inputs"] == [
        {
            "access_modes": ["read_text", "stage_file", "read_table"],
            "exposure": "full",
            "media_type": "application/json",
            "relative_path": "inputs/scientific_foundation.json",
            "size_bytes": source_path.stat().st_size,
            "source_name": "scientific_foundation",
        }
    ]
    assert "task_id" not in assignment_path.read_text(encoding="utf-8")
    assert "artifact" not in assignment_path.read_text(encoding="utf-8").lower()
    input_path = root_path / assignment["inputs"][0]["relative_path"]
    assert json.loads(input_path.read_text(encoding="utf-8"))["objective"].startswith(
        "Audit"
    )
    assert stat.S_IMODE(input_path.stat().st_mode) == 0o440

    output_path.write_bytes(
        canonical_json(_critic_output(summary="File exchange review complete."))
    )
    validation = worker.call_tool("worker_validate_output_file", {})
    assert validation["valid"] is True
    assert validation["size_bytes"] == 66
    assert output_path.stat().st_size > validation["size_bytes"]
    assert validation["errors"] == []
    assert worker.call_tool(
        "worker_finalize_file",
        {},
    ) == {"state": "completed"}
    assert root.call_tool("task_status", {"name": task_name})["state"] == "completed"
    assert not root_path.exists()


def test_worker_output_file_is_revalidated_and_rejects_symlinks(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    worker = _claim(root, runtime, task_name)
    workspace = worker.call_tool("worker_materialize_assignment", {})
    output_path = Path(workspace["output_path"])

    output_path.write_text("{}", encoding="utf-8")
    rejected = worker.call_tool("worker_validate_output_file", {})
    assert rejected["valid"] is False
    assert rejected["errors"]

    external = tmp_path / "external.json"
    external.write_text(json.dumps(_critic_output()), encoding="utf-8")
    output_path.unlink()
    output_path.symlink_to(external)
    with pytest.raises(Exception, match="regular file"):
        worker.call_tool("worker_validate_output_file", {})


def test_failed_dependency_is_reported_as_blocked(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    upstream = _schedule(root)
    downstream = _schedule(root, dependencies=[upstream])

    observed = root.call_tool("task_status", {"name": upstream})
    root.call_tool(
        "task_record_failure",
        {
            "name": upstream,
            "reason": "required evidence is absent",
            "timed_out": False,
            "expected_state": observed["state"],
            "expected_last_activity_at": observed["last_activity_at"],
        },
    )

    status = root.call_tool("task_status", {"name": downstream})
    assert status["state"] == "created"
    assert status["readiness"] == "blocked_by_dependency"
    assert status["blocking_names"] == [upstream]
    assert downstream not in root.call_tool("task_ready", {})["task_names"]
    with pytest.raises(Exception, match="dependency is terminal"):
        root.call_tool(
            "task_prepare_dispatch", {"name": downstream, "ttl_seconds": 60}
        )


def test_failed_task_can_retry_within_attempt_budget(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    _claim(root, runtime, task_name)
    observed = root.call_tool("task_status", {"name": task_name})
    root.call_tool(
        "task_record_failure",
        {
            "name": task_name,
            "reason": "transient worker failure",
            "timed_out": False,
            "expected_state": observed["state"],
            "expected_last_activity_at": observed["last_activity_at"],
        },
    )

    retried = root.call_tool("task_retry", {"name": task_name})
    assert retried["name"] == task_name
    assert retried["state"] == "created"
    assert retried["attempt"] == 1
    assert task_name in root.call_tool("task_ready", {})["task_names"]

    _claim(root, runtime, task_name)
    observed = root.call_tool("task_status", {"name": task_name})
    root.call_tool(
        "task_record_failure",
        {
            "name": task_name,
            "reason": "second worker failure",
            "timed_out": False,
            "expected_state": observed["state"],
            "expected_last_activity_at": observed["last_activity_at"],
        },
    )
    with pytest.raises(Exception, match="attempt budget is exhausted"):
        root.call_tool("task_retry", {"name": task_name})


def test_dispatch_deadline_converges_abandoned_task_to_timed_out(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    task_name = "deadline_task"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "critic",
            "instruction": "Review one bounded claim.",
            "inputs": [],
            "timeout_seconds": 1,
            "max_attempts": 2,
        },
    )
    root.call_tool("task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60})
    task_id = _task_id(root, task_name)

    with sqlite3.connect(runtime.tasks.database_path) as connection:
        connection.execute(
            "UPDATE tasks SET deadline_at = ? WHERE task_id = ?",
            ("1970-01-01T00:00:00.000000Z", task_id),
        )

    status = root.call_tool("task_status", {"name": task_name})
    assert status["state"] == "timed_out"
    assert status["reason"] == "worker attempt exceeded its dispatch deadline"
    with sqlite3.connect(runtime.tasks.database_path) as connection:
        instance_state = connection.execute(
            "SELECT state FROM assignment_instances WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
    assert instance_state == "timed_out"
    assert root.call_tool("task_retry", {"name": task_name})["state"] == "created"


def test_deck_author_output_is_validated_before_artifact_registration(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    task_name = "deck_author"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "tcad_deck_author",
            "instruction": "Author a deployment-smoke project.",
            "inputs": [],
        },
    )
    root.call_tool(
        "task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60}
    )
    worker = WorkerMCPRouter(runtime.tasks, worker_id="tcad_deck_author")
    worker.call_tool("worker_claim_task", {})
    assignment = worker.call_tool("worker_get_assignment", {})
    schema = assignment["output"]["json_schema"]
    assert schema["title"] == "RoleResultEnvelope[DeckProjectDraft]"
    assert set(schema["required"]) == {"schema_version", "handoff", "payload"}
    assert "realization_manifest" in json.dumps(schema)

    invalid = worker.call_tool(
        "worker_validate_output",
        {"content": _envelope({"files": []})},
    )
    assert invalid["valid"] is False
    assert any("realization_manifest" in item["message"] for item in invalid["errors"])

    rejected = worker.call_tool(
        "worker_finalize",
        {"content": _envelope({"files": []})},
    )
    assert rejected["state"] == "rejected"
    assert any(
        "realization_manifest" in item["message"] for item in rejected["errors"]
    )

    worker.call_tool(
        "worker_finalize",
        {
            "content": _envelope({
                "schema_version": 1,
                "tool_profile": "deployment_smoke",
                "files": [{"relative_path": "run.sh", "content": "#!/bin/sh\ntrue\n"}],
                "entrypoint": "run.sh",
                "arguments": [],
                "expected_outputs": [],
                "parameter_bindings": [],
                "runtime_assertions": [],
                "realization_manifest": [
                    {
                        "requirement_key": "smoke_entrypoint",
                        "category": "numerical_protocol",
                        "requirement": "Run the frozen shell smoke entrypoint.",
                        "evidence_class": "test_fixture",
                        "evidence_source": "deployment smoke contract",
                        "evidence_locator": "run.sh",
                        "rationale": "The fixture verifies project packaging only.",
                        "implementation_status": "implemented",
                        "relative_path": "run.sh",
                        "locator": "true",
                        "verification_mode": "static_review",
                        "expected_output_name": None,
                    }
                ],
                "resource_limits": {
                    "wall_time_seconds": 10,
                    "cpu_time_seconds": 10,
                    "max_memory_bytes": 1048576,
                    "max_output_bytes": 1048576,
                    "max_processes": 2,
                },
            }, summary="Project authored."),
        },
    )
    status = root.call_tool("task_status", {"name": task_name})
    output = runtime.artifacts.get_by_id(
        root.facade.bindings.resolve(
            instance="test", namespace="artifact", name=status["output_artifact_name"]
        )
    )
    assert output.schema_id == "tcad.deck-project.v1"


def test_worker_can_read_table_and_stage_binary_task_inputs(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    project = runtime.project_root
    (project / "curve.csv").write_text(
        "bias_v,current_a\n-0.1,1e-9\n0.0,2e-9\n0.1,4e-9\n",
        encoding="utf-8",
    )
    (project / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    curve = root.call_tool(
        "artifact_ingest_file",
        {"name": "curve.csv", "relative_path": "curve.csv", "media_type": "text/csv"},
    )
    plot = root.call_tool(
        "artifact_ingest_file",
        {"name": "plot.png", "relative_path": "plot.png", "media_type": "image/png"},
    )
    task_name = "input_reader"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "critic",
            "instruction": "Inspect the supplied curve and image.",
            "inputs": [
                {"source_name": "curve", "artifact_name": curve["name"]},
                {"source_name": "plot", "artifact_name": plot["name"]},
            ],
        },
    )
    worker = _claim(root, runtime, task_name)

    table = worker.call_tool(
        "worker_read_table",
        {"name": "curve", "start_row": 1, "max_rows": 1},
    )
    assert table["columns"] == ["bias_v", "current_a"]
    assert table["rows"] == [["0.0", "2e-9"]]
    assert table["next_row"] == 2

    profile = worker.call_tool("worker_profile_input", {"name": "curve"})
    assert profile["profile_type"] == "table"
    assert profile["row_count"] == 3
    assert profile["column_count"] == 2
    assert profile["columns"] == [
        {
            "name": "bias_v",
            "missing_count": 0,
            "numeric_count": 3,
            "non_finite_count": 0,
            "minimum": -0.1,
            "maximum": 0.1,
        },
        {
            "name": "current_a",
            "missing_count": 0,
            "numeric_count": 3,
            "non_finite_count": 0,
            "minimum": 1e-09,
            "maximum": 4e-09,
        },
    ]

    worker.call_tool(
        "worker_stage_input",
        {"name": "curve"},
    )

    staged = worker.call_tool(
        "worker_stage_input",
        {"name": "plot"},
    )
    assert staged["access"] == "read_only"
    assert Path(staged["local_path"]).read_bytes().startswith(b"\x89PNG")

    analysis = worker.call_tool(
        "worker_run_analysis",
        {
            "code": (
                "import csv\n"
                    "with open('/inputs/curve', newline='') as stream:\n"
                "    rows = list(csv.DictReader(stream))\n"
                "print(sum(float(row['current_a']) for row in rows))\n"
            ),
            "timeout_seconds": 10,
        },
    )
    assert analysis["exit_code"] == 0
    assert float(analysis["stdout"].strip()) == pytest.approx(7e-9)
    assert analysis["input_directory"] == "/inputs"


def test_task_local_source_alias_is_validated_before_finalize(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    (runtime.project_root / "source.txt").write_text("frozen evidence", encoding="utf-8")
    artifact = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "control.execution.output.profile",
            "relative_path": "source.txt",
            "media_type": "text/plain",
        },
    )
    task_name = "source_alias_validation"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "critic",
            "instruction": "Audit one supplied profile.",
            "inputs": [
                {
                    "source_name": "simulation_profile",
                    "artifact_name": artifact["name"],
                }
            ],
        },
    )
    worker = _claim(root, runtime, task_name)
    assert worker.call_tool("worker_list_inputs", {})["inputs"][0]["name"] == "simulation_profile"

    wrong_payload = {
        "schema_version": 1,
        "reviews": [],
        "evidence": [
            {
                "source_key": "control.execution.output.profile",
                "source_type": "runtime_output",
                "locator": "full profile",
            }
        ],
    }
    wrong = _envelope(
        wrong_payload, summary="The supplied profile was inspected."
    )
    checked = worker.call_tool("worker_validate_output", {"content": wrong})
    assert checked == {
        "valid": False,
        "size_bytes": None,
        "errors": [
            {
                "path": "$.payload.evidence[0].source_key",
                "message": (
                    "unknown task-local input source: "
                    "control.execution.output.profile"
                ),
                "type": "value_error.source_binding",
            }
        ],
    }
    assert root.call_tool("task_status", {"name": task_name})["last_activity"] == "output_rejected"
    rejected = worker.call_tool(
        "worker_finalize",
        {
            "content": wrong,
        },
    )
    assert rejected["state"] == "rejected"
    assert rejected["errors"] == checked["errors"]

    correct_payload = dict(wrong_payload)
    correct_payload["evidence"] = [
        {
            "source_key": "simulation_profile",
            "source_type": "runtime_output",
            "locator": "full profile",
        }
    ]
    correct = _envelope(
        correct_payload, summary="The supplied profile was inspected."
    )
    assert worker.call_tool("worker_validate_output", {"content": correct})["valid"]
    worker.call_tool(
        "worker_finalize",
        {
            "content": correct,
        },
    )
    status = root.call_tool("task_status", {"name": task_name})
    output_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="artifact", name=status["output_artifact_name"]
    )
    output = runtime.artifacts.get_by_id(output_id)
    input_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="artifact", name=artifact["name"]
    )
    assert any(parent.artifact_id == input_id for parent in output.parent_refs)


def test_worker_extracts_bounded_pdf_text_without_exposing_control_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, runtime = _routers(tmp_path)
    (runtime.project_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture")
    paper = root.call_tool(
        "artifact_ingest_file",
        {"name": "paper.pdf", "relative_path": "paper.pdf", "media_type": "application/pdf"},
    )
    task_name = "paper_extract"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "evidence_extractor",
            "instruction": "Extract the Fig. 4 evidence.",
            "inputs": [
                {"source_name": "paper", "artifact_name": paper["name"]},
            ],
        },
    )
    root.call_tool(
        "task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60}
    )
    worker = WorkerMCPRouter(runtime.tasks, worker_id="evidence_extractor")
    worker.call_tool("worker_claim_task", {})
    monkeypatch.setattr(
        "scidiscovery.artifact_agent.interfaces.mcp_worker.subprocess.run",
        lambda *args, **kwargs: _CompletedProcess(),
    )

    assignment = worker.call_tool("worker_get_assignment", {})
    assert assignment["inputs"][0]["access_modes"] == [
        "stage_file",
        "extract_pdf_text",
    ]
    extracted = worker.call_tool(
        "worker_extract_pdf_text",
        {
            "name": "paper",
            "first_page": 4,
            "last_page": 4,
            "max_chars": 12,
        },
    )
    assert extracted["content"] == "Figure 4 dif"
    assert extracted["truncated"] is True
    assert "artifact" not in str(extracted).lower()


def test_worker_heartbeat_extends_claim_lease_without_exceeding_budget(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    task_name = "heartbeat_task"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "critic",
            "instruction": "Review one bounded claim.",
            "inputs": [],
            "timeout_seconds": 1200,
        },
    )
    worker = _claim(root, runtime, task_name)
    task_id = _task_id(root, task_name)
    short_lease = (
        datetime.now(timezone.utc) + timedelta(seconds=5)
    ).isoformat(timespec="microseconds").replace("+00:00", "Z")
    with sqlite3.connect(runtime.tasks.database_path) as connection:
        before = connection.execute(
            "SELECT deadline_at, absolute_deadline_at FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        connection.execute(
            "UPDATE tasks SET deadline_at = ? WHERE task_id = ?",
            (short_lease, task_id),
        )

    heartbeat = worker.call_tool("worker_heartbeat", {})
    assert heartbeat["state"] == "claimed"
    assert datetime.fromisoformat(heartbeat["lease_deadline_at"].replace("Z", "+00:00"))
    assert heartbeat["lease_deadline_at"] <= heartbeat["absolute_deadline_at"]
    assert heartbeat["lease_deadline_at"] > short_lease
    assert before[1] == heartbeat["absolute_deadline_at"]


def test_worker_heartbeat_cannot_revive_an_expired_lease(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    worker = _claim(root, runtime, task_name)
    task_id = _task_id(root, task_name)
    with sqlite3.connect(runtime.tasks.database_path) as connection:
        connection.execute(
            "UPDATE tasks SET deadline_at = ? WHERE task_id = ?",
            ("2000-01-01T00:00:00.000000Z", task_id),
        )

    with pytest.raises(Exception, match="active claimed attempt"):
        worker.call_tool("worker_heartbeat", {})
    assert root.call_tool("task_status", {"name": task_name})["state"] == "timed_out"


def test_task_recovery_list_and_worker_activity_are_bounded(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    created = root.call_tool("task_list", {"state": "created", "limit": 1})
    assert [item["name"] for item in created["tasks"]] == [task_name]
    assert created["tasks"][0]["last_activity"] is None

    worker = _claim(root, runtime, task_name)
    claimed = root.call_tool("task_status", {"name": task_name})
    assert claimed["last_activity"] == "claimed"
    assert claimed["lease_deadline_at"]
    assert claimed["absolute_deadline_at"]

    worker.call_tool("worker_get_assignment", {})
    active = root.call_tool("task_list", {"state": "claimed", "limit": 10})
    assert active["tasks"][0]["last_activity"] == "assignment_read"
    assert active["tasks"][0]["last_activity_at"]

    worker.call_tool(
        "worker_finalize",
        {
            "content": _critic_output(),
        },
    )
    completed = root.call_tool("task_list", {"state": "completed", "limit": 1})
    assert completed["tasks"][0]["name"] == task_name
    assert completed["tasks"][0]["last_activity"] == "finalized"


def test_task_status_reports_bounded_performance_breakdown(tmp_path: Path) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    worker = _claim(root, runtime, task_name)

    worker.call_tool("worker_get_assignment", {})
    worker.call_tool(
        "worker_run_analysis",
        {"code": "print('ok')", "timeout_seconds": 5},
    )
    worker.call_tool(
        "worker_finalize",
        {
            "content": _critic_output(),
        },
    )

    performance = root.call_tool("task_status", {"name": task_name})["performance"]
    assert performance["input_count"] == 0
    assert performance["input_bytes"] == 0
    assert performance["output_bytes"] > 0
    assert performance["phase_counts"]["assignment_read"] == 1
    assert performance["phase_counts"]["deterministic_analysis_completed"] == 1
    assert performance["phase_counts"]["finalized"] == 1
    assert performance["schema_rejections"] == 0
    assert performance["durations_seconds"]["dispatch_to_claim"] >= 0
    assert performance["durations_seconds"]["claim_to_finalize"] >= 0


def test_completed_output_is_available_to_downstream_without_status_read(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    upstream = _schedule(root)
    worker = _claim(root, runtime, upstream)
    worker.call_tool(
        "worker_finalize",
        {
            "content": _critic_output(summary="Upstream review complete."),
        },
    )

    downstream = root.call_tool(
        "task_schedule",
        {
            "name": "downstream_without_status_read",
            "role": "critic",
            "instruction": "Review the upstream result.",
            "inputs": [
                {"source_name": "upstream_review", "artifact_name": f"{upstream}.output"},
            ],
            "dependency_names": [upstream],
        },
    )
    assert downstream["state"] == "created"
    assert downstream["readiness"] == "ready"

    downstream_worker = _claim(
        root, runtime, "downstream_without_status_read"
    )
    assignment = downstream_worker.call_tool("worker_get_assignment", {})
    assert assignment["inputs"][0]["handoff"] is None
    assert root.call_tool("task_status", {"name": upstream})["scheduler_signal"][
        "summary"
    ] == "Upstream review complete."


def test_scheduler_failure_write_rejects_a_concurrent_worker_claim(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    task_name = _schedule(root)
    root.call_tool(
        "task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60}
    )
    stale = root.call_tool("task_status", {"name": task_name})

    worker = WorkerMCPRouter(runtime.tasks, worker_id="critic")
    worker.call_tool("worker_claim_task", {})

    with pytest.raises(Exception, match="changed since scheduler observation"):
        root.call_tool(
            "task_record_failure",
            {
                "name": task_name,
                "reason": "stale scheduler timeout",
                "timed_out": True,
                "expected_state": stale["state"],
                "expected_last_activity_at": stale["last_activity_at"],
            },
        )
    assert root.call_tool("task_status", {"name": task_name})["state"] == "claimed"


def test_deck_reviewer_context_profile_enforces_minimal_stateless_view(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    upstream = _schedule(root)
    upstream_worker = _claim(root, runtime, upstream)
    upstream_worker.call_tool(
        "worker_finalize",
        {
            "content": _critic_output(summary="The frozen base review passed."),
        },
    )

    def bind_artifact(name: str, content: bytes, kind: str, schema: str) -> None:
        envelope = runtime.artifacts.register(
            content,
            ArtifactRegistration(
                kind=kind,
                schema_id=schema,
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"context-policy:{name}",
        )
        root.facade.bindings.bind(
            instance="test",
            namespace="artifact",
            name=name,
            object_id=envelope.artifact_id,
        )

    bind_artifact(
        "revised_project", b'{"schema_version":1}', "tcad_project", "tcad.deck-project.v1"
    )
    bind_artifact(
        "project_diff", b'{"schema_version":1}', "tcad_project_diff", "tcad.deck-project-diff.v1"
    )
    bind_artifact(
        "prior_deck_review",
        b"{}",
        "tcad_project_review",
        "tcad.deck-review-report.v1",
    )
    bind_artifact("unneeded_base", b"{}", "tcad_project", "tcad.deck-project.v1")

    compact_inputs = [
        {
            "source_name": "revised_project",
            "artifact_name": "revised_project",
            "exposure": "full",
        },
        {
            "source_name": "project_diff",
            "artifact_name": "project_diff",
            "exposure": "full",
        },
        {
            "source_name": "prior_review",
            "artifact_name": "prior_deck_review",
            "exposure": "on_demand",
        },
    ]
    with pytest.raises(Exception, match="explicit context profile"):
        root.call_tool(
            "task_schedule",
            {
                "name": "missing_profile",
                "role": "tcad_deck_reviewer",
                "instruction": "Review the revised project.",
                "inputs": compact_inputs,
            },
        )
    with pytest.raises(Exception, match="undeclared sources: base_project"):
        root.call_tool(
            "task_schedule",
            {
                "name": "over_scoped_review",
                "role": "tcad_deck_reviewer",
                "context_profile": "tcad.deck-review.revision.v2",
                "instruction": "Review the revised project.",
                "inputs": compact_inputs
                + [
                    {
                        "source_name": "base_project",
                        "artifact_name": "unneeded_base",
                        "exposure": "on_demand",
                    }
                ],
            },
        )

    scheduled = root.call_tool(
        "task_schedule",
        {
            "name": "compact_review",
            "role": "tcad_deck_reviewer",
            "context_profile": "tcad.deck-review.revision.v2",
            "instruction": "Review the complete revised project and deterministic diff.",
            "inputs": compact_inputs,
        },
    )
    assert scheduled["performance"]["input_exposure_counts"] == {
        "full": 2,
        "on_demand": 1,
        "handoff_only": 0,
    }
    assert scheduled["performance"]["handoff_only_input_bytes"] == 0
    assert scheduled["performance"]["readable_input_bytes"] == scheduled["performance"]["input_bytes"]

    root.call_tool(
        "task_prepare_dispatch", {"name": "compact_review", "ttl_seconds": 60}
    )
    worker = WorkerMCPRouter(runtime.tasks, worker_id="tcad_deck_reviewer")
    assert worker.call_tool("worker_claim_task", {}) == {"state": "claimed"}
    assignment = worker.call_tool("worker_get_assignment", {})
    assert assignment["context_profile"] == "tcad.deck-review.revision.v2"
    assert assignment["output"]["json_schema"]["title"] == (
        "RoleResultEnvelope[DeckReviewReport]"
    )
    prior = next(item for item in assignment["inputs"] if item["name"] == "prior_review")
    assert prior["exposure"] == "on_demand"
    assert prior["handoff"] is None
    assert worker.call_tool("worker_read_input", {"name": "prior_review"})[
        "content"
    ] == "{}"


def test_provenance_deck_review_uses_diagnosis_and_metrics_not_experiment_plan(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)

    def bind(name: str, *, kind: str, schema: str) -> None:
        envelope = runtime.artifacts.register(
            b"{}",
            ArtifactRegistration(
                kind=kind,
                schema_id=schema,
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"provenance-review:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance="test",
            namespace="artifact",
            name=name,
            object_id=envelope.artifact_id,
        )

    bind("project", kind="tcad_project", schema="tcad.deck-project.v1")
    bind(
        "diagnosis",
        kind="layered_diagnosis",
        schema="scidiscovery.layered-diagnosis.v1",
    )
    bind("metrics", kind="metric_report", schema="domain.metric-report.v1")
    bind(
        "audit",
        kind="evidence_audit",
        schema="scidiscovery.decision-packet.v1",
    )

    scheduled = root.call_tool(
        "task_schedule",
        {
            "name": "provenance_review",
            "role": "tcad_deck_reviewer",
            "context_profile": "tcad.deck-review.provenance.v1",
            "instruction": "Review one bounded provenance replay.",
            "inputs": [
                {
                    "source_name": "project",
                    "artifact_name": "project",
                    "exposure": "full",
                },
                {
                    "source_name": "diagnosis",
                    "artifact_name": "diagnosis",
                    "exposure": "full",
                },
                {
                    "source_name": "metric_report",
                    "artifact_name": "metrics",
                    "exposure": "full",
                },
                {
                    "source_name": "evidence_audit",
                    "artifact_name": "audit",
                    "exposure": "on_demand",
                },
            ],
        },
    )
    assert scheduled["readiness"] == "ready"
    assert scheduled["performance"]["input_exposure_counts"] == {
        "full": 3,
        "on_demand": 1,
        "handoff_only": 0,
    }


def test_legacy_task_bytes_remain_verifiable_after_context_schema_extension(
    tmp_path: Path,
) -> None:
    root, runtime = _routers(tmp_path)
    (runtime.project_root / "legacy.json").write_text("{}", encoding="utf-8")
    root.call_tool(
        "artifact_ingest_file",
        {
            "name": "legacy_input",
            "relative_path": "legacy.json",
            "media_type": "application/json",
        },
    )
    task_name = "legacy_context_task"
    root.call_tool(
        "task_schedule",
        {
            "name": task_name,
            "role": "critic",
            "instruction": "Read a legacy task record.",
            "inputs": [
                {"source_name": "legacy_source", "artifact_name": "legacy_input"}
            ],
        },
    )
    current = runtime.tasks.get_task(_task_id(root, task_name)).model_dump(mode="json")
    del current["context_profile"]
    del current["inputs"][0]["exposure"]
    decoded = _decode_agent_task(canonical_json(current))
    assert decoded.context_profile == "default"
    assert decoded.inputs[0].exposure == "on_demand"
