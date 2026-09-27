#!/usr/bin/env python3
"""Run and verify the exact revision half of the persistent L4 TCAD probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
for candidate in (
    REPOSITORY,
    REPOSITORY / "src",
    REPOSITORY / "plugins/curve_score",
    REPOSITORY / "plugins/tcad_artifact",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts import l4_live_tcad_agent_probe as base  # noqa: E402
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration  # noqa: E402
from scidiscovery.operations.tooling import operation_agent_type  # noqa: E402
from scidiscovery.platforms.codex import initialize  # noqa: E402
from tcad_artifact.project_packager import (  # noqa: E402
    DeckProjectDraft,
    DeckReviewReport,
)


REVISION_OPERATION = "tcad.deck.author.revise.v1"
REVISION_RECEIPT = "tcad_revision_launcher_receipt"
REVISION_REVIEW_RECEIPT = "tcad_revision_reviewer_launcher_receipt"


def _is_qualified_debug_report(
    value: object, *, mode: str, source_tree_sha256: str
) -> bool:
    profile = {
        "preflight": "tcad.project-preflight.v1",
        "initialization": "tcad.project-initialization.v1",
    }.get(mode)
    return bool(
        profile
        and isinstance(value, dict)
        and value.get("schema_version") == 1
        and value.get("profile") == profile
        and value.get("mode") == mode
        and value.get("source_tree_sha256") == source_tree_sha256
        and value.get("terminal_state") == "succeeded"
        and value.get("exit_code") == 0
        and value.get("diagnostic_layer") == "complete"
        and value.get("qualified") is True
    )


def _qualified_debug_report(
    runtime, run_id: str, *, mode: str, source_tree_sha256: str
) -> bool:
    try:
        workspace = runtime.runs.backend.open(run_id)
        value = json.loads(
            (workspace.root / f"deck/reports/{mode}.json").read_text("utf-8")
        )
    except (AttributeError, json.JSONDecodeError, OSError, ValueError):
        return False
    return _is_qualified_debug_report(
        value, mode=mode, source_tree_sha256=source_tree_sha256
    )


def _artifact_ref(runtime, control: dict[str, object], name: str):
    return runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=str(control["instance_id"]),
            namespace="artifact",
            name=name,
        )
    ).ref


def _refresh_profiles(root: Path, runtime) -> None:
    initialize(
        root / "project",
        python_executable=Path(sys.executable),
        python_path=root / "pythonpath",
        control_socket=root / "unused-control.sock",
        state_root=root / "state",
        operation_catalog=runtime.runs.operation_catalog,
        runtime_plugin_configs={"tcad_artifact": root / "tcad-plugin.json"},
    )


def queue_revision(root: Path, device_grid: Path) -> None:
    control: dict[str, object] = base._control(root)
    runtime = base._runtime(root)
    router = base._root(runtime, str(control["instance_id"]))
    current = router.call_tool("instance_current", {})
    if current.get("state") != "active":
        raise SystemExit("TCAD probe instance is not active")

    author = router.call_tool("run_status", {"name": control["author_run_name"]})
    review = router.call_tool("run_status", {"name": control["review_run_name"]})
    if author["state"] != "completed" or review["state"] != "completed":
        raise SystemExit("initial TCAD author-review pair is incomplete")
    base._verify_operation_launch(
        root,
        control=control,
        run=review,
        operation_id=base.REVIEW_OPERATION,
        agent_type=str(control["review_agent_type"]),
        receipt_name=str(control["review_launcher_receipt"]),
        required_worker_tools={"worker_open_assignment", "worker_submit_result"},
    )
    prior_ref = _artifact_ref(runtime, control, str(control["project_name"]))
    change_name = str(review["output_artifact_name"])
    change_ref = _artifact_ref(runtime, control, change_name)
    if not runtime.runs.is_exact_reviewer_output(
        change_ref,
        reviewer_operation=base.REVIEW_OPERATION,
        reviewer_input_port="project",
        accepted_verdicts=("revise",),
        subject_ref=prior_ref,
    ):
        raise SystemExit("revision input is not the exact sealed review request")

    source = device_grid.expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise SystemExit("device grid must be one regular file")
    raw = source.read_bytes()
    if not raw or len(raw) > 64 * 1024 * 1024:
        raise SystemExit("device grid size is outside the compiled port limit")
    digest = hashlib.sha256(raw).hexdigest()
    grid = runtime.artifacts.register(
        raw,
        ArtifactRegistration(
            kind="tcad_solver_input",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="application/octet-stream",
            creator=runtime.actor,
        ),
        idempotency_key=f"m7-live:device-grid:{digest}",
    )
    runtime.scheduler_bindings.bind(
        instance=str(control["instance_id"]),
        namespace="artifact",
        name="device_grid",
        object_id=grid.artifact_id,
    )

    _refresh_profiles(root, runtime)
    request = {
        "name": "revision",
        "operation_id": REVISION_OPERATION,
        "inputs": [
            {"port": "prior_project", "artifact_names": [control["project_name"]]},
            {"port": "change_request", "artifact_names": [change_name]},
            {
                "port": "execution_capability",
                "artifact_names": ["execution_capability"],
            },
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
            {"port": "device_grid", "artifact_names": ["device_grid"]},
        ],
        "instruction": (
            "Apply only the exact independent change request: declare one "
            "device_grid input slot targeting device.tdr, reference that Grid in "
            "main.cmd, preserve the plan and capability, author and declare the "
            "smallest separate initialization entrypoint, then run qualified "
            "preflight and initialization against the same unchanged final "
            "source before submitting a complete revised project."
        ),
    }
    preflight = router.call_tool("operation_preflight", request)
    if preflight.get("admissible") is not True:
        raise SystemExit(f"revision preflight rejected: {preflight}")
    invoked = router.call_tool("operation_invoke", request)
    control.update(
        {
            "device_grid_artifact_name": "device_grid",
            "device_grid_sha256": digest,
            "revision_agent_type": invoked["result"]["agent_type"],
            "revision_launcher_receipt": REVISION_RECEIPT,
            "revision_run_name": "revision",
        }
    )
    base._write_control(root, control)
    base._write_dispatch(
        root,
        label="revision",
        operation_id=REVISION_OPERATION,
        python_path=root / "pythonpath",
        receipt_name=REVISION_RECEIPT,
        require_tcad_debug=True,
    )


def queue_review(root: Path) -> None:
    control: dict[str, object] = base._control(root)
    runtime = base._runtime(root)
    router = base._root(runtime, str(control["instance_id"]))
    revision = router.call_tool(
        "run_status", {"name": control["revision_run_name"]}
    )
    if revision["state"] != "completed":
        raise SystemExit(f"revision Run is not complete: {revision['state']}")
    base._verify_operation_launch(
        root,
        control=control,
        run=revision,
        operation_id=REVISION_OPERATION,
        agent_type=str(control["revision_agent_type"]),
        receipt_name=str(control["revision_launcher_receipt"]),
        required_worker_tools={
            "worker_open_assignment",
            "worker_tcad_debug_run",
            "worker_submit_result",
        },
    )
    run_id = runtime.scheduler_bindings.resolve(
        instance=str(control["instance_id"]),
        namespace="run",
        name=str(control["revision_run_name"]),
    )
    if "worker_tcad_debug_run" not in runtime.runs.successful_tools(run_id):
        raise SystemExit("revision has no successful TCAD debug activity")
    project_name = str(revision["output_artifact_name"])
    project_ref = _artifact_ref(runtime, control, project_name)
    project = DeckProjectDraft.model_validate_json(
        runtime.artifacts.read(project_ref), strict=True
    )
    if project.preflight_attestation is None or not project.preflight_attestation.qualified:
        raise SystemExit("revision output has no qualified preflight attestation")
    if not _qualified_debug_report(
        runtime,
        run_id,
        mode="initialization",
        source_tree_sha256=project.preflight_attestation.source_tree_sha256,
    ):
        raise SystemExit(
            "revision output has no source-bound qualified initialization report"
        )

    request = {
        "name": "revision_reviewer",
        "operation_id": base.REVIEW_OPERATION,
        "inputs": [
            {"port": "project", "artifact_names": [project_name]},
            {
                "port": "execution_capability",
                "artifact_names": ["execution_capability"],
            },
            {"port": "experiment_plan", "artifact_names": ["experiment_plan"]},
        ],
        "instruction": "Independently review the exact revised TCAD project.",
    }
    preflight = router.call_tool("operation_preflight", request)
    if preflight.get("admissible") is not True:
        raise SystemExit(f"revision review preflight rejected: {preflight}")
    invoked = router.call_tool("operation_invoke", request)
    control.update(
        {
            "revision_project_name": project_name,
            "revision_review_agent_type": invoked["result"]["agent_type"],
            "revision_review_launcher_receipt": REVISION_REVIEW_RECEIPT,
            "revision_review_run_name": "revision_reviewer",
        }
    )
    base._write_control(root, control)
    base._write_dispatch(
        root,
        label="revision-reviewer",
        operation_id=base.REVIEW_OPERATION,
        python_path=root / "pythonpath",
        receipt_name=REVISION_REVIEW_RECEIPT,
        require_tcad_debug=False,
    )


def status(root: Path) -> None:
    control: dict[str, object] = base._control(root)
    runtime = base._runtime(root)
    router = base._root(runtime, str(control["instance_id"]))
    names = {
        "author": control["author_run_name"],
        "initial_review": control["review_run_name"],
        "revision": control["revision_run_name"],
        "revision_review": control["revision_review_run_name"],
    }
    runs = {
        key: router.call_tool("run_status", {"name": name})
        for key, name in names.items()
    }
    if any(value["state"] != "completed" for value in runs.values()):
        raise SystemExit("TCAD revision probe has an incomplete Run")
    invocations = {
        base._verify_operation_launch(
            root,
            control=control,
            run=runs["author"],
            operation_id=base.AUTHOR_OPERATION,
            agent_type=str(control["author_agent_type"]),
            receipt_name=str(control["author_launcher_receipt"]),
            required_worker_tools={
                "worker_open_assignment",
                "worker_tcad_debug_run",
                "worker_submit_result",
            },
        ),
        base._verify_operation_launch(
            root,
            control=control,
            run=runs["initial_review"],
            operation_id=base.REVIEW_OPERATION,
            agent_type=str(control["review_agent_type"]),
            receipt_name=str(control["review_launcher_receipt"]),
            required_worker_tools={"worker_open_assignment", "worker_submit_result"},
        ),
        base._verify_operation_launch(
            root,
            control=control,
            run=runs["revision"],
            operation_id=REVISION_OPERATION,
            agent_type=str(control["revision_agent_type"]),
            receipt_name=str(control["revision_launcher_receipt"]),
            required_worker_tools={
                "worker_open_assignment",
                "worker_tcad_debug_run",
                "worker_submit_result",
            },
        ),
        base._verify_operation_launch(
            root,
            control=control,
            run=runs["revision_review"],
            operation_id=base.REVIEW_OPERATION,
            agent_type=str(control["revision_review_agent_type"]),
            receipt_name=str(control["revision_review_launcher_receipt"]),
            required_worker_tools={"worker_open_assignment", "worker_submit_result"},
        ),
    }
    old_project_ref = _artifact_ref(runtime, control, str(control["project_name"]))
    old_review_ref = _artifact_ref(
        runtime, control, str(runs["initial_review"]["output_artifact_name"])
    )
    revised_ref = _artifact_ref(
        runtime, control, str(control["revision_project_name"])
    )
    new_review_ref = _artifact_ref(
        runtime, control, str(runs["revision_review"]["output_artifact_name"])
    )
    revised = runtime.artifacts.get_by_id(revised_ref.artifact_id)
    grid_ref = _artifact_ref(
        runtime, control, str(control["device_grid_artifact_name"])
    )
    initial_is_revision_request = runtime.runs.is_exact_reviewer_output(
        old_review_ref,
        reviewer_operation=base.REVIEW_OPERATION,
        reviewer_input_port="project",
        accepted_verdicts=("revise",),
        subject_ref=old_project_ref,
    )
    old_review_not_inherited = not runtime.runs.is_exact_reviewer_output(
        old_review_ref,
        reviewer_operation=base.REVIEW_OPERATION,
        reviewer_input_port="project",
        accepted_verdicts=("pass",),
        subject_ref=revised_ref,
    )
    new_review_passing = runtime.runs.is_exact_reviewer_output(
        new_review_ref,
        reviewer_operation=base.REVIEW_OPERATION,
        reviewer_input_port="project",
        accepted_verdicts=("pass",),
        subject_ref=revised_ref,
    )
    revision_project = DeckProjectDraft.model_validate_json(
        runtime.artifacts.read(revised_ref), strict=True
    )
    review_value = DeckReviewReport.model_validate_json(
        runtime.artifacts.read(new_review_ref), strict=True
    )
    evidence = {
        "all_runs_completed": True,
        "distinct_launcher_invocations": len(invocations) == 4,
        "initial_review_is_exact_revision_request": initial_is_revision_request,
        "launcher_receipts_verified": True,
        "old_review_not_inherited": old_review_not_inherited,
        "revision_debug_tool_succeeded": "worker_tcad_debug_run"
        in runtime.runs.successful_tools(
            runtime.scheduler_bindings.resolve(
                instance=str(control["instance_id"]),
                namespace="run",
                name=str(control["revision_run_name"]),
            )
        ),
        "revision_has_exact_parents": {
            old_project_ref,
            old_review_ref,
            grid_ref,
        }.issubset(revised.parent_refs),
        "revision_preflight_qualified": bool(
            revision_project.preflight_attestation
            and revision_project.preflight_attestation.qualified
        ),
        "revision_initialization_qualified": bool(
            revision_project.preflight_attestation
            and _qualified_debug_report(
                runtime,
                runtime.scheduler_bindings.resolve(
                    instance=str(control["instance_id"]),
                    namespace="run",
                    name=str(control["revision_run_name"]),
                ),
                mode="initialization",
                source_tree_sha256=(
                    revision_project.preflight_attestation.source_tree_sha256
                ),
            )
        ),
        "revision_review_has_exact_subject_parent": revised_ref
        in runtime.artifacts.get_by_id(new_review_ref.artifact_id).parent_refs,
        "revision_review_is_exact_and_passing": new_review_passing,
        "revision_review_verdict": review_value.verdict,
        "worker_transport": "independent_codex_exec",
    }
    (root / "final-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    if not all(value is True for key, value in evidence.items() if key not in {
        "revision_review_verdict", "worker_transport"
    }) or review_value.verdict != "pass":
        raise SystemExit("TCAD revision evidence is incomplete")
    print(json.dumps(evidence, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("queue-revision", "queue-review", "status"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--device-grid", type=Path)
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    if args.action == "queue-revision":
        if args.device_grid is None:
            parser.error("queue-revision requires --device-grid")
        queue_revision(root, args.device_grid)
    elif args.action == "queue-review":
        queue_review(root)
    else:
        status(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
