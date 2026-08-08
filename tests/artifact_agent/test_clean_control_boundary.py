from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS, RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
from scidiscovery.artifact_agent.interfaces.mcp_proxy import (
    SCHEDULER_PROXY_FIELD,
    bind_scheduler_proxy,
)
from scidiscovery.artifact_agent.interfaces.mcp_worker import WORKER_TOOLS, WorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.cli import build_parser
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema import LocalFileDescriptor, TaskBudget, TaskOutputSpec
from scidiscovery.artifact_agent.schema import LocalIdentityRef
from scidiscovery.artifact_agent.service import SchedulerNameConflict


ROOT_NAMES = {
    "instance_prepare",
    "instance_status",
    "instance_select",
    "instance_current",
    "instance_list",
    "instance_close",
    "scientific_readiness",
    "lifecycle_events",
    "artifact_ingest_file",
    "artifact_catalog",
    "artifact_transform",
    "task_schedule",
    "task_ready",
    "task_list",
    "task_status",
    "task_evidence_sources",
    "task_prepare_dispatch",
    "task_record_failure",
    "task_retry",
    "approval_request_create",
    "approval_list",
    "approval_status",
    "execution_request_create",
    "execution_approval_request_create",
    "execution_abandon",
    "execution_cancel",
    "execution_list",
    "execution_status",
    "execution_outputs",
    "execution_start",
    "execution_sync",
}
WORKER_NAMES = {
    "worker_claim_task",
    "worker_get_assignment",
    "worker_materialize_assignment",
    "worker_list_inputs",
    "worker_read_input",
    "worker_stage_input",
    "worker_extract_pdf_text",
    "worker_read_table",
    "worker_profile_input",
    "worker_run_analysis",
    "worker_fetch_web_evidence",
    "worker_validate_output",
    "worker_validate_output_file",
    "worker_heartbeat",
    "worker_finalize",
    "worker_finalize_file",
}


def _runtime(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "input.json").write_text('{"temperature_k":140}', encoding="utf-8")
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    return project, runtime


def test_public_tool_surfaces_are_clean_break() -> None:
    assert {tool.name for tool in ROOT_TOOLS} == ROOT_NAMES
    assert {tool.name for tool in WORKER_TOOLS} == WORKER_NAMES
    rendered = json.dumps(
        [tool.schema() for tool in WORKER_TOOLS], sort_keys=True
    ).lower()
    for forbidden in (
        "artifact_id",
        "sha256",
        "schema_id",
        "parent_ref",
        "idempotency",
        "task_id",
        "dispatch_handle",
        "session_token",
        "capsule",
    ):
        assert forbidden not in rendered
    root_rendered = json.dumps(
        [tool.schema() for tool in ROOT_TOOLS], sort_keys=True
    ).lower()
    for forbidden in (
        "artifact_id",
        "task_id",
        "approval_id",
        "execution_id",
        "external_run_id",
        "sha256",
        "hash",
        "token",
        "_ref",
    ):
        assert forbidden not in root_rendered
    assert "instance_create" not in {tool.name for tool in ROOT_TOOLS}


def test_scheduler_proxy_identity_is_transport_managed() -> None:
    raw = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    ).encode("utf-8")
    bound = json.loads(bind_scheduler_proxy(raw, "sch_" + "a" * 32))
    assert bound[SCHEDULER_PROXY_FIELD] == "sch_" + "a" * 32
    assert SCHEDULER_PROXY_FIELD not in json.loads(raw)
    with pytest.raises(ValueError, match="transport-managed"):
        bind_scheduler_proxy(json.dumps(bound).encode("utf-8"), "sch_" + "b" * 32)

    broker = RootBrokerRouter(lambda _: None)
    missing = broker.handle(json.loads(raw))
    assert missing["error"]["message"] == "missing or invalid scheduler proxy binding"


def test_administrative_cli_uses_semantic_names() -> None:
    parser = build_parser()
    ingest = parser.parse_args(
        ["--instance", "fig4_sims", "ingest-file", "paper_source", "paper.pdf"]
    )
    catalog = parser.parse_args(
        ["--instance", "fig4_sims", "artifact-catalog", "paper_source"]
    )
    approval = parser.parse_args(
        ["--instance", "fig4_sims", "approval-status", "paper_review"]
    )
    assert ingest.name == "paper_source"
    assert ingest.instance == "fig4_sims"
    assert catalog.name == "paper_source"
    assert approval.name == "paper_review"
    assert not hasattr(catalog, "artifact_id")
    assert not hasattr(approval, "approval_id")


