from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import (
    CaseExpectation,
    ComparisonContract,
    ComparisonVariable,
    IdentifiabilityClaim,
    ExperimentCase,
    ExperimentFactor,
    FactorSetting,
    PredictionTest,
    ExperimentPortfolio,
    ExperimentProposal,
    ExperimentValueAssessment,
    ResourceEstimate,
    ValidationCheck,
    ValidationDimensionPlan,
    ValidationPlan,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.input_validation import BoundSourceError
from scidiscovery.operation_contract import SemanticRuleViolation
from tcad_artifact.debug_contract import (
    CollectedTCADDebugFile,
    CollectedTCADDebugRun,
    PreparedTCADDebugRun,
)
from tcad_artifact.debug_adapter import (
    _development_arguments,
    _earliest_diagnostic,
    _source_diagnostic,
)
from tcad_artifact.execution_control import SolverCapability
from tcad_artifact.local_debug_service import LocalTCADDebugService
from tcad_artifact.plugin import (
    AUTHOR_PROMPT, PLUGIN as TCAD_PLUGIN, _author_context, _review_context,
)
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    DeckRequirementReview,
    DeckReviewReport,
    ParameterBinding,
    ProjectPreflightAttestation,
    ProjectExpectedOutput,
    ProjectInputSlot,
    ProjectResourceLimits,
    RealizationRequirement,
)
from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor


def test_sdevice_initialization_uses_the_manual_backed_initial_solution_mode() -> None:
    assert _development_arguments(
        release="R-2020.09",
        solver_kind="sdevice",
        entrypoint="initialize.cmd",
        mode="initialization",
    ) == ("-i", "initialize.cmd")
    with pytest.raises(ValueError, match="unsupported for the solver"):
        _development_arguments(
            release="R-2020.09",
            solver_kind="sdevice",
            entrypoint="main.cmd",
            mode="smoke",
        )


class _ImmediateDebugAdapter:
    def collect_with_budget(self, external_run_id, *, context):
        context.remaining_seconds()
        result = self.collect(external_run_id)
        context.remaining_seconds()
        return result

    def __init__(self) -> None:
        self.submissions = 0

    def prepare(self, *, project, capability, sources, exchange_directory, mode):
        del capability, sources, mode
        path = exchange_directory / "candidate.json"
        path.write_bytes(project)
        return PreparedTCADDebugRun(
            LocalFileDescriptor(
                name="candidate",
                local_path=str(path),
                sha256=hashlib.sha256(project).hexdigest(),
                size_bytes=len(project),
                media_type="application/json",
            ),
            30,
        )

    def clamp_wall_time(self, prepared, *, wall_time_seconds):
        return PreparedTCADDebugRun(
            prepared.submission,
            min(prepared.wall_time_seconds, wall_time_seconds),
        )

    def prepare_submission(self, prepared):
        return prepared.submission

    def submit(self, submission):
        del submission
        self.submissions += 1
        return f"local-debug-{self.submissions}", "succeeded"

    def status(self, external_run_id):
        del external_run_id
        return "succeeded"

    def cancel(self, external_run_id):
        del external_run_id
        return "cancelled"

    def collect(self, external_run_id):
        del external_run_id
        return CollectedTCADDebugRun(
            terminal_state="succeeded",
            exit_code=0,
            diagnostic_layer="complete",
            summary="bounded local debug completed",
            log_excerpt="local solver fixture",
            files=(
                CollectedTCADDebugFile(
                    name="profile.tdr",
                    media_type="application/octet-stream",
                    content=b"fixture-tdr",
                ),
            ),
        )


def _portfolio() -> ExperimentPortfolio:
    proposal = ExperimentProposal(
        experiment_key="entrypoint_smoke",
        objectives=(
            "Verify one direct solver entrypoint.",
            "Verify one bounded direct solver entrypoint.",
        ),
        current_objectives=("Verify one bounded direct solver entrypoint.",),
        frozen_invariants=("No scientific claim is made.",),
        cases=(
            ExperimentCase(
                case_key="smoke",
                scientific_role="baseline",
                purpose="Check parser and terminal state.",
            ),
        ),
        required_observables=("terminal state",),
        resource_estimate=ResourceEstimate(
            case_count=1,
            relative_cost="low",
            runtime_basis="One bounded invocation.",
        ),
        stop_conditions=("Stop after terminal state.",),
        value_assessment=ExperimentValueAssessment(
            evidence_support="high",
            discrimination_power="low",
            information_gain="medium",
            cost="low",
            added_free_parameters=0,
            rationale="This closes an implementation invariant only.",
        ),
    )
    check = ValidationCheck(
        check_key="clean_completion",
        observable="terminal state",
        metric="clean completion",
        evaluation_mode="reviewed_qualitative",
        acceptance_condition="The run completes.",
        failure_action="Reject the implementation.",
        basis="Engineering smoke contract.",
    )
    required = ValidationDimensionPlan(
        applicability="required",
        rationale="The entrypoint must terminate cleanly.",
        checks=(check,),
    )
    not_applicable = ValidationDimensionPlan(
        applicability="not_applicable",
        rationale="This bounded engineering test makes no scientific claim.",
    )
    return ExperimentPortfolio(
        study_kind="engineering",
        objective="Verify one direct solver entrypoint.",
        proposals=(proposal,),
        validation_plans=(
            ValidationPlan(
                plan_key="entrypoint_smoke_plan",
                experiment_key=proposal.experiment_key,
                numerical=required,
                physical=not_applicable,
                experimental=not_applicable,
            ),
        ),
        priority_order=(proposal.experiment_key,),
        priority_rationale="Only one implementation check is required.",
    )


def test_experiment_revision_changes_content_without_replacing_identity() -> None:
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
    from scidiscovery.general_science_experiment_components import (
        _experiment_revision_context,
    )
    from scidiscovery.operation_contract import SemanticRuleViolation

    prior = _portfolio()
    review = ScientificReview(
        review_target="experiment_portfolio",
        verdict="revise",
        summary="Clarify the bounded validation rationale.",
    )
    sources = {
        "prior_draft": canonical_json(prior.model_dump(mode="json")),
        "change_request": canonical_json(review.model_dump(mode="json")),
    }
    revised = prior.model_copy(
        update={"priority_rationale": "The review requested this clarification."}
    )
    _experiment_revision_context(revised.model_dump(mode="json"), sources, {})

    replacement = revised.model_copy(
        update={
            "objective": "Replace the experiment with another objective.",
            "proposals": (revised.proposals[0].model_copy(update={
                "objectives": (
                    "Replace the experiment with another objective.",
                    *revised.proposals[0].objectives,
                ),
            }),),
        }
    )
    with pytest.raises(SemanticRuleViolation, match="experiment identity"):
        _experiment_revision_context(
            replacement.model_dump(mode="json"), sources, {}
        )


def _project(capability: SolverCapability) -> DeckProjectDraft:
    return DeckProjectDraft(
        tool_profile=capability.profile_id,
        solver_kind="sdevice",
        capability_sha256=capability.canonical_sha256(),
        files=(DeckFile(relative_path="main.cmd", content="Solve {}\n"),),
        entrypoint="main.cmd",
        expected_outputs=(
            ProjectExpectedOutput(
                name="profile",
                relative_path="profile.tdr",
                media_type="application/octet-stream",
                max_bytes=4096,
            ),
        ),
        realization_manifest=(
            RealizationRequirement(
                requirement_key="entrypoint",
                category="numerical_protocol",
                requirement="Run one bounded fixture.",
                evidence_class="test_fixture",
                evidence_source="L4 local fixture",
                evidence_locator="main.cmd",
                rationale="Exercise the registered deck workspace.",
                implementation_status="implemented",
                relative_path="main.cmd",
                locator="Solve",
                verification_mode="static_review",
            ),
        ),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=60,
            cpu_time_seconds=60,
            max_memory_bytes=512 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=2,
        ),
    )


def _project_with_grid(capability: SolverCapability) -> DeckProjectDraft:
    project = _project(capability)
    return project.model_copy(
        update={
            "files": (
                DeckFile(
                    relative_path="main.cmd",
                    content='File { Grid="device.tdr" }\nSolve { Poisson }\n',
                ),
            ),
            "input_slots": (
                ProjectInputSlot(
                    semantic_name="device_grid",
                    target_relative_path="device.tdr",
                    media_type="application/octet-stream",
                ),
            ),
        }
    )


