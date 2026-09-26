from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolError,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import (
    ApprovalOption,
    CompiledApprovalIdentity,
    LocalIdentityRef,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service.executions import ExecutionApprovalError
from scidiscovery.artifact_agent.service.executions import ExecutionServiceError
from scidiscovery.artifact_agent.storage import ArtifactRegistryError
from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN
from scidiscovery.operations.catalog import compile_catalog


class _NoEffectAdapter:
    def __init__(self) -> None:
        self.submit_count = 0
        self.submissions: dict[str, tuple[str, str]] = {}
        self.fail_lookup = False
        self.lose_response_once = False

    @staticmethod
    def supports_preparation_profile(profile: str) -> bool:
        return profile == "fixture.no-effect.v1"

    @staticmethod
    def validate_preparation_payload(
        raw: bytes, *, preparation_profile: str
    ) -> None:
        if preparation_profile != "fixture.no-effect.v1" or raw not in {
            b"{}",
            b'{"revision":2}',
        }:
            raise ValueError("unexpected architecture effect payload")

    @staticmethod
    def prepare(payload, *, preparation_profile: str, exchange_directory: Path):
        del exchange_directory
        if preparation_profile != "fixture.no-effect.v1":
            raise ValueError("unexpected architecture preparation profile")
        return payload

    def submit(self, _submission) -> tuple[str, str]:
        existing = self.submissions.get(_submission.sha256)
        if existing is not None:
            return existing
        self.submit_count += 1
        result = ("unexpected-run", "accepted")
        self.submissions[_submission.sha256] = result
        if self.lose_response_once:
            self.lose_response_once = False
            raise RuntimeError("submission response was lost")
        return result

    def lookup_submission(self, submission) -> tuple[str, str] | None:
        if self.fail_lookup:
            raise RuntimeError("submission authority is unavailable")
        return self.submissions.get(submission.sha256)


def _effect_operation():
    return next(
        operation
        for operation in ARCHITECTURE_TEST_PLUGIN.operations
        if operation.operation_id == "builtin.test.effect"
    )


def _drifted_catalog():
    effect = _effect_operation()
    assert effect.review is not None and effect.review.approval is not None
    changed_contract = effect.review.approval.model_copy(
        update={"question": "Changed architecture execution contract?"}
    )
    changed_effect = effect.model_copy(
        update={
            "review": effect.review.model_copy(
                update={"approval": changed_contract}
            )
        }
    )
    plugin = ARCHITECTURE_TEST_PLUGIN.model_copy(
        update={
            "operations": tuple(
                changed_effect
                if operation.operation_id == changed_effect.operation_id
                else operation
                for operation in ARCHITECTURE_TEST_PLUGIN.operations
            )
        }
    )
    return compile_catalog((plugin,))


def _setup(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
    )
    catalog = compile_catalog((ARCHITECTURE_TEST_PLUGIN,))
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="r4d_execution_identity",
        title="R4-D execution approval identity",
        objective="Reject execution authorization when compiled identity differs.",
    )
    payload = runtime.artifacts.register(
        b"{}",
        ArtifactRegistration(
            kind="architecture_test_input",
            schema_id="scidiscovery.architecture-test.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="r4d-execution-identity:payload",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="effect_input",
        object_id=payload.artifact_id,
    )
    adapter = _NoEffectAdapter()
    facade = RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
        execution_bridge=ExecutionBridge(
            runtime.executions,
            adapters={"architecture_fixture:fixture": adapter},
        ),
    )
    return runtime, instance, adapter, facade, RootMCPRouter(facade), catalog


def _reopen(tmp_path: Path, instance, adapter, catalog):
    runtime = open_runtime(
        project_root=tmp_path / "project",
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
    )
    runtime.runs.operation_catalog = catalog
    facade = RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
        execution_bridge=ExecutionBridge(
            runtime.executions,
            adapters={"architecture_fixture:fixture": adapter},
        ),
    )
    return runtime, RootMCPRouter(facade)


def _effect_call(name: str) -> dict:
    return {
        "name": name,
        "operation_id": "builtin.test.effect",
        "inputs": [
            {"port": "effect_input", "artifact_names": ["effect_input"]}
        ],
    }