def test_administrative_cli_exposes_identity_neutral_active_bundle_commands() -> None:
    parser = build_parser()
    exported = parser.parse_args(
        [
            "--state-root",
            "/var/lib/scidiscovery",
            "active-bundle-export",
            "selection.json",
            "active-bundle",
        ]
    )
    verified = parser.parse_args(["active-bundle-verify", "active-bundle"])
    imported = parser.parse_args(
        [
            "--instance",
            "fig4_target",
            "active-bundle-import",
            "active-bundle",
        ]
    )
    assert exported.command == "active-bundle-export"
    assert verified.command == "active-bundle-verify"
    assert imported.instance == "fig4_target"
    for parsed in (exported, verified, imported):
        assert not hasattr(parsed, "artifact_id")
        assert not hasattr(parsed, "task_id")


def test_root_can_only_prepare_instance_for_local_human_creation(
    tmp_path: Path,
) -> None:
    _, runtime = _runtime(tmp_path)
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=None,
            session_key="sch_instance_proposal",
            approval_base_url="http://127.0.0.1:8765",
        )
    )

    prepared = root.call_tool(
        "instance_prepare",
        {
            "name": "paper_reproduction",
            "title": "Paper reproduction",
            "objective": "Reproduce one user-approved paper task.",
        },
    )
    assert prepared["proposal_status"] == "pending"
    assert prepared["review_url"] == "http://127.0.0.1:8765/"
    assert runtime.scheduler_bindings.list_instances() == ()
    assert "approval_id" not in json.dumps(prepared)
    with pytest.raises(Exception, match="no active research instance exists"):
        root.call_tool("instance_current", {})

    proposal = runtime.scheduler_bindings.get_instance_proposal(
        name="paper_reproduction"
    )
    approval = runtime.approvals.status(proposal.approval_id)
    token = parse_qs(urlparse(approval.review_path).query)["token"][0]
    review = runtime.approvals.review(
        proposal.approval_id,
        access_token=token,
    )
    runtime.approvals.record_ui_decision(
        approval_id=proposal.approval_id,
        access_token=token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="create_instance",
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="fixture_user",
            display_name="Fixture user",
        ),
        ui_session_id="fixture_instance_review",
    )
    activated = root.call_tool(
        "instance_status", {"name": "paper_reproduction"}
    )
    assert activated["proposal_status"] == "activated"
    assert activated["instance_state"] == "active"
    assert runtime.scheduler_bindings.session_instance(
        session_key="sch_instance_proposal"
    ) is not None
    assert root.call_tool("instance_current", {})["name"] == "paper_reproduction"


