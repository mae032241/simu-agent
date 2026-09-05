from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import (
    ExperimentCase,
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
from tcad_artifact.debug_contract import (
    CollectedTCADDebugFile,
    CollectedTCADDebugRun,
    PreparedTCADDebugRun,
)
from tcad_artifact.debug_adapter import _development_arguments
from tcad_artifact.execution_control import SolverCapability
from tcad_artifact.local_debug_service import LocalTCADDebugService
from tcad_artifact.plugin import AUTHOR_PROMPT, PLUGIN as TCAD_PLUGIN
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    DeckRequirementReview,
    DeckReviewReport,
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
        objective="Verify one bounded direct solver entrypoint.",
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
        update={"objective": "Replace the experiment with another objective."}
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


def _system(tmp_path: Path, *, worker_backend: str = "local"):
    catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
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
        solver_kind="sdevice",
        executable="/opt/fake/sdevice",
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


def test_tcad_device_grid_is_one_declared_optional_port_and_debug_fails_closed(
    tmp_path: Path,
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
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    prior_name = root.call_tool("run_status", {"name": "grid_base"})[
        "output_artifact_name"
    ]

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
    assert root.call_tool("operation_preflight", wrong_request) == {
        "admissible": False,
        "reason_code": "input_media_type_mismatch",
        "port": "device_grid",
        "executor_kind": None,
    }

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
    with pytest.raises(Exception, match="runtime_backend_capability_missing"):
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


def test_local_tcad_author_debug_and_independent_review_share_one_operation_path(
    tmp_path: Path,
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
    debug = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert debug["state"] == "succeeded", debug
    assert debug["scientific_claim_admissible"] is False
    debug_root = Path(str(opened["workspace_path"])) / ".operation-tools/tcad/preflight"
    assert (debug_root / "profile.tdr").read_bytes() == b"fixture-tdr"
    assert not (Path(str(opened["output_directory"])) / "profile.tdr").exists()
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    author_status = root.call_tool("run_status", {"name": "deck"})
    project_name = author_status["output_artifact_name"]

    _invoke(
        root,
        "deck_review",
        "tcad.deck.review.v1",
        [
            {"port": "project", "artifact_names": [project_name]},
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
    )
    review_compiled = catalog.operation("tcad.deck.review.v1")
    reviewer = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=review_compiled.spec.operation_id,
        operation_digest=review_compiled.digest,
    )
    review_open = reviewer.call_tool("worker_open_assignment", {})
    review_domain = json.loads(
        Path(str(review_open["domain_workspace_path"])).read_text("utf-8")
    )
    assert review_domain["manifest"]["access"] == "read_only"
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
    Path(str(review_open["output_directory"]), "result.json").write_bytes(
        canonical_json(
            {
                "schema_version": 1,
                "handoff": {
                    "verdict": "pass",
                    "summary": "The exact TCAD project passed independent review.",
                },
                "payload": review.model_dump(mode="json"),
            }
        )
    )
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "completed"
    review_status = root.call_tool("run_status", {"name": "deck_review"})
    assert review_status["state"] == "completed"
    assert not hasattr(runtime, "tasks") and not hasattr(runtime, "tokens")


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
    assert worker.call_tool("worker_submit_result", {}) == debug
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

    def fail_checker(_value):
        raise RunCheckerError("fixture checker defect")

    monkeypatch.setattr(runtime.runs, "_validated_candidate", fail_checker)
    debug = worker.call_tool(
        "worker_tcad_debug_run", {"run_name": "preflight", "mode": "preflight"}
    )
    assert debug == {"state": "failed", "diagnostics": []}
    status = root.call_tool("run_status", {"name": "broken_checker_deck"})
    assert status["state"] == "failed"
    assert "fixture checker defect" in status["reason"]


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
    assert rejected["state"] == "rejected"
    assert not (outside / "result.json").exists()
    assert root.call_tool("run_status", {"name": "output_symlink_deck"})[
        "state"
    ] == "running"
