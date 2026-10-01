"""Task identity is independent of the instance-wide diagnostic allowance."""
import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from scidiscovery.operation_contract import DiagnosticError
from tcad_artifact import local_debug_service as module
from tcad_artifact.debug_contract import PreparedTCADDebugRun, CollectedTCADDebugRun, CollectedTCADDebugFile, TCADDebugError
from tests.operations.tcad_policy_fixtures import policy_snapshot

SUBJECT = "one-instance"


def fixture(tmp_path, monkeypatch):
    project = canonical_json(dict(tool_profile="fixture", solver_kind="sprocess",
        files=[{"relative_path":"main.cmd", "content":"# fixture"}], entrypoint="main.cmd",
        resource_limits=dict(wall_time_seconds=1, cpu_time_seconds=1, max_memory_bytes=1024,
                             max_output_bytes=1024, max_storage_bytes=1024)))
    class Adapter:
        policy = policy_snapshot().debug
        def __init__(self):
            self.submitted, self.collected, self.cancelled, self.states = [], [], [], {}
        def prepare(self, **kwargs):
            path = kwargs["exchange_directory"] / "submission.json"
            path.write_bytes(project)
            return PreparedTCADDebugRun(LocalFileDescriptor(name="submission", local_path=str(path),
                media_type="application/json", size_bytes=len(project), sha256="a"*64), 1)
        def clamp_wall_time(self, prepared, **kwargs): return prepared
        def prepare_submission(self, prepared): return prepared.submission
        def submit(self, submission):
            self.submitted.append(submission.local_path)
            external = str(len(self.submitted))
            self.states[external] = "running"
            return external, "running"
        def lookup_submission(self, descriptor):
            if descriptor.local_path not in self.submitted: return None
            external = str(self.submitted.index(descriptor.local_path) + 1)
            return external, self.states[external]
        def status(self, external): return self.states[external]
        def cancel(self, external):
            self.cancelled.append(external)
            self.states[external] = "cancelled"
            return "cancelled"
        def collect_with_budget(self, external, **kwargs):
            self.collected.append(external)
            return CollectedTCADDebugRun("succeeded", 0, "complete", "job " + external, "job " + external,
                (CollectedTCADDebugFile("debug.log.txt", "text/plain", ("job " + external).encode()),))
    adapter = Adapter()
    service = module.LocalTCADDebugService(adapter=adapter, exchange_root=tmp_path / "exchange")
    monkeypatch.setattr(module, "_candidate", lambda _: (project, "b"*64, ()))
    monkeypatch.setattr(module, "_delivery_budget", lambda *args: {"effective_collection_bytes":1024})
    def context(owner, recovered=()):
        workspace = tmp_path / owner
        workspace.mkdir(exist_ok=True)
        return SimpleNamespace(run_id=owner, operation_id="experiment", workspace=workspace,
            remaining_seconds=100, state={"experiment_project":project.decode(),
                "experiment_implementation_ref":"same-sealed-implementation", "experiment_capability":b'{}'},
            recovery_authorized=lambda source: source == owner or source in recovered,
            record_activity=lambda _: None)
    path = service.exchange_root / "budgets" / (canonical_sha256({"subject":SUBJECT}) + ".json")
    return service, adapter, context, path


def run(service, context, name="probe"):
    return service.run(context, run_name=name, mode="preflight", budget_subject=SUBJECT)


def test_same_alias_has_independent_submission_collection_and_shared_budget(tmp_path, monkeypatch):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    first, second = context("first"), context("second")
    run(service, first)
    assert service.status(second, run_name="probe", budget_subject=SUBJECT)["state"] == "not_created"
    run(service, second)
    assert len(adapter.submitted) == 2
    run(service, first)
    assert len(adapter.submitted) == 2
    adapter.states.update({"1":"succeeded", "2":"succeeded"})
    assert run(service, first)["summary"] == "job 1"
    assert run(service, second)["summary"] == "job 2"
    assert adapter.collected == ["1", "2"]
    assert (first.workspace / "deck/reports/log-probe.txt").read_text() == "job 1"
    assert (second.workspace / "deck/reports/log-probe.txt").read_text() == "job 2"
    ledger = json.loads(path.read_bytes())
    assert len(ledger["reservations"]) == 2 and ledger["reserved_wall_seconds"] == 2
    ledger["debug_policy"]["max_runs"] = 2
    path.write_bytes(canonical_json(ledger))
    with pytest.raises(DiagnosticError) as error:
        run(service, context("third"))
    assert error.value.details[0]["code"] == "tcad_debug_attempts_exhausted"
    assert len(adapter.submitted) == 2


def test_authorized_restart_restores_receipt_without_resubmission_or_refund(tmp_path, monkeypatch):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    run(service, context("first"))
    adapter.states["1"] = "succeeded"
    assert run(service, context("first"))["summary"] == "job 1"
    before = path.read_bytes()
    restarted = module.LocalTCADDebugService(adapter=adapter, exchange_root=service.exchange_root)
    recovered = context("recovered", ("first",))
    assert restarted.status(recovered, run_name="probe", budget_subject=SUBJECT)["summary"] == "job 1"
    assert path.read_bytes() == before
    assert run(restarted, recovered)["summary"] == "job 1"
    assert len(adapter.submitted) == 1 and adapter.collected == ["1"]
    assert path.read_bytes() == before
    assert (recovered.workspace / "deck/reports/log-probe.txt").read_text() == "job 1"
    assert module.debug_response(recovered, "probe", {})["budget"]["created_runs"] == 1
    assert module.debug_response(recovered, "probe", {})["reserved_wall_seconds_for_run"] == 1