def _create_effect(root: RootMCPRouter, *, name: str) -> dict:
    created = root.call_tool(
        "operation_invoke",
        _effect_call(name),
    )
    assert created["executor_kind"] == "effect"
    assert created["result"]["state"] == "created"
    assert created["result"]["approval"]["status"] == "pending"
    return created


def _decide_execution_approval(runtime, root: RootMCPRouter, *, name: str) -> str:
    approval_id = runtime.scheduler_bindings.resolve(
        instance=root.facade._instance_id(),
        namespace="approval",
        name=f"{name}.approval",
    )
    launch = runtime.approvals.status(approval_id)
    assert launch.review_path is not None
    access_token = parse_qs(urlparse(launch.review_path).query)["token"][0]
    review = runtime.approvals.review(
        approval_id, access_token=access_token
    )
    runtime.approvals.record_ui_decision(
        approval_id=approval_id,
        access_token=access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="authorize_execution",
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="r4d_independent_fixture_reviewer",
            display_name="R4-D Independent Fixture Reviewer",
        ),
        ui_session_id="r4d-execution-identity-test",
    )
    return approval_id


def _switch_catalog(runtime, facade: RootToolFacade, catalog) -> None:
    runtime.runs.operation_catalog = catalog
    facade._operation_catalog = catalog


def test_effect_invoke_creates_one_exact_approval_and_replays_it(
    tmp_path: Path,
) -> None:
    runtime, instance, adapter, _, root, _ = _setup(tmp_path)
    first = _create_effect(root, name="automatic_approval")
    approval_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="approval",
        name="automatic_approval.approval",
    )
    assert root.call_tool("operation_invoke", _effect_call("automatic_approval")) == first
    assert runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="approval",
        name="automatic_approval.approval",
    ) == approval_id
    with pytest.raises(
        RootToolError, match="unknown root tool: execution_approval_request_create"
    ):
        root.call_tool(
            "execution_approval_request_create", {"name": "automatic_approval"}
        , surface="execution")
    assert adapter.submit_count == 0


@pytest.mark.parametrize("failure", ("response_lost", "local_record_failed"))
def test_unknown_submission_is_recovered_by_lookup_without_resubmit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    runtime, instance, adapter, _, root, catalog = _setup(tmp_path)
    _create_effect(root, name="unknown_submission")
    _decide_execution_approval(runtime, root, name="unknown_submission")
    if failure == "response_lost":
        adapter.lose_response_once = True
    else:
        monkeypatch.setattr(
            runtime.executions,
            "record_submission",
            lambda **_: (_ for _ in ()).throw(
                RuntimeError("local submission record failed")
            ),
        )

    with pytest.raises(RuntimeError):
        root.call_tool("execution_start", {"name": "unknown_submission"}, surface="execution")
    assert adapter.submit_count == 1
    assert root.call_tool(
        "execution_status", {"name": "unknown_submission"}
    , surface="execution")["state"] == "authorized"

    restarted, restarted_root = _reopen(tmp_path, instance, adapter, catalog)
    recovered = restarted_root.call_tool(
        "execution_start", {"name": "unknown_submission"}
    , surface="execution")
    assert recovered["state"] == "submitted"
    assert adapter.submit_count == 1
    execution_id = restarted.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="execution",
        name="unknown_submission",
    )
    restarted.executions.record_submission(
        execution_id=execution_id, external_run_id="unexpected-run"
    )
    assert adapter.submit_count == 1


def test_unavailable_submission_lookup_fails_before_external_submit(
    tmp_path: Path,
) -> None:
    runtime, _, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="lookup_unavailable")
    _decide_execution_approval(runtime, root, name="lookup_unavailable")
    adapter.fail_lookup = True

    with pytest.raises(RuntimeError, match="authority is unavailable"):
        root.call_tool("execution_start", {"name": "lookup_unavailable"}, surface="execution")
    assert adapter.submit_count == 0
    assert root.call_tool(
        "execution_status", {"name": "lookup_unavailable"}
    , surface="execution")["state"] == "authorized"

    adapter.fail_lookup = False
    assert root.call_tool(
        "execution_start", {"name": "lookup_unavailable"}
    , surface="execution")["state"] == "submitted"
    assert adapter.submit_count == 1