def test_control_assigns_identity_and_worker_only_returns_content(tmp_path: Path) -> None:
    _, runtime = _runtime(tmp_path)
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
    source = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "approved_context",
            "relative_path": "input.json",
            "media_type": "application/json",
        },
    )
    task = root.call_tool(
        "task_schedule",
        {
            "name": "bounded_idea",
            "role": "ideator",
            "instruction": "Propose one bounded scientific test.",
            "inputs": [
                {"source_name": "context", "artifact_name": "approved_context"},
            ],
        },
    )
    assert source == {
        "name": "approved_context",
        "logical_name": "approved_context",
        "revision": 1,
        "state": "bound",
    }
    assert root.call_tool("task_ready", {}) == {"task_names": ["bounded_idea"]}
    dispatch = root.call_tool(
        "task_prepare_dispatch", {"name": "bounded_idea", "ttl_seconds": 60}
    )
    assert dispatch == {"task_name": "bounded_idea", "agent_type": "ideator"}
    worker = WorkerMCPRouter(runtime.tasks, worker_id="ideator")
    assert worker.call_tool("worker_claim_task", {}) == {"state": "claimed"}
    assignment = worker.call_tool("worker_get_assignment", {})
    assert assignment["role"] == "ideator"
    assert assignment["instruction"] == "Propose one bounded scientific test."
    assert assignment["inputs"] == [
        {
            "schema_version": 1,
            "name": "context",
            "media_type": "application/json",
            "size_bytes": 21,
            "exposure": "on_demand",
            "access_modes": ["read_text", "stage_file", "read_table"],
            "handoff": None,
        }
    ]
    assert assignment["output"]["format"] == "json"
    assert assignment["output"]["media_type"] == "application/json"
    assert assignment["output"]["max_bytes"] == 262144
    schema = assignment["output"]["json_schema"]
    assert schema["additionalProperties"] is False
    assert schema["title"] == "RoleResultEnvelope[HypothesisProposal]"
    assert set(schema["properties"]) == {"schema_version", "handoff", "payload"}
    assert assignment["output"]["protocol"] == "scidiscovery.role-result-envelope.v1"
    assert set(assignment["capabilities"]) == {
        "input.read_text",
        "input.stage_file",
        "input.extract_pdf_text",
        "input.read_table",
        "input.profile",
        "analysis.python",
            "evidence.web_snapshot",
            "assignment.materialize",
            "output.file",
            "output.validate",
        "task.heartbeat",
        "image.view",
        "web.search",
    }
    assert assignment["lease_seconds"] >= 1
    read = worker.call_tool(
        "worker_read_input",
        {"name": "context"},
    )
    assert json.loads(read["content"]) == {"temperature_k": 140}
    assert worker.call_tool(
        "worker_finalize",
        {
            "content": {
                "schema_version": 1,
                "handoff": {
                    "verdict": "pass",
                    "summary": "One bounded temperature hypothesis is testable.",
                },
                "payload": {
                    "schema_version": 1,
                    "objective": "Explain the temperature-dependent observation.",
                    "contradiction": "The observation changes with temperature.",
                    "evidence": [
                        {
                            "source_key": "context",
                            "source_type": "frozen_input",
                            "locator": "temperature_k",
                        }
                    ],
                    "hypotheses": [
                        {
                            "hypothesis_key": "temperature_transport",
                            "statement": "Transport changes with temperature.",
                            "mechanism": "A temperature-dependent transport coefficient changes the observable.",
                            "scope": "The bounded supplied context only.",
                            "predictions": [
                                {
                                    "prediction_key": "temperature_trend",
                                    "observable": "Measured transport response",
                                    "expected_outcome": "A repeat at another temperature changes monotonically.",
                                }
                            ],
                            "falsifiers": [
                                {
                                    "falsifier_key": "no_temperature_effect",
                                    "observable": "Measured transport response",
                                    "rejection_condition": "The response is invariant over a resolved temperature range.",
                                }
                            ],
                            "evidence_keys": ["context"],
                        }
                    ],
                },
            },
        },
    ) == {"state": "completed"}
    status = root.call_tool("task_status", {"name": "bounded_idea"})
    assert status["state"] == "completed"
    assert status["output_artifact_name"] == "bounded_idea.output"
    output = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance="test", namespace="artifact", name=status["output_artifact_name"]
        )
    )
    stored = json.loads(runtime.artifacts.read(output.ref))
    assert stored["hypotheses"][0]["hypothesis_key"] == "temperature_transport"
    assert output.schema_id == "scidiscovery.hypothesis-proposal.v1"


def test_task_local_source_name_rejects_staging_ambiguous_characters(
    tmp_path: Path,
) -> None:
    _, runtime = _runtime(tmp_path)
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
    artifact = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "control/source:one",
            "relative_path": "input.json",
            "media_type": "application/json",
        },
    )
    with pytest.raises(Exception, match="invalid arguments"):
        root.call_tool(
            "task_schedule",
            {
                "name": "invalid_local_alias",
                "role": "critic",
                "instruction": "This task must not be created.",
                "inputs": [
                    {
                        "source_name": "source/one",
                        "artifact_name": artifact["name"],
                    }
                ],
            },
        )