def _system(tmp_path: Path, *, worker_backend: str = "local", solver_kind: str = "sdevice", science_plugin=SCIENCE_PLUGIN):
    catalog = compile_catalog((CORE_PLUGIN, science_plugin, CURVE_PLUGIN, TCAD_PLUGIN))
    project_root = tmp_path / "project"
    project_root.mkdir()
    runtime = open_runtime(
        project_root=project_root,
        state_root=tmp_path / "state",
        worker_backend=worker_backend,
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="l4_tcad",
        title="L4 local TCAD",
        objective="Exercise author, debug and independent review on the minimal Run.",
    )
    capability = SolverCapability(
        profile_id="l4_local",
        solver_kind=solver_kind,
        executable=f"/opt/fake/{solver_kind}",
        environment={},
        release_evidence="Synthetic R-2020.09 fixture",
        public_release_label="Sentaurus R-2020.09",
    )
    values = (
        (
            "execution_capability",
            "solver_capability",
            "tcad.solver-capability.v2",
            2,
            canonical_json(capability.public_snapshot().model_dump(mode="json")),
        ),
        (
            "experiment_plan",
            "experiment_portfolio",
            "scidiscovery.experiment-portfolio.v1",
            1,
            canonical_json(_portfolio().model_dump(mode="json")),
        ),
    )
    for name, kind, schema_id, version, raw in values:
        artifact = runtime.artifacts.register(
            raw,
            ArtifactRegistration(
                kind=kind,
                schema_id=schema_id,
                payload_schema_version=version,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"l4:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=artifact.artifact_id,
        )
    grid = runtime.artifacts.register(
        b"bounded-device-grid",
        ArtifactRegistration(
            kind="tcad_solver_input",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="application/octet-stream",
            creator=runtime.actor,
        ),
        idempotency_key="l4:device_grid",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="device_grid",
        object_id=grid.artifact_id,
    )
    root = RootMCPRouter(
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
    return catalog, runtime, root, capability


@pytest.mark.parametrize("historical", (False, True))
def test_tcad_device_grid_is_one_declared_optional_port_and_debug_fails_closed(
    tmp_path: Path, historical: bool,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    author = catalog.operation("tcad.deck.author.revise.v1")
    port = next(item for item in author.spec.inputs if item.name == "device_grid")
    assert (port.schema_id, port.media_types, port.min_items, port.max_items) == (
        "opaque",
        ("application/octet-stream",),
        0,
        1,
    )
    assert sum(item.name == "device_grid" for item in author.spec.inputs) == 1
    for operation_id in (
        "tcad.deck.author.initial.v1",
        "tcad.deck.review.v1",
    ):
        assert not any(
            item.name == "device_grid"
            for item in catalog.operation(operation_id).spec.inputs
        )

    instance_id = runtime.scheduler_bindings.list_instances()[0].instance_id
    wrong_grid = runtime.artifacts.register(
        b"not-a-binary-grid",
        ArtifactRegistration(
            kind="tcad_solver_input",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="text/plain",
            creator=runtime.actor,
        ),
        idempotency_key="l4:wrong-device-grid",
    )
    runtime.scheduler_bindings.bind(
        instance=instance_id,
        namespace="artifact",
        name="wrong_device_grid",
        object_id=wrong_grid.artifact_id,
    )
    _invoke(
        root,
        "grid_base",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    initial = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=initial.spec.operation_id,
        operation_digest=initial.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "base-debug",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    assert worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )["state"] == "succeeded"
    assert worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "initialization", "mode": "initialization"}
    )["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    prior_name = root.call_tool("run_status", {"name": "grid_base"})[
        "output_artifact_name"
    ]

    if historical:
        changed = TCAD_PLUGIN.model_copy(update={"operations": tuple(
            op.model_copy(update={"version": "new-generation"})
            if op.operation_id == "tcad.deck.author.initial.v1" else op
            for op in TCAD_PLUGIN.operations)})
        catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, changed))
        runtime.runs.operation_catalog = catalog
        root.facade._operation_catalog = catalog
        assert root.call_tool("run_status", {"name": "grid_base"})["sealed_output_status"] == "historical"

    _invoke(
        root,
        "grid_change_request",
        "tcad.deck.review.v1",
        [
            {"port": "project", "artifact_names": [prior_name]},
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    review_operation = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=review_operation.spec.operation_id,
        operation_digest=review_operation.digest,
    )
    review_open = reviewer.call_tool("worker_open_assignment", {})
    change_request = DeckReviewReport(
        verdict="revise",
        capability_sha256=capability.canonical_sha256(),
        summary="The direct SDevice source needs one exact device grid input.",
        rationale="The source has no closed device-grid input.",
        physical_fidelity="unknown",
        implementation_fidelity="fail",
        numerical_protocol_fidelity="fail",
        requirement_reviews=(
            DeckRequirementReview(
                requirement_key="entrypoint",
                status="fail",
                rationale="The entrypoint does not bind a device grid.",
            ),
        ),
        execution_ready=False,
    )
    Path(str(review_open["output_directory"]), "result.json").write_bytes(
        canonical_json(
            {
                "schema_version": 1,
                "handoff": {
                    "verdict": "revise",
                    "summary": "Add the exact device grid input and review again.",
                },
                "payload": change_request.model_dump(mode="json"),
            }
        )
    )
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "completed"
    change_name = root.call_tool("run_status", {"name": "grid_change_request"})[
        "output_artifact_name"
    ]

    revision_inputs = [
        {"port": "prior_project", "artifact_names": [prior_name]},
        {"port": "change_request", "artifact_names": [change_name]},
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ]
    wrong_request = {
        "name": "wrong_grid",
        "operation_id": "tcad.deck.author.revise.v1",
        "inputs": [
            *revision_inputs,
            {"port": "device_grid", "artifact_names": ["wrong_device_grid"]},
        ],
        "instruction": "Exercise the declared grid input.",
    }
    refused = root.call_tool("operation_preflight", wrong_request)
    assert not refused["admissible"]
    assert refused["reason_code"] == "input_media_type_mismatch" and refused["port"] == "device_grid"
    assert refused["diagnostics"][0]["path"] == "$.inputs.device_grid"

    _invoke(
        root,
        "missing_grid",
        "tcad.deck.author.revise.v1",
        revision_inputs,
    )
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=author.spec.operation_id,
        operation_digest=author.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "missing-grid-debug",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
    assert assignment["revision"] == {
        "mode": "copy_on_write",
        "base_source_name": "prior_project",
        "editable_target": "domain_workspace",
        "publication": "complete_immutable_snapshot",
    }
    assert not Path(opened["output_directory"], "result.json").exists()
    _write_author_workspace(opened, _project_with_grid(capability))
    rejected = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert rejected["state"] == "rejected"
    assert "`diagnostics`" in AUTHOR_PROMPT
    assert "diagnostic" not in rejected
    assert any(
        "undeclared Run input" in item["message"]
        for item in rejected["diagnostics"]
    )
    runtime.runs.fail(
        runtime.scheduler_bindings.resolve(
            instance=instance_id,
            namespace="run",
            name="missing_grid",
        ),
        reason="bounded negative probe complete",
    )

    _invoke(
        root,
        "bound_grid",
        "tcad.deck.author.revise.v1",
        [
            *revision_inputs,
            {"port": "device_grid", "artifact_names": ["device_grid"]},
        ],
    )
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=author.spec.operation_id,
        operation_digest=author.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "bound-grid-debug",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project_with_grid(capability))
    assert worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"

    revised_name = root.call_tool("run_status", {"name": "bound_grid"})[
        "output_artifact_name"
    ]
    prior_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance_id, namespace="artifact", name=prior_name
        )
    ).ref
    change_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance_id, namespace="artifact", name=change_name
        )
    ).ref
    grid_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance_id, namespace="artifact", name="device_grid"
        )
    ).ref
    revised = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance_id, namespace="artifact", name=revised_name
        )
    )
    assert {prior_ref, change_ref, grid_ref}.issubset(revised.parent_refs)
    assert not runtime.runs.is_exact_reviewer_output(
        change_ref,
        reviewer_operation="tcad.deck.review.v1",
        reviewer_input_port="project",
        accepted_verdicts=("pass",),
        subject_ref=revised.ref,
    )



def test_hardened_v1_rejects_tcad_native_shell_before_run_creation(
    tmp_path: Path,
) -> None:
    _, runtime, root, _ = _system(tmp_path, worker_backend="hardened")
    catalog = root.call_tool("operation_catalog", {"scope": "all"})
    author = next(
        item
        for item in catalog["operations"]
        if item["operation_id"] == "tcad.deck.author.initial.v1"
    )
    assert author["runtime_binding"] == {
        "process": "worker",
        "required": ["native_shell"],
        "status": "unavailable",
    }
    with pytest.raises(Exception, match="operation_runtime_unavailable"):
        _invoke(
            root,
            "hardened_deck",
            "tcad.deck.author.initial.v1",
            [
                {
                    "port": "execution_capability",
                    "artifact_names": ["execution_capability"],
                },
                {
                    "port": "experiment_plan",
                    "artifact_names": ["experiment_plan"],
                },
            ],
        )
    assert runtime.runs.list(
        instance_id=runtime.scheduler_bindings.list_instances()[0].instance_id
    ) == ()


def _invoke(root, name: str, operation_id: str, inputs: list[dict[str, object]]):
    return root.call_tool(
        "operation_invoke",
        {
            "name": name,
            "operation_id": operation_id,
            "inputs": inputs,
            "instruction": "Complete the bounded L4 fixture.",
        },
    )


def _write_author_workspace(opened: dict[str, object], project: DeckProjectDraft) -> None:
    domain = json.loads(Path(str(opened["domain_workspace_path"])).read_text("utf-8"))
    assert domain["manifest"]["access"] == "native_edit"
    workspace = Path(str(opened["workspace_path"]))
    metadata = project.model_dump(mode="json")
    files = metadata.pop("files")
    (workspace / "deck/project.json").write_bytes(canonical_json(metadata))
    (workspace / "deck/handoff.json").write_bytes(
        canonical_json(
            {
                "verdict": "pass",
                "summary": "The bounded deck candidate is ready for review.",
                "assumptions": [],
                "missing_inputs": [],
                "next_actions": [],
            }
        )
    )
    for item in files:
        path = workspace / "deck/files" / item["relative_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"], encoding="utf-8")


def _debug_worker(catalog, runtime, adapter, exchange):
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    return LocalWorkerMCPRouter(
        runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={"tcad_artifact:tcad.development_debug": LocalTCADDebugService(
            adapter=adapter, exchange_root=exchange,
        )},
    )


def _write_sprocess_workspace(opened):
    workspace = Path(str(opened["workspace_path"]))
    (workspace / "deck/files/main.cmd").write_text("set case_smoke 1\nputs case_smoke\n")
    (workspace / "deck/files/initialize.cmd").write_text("set case_smoke 1\n")
    declarations_path = workspace / "deck/declarations.json"
    declarations = json.loads(declarations_path.read_bytes())
    declarations.update({
        "entrypoint": "main.cmd", "development_initialization_entrypoint": "initialize.cmd",
        "case_anchors": [{"experiment_key": "entrypoint_smoke", "case_key": "smoke",
                          "relative_path": "main.cmd", "locator": "set case_smoke 1"}],
        "raw_outputs": [],
    })
    declarations_path.write_bytes(canonical_json(declarations))
    (workspace / "deck/handoff.json").write_bytes(canonical_json({
        "verdict": "pass", "summary": "Fixture code ready for review.",
        "assumptions": [], "missing_inputs": [], "next_actions": [],
    }))


def test_local_tcad_retry_discards_control_proofs_before_debug(tmp_path):
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    inputs = [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ]
    _invoke(root, "original", "tcad.deck.author.initial.v1", inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "original-debug")
    opened = worker.call_tool("worker_open_assignment", {})
    _write_sprocess_workspace(opened)
    for name, mode in (("parser", "preflight"), ("init", "initialization"), ("snapshot", "preflight")):
        assert worker.call_tool("worker_tcad_debug_run", {"run_name": name, "mode": mode})["state"] == "succeeded"
    envelope = json.loads(Path(str(opened["output_directory"]), "result.json").read_bytes())
    assert envelope["payload"]["preflight_attestation"]["qualified"]
    assert envelope["payload"]["initialization_attestation"]["qualified"]
    status = root.call_tool("run_status", {"name": "original"})
    failed = root.call_tool("run_record_failure", {
        "name": "original", "reason": "Exercise bounded retry of an unsubmitted candidate.",
        "expected_state": "running", "expected_last_activity_at": status["last_activity_at"],
    })
    assert failed["state"] == "failed" and failed["recovery_available"]
    root.call_tool("operation_invoke", {
        "name": "retried", "operation_id": "tcad.deck.author.initial.v1",
        "inputs": inputs, "instruction": "Complete the bounded L4 fixture.", "resume_from": "original",
    })
    adapter = _ImmediateDebugAdapter()
    retry = _debug_worker(catalog, runtime, adapter, tmp_path / "retry-debug")
    restored = retry.call_tool("worker_open_assignment", {})
    workspace = Path(str(restored["workspace_path"]))
    metadata = workspace / "deck/project.json"
    assert metadata.stat().st_mode & 0o222 == 0
    assert (workspace / "deck/files/main.cmd").read_text() == "set case_smoke 1\nputs case_smoke\n"
    # This fixture has no parameter bindings from which to reconstruct its
    # case anchor. The author may complete that declaration, never metadata.
    declarations_path = workspace / "deck/declarations.json"
    declarations = json.loads(declarations_path.read_bytes())
    declarations["case_anchors"][0].update(relative_path="main.cmd", locator="set case_smoke 1")
    declarations_path.write_bytes(canonical_json(declarations))
    rejected = retry.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    debug = retry.call_tool("worker_tcad_debug_run", {"run_name": "new_parser", "mode": "preflight"})
    assert debug["state"] == "succeeded", debug
    assert adapter.submissions == 1
    assert retry.call_tool("worker_submit_result", {})["diagnostics"][0]["type"] == "tcad_initialization_missing"
    assert retry.call_tool("worker_tcad_debug_run", {"run_name": "new_init", "mode": "initialization"})["state"] == "succeeded"
    assert retry.call_tool("worker_submit_result", {})["state"] == "completed"


