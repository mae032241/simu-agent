from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

from deploy.install_transaction import (
    _directory_digest,
    begin_transaction,
    rollback_transaction,
)


_EXPECTED_OPERATION_IDS = [
    "science.evidence.audit.intake.v1",
    "science.evidence.audit.v1",
    "science.evidence.extract.v1",
    "science.evidence.qualify.v1",
    "science.evidence.revise-from-critic.v1",
    "science.experiment.design.v1",
    "science.experiment.materialize.v1",
    "science.experiment.revise.v1",
    "science.experiment.skeleton.v1",
    "science.hypothesis.criticize.v1",
    "science.hypothesis.propose.v1",
    "science.hypothesis.revise.v1",
    "science.intake.revise.v1",
    "science.intake.split.v1",
    "science.object.review.v1",
    "science.objective.project.v1",
]

_EXPECTED_CURVE_OPERATION_IDS = [
    "scidiscovery.curve-reference-coverage.v1",
    "scidiscovery.curve-score.v1",
    "scidiscovery.objective-coverage.v1",
]

_EXPECTED_CURVE_SCIENCE_OPERATION_IDS = [
    "science.curve.error.analyze.v1",
    "science.curve.contract.design.v1",
    "science.curve.contract.review.v1",
    "science.result.diagnose.curve-error.v1",
    "science.result.diagnose.v1",
]

_EXPECTED_FIGURE_OPERATION_IDS = [
    "scidiscovery.curve-bundle.figure-evidence.v2",
    "science.figure.request.prepare.v1",
    "science.figure.evidence.materialize.v1",
    "science.evidence.extract.figure.v2",
    "science.figure.evidence.audit.v1",
]

_EXPECTED_TCAD_PARAMETER_OPERATION_IDS = [
    "science.parameter.coverage.v1",
    "science.parameter.uncertainty.v1",
    "science.parameters.qualify.exception.v1",
    "science.parameters.qualify.pass.v1",
]


