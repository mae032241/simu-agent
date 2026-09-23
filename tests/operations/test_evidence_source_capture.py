"""Capability grouping and real Run-owned source publication; no external network."""
import json
from pathlib import Path

import pytest

from scidiscovery import source_capture
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter, WorkerToolError
from scidiscovery.operations.tooling import operation_agent_type, operation_role_instructions
from tests.operations.test_l2_run_invariants import _system, _audit_envelope
from tests.operations.test_general_transform_operations import _intake


def open_extraction(tmp_path):
    catalog, runtime, instance, _, root = _system(tmp_path)
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    source = runtime.artifacts.register(b"Study the concentration profile.", ArtifactRegistration(
        kind="source", schema_id="opaque", payload_schema_version=1,
        media_type="text/plain", creator=runtime.actor), idempotency_key="source-question")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="source_paper", object_id=source.artifact_id)
    request = dict(name="evidence", instruction="Extract the bounded source facts.", operation_id="science.evidence.extract.v1",
        inputs=[dict(port="source_material", artifact_names=["source_paper"])])
    root.call_tool("operation_invoke", request)
    op = catalog.operation(request["operation_id"])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=op.spec.operation_id, operation_digest=op.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    return catalog, runtime, root, worker, opened, request


def mock_original(monkeypatch):
    def fetch(url, *, reserve_request, timeout):
        reserve_request(url)
        return b"Measured target at a bounded depth.", "text/plain", {
            "origin": "public_web", "url": url, "requested_url": url,
            "retrieved_at": "2026-09-17T01:00:00+00:00", "redirect_count": 0}
    monkeypatch.setattr(source_capture, "fetch_source", fetch)


def test_search_capture_publication_and_independent_audit(tmp_path, monkeypatch):
    mock_original(monkeypatch)
    catalog, runtime, root, worker, opened, _ = open_extraction(tmp_path)
    assignment = json.loads(Path(opened["assignment_path"]).read_bytes())
    assert assignment["role_instructions"] == operation_role_instructions(catalog.operation("science.evidence.extract.v1"))
    captured = worker.call_tool("worker_capture_source", {"url": "https://example.org/paper"})
    assert captured["source_alias"] == "tool_evidence_001"
    assert Path(captured["path"]).read_bytes() == b"Measured target at a bounded depth."
    again = worker.call_tool("worker_capture_source", {"url": "https://example.org/paper"})
    assert again == captured
    payload = _intake().model_dump(mode="json")
    payload["scientific_foundation"]["evidence"][0]["source_key"] = captured["source_alias"]
    payload["scientific_foundation"]["items"][0]["evidence_keys"] = [captured["source_alias"]]
    Path(opened["output_directory"], "result.json").write_text(json.dumps({"schema_version": 1,
        "handoff": {"verdict": "pass", "summary": "Bounded source fixture."}, "payload": payload}))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    status = root.call_tool("run_status", {"name": "evidence", "view": "detail"})
    assert status["state"] == "completed"
    sources = status["evidence_outputs"]
    source = next(x for x in sources if x["artifact_name"].endswith("." + captured["source_alias"]))
    manifest = next(x for x in sources if x["artifact_name"].endswith(".recovery_manifest"))
    # Exact output field names are provided by the control plane, never Worker-written.
    request = dict(name="audit", instruction="Independently audit the preserved source facts.", operation_id="science.evidence.audit.intake.v1", inputs=[
        dict(port="scientific_intake", artifact_names=["evidence.output"]),
        dict(port="source_material", artifact_names=["source_paper", source["artifact_name"]]),
        dict(port="source_manifest", artifact_names=[manifest["artifact_name"]])])
    root.call_tool("operation_invoke", request)
    review = catalog.operation(request["operation_id"])
    auditor = LocalWorkerMCPRouter(runtime.runs, operation_id=review.spec.operation_id, operation_digest=review.digest)
    audit_open = auditor.call_tool("worker_open_assignment", {})
    audit_assignment = json.loads(Path(audit_open["assignment_path"]).read_bytes())
    original = next(i for i in audit_assignment["inputs"] if i.get("source_provenance"))
    assert original["source_provenance"]["original_source_alias"] == captured["source_alias"]
    proof_input = next(i for i in audit_assignment["inputs"] if i["port"] == "source_manifest")
    proof = json.loads(Path(audit_open["workspace_path"], proof_input["relative_path"]).read_bytes())
    assert proof["records"][0]["metadata"]["url"] == "https://example.org/paper"
    assert proof["records"][0]["metadata"]["retrieved_at"]
    assert Path(audit_open["workspace_path"], original["relative_path"]).read_bytes() == Path(captured["path"]).read_bytes()
    assert "worker_capture_source" not in audit_assignment["tools"]
    with pytest.raises(WorkerToolError):
        auditor.call_tool("worker_capture_source", {"url": "https://example.org/other"})
    Path(audit_open["output_directory"], "result.json").write_bytes(_audit_envelope(original["source_name"]))
    assert auditor.call_tool("worker_submit_result", {})["state"] == "completed"