def test_root_results_never_expose_control_identity(tmp_path: Path) -> None:
    _, runtime = _runtime(tmp_path)
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
    artifact = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "approved_context",
            "relative_path": "input.json",
            "media_type": "application/json",
        },
    )
    catalog = root.call_tool("artifact_catalog", {"name": artifact["name"]})
    task = root.call_tool(
        "task_schedule",
        {
            "name": "bounded_review",
            "role": "critic",
            "instruction": "Review the bounded context.",
            "inputs": [
                {"source_name": "source", "artifact_name": artifact["name"]},
            ],
        },
    )
    values = [
        artifact,
        catalog,
        task,
        root.call_tool("task_ready", {}),
        root.call_tool("task_list", {"limit": 10}),
        root.call_tool(
            "task_prepare_dispatch",
            {"name": task["name"], "ttl_seconds": 60},
        ),
    ]
    rendered = json.dumps(values, sort_keys=True).lower()
    for forbidden in (
        "artifact_id",
        "task_id",
        "approval_id",
        "execution_id",
        "external_run_id",
        "sha256",
        "token",
        "review_path",
        "_ref",
        "art_",
        "tsk_",
        "apr_",
        "exe_",
    ):
        assert forbidden not in rendered


def test_same_name_is_idempotent_only_for_same_request_and_can_create_revision(
    tmp_path: Path,
) -> None:
    project, runtime = _runtime(tmp_path)
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
    arguments = {
        "name": "approved_context",
        "relative_path": "input.json",
        "media_type": "application/json",
    }
    first = root.call_tool("artifact_ingest_file", arguments)
    assert root.call_tool("artifact_ingest_file", arguments) == first

    (project / "input.json").write_text('{"temperature_k":300}', encoding="utf-8")
    with pytest.raises(SchedulerNameConflict, match="explicit revision"):
        root.call_tool("artifact_ingest_file", arguments)
    revised = root.call_tool(
        "artifact_ingest_file", {**arguments, "on_conflict": "create_revision"}
    )
    assert revised == {
        "name": "approved_context.rev2",
        "logical_name": "approved_context",
        "revision": 2,
        "state": "bound",
    }
    assert root.call_tool(
        "artifact_ingest_file", {**arguments, "on_conflict": "create_revision"}
    ) == revised

    task_arguments = {
        "name": "context_review",
        "role": "critic",
        "instruction": "Review the revised context.",
        "inputs": [
            {"source_name": "source", "artifact_name": revised["name"]},
        ],
    }
    task = root.call_tool("task_schedule", task_arguments)
    assert root.call_tool("task_schedule", task_arguments)["name"] == task["name"]
    with pytest.raises(SchedulerNameConflict, match="explicit revision"):
        root.call_tool(
            "task_schedule",
            {**task_arguments, "instruction": "Use a different review question."},
        )
    task_revision = root.call_tool(
        "task_schedule",
        {
            **task_arguments,
            "instruction": "Use a different review question.",
            "on_conflict": "create_revision",
        },
    )
    assert task_revision["name"] == "context_review.rev2"
    assert task_revision["logical_name"] == "context_review"
    assert task_revision["revision"] == 2


def test_root_sessions_isolate_same_semantic_name_between_research_instances(
    tmp_path: Path,
) -> None:
    _, runtime = _runtime(tmp_path)

    def router(session_key: str) -> RootMCPRouter:
        return RootMCPRouter(
            RootToolFacade(
                runtime.artifacts,
                runtime.intake,
                tasks=runtime.tasks,
                approvals=runtime.approvals,
                executions=runtime.executions,
                bindings=runtime.scheduler_bindings,
                instance=runtime.scheduler_bindings.session_instance(
                    session_key=session_key
                ),
                session_key=session_key,
            )
        )

    first = router("sch_first")
    with pytest.raises(Exception, match="no active research instance exists"):
        first.call_tool("artifact_catalog", {"name": "paper_source"})
    first_instance = runtime.scheduler_bindings.create_instance(
        name="fig4_profile",
        title="Fig. 4 profile",
        objective="Reproduce the single-layer profile.",
    )
    runtime.scheduler_bindings.bind_session(
        session_key="sch_first", instance_id=first_instance.instance_id
    )
    first = router("sch_first")
    second = router("sch_second")
    second_instance = runtime.scheduler_bindings.create_instance(
        name="dark_current",
        title="Dark current",
        objective="Test the complete-device electrical baseline.",
    )
    runtime.scheduler_bindings.bind_session(
        session_key="sch_second", instance_id=second_instance.instance_id
    )
    second = router("sch_second")
    assert first_instance.name != second_instance.name

    first.call_tool(
        "artifact_ingest_file",
        {"name": "paper_source", "relative_path": "input.json"},
    )
    second.call_tool(
        "artifact_ingest_file",
        {"name": "paper_source", "relative_path": "input.json"},
    )
    first_id = runtime.scheduler_bindings.select_instance(
        name="fig4_profile"
    ).instance_id
    second_id = runtime.scheduler_bindings.select_instance(
        name="dark_current"
    ).instance_id
    assert runtime.scheduler_bindings.resolve(
        instance=first_id, namespace="artifact", name="paper_source"
    ) != runtime.scheduler_bindings.resolve(
        instance=second_id, namespace="artifact", name="paper_source"
    )

    restarted_session = router("sch_first")
    assert restarted_session.call_tool("instance_current", {})["name"] == "fig4_profile"
    first.call_tool("instance_close", {})
    with pytest.raises(Exception, match="local human confirmation is required"):
        restarted_session.call_tool("artifact_catalog", {"name": "paper_source"})


