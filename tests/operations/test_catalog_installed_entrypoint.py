from __future__ import annotations

import json

import pytest


_EXPECTED_OPERATION_IDS = [
    "science.evidence.audit.intake.v1",
    "science.evidence.audit.v1",
    "science.evidence.extract.v1",
    "science.evidence.qualify.v1",
    "science.evidence.revise-from-critic.v1",
    "science.experiment.design.v1",
    "science.experiment.materialize.v1",
    "science.experiment.revise.v1",
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
assert source_key["enum"] == ["source_material"]
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

output.write_bytes(result("source_material"))
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