def test_failed_fetch_has_diagnostic_and_no_false_evidence(tmp_path, monkeypatch):
    _, runtime, _, worker, _, _ = open_extraction(tmp_path)
    def fail(*args, **kwargs):
        raise TimeoutError("source capture deadline exceeded")
    monkeypatch.setattr(source_capture, "fetch_source", fail)
    with pytest.raises((TimeoutError, WorkerToolError)):
        worker.call_tool("worker_capture_source", {"url": "https://example.org/paper"})
    assert runtime.runs.tool_evidence(worker._run_id) == []
    attempts = runtime.runs.tool_attempts(worker._run_id)
    assert attempts[-1]["state"] == "rejected"
    assert "deadline" in json.dumps(attempts[-1])


def test_fetched_evidence_survives_bounded_recovery(tmp_path, monkeypatch):
    mock_original(monkeypatch)
    catalog, runtime, root, worker, _, request = open_extraction(tmp_path)
    captured = worker.call_tool("worker_capture_source", {"url": "https://example.org/paper"})
    prior = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(prior.run_id, reason="fixture interruption",
        expected_state=prior.state, expected_last_activity_at=prior.last_activity_at)
    root.call_tool("operation_invoke", {**request, "name": "continued", "draft_from": "evidence", "max_attempts": 2})
    op = catalog.operation(request["operation_id"])
    following = LocalWorkerMCPRouter(runtime.runs, operation_id=op.spec.operation_id, operation_digest=op.digest)
    original_compiled = runtime.runs._compiled
    def current_contract_only(value):
        if value.run_id == prior.run_id:
            raise AssertionError("Historical source recovery must not recompile its old producer")
        return original_compiled(value)
    monkeypatch.setattr(runtime.runs, "_compiled", current_contract_only)
    following.call_tool("worker_open_assignment", {})
    receipt = runtime.runs.tool_evidence(following._run_id)[0]
    assert receipt["alias"] == captured["source_alias"] and receipt["source_ref"] is None
    assert receipt["metadata"]["origin"] == "public_web"
    assert following.call_tool("worker_capture_source", {"url": "https://example.org/paper"})["source_alias"] == receipt["alias"]


@pytest.mark.parametrize("url", ["http://example.org", "file:///etc/passwd", "https://user:pass@example.org", "https://example.org:8443/"])
def test_capture_rejects_non_public_url_shapes(url):
    with pytest.raises(ValueError):
        source_capture.public_source_url(url)


def test_capture_rejects_private_dns_and_redirect_targets(monkeypatch):
    monkeypatch.setattr(source_capture, "_resolve_addresses", lambda *a, **k: ["127.0.0.1"])
    with pytest.raises(ValueError, match="non-public"):
        source_capture.fetch_source("https://example.org/", reserve_request=lambda _: None, timeout=1)


def test_native_profiles_share_roles_but_keep_operation_identity(tmp_path):
    catalog, _, _, _, _ = _system(tmp_path)
    operations = [catalog.operation(key) for key in catalog.operation_ids() if catalog.operation(key).spec.executor.kind == "agent"]
    assert len({operation_agent_type(op) for op in operations}) < len(operations)
    extract = catalog.operation("science.evidence.extract.v1")
    audit = catalog.operation("science.evidence.audit.intake.v1")
    assert extract.spec.executor.native_tools.web_search == "live"
    assert audit.spec.executor.native_tools.web_search == "disabled"
    assert operation_agent_type(extract) != operation_agent_type(audit)
    assert "ScientificIntake" in operation_role_instructions(extract)