def test_execution_bridge_rejects_adapter_without_submission_lookup(
    tmp_path: Path,
) -> None:
    runtime, _, adapter, _, _, _ = _setup(tmp_path)
    adapter.lookup_submission = None  # type: ignore[method-assign]
    with pytest.raises(
        ExecutionServiceError, match="no authoritative submission lookup"
    ):
        ExecutionBridge(
            runtime.executions,
            adapters={"architecture_fixture:fixture": adapter},
        )


def test_effect_approval_recovers_one_request_after_binding_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    original_bind = facade._bind
    failed = False

    def fail_first_approval_binding(
        namespace: str,
        name: str,
        object_id: str,
        *,
        request_fingerprint: str | None = None,
    ):
        nonlocal failed
        if namespace == "approval" and not failed:
            failed = True
            raise RuntimeError("injected approval binding failure")
        return original_bind(
            namespace,
            name,
            object_id,
            request_fingerprint=request_fingerprint,
        )

    monkeypatch.setattr(facade, "_bind", fail_first_approval_binding)
    with pytest.raises(RuntimeError, match="injected approval binding failure"):
        root.call_tool("operation_invoke", _effect_call("recoverable_approval"))
    execution_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="execution",
        name="recoverable_approval",
    )
    expected_approval_id = f"apr_{execution_id}"
    assert [
        item.approval_id
        for item in runtime.approvals.list_requests(status="pending", limit=100)
    ] == [expected_approval_id]
    assert facade._optional("approval", "recoverable_approval.approval") is None

    monkeypatch.setattr(facade, "_bind", original_bind)
    recovered = root.call_tool(
        "operation_invoke", _effect_call("recoverable_approval")
    )
    assert recovered["result"]["approval"]["status"] == "pending"
    assert runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="approval",
        name="recoverable_approval.approval",
    ) == expected_approval_id
    assert [
        item.approval_id
        for item in runtime.approvals.list_requests(status="pending", limit=100)
    ] == [expected_approval_id]
    assert adapter.submit_count == 0


def test_effect_execution_identity_is_stable_across_binding_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    original_bind_target = facade._bind_target
    remaining_faults = 3

    def fail_execution_binding(
        namespace: str,
        target,
        object_id: str,
        request_fingerprint: str,
    ):
        nonlocal remaining_faults
        if namespace == "execution" and remaining_faults:
            remaining_faults -= 1
            raise RuntimeError("injected execution binding failure")
        return original_bind_target(
            namespace,
            target,
            object_id,
            request_fingerprint,
        )

    monkeypatch.setattr(facade, "_bind_target", fail_execution_binding)
    for _ in range(3):
        with pytest.raises(RuntimeError, match="injected execution binding failure"):
            root.call_tool("operation_invoke", _effect_call("stable_execution"))
        assert len(runtime.executions.list_statuses(limit=100)) == 1
        assert len(
            runtime.artifacts.list_artifacts(kind="execution_request", limit=100)
        ) == 1
        assert facade._optional("execution", "stable_execution") is None

    recovered = root.call_tool(
        "operation_invoke", _effect_call("stable_execution")
    )["result"]
    execution_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="execution",
        name="stable_execution",
    )
    assert recovered["name"] == "stable_execution"
    statuses = runtime.executions.list_statuses(limit=100)
    assert len(statuses) == 1
    assert statuses[0].execution_id == execution_id
    assert len(
        runtime.artifacts.list_artifacts(kind="execution_request", limit=100)
    ) == 1
    assert len(runtime.approvals.list_requests(status="pending", limit=100)) == 1
    assert adapter.submit_count == 0


