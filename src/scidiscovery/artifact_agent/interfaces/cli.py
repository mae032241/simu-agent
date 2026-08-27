"""Administrative CLI for the current SciDiscovery control plane."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

from ..approval_ui import ApprovalUI
from ..portable_bundle import (
    export_active_research_bundle,
    import_active_research_bundle,
    load_active_bundle_selection,
    verify_active_research_bundle,
)
from .mcp_root import RootToolFacade
from ..runtime import open_runtime, read_secret_file
from ..schema.approval import LocalIdentityRef
from ..schema.common import canonical_json
from ..service import (
    CONFIRM_ORPHAN_CLEANUP,
    InstanceAdministrationService,
    OrphanAdministrationService,
    StateMaintenanceLock,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scid")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--state-root", type=Path, default=Path(".scidiscovery-state")
    )
    parser.add_argument("--task-secret-file", type=Path)
    parser.add_argument("--approval-secret-file", type=Path)
    parser.add_argument("--shared-group", action="store_true")
    parser.add_argument("--instance")
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init")
    initialize.add_argument("platform", choices=("codex",))
    initialize.add_argument("--python", type=Path, default=Path(sys.executable))
    initialize.add_argument("--control-socket", type=Path, required=True)
    initialize.add_argument("--worker-socket", type=Path, required=True)
    initialize.add_argument("--dry-run", action="store_true")

    ingest = commands.add_parser("ingest-file")
    ingest.add_argument("name")
    ingest.add_argument("relative_path")
    ingest.add_argument("--media-type")
    ingest.add_argument(
        "--on-conflict", choices=("reject", "create_revision"), default="reject"
    )

    catalog = commands.add_parser("artifact-catalog")
    catalog.add_argument("name")

    approval_status = commands.add_parser("approval-status")
    approval_status.add_argument("name")

    instance_create = commands.add_parser("instance-create")
    instance_create.add_argument("name")
    instance_create.add_argument("--title", required=True)
    instance_create.add_argument("--objective", required=True)

    instance_list = commands.add_parser("instance-list")
    instance_list.add_argument("--state", choices=("active", "closed"))

    instance_close = commands.add_parser("instance-close")
    instance_close.add_argument("name")

    bundle_export = commands.add_parser("active-bundle-export")
    bundle_export.add_argument("selection", type=Path)
    bundle_export.add_argument("output", type=Path)

    bundle_verify = commands.add_parser("active-bundle-verify")
    bundle_verify.add_argument("bundle", type=Path)

    bundle_import = commands.add_parser("active-bundle-import")
    bundle_import.add_argument("bundle", type=Path)

    orphan_cleanup = commands.add_parser("state-orphans-cleanup")
    orphan_cleanup.add_argument("--confirm")

    serve_ui = commands.add_parser("serve-approval-ui")
    serve_ui.add_argument("--host", default="127.0.0.1")
    serve_ui.add_argument("--port", type=int, default=0)
    serve_ui.add_argument("--identity-id", default="local_user")
    serve_ui.add_argument("--display-name", default="Local user")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = _run(args)
    except Exception as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}), file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


def _run(args: argparse.Namespace) -> Any:
    state = args.state_root.expanduser().absolute()
    if args.command == "init":
        from scidiscovery.platforms import initialize_platform

        report = initialize_platform(
            args.platform,
            args.project_root,
            python_executable=args.python,
            control_socket=args.control_socket,
            worker_socket=args.worker_socket,
            worker_workspace_root=state / "workspaces",
            dry_run=args.dry_run,
        )
        return {
            "status": "preview" if args.dry_run else "initialized",
            "changed": [str(path) for path in report.changed],
            "unchanged": [str(path) for path in report.unchanged],
        }
    if args.command == "active-bundle-export":
        maintenance = StateMaintenanceLock(
            state / "maintenance.lock", shared_group=args.shared_group
        )
        with maintenance.shared():
            return export_active_research_bundle(
                state_root=state,
                selection=load_active_bundle_selection(args.selection),
                output=args.output,
            )
    if args.command == "active-bundle-verify":
        manifest = verify_active_research_bundle(args.bundle)
        return {
            "bundle_name": manifest.bundle_name,
            "bundle_sha256": manifest.content_hash,
            "entries": len(manifest.entries),
            "bound_artifacts": sum(
                len(entry.semantic_names) for entry in manifest.entries
            ),
            "status": "verified",
        }

    runtime = open_runtime(
        project_root=args.project_root,
        state_root=state,
        task_token_secret=read_secret_file(
            args.task_secret_file or state / "secrets" / "task-token.key",
            label="task token",
        ),
        approval_receipt_secret=read_secret_file(
            args.approval_secret_file or state / "secrets" / "approval-receipt.key",
            label="approval receipt",
        ),
        actor_id="admin_cli",
        shared_group=args.shared_group,
    )
    if args.command == "instance-create":
        with runtime.maintenance.shared():
            return _instance_value(
                runtime.scheduler_bindings.create_instance(
                    name=args.name, title=args.title, objective=args.objective
                )
            )
    if args.command == "instance-list":
        with runtime.maintenance.shared():
            return {
                "instances": [
                    _instance_value(value)
                    for value in runtime.scheduler_bindings.list_instances(
                        state=args.state
                    )
                ]
            }
    if args.command == "instance-close":
        with runtime.maintenance.shared():
            instance = runtime.scheduler_bindings.select_instance(name=args.name)
            return RootToolFacade(
                runtime.artifacts,
                runtime.intake,
                tasks=runtime.tasks,
                approvals=runtime.approvals,
                executions=runtime.executions,
                bindings=runtime.scheduler_bindings,
                instance=instance.instance_id,
            ).instance_close()
    if args.command == "active-bundle-import":
        if args.instance is None:
            raise ValueError("--instance is required for active bundle import")
        with runtime.maintenance.shared():
            return import_active_research_bundle(
                runtime=runtime,
                instance_name=args.instance,
                bundle_path=args.bundle,
            )
    if args.command == "state-orphans-cleanup":
        assert runtime.approvals is not None
        assert runtime.executions is not None
        admin = _orphan_admin(runtime)
        if args.confirm is None:
            with runtime.maintenance.shared():
                return _orphan_plan_value(admin.plan())
        with runtime.maintenance.exclusive():
            receipt = admin.delete(confirmation=args.confirm)
        return {
            "status": "deleted",
            "confirmation": CONFIRM_ORPHAN_CLEANUP,
            "deleted": {
                "tasks": receipt.deleted_tasks,
                "approvals": receipt.deleted_approvals,
                "executions": receipt.deleted_executions,
                "artifact_registrations": receipt.deleted_artifact_registrations,
                "runtime_workspaces": receipt.deleted_workspaces,
                "execution_exchange_directories": receipt.deleted_exchange_directories,
                "executor_result_directories": receipt.deleted_executor_runs,
                "submission_markers": receipt.deleted_submission_markers,
            },
            "verification": {
                "database_integrity_ok": receipt.database_integrity_ok,
                "artifact_integrity_ok": receipt.artifact_integrity_ok,
                "remaining_cas_orphans": receipt.remaining_cas_orphans,
            },
        }
    if args.command in {"ingest-file", "artifact-catalog", "approval-status"}:
        if args.instance is None:
            raise ValueError("--instance is required for instance-scoped commands")
        with runtime.maintenance.shared():
            instance = runtime.scheduler_bindings.select_instance(name=args.instance)
            facade = RootToolFacade(
                runtime.artifacts,
                runtime.intake,
                tasks=runtime.tasks,
                approvals=runtime.approvals,
                executions=runtime.executions,
                bindings=runtime.scheduler_bindings,
                instance=instance.instance_id,
            )
            if args.command == "ingest-file":
                return facade.artifact_ingest_file(
                    name=args.name,
                    relative_path=args.relative_path,
                    media_type=args.media_type,
                    on_conflict=args.on_conflict,
                )
            if args.command == "artifact-catalog":
                return facade.artifact_catalog(name=args.name)
            return facade.approval_status(name=args.name)
    if args.command == "serve-approval-ui":
        assert runtime.approvals is not None
        ui = ApprovalUI(
            runtime.approvals,
            host=args.host,
            port=args.port,
            bindings=runtime.scheduler_bindings,
            instance_admin=InstanceAdministrationService(
                artifacts=runtime.artifacts,
                approvals=runtime.approvals,
                bindings=runtime.scheduler_bindings,
                tasks=runtime.tasks,
                executions=runtime.executions,
            ),
            orphan_admin=_orphan_admin(runtime),
            maintenance=runtime.maintenance,
            local_identity=LocalIdentityRef(
                identity_id=args.identity_id,
                display_name=args.display_name,
            ),
        )
        url = ui.start()
        print(canonical_json({"approval_ui": url}).decode("utf-8"), flush=True)
        stopped = threading.Event()
        previous = signal.signal(signal.SIGTERM, lambda *_: stopped.set())
        try:
            stopped.wait()
        except KeyboardInterrupt:
            pass
        finally:
            signal.signal(signal.SIGTERM, previous)
            ui.stop()
        return {"approval_ui": "stopped"}
    raise AssertionError(f"unhandled command: {args.command}")


def _instance_value(value: Any) -> dict[str, Any]:
    return {
        "name": value.name,
        "title": value.title,
        "objective": value.objective,
        "state": value.state,
        "created_at": value.created_at,
        "closed_at": value.closed_at,
    }


def _orphan_admin(runtime: Any) -> OrphanAdministrationService:
    return OrphanAdministrationService(
        artifacts=runtime.artifacts,
        approvals=runtime.approvals,
        bindings=runtime.scheduler_bindings,
        tasks=runtime.tasks,
        executions=runtime.executions,
        executor_result_root=runtime.state_root / "executor-results",
    )


def _orphan_plan_value(value: Any) -> dict[str, Any]:
    return {
        "status": "preview",
        "confirmation_required": CONFIRM_ORPHAN_CLEANUP,
        "delete": {
            "tasks": len(value.orphan_task_ids),
            "approvals": len(value.orphan_approval_ids),
            "executions": len(value.orphan_execution_ids),
            "artifact_registrations": len(value.artifact_refs),
            "runtime_workspaces": len(value.stale_workspace_names),
            "execution_exchange_directories": len(value.stale_exchange_names),
            "executor_result_directories": len(value.stale_executor_run_names),
            "submission_markers": len(value.stale_submission_names),
        },
        "blockers": list(value.blockers),
        "preserves": [
            "research instances and instance-bound control objects",
            "project workspace",
            "database files and runtime lock files",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