def test_request_budget_survives_worker_reconnection(tmp_path, monkeypatch):
    catalog, runtime, _, worker, _, _ = open_extraction(tmp_path)
    def fail(url, *, reserve_request, timeout):
        reserve_request(url)
        raise TimeoutError("fixture remote timeout")
    monkeypatch.setattr(source_capture, "fetch_source", fail)
    for _ in range(24):
        with pytest.raises(WorkerToolError, match="timeout"):
            worker.call_tool("worker_capture_source", {"url": "https://example.org/paper"})
    op = catalog.operation("science.evidence.extract.v1")
    reopened = LocalWorkerMCPRouter(runtime.runs, operation_id=op.spec.operation_id, operation_digest=op.digest)
    reopened.call_tool("worker_open_assignment", {})
    with pytest.raises(WorkerToolError, match="request budget exhausted"):
        reopened.call_tool("worker_capture_source", {"url": "https://example.org/paper"})
    assert runtime.runs.tool_evidence(reopened._run_id) == []


def test_captured_pdf_uses_existing_pdf_reader(tmp_path, monkeypatch):
    from tests.operations.test_l2_run_invariants import _minimal_pdf
    def fetch(url, *, reserve_request, timeout):
        reserve_request(url)
        return _minimal_pdf("Frozen fetched source"), "application/pdf", {
            "origin": "public_web", "url": url, "requested_url": url,
            "retrieved_at": "2026-09-17T01:00:00+00:00"}
    monkeypatch.setattr(source_capture, "fetch_source", fetch)
    _, _, _, worker, _, _ = open_extraction(tmp_path)
    captured = worker.call_tool("worker_capture_source", {"url": "https://example.org/paper.pdf"})
    result = worker.call_tool("worker_extract_pdf_text", {"name": captured["source_alias"]})
    assert "Frozen fetched source" in Path(result["local_path"]).read_text()


def test_http_redirect_to_private_address_is_never_connected(monkeypatch):
    def addresses(host, *args, **kwargs):
        return ["93.184.216.34" if host == "example.org" else "127.0.0.1"]
    monkeypatch.setattr(source_capture, "_resolve_addresses", addresses)
    connected = []
    class Redirect:
        status = 302
        def getheader(self, name):
            return "https://internal.example/secret"
    class Connection:
        def __init__(self, host, address, timeout): connected.append(address)
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Redirect()
        def close(self): pass
    monkeypatch.setattr(source_capture, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(ValueError, match="non-public"):
        source_capture.fetch_source("https://example.org/", reserve_request=lambda _: None, timeout=5)
    assert connected == ["93.184.216.34"]


def test_installed_source_tool_and_profiles_share_compiled_policy(installed_probe):
    installed_probe("all_domains", r'''
import tempfile, tomllib
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_agent_type
from scidiscovery.platforms.codex import initialize, validate_installation_profile
from scidiscovery.platforms.scheduler_prompt import load_scheduler_guides
from scidiscovery.source_capture import SOURCE_CAPTURE_TOOL, SourceCaptureInput
catalog = compile_installed_catalog()
root = Path(tempfile.mkdtemp(prefix="installed-capability-roles-"))
initialize(root, control_socket=root / "control.sock", state_root=root / "state", operation_catalog=catalog)
roles = list((root / ".codex/agents").glob("*.toml"))
assert len(roles) == 3
extract = catalog.operation("science.evidence.extract.v1")
assert SOURCE_CAPTURE_TOOL.name in {tool.name for tool in extract.worker_tools}
assert SourceCaptureInput.model_json_schema()["properties"]["url"]["maxLength"] == 2048
profile = tomllib.loads((root / ".codex/agents" / (operation_agent_type(extract) + ".toml")).read_text())
assert profile["web_search"] == "live"
assert "role_instructions" in profile["developer_instructions"]
assert "ScientificIntake" not in profile["developer_instructions"]
prompt = (root / "AGENTS.md").read_text()
guides = load_scheduler_guides()
assert set(guides) == {"research.md", "inputs.md", "results.md", "dispatch.md",
                       "recovery.md", "execution.md", "evidence.md", "domain-analysis.md"}
for name, content in guides.items():
    assert (root / ".codex/scidiscovery-guides" / name).read_text() == content
    assert content.strip() not in prompt
assert str(root / ".codex/scidiscovery-guides") in prompt
for key in catalog.operation_ids():
    operation = catalog.operation(key)
    if operation.spec.executor.kind == "agent" and operation is not extract:
        assert operation.spec.executor.native_tools.web_search == "disabled"
print("installed capability profiles and preserved-source tool: pass")
''')