def test_effect_recovers_request_artifact_committed_before_execution_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    original_register = runtime.artifacts.register
    remaining_faults = 3

    def fail_after_request_commit(content, registration, *, idempotency_key):
        nonlocal remaining_faults
        envelope = original_register(
            content, registration, idempotency_key=idempotency_key
        )
        if registration.kind == "execution_request" and remaining_faults:
            remaining_faults -= 1
            raise RuntimeError("injected after request Artifact commit")
        return envelope

    monkeypatch.setattr(runtime.artifacts, "register", fail_after_request_commit)
    for _ in range(3):
        with pytest.raises(RuntimeError, match="after request Artifact commit"):
            root.call_tool("operation_invoke", _effect_call("recover_request_commit"))
        assert runtime.executions.list_statuses(limit=100) == ()
        assert len(
            runtime.artifacts.list_artifacts(kind="execution_request", limit=100)
        ) == 1
        assert runtime.approvals.list_requests(status="pending", limit=100) == ()
        assert facade._optional("execution", "recover_request_commit") is None

    recovered = root.call_tool(
        "operation_invoke", _effect_call("recover_request_commit")
    )["result"]
    execution_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="execution",
        name="recover_request_commit",
    )
    assert recovered["name"] == "recover_request_commit"
    assert [item.execution_id for item in runtime.executions.list_statuses(limit=100)] == [
        execution_id
    ]
    assert len(
        runtime.artifacts.list_artifacts(kind="execution_request", limit=100)
    ) == 1
    assert len(runtime.approvals.list_requests(status="pending", limit=100)) == 1
    assert adapter.submit_count == 0


@pytest.mark.parametrize("record_fault", ["missing", "wrong_hash"])
def test_effect_existing_execution_requires_original_request_idempotency_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_fault: str,
) -> None:
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    original_bind_target = facade._bind_target
    failed = False

    def fail_first_execution_binding(
        namespace: str,
        target,
        object_id: str,
        request_fingerprint: str,
    ):
        nonlocal failed
        if namespace == "execution" and not failed:
            failed = True
            raise RuntimeError("injected execution binding failure")
        return original_bind_target(
            namespace, target, object_id, request_fingerprint
        )

    monkeypatch.setattr(facade, "_bind_target", fail_first_execution_binding)
    with pytest.raises(RuntimeError, match="injected execution binding failure"):
        root.call_tool("operation_invoke", _effect_call("record_required"))
    execution_id = runtime.executions.list_statuses(limit=100)[0].execution_id
    idempotency_key = f"execution:{execution_id}:request"
    with sqlite3.connect(runtime.artifacts.registry.database_path) as connection:
        if record_fault == "missing":
            connection.execute("DROP TRIGGER idempotency_records_deny_delete")
            connection.execute(
                "DELETE FROM idempotency_records WHERE idempotency_key = ?",
                (idempotency_key,),
            )
        else:
            connection.execute("DROP TRIGGER idempotency_records_deny_update")
            connection.execute(
                """
                UPDATE idempotency_records SET request_sha256 = ?
                WHERE idempotency_key = ?
                """,
                ("0" * 64, idempotency_key),
            )

    monkeypatch.setattr(facade, "_bind_target", original_bind_target)
    with pytest.raises(ArtifactRegistryError):
        root.call_tool("operation_invoke", _effect_call("record_required"))
    assert facade._optional("execution", "record_required") is None
    assert runtime.approvals.list_requests(status="pending", limit=100) == ()
    assert runtime.scheduler_bindings.list(
        instance=instance.instance_id, namespace="approval"
    ) == ()
    assert adapter.submit_count == 0


def test_execution_status_and_list_do_not_publish_collected_result(
    tmp_path: Path,
) -> None:
    runtime, instance, adapter, facade, root, _ = _setup(tmp_path)
    _create_effect(root, name="pure_execution_query")
    _decide_execution_approval(runtime, root, name="pure_execution_query")
    started = root.call_tool("execution_start", {"name": "pure_execution_query"}, surface="execution")
    assert started["state"] == "submitted"
    execution_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="execution",
        name="pure_execution_query",
    )
    runtime.executions.record_status(
        execution_id=execution_id,
        external_run_id="unexpected-run",
        state="succeeded",
    )
    result_ref = runtime.executions.ingest_result(
        execution_id=execution_id,
        external_run_id="unexpected-run",
        outputs=(),
    )
    assert facade._optional("artifact", "pure_execution_query.result") is None

    before = tuple(
        runtime.scheduler_bindings.list(
            instance=instance.instance_id, namespace="artifact"
        )
    )
    status = root.call_tool("execution_status", {"name": "pure_execution_query"}, surface="execution")
    listed = root.call_tool("execution_list", {"state": "collected", "limit": 10}, surface="execution")
    after = tuple(
        runtime.scheduler_bindings.list(
            instance=instance.instance_id, namespace="artifact"
        )
    )

    assert status["state"] == "collected"
    assert status["result_artifact_name"] is None
    assert listed["executions"] == [{"name": status["name"], "state": status["state"]}]
    assert "result_artifact_name" not in listed["executions"][0]
    assert before == after
    assert facade._optional("artifact", "pure_execution_query.result") is None

    assert root.call_tool(
        "execution_outputs", {"name": "pure_execution_query"}
    , surface="execution")["outputs"] == []
    assert runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name="pure_execution_query.result",
    ) == result_ref.artifact_id
    assert adapter.submit_count == 1


