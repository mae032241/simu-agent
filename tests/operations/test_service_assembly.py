"""Runtime finalization and explicit cancellation use the same authority."""
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge


def test_additional_root_and_gateway_preserve_experiment_finalization_owner(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolFacade, RootMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_r4_experiment_task import _real_experiment

    def check(runtime, root, worker, instance, workspace, catalog, collected):
        coordinator = runtime.runs.experiment_executions
        original_services = coordinator.services_for
        second = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake,
            runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
            bindings=runtime.scheduler_bindings, instance=instance.instance_id,
            execution_bridge=coordinator.bridge, operation_catalog=catalog))
        UnifiedMCPRouter(second)
        assert runtime.runs.experiment_executions is coordinator
        assert coordinator.services_for is original_services
        class Diagnostic:
            active = True
            def experiment_activity(self, lineage, inputs, *, cancel=False):
                assert worker._run_id in lineage
                if cancel:
                    self.active = False
                return self.active
        activity = Diagnostic()
        coordinator.worker_services["fixture:diagnostic"] = activity
        (workspace / "output/result.json").write_text(json.dumps({"schema_version": 1,
            "payload": {"summary": "Pending.", "outcome": "blocked", "remaining_question": "Pending diagnostic."}}))
        assert worker.call_tool("worker_submit_result", {})["state"] == "rejected"
        # External completion, not Worker failure, releases finalization.
        activity.active = False
        assert runtime.runs.experiment_executions is coordinator
        return []  # The fixture now completes through this same require_idle owner.
    _real_experiment(tmp_path, monkeypatch, before_submit=check)


@pytest.mark.parametrize("lookup", [None, ("accepted-job", "running"), TimeoutError("lookup unknown")])
def test_cancel_or_abandon_never_submits_and_preserves_uncertainty(lookup):
    events = []
    status = SimpleNamespace(state="authorized", executor="fixture", external_run_id=None)
    def found(_):
        events.append("lookup")
        if isinstance(lookup, Exception):
            raise lookup
        return lookup
    def record(**kwargs):
        events.append("record")
        status.external_run_id = kwargs["external_run_id"]
        status.state = "submitted"
    def abandon(_, *, submission_confirmed_absent=False):
        assert submission_confirmed_absent is True
        events.append("abandon")
    executions = SimpleNamespace(status=lambda _: status, prepared_submission=lambda _: "exact-descriptor",
        abandon=abandon, record_submission=record,
        record_status=lambda **kwargs: setattr(status, "state", kwargs["state"]))
    adapter = SimpleNamespace(lookup_submission=found,
        submit=lambda *_: pytest.fail("cancellation must not submit"),
        cancel=lambda _: events.append("cancel") or "cancelled")
    bridge = ExecutionBridge(executions, adapters={"fixture": adapter})
    if isinstance(lookup, Exception):
        with pytest.raises(TimeoutError) as caught:
            bridge.cancel_or_abandon(execution_id="execution")
        assert caught.value.failure_stage == "submission_unknown"
        assert status.state == "authorized" and events == ["lookup"]
    else:
        bridge.cancel_or_abandon(execution_id="execution")
        assert events == (["lookup", "abandon"] if lookup is None else ["lookup", "record", "cancel"])


def test_root_and_standalone_worker_construct_their_coordinator_once(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent import runtime as runtime_module
    from scidiscovery.artifact_agent.interfaces.mcp import build_root_router
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import build_local_worker_router
    from scidiscovery.artifact_agent import runtime_plugin_bindings
    from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    monkeypatch.setattr(runtime_module, "compile_installed_catalog", lambda: catalog)
    secret = tmp_path / "secret"
    secret.write_bytes(b"s" * 32)
    secret.chmod(0o600)
    root = build_root_router(project_root=tmp_path, state_root=tmp_path / "state",
        approval_secret_file=secret, local_workspace_root=tmp_path / "workspaces", unified=True)
    coordinator = root.facade.runs.experiment_executions
    assert coordinator.runs is root.facade.runs
    assert coordinator.bridge is root.facade.execution_bridge
    assert callable(coordinator.services_for)
    monkeypatch.setattr(runtime_plugin_bindings, "load_runtime_plugin_contributions",
        lambda *args, **kwargs: SimpleNamespace(execution_adapters={}))
    operation = catalog.operation("science.experiment.v1")
    worker = build_local_worker_router(state_root=tmp_path / "state",
        operation_id=operation.spec.operation_id, operation_digest=operation.digest,
        operation_catalog=catalog, local_workspace_root=tmp_path / "workspaces",
        approval_secret_file=secret)
    owner = worker.router.runs
    assert owner.experiment_executions.runs is owner
    assert callable(owner.experiment_executions.services_for)
    assert owner.experiment_executions is not coordinator