def test_unbound_root_requires_review_and_takeover_revokes_old_session(
    tmp_path: Path,
) -> None:
    _, runtime = _runtime(tmp_path)
    instance = runtime.scheduler_bindings.create_instance(
        name="fig4_takeover",
        title="Fig. 4 takeover",
        objective="Verify exclusive scheduler-process ownership.",
    )
    runtime.scheduler_bindings.bind_session(
        session_key="sch_old", instance_id=instance.instance_id
    )

    def router(session_key: str) -> RootMCPRouter:
        return RootMCPRouter(
            RootToolFacade(
                runtime.artifacts,
                runtime.intake,
                tasks=runtime.tasks,
                approvals=runtime.approvals,
                executions=runtime.executions,
                bindings=runtime.scheduler_bindings,
                instance=runtime.scheduler_bindings.session_instance(
                    session_key=session_key
                ),
                session_key=session_key,
                approval_base_url="http://127.0.0.1:8765",
            )
        )

    old = router("sch_old")
    newcomer = router("sch_new")
    pending = newcomer.call_tool("instance_current", {})
    assert pending["binding_status"] == "pending"
    assert pending["review_url"] == "http://127.0.0.1:8765/"
    assert runtime.scheduler_bindings.session_instance(
        session_key="sch_old"
    ) == instance.instance_id
    assert runtime.scheduler_bindings.session_instance(session_key="sch_new") is None

    request, candidates = runtime.scheduler_bindings.prepare_session_binding_request(
        session_key="sch_new"
    )
    assert [item.instance.name for item in candidates] == ["fig4_takeover"]
    approval = runtime.approvals.status(request.approval_id)
    token = parse_qs(urlparse(approval.review_path).query)["token"][0]
    review = runtime.approvals.review(request.approval_id, access_token=token)
    runtime.approvals.record_ui_decision(
        approval_id=request.approval_id,
        access_token=token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option=candidates[0].option_id,
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="fixture_user", display_name="Fixture user"
        ),
        ui_session_id="fixture_takeover",
    )
    runtime.scheduler_bindings.apply_session_binding_decision(
        approval_id=request.approval_id,
        selected_option=candidates[0].option_id,
    )

    assert newcomer.call_tool("instance_current", {})["name"] == "fig4_takeover"
    assert runtime.scheduler_bindings.session_instance(session_key="sch_old") is None
    revoked = old.call_tool("instance_current", {})
    assert revoked["binding_status"] == "pending"
    with pytest.raises(Exception, match="local human confirmation is required"):
        old.call_tool("artifact_catalog", {"name": "paper_source"})


def test_instance_select_requests_review_instead_of_binding_directly(
    tmp_path: Path,
) -> None:
    _, runtime = _runtime(tmp_path)
    target = runtime.scheduler_bindings.create_instance(
        name="dark_current_target",
        title="Dark-current target",
        objective="Verify reviewed selection.",
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=None,
            session_key="sch_select_review",
            approval_base_url="http://127.0.0.1:8765",
        )
    )

    pending = root.call_tool("instance_select", {"name": target.name})
    assert pending == {
        "binding_status": "pending",
        "candidate_names": [target.name],
        "review_url": "http://127.0.0.1:8765/",
    }
    assert runtime.scheduler_bindings.session_instance(
        session_key="sch_select_review"
    ) is None