def test_raw_tcad_retry_clears_proofs_and_keeps_author_rejection(tmp_path):
    import shutil
    from scidiscovery.operations.workspace import (
        WorkspaceMaterializationRequest, WorkspaceFinalizationRequest, WorkspaceProtocolError,
    )
    from tcad_artifact.operation_workspace import materialize_workspace, finalize_workspace

    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    _invoke(root, "raw_source", "tcad.deck.author.initial.v1", [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ])
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "debug")
    opened = worker.call_tool("worker_open_assignment", {})
    _write_sprocess_workspace(opened)
    for name, mode in (("parser", "preflight"), ("init", "initialization"), ("snapshot", "preflight")):
        assert worker.call_tool("worker_tcad_debug_run", {"run_name": name, "mode": mode})["state"] == "succeeded"
    source = Path(str(opened["workspace_path"]))
    raw = tmp_path / "raw"
    shutil.copytree(source / "deck", raw / "deck")
    metadata = json.loads(Path(str(opened["output_directory"]), "result.json").read_bytes())["payload"]
    metadata.pop("files")
    (raw / "deck/project.json").chmod(0o600)
    (raw / "deck/project.json").write_bytes(canonical_json(metadata))
    inputs = {"execution_capability": source / "deck/contract/capability.json",
              "experiment_plan": source / "deck/contract/experiment-controls.json"}
    restored = tmp_path / "restored"
    request = WorkspaceMaterializationRequest(
        operation_id="tcad.deck.author.initial.v1", workspace=restored,
        input_paths=inputs, provisional_roots=(raw,), edit_protocol="native",
    )
    materialize_workspace(request)
    project_path = restored / "deck/project.json"
    assert project_path.stat().st_mode & 0o222 == 0
    clean = json.loads(project_path.read_bytes())
    assert all(field not in clean for field in ("materialization_report", "preflight_attestation", "initialization_attestation"))
    assert (restored / "deck/declarations.json").read_bytes() == (raw / "deck/declarations.json").read_bytes()
    assert not (restored / "deck/reports/preflight.json").exists()
    final = WorkspaceFinalizationRequest(
        operation_id=request.operation_id, workspace=restored, input_paths=inputs,
        output_limit_bytes=16 * 1024 * 1024,
    )
    with pytest.raises(WorkspaceProtocolError, match="current qualified preflight"):
        finalize_workspace(final)
    # Deliberate tampering tests the finalizer; author permissions are not widened.
    project_path.chmod(0o600)
    clean["preflight_attestation"] = metadata["preflight_attestation"]
    project_path.write_bytes(canonical_json(clean))
    with pytest.raises(WorkspaceProtocolError, match="control-owned and cannot be authored"):
        finalize_workspace(final)


class _BudgetDebugAdapter(_ImmediateDebugAdapter):
    pending = False
    failed = False

    def prepare(self, **kwargs):
        prepared = super().prepare(**kwargs)
        project = json.loads(kwargs["project"])
        return PreparedTCADDebugRun(prepared.submission, min(
            {"preflight": 60, "initialization": 120, "smoke": 180}[kwargs["mode"]],
            project["resource_limits"]["wall_time_seconds"],
        ))

    def submit(self, submission):
        binding, _ = super().submit(submission)
        return binding, "running"

    def status(self, external_run_id):
        return "running" if self.pending else "failed" if self.failed else "succeeded"

    def collect(self, external_run_id):
        if self.failed:
            return CollectedTCADDebugRun(
                terminal_state="failed", exit_code=1, diagnostic_layer="parser",
                summary="fixture syntax error", log_excerpt="fixture syntax error", files=(),
            )
        return super().collect(external_run_id)


def _budget_case(tmp_path, *, wall_seconds=600):
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(root, "budget", "tcad.deck.author.initial.v1", [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ])
    adapter = _BudgetDebugAdapter()
    worker = _debug_worker(catalog, runtime, adapter, tmp_path / "debug")
    opened = worker.call_tool("worker_open_assignment", {})
    project = _project(capability)
    project = project.model_copy(update={"resource_limits": project.resource_limits.model_copy(
        update={"wall_time_seconds": wall_seconds},
    )})
    _write_author_workspace(opened, project)
    return worker, adapter, opened


def test_local_tcad_budget_covers_pending_failure_cache_and_exhaustion(tmp_path):
    worker, adapter, opened = _budget_case(tmp_path)
    tool = next(item for item in worker.list_tools() if item["name"] == "worker_tcad_debug_run")
    assert "360" in tool["description"] and "120" in tool["description"]
    adapter.pending = True
    first = worker.call_tool("worker_tcad_debug_run", {"run_name": "p1", "mode": "preflight"})
    assert first["phase"] == "pending"
    assert first["budget"]["reserved_wall_seconds"] == 60
    assert first["reserved_wall_seconds_for_run"] == 60
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "p1", "mode": "preflight"})["budget"]["created_runs"] == 1
    adapter.pending = False
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "p1", "mode": "preflight"})["state"] == "succeeded"
    metadata = Path(str(opened["workspace_path"]), "deck/project.json")
    original = metadata.read_bytes()
    broken = json.loads(original)
    broken.pop("entrypoint")
    metadata.write_bytes(canonical_json(broken))
    rejected = worker.call_tool("worker_tcad_debug_run", {"run_name": "invalid", "mode": "initialization"})
    assert rejected["state"] == "rejected"
    assert any(item["path"] == "$.deck.entrypoint" for item in rejected["diagnostics"]), rejected["diagnostics"]
    assert rejected["budget"]["reserved_wall_seconds"] == 60
    assert adapter.submissions == 1
    metadata.write_bytes(original)
    for name, mode, used in (("i1", "initialization", 180), ("p2", "preflight", 240), ("i2", "initialization", 360)):
        adapter.failed = name == "i1"
        result = worker.call_tool("worker_tcad_debug_run", {"run_name": name, "mode": mode})
        assert result["state"] == ("failed" if adapter.failed else "succeeded")
        assert result["budget"]["reserved_wall_seconds"] == used
    reports = Path(str(opened["workspace_path"]), "deck/reports")
    diagnostic = json.loads((reports / "diagnostic-i1.json").read_bytes())
    assert diagnostic["state"] == "failed" and diagnostic["exit_code"] != 0
    assert diagnostic["source_tree_sha256"] and diagnostic["project_sha256"]
    assert "log_excerpt" in diagnostic and "run_name" not in diagnostic
    assert len(tuple(reports.glob("diagnostic-*.json"))) == 4
    cached = worker.call_tool("worker_tcad_debug_run", {"run_name": "p1", "mode": "preflight"})
    assert cached["state"] == "succeeded"
    assert cached["budget"]["remaining_wall_seconds"] == 0
    assert cached["reserved_wall_seconds_for_run"] == 60
    rejected = worker.call_tool("worker_tcad_debug_run", {"run_name": "p3", "mode": "preflight"})
    assert rejected["state"] == "rejected" and adapter.submissions == 4
    assert rejected["budget"]["remaining_runs"] == 2


def test_local_tcad_budget_clamps_and_separates_name_limit(tmp_path, monkeypatch):
    from dataclasses import replace

    worker, adapter, _ = _budget_case(tmp_path, wall_seconds=25)
    first = worker.call_tool("worker_tcad_debug_run", {"run_name": "one", "mode": "initialization"})
    assert first["reserved_wall_seconds_for_run"] == 25
    context = worker._context
    monkeypatch.setattr(worker, "_context", lambda name, tool: replace(context(name, tool), remaining_seconds=17))
    for index in range(2, 7):
        result = worker.call_tool("worker_tcad_debug_run", {"run_name": f"p{index}", "mode": "preflight"})
        assert result["reserved_wall_seconds_for_run"] == 17
        assert result["budget"]["run_remaining_seconds"] == 17
        assert result["budget"]["effective_wall_seconds"] == 17
    result = worker.call_tool("worker_tcad_debug_run", {"run_name": "seventh", "mode": "preflight"})
    assert result["state"] == "rejected" and adapter.submissions == 6
    assert result["budget"]["remaining_runs"] == 0
    assert result["budget"]["remaining_wall_seconds"] == 250
    assert "run limit" in result["diagnostics"][0]["message"]


def test_local_tcad_response_bound_includes_budget_before_sealing(tmp_path, monkeypatch):
    from dataclasses import replace

    worker, adapter, opened = _budget_case(tmp_path)
    first = worker.call_tool("worker_tcad_debug_run", {"run_name": "one", "mode": "preflight"})
    report = Path(str(opened["workspace_path"]), "deck/reports/preflight.json")
    prior = report.read_bytes()
    diagnostic = {key: value for key, value in first.items() if key not in {"budget", "reserved_wall_seconds_for_run"}}
    diagnostic["log_excerpt"] = ""
    log = "x" * (32 * 1024 - len(canonical_json(diagnostic)))
    collect = adapter.collect
    monkeypatch.setattr(adapter, "collect", lambda binding: replace(collect(binding), log_excerpt=log))
    result = worker.call_tool("worker_tcad_debug_run", {"run_name": "big", "mode": "preflight"})
    assert result["state"] == "rejected"
    assert result["budget"]["reserved_wall_seconds"] == 120
    assert len(canonical_json(result)) <= 32 * 1024
    assert report.read_bytes() == prior


# Bounded excerpts from the 2026-09-08 R-2020.09 author tool returns.
# Banners, host/user details and unrelated scientific source are omitted.
_AUTHOR_INIT_FAILURE = '''Checking syntax of fig4_initialization.cmd:
Syntax check complete.
Starting Tcl interpreter with inputfile: fig4_initialization.cmd
Creating structure...
Points: 545
Nodes: 547
Creating structure...
** Error **
No regions specified !
 ... aborting
'''
_AUTHOR_PARSER_FAILURE = '''Checking syntax of fig4_initialization.cmd:
space required after '=' in: 'fields.values={ZnMain=0.0'
    while executing
"init fields.values={ZnMain=0.0 ZnTail=0.0}"
    (file "fig4_initialization.cmd" line 12)
Failure during syntax check, aborting.
'''