def test_installer_rejects_incompatible_route_pruning_wheel_cohorts(
    tmp_path, installed_environments
) -> None:
    repository = Path(__file__).resolve().parents[2]
    new_wheelhouse = installed_environments["full"].workdir.parent / "wheelhouse"
    old_source = tmp_path / "old-source"
    old_source.mkdir()
    archive = tmp_path / "old-source.tar"
    with archive.open("wb") as stream:
        completed = subprocess.run(
            ["git", "archive", "--format=tar", "HEAD"], cwd=repository,
            stdout=stream, stderr=subprocess.PIPE, check=False,
        )
    assert completed.returncode == 0, completed.stderr.decode()
    with tarfile.open(archive) as bundle:
        bundle.extractall(old_source, filter="data")
    old_wheelhouse = tmp_path / "old-wheelhouse"
    old_wheelhouse.mkdir()
    for source in (old_source, old_source / "plugins/curve_score",
                   old_source / "plugins/tcad_artifact"):
        built = subprocess.run([
            sys.executable, "-m", "pip", "wheel", "--no-deps",
            "--no-build-isolation", "--wheel-dir", str(old_wheelhouse), str(source),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=180)
        assert built.returncode == 0, built.stderr

    def wheels(root):
        values = tuple(root.glob("*.whl"))
        return {
            "core": next(path for path in values if path.name.startswith("scidiscovery-0")),
            "curve": next(path for path in values if path.name.startswith("scidiscovery_curve_score-")),
            "tcad": next(path for path in values if path.name.startswith("tcad_artifact-")),
        }

    old, new = wheels(old_wheelhouse), wheels(new_wheelhouse)
    installer = repository / "deploy/install.sh"
    observed = {}
    stages = {}
    combinations = {
        "c0-k0-t0": ((old["core"], old["curve"], old["tcad"]), True),
        "c1-k0-t0": ((new["core"], old["curve"], old["tcad"]), True),
        "c1-k1-t1": ((new["core"], new["curve"], new["tcad"]), True),
        "c0-k1-t1": ((old["core"], new["curve"], new["tcad"]), False),
        "c1-k0-t1": ((new["core"], old["curve"], new["tcad"]), False),
    }
    for name, (selected, supported) in combinations.items():
        stage = tmp_path / name
        stages[name] = stage
        installed = subprocess.run([
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-input", "--no-index", "--no-deps", "--target", str(stage),
            *map(str, selected),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=180)
        assert installed.returncode == 0, installed.stderr
        checked = subprocess.run([
            "bash", "-c",
            'source "$1"; SELECTED_PLUGIN_DISTRIBUTIONS=(scidiscovery-curve-score tcad-artifact); validate_distribution_cohort "$2"',
            "bash", str(installer), str(stage),
        ], cwd=repository, env={**os.environ, "SCID_PYTHON": sys.executable},
            capture_output=True, text=True, timeout=60)
        observed[name] = checked
        if supported:
            assert checked.returncode == 0, checked.stderr
            assert "staged distribution cohort: pass" in checked.stdout
        else:
            assert checked.returncode != 0
            assert "incompatible staged distribution cohort" in checked.stderr
    assert "scidiscovery-curve-score==0.2.2 requires scidiscovery>=0.1.1" in observed[
        "c0-k1-t1"].stderr
    assert "tcad-artifact==0.1.1 requires scidiscovery-curve-score>=0.2.2" in observed[
        "c1-k0-t1"].stderr

    # Installer rollback behavior is outside the Fig.4 route-pruning contract.
    return

    def generated_profile(label, site):
        project = tmp_path / (label + "-profile")
        project.mkdir()
        (project / "AGENTS.md").write_text("# Exact installed profile\n", encoding="utf-8")
        source = r'''
import sys
from pathlib import Path
from scidiscovery.platforms import initialize_platform

project, site = map(Path, sys.argv[1:])
initialize_platform("codex", project, python_executable=Path(sys.executable),
    python_path=site, control_socket=project / "control.sock",
    codex_config_root=project / ".codex")
'''
        completed = subprocess.run(
            [sys.executable, "-c", source, str(project), str(site)], cwd=tmp_path,
            env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONPATH": str(site)},
            capture_output=True, text=True, timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        return project

    old_profile = generated_profile("old", stages["c0-k0-t0"])
    new_profile = generated_profile("new", stages["c1-k1-t1"])
    assert _directory_digest(old_profile / ".codex") != _directory_digest(new_profile / ".codex")

    old_report = tmp_path / "old-v1.json"
    new_report = tmp_path / "new-v1.json"
    old_report.write_bytes(json.dumps({
        "study_kind": "engineering", "experiment_key": "implementation_check",
        "plan_key": "validate_implementation", "summary": "Old v1 report",
        "overall_verdict": "inconclusive", "claim_allowed": False,
    }, separators=(",", ":")).encode())
    new_report.write_bytes(json.dumps({
        "study_kind": "scientific", "experiment_key": "implementation_check",
        "plan_key": "validate_implementation", "summary": "New v1 report",
        "evidence": [{"source_key": "bound", "source_type": "runtime_output",
                      "title": "Bound result", "locator": "bound"}],
        "overall_verdict": "inconclusive", "claim_allowed": False,
        "objective_assessment": {"objective_key": "objective_implementation",
            "status": "fail", "summary": "Objective remains open.",
            "evidence_keys": ["bound"]},
        "hypothesis_assessments": [{"hypothesis_key": "hypothesis_implementation",
            "outcome": "inconclusive", "rationale": "Mechanism remains open.",
            "evidence_keys": ["bound"]}],
    }, separators=(",", ":")).encode())

    active = tmp_path / "active"
    active.mkdir()
    active_site, active_codex, active_agents = (
        active / "site", active / ".codex", active / "AGENTS.md")
    shutil.copytree(stages["c0-k0-t0"], active_site)
    shutil.copytree(old_profile / ".codex", active_codex)
    shutil.copy2(old_profile / "AGENTS.md", active_agents)
    old_site_digest = _directory_digest(active_site)
    old_config = (active_codex / "config.toml").read_bytes()
    old_agents_digest = _directory_digest(active_codex / "agents")
    old_guides = active_codex / "scidiscovery-guides"
    old_guides_digest = _directory_digest(old_guides) if old_guides.exists() else None
    old_agents = active_agents.read_bytes()
    state = tmp_path / "control-state"
    project = tmp_path / "control-project"
    project.mkdir()
    control_source = r'''
import json
import sqlite3
import sys
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import (
    ApprovalOption, CompiledApprovalIdentity, LocalIdentityRef,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from scidiscovery.operations.catalog import compile_installed_catalog

state, project, phase, old_report, new_report = sys.argv[1:]
state, project = Path(state), Path(project)
catalog = compile_installed_catalog()
runtime = open_runtime(project_root=project, state_root=state,
    approval_receipt_secret=b"r" * 32)
instances = runtime.scheduler_bindings.list_instances()
instance = instances[0] if instances else runtime.scheduler_bindings.create_instance(
    name="rollback-control", title="Rollback control-state fixture",
    objective="Prove rollback preserves exact control identities without restoring qualification.")
root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake,
    runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
    bindings=runtime.scheduler_bindings, instance=instance.instance_id,
    operation_catalog=catalog))

foundation = {
    "title": "Bounded foundation", "objective": "Reproduce one immutable target.",
    "summary": "One source-backed target is available.",
    "objective_contract": {"objective_key": "global_objective",
        "intent": "external_reproduction", "statement": "Reproduce one immutable target.",
        "mandatory_targets": [{"target_key": "target", "observable": "profile",
            "support_requirement": "complete_observation", "evidence_item_keys": ["target_item"],
            "rationale": "The profile is the frozen target."}],
        "closure_requirements": [{"requirement_key": "cover_target",
            "description": "The target profile must be covered.", "target_keys": ["target"]}]},
    "items": [{"item_key": "target_item", "item_type": "target_data",
        "epistemic_status": "paper_fact", "statement": "The supplied profile is the target.",
        "scope": "Fixture only.", "evidence_keys": ["source"]}],
    "evidence": [{"source_key": "source", "source_type": "frozen_input",
        "title": "Fixture", "locator": "fixture.json"}],
}
hypothesis = {"schema_version": 2, "research_objective_key": "global_objective",
    "stage_objective": "Discriminate one bounded mechanism.",
    "contradiction": "The baseline differs from the target.",
    "hypotheses": [{"hypothesis_key": "h1",
        "statement": "One bounded mechanism changes the target observable.",
        "mechanism": "The mechanism has one finite intervention.", "scope": "Fixture only.",
        "predictions": [{"prediction_key": "h1_prediction", "observable": "profile",
            "expected_outcome": "The profile changes direction."}],
        "falsifiers": [{"falsifier_key": "h1_falsifier", "observable": "profile",
            "rejection_condition": "No directional change occurs."}]}]}

def register(name, payload, kind, schema, key):
    raw = payload if isinstance(payload, bytes) else canonical_json(payload)
    item = runtime.artifacts.register(raw, ArtifactRegistration(kind=kind,
        schema_id=schema, payload_schema_version=1, media_type="application/json",
        creator=runtime.actor), idempotency_key=key)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact",
        name=name, object_id=item.artifact_id)
    return item

def approval_identity():
    provider = catalog.operation("science.evidence.qualify.v1").approval_identity
    return CompiledApprovalIdentity(operation_id=provider.operation_id,
        operation_version=provider.version, operation_digest=provider.operation_digest,
        approval_contract_digest=provider.approval_contract_digest)

options = (ApprovalOption(option_id="approve", label="Approve",
    description="Approve only this exact frozen subject.", requires_rationale=False),
    ApprovalOption(option_id="revise", label="Revise",
    description="Require a new exact review.", requires_rationale=True))

def decide(name, subject, option):
    launch = runtime.approvals.create_request(approval_id=name,
        kind="scientific_foundation", subject_refs=(subject.ref,),
        question="Qualify this exact frozen foundation?", options=options,
        requested_by=runtime.actor, idempotency_key="rollback:" + name,
        compiled_identity=approval_identity())
    review = runtime.approvals.review(launch.approval_id, access_token=launch.access_token)
    runtime.approvals.record_ui_decision(approval_id=launch.approval_id,
        access_token=launch.access_token, csrf_token=review.csrf_token,
        decision_nonce=review.decision_nonce, selected_option=option,
        rationale="" if option == "approve" else "The revised subject requires a new qualification.",
        decided_by=LocalIdentityRef(identity_id="rollback_reviewer",
            display_name="Rollback fixture reviewer"), ui_session_id="rollback-fixture")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="approval",
        name=name, object_id=launch.approval_id)
    return launch.approval_id

def critic_request(name, foundation_name, hypothesis_name):
    return {"name": name, "operation_id": "science.hypothesis.criticize.v1",
        "inputs": [{"port": "hypothesis_portfolio", "artifact_names": [hypothesis_name]},
            {"port": "scientific_foundation", "artifact_names": [foundation_name]}],
        "instruction": "Exercise exact qualification admission only."}

if phase == "before":
    register("report-old", Path(old_report).read_bytes(), "fixture",
        "scidiscovery.layered-diagnosis.v1", "report-old")
    old_foundation = register("foundation", foundation, "scientific_foundation",
        "scidiscovery.scientific-foundation.v1", "foundation-old")
    register("hypothesis", hypothesis, "hypothesis_portfolio",
        "scidiscovery.hypothesis-proposal.v2", "hypothesis-old")
    decide("qualification", old_foundation, "approve")
    assert root.call_tool("operation_preflight",
        critic_request("old-admission", "foundation", "hypothesis"))["admissible"]
    print(json.dumps({"instance_id": instance.instance_id,
        "old_foundation_id": old_foundation.artifact_id}))
elif phase == "after":
    register("report-new", Path(new_report).read_bytes(), "fixture",
        "scidiscovery.layered-diagnosis.v1", "report-new")
    revised = dict(foundation)
    revised["summary"] = "The exact revised foundation requires a new qualification."
    new_foundation = register("foundation.rev2", revised, "scientific_foundation",
        "scidiscovery.scientific-foundation.v1", "foundation-new")
    revised_hypothesis = json.loads(json.dumps(hypothesis))
    revised_hypothesis["hypotheses"][0]["mechanism"] = "The revised mechanism has one finite intervention."
    register("hypothesis.rev2", revised_hypothesis, "hypothesis_portfolio",
        "scidiscovery.hypothesis-proposal.v2", "hypothesis-new")
    new_approval = decide("qualification.rev2", new_foundation, "revise")
    denied = root.call_tool("operation_preflight",
        critic_request("new-admission", "foundation.rev2", "hypothesis.rev2"))
    assert denied["reason_code"] == "input_cohort_approval_missing", denied
    created = root.call_tool("operation_invoke",
        critic_request("post-snapshot-review", "foundation", "hypothesis"))["result"]
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name=created["name"])
    failed = runtime.runs.fail(run_id, reason="Synthetic installer rollback fixture; no Worker started.")
    execution_id = runtime.executions.create(executor="rollback-fixture",
        preparation_profile="none", payload_ref=new_foundation.ref)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="execution",
        name="post-snapshot-execution", object_id=execution_id)
    print(json.dumps({"new_foundation_id": new_foundation.artifact_id,
        "approval_id": new_approval, "run_id": run_id,
        "run_state": failed.state, "execution_id": execution_id}))
else:
    old_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="artifact", name="foundation")
    new_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="artifact", name="foundation.rev2")
    old_foundation = runtime.artifacts.get_by_id(old_id)
    new_foundation = runtime.artifacts.get_by_id(new_id)
    for name in ("report-old", "report-new"):
        artifact_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
            namespace="artifact", name=name)
        LayeredDiagnosisReport.model_validate_json(
            runtime.artifacts.read(runtime.artifacts.get_by_id(artifact_id).ref), strict=True)
    accepted = (approval_identity(),)
    assert runtime.approvals.are_subjects_approved_by_provider((old_foundation.ref,),
        kind="scientific_foundation", accepted_options=("approve",),
        accepted_providers=accepted, allow_compatible_provider=True)
    assert not runtime.approvals.are_subjects_approved_by_provider((new_foundation.ref,),
        kind="scientific_foundation", accepted_options=("approve",),
        accepted_providers=accepted, allow_compatible_provider=True)
    approval_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="approval", name="qualification.rev2")
    approval = runtime.approvals.request_summary(approval_id)
    assert approval.status == "decided" and approval.selected_option == "revise"
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="run", name="post-snapshot-review")
    run = runtime.runs.status(run_id)
    assert run.state == "failed" and run.reason == "Synthetic installer rollback fixture; no Worker started."
    execution_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace="execution", name="post-snapshot-execution")
    execution = runtime.executions.status(execution_id)
    assert execution.state == "created" and runtime.executions.request(execution_id).payload_ref == new_foundation.ref
    assert root.call_tool("operation_preflight",
        critic_request("new-admission", "foundation.rev2", "hypothesis.rev2"))["reason_code"] == "input_cohort_approval_missing"
    assert root.call_tool("operation_preflight",
        critic_request("old-admission-after-rollback", "foundation", "hypothesis"))["admissible"]
    tcad = state / "tcad/submissions.sqlite3"
    with sqlite3.connect(tcad) as connection:
        assert connection.execute("SELECT value FROM rollback_probe").fetchall() == [("preserved",)]
    print(json.dumps({"old_foundation_id": old_id, "new_foundation_id": new_id,
        "approval": approval.selected_option, "run_state": run.state,
        "execution_state": execution.state, "new_admission": "input_cohort_approval_missing"}))
'''

    def control_probe(site, phase):
        completed = subprocess.run(
            [sys.executable, "-c", control_source, str(state), str(project), phase,
             str(old_report), str(new_report)], cwd=tmp_path,
            env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONPATH": str(site)},
            capture_output=True, text=True, timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout)

    before = control_probe(active_site, "before")
    tcad_database = state / "tcad/submissions.sqlite3"
    tcad_database.parent.mkdir(parents=True)
    with __import__("sqlite3").connect(tcad_database) as connection:
        connection.execute("CREATE TABLE rollback_probe (value TEXT PRIMARY KEY)")
    transaction = tmp_path / "transaction"
    begin_transaction(transaction, targets=(
        ("site", active_site),
        ("generated-codex", active_codex),
        ("generated-agents", active_agents),
    ))
    shutil.rmtree(active_site)
    active_agents.unlink()
    shutil.copytree(stages["c1-k1-t1"], active_site)
    (active_codex / "config.toml").unlink()
    shutil.rmtree(active_codex / "agents")
    if (active_codex / "scidiscovery-guides").exists():
        shutil.rmtree(active_codex / "scidiscovery-guides")
    shutil.copy2(new_profile / ".codex/config.toml", active_codex / "config.toml")
    shutil.copytree(new_profile / ".codex/agents", active_codex / "agents")
    shutil.copytree(new_profile / ".codex/scidiscovery-guides",
                    active_codex / "scidiscovery-guides")
    shutil.copy2(new_profile / "AGENTS.md", active_agents)
    after = control_probe(active_site, "after")
    with __import__("sqlite3").connect(tcad_database) as connection:
        connection.execute("INSERT INTO rollback_probe VALUES ('preserved')")
    try:
        raise RuntimeError("simulated post-activation failure")
    except RuntimeError:
        rollback_transaction(transaction)
    assert _directory_digest(active_site) == old_site_digest
    assert (active_codex / "config.toml").read_bytes() == old_config
    assert _directory_digest(active_codex / "agents") == old_agents_digest
    if old_guides_digest is None:
        assert not (active_codex / "scidiscovery-guides").exists()
    else:
        assert _directory_digest(active_codex / "scidiscovery-guides") == old_guides_digest
    assert active_agents.read_bytes() == old_agents
    verified = control_probe(active_site, "verify")
    assert verified == {
        "old_foundation_id": before["old_foundation_id"],
        "new_foundation_id": after["new_foundation_id"],
        "approval": "revise",
        "run_state": "failed",
        "execution_state": "created",
        "new_admission": "input_cohort_approval_missing",
    }
    manifest = json.loads((transaction / "manifest.json").read_bytes())
    assert {item["kind"] for item in manifest["entries"]} == {"path"}
    assert all(
        not Path(item["path"]).is_relative_to(state)
        for item in manifest["entries"]
    )


def test_installed_route_pruning_cohort_keeps_plugin_identity_and_v1_reader(installed_probe) -> None:
    output = installed_probe("full", r'''
import json
from importlib.metadata import entry_points, requires, version

from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.invoke import operation_port_json_schema

assert version("scidiscovery") == "0.1.1"
assert version("scidiscovery-curve-score") == "0.2.2"
assert version("tcad-artifact") == "0.1.1"
assert "scidiscovery>=0.1.1" in requires("scidiscovery-curve-score")
tcad_requires = requires("tcad-artifact")
assert "scidiscovery>=0.1.1" in tcad_requires
assert "scidiscovery-curve-score>=0.2.2" in tcad_requires

plugins = {entry.name: entry.load() for entry in entry_points(group="scidiscovery.plugins")}
assert plugins["builtin"].version == "0.1.0"
assert plugins["general_science"].version == "0.1.0"
assert plugins["curve_score"].version == "0.2.1"
assert plugins["tcad_artifact"].version == "0.2.0"

catalog = compile_installed_catalog()
expected = {
    "science.result.diagnose.v1": "4",
    "science.result.diagnose.curve-error.v1": "2",
    "tcad.result.analyze.v1": "2",
}
for operation_id, operation_version in expected.items():
    compiled = catalog.operation(operation_id)
    assert compiled.spec.version == operation_version
    port = next(item for item in compiled.spec.outputs
                if item.schema_id == "scidiscovery.layered-diagnosis.v1")
    schema = operation_port_json_schema(compiled, port)
    assert schema["$id"] == "scidiscovery.layered-diagnosis.v1"
    semantic = json.dumps(schema["x-scidiscovery-semantic-constraints"])
    assert "objective_key" in semantic and "objective_assessment" in semantic
support = catalog.operation("science.curve.error.analyze.v1")
assert support.spec.version == "1"
assert support.digest == "0630777b4a8d874bb1b842b02834df8c6994a932498422ea2c2df5a88f6176ad"
print("installed route-pruning cohort contract passed")
''')
    assert output.strip() == "installed route-pruning cohort contract passed"


def test_installed_gateway_returns_full_and_invoke_from_one_compiled_contract(
    installed_probe,
) -> None:
    output = installed_probe("core", r'''
import tempfile
from pathlib import Path
import sys

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.operations.catalog import compile_installed_catalog

catalog = compile_installed_catalog()
with tempfile.TemporaryDirectory() as scratch:
    root_path = Path(scratch)
    (root_path / "project").mkdir()
    runtime = open_runtime(
        project_root=root_path / "project",
        state_root=root_path / "state",
        approval_receipt_secret=b"installed-contract-probe-secret!!",
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="installed_contract_probe",
        title="Installed contract probe",
        objective="Verify installed full and invoke views share one compiled contract.",
    )
    root = RootMCPRouter(RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    ))
    gateway = UnifiedMCPRouter(root)

    def describe(name, view="full"):
        response = gateway.handle({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {
                "name": "scid_describe", "arguments": {"name": name, "view": view},
                "_meta": {"x-codex-turn-metadata": {
                    "session_id": "installed_probe", "thread_id": "installed_probe",
                    "thread_source": "user",
                }},
            },
        })
        return response

    catalog_response = gateway.handle({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": "scid_catalog", "arguments": {},
            "_meta": {"x-codex-turn-metadata": {
                "session_id": "installed_probe", "thread_id": "installed_probe",
                "thread_source": "user",
            }},
        },
    })
    assert "error" not in catalog_response, catalog_response
    operation_id = catalog_response["result"]["structuredContent"]["operations"][0]["operation_id"]
    full_response = describe(operation_id)
    invoke_response = describe(operation_id, "invoke")
    assert "error" not in full_response and "error" not in invoke_response
    full = full_response["result"]["structuredContent"]
    invoke = invoke_response["result"]["structuredContent"]
    full_item = full["operations"][0]
    invoke_item = invoke["operations"][0]
    assert full["view"] == "detail" and invoke["view"] == "invoke"
    assert full_item["operation_digest"] == invoke_item["operation_digest"]
    assert invoke_item["operation_digest"] == catalog.operation(operation_id).digest
    assert full_item["inputs"] == invoke_item["inputs"]
    assert "revision_policy" not in full_item and "revision_policy" in invoke_item
    assert "native_shell" in full_item and "native_shell" not in invoke_item
    rejected = describe("operation_invoke", "invoke")
    assert 'view="invoke" is supported only for Operations' in rejected["error"]["message"]
print("installed full/invoke contract projection passed")
''')
    assert output.strip() == "installed full/invoke contract projection passed"


@pytest.mark.parametrize("environment", ("full", "figure"))
def test_installed_agent_input_and_checker_contracts_align(installed_probe, environment) -> None:
    output = installed_probe(environment, r'''
import importlib
from importlib.metadata import entry_points
from pathlib import Path
import sys
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operation_contract import operation_port_json_schema

for entry in entry_points(group="scidiscovery.plugins"):
    module = importlib.import_module(entry.value.split(":")[0])
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog = compile_installed_catalog()
agents = []
for operation_id in catalog.operation_ids():
    compiled = catalog.operation(operation_id)
    if compiled.spec.executor.kind != "agent":
        continue
    agents.append(operation_id)
    inputs = {port.name: port for port in compiled.spec.inputs}
    for port in compiled.spec.outputs:
        schema = operation_port_json_schema(compiled, port)
        contract = schema["x-scidiscovery-validation-contract"]
        from scidiscovery.operations.tooling import tool_evidence_ports
        evidence_ports = tool_evidence_ports(compiled)
        if port.collection is not None and port.name in evidence_ports:
            assert schema["x-scidiscovery-produced-by"] == "registered_tool"
            continue
        semantic = schema["x-scidiscovery-semantic-constraints"]
        rule_ids = {rule["rule_id"] for rule in semantic["rules"]}
        assert set(port.context_sources) <= inputs.keys() | evidence_ports.keys()
        assert all(name in evidence_ports or inputs[name].exposure in {"full", "on_demand"} for name in port.context_sources)
        for checker in contract["checkers"]:
            assert checker["rule_id"] in rule_ids
        assert {item["port"] for item in contract["context_sources"]} == set(port.context_sources)
design = catalog.operation("science.experiment.design.v1").spec
assert next(port for port in design.inputs if port.name == "critic_review").exposure == "full"
assert next(port for port in design.inputs if port.name == "scientific_foundation").exposure == "handoff_only"
execution_context = next(port for port in design.inputs if port.name == "execution_context")
assert execution_context.schema_id == "scidiscovery.execution-context.v1"
assert execution_context.media_types == ("application/json",)
assert execution_context.min_items == 0 and execution_context.max_items == 1
objective = catalog.operation("science.objective.project.v1").spec
assert objective.inputs[0].required_non_null_fields == ("objective_contract",)
assert agents
print("installed contracts aligned")
''')
    assert output.strip() == "installed contracts aligned"


def test_installed_e52_core_and_tcad_contracts_are_packaged(installed_probe) -> None:
    output = installed_probe("full", r'''
import json
import tempfile
from jsonschema.validators import validator_for
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import (
    ApprovalOption,
    CompiledApprovalIdentity,
    LocalIdentityRef,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.cognitive import CriticReview, HypothesisProposal
from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentDesignIntent
from scidiscovery.artifact_agent.schema.research_objective import (
    ObjectiveClosureRequirement,
    ResearchObjectiveContract,
)
from scidiscovery.artifact_agent.schema.execution_context import ExecutionContext
from scidiscovery.artifact_agent.schema.scientific_foundation import ScientificFoundation
from scidiscovery.operations.catalog import compile_installed_catalog
from tcad_artifact.execution_control import SolverCapabilitySnapshot

schema = ObjectiveClosureRequirement.model_json_schema(mode="validation")
validator_type = validator_for(schema)
validator_type.check_schema(schema)
validator = validator_type(schema)
valid = {
    "requirement_key": "comparison",
    "description": "Require one exact comparison.",
    "requirement_type": "comparison_present",
    "comparison_purposes": ["target_fit"],
}
invalid = {
    "requirement_key": "comparison",
    "description": "Require one exact comparison.",
    "requirement_type": "comparison_present",
}
assert not tuple(validator.iter_errors(valid))
assert tuple(validator.iter_errors(invalid))
assert schema["properties"]["target_keys"]["uniqueItems"] is True
assert schema["properties"]["comparison_purposes"]["uniqueItems"] is True
assert schema["properties"]["validation_check_keys"]["uniqueItems"] is True

catalog = compile_installed_catalog()
audit = catalog.operation("science.evidence.audit.v1")
rules = json.loads(
    audit.implementations["general_science:evidence_audit_semantic_contract"]
)["rules"]
descriptions = "\n".join(rule["description"] for rule in rules)
assert "faithful to the exact sources" in descriptions
assert "not whether those sources are sufficient" in descriptions

extraction = catalog.operation("tcad.parameter.evidence.extract.v1")
usages = {port.name: port.usage for port in extraction.spec.inputs}
assert usages["required_parameter_checklist"] == "prior_signal"
assert usages["source_material"] == "evidence_inventory"
for operation_id in (
    "science.parameters.qualify.pass.v1",
    "science.parameters.qualify.exception.v1",
):
    assert catalog.operation(operation_id).spec.version == "2"
projection = catalog.operation("tcad.execution-context.project.v1")
assert projection.spec.catalog_scope == "support"
assert projection.spec.executor.kind == "transform"
assert tuple(port.name for port in projection.spec.inputs) == ("capability",)
assert projection.spec.inputs[0].schema_id == "tcad.solver-capability.v2"
assert tuple(port.name for port in projection.spec.outputs) == ("execution_context",)
assert projection.spec.outputs[0].schema_id == "scidiscovery.execution-context.v1"
assert "general_science:execution_context_schema" in projection.implementations
ExecutionContext.model_validate(
    {
        "schema_version": 1,
        "domain": "tcad",
        "implementation_backend": "sprocess",
        "implementation_kind": "sprocess",
        "release_label": "R-2020.09",
        "public_arguments": ("-i",),
        "capability_statements": None,
        "limitations": None,
    },
    strict=True,
)

root_dir = Path(tempfile.mkdtemp(prefix="installed-e52-execution-context-"))
project = root_dir / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed execution-context probe\n", encoding="utf-8")
runtime = open_runtime(
    project_root=project,
    state_root=root_dir / "state",
    worker_backend="local",
    approval_receipt_secret=b"i" * 32,
)
instance = runtime.scheduler_bindings.create_instance(
    name="installed_execution_context",
    title="Installed execution-context closure",
    objective="Exercise the installed projection and design contracts.",
)
root = RootMCPRouter(RootToolFacade(
    runtime.artifacts,
    runtime.intake,
    runs=runtime.runs,
    approvals=runtime.approvals,
    executions=runtime.executions,
    bindings=runtime.scheduler_bindings,
    instance=instance.instance_id,
    operation_catalog=catalog,
))

def register(name, content, *, kind, schema_id, parents=(), media_type="application/json"):
    envelope = runtime.artifacts.register(
        content,
        ArtifactRegistration(
            kind=kind,
            schema_id=schema_id,
            payload_schema_version=1,
            media_type=media_type,
            creator=runtime.actor,
            parent_refs=parents,
        ),
        idempotency_key=f"installed-execution-context:{name}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=name,
        object_id=envelope.artifact_id,
    )
    return envelope

objective = ResearchObjectiveContract.model_validate_json(canonical_json({
    "objective_key": "installed_objective",
    "intent": "mechanism_discrimination",
    "statement": "Distinguish one bounded mechanism.",
    "closure_requirements": [{
        "requirement_key": "comparison_required",
        "description": "Compare the bounded candidates.",
        "requirement_type": "comparison_present",
        "comparison_purposes": ["mechanism_separation"],
    }],
}), strict=True)
foundation = ScientificFoundation.model_validate_json(canonical_json({
    "title": "Installed foundation",
    "objective": objective.statement,
    "summary": "One bounded assumption supports this packaging test.",
    "objective_contract": objective,
    "items": [{
        "item_key": "bounded_assumption",
        "item_type": "assumption",
        "epistemic_status": "assumption",
        "statement": "The installed test uses one bounded mechanism.",
        "scope": "This isolated installed-package test only.",
        "rationale": "It is sufficient to exercise transport, not scientific truth.",
    }],
}), strict=True)
hypotheses = HypothesisProposal.model_validate_json(canonical_json({
    "schema_version": 2,
    "research_objective_key": objective.objective_key,
    "stage_objective": "Separate one bounded mechanism.",
    "contradiction": "The bounded mechanism is not yet distinguished.",
    "hypotheses": [{
        "hypothesis_key": "hypothesis_a",
        "statement": "One bounded intervention changes the response.",
        "mechanism": "The intervention alters one observable response.",
        "scope": "This isolated installed-package test only.",
        "predictions": [{
            "prediction_key": "prediction_a",
            "observable": "response",
            "expected_outcome": "The response changes.",
        }],
        "falsifiers": [{
            "falsifier_key": "falsifier_a",
            "observable": "response",
            "rejection_condition": "The response does not change.",
        }],
    }],
}), strict=True)
critic = CriticReview.model_validate_json(canonical_json({
    "schema_version": 2,
    "disposition": "ready_for_experiment",
    "reviews": [{
        "hypothesis_key": "hypothesis_a",
        "physical_plausibility": "pass",
        "falsifiability": "pass",
        "finite_discriminability": "pass",
    }],
}), strict=True)
intent = ExperimentDesignIntent.model_validate_json(canonical_json({
    "study_kind": "engineering",
    "objective_key": None,
    "engineering_objective": "Check one bounded numerical case.",
    "selected_hypothesis_keys": [],
    "proposals": [{
        "experiment_key": "installed_case",
        "objectives": ["Check one bounded numerical case."],
        "current_objectives": ["Check one bounded numerical case."],
        "hypothesis_keys": [],
        "frozen_invariants": ["Use the exact installed-package inputs."],
        "cases": [{
            "case_key": "single_case",
            "scientific_role": "control",
            "purpose": "Exercise one bounded installed Run.",
        }],
        "baseline_case_key": None,
        "variables": [],
        "required_observables": ["completion"],
        "identifiability_claims": [],
        "prediction_tests": [],
        "validation_intent": {
            "numerical": {
                "rationale": "Check bounded numerical completion.",
                "reviewed_checks": [{
                    "observable": "completion",
                    "metric": "bounded completion",
                    "acceptance_condition": "The single case completes.",
                    "failure_action": "Stop and inspect the failure.",
                    "basis": "This packaging test has one numerical case.",
                }],
            },
            "physical": {"rationale": "Not applicable to this packaging test."},
            "experimental": {"rationale": "Not applicable to this packaging test."},
        },
        "resource_estimate": {
            "relative_cost": "low",
            "runtime_basis": "One local contract-only Run.",
        },
        "stop_conditions": ["Stop after the result is sealed."],
        "value_assessment": {
            "evidence_support": "low",
            "discrimination_power": "low",
            "information_gain": "low",
            "cost": "low",
            "added_free_parameters": 0,
            "rationale": "This verifies installed protocol closure only.",
        },
    }],
    "priority_order": ["installed_case"],
    "priority_rationale": "There is exactly one bounded packaging check.",
}), strict=True)

foundation_artifact = register(
    "foundation", foundation.canonical_json(), kind="scientific_foundation",
    schema_id="scidiscovery.scientific-foundation.v1",
)
register(
    "objective", canonical_json(objective), kind="research_objective",
    schema_id="scidiscovery.research-objective.v1", parents=(foundation_artifact.ref,),
)
portfolio_artifact = register(
    "portfolio", hypotheses.canonical_json(), kind="hypothesis_portfolio",
    schema_id="scidiscovery.hypothesis-proposal.v2", parents=(foundation_artifact.ref,),
)
register(
    "critic", critic.canonical_json(), kind="critic_review",
    schema_id="scidiscovery.critic-review.v2",
    parents=(foundation_artifact.ref, portfolio_artifact.ref),
)

provider = catalog.operation("science.evidence.qualify.v1").approval_identity
assert provider is not None
launch = runtime.approvals.create_request(
    approval_id="installed_foundation_approval",
    kind="scientific_foundation",
    subject_refs=(foundation_artifact.ref,),
    question="Approve the exact isolated fixture?",
    options=(
        ApprovalOption(
            option_id="approve", label="Approve", description="Approve this fixture.",
            requires_rationale=False,
        ),
        ApprovalOption(
            option_id="reject", label="Reject", description="Reject this fixture.",
            requires_rationale=False,
        ),
    ),
    requested_by=runtime.actor,
    idempotency_key="installed-foundation-approval",
    compiled_identity=CompiledApprovalIdentity(
        operation_id=provider.operation_id,
        operation_version=provider.version,
        operation_digest=provider.operation_digest,
        approval_contract_digest=provider.approval_contract_digest,
    ),
)
review = runtime.approvals.review(launch.approval_id, access_token=launch.access_token)
runtime.approvals.record_ui_decision(
    approval_id=launch.approval_id,
    access_token=launch.access_token,
    csrf_token=review.csrf_token,
    decision_nonce=review.decision_nonce,
    selected_option="approve",
    rationale="",
    decided_by=LocalIdentityRef(
        identity_id="installed_fixture_reviewer",
        display_name="Installed Fixture Reviewer",
    ),
    ui_session_id="installed-execution-context-test",
)

snapshot = SolverCapabilitySnapshot(
    profile_id="installed_shell_runner",
    solver_kind="shell_runner",
    launch_name="installed-runner",
    public_arguments=(),
    public_release_label="unknown-release",
    private_fixed_argument_count=0,
    private_fixed_arguments_sha256="a" * 64,
    private_release_evidence_bytes=1,
    private_release_evidence_sha256="b" * 64,
    capability_sha256="c" * 64,
)
capability = register(
    "capability",
    json.dumps(
        snapshot.model_dump(mode="json"),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8"),
    kind="solver_capability",
    schema_id="tcad.solver-capability.v2",
)
projection_request = {
    "name": "projected_context",
    "operation_id": "tcad.execution-context.project.v1",
    "inputs": [{"port": "capability", "artifact_names": ["capability"]}],
}
assert root.call_tool("operation_preflight", projection_request)["admissible"] is True
projected = root.call_tool("operation_invoke", projection_request)
context_name = projected["result"]["outputs"][0]["artifact_name"]
context_id = runtime.scheduler_bindings.resolve(
    instance=instance.instance_id, namespace="artifact", name=context_name,
)
context_envelope = runtime.artifacts.get_by_id(context_id)
assert context_envelope.parent_refs == (capability.ref,)
context = ExecutionContext.model_validate_json(
    runtime.artifacts.read(context_envelope.ref), strict=True,
)
assert context.implementation_kind == "shell_runner"
assert context.release_label == "unknown-release"
assert context.capability_statements is None and context.limitations is None

def design_request(name, context_artifact_names=()):
    inputs = [
        {"port": "scientific_foundation", "artifact_names": ["foundation"]},
        {"port": "research_objective", "artifact_names": ["objective"]},
        {"port": "hypothesis_portfolio", "artifact_names": ["portfolio"]},
        {"port": "critic_review", "artifact_names": ["critic"]},
    ]
    if context_artifact_names:
        inputs.append({
            "port": "execution_context", "artifact_names": list(context_artifact_names),
        })
    return {
        "name": name,
        "operation_id": "science.experiment.design.v1",
        "inputs": inputs,
        "instruction": "Design one bounded installed-package experiment.",
    }

assert root.call_tool("operation_preflight", design_request("without_context"))[
    "admissible"
] is True
wrong_schema = root.call_tool(
    "operation_preflight", design_request("wrong_schema", ("capability",)),
)
assert wrong_schema["admissible"] is False
assert wrong_schema["reason_code"] == "input_schema_mismatch"
wrong_media = register(
    "wrong_media_context", canonical_json(context), kind="execution_context",
    schema_id="scidiscovery.execution-context.v1", media_type="text/plain",
)
wrong_media_result = root.call_tool(
    "operation_preflight", design_request("wrong_media", ("wrong_media_context",)),
)
assert wrong_media_result["admissible"] is False
assert wrong_media_result["reason_code"] == "input_media_type_mismatch"

request = design_request("with_context", (context_name,))
assert root.call_tool("operation_preflight", request)["admissible"] is True
assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
compiled_design = catalog.operation("science.experiment.design.v1")
worker = LocalWorkerMCPRouter(
    runtime.runs,
    operation_id=compiled_design.spec.operation_id,
    operation_digest=compiled_design.digest,
)
opened = worker.call_tool("worker_open_assignment", {})
context_path = Path(opened["workspace_path"], "inputs", "execution_context.json")
assert context_path.read_bytes() == runtime.artifacts.read(context_envelope.ref)
assert context_path.stat().st_mode & 0o222 == 0
Path(opened["output_directory"], "result.json").write_bytes(canonical_json({
    "schema_version": 1,
    "handoff": {"verdict": "pass", "summary": "Installed contract closure passed."},
    "payload": intent,
}))
assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
assert root.call_tool("run_status", {"name": "with_context"})["state"] == "completed"

damaged_snapshot = register(
    "damaged_capability", b'{}', kind="solver_capability",
    schema_id="tcad.solver-capability.v2",
)
damaged_request = {
    "name": "damaged_projection",
    "operation_id": "tcad.execution-context.project.v1",
    "inputs": [{"port": "capability", "artifact_names": ["damaged_capability"]}],
}
assert root.call_tool("operation_preflight", damaged_request)["admissible"] is True
try:
    root.call_tool("operation_invoke", damaged_request)
except Exception as error:
    assert error.details[0]["code"] == "executor_component_failed"
    assert error.details[0]["repairable"] is False
else:
    raise AssertionError("a damaged capability snapshot was projected")

print("installed E5.2 execution-context closure passed")
''')
    assert output.strip() == "installed E5.2 execution-context closure passed"


def test_installed_e52_curve_contracts_are_packaged(installed_probe) -> None:
    output = installed_probe("figure", r'''
import json
from curve_figure_evidence.figure_science_operations import FIGURE_REQUEST_SCHEMA
from curve_figure_evidence.figure_evidence_validation import VALIDATOR_VERSION
from scidiscovery.operations.catalog import compile_installed_catalog

assert VALIDATOR_VERSION == "6"
request_schema = json.loads(FIGURE_REQUEST_SCHEMA)
serialized = json.dumps(request_schema)
for field in ("tracking", "min_points", "shared_support", "color_tolerance"):
    assert field not in serialized

catalog = compile_installed_catalog()
prepare = catalog.operation("science.figure.request.prepare.v1")
assert prepare.spec.outputs[0].schema_id == "scidiscovery.curve-figure-digitization-request.v2"
audit = catalog.operation("science.figure.evidence.audit.v1")
prompt = audit.implementations["curve_figure_evidence:figure_audit_prompt"]
assert "not whether that family is sufficient" in prompt
assert "shared dependency" in prompt
print("installed E5.2 curve contracts present")
''')
    assert output.strip() == "installed E5.2 curve contracts present"




def test_installed_evidence_alias_schema_matches_local_worker_submit(
    installed_probe,
) -> None:
    installed_probe(
        "core",
        r'''
import json
import tempfile
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json

root_dir = Path(tempfile.mkdtemp(prefix="installed-e52-alias-"))
project = root_dir / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed E5.2 alias probe\n", encoding="utf-8")
runtime = open_runtime(
    project_root=project,
    state_root=root_dir / "state",
    worker_backend="local",
)
catalog = runtime.operation_catalog
instance = runtime.scheduler_bindings.create_instance(
    name="installed_e52_alias",
    title="Installed E5.2 source alias probe",
    objective="Prove one compiled source alias is visible and executable.",
)

foundation = canonical_json({
    "title": "Bounded foundation",
    "objective": "Audit one bounded premise.",
    "summary": "The premise is explicitly marked as an assumption.",
    "items": [{
        "item_key": "premise",
        "item_type": "assumption",
        "epistemic_status": "assumption",
        "statement": "The supplied line is the bounded context.",
        "scope": "Installed probe only.",
        "rationale": "The audit must remain tied to its frozen input.",
    }],
})

def register(name, content, *, kind, schema_id, media_type):
    artifact = runtime.artifacts.register(
        content,
        ArtifactRegistration(
            kind=kind,
            schema_id=schema_id,
            payload_schema_version=1,
            media_type=media_type,
            creator=runtime.actor,
        ),
        idempotency_key=f"installed-e52:{name}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=name,
        object_id=artifact.artifact_id,
    )

register(
    "foundation",
    foundation,
    kind="scientific_foundation",
    schema_id="scidiscovery.scientific-foundation.v1",
    media_type="application/json",
)
register(
    "paper_001",
    b"one bounded source line\n",
    kind="paper_source",
    schema_id="opaque",
    media_type="text/plain",
)
router = RootMCPRouter(
    RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )
)
request = {
    "name": "audit",
    "operation_id": "science.evidence.audit.v1",
    "inputs": [
        {"port": "scientific_foundation", "artifact_names": ["foundation"]},
        {"port": "source_material", "artifact_names": ["paper_001"]},
    ],
    "instruction": "Audit only the exact bound source.",
}
assert router.call_tool("operation_preflight", request)["admissible"] is True
assert router.call_tool("operation_invoke", request)["result"]["state"] == "queued"
compiled = catalog.operation("science.evidence.audit.v1")
worker = LocalWorkerMCPRouter(
    runtime.runs,
    operation_id=compiled.spec.operation_id,
    operation_digest=compiled.digest,
)
opened = worker.call_tool("worker_open_assignment", {})
result_schema = json.loads(
    Path(opened["workspace_path"], "schema", "result.schema.json").read_text("utf-8")
)
source_key = result_schema["properties"]["payload"]["properties"]["evidence"][
    "items"
]["allOf"][-1]["properties"]["source_key"]
assert source_key["enum"] == ["scientific_foundation", "source_material"]
# The workspace copy is only a Worker aid.  Expanding it must not expand the
# authoritative schema rebuilt by submit from the frozen Run binding.
source_key["enum"].append("invented_source")
schema_path = Path(opened["workspace_path"], "schema", "result.schema.json")
schema_path.chmod(0o600)
schema_path.write_bytes(canonical_json(result_schema))

def result(source_name):
    return canonical_json({
        "schema_version": 1,
        "handoff": {
            "verdict": "pass",
            "summary": "The bounded statement is faithful to the exact source.",
        },
        "payload": {
            "schema_version": 1,
            "checks": [{
                "check_key": "source_fidelity",
                "subject": "The statement remains bounded to the supplied line.",
                "status": "pass",
                "basis": "The exact frozen line is available.",
                "evidence_keys": [source_name],
            }],
            "evidence": [{
                "source_key": source_name,
                "source_type": "frozen_input",
                "locator": f"{source_name}:line-1",
            }],
        },
    })

output = Path(opened["output_directory"], "result.json")
output.write_bytes(result("invented_source"))
rejected = worker.call_tool("worker_submit_result", {})
assert rejected["state"] == "rejected"
assert {item["rule_id"] for item in rejected["diagnostics"]} == {"runtime.schema"}
assert router.call_tool("run_status", {"name": "audit"})["state"] == "running"

output.write_bytes(result("scientific_foundation"))
completed = worker.call_tool("worker_submit_result", {})
assert completed["state"] == "completed"
''',
    )


_INSTALLED_CURVE_TOOL_PROBE = r'''
import hashlib
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
import curve_score
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(curve_score.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
image = Image.new("RGB", (12, 12), "white")
ImageDraw.Draw(image).line([(1, 9), (9, 1)], fill="#ff0000", width=1)
stream = io.BytesIO()
image.save(stream, format="PNG")
class Context:
    def __init__(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="installed-figure-"))
        self.source = self.workspace / "source.png"
        self.source.write_bytes(stream.getvalue())
        self.remaining_seconds = 30
        self.events = []
    def input_path(self, name):
        assert name == "paper_source"
        return self.source
    def input_media_type(self, name):
        assert name == "paper_source"
        return "image/png"
    def input_ref(self, name):
        assert name == "paper_source"
        return ArtifactRef(
            artifact_id="installed_source",
            sha256=hashlib.sha256(stream.getvalue()).hexdigest(),
            kind="paper_source",
            schema_id="opaque",
        )
    def record_activity(self, event): self.events.append(event)

tools = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("science.figure.request.prepare.v1")
    )
}
assert "worker_curve_figure_preview" in tools
tool = tools["worker_curve_figure_inspect_source"]
assert set(tool.input_model.model_json_schema()["properties"]) == {"name", "source_page"}
context = Context()
result = tool.contextual_handler(
    tool.input_model(),
    context,
)
assert len(result["images"]) == 1
assert "candidate_overlay" not in result["images"][0]
assert Path(result["images"][0]["local_path"]).is_file()
assert Path(result["images"][0]["local_path"]).stat().st_mode & 0o222 == 0
assert context.events == ["deterministic_analysis_completed"]
'''


_INSTALLED_TCAD_TOOL_PROBE = r'''
import sys
from pathlib import Path

import tcad_artifact
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(tcad_artifact.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
tool = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("tcad.deck.author.initial.v1")
    )
}["worker_tcad_debug_run"]
class Service:
    def run(self, context, *, run_name, mode):
        assert (run_name, mode) == ("probe", "preflight")
        return {"state": "completed", "scientific_claim_admissible": False}
class Context:
    state = {}
    remaining_seconds = 1200
    def require_service(self, name):
        assert name == "tcad.development_debug"
        return Service()
result = tool.contextual_handler(
    tool.input_model(run_name="probe", mode="preflight"),
    Context(),
)
assert result["state"] == "completed" and result["scientific_claim_admissible"] is False
assert result["budget"]["remaining_wall_seconds"] == 360
'''


def test_installed_tcad_retry_and_budget_use_local_worker(installed_probe):
    import ast
    from pathlib import Path

    # Reuse only test fixtures. All production imports run inside the isolated
    # installed environment, with no source path or host site-packages available.
    source = Path(__file__).with_name("test_l4_local_tcad.py").read_text("utf-8")
    selected = {
        "_ImmediateDebugAdapter", "_BudgetDebugAdapter", "_portfolio", "_project",
        "_system", "_invoke", "_write_author_workspace", "_debug_worker",
        "_write_sprocess_workspace", "_budget_case",
        "test_local_tcad_retry_discards_control_proofs_before_debug",
        "test_local_tcad_budget_covers_pending_failure_cache_and_exhaustion",
        "test_tcad_source_locator_does_not_cross_log_omissions",
    }
    fixtures = []
    for node in ast.parse(source).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            if isinstance(node, ast.Import) and any(alias.name == "pytest" for alias in node.names):
                continue
            fixtures.append(ast.get_source_segment(source, node))
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in selected:
            fixtures.append(ast.get_source_segment(source, node))
    output = installed_probe("full", "\n\n".join(fixtures) + r'''
import tempfile
import sys
import tcad_artifact.plugin as installed_tcad
from scidiscovery.operations.catalog import compile_installed_catalog

assert Path(installed_tcad.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
loaded = compile_installed_catalog()
fixture_catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
for name in fixture_catalog.operation_ids():
    assert loaded.operation(name).digest == fixture_catalog.operation(name).digest
with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    (root / "retry").mkdir()
    test_local_tcad_retry_discards_control_proofs_before_debug(root / "retry")
    (root / "budget").mkdir()
    test_local_tcad_budget_covers_pending_failure_cache_and_exhaustion(root / "budget")
for marker in ("--- bounded diagnostic omission ---", "--- bounded log omission ---"):
    test_tcad_source_locator_does_not_cross_log_omissions(marker)
print("installed retry and budget passed through LocalWorkerMCPRouter")
''')
    assert output.strip() == "installed retry and budget passed through LocalWorkerMCPRouter"


def test_clean_installed_core_compiles_only_the_single_plugin_group(installed_probe) -> None:
    output = installed_probe(
        "core",
        r'''
import importlib
from importlib.metadata import entry_points
import scidiscovery.builtin_plugin as builtin_plugin
from scidiscovery.operations.catalog import (
    PLUGIN_ENTRY_POINT_GROUP,
    compile_installed_catalog,
)

assert not hasattr(builtin_plugin, "ARCHITECTURE_TEST_PLUGIN")
for module_name in (
    "architecture_operation_test_plugin",
    "scidiscovery.artifact_agent.service.agent_dispatch",
    "scidiscovery.platforms.codex_worker",
):
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError(f"core-only install exposed {module_name}")

selected = tuple(sorted(
    entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP),
    key=lambda item: item.name,
))
assert [(item.name, item.value) for item in selected] == [
    ("builtin", "scidiscovery.builtin_plugin:CORE_PLUGIN"),
    ("general_science", "scidiscovery.general_science_plugin:PLUGIN"),
]
catalog = compile_installed_catalog()
assert compile_installed_catalog() is catalog
try:
    import scidiscovery.artifact_agent.schema.device_parameters  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("core-only install exposed the TCAD parameter schema")
assert not any("parameter" in item for item in catalog.operation_ids())
print("\n".join(catalog.operation_ids()))
''',
    )
    assert output.splitlines() == _EXPECTED_OPERATION_IDS


def test_architecture_operations_require_the_explicit_test_plugin(
    installed_probe,
) -> None:
    output = installed_probe(
        "architecture",
        r'''
from importlib.metadata import entry_points
from scidiscovery.operations.catalog import (
    PLUGIN_ENTRY_POINT_GROUP,
    compile_installed_catalog,
)

selected = tuple(sorted(
    entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP),
    key=lambda item: item.name,
))
assert [(item.name, item.value) for item in selected] == [
    (
        "architecture_fixture",
        "architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_PLUGIN",
    ),
    ("builtin", "scidiscovery.builtin_plugin:CORE_PLUGIN"),
    ("general_science", "scidiscovery.general_science_plugin:PLUGIN"),
]
catalog = compile_installed_catalog()
production_digests = {
    operation_id: catalog.operation(operation_id).digest
    for operation_id in catalog.operation_ids()
    if not operation_id.startswith("builtin.test.")
}
assert len(production_digests) == 15
print("\n".join(catalog.operation_ids()))
''',
    )
    assert output.splitlines() == [
        "builtin.test.agent",
        "builtin.test.effect",
        "builtin.test.transform",
        *_EXPECTED_OPERATION_IDS,
    ]


def test_architecture_plugin_does_not_change_production_operation_digests(
    installed_probe,
) -> None:
    source = r'''
import json
from scidiscovery.operations.catalog import compile_installed_catalog

catalog = compile_installed_catalog()
print(json.dumps({
    operation_id: catalog.operation(operation_id).digest
    for operation_id in catalog.operation_ids()
    if not operation_id.startswith("builtin.test.")
}, sort_keys=True))
'''
    core = json.loads(installed_probe("core", source))
    architecture = json.loads(installed_probe("architecture", source))
    assert len(core) == 15
    assert architecture == core


def test_codex_profiles_follow_the_installed_catalog_without_scope_filters(
    installed_probe,
) -> None:
    source = r'''
import json
import sys
import tempfile
from pathlib import Path

from scidiscovery.platforms import initialize_platform

root = Path(tempfile.mkdtemp(prefix="catalog-profile-"))
(root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
initialize_platform(
    "codex",
    root,
        python_executable=Path(sys.executable),
        control_socket=root / "control.sock",
                codex_config_root=root / ".codex",
)
print(json.dumps(sorted(
    path.stem for path in (root / ".codex" / "agents").glob("op_*.toml")
    if "builtin_test" in path.stem
)))
'''
    assert json.loads(installed_probe("core", source)) == []
    architecture_profiles = json.loads(installed_probe("architecture", source))
    assert len(architecture_profiles) == 1
    assert architecture_profiles[0].startswith("op_builtin_test_agent_")


def test_installed_scheduler_guides_use_context_projection_paths(installed_probe) -> None:
    output = installed_probe("core", r'''
import sys
import tempfile
from pathlib import Path

from scidiscovery.platforms import initialize_platform

root = Path(tempfile.mkdtemp(prefix="installed-guides-"))
(root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
initialize_platform(
    "codex",
    root,
    python_executable=Path(sys.executable),
    control_socket=root / "control.sock",
    codex_config_root=root / ".codex",
)
prompt = (root / "AGENTS.md").read_text(encoding="utf-8")
guide_root = root / ".codex" / "scidiscovery-guides"
results = (guide_root / "results.md").read_text(encoding="utf-8")
inputs = (guide_root / "inputs.md").read_text(encoding="utf-8")
domain = (guide_root / "domain-analysis.md").read_text(encoding="utf-8")
assert 'scid_describe(name=..., view="invoke")' in prompt
assert all(f'response_profile="{name}"' in results
    for name in ("poll", "navigation", "decision"))
assert 'artifact_catalog(view="producer_inputs")' in inputs
assert "parents_fallback" in inputs
assert 'artifact_catalog(view="producer_inputs")' in domain
print("installed scheduler projection guides passed")
''')
    assert output.strip() == "installed scheduler projection guides passed"


def test_legacy_domain_entry_points_are_not_an_operation_discovery_fallback(
    installed_probe,
) -> None:
    output = installed_probe(
        "full",
        r'''
from scidiscovery.operations.catalog import compile_installed_catalog

catalog = compile_installed_catalog()
print("\n".join(catalog.operation_ids()))
''',
    )
    assert output.splitlines() == sorted([
        *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS,
        *_EXPECTED_OPERATION_IDS,
        *_EXPECTED_TCAD_PARAMETER_OPERATION_IDS,
        "tcad.control-equivalence.v1",
        "tcad.curve-bundle.sprocess-log.v1",
        "tcad.curve-bundle.sprocess-plx.v1",
        "tcad.deck-project-compare.v1",
        "tcad.deck-review-validate.v1",
        "tcad.deck.author.initial.v1",
        "tcad.deck.author.revise.v1",
        "tcad.deck.author.runtime-failure.v1",
        "tcad.deck.review.v1",
        "tcad.parameter.evidence.audit.v1",
        "tcad.parameter.evidence.expand.v1",
        "tcad.parameter.evidence.extract.v1",
        "tcad.execution-context.project.v1",
        "tcad.realization-snapshot-materialize.v1",
        "tcad.reviewed-deck-package.v2",
        "tcad.runtime-attestation.v1",
        "tcad.study.execute",
        "tcad.result.analyze.v1",
    ])


def test_clean_domain_wheel_matrix_has_exact_plugin_ownership(installed_probe) -> None:
    source = r'''
from importlib.metadata import entry_points
from scidiscovery.operations.catalog import PLUGIN_ENTRY_POINT_GROUP, compile_installed_catalog

catalog = compile_installed_catalog()
plugins = sorted(item.name for item in entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP))
print(",".join(plugins))
print("\n".join(catalog.operation_ids()))
'''
    curve = installed_probe("curve", source).splitlines()
    assert curve[0] == "builtin,curve_score,general_science"
    assert set(curve[1:]) == {
        *_EXPECTED_OPERATION_IDS,
        *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS,
    }
    assert not set(_EXPECTED_FIGURE_OPERATION_IDS) & set(curve[1:])
    figure = installed_probe("figure", source).splitlines()
    assert figure[0] == (
        "builtin,curve_figure_evidence,curve_score,general_science"
    )
    assert set(figure[1:]) == {
        *_EXPECTED_OPERATION_IDS,
        *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS,
        *_EXPECTED_FIGURE_OPERATION_IDS,
    }
    table = installed_probe("table", source).splitlines()
    assert table[0] == "builtin,general_science,table_observation"
    assert set(table[1:]) == {
        *_EXPECTED_OPERATION_IDS,
        "science.table.observation.analyze.v1",
        "science.table.observation.review.v1",
    }
    tcad = installed_probe("tcad_resolved", source).splitlines()
    assert tcad[0] == "builtin,curve_score,general_science,tcad_artifact"
    assert "science.evidence.extract.figure.v1" not in tcad[1:]
    assert "tcad.curve-bundle.sprocess-plx.v1" in tcad[1:]
    full = installed_probe("full", source).splitlines()
    assert tcad == full
    assert set(tcad[1:]) == {
        *_EXPECTED_OPERATION_IDS, *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS, *_EXPECTED_TCAD_PARAMETER_OPERATION_IDS,
        "tcad.control-equivalence.v1", "tcad.curve-bundle.sprocess-log.v1",
        "tcad.curve-bundle.sprocess-plx.v1", "tcad.deck-project-compare.v1",
        "tcad.deck-review-validate.v1", "tcad.deck.author.initial.v1",
        "tcad.deck.author.revise.v1", "tcad.deck.author.runtime-failure.v1",
        "tcad.deck.review.v1", "tcad.parameter.evidence.audit.v1",
        "tcad.parameter.evidence.expand.v1", "tcad.parameter.evidence.extract.v1",
        "tcad.execution-context.project.v1",
        "tcad.realization-snapshot-materialize.v1", "tcad.reviewed-deck-package.v2",
        "tcad.runtime-attestation.v1", "tcad.study.execute", "tcad.result.analyze.v1",
    }
    core = installed_probe("core", source).splitlines()
    assert core[0] == "builtin,general_science"
    assert set(core[1:]) == set(_EXPECTED_OPERATION_IDS)
    all_domains = installed_probe("all_domains", source).splitlines()
    assert all_domains[0] == "builtin,curve_figure_evidence,curve_score,general_science,tcad_artifact"
    assert set(all_domains[1:]) == set(tcad[1:]) | set(_EXPECTED_FIGURE_OPERATION_IDS)


@pytest.mark.parametrize("environment", ("core", "curve", "figure", "full", "all_domains"))
def test_installed_case_distribution_and_import_are_absent(installed_probe, environment):
    installed_probe(environment, r'''
from importlib.metadata import distribution, entry_points, PackageNotFoundError
from importlib.util import find_spec
from pathlib import Path
import importlib
import sys
assert find_spec("ingaas_fig4") is None
try:
    distribution("scidiscovery-ingaas-fig4")
except PackageNotFoundError:
    pass
else:
    raise AssertionError("removed case distribution remains installed")
for entry in entry_points(group="scidiscovery.plugins"):
    assert entry.name != "ingaas_fig4"
    module = importlib.import_module(entry.value.split(":")[0])
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
''')


def test_curve_wheel_scores_without_installing_figure(installed_probe):
    from tests.operations.test_m2_curve_analysis_boundary import _inputs

    payloads = {key: value.decode() for key, value in _inputs().items()
                if key in {"curve_bundle", "curve_contract", "experiment_plan"}}
    installed_probe("curve", "payloads = " + repr(payloads) + r'''
from importlib.metadata import distribution, PackageNotFoundError
from importlib.util import find_spec
from pathlib import Path
import json
import sys
import curve_score
import curve_score.transform_adapter as adapter
assert find_spec("curve_figure_evidence") is None
assert find_spec("curve_score.figure_evidence_normalizer") is None
assert not tuple(Path(curve_score.__file__).parent.glob("figure*.py"))
try:
    distribution("scidiscovery-curve-figure-evidence")
except PackageNotFoundError:
    pass
else:
    raise AssertionError("figure wheel must not be installed for this smoke")
outputs = adapter.score_curve_bundle_outputs({key: value.encode() for key, value in payloads.items()})
assert set(outputs) == {"metric_report", "merged_curve_bundle", "score_audit", "comparison_plot"}
assert json.loads(outputs["metric_report"][0])["aggregate_status"] == "fail"
assert outputs["comparison_plot"][0].startswith(b"\x89PNG")
assert not any(name.startswith("curve_figure_evidence") for name in sys.modules)
assert Path(adapter.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
''')


def test_clean_installed_domain_tools_execute_the_packaged_implementations(
    installed_probe,
) -> None:
    installed_probe("figure", _INSTALLED_CURVE_TOOL_PROBE)
    installed_probe(
        "table",
        r'''
import sys
from pathlib import Path

import table_observation
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(table_observation.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
tool = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("science.table.observation.analyze.v1")
    )
}["worker_table_summarize"]
class Context:
    def __init__(self): self.events = []
    def read_input(self, name):
        assert name == "observation_table"
        return b"sample,value\na,1\nb,3\n"
    def record_activity(self, event): self.events.append(event)
context = Context()
result = tool.contextual_handler(
    tool.input_model(),
    context,
)
assert result["rows"] == 2
assert result["numeric_columns"][0]["mean"] == 2.0
assert context.events == ["deterministic_analysis_completed"]
''',
    )
    installed_probe("tcad_resolved", _INSTALLED_TCAD_TOOL_PROBE)
    installed_probe("full", _INSTALLED_TCAD_TOOL_PROBE)


def test_clean_installed_pure_mcp_plugin_completes_a_hardened_run(
    installed_probe,
) -> None:
    installed_probe(
        "blind_csv",
        r'''
import json
import sys
import tempfile
import tomllib
from pathlib import Path

import blind_csv_plugin
from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import (
    HardenedWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.tooling import (
    operation_agent_type,
    operation_worker_server_name,
)
from scidiscovery.platforms import initialize_platform

assert Path(blind_csv_plugin.__file__).resolve().is_relative_to(
    Path(sys.prefix).resolve()
)
root = Path(tempfile.mkdtemp(prefix="installed-hardened-"))
project = root / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed Hardened probe\n", encoding="utf-8")
runtime = open_runtime(
    project_root=project,
    state_root=root / "state",
    worker_backend="hardened",
)
catalog = runtime.operation_catalog
compiled = catalog.operation("blind.csv.observe.v1")
instance = runtime.scheduler_bindings.create_instance(
    name="installed_hardened",
    title="Installed Hardened probe",
    objective="Complete one installed pure-MCP Operation through Hardened.",
)
raw = b"sample,value\na,1\nb,3\n"
source = runtime.artifacts.register(
    raw,
    ArtifactRegistration(
        kind="blind_csv_input",
        schema_id="blind.opaque.v1",
        payload_schema_version=1,
        media_type="text/csv",
        creator=runtime.actor,
    ),
    idempotency_key="installed:hardened:source",
)
runtime.scheduler_bindings.bind(
    instance=instance.instance_id,
    namespace="artifact",
    name="source_csv",
    object_id=source.artifact_id,
)
root_router = RootMCPRouter(
    RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )
)
invoked = root_router.call_tool(
    "operation_invoke",
    {
        "name": "observation",
        "operation_id": compiled.spec.operation_id,
        "inputs": [
            {"port": "source_table", "artifact_names": ["source_csv"]}
        ],
        "instruction": "Make one bounded observation from the exact CSV.",
    },
)
assert invoked["result"]["state"] == "queued"

initialize_platform(
    "codex",
    project,
    python_executable=Path(sys.executable),
    control_socket=root / "control.sock",
    state_root=runtime.state_root,
    worker_backend="hardened",
    operation_catalog=catalog,
)
profile = tomllib.loads(
    project.joinpath(
        ".codex/agents", f"{operation_agent_type(compiled)}.toml"
    ).read_text(encoding="utf-8")
)
server = profile["mcp_servers"][operation_worker_server_name(compiled)]
assert server["args"][:2] == [
    "-m",
    "scidiscovery.artifact_agent.interfaces.mcp_hardened_worker",
]

worker = HardenedWorkerMCPRouter(
    runtime.runs,
    operation_id=compiled.spec.operation_id,
    operation_digest=compiled.digest,
)
opened = worker.call_tool("worker_open_assignment", {})
assert opened["write_protocol"] == "server_file_tools"
assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
assignment_tools = tuple(sorted(assignment["tools"]))
profile_tools = tuple(sorted(server["enabled_tools"]))
router_tools = tuple(sorted(item["name"] for item in worker.list_tools()))
assert assignment_tools == profile_tools == router_tools
structure = worker.call_tool("worker_csv_summarize", {})
assert structure["numeric_means"] == {"value": 2.0}
result = canonical_json(
    {
        "schema_version": 1,
        "handoff": {"verdict": "pass", "summary": "Bounded result."},
        "payload": {
            "schema_probe": CSV_SCHEMA_PROBE,
            "structure": structure,
            "interpretation": "The bounded arithmetic mean is two.",
            "limitations": ["Two rows do not establish causality."],
        },
    }
).decode("utf-8")
worker.call_tool(
    "worker_file_write_begin",
    {"relative_path": "output/result.json", "operation": "create"},
)
worker.call_tool("worker_file_write_chunk", {"content": result})
worker.call_tool("worker_file_write_commit", {})
assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
status = root_router.call_tool("run_status", {"name": "observation"})
assert status["state"] == "completed"
assert status["backend"] == "hardened_worker"
assert status["output_artifact_name"] == "observation.output"
''',
    )


def test_installed_component_import_failure_has_a_stable_reason_code(
    installed_probe,
) -> None:
    installed_probe(
        "broken",
        r'''
from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

try:
    compile_installed_catalog()
except CatalogCompileError as error:
    assert error.reason_code == "component_implementation_error", error
    assert error.plugin_id == "broken", error
    assert error.field == "broken_transform", error
else:
    raise AssertionError("the installed broken plugin unexpectedly compiled")
''',
    )


def test_installed_invalid_unicode_resource_has_a_stable_reason_code(
    installed_probe,
) -> None:
    installed_probe(
        "invalid_unicode",
        r'''
from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

try:
    compile_installed_catalog()
except CatalogCompileError as error:
    assert error.reason_code == "component_resource_digest_invalid", error
    assert error.plugin_id == "invalid_unicode", error
    assert error.field == "invalid_resource", error
else:
    raise AssertionError("the installed invalid-unicode plugin unexpectedly compiled")
''',
    )


def test_installed_historical_review_analysis_crossing(installed_environments, installed_probe):
    """Use existing fixture helpers while all production modules come from wheels."""
    import sys
    from pathlib import Path
    from tests.operations.conftest import _copy_runtime_distribution
    environment = installed_environments["all_domains"]
    prefix = environment.python.parent.parent
    site = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    # Offline test-only dependencies in this disposable environment.
    for distribution in ("pytest", "pluggy", "iniconfig", "packaging", "pygments"):
        _copy_runtime_distribution(distribution, site)
    repository = str(Path(__file__).resolve().parents[2])
    output = installed_probe("all_domains", '''
import sys, tempfile
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operation_contract import operation_port_json_schema
import scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes as root_module
import tcad_artifact.result_analysis as tcad_module
import curve_score.science_operations as curve_module
for module in (root_module, tcad_module, curve_module):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog = compile_installed_catalog()
for operation_id in ("tcad.result.analyze.v1", "science.result.diagnose.v1"):
    operation = catalog.operation(operation_id)
    for port in operation.spec.inputs:
        if port.name in ("experiment_plan", "experiment_review"):
            assert port.usage == "evidence_inventory" and port.schema_id != "*"
    assert operation.spec.input_validation is not None
    assert operation_port_json_schema(operation, operation.spec.outputs[0])["x-scidiscovery-input-validation-contract"]
# Only the tests namespace is obtained from the checkout, never src or plugin paths.
sys.path.append(''' + repr(repository) + ''')
from tests.operations.test_collector_analysis_handoff import test_historical_review_reaches_new_analysis_without_current_authority
for operation_id in ("tcad.result.analyze.v1", "science.result.diagnose.v1"):
    with tempfile.TemporaryDirectory() as directory:
        test_historical_review_reaches_new_analysis_without_current_authority(Path(directory), operation_id)
print("installed historical analysis completed; current author authority not inherited")
''')
    assert output.strip() == "installed historical analysis completed; current author authority not inherited"


def test_installed_analysis_evidence_recovery(installed_environments, installed_probe):
    import sys
    from pathlib import Path
    from tests.operations.conftest import _copy_runtime_distribution
    environment=installed_environments['all_domains']
    site=environment.python.parent.parent/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
    for distribution in ('pytest','pluggy','iniconfig','packaging','pygments'):
        _copy_runtime_distribution(distribution,site)
    repository=str(Path(__file__).resolve().parents[2])
    output=installed_probe('all_domains', '''
import sys,tempfile
from pathlib import Path
import scidiscovery.artifact_agent.service.tool_evidence as core
import tcad_artifact.output_recovery as tcad
for module in (core,tcad):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
sys.path.append('''+repr(repository)+''')
from tests.operations.test_analysis_evidence_recovery import test_new_run_replays_original_record_from_sealed_evidence,test_offline_tools_do_not_prevent_open_or_limited_submit,test_failed_run_preserves_tool_evidence_for_new_bound_run
for test in (test_new_run_replays_original_record_from_sealed_evidence,test_offline_tools_do_not_prevent_open_or_limited_submit,test_failed_run_preserves_tool_evidence_for_new_bound_run):
    with tempfile.TemporaryDirectory() as directory:
        test(Path(directory))
import pytest
from tests.operations.test_analysis_evidence_recovery import test_corrupt_preserved_receipt_fails_successor_open_explicitly
with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as patch:
    test_corrupt_preserved_receipt_fails_successor_open_explicitly(Path(directory), patch)
print('installed recovery, replay, offline and failure handoff passed')
''')
    assert output.strip()=='installed recovery, replay, offline and failure handoff passed'


def test_installed_r4_author_delivery_and_result_registration(installed_probe):
    installed_probe("full", '"""Exercise installed schema/route projection without repository imports."""\nimport json\nfrom pathlib import Path\nfrom types import SimpleNamespace\nimport scidiscovery\nimport tcad_artifact\nfrom scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter\nfrom scidiscovery.operations.workspace import WorkspaceFinalizationRequest\nfrom tcad_artifact.project_packager import DeckProjectDraft\nassert \'site-packages\' in str(Path(scidiscovery.__file__).resolve())\nassert \'site-packages\' in str(Path(tcad_artifact.__file__).resolve())\nassert \'development_diagnostics\' in DeckProjectDraft.model_json_schema()[\'properties\']\nfacade=SimpleNamespace(runs=SimpleNamespace(),session_key=None,_instance_id=lambda:\'fixture\',\n    execution_outputs=lambda **args:{\'execution_name\':\'e\',\'result_artifact_name\':\'e.result\',\'outputs\':[{\'output_label\':\'raw\',\'artifact_name\':\'e.raw\'}]})\nrouter=RootMCPRouter(facade)\nassert router.call_tool(\'execution_outputs\',{\'name\':\'e\',\'limit\':1})[\'result_artifact_name\']==\'e.result\'\nrequest=WorkspaceFinalizationRequest(operation_id=\'fixture\',workspace=Path(\'/tmp\'),input_paths={},output_limit_bytes=1,trusted_tool_records={\'tool\':(b\'{}\',)})\ntry:request.trusted_tool_records[\'other\']=()\nexcept TypeError:pass\nelse:raise AssertionError(\'records mapping is mutable\')\nprint(json.dumps({\'installed_schema\':True,\'installed_output_binding_route\':True,\'readonly_internal_records\':True}))\n')


def test_installed_scientific_skeleton_author_contract(installed_probe):
    output = installed_probe("full", r'''
import json, tempfile
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.tooling import operation_worker_tools
from scidiscovery.platforms import initialize_platform
from tcad_artifact.execution_control import SolverCapability
catalog = compile_installed_catalog()
assert catalog.operation("science.experiment.skeleton.v1").spec.review is None
assert catalog.operation("tcad.execution-plan.project.v1").spec.executor.kind == "transform"
assert catalog.operation("tcad.execution-plan.project.v1").spec.consequence == "explore"
review_operation = catalog.operation("tcad.deck.review.v1")
assert next(port for port in review_operation.spec.inputs
            if port.name == "experiment_plan").usage == "prior_signal"
reference = next(tool for tool in operation_worker_tools(review_operation)
                 if tool.name == "worker_reference_read")
assert any(rule.schema_id == "scidiscovery.experiment-scientific-skeleton.v1"
           and rule.producer_input_alias == "research_objective"
           for rule in reference.reference_policy.rules)
root_dir = Path(tempfile.mkdtemp(prefix="installed-skeleton-"))
project = root_dir / "project"; project.mkdir()
runtime = open_runtime(project_root=project, state_root=root_dir / "state", worker_backend="local")
runtime.runs.operation_catalog = catalog
instance = runtime.scheduler_bindings.create_instance(name="skeleton", title="Installed skeleton", objective="Test installed contract.")
root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
    approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
    instance=instance.instance_id, operation_catalog=catalog))
skeleton = {"selected_hypothesis_keys": ["hypothesis_a"], **{name:["Bounded science with an evidence basis."] for name in (
    "current_objectives", "competing_explanations_and_controls", "changed_conditions", "held_conditions",
    "observables", "discrimination_criteria_and_basis", "immutable_conditions", "stop_conditions")}}
capability = SolverCapability(profile_id="fixture", solver_kind="sprocess", executable="/opt/fake/sprocess",
    environment={}, release_evidence="Fixture", public_release_label="Fixture")
for name, schema, value in (("skeleton", "scidiscovery.experiment-scientific-skeleton.v1", skeleton),
    ("capability", "tcad.solver-capability.v2", capability.public_snapshot().model_dump(mode="json")),
    ("plan", "scidiscovery.experiment-portfolio.v1", {})):
    record = runtime.artifacts.register(canonical_json(value), ArtifactRegistration(kind="fixture", schema_id=schema,
        payload_schema_version=1, media_type="application/json", creator=runtime.actor), idempotency_key=name)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name=name, object_id=record.artifact_id)
request = dict(name="author", operation_id="tcad.deck.author.initial.v1", instruction="Author the bounded installed fixture.",
    inputs=[dict(port="execution_capability", artifact_names=["capability"]), dict(port="scientific_skeleton", artifact_names=["skeleton"])])
assert root.call_tool("operation_preflight", request)["admissible"]
bad = {**request, "name":"both", "inputs":[*request["inputs"],dict(port="experiment_plan", artifact_names=["plan"])]}
assert root.call_tool("operation_preflight", bad)["reason_code"] == "input_author_plan_exact_one"
root.call_tool("operation_invoke", request)
compiled = catalog.operation("tcad.deck.author.initial.v1")
worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest,
    tool_services={"tcad_artifact:tcad.development_debug": object()})
opened = worker.call_tool("worker_open_assignment", {})
manifest = json.loads(Path(opened["domain_workspace_path"]).read_bytes())["manifest"]
assert manifest["execution_plan_relative_path"] == "deck/execution-plan.json"
initialize_platform("codex", root_dir / "installed-profile", control_socket=root_dir / "control.sock")
guide = (root_dir / "installed-profile/.codex/scidiscovery-guides/research.md").read_text()
assert "science.experiment.skeleton.v1" in guide and "comprehensive review" in guide
print("installed skeleton author admission and generated guide verified")
''')
    assert output.strip() == "installed skeleton author admission and generated guide verified"