def test_effect_revision_gets_a_new_undecided_exact_approval(
    tmp_path: Path,
) -> None:
    runtime, instance, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="revision_execution")
    first_approval = _decide_execution_approval(
        runtime, root, name="revision_execution"
    )
    revised_payload = runtime.artifacts.register(
        b'{"revision":2}',
        ArtifactRegistration(
            kind="architecture_test_input",
            schema_id="scidiscovery.architecture-test.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="r4d-execution-identity:revised-payload",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="effect_input_revision",
        object_id=revised_payload.artifact_id,
    )
    revised = root.call_tool(
        "operation_invoke",
        {
            "name": "revision_execution",
            "operation_id": "builtin.test.effect",
            "inputs": [
                {
                    "port": "effect_input",
                    "artifact_names": ["effect_input_revision"],
                }
            ],
            "on_conflict": "create_revision",
        },
    )["result"]
    assert revised["name"] == "revision_execution.rev2"
    assert revised["revision"] == 2
    assert revised["approval"]["status"] == "pending"
    revised_approval = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="approval",
        name="revision_execution.rev2.approval",
    )
    assert revised_approval != first_approval
    with pytest.raises(ExecutionApprovalError, match="not decided"):
        root.call_tool("execution_start", {"name": "revision_execution.rev2"}, surface="execution")
    assert adapter.submit_count == 0


def test_contract_drift_blocks_previously_decided_execution_start(
    tmp_path: Path,
) -> None:
    runtime, _, adapter, facade, root, _ = _setup(tmp_path)
    _create_effect(root, name="drift_after_decision")
    _decide_execution_approval(runtime, root, name="drift_after_decision")
    _switch_catalog(runtime, facade, _drifted_catalog())

    with pytest.raises(RootToolError, match="operation contract changed"):
        root.call_tool("execution_start", {"name": "drift_after_decision"}, surface="execution")
    assert adapter.submit_count == 0
    assert root.call_tool(
        "execution_status", {"name": "drift_after_decision"}
    , surface="execution")["state"] == "created"


def test_plugin_removal_blocks_previously_decided_execution_start(
    tmp_path: Path,
) -> None:
    runtime, _, adapter, facade, root, _ = _setup(tmp_path)
    _create_effect(root, name="removed_after_decision")
    _decide_execution_approval(runtime, root, name="removed_after_decision")
    _switch_catalog(runtime, facade, compile_catalog(()))

    with pytest.raises(RootToolError, match="operation is not installed"):
        root.call_tool("execution_start", {"name": "removed_after_decision"}, surface="execution")
    assert adapter.submit_count == 0
    assert root.call_tool(
        "execution_status", {"name": "removed_after_decision"}
    , surface="execution")["state"] == "created"


