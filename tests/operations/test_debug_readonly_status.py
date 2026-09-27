import json
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_sha256
from scidiscovery.operation_contract import DiagnosticError
from tcad_artifact.local_debug_service import LocalTCADDebugService


def fixture(tmp_path, *, reservation=False, external=None, lookup=None):
    class Adapter:
        @property
        def policy(self):
            pytest.fail("status must not need policy discovery")
        def submit(self, *args):
            pytest.fail("status must never submit")
        def prepare(self, **kwargs):
            pytest.fail("status must never prepare")
        def collect(self, *args):
            pytest.fail("status must never collect")
        def lookup_submission(self, descriptor):
            if isinstance(lookup, Exception):
                raise lookup
            return lookup
        def status(self, external):
            return "succeeded"
    service = LocalTCADDebugService(adapter=Adapter(), exchange_root=tmp_path)
    context = SimpleNamespace(input_ref=lambda _: {"fixture":"exact-subject"})
    path = tmp_path / "budgets" / (canonical_sha256({"subject":context.input_ref("")}) + ".json")
    path.parent.mkdir()
    path.with_suffix(".lock").touch()
    record = {"run_id":"private-run", "external_run_id":external, "state":"accepted", "mode":"initialization"}
    ledger = {"runs":{}, "reservations":{}}
    if reservation:
        ledger["reservations"]["init"] = {"record":record, "submission":{
            "schema_version":1, "name":"submission", "local_path":"/private/submission.json",
            "media_type":"application/json", "size_bytes":1, "sha256":"a"*64}}
    if external:
        ledger["runs"]["init"] = record
    path.write_text(json.dumps(ledger))
    return service, context, path


@pytest.mark.parametrize("ledger_exists", [True, False])
def test_absent_diagnostic_never_contacts_remote(tmp_path, ledger_exists):
    service, context, path = fixture(tmp_path, lookup=AssertionError("remote should not be contacted"))
    if not ledger_exists:
        path.unlink()
    before = path.read_bytes() if path.exists() else None
    assert service.status(context, run_name="init") == {
        "name":"init", "state":"not_created", "submission":"not_submitted"}
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize("external,lookup,state", [
    (None, None, "not_created"),
    (None, ("private-job", "running"), "succeeded"),
    ("private-job", None, "succeeded"),
])
def test_reserved_diagnostic_status_is_observation_only(tmp_path, external, lookup, state):
    service, context, path = fixture(tmp_path, reservation=True, external=external, lookup=lookup)
    before = path.read_bytes()
    result = service.status(context, run_name="init")
    assert result["state"] == state and result["allowance_reserved"] is True
    assert "private" not in json.dumps(result)
    assert path.read_bytes() == before


def test_uncertain_lookup_is_not_reported_as_absent(tmp_path):
    service, context, path = fixture(tmp_path, reservation=True, lookup=TimeoutError("/private/endpoint"))
    before = path.read_bytes()
    with pytest.raises(DiagnosticError) as caught:
        service.status(context, run_name="init")
    assert caught.value.details[0]["code"] == "tcad_debug_status_unknown"
    assert "do not start" in str(caught.value) and "/private" not in str(caught.value)
    assert path.read_bytes() == before


def test_old_remote_runner_is_classified_at_policy_discovery(tmp_path):
    from tcad_artifact.ssh_transport import SSHTCADTransport, RemoteRunnerUpgradeRequired
    class OldRemote:
        def rpc(self, request):
            assert request["params"]["name"] == "tcad_execution_policy"
            return {"jsonrpc":"2.0", "id":request["id"], "error":{"message":"unknown runner tool"}}
    transport = SSHTCADTransport(OldRemote(), local_result_root=tmp_path)
    with pytest.raises(RemoteRunnerUpgradeRequired):
        transport.handle("execution_policy", {})


def test_runner_upgrade_diagnostic_survives_command_boundary(tmp_path, monkeypatch):
    import sys
    from tcad_artifact import command_adapter
    wire = {"schema_version":1, "operation":"execution_policy", "ok":False,
        "error_code":"tcad_runner_upgrade_required", "error":"/private/remote/config", "payload":{}}
    monkeypatch.setattr(command_adapter, "run_bounded", lambda *args, **kwargs:
        SimpleNamespace(returncode=0, stdout=json.dumps(wire).encode(), stderr=b""))
    adapter = command_adapter.CommandTCADExecutorAdapter(
        command_adapter.CommandAdapterConfig(executable=sys.executable), local_result_root=tmp_path)
    with pytest.raises(DiagnosticError) as caught:
        adapter.execution_policy()
    assert caught.value.details[0]["code"] == "tcad_runner_upgrade_required"
    assert "did not submit a job" in str(caught.value) and "/private" not in str(caught.value)