@pytest.mark.parametrize("log,layer,message,line", (
    (_AUTHOR_INIT_FAILURE, "initialization", "No regions specified !", None),
    (_AUTHOR_PARSER_FAILURE, "parser", "space required after '='", 12),
))
def test_author_failure_log_has_the_actual_error_layer_and_locator(log, layer, message, line):
    assert _earliest_diagnostic(terminal="failed", exit_code=1, error="", log=log, output_count=0)[0] == layer
    locator = _source_diagnostic(error="", log=log)
    assert locator is not None and message in locator.message
    assert locator.source_relative_path == "fig4_initialization.cmd"
    assert locator.reported_line == line


@pytest.mark.parametrize("error,exit_code,layer", (
    ("syntax error near init", 1, "parser"),
    ("Newton failed to converge", 1, "numerical"),
    ("Failed to converge", 1, "numerical"),
    ("wall_time_exceeded", 124, "resource_limit"),
    ("required output missing", 0, "output_contract"),
))
def test_tcad_success_markers_do_not_override_the_actual_failure(error, exit_code, layer):
    log = "Checking syntax of main.cmd:\nSyntax check complete.\nContact setup complete.\nNewton iteration complete.\n"
    assert _earliest_diagnostic(terminal="failed", exit_code=exit_code, error=error, log=log, output_count=0)[0] == layer


def test_tcad_source_locator_stays_in_one_error_stack():
    log = '''Checking syntax of main.cmd:
syntax error in inner command
    while executing
"bad_command"
    (file "lib/inner.cmd" line 4)
    invoked from within
"source lib/inner.cmd"
    (file "main.cmd" line 99)
Checking syntax of other.cmd:
parse error in unrelated command
    (file "other.cmd" line 72)
'''
    locator = _source_diagnostic(error="", log=log)
    assert locator.source_relative_path == "lib/inner.cmd"
    assert locator.reported_line == 4 and locator.command_excerpt == "bad_command"
    private = _source_diagnostic(error="", log=log.replace("lib/inner.cmd", "/private/inner.cmd"))
    assert private.source_relative_path is None
    assert private.reported_line == 4 and private.line_basis == "solver_reported"
    assert _source_diagnostic(error="", log="Checking syntax of ../private.cmd:\nNo regions specified !").source_relative_path is None


@pytest.mark.parametrize("marker", (
    "--- bounded diagnostic omission ---", "--- bounded log omission ---",
))
def test_tcad_source_locator_does_not_cross_log_omissions(marker):
    head = "Checking syntax of main.cmd:\n"
    failure = "syntax error in first fragment\n"
    tail = '    while executing\n"unrelated_tail_command"\n    (file "other.cmd" line 72)\n'
    locator = _source_diagnostic(error="", log=head + failure + marker + "\n" + tail)
    assert locator.message == failure.strip()
    assert locator.source_relative_path == "main.cmd"
    assert locator.reported_line is None and locator.command_excerpt is None
    assert locator.line_basis == "log_only"
    # A header before an omitted region cannot locate a later error either.
    later = _source_diagnostic(error="", log=head + marker + "\n" + failure)
    assert later.source_relative_path is None and later.reported_line is None