def test_wrong_approval_request_identity_cannot_authorize_execution(
    tmp_path: Path,
) -> None:
    runtime, instance, adapter, _, root, catalog = _setup(tmp_path)
    payload_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name="effect_input",
    )
    current = catalog.operation("builtin.test.effect").approval_identity
    assert current is not None
    identity = CompiledApprovalIdentity(
        operation_id=current.operation_id,
        operation_version=current.version,
        operation_digest=current.operation_digest,
        approval_contract_digest=current.approval_contract_digest,
    )
    execution_id = runtime.executions.create(
        executor="architecture_fixture:fixture",
        preparation_profile="fixture.no-effect.v1",
        payload_ref=runtime.artifacts.get_by_id(payload_id).ref,
        compiled_identity=identity,
        labels={
            "operation_id": identity.operation_id,
            "operation_version": identity.operation_version,
            "operation_digest": identity.operation_digest,
            "approval_contract_digest": identity.approval_contract_digest,
        },
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="execution",
        name="wrong_approval_identity",
        object_id=execution_id,
    )
    request_ref, payload_ref = runtime.executions.approval_subject_refs(execution_id)
    wrong_identity = CompiledApprovalIdentity(
        operation_id=current.operation_id,
        operation_version=current.version,
        operation_digest="0" * 64,
        approval_contract_digest=current.approval_contract_digest,
    )
    launch = runtime.approvals.create_request(
        approval_id="wrong_compiled_execution_approval",
        kind="execution_authorization",
        subject_refs=(request_ref, payload_ref),
        question="Authorize using the wrong compiled operation identity?",
        options=(
            ApprovalOption(
                option_id="authorize_execution",
                label="Authorize",
                description="Authorize the exact request and payload.",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="reject_execution",
                label="Reject",
                description="Reject the exact request and payload.",
                requires_rationale=False,
            ),
        ),
        requested_by=runtime.actor,
        idempotency_key="r4d-execution-identity:wrong-approval",
        compiled_identity=wrong_identity,
    )
    review = runtime.approvals.review(
        launch.approval_id, access_token=launch.access_token
    )
    runtime.approvals.record_ui_decision(
        approval_id=launch.approval_id,
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="authorize_execution",
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="r4d_wrong_identity_fixture",
            display_name="R4-D Wrong Identity Fixture",
        ),
        ui_session_id="r4d-execution-identity-test",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="approval",
        name="wrong_approval_identity.approval",
        object_id=launch.approval_id,
    )

    with pytest.raises(
        ExecutionApprovalError,
        match="execution approval compiled identity is missing or changed",
    ):
        root.call_tool("execution_start", {"name": "wrong_approval_identity"}, surface="execution")
    assert adapter.submit_count == 0
    assert root.call_tool(
        "execution_status", {"name": "wrong_approval_identity"}
    , surface="execution")["state"] == "created"


def test_decided_legacy_execution_request_remains_non_authorizable(
    tmp_path: Path,
) -> None:
    runtime, instance, adapter, _, root, catalog = _setup(tmp_path)
    payload_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name="effect_input",
    )
    execution_id = runtime.executions.create(
        executor="architecture_fixture:fixture",
        preparation_profile="fixture.no-effect.v1",
        payload_ref=runtime.artifacts.get_by_id(payload_id).ref,
        compiled_identity=None,
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="execution",
        name="legacy_decided",
        object_id=execution_id,
    )
    request_ref, payload_ref = runtime.executions.approval_subject_refs(execution_id)
    current = catalog.operation("builtin.test.effect").approval_identity
    assert current is not None
    identity = CompiledApprovalIdentity(
        operation_id=current.operation_id,
        operation_version=current.version,
        operation_digest=current.operation_digest,
        approval_contract_digest=current.approval_contract_digest,
    )
    launch = runtime.approvals.create_request(
        approval_id="legacy_decided_approval",
        kind="execution_authorization",
        subject_refs=(request_ref, payload_ref),
        question="Historical fallback decision",
        options=(
            ApprovalOption(
                option_id="authorize_execution",
                label="Authorize",
                description="Historical authorization fixture.",
                requires_rationale=False,
            ),
            ApprovalOption(
                option_id="reject_execution",
                label="Reject",
                description="Historical rejection fixture.",
                requires_rationale=False,
            ),
        ),
        requested_by=runtime.actor,
        idempotency_key="r4d-execution-identity:legacy-decision",
        compiled_identity=identity,
    )
    review = runtime.approvals.review(
        launch.approval_id, access_token=launch.access_token
    )
    runtime.approvals.record_ui_decision(
        approval_id=launch.approval_id,
        access_token=launch.access_token,
        csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce,
        selected_option="authorize_execution",
        rationale="",
        decided_by=LocalIdentityRef(
            identity_id="r4d_legacy_fixture",
            display_name="R4-D Legacy Fixture",
        ),
        ui_session_id="r4d-execution-identity-test",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="approval",
        name="legacy_decided.approval",
        object_id=launch.approval_id,
    )

    with pytest.raises(RootToolError, match="no compiled approval identity"):
        root.call_tool("execution_start", {"name": "legacy_decided"}, surface="execution")
    assert adapter.submit_count == 0
    assert root.call_tool(
        "execution_status", {"name": "legacy_decided"}
    , surface="execution")["state"] == "created"