def test_pending_unknown_isolated_and_authorized_recovery_never_resubmits(tmp_path, monkeypatch):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    submit = adapter.submit
    def uncertain(descriptor):
        submit(descriptor)
        raise TimeoutError("ack lost")
    monkeypatch.setattr(adapter, "submit", uncertain)
    with pytest.raises(DiagnosticError) as error:
        run(service, context("first"))
    assert error.value.details[0]["code"] == "tcad_debug_submission_unknown"
    before = path.read_bytes()
    assert service.status(context("other"), run_name="probe", budget_subject=SUBJECT)["state"] == "not_created"
    assert service.status(context("recovery", ("first",)), run_name="probe", budget_subject=SUBJECT)["state"] == "running"
    assert path.read_bytes() == before
    assert run(service, context("recovery", ("first",)))["state"] == "running"
    assert len(adapter.submitted) == 1
    ledger = json.loads(path.read_bytes())
    assert ledger["reserved_wall_seconds"] == 1 and len(ledger["reservations"]) == 1


def test_absent_submission_retains_reservation_and_names_only_existing_repair_reads(tmp_path, monkeypatch):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    def uncertain(_):
        raise TimeoutError('No acknowledgement')
    monkeypatch.setattr(adapter, 'submit', uncertain)
    with pytest.raises(DiagnosticError):
        run(service, context('first'))
    before = path.read_bytes()
    with pytest.raises(DiagnosticError) as caught:
        run(service, context('recovery', ('first',)))
    wire = json.dumps(caught.value.details)
    assert 'tcad_debug_not_submitted' in wire
    assert 'run_status' in wire and 'no trusted absence-certification or refund entry point' in wire
    assert 'request control-side budget reconciliation' not in wire
    assert path.read_bytes() == before and adapter.submitted == []


@pytest.mark.parametrize("action", ["run", "status", "cancel"])
def test_ambiguous_authorized_lineage_is_rejected_before_remote_access(tmp_path, monkeypatch, action):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    run(service, context("first"))
    run(service, context("second"))
    before = path.read_bytes()
    recovered = context("recovered", ("first", "second"))
    monkeypatch.setattr(adapter, "status", lambda _: pytest.fail("ambiguous owner contacted"))
    with pytest.raises(DiagnosticError) as error:
        if action == "run": run(service, recovered)
        elif action == "status": service.status(recovered, run_name="probe", budget_subject=SUBJECT)
        else: service.experiment_activity({"recovered", "first", "second"}, SUBJECT,
            cancel=True, name="probe", current_run_id="recovered")
    assert error.value.details[0]["code"] == "tcad_debug_recovery_ambiguous"
    assert adapter.cancelled == [] and len(adapter.submitted) == 2
    assert path.read_bytes() == before


def test_cancel_name_selects_current_owner_and_keeps_other_reservation(tmp_path, monkeypatch):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    run(service, context("first"))
    run(service, context("second"))
    before = json.loads(path.read_bytes())
    assert not service.experiment_activity({"first", "second"}, SUBJECT, cancel=True,
        name="probe", current_run_id="second")
    assert adapter.cancelled == ["2"]
    assert service.status(context("first"), run_name="probe", budget_subject=SUBJECT)["state"] == "running"
    assert service.status(context("second"), run_name="probe", budget_subject=SUBJECT)["state"] == "cancelled"
    after = json.loads(path.read_bytes())
    assert after["reservations"] == before["reservations"] and after["reserved_wall_seconds"] == 2


@pytest.mark.parametrize("action", ["run", "status", "cancel"])
def test_incompatible_ledger_rejected_without_rewriting_allowance(tmp_path, monkeypatch, action):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    run(service, context("first"))
    ledger = json.loads(path.read_bytes())
    del ledger["schema_version"]
    path.write_bytes(canonical_json(ledger))
    before = path.read_bytes()
    with pytest.raises(TCADDebugError, match="Incompatible"):
        if action == "run": run(service, context("second"))
        elif action == "status": service.status(context("second"), run_name="probe", budget_subject=SUBJECT)
        else: service.experiment_activity({"first"}, SUBJECT, cancel=True, name="probe")
    assert path.read_bytes() == before and len(adapter.submitted) == 1 and not adapter.cancelled


def test_other_task_cannot_restore_terminal_receipt_just_for_same_implementation(tmp_path, monkeypatch):
    service, adapter, context, path = fixture(tmp_path, monkeypatch)
    run(service, context("first"))
    adapter.states["1"] = "succeeded"
    run(service, context("first"))
    other = context("other")
    assert service.status(other, run_name="probe", budget_subject=SUBJECT)["state"] == "not_created"
    assert run(service, other)["state"] == "running"
    assert len(adapter.submitted) == 2 and adapter.collected == ["1"]
    assert not (other.workspace / "deck/reports/log-probe.txt").exists()