@pytest.mark.parametrize("verdict", ("pass", "revise", "blocked"))
def test_local_tcad_author_debug_and_independent_review_share_one_operation_path(
    tmp_path: Path, verdict: str,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    adapter = _ImmediateDebugAdapter()
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=adapter,
                exchange_root=tmp_path / "debug-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    assert "tool_contracts" not in opened
    assert opened["tool_contracts_pointer"] == "/tool_contracts"
    # Necessary implementation notes travel with the sealed source, not Root-only handoff.
    source_note = "# Probe initializes production equations; the second reset path is untested.\n"
    source_path = Path(opened["workspace_path"], "deck/files/main.cmd")
    source_path.write_text(source_note + source_path.read_text())
    if verdict != "pass":
        handoff_path = Path(str(opened["workspace_path"]), "deck/handoff.json")
        handoff_path.write_bytes(canonical_json({
            "verdict": "blocked", "summary": "The exact grid input remains missing.",
            "missing_inputs": ["The direct SDevice entrypoint has no device grid."],
        }))
    debug = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert debug["state"] == "succeeded", debug
    assert debug["scientific_claim_admissible"] is False
    debug_root = Path(str(opened["workspace_path"])) / ".operation-tools/tcad/preflight"
    assert (debug_root / "profile.tdr").read_bytes() == b"fixture-tdr"
    assert not (Path(str(opened["output_directory"])) / "profile.tdr").exists()
    assert worker.call_tool("worker_submit_result", {})["diagnostics"][0]["type"] == "tcad_initialization_missing"
    assert worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "initialization", "mode": "initialization"}
    )["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    author_status = root.call_tool("run_status", {"name": "deck"})
    project_name = author_status["output_artifact_name"]

    review_request = {
        "name": "deck_review", "operation_id": "tcad.deck.review.v1",
        "inputs": [
            {"port": "project", "artifact_names": [project_name]},
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
        "instruction": "Review the exact bounded project including its implementation gaps.",
    }
    preflight = root.call_tool("operation_preflight", review_request)
    assert preflight["admissible"] is True, preflight
    root.call_tool("operation_invoke", review_request)
    review_compiled = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=review_compiled.spec.operation_id,
        operation_digest=review_compiled.digest,
    )
    review_open = reviewer.call_tool("worker_open_assignment", {})
    assert "tool_contracts" not in review_open
    assert review_open["tool_contracts_pointer"] == "/tool_contracts"
    review_domain = json.loads(
        Path(str(review_open["domain_workspace_path"])).read_text("utf-8")
    )
    assert review_domain["manifest"]["access"] == "read_only"
    reviewed_project = json.loads(
        Path(str(review_open["workspace_path"]), "deck/project.json").read_bytes()
    )
    assert Path(review_open["workspace_path"], "deck/files/main.cmd").read_text().startswith(source_note)
    assert reviewed_project["initialization_attestation"]["qualified"] is True
    assert reviewed_project["initialization_attestation"]["project_sha256"] == reviewed_project["preflight_attestation"]["project_sha256"]
    snapshot = capability.public_snapshot()
    review = DeckReviewReport(
        verdict="pass",
        capability_sha256=snapshot.capability_sha256,
        summary="The exact bounded project is internally consistent.",
        rationale="The source, capability and declared requirement were reviewed.",
        physical_fidelity="pass",
        implementation_fidelity="pass",
        syntax_fidelity="pass",
        numerical_protocol_fidelity="pass",
        requirement_reviews=(
            DeckRequirementReview(
                requirement_key="entrypoint",
                status="pass",
                rationale="The declared entrypoint is present in the exact source.",
            ),
        ),
        execution_ready=True,
    )
    if verdict != "pass":
        review = review.model_copy(update={
            "verdict": verdict, "execution_ready": False, "implementation_fidelity": "fail",
            "missing_inputs": ("The direct SDevice entrypoint has no device grid.",),
        })
    Path(str(review_open["output_directory"]), "result.json").write_bytes(
        canonical_json(
            {
                "schema_version": 1,
                "handoff": {
                    "verdict": verdict,
                    "summary": "The exact TCAD project received independent review.",
                },
                "payload": review.model_dump(mode="json"),
            }
        )
    )
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "completed"
    review_status = root.call_tool("run_status", {"name": "deck_review", "view": "detail"})
    assert review_status["state"] == "completed"
    assert review_status["sealed_output"]["payload"]["verdict"] == verdict
    assert review_status["sealed_output"]["payload"]["execution_ready"] is (verdict == "pass")
    if verdict != "pass":
        package_request = {
            "name": "blocked_package", "operation_id": "tcad.reviewed-deck-package.v2",
            "inputs": [
                {"port": "project", "artifact_names": [project_name]},
                {"port": "review", "artifact_names": [review_status["output_artifact_name"]]},
                {"port": "capability", "artifact_names": ["execution_capability"]},
                {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
            ],
        }
        denied = root.call_tool("operation_preflight", package_request)
        assert denied["admissible"] is False
        assert denied["reason_code"] == "input_independent_review_missing"
        with pytest.raises(Exception, match="input_independent_review_missing"):
            root.call_tool("operation_invoke", package_request)
        # An effect still requires the declared reviewed-package schema.
        denied = root.call_tool("operation_preflight", {
            "name": "blocked_execution", "operation_id": "tcad.study.execute",
            "inputs": [{"port": "reviewed_package", "artifact_names": [project_name]}],
        })
        assert denied["admissible"] is False
        assert denied["reason_code"] == "input_schema_mismatch"
        assert root.call_tool("run_status", {"name": "deck"})["scheduler_signal"]["verdict"] == "blocked"
    assert not hasattr(runtime, "tasks") and not hasattr(runtime, "tokens")


@pytest.mark.parametrize("change", (
    "missing", "failed", "source", "entrypoint", "declaration", "initialization",
    "initialization_failed", "initialization_stale",
))
def test_author_submission_requires_current_control_diagnostics(tmp_path, change):
    class Adapter(_ImmediateDebugAdapter):
        failed = change == "failed"

        def collect(self, external_run_id):
            if not self.failed:
                return super().collect(external_run_id)
            return CollectedTCADDebugRun(
                terminal_state="failed", exit_code=1, diagnostic_layer="parser",
                summary="fixture parser failure", log_excerpt="fixture failure", files=(),
            )

    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(root, "diagnostics", "tcad.deck.author.initial.v1", [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ])
    operation = catalog.operation("tcad.deck.author.initial.v1")
    adapter = Adapter()
    worker = LocalWorkerMCPRouter(
        runtime.runs, operation_id=operation.spec.operation_id, operation_digest=operation.digest,
        tool_services={"tcad_artifact:tcad.development_debug": LocalTCADDebugService(
            adapter=adapter, exchange_root=tmp_path / "debug",
        )},
    )
    opened = worker.call_tool("worker_open_assignment", {})
    project = _project(capability).model_copy(update={
        "files": (*_project(capability).files, DeckFile(relative_path="initialize.cmd", content="Solve {}\n")),
        "development_initialization_entrypoint": "initialize.cmd",
    })
    _write_author_workspace(opened, project)
    workspace = Path(str(opened["workspace_path"]))
    if change != "missing":
        result = worker.call_tool("worker_tcad_debug_run", {"run_name": "first", "mode": "preflight"})
        assert result["state"] == ("failed" if change == "failed" else "succeeded")
    if change in {"initialization_failed", "initialization_stale"}:
        adapter.failed = change == "initialization_failed"
        result = worker.call_tool("worker_tcad_debug_run", {"run_name": "first_init", "mode": "initialization"})
        assert result["state"] == ("failed" if adapter.failed else "succeeded")
    if change in {"source", "initialization_stale"}:
        (workspace / "deck/files/main.cmd").write_text("Solve {}\n# changed\n", encoding="utf-8")
    elif change in {"entrypoint", "declaration"}:
        path = workspace / "deck/project.json"
        metadata = json.loads(path.read_bytes())
        if change == "entrypoint":
            metadata["entrypoint"] = "initialize.cmd"
        else:
            metadata["expected_outputs"][0]["relative_path"] = "changed.tdr"
        path.write_bytes(canonical_json(metadata))
    if change == "initialization_stale":
        assert worker.call_tool("worker_tcad_debug_run", {"run_name": "new_source", "mode": "preflight"})["state"] == "succeeded"
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    expected = {
        "missing": "tcad_preflight_missing", "failed": "tcad_preflight_failed",
        "initialization": "tcad_initialization_missing",
        "initialization_failed": "tcad_initialization_failed",
        "initialization_stale": "tcad_initialization_stale",
    }.get(change, "tcad_preflight_stale")
    assert rejected["diagnostics"][0]["type"] == expected
    assert root.call_tool("run_status", {"name": "diagnostics"})["state"] == "running"
    adapter.failed = False
    # A stale or failed report cannot deadlock the next debug candidate.
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "corrected", "mode": "preflight"})["state"] == "succeeded"
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "initialized", "mode": "initialization"})["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_materialized_sprocess_binds_declarations_and_seals_initialization(tmp_path):
    catalog, runtime, root, capability = _system(tmp_path, solver_kind="sprocess")
    _invoke(root, "process", "tcad.deck.author.initial.v1", [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
    ])
    operation = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs, operation_id=operation.spec.operation_id, operation_digest=operation.digest,
        tool_services={"tcad_artifact:tcad.development_debug": LocalTCADDebugService(
            adapter=_ImmediateDebugAdapter(), exchange_root=tmp_path / "debug",
        )},
    )
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(str(opened["workspace_path"]))
    (workspace / "deck/files/main.cmd").write_text("set case_smoke 1\nputs case_smoke\n", encoding="utf-8")
    (workspace / "deck/files/initialize.cmd").write_text("set case_smoke 1\n", encoding="utf-8")
    declarations_path = workspace / "deck/declarations.json"
    declarations = json.loads(declarations_path.read_bytes())
    declarations.update({
        "entrypoint": "main.cmd", "development_initialization_entrypoint": "initialize.cmd",
        "case_anchors": [{"experiment_key": "entrypoint_smoke", "case_key": "smoke",
                          "relative_path": "main.cmd", "locator": "set case_smoke 1"}],
        "raw_outputs": [],
    })
    declarations_path.write_bytes(canonical_json(declarations))
    (workspace / "deck/handoff.json").write_bytes(canonical_json({
        "verdict": "pass", "summary": "Fixture code ready for review.",
        "assumptions": [], "missing_inputs": [], "next_actions": [],
    }))
    assert worker.call_tool("worker_submit_result", {})["diagnostics"][0]["type"] == "tcad_preflight_missing"
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "first", "mode": "preflight"})["state"] == "succeeded"
    # This engineering plan has no comparison bindings; even its unprojected
    # source anchor must invalidate diagnostic evidence when changed.
    declarations["case_anchors"][0]["locator"] = "puts case_smoke"
    declarations_path.write_bytes(canonical_json(declarations))
    assert worker.call_tool("worker_submit_result", {})["diagnostics"][0]["type"] == "tcad_preflight_stale"
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "second", "mode": "preflight"})["state"] == "succeeded"
    assert worker.call_tool("worker_tcad_debug_run", {"run_name": "initialized", "mode": "initialization"})["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    project = json.loads(Path(str(opened["output_directory"]), "result.json").read_bytes())["payload"]
    assert project["materialization_report"]["status"] == "pass"
    assert project["initialization_attestation"]["qualified"] is True
    assert project["initialization_attestation"]["declarations_sha256"] == project["preflight_attestation"]["declarations_sha256"]


def test_local_tcad_finalizer_rejects_a_source_file_above_eight_mib(
    tmp_path: Path,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "oversized_deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "debug-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    project = _project(capability)
    _write_author_workspace(opened, project)
    Path(str(opened["workspace_path"]), "deck/files/main.cmd").write_text(
        "x" * (8 * 1024 * 1024 + 1), encoding="utf-8"
    )
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert any("byte limit" in item["message"] for item in rejected["diagnostics"])
    assert root.call_tool("run_status", {"name": "oversized_deck"})["state"] == "running"


def test_local_tcad_debug_preserves_candidate_validation_diagnostics(
    tmp_path: Path,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "invalid_debug_deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "invalid-debug-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    metadata_path = Path(str(opened["workspace_path"]), "deck/project.json")
    metadata = json.loads(metadata_path.read_text("utf-8"))
    metadata.pop("entrypoint")
    metadata_path.write_bytes(canonical_json(metadata))

    debug = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert debug["state"] == "rejected"
    assert any(item["path"] == "$.deck.entrypoint" for item in debug["diagnostics"])
    assert worker.call_tool("worker_submit_result", {})["diagnostics"] == debug["diagnostics"]
    assert debug["budget"]["reserved_wall_seconds"] == 0
    assert root.call_tool("run_status", {"name": "invalid_debug_deck"})[
        "state"
    ] == "running"


def test_local_tcad_debug_treats_checker_failure_as_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError

    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "broken_checker_deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "broken-checker-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))

    def fail_checker(_value, **_kwargs):
        raise RunCheckerError("fixture checker defect")

    monkeypatch.setattr(runtime.runs, "_validated_candidate", fail_checker)
    debug = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert debug == {"state": "failed", "diagnostics": []}
    status = root.call_tool("run_status", {"name": "broken_checker_deck"})
    assert status["state"] == "failed"
    assert status["reason"] == "Run validation framework failure: fixture checker defect"


def test_local_tcad_debug_rejects_a_private_output_symlink(
    tmp_path: Path,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "symlink_deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "debug-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    tool_root = Path(str(opened["workspace_path"])) / ".operation-tools"
    tool_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tool_root / "tcad").symlink_to(outside, target_is_directory=True)

    rejected = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert rejected["state"] == "rejected"
    assert any(
        "unavailable" in item["message"] for item in rejected["diagnostics"]
    )
    assert not (outside / "preflight/profile.tdr").exists()


def test_local_tcad_debug_rejects_a_preflight_parent_symlink(
    tmp_path: Path,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "preflight_symlink_deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "debug-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    reports = Path(str(opened["workspace_path"])) / "deck/reports"
    outside = tmp_path / "outside-preflight"
    outside.mkdir()
    reports.symlink_to(outside, target_is_directory=True)

    rejected = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert rejected["state"] == "rejected"
    assert not (outside / "preflight.json").exists()
    assert root.call_tool("run_status", {"name": "preflight_symlink_deck"})[
        "state"
    ] == "running"


def test_local_tcad_finalizer_rejects_an_output_root_symlink(
    tmp_path: Path,
) -> None:
    catalog, runtime, root, capability = _system(tmp_path)
    _invoke(
        root,
        "output_symlink_deck",
        "tcad.deck.author.initial.v1",
        [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    compiled = catalog.operation("tcad.deck.author.initial.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
        tool_services={
            "tcad_artifact:tcad.development_debug": LocalTCADDebugService(
                adapter=_ImmediateDebugAdapter(),
                exchange_root=tmp_path / "debug-exchange",
            )
        },
    )
    opened = worker.call_tool("worker_open_assignment", {})
    _write_author_workspace(opened, _project(capability))
    output = Path(str(opened["output_directory"]))
    output.rmdir()
    outside = tmp_path / "outside-output"
    outside.mkdir()
    output.symlink_to(outside, target_is_directory=True)

    rejected = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert rejected["state"] == "failed"
    assert not (outside / "result.json").exists()
    assert root.call_tool("run_status", {"name": "output_symlink_deck"})[
        "state"
    ] == "failed"


def _review_context_fixture(defect):
    capability = SolverCapability(
        profile_id="review_fixture", solver_kind="sdevice", executable="/opt/fake/sdevice",
        environment={}, release_evidence="Synthetic fixture", public_release_label="R-2020.09",
    )
    project = _project(capability)
    plan = _portfolio()
    sources = {}
    if defect == "case":
        proposal = plan.proposals[0]
        contract = ComparisonContract(
            baseline_case_key="smoke", comparison_case_keys=("comparison",),
            variables=(ComparisonVariable(
                variable_key="bias", scientific_path="device.bias", factor_type="physical",
                comparison_role="intended_change", unit="V", equivalence_rule="exact",
                expectations=(CaseExpectation(case_key="smoke", value=0.0),
                              CaseExpectation(case_key="comparison", value=1.0)),
                rationale="Compare two declared biases.",
            ),),
            required_observables=proposal.required_observables,
            identifiability_claims=(IdentifiabilityClaim(
                hypothesis_key="fixture", observable="terminal state",
                distinguishing_outcome="Both cases complete.", decision_rule="Review both cases.",
                ambiguity_conditions=("A missing case cannot support the comparison.",),
                smallest_resolving_control="Implement the missing case.",
            ),),
        )
        proposal = proposal.model_copy(update={
            "cases": tuple(ExperimentCase(
                case_key=key, scientific_role=role, purpose="Compare bias.",
                settings=(FactorSetting(name="bias", value=value, unit="V"),),
            ) for key, role, value in (("smoke", "baseline", 0.0), ("comparison", "perturbation", 1.0))),
            "comparison_contract": contract, "hypothesis_keys": ("fixture",),
            "changed_factors": (ExperimentFactor(
                name="bias", factor_type="physical", values=(0.0, 1.0), unit="V", rationale="Compare bias.",
            ),),
            "prediction_tests": (PredictionTest(
                hypothesis_key="fixture", prediction_key="completion", observable="terminal state",
                expected_result="Both cases complete.", falsifying_result="One case fails.",
            ),),
            "resource_estimate": proposal.resource_estimate.model_copy(update={"case_count": 2}),
        })
        plan = plan.model_copy(update={
            "proposals": (proposal,), "study_kind": "scientific", "objective_key": "fixture_objective",
            "selected_hypothesis_keys": ("fixture",),
        })
    elif defect in {"value", "unit", "uncertainty", "none"}:
        project = project.model_copy(update={"parameter_bindings": (ParameterBinding(
            name="bias", approved_parameter_key="bias", declared_value="2.0e+0" if defect == "value" else "1.0e+0",
            unit="mV" if defect == "unit" else "V", relative_path="main.cmd", locator="Solve",
            requirement_keys=("entrypoint",),
        ),)})
        sources["device_parameters"] = canonical_json({
            "parameter_set_key": "parameters", "requirement_set_key": "requirements",
            "title": "Fixture parameters", "objective": "Bound one bias.",
            "claims": [{"parameter_key": "bias", "selected_value": "1.0e+0", "unit": "V",
                        "epistemic_status": "user_defined", "selection_rationale": "Fixture input."}],
        })
        sources["parameter_coverage"] = canonical_json({
            "requirement_set_key": "requirements", "parameter_set_key": "parameters",
            "source_catalog_key": "sources", "status": "pass", "confirmed_count": 1,
            "review_count": 0, "blocking_count": 0,
            "items": [{"parameter_key": "bias", "status": "confirmed", "selected_value": "1.0e+0",
                       "canonical_unit": "V", "independent_source_count": 1, "summary": "Fixture coverage."}],
        })
        if defect == "uncertainty":
            sources["parameter_uncertainty"] = canonical_json({
                "requirement_set_key": "requirements", "parameter_set_key": "parameters",
                "status": "blocking_unbounded", "items": [{
                    "parameter_key": "bias", "classification": "blocking_unbounded",
                    "canonical_unit": "V", "rationale": "Missing finite bounds.",
                }],
            })
    digest = hashlib.sha256()
    for item in sorted(project.files, key=lambda item: item.relative_path):
        digest.update(item.relative_path.encode() + b"\0" + item.content.encode() + b"\0")
    project = project.model_copy(update={"preflight_attestation": ProjectPreflightAttestation(
        source_tree_sha256=digest.hexdigest(), terminal_state="succeeded", exit_code=0,
        diagnostic_layer="complete", qualified=True, summary="Synthetic source-bound preflight.",
    )})
    sources.update({
        "project": canonical_json(project.model_dump(mode="json")),
        "experiment_plan": canonical_json(plan.model_dump(mode="json")),
        "execution_capability": canonical_json(capability.public_snapshot().model_dump(mode="json")),
    })
    report = DeckReviewReport(
        verdict="pass", capability_sha256=project.capability_sha256,
        summary="Fixture review", rationale="Check the exact declared implementation.",
        physical_fidelity="pass", implementation_fidelity="pass", syntax_fidelity="pass",
        numerical_protocol_fidelity="pass", execution_ready=True,
        requirement_reviews=(DeckRequirementReview(
            requirement_key="entrypoint", status="pass", rationale="The entrypoint exists.",
        ),),
    ).model_dump(mode="json")
    return project, sources, report


@pytest.mark.parametrize("defect", ("case", "value", "unit", "uncertainty"))
@pytest.mark.parametrize("verdict", ("revise", "blocked"))
def test_negative_deck_review_can_report_implementation_defects(defect, verdict):
    project, sources, report = _review_context_fixture(defect)
    report.update(verdict=verdict, execution_ready=False, implementation_fidelity="fail",
                  missing_inputs=[f"Resolve the {defect} implementation gap."])
    _review_context(report, sources, {"verdict": verdict})
    if defect == "uncertainty":
        # Input uncertainty is a design/review consideration, not an output prerequisite.
        _author_context(project.model_dump(mode="json"), sources, {"verdict": "blocked"})
    else:
        with pytest.raises(SemanticRuleViolation):
            _author_context(project.model_dump(mode="json"), sources, {"verdict": "blocked"})


@pytest.mark.parametrize("defect, diagnostic", (
    ("case", "case_parameter_bindings"), ("value", "approved parameter value"),
    ("unit", "approved parameter value"), ("uncertainty", "blocking-unbounded"),
))
def test_deck_review_checks_implementation_without_rechecking_input_readiness(defect, diagnostic):
    _, sources, report = _review_context_fixture(defect)
    if defect == "uncertainty":
        _review_context(report, sources, {"verdict": "pass"})
    else:
        with pytest.raises(SemanticRuleViolation, match=diagnostic):
            _review_context(report, sources, {"verdict": "pass"})


@pytest.mark.parametrize("verdict", ("pass", "revise", "blocked"))
@pytest.mark.parametrize("mismatch", (
    "project_parse", "plan_parse", "parameters_parse", "coverage_parse", "uncertainty_parse",
    "coverage_identity", "missing_coverage", "approved_key", "handoff", "subject", "capability",
))
def test_deck_review_keeps_exact_input_and_report_validation(verdict, mismatch):
    project, sources, report = _review_context_fixture("none")
    report.update(verdict=verdict, execution_ready=verdict == "pass")
    handoff = {"verdict": verdict}
    if mismatch.endswith("_parse"):
        port = {"parameters": "device_parameters", "plan": "experiment_plan"}.get(
            mismatch[:-6], mismatch[:-6])
        if port == "coverage":
            port = "parameter_coverage"
        if port == "uncertainty":
            port = "parameter_uncertainty"
        sources[port] = b"{}"
    elif mismatch == "coverage_identity":
        coverage = json.loads(sources["parameter_coverage"])
        coverage["parameter_set_key"] = "another_set"
        sources["parameter_coverage"] = canonical_json(coverage)
    elif mismatch == "missing_coverage":
        sources.pop("parameter_coverage")
    elif mismatch == "approved_key":
        value = project.model_dump(mode="json")
        value["parameter_bindings"][0]["approved_parameter_key"] = "unknown"
        sources["project"] = canonical_json(value)
    elif mismatch == "handoff":
        handoff["verdict"] = "blocked" if verdict != "blocked" else "revise"
    elif mismatch == "subject":
        report["requirement_reviews"][0]["requirement_key"] = "another_subject"
    elif mismatch == "capability":
        report["capability_sha256"] = "f" * 64
    if mismatch in {"coverage_identity", "missing_coverage", "parameters_parse", "coverage_parse"}:
        from tcad_artifact.plugin import _parameter_inputs
        with pytest.raises(Exception):
            _parameter_inputs(sources)
    elif mismatch == "uncertainty_parse" or (mismatch == "approved_key" and verdict != "pass"):
        _review_context(report, sources, handoff)
    else:
        with pytest.raises((SemanticRuleViolation, ValidationError, BoundSourceError)):
            _review_context(report, sources, handoff)


@pytest.mark.parametrize("defect", ("case", "unknown_key"))
def test_local_review_rejects_false_pass_then_seals_missing_case_report(tmp_path, defect):
    catalog, runtime, root, capability = _system(tmp_path)
    project, sources, report = _review_context_fixture("case")
    if defect == "unknown_key":
        project = project.model_copy(update={"parameter_bindings": (ParameterBinding(
            name="bias", approved_parameter_key="unknown", declared_value="1", unit="V",
            relative_path="main.cmd", locator="Solve", requirement_keys=("entrypoint",)),)})
    project = project.model_copy(update={
        "tool_profile": capability.profile_id, "capability_sha256": capability.canonical_sha256(),
    })
    report["capability_sha256"] = capability.canonical_sha256()
    sources["project"] = canonical_json(project.model_dump(mode="json"))
    instance = runtime.scheduler_bindings.list_instances()[0].instance_id
    for name, schema, kind, raw in (
        ("case_project", "tcad.deck-project.v1", "tcad_project", sources["project"]),
        ("case_plan", "scidiscovery.experiment-portfolio.v1", "experiment_portfolio", sources["experiment_plan"]),
    ):
        artifact = runtime.artifacts.register(raw, ArtifactRegistration(
            kind=kind, schema_id=schema, payload_schema_version=1,
            media_type="application/json", creator=runtime.actor,
        ), idempotency_key=f"p1:{name}")
        runtime.scheduler_bindings.bind(
            instance=instance, namespace="artifact", name=name, object_id=artifact.artifact_id,
        )
    request = {
        "name": "case_review", "operation_id": "tcad.deck.review.v1",
        "inputs": [
            {"port": "project", "artifact_names": ["case_project"]},
            {"port": "experiment_plan", "artifact_names": ["case_plan"]},
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        ], "instruction": "Review the fixture's missing declared case implementation.",
    }
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    root.call_tool("operation_invoke", request)
    compiled = catalog.operation("tcad.deck.review.v1")
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                  operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(str(opened["workspace_path"]))
    project_path = workspace / "deck/project.json"
    frozen_project = project_path.read_bytes()
    assert project_path.stat().st_mode & 0o222 == 0
    output = Path(str(opened["output_directory"]), "result.json")
    output.write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": "pass", "summary": "Fixture false pass."},
        "payload": report,
    }))
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert "case_parameter_bindings" in str(rejected["diagnostics"])
    assert root.call_tool("run_status", {"name": "case_review"})["state"] == "running"
    report.update(verdict="blocked", execution_ready=False, implementation_fidelity="fail",
                  missing_inputs=["Both declared case bias bindings are absent."])
    for change, diagnostic in (("readiness", "execution_ready"), ("subject", "realization manifest")):
        candidate = json.loads(canonical_json(report))
        verdict = "blocked"
        if change == "readiness":
            candidate["execution_ready"] = True
        else:
            candidate["requirement_reviews"][0]["requirement_key"] = "wrong_subject"
        output.write_bytes(canonical_json({
            "schema_version": 1, "handoff": {"verdict": verdict, "summary": "Fixture mismatch."},
            "payload": candidate,
        }))
        rejected = worker.call_tool("worker_submit_result", {})
        assert rejected["state"] == "rejected"
        assert diagnostic in str(rejected["diagnostics"])
    output.write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": "revise", "summary": "Missing case controls."},
        "payload": report,
    }))
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    status = root.call_tool("run_status", {"name": "case_review"})
    assert status["state"] == "completed"
    assert status["sealed_output"]["payload"]["missing_inputs"] == report["missing_inputs"]
    assert status["sealed_output"]["payload"]["execution_ready"] is False
    assert status["scheduler_signal"]["verdict"] == "blocked"
    assert project_path.read_bytes() == frozen_project