def test_research_instance_cannot_close_with_active_work(tmp_path: Path) -> None:
    _, runtime = _runtime(tmp_path)
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=None,
            session_key="sch_active",
        )
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="active_work",
        title="Active work",
        objective="Verify instance closure guards.",
    )
    runtime.scheduler_bindings.bind_session(
        session_key="sch_active", instance_id=instance.instance_id
    )
    root.facade.instance = instance.instance_id
    root.call_tool(
        "task_schedule",
        {
            "name": "pending_review",
            "role": "critic",
            "instruction": "Keep this task pending.",
        },
    )
    with pytest.raises(Exception, match="active scientific task"):
        root.call_tool("instance_close", {})
    assert root.call_tool("instance_current", {})["state"] == "active"


def test_dispatch_role_is_bound_by_control(tmp_path: Path) -> None:
    _, runtime = _runtime(tmp_path)
    contract = runtime.tasks.output_contract("critic")
    task_id = runtime.tasks.schedule(
        role="critic",
        instruction="Review the proposal.",
        inputs=(),
        output=TaskOutputSpec(
            format=contract.format,
            kind=contract.kind,
            schema_id=contract.schema_id,
            validator=contract.validator,
            media_type="application/json",
            max_bytes=1024,
        ),
        budget=TaskBudget(),
    )
    runtime.tasks.prepare_dispatch(task_id, ttl_seconds=60)
    wrong_worker = WorkerMCPRouter(runtime.tasks, worker_id="ideator")
    with pytest.raises(Exception, match="no queued assignment"):
        wrong_worker.call_tool("worker_claim_task", {})


def test_approved_execution_lifecycle_registers_results_in_control(tmp_path: Path) -> None:
    _, runtime = _runtime(tmp_path)
    output_path = tmp_path / "result.txt"
    output_path.write_text("result\n", encoding="utf-8")

    class FixtureAdapter:
        prepared_payload: bytes | None = None

        def prepare(self, payload, *, preparation_profile, exchange_directory):
            assert preparation_profile == "identity.v1"
            assert exchange_directory == Path(payload.local_path).parent
            self.prepared_payload = Path(payload.local_path).read_bytes()
            return payload

        def submit(self, submission):
            assert Path(submission.local_path).is_file()
            return "run_test", "accepted"

        def status(self, external_run_id):
            assert external_run_id == "run_test"
            return "succeeded"

        def collect(self, external_run_id):
            raw = output_path.read_bytes()
            return (
                LocalFileDescriptor(
                    name="result",
                    local_path=str(output_path),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    size_bytes=len(raw),
                    media_type="text/plain",
                ),
            )

    adapter = FixtureAdapter()
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
                runtime.executions, adapters={"fixture": adapter}
            ),
        )
    )
    payload = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "execution_payload",
            "relative_path": "input.json",
            "media_type": "application/json",
        },
    )
    execution = root.call_tool(
        "execution_request_create",
        {
            "name": "fixture_execution",
            "executor": "fixture",
            "preparation_profile": "identity.v1",
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
    access_token = parse_qs(urlparse(approval_status.review_path).query)["token"][0]
    review = runtime.approvals.review(approval_id, access_token=access_token)
    runtime.approvals.record_ui_decision(
        approval_id=approval_id,
        access_token=access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="authorize_execution",
        rationale="",
        decided_by=LocalIdentityRef(identity_id="test_user", display_name="Test user"),
        ui_session_id="test_session",
    )
    started = root.call_tool(
        "execution_start",
        {"name": execution["name"]},
    )
    assert started["state"] == "submitted"
    assert adapter.prepared_payload == b'{"temperature_k":140}'
    collected = root.call_tool(
        "execution_sync", {"name": execution["name"]}
    )
    assert collected["state"] == "collected"
    assert root.call_tool(
        "execution_status", {"name": execution["name"]}
    )["state"] == "collected"
