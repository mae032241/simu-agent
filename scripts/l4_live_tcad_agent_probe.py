#!/usr/bin/env python3
"""Prepare and verify the persistent direct-Agent L4 TCAD probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PLUGIN_ROOTS = (
    REPOSITORY / "plugins/curve_score",
    REPOSITORY / "plugins/tcad_artifact",
)
for candidate in (REPOSITORY, REPOSITORY / "src", *PLUGIN_ROOTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from curve_score.plugin import PLUGIN as CURVE_PLUGIN  # noqa: E402
from scripts import run_compiled_codex_worker as launcher  # noqa: E402
from scidiscovery.artifact_agent.interfaces.mcp_root import (  # noqa: E402
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime  # noqa: E402
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration  # noqa: E402
from scidiscovery.artifact_agent.schema.common import canonical_json  # noqa: E402
from scidiscovery.artifact_agent.schema.experiment import (  # noqa: E402
    ExperimentCase,
    ExperimentPortfolio,
    ExperimentProposal,
    ExperimentValueAssessment,
    ResourceEstimate,
    ValidationCheck,
    ValidationDimensionPlan,
    ValidationPlan,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN  # noqa: E402
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN  # noqa: E402
from scidiscovery.operations.catalog import compile_catalog  # noqa: E402
from scidiscovery.operations.tooling import (  # noqa: E402
    operation_agent_type,
    operation_local_worker_tool_names,
    operation_worker_server_name,
)
from scidiscovery.platforms.codex import initialize  # noqa: E402
from tcad_artifact.execution_control import SolverCapability  # noqa: E402
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN  # noqa: E402
from tcad_artifact.project_packager import DeckProjectDraft  # noqa: E402


AUTHOR_OPERATION = "tcad.deck.author.initial.v1"
REVIEW_OPERATION = "tcad.deck.review.v1"
LAUNCHER_MEMORY_LIMIT_MIB = 4096
AUTHOR_LAUNCHER_RECEIPT = "tcad_author_launcher_receipt"
REVIEW_LAUNCHER_RECEIPT = "tcad_reviewer_launcher_receipt"


def _catalog():
    return compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))


def _runtime(root: Path):
    runtime = open_runtime(
        project_root=root / "project",
        state_root=root / "state",
        worker_backend="local",
    )
    assert runtime.runs is not None
    runtime.runs.operation_catalog = _catalog()
    return runtime


def _root(runtime, instance_id: str):
    return RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance_id,
            operation_catalog=runtime.runs.operation_catalog,
        )
    )


def _portfolio() -> ExperimentPortfolio:
    proposal = ExperimentProposal(
        experiment_key="entrypoint_smoke",
        objectives=(
            "Verify the Local TCAD author-debug-review path.",
            "Verify one bounded SDevice entrypoint.",
        ),
        current_objectives=("Verify one bounded SDevice entrypoint.",),
        frozen_invariants=("No physical conclusion is claimed.",),
        cases=(
            ExperimentCase(
                case_key="smoke",
                scientific_role="baseline",
                purpose="Check the direct-solver development path.",
            ),
        ),
        required_observables=("terminal state",),
        resource_estimate=ResourceEstimate(
            case_count=1,
            relative_cost="low",
            runtime_basis="One deterministic transport invocation.",
        ),
        stop_conditions=("Stop after the preflight result.",),
        value_assessment=ExperimentValueAssessment(
            evidence_support="high",
            discrimination_power="low",
            information_gain="medium",
            cost="low",
            added_free_parameters=0,
            rationale="This validates the registered implementation boundary only.",
        ),
    )
    required = ValidationDimensionPlan(
        applicability="required",
        rationale="The entrypoint must complete the bounded preflight.",
        checks=(
            ValidationCheck(
                check_key="clean_completion",
                observable="terminal state",
                metric="clean completion",
                evaluation_mode="reviewed_qualitative",
                acceptance_condition="The fixture returns a successful terminal state.",
                failure_action="Request a deck revision.",
                basis="L4 implementation probe.",
            ),
        ),
    )
    not_applicable = ValidationDimensionPlan(
        applicability="not_applicable",
        rationale="The probe makes no physical or experimental claim.",
    )
    return ExperimentPortfolio(
        study_kind="engineering",
        objective="Verify the Local TCAD author-debug-review path.",
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
        priority_rationale="One bounded implementation probe is sufficient.",
    )


def _capability() -> SolverCapability:
    return SolverCapability(
        profile_id="l4_live",
        solver_kind="sdevice",
        executable="/opt/synopsys/sdevice",
        environment={},
        release_evidence="L4 deterministic Sentaurus R-2020.09 fixture",
        public_release_label="Sentaurus R-2020.09",
    )


def _standalone_python_path(root: Path) -> Path:
    target = root / "pythonpath"
    target.mkdir()
    for source, name in (
        (REPOSITORY / "src/scidiscovery", "scidiscovery"),
        (REPOSITORY / "plugins/curve_score/curve_score", "curve_score"),
        (REPOSITORY / "plugins/tcad_artifact/tcad_artifact", "tcad_artifact"),
    ):
        os.symlink(source, target / name, target_is_directory=True)
    metadata = target / "scidiscovery_l4_probe-0.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: scidiscovery-l4-probe\nVersion: 0.0\n",
        "utf-8",
    )
    (metadata / "entry_points.txt").write_text(
        "[scidiscovery.plugins]\n"
        "builtin = scidiscovery.builtin_plugin:CORE_PLUGIN\n"
        "general_science = scidiscovery.general_science_plugin:PLUGIN\n"
        "curve_score = curve_score.plugin:PLUGIN\n"
        "tcad_artifact = tcad_artifact.plugin:PLUGIN\n",
        "utf-8",
    )
    return target


def _control(root: Path) -> dict[str, str]:
    return json.loads((root / "control.json").read_text("utf-8"))


def _write_control(root: Path, value: dict[str, str]) -> None:
    (root / "control.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8"
    )


def _write_dispatch(
    root: Path,
    *,
    label: str,
    operation_id: str,
    python_path: Path,
    receipt_name: str | None = None,
    require_tcad_debug: bool | None = None,
) -> None:
    compiled = _catalog().operation(operation_id)
    agent_type = operation_agent_type(compiled)
    author_like = (
        operation_id == AUTHOR_OPERATION
        if require_tcad_debug is None
        else require_tcad_debug
    )
    required = ["worker_open_assignment"]
    if author_like:
        required.append("worker_tcad_debug_run")
    required.append("worker_submit_result")
    if receipt_name is None:
        receipt_name = (
            AUTHOR_LAUNCHER_RECEIPT if author_like else REVIEW_LAUNCHER_RECEIPT
        )
    launcher_command = [
        sys.executable,
        str(REPOSITORY / "scripts/run_compiled_codex_worker.py"),
        "--project-root",
        str(root / "project"),
        "--agent-type",
        agent_type,
        "--memory-limit-mib",
        str(LAUNCHER_MEMORY_LIMIT_MIB),
        "--receipt-name",
        receipt_name,
    ]
    if launcher._inside_codex_outer_sandbox():
        launcher_command.append("--externally-sandboxed-debug")
    (root / f"{label}-dispatch.json").write_text(
        json.dumps(
            {
                "generated_profile": str(
                    root
                    / "project/.codex/agents"
                    / f"{agent_type}.toml"
                ),
                "expected_agent_type": agent_type,
                "launcher_command": launcher_command,
                "required_worker_calls": required,
                "standalone_python_path": str(python_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )


def _verify_operation_launch(
    root: Path,
    *,
    control: dict[str, object],
    run: dict[str, object],
    operation_id: str,
    agent_type: str,
    receipt_name: str,
    required_worker_tools: set[str],
) -> str:
    compiled = _catalog().operation(operation_id)
    try:
        return launcher.verify_receipt(
            receipt_path=root / "launch-receipts" / f"{receipt_name}.json",
            project_root=root / "project",
            agent_type=agent_type,
            expected_target_server=operation_worker_server_name(compiled),
            allowed_worker_tools=set(operation_local_worker_tool_names(compiled)),
            required_worker_tools=required_worker_tools,
            run_started_at=str(run["started_at"]),
            run_completed_at=str(run["completed_at"]),
            expected_memory_limit_mib=int(control["launcher_memory_limit_mib"]),
            expected_external_sandbox_debug=bool(
                control["launcher_externally_sandboxed_debug"]
            ),
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise SystemExit(str(error)) from error


def prepare(root: Path) -> None:
    if root.exists():
        raise SystemExit(f"refusing to overwrite existing probe: {root}")
    (root / "project").mkdir(parents=True)
    (root / "project/AGENTS.md").write_text("# L4 direct TCAD probe\n", "utf-8")
    python_path = _standalone_python_path(root)
    capability = _capability()
    capability_path = root / "capability.json"
    capability_path.write_bytes(
        canonical_json(capability.public_snapshot().model_dump(mode="json"))
    )
    command_config = root / "command-adapter.json"
    command_config.write_text(
        json.dumps(
            {
                "executable": sys.executable,
                "arguments": [str(REPOSITORY / "scripts/l4_tcad_transport_fixture.py")],
                "environment": {"SCID_L4_CAPABILITY_FILE": str(capability_path)},
                "operation_timeout_seconds": 30,
            },
            sort_keys=True,
        ),
        "utf-8",
    )
    plugin_config = root / "tcad-plugin.json"
    plugin_config.write_text(
        json.dumps(
            {
                "transport": "command",
                "command_config_path": str(command_config),
            },
            sort_keys=True,
        ),
        "utf-8",
    )
    runtime = _runtime(root)
    catalog = runtime.runs.operation_catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="l4_live_tcad",
        title="L4 direct TCAD probe",
        objective="Verify one real Agent author-debug-review path on the minimal Run.",
    )
    for name, kind, schema_id, version, raw in (
        (
            "execution_capability",
            "solver_capability",
            "tcad.solver-capability.v2",
            2,
            capability_path.read_bytes(),
        ),
        (
            "experiment_plan",
            "experiment_portfolio",
            "scidiscovery.experiment-portfolio.v1",
            1,
            canonical_json(_portfolio().model_dump(mode="json")),
        ),
    ):
        artifact = runtime.artifacts.register(
            raw,
            ArtifactRegistration(
                kind=kind,
                schema_id=schema_id,
                payload_schema_version=version,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"l4-live:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=artifact.artifact_id,
        )
    router = _root(runtime, instance.instance_id)
    current = router.call_tool("instance_current", {})
    if current.get("name") != instance.name or current.get("state") != "active":
        raise SystemExit("L4 probe is not bound to the created active instance")
    request = {
        "name": "author",
        "operation_id": AUTHOR_OPERATION,
        "inputs": [
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
        "instruction": (
            "Create one minimal SDevice project with main.cmd as entrypoint, no "
            "input slots, one optional profile.tdr output, an implemented "
            "entrypoint requirement, empty arguments, and bounded resources. "
            "Call preflight before submitting."
        ),
    }
    preflight = router.call_tool("operation_preflight", request)
    if preflight.get("admissible") is not True:
        raise SystemExit(f"author preflight rejected: {preflight}")
    invoked = router.call_tool("operation_invoke", request)
    initialize(
        root / "project",
        python_executable=Path(sys.executable),
        python_path=python_path,
        control_socket=root / "unused-control.sock",
        state_root=root / "state",
        operation_catalog=catalog,
        runtime_plugin_configs={"tcad_artifact": plugin_config},
    )
    _write_control(
        root,
        {
            "instance_id": instance.instance_id,
            "author_run_name": "author",
            "author_agent_type": invoked["result"]["agent_type"],
            "author_launcher_receipt": AUTHOR_LAUNCHER_RECEIPT,
            "review_launcher_receipt": REVIEW_LAUNCHER_RECEIPT,
            "launcher_externally_sandboxed_debug": launcher._inside_codex_outer_sandbox(),
            "launcher_memory_limit_mib": LAUNCHER_MEMORY_LIMIT_MIB,
            "instance_current_checked": True,
        },
    )
    _write_dispatch(
        root,
        label="author",
        operation_id=AUTHOR_OPERATION,
        python_path=python_path,
    )


def queue_review(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    router = _root(runtime, control["instance_id"])
    author = router.call_tool("run_status", {"name": control["author_run_name"]})
    if author["state"] != "completed":
        raise SystemExit(f"author Run is not complete: {author['state']}")
    _verify_operation_launch(
        root,
        control=control,
        run=author,
        operation_id=AUTHOR_OPERATION,
        agent_type=control["author_agent_type"],
        receipt_name=control["author_launcher_receipt"],
        required_worker_tools={
            "worker_open_assignment",
            "worker_tcad_debug_run",
            "worker_submit_result",
        },
    )
    author_run_id = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"],
        namespace="run",
        name=control["author_run_name"],
    )
    if "worker_tcad_debug_run" not in runtime.runs.successful_tools(author_run_id):
        raise SystemExit("author Run has no successful TCAD debug tool activity")
    project_name = author["output_artifact_name"]
    project_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="artifact",
            name=project_name,
        )
    ).ref
    project = DeckProjectDraft.model_validate_json(
        runtime.artifacts.read(project_ref), strict=True
    )
    if project.preflight_attestation is None or not project.preflight_attestation.qualified:
        raise SystemExit("author output has no qualified preflight attestation")
    request = {
        "name": "reviewer",
        "operation_id": REVIEW_OPERATION,
        "inputs": [
            {"port": "project", "artifact_names": [project_name]},
            {"port": "execution_capability", "artifact_names": ["execution_capability"]},
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
        "instruction": "Independently review the exact completed TCAD project.",
    }
    preflight = router.call_tool("operation_preflight", request)
    if preflight.get("admissible") is not True:
        raise SystemExit(f"review preflight rejected: {preflight}")
    invoked = router.call_tool("operation_invoke", request)
    control.update(
        {
            "project_name": project_name,
            "review_run_name": "reviewer",
            "review_agent_type": invoked["result"]["agent_type"],
        }
    )
    _write_control(root, control)
    _write_dispatch(
        root,
        label="reviewer",
        operation_id=REVIEW_OPERATION,
        python_path=root / "pythonpath",
    )


def status(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    router = _root(runtime, control["instance_id"])
    author = router.call_tool("run_status", {"name": control["author_run_name"]})
    review = router.call_tool("run_status", {"name": control["review_run_name"]})
    if author["state"] != "completed" or review["state"] != "completed":
        raise SystemExit("L4 author-reviewer probe is incomplete")
    author_invocation = _verify_operation_launch(
        root,
        control=control,
        run=author,
        operation_id=AUTHOR_OPERATION,
        agent_type=control["author_agent_type"],
        receipt_name=control["author_launcher_receipt"],
        required_worker_tools={
            "worker_open_assignment",
            "worker_tcad_debug_run",
            "worker_submit_result",
        },
    )
    review_invocation = _verify_operation_launch(
        root,
        control=control,
        run=review,
        operation_id=REVIEW_OPERATION,
        agent_type=control["review_agent_type"],
        receipt_name=control["review_launcher_receipt"],
        required_worker_tools={
            "worker_open_assignment",
            "worker_submit_result",
        },
    )
    if author_invocation == review_invocation:
        raise SystemExit("TCAD author and reviewer reused one launcher invocation")
    project_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="artifact",
            name=control["project_name"],
        )
    ).ref
    review_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=control["instance_id"],
            namespace="artifact",
            name=review["output_artifact_name"],
        )
    ).ref
    project = DeckProjectDraft.model_validate_json(
        runtime.artifacts.read(project_ref), strict=True
    )
    author_run_id = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"],
        namespace="run",
        name=control["author_run_name"],
    )
    author_workspace = runtime.runs.backend.open(author_run_id)
    debug_files = tuple(
        (author_workspace.root / ".operation-tools/tcad").glob("*/profile")
    )
    evidence = {
        "author_state": author["state"],
        "review_state": review["state"],
        "author_agent_type": control["author_agent_type"],
        "review_agent_type": control["review_agent_type"],
        "debug_tool_succeeded": "worker_tcad_debug_run"
        in runtime.runs.successful_tools(author_run_id),
        "preflight_attached": (
            project.preflight_attestation is not None
            and project.preflight_attestation.qualified
        ),
        "debug_result_is_private": (
            len(debug_files) == 1
            and debug_files[0].is_file()
            and not (author_workspace.output_directory / "profile").exists()
        ),
        "review_is_exact_and_passing": runtime.runs.is_exact_reviewer_output(
            review_ref,
            reviewer_operation=REVIEW_OPERATION,
            reviewer_input_port="project",
            accepted_verdicts=("pass",),
            subject_ref=project_ref,
        ),
        "review_has_exact_subject_parent": project_ref
        in runtime.artifacts.get_by_id(review_ref.artifact_id).parent_refs,
        "task_service_absent": not hasattr(runtime, "tasks"),
        "launcher_receipts_verified": True,
        "distinct_launcher_invocations": True,
        "worker_transport": "independent_codex_exec",
    }
    (root / "final-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    if not all(
        evidence[key]
        for key in (
            "debug_tool_succeeded",
            "preflight_attached",
            "debug_result_is_private",
            "review_is_exact_and_passing",
            "review_has_exact_subject_parent",
            "task_service_absent",
        )
    ):
        raise SystemExit("L4 evidence is incomplete")
    print(json.dumps(evidence, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "queue-review", "status"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    {"prepare": prepare, "queue-review": queue_review, "status": status}[
        args.action
    ](root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