from scidiscovery.operation_contract import semantic_contract
from scidiscovery.operations.spec import ComponentRef, ComponentSpec, SemanticRuleSpec


PLAN_FIXTURE_SEMANTIC_CONTRACT = semantic_contract(SemanticRuleSpec(
    rule_id="fixture.plan.schema", description="The fixture output is a valid experiment portfolio.",
))


def _plan_producer_plugin():
    """Small real Agent producer; retain the compiled scientific review edge."""
    revision = next(op for op in SCIENCE_PLUGIN.operations
                    if op.operation_id == "science.experiment.revise.v1")
    producer = revision.model_copy(update={
        "operation_id": "science.fixture.plan.v1",
        "input_validation": None,
        "inputs": (revision.inputs[2].model_copy(update={"min_items": 0}),), "guards": (),
        "outputs": (revision.outputs[0].model_copy(update={
            "semantic_contract": ComponentRef("fixture_plan_contract"),
            "validator": ComponentRef("fixture_plan_validator"),
            "validator_rule_id": "fixture.plan.schema",
            "context_validator": None, "context_rule_id": None, "context_sources": (),
        }),),
    })
    reviewer = next(op for op in SCIENCE_PLUGIN.operations
                    if op.operation_id == "science.object.review.v1")
    wrong_reviewer = reviewer.model_copy(update={
        "operation_id": "science.fixture.unrelated-review.v1",
        "inputs": tuple(port.model_copy(update={"usage": "evidence_inventory"})
                        if port.name == "experiment_plan" else port for port in reviewer.inputs),
    })
    validator = next(item for item in SCIENCE_PLUGIN.components
                     if item.component_id == "experiment_portfolio_validator")
    return SCIENCE_PLUGIN.model_copy(update={
        "operations": (*SCIENCE_PLUGIN.operations, producer, wrong_reviewer),
        "components": (*SCIENCE_PLUGIN.components,
            ComponentSpec("fixture_plan_contract", "resource",
                          "tests.operations.test_l4_local_tcad:PLAN_FIXTURE_SEMANTIC_CONTRACT"),
            validator.model_copy(update={"component_id": "fixture_plan_validator",
                                         "resources": (ComponentRef("fixture_plan_contract"),)}),
        ),
    })


def _complete_plan_fixture(catalog, runtime, root, name, operation_id, payload, inputs=(), verdict="pass"):
    _invoke(root, name, operation_id, list(inputs))
    compiled = catalog.operation(operation_id)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation_id,
                                 operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    Path(str(opened["output_directory"]), "result.json").write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": verdict, "summary": "Bounded admission fixture."},
        "payload": payload,
    }))
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", json.dumps(submitted, indent=2)
    status = root.call_tool("run_status", {"name": name})
    assert status["state"] == "completed"
    return status["output_artifact_name"]


@pytest.mark.parametrize("produced", (False, True), ids=("imported-plan", "reviewed-producer-plan"))
@pytest.mark.parametrize("with_controls", (False, True), ids=("single-case-no-controls", "comparison"))
def test_materialized_sprocess_author_review_package_preserves_case_anchors(tmp_path, monkeypatch, produced, with_controls):
    catalog, runtime, root, capability = _system(
        tmp_path, solver_kind="sprocess", science_plugin=_plan_producer_plugin() if produced else SCIENCE_PLUGIN,
    )
    _, sources, _ = _review_context_fixture("case")
    if not with_controls:
        sources["experiment_plan"] = canonical_json(_portfolio().model_dump(mode="json"))
    artifact = runtime.artifacts.register(sources["experiment_plan"], ArtifactRegistration(
        kind="experiment_portfolio", schema_id="scidiscovery.experiment-portfolio.v1",
        payload_schema_version=1, media_type="application/json", creator=runtime.actor,
    ), idempotency_key="p1:comparison-plan")
    plan_name = "comparison_plan"
    runtime.scheduler_bindings.bind(
        instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
        namespace="artifact", name=plan_name, object_id=artifact.artifact_id,
    )
    experiment_review_name = None
    if produced:
        plan_name = _complete_plan_fixture(
            catalog, runtime, root, "produced_plan", "science.fixture.plan.v1",
            json.loads(sources["experiment_plan"]),
        )
        experiment_review_name = _complete_plan_fixture(
            catalog, runtime, root, "plan_review", "science.object.review.v1",
            {"review_target": "experiment_portfolio", "verdict": "pass", "summary": "Plan is consistent."},
            [{"port": "experiment_plan", "artifact_names": [plan_name]}],
        )
    plan_proofs = ([{"port": "experiment_review", "artifact_names": [experiment_review_name]}]
                   if experiment_review_name is not None else [])
    _invoke(root, "process", "tcad.deck.author.initial.v1", [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": [plan_name]},
        *plan_proofs,
    ])
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "debug")
    opened = worker.call_tool("worker_open_assignment", {})
    _write_sprocess_workspace(opened)
    workspace = Path(str(opened["workspace_path"]))
    (workspace / "deck/files/main.cmd").write_text("set bias_smoke 0.0\nset bias_comparison 1.0\n")
    path = workspace / "deck/declarations.json"
    declarations = json.loads(path.read_bytes())
    declarations["case_anchors"] = [
        {"experiment_key": "entrypoint_smoke", "case_key": key,
         "relative_path": "main.cmd", "locator": f"set bias_{key} {value}"}
        for key, value in ((("smoke", "0.0"), ("comparison", "1.0"))
                           if with_controls else (("smoke", "0.0"),))
    ]
    path.write_bytes(canonical_json(declarations))
    for mode in ("preflight", "initialization"):
        assert worker.call_tool("worker_tcad_debug_run", {"run_name": mode, "mode": mode})["state"] == "succeeded"
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    project_name = root.call_tool("run_status", {"name": "process"})["output_artifact_name"]
    _invoke(root, "process_review", "tcad.deck.review.v1", [
        {"port": "project", "artifact_names": [project_name]},
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": [plan_name]},
        *plan_proofs,
    ])
    compiled = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
                                    operation_digest=compiled.digest)
    review_open = reviewer.call_tool("worker_open_assignment", {})
    review = DeckReviewReport(
        verdict="pass", capability_sha256=capability.canonical_sha256(),
        summary="The materialized fixture is ready.", rationale="Its bounded requirements are realized.",
        physical_fidelity="pass", implementation_fidelity="pass", syntax_fidelity="pass",
        numerical_protocol_fidelity="pass", execution_ready=True,
    )
    Path(str(review_open["output_directory"]), "result.json").write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": "pass", "summary": "Ready for packaging."},
        "payload": review.model_dump(mode="json"),
    }))
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "completed"
    review_name = root.call_tool("run_status", {"name": "process_review"})["output_artifact_name"]
    package_request = {
        "name": "process_package", "operation_id": "tcad.reviewed-deck-package.v2",
        "inputs": [
            {"port": "project", "artifact_names": [project_name]},
            {"port": "review", "artifact_names": [review_name]},
            {"port": "capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": [plan_name]},
        ],
    }
    if produced:
        from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
        from tcad_artifact import operation_transforms

        other_plan = _complete_plan_fixture(
            catalog, runtime, root, "other_plan", "science.fixture.plan.v1",
            {**json.loads(sources["experiment_plan"]), "priority_rationale": "A different bounded plan."},
        )
        invalid_reviews = [None]
        for name, subject, operation_id, verdict in (
            ("other_plan_review", other_plan, "science.object.review.v1", "pass"),
            ("nonpass_plan_review", plan_name, "science.object.review.v1", "revise"),
            ("wrong_plan_reviewer", plan_name, "science.fixture.unrelated-review.v1", "pass"),
        ):
            invalid_reviews.append(_complete_plan_fixture(
                catalog, runtime, root, name, operation_id,
                {"review_target": "experiment_portfolio", "verdict": verdict, "summary": name},
                [{"port": "experiment_plan", "artifact_names": [subject]}], verdict,
            ))
        with monkeypatch.context() as patch:
            def forbidden_package(*args, **kwargs):
                pytest.fail("Invalid plan proof reached the business implementation")
            patch.setattr(operation_transforms, "package_reviewed_project", forbidden_package)
            for invalid in invalid_reviews:
                request = {**package_request, "inputs": [*package_request["inputs"]]}
                if invalid is not None:
                    request["inputs"].append({"port": "experiment_review", "artifact_names": [invalid]})
                denied = root.call_tool("operation_preflight", request)
                assert denied["admissible"] is False
                assert denied["reason_code"] == "input_independent_review_missing"
                with pytest.raises(RootToolError, match="input_independent_review_missing"):
                    root.call_tool("operation_invoke", request)
        # Removing the proof port still compiles, but leaves this real producer blocked.
        without_proof = TCAD_PLUGIN.model_copy(update={"operations": tuple(
            op.model_copy(update={"inputs": tuple(port for port in op.inputs
                                                  if port.name != "experiment_review")})
            if op.operation_id == "tcad.reviewed-deck-package.v2" else op
            for op in TCAD_PLUGIN.operations
        )})
        missing_catalog = compile_catalog((CORE_PLUGIN, _plan_producer_plugin(), CURVE_PLUGIN, without_proof))
        missing_root = RootMCPRouter(RootToolFacade(
            runtime.artifacts, runtime.intake, runs=runtime.runs,
            approvals=runtime.approvals, executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
            operation_catalog=missing_catalog,
        ))
        assert missing_root.call_tool("operation_preflight", package_request)["reason_code"] == "input_independent_review_missing"
        with pytest.raises(RootToolError, match="input_independent_review_missing"):
            missing_root.call_tool("operation_invoke", package_request)
        package_request["inputs"].append({
            "port": "experiment_review", "artifact_names": [experiment_review_name],
        })
        unknown = {**package_request, "inputs": [*package_request["inputs"],
                   {"port": "undeclared_proof", "artifact_names": [experiment_review_name]}]}
        assert root.call_tool("operation_preflight", unknown)["admissible"] is False
    assert root.call_tool("operation_preflight", package_request)["admissible"] is True
    from tcad_artifact import operation_transforms
    business_package = operation_transforms.package_reviewed_project
    business_calls = []

    def checked_projection(inputs):
        assert set(inputs) == {"project", "review", "capability", "experiment_plan"}
        business_calls.append(set(inputs))
        return business_package(inputs)

    with monkeypatch.context() as patch:
        patch.setattr(operation_transforms, "package_reviewed_project", checked_projection)
        packaged = root.call_tool("operation_invoke", package_request)
    assert business_calls

    assert packaged["executor_kind"] == "transform"
    assert len(packaged["result"]["outputs"]) == 1
    package_name = packaged["result"]["outputs"][0]["artifact_name"]
    package_id = runtime.scheduler_bindings.resolve(
        instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
        namespace="artifact", name=package_name,
    )
    envelope = runtime.artifacts.get_by_id(package_id)
    if produced:
        proof_id = runtime.scheduler_bindings.resolve(
            instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
            namespace="artifact", name=experiment_review_name,
        )
        assert proof_id in {ref.artifact_id for ref in envelope.parent_refs}
    package = json.loads(runtime.artifacts.read(envelope.ref))
    author_project = root.call_tool("run_status", {"name": "process", "view": "detail"})["sealed_output"]["payload"]
    assert len(author_project["case_parameter_bindings"]) == (2 if with_controls else 0)
    assert author_project["case_anchors"] == declarations["case_anchors"]
    assert package["project"]["case_anchors"] == declarations["case_anchors"]
    from tcad_artifact.project_materializer import declarations_template
    sealed = DeckProjectDraft.model_validate_json(canonical_json(author_project), strict=True)
    assert declarations_template(sources["experiment_plan"], base_project=sealed)["case_anchors"] == declarations["case_anchors"]
    assert author_project["initialization_attestation"]["qualified"] is True
    assert canonical_json(package["project"]["initialization_attestation"]) == canonical_json(
        author_project["initialization_attestation"]
    )
    assert package["review"] == review.model_dump(mode="json")

    from tcad_artifact import transform_adapter

    exact_inputs = {
        "project": canonical_json(author_project),
        "review": canonical_json(review.model_dump(mode="json")),
        "capability": canonical_json(capability.public_snapshot().model_dump(mode="json")),
        "experiment_plan": sources["experiment_plan"],
    }
    # Historical serialization and proof digests must survive the added field.
    # Emulate the pre-fix producer which never retained case_anchors.
    legacy = dict(author_project)
    legacy.pop("case_anchors")
    legacy_digest = hashlib.sha256(canonical_json({
        key: value for key, value in legacy.items()
        if key not in {"preflight_attestation", "initialization_attestation", "materialization_report"}
    })).hexdigest()
    for field in ("preflight_attestation", "initialization_attestation"):
        legacy[field] = {**legacy[field], "project_sha256": legacy_digest}
    legacy_raw = canonical_json(legacy)
    assert canonical_json(DeckProjectDraft.model_validate_json(legacy_raw, strict=True).model_dump(mode="json")) == legacy_raw
    legacy_package = transform_adapter.package_reviewed_project({**exact_inputs, "project": legacy_raw})
    assert canonical_json(json.loads(legacy_package["reviewed_package"][0])["project"]) == legacy_raw

    # Removing a new project's retained anchors invalidates its bound proof;
    # it must not silently turn into a compatible historical object.
    stripped = dict(author_project)
    stripped.pop("case_anchors")
    with pytest.raises(ValidationError, match="project digest differs"):
        transform_adapter.package_reviewed_project({**exact_inputs, "project": canonical_json(stripped)})
    # An explicitly empty declaration is not the same as historical absence.
    from tcad_artifact.project_materializer import ProjectMaterializationError
    from tcad_artifact.project_packager import project_debug_sha256
    empty = sealed.model_copy(update={"case_anchors": (), "preflight_attestation": None,
                                      "initialization_attestation": None})
    empty = empty.model_copy(update={"preflight_attestation": sealed.preflight_attestation.model_copy(
        update={"project_sha256": project_debug_sha256(empty)})})
    with pytest.raises(ProjectMaterializationError, match="no declared source anchor"):
        transform_adapter.package_reviewed_project({**exact_inputs, "project": canonical_json(empty.model_dump(mode="json"))})
    for field, diagnostic in (("source_tree_sha256", "source digest differs"),
                               ("project_sha256", "project digest differs")):
        changed = json.loads(exact_inputs["project"])
        changed["initialization_attestation"][field] = "f" * 64
        with pytest.raises(ValidationError, match=diagnostic):
            transform_adapter.package_reviewed_project({
                **exact_inputs, "project": canonical_json(changed),
            })

    materialize = transform_adapter.materialize_deck_project
    for field, diagnostic in (("arguments", "project digest differs"),
                               ("materialization_report", "differs from deterministic rematerialization")):
        def changed_rebuild(**kwargs):
            rebuilt = materialize(**kwargs)
            if field == "arguments":
                return rebuilt.model_copy(update={"arguments": ("changed",)})
            return rebuilt.model_copy(update={"materialization_report":
                rebuilt.materialization_report.model_copy(update={"generated_case_bindings": 3})})

        with monkeypatch.context() as patch:
            patch.setattr(transform_adapter, "materialize_deck_project", changed_rebuild)
            with pytest.raises(ValueError, match=diagnostic):
                transform_adapter.package_reviewed_project(exact_inputs)

    # A historical absent proof stays absent; packaging does not synthesize one.
    absent = json.loads(exact_inputs["project"])
    absent["initialization_attestation"] = None
    result = transform_adapter.package_reviewed_project({
        **exact_inputs, "project": canonical_json(absent),
    })
    assert json.loads(result["reviewed_package"][0])["project"]["initialization_attestation"] is None


def _task_gap():
    return {"schema_version": 1, "result_kind": "implementation_gap",
            "summary": "The task requires unavailable implementation inputs.",
            "missing_inputs": [],
            "affected_work": [{"plan_locator": "/proposals/0", "impact": "Cannot construct the requested domain."}],
            "suggested_resolution": "Reassess the task using the bound evidence and supported capability."}


def _write_gap(opened, *, raw=None):
    deck = Path(str(opened["workspace_path"])) / "deck"
    (deck / "gap.json").write_bytes(canonical_json(_task_gap()) if raw is None else raw)
    (deck / "handoff.json").write_bytes(canonical_json({
        "verdict": "blocked", "summary": "Implementation is unavailable.", "missing_inputs": [],
    }))


def test_author_gap_submits_without_source_and_has_independent_review(tmp_path):
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    inputs = [{"port": "execution_capability", "artifact_names": ["execution_capability"]},
              {"port": "experiment_plan", "artifact_names": ["experiment_plan"]}]
    _invoke(root, "gap_author", "tcad.deck.author.initial.v1", inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "unused-debug")
    opened = worker.call_tool("worker_open_assignment", {})
    _write_gap(opened)
    gap = _task_gap()
    gap['affected_work'][0]['plan_locator'] = '/missing_plan_field'
    _write_gap(opened, raw=canonical_json(gap))
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    detail = rejected['diagnostics'][0]
    assert detail['path'] == '$.deck.gap.affected_work[0].plan_locator'
    assert detail['message'] == 'gap plan_locator must be an existing JSON pointer in experiment_plan'
    assert runtime.runs.diagnostic_summary(runtime.runs.status(worker._run_id))['latest_rejection']['details'] == rejected['diagnostics']
    _write_gap(opened)
    # No source, materialization or solver diagnostics are necessary for a negative result.
    assert not tuple(Path(str(opened["workspace_path"]), "deck/files").iterdir())
    handoff_path = Path(str(opened["workspace_path"]), "deck/handoff.json")
    invalid_handoff = json.loads(handoff_path.read_bytes())
    invalid_handoff["summary"] = ""
    handoff_path.write_bytes(canonical_json(invalid_handoff))
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert rejected["diagnostics"][0]["path"] == "$.deck.handoff.summary"
    # A stale mirror is projected from the formal gap before sealing.
    handoff_path.write_bytes(canonical_json({"verdict": "pass", "summary": "The task has an implementation gap.", "missing_inputs": []}))
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", json.dumps(submitted, indent=2)
    status = root.call_tool("run_status", {"name": "gap_author"})
    assert status["scheduler_signal"]["verdict"] == "blocked"
    name = status["output_artifact_name"]
    review_request = {"name": "gap_review", "operation_id": "tcad.deck.review.v1",
                      "inputs": [{"port": "project", "artifact_names": [name]}, *inputs],
                      "instruction": "Independently assess this exact task gap."}
    assert root.call_tool("operation_preflight", review_request)["admissible"]
    root.call_tool("operation_invoke", review_request)
    compiled = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    reviewed = reviewer.call_tool("worker_open_assignment", {})
    deck = Path(str(reviewed["workspace_path"])) / "deck"
    assert {k: v for k, v in json.loads((deck / "gap.json").read_bytes()).items() if k != "attempt_files"} == _task_gap()
    envelope = json.loads((deck / "review-template.json").read_bytes())
    envelope["handoff"]["summary"] = "The exact gap was reviewed."
    envelope["payload"]["summary"] = "The task is not executable from the bound inputs."
    envelope["payload"]["rationale"] = "No physical implementation exists; redesign or input evidence is needed."
    Path(str(reviewed["output_directory"]), "result.json").write_bytes(canonical_json(envelope))
    result = reviewer.call_tool("worker_submit_result", {})
    assert result["state"] == "completed", result
    from tcad_artifact.project_packager import DeckProjectDraft
    with pytest.raises(ValueError):
        DeckProjectDraft.model_validate_json(canonical_json(_task_gap()), strict=True)


@pytest.mark.parametrize("change", ["new_gap", "new_source", "malformed_gap"])
def test_author_failure_recovers_latest_domain_draft_through_run(tmp_path, change):
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    inputs = [{"port": "execution_capability", "artifact_names": ["execution_capability"]},
              {"port": "experiment_plan", "artifact_names": ["experiment_plan"]}]
    _invoke(root, "original_gap", "tcad.deck.author.initial.v1", inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "unused-debug")
    opened = worker.call_tool("worker_open_assignment", {})
    deck = Path(str(opened["workspace_path"])) / "deck"
    if change == "malformed_gap":
        _write_gap(opened, raw=b'{"result_kind":')
    else:
        _write_gap(opened)
        # An older output candidate must not override later domain edits.
        Path(str(opened["output_directory"]), "result.json").write_bytes(canonical_json({
            "schema_version": 1, "payload": _task_gap(),
            "handoff": {"verdict": "blocked", "summary": "Old candidate.", "missing_inputs": []},
        }))
        (deck / "files/main.cmd").write_text("set newer_source 1\n")
        if change == "new_source":
            (deck / "gap.json").unlink()
    status = root.call_tool("run_status", {"name": "original_gap"})
    failed = root.call_tool("run_record_failure", {
        "name": "original_gap", "reason": "Exercise failed draft preservation.",
        "expected_state": "running", "expected_last_activity_at": status["last_activity_at"],
    })
    assert failed["state"] == "failed" and failed["recovery_available"], failed
    root.call_tool("operation_invoke", {"name": "retry_gap", "operation_id": "tcad.deck.author.initial.v1",
        "inputs": inputs, "instruction": "Complete the bounded L4 fixture.", "resume_from": "original_gap"})
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "retry-debug")
    restored = worker.call_tool("worker_open_assignment", {})
    restored_deck = Path(str(restored["workspace_path"])) / "deck"
    if change == "new_source":
        assert not (restored_deck / "gap.json").exists()
        assert (restored_deck / "files/main.cmd").read_text() == "set newer_source 1\n"
    elif change == "malformed_gap":
        assert (restored_deck / "gap.json").read_bytes() == b'{"result_kind":'
        assert worker.call_tool("worker_submit_result", {})["state"] == "rejected"
    else:
        assert json.loads((restored_deck / "gap.json").read_bytes()) == _task_gap()
        assert worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_domain_snapshot_rejects_symlinked_deck_root(tmp_path):
    import shutil
    catalog, runtime, root, _ = _system(tmp_path, solver_kind="sprocess")
    inputs = [{"port": "execution_capability", "artifact_names": ["execution_capability"]},
              {"port": "experiment_plan", "artifact_names": ["experiment_plan"]}]
    _invoke(root, "outside_gap", "tcad.deck.author.initial.v1", inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / "unused-debug")
    opened = worker.call_tool("worker_open_assignment", {})
    _write_gap(opened)
    deck = Path(str(opened["workspace_path"])) / "deck"
    outside = tmp_path / "unbound-deck"
    shutil.move(str(deck), outside)
    deck.symlink_to(outside, target_is_directory=True)
    assert worker.call_tool("worker_submit_result", {})["state"] == "rejected"
    status = root.call_tool("run_status", {"name": "outside_gap"})
    failed = root.call_tool("run_record_failure", {
        "name": "outside_gap", "reason": "Check snapshot source confinement.",
        "expected_state": "running", "expected_last_activity_at": status["last_activity_at"],
    })
    assert failed["state"] == "failed" and not failed["recovery_available"]
    assert failed["recovery"]["recovery_pending"] is True
    assert runtime.runs.status(worker._run_id).recovery_draft["code"] == "snapshot_unavailable"
    assert (outside / "gap.json").read_bytes() == canonical_json(_task_gap())


@pytest.mark.parametrize("verdict", ["revise", "blocked"])
def test_negative_review_can_report_conflicting_parameter_coverage(verdict):
    _, sources, report = _review_context_fixture("none")
    coverage = json.loads(sources["parameter_coverage"])
    coverage.update(status="fail", confirmed_count=0, blocking_count=1)
    coverage["items"][0]["status"] = "conflict"
    sources["parameter_coverage"] = canonical_json(coverage)
    report.update(verdict=verdict, execution_ready=False, implementation_fidelity="fail")
    _review_context(report, sources, {"verdict": verdict})
    report.update(verdict="pass", execution_ready=True, implementation_fidelity="pass")
    with pytest.raises(SemanticRuleViolation):
        _review_context(report, sources, {"verdict": "pass"})
