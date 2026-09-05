from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog


OPERATION_ID = "science.evidence.audit.v1"
UNAFFECTED_OPERATION_ID = "science.object.review.v1"


def _status_payload(status) -> dict[str, object]:
    return json.loads(
        json.dumps(
            asdict(status),
            default=lambda value: value.model_dump(mode="json"),
        )
    )


def _catalog():
    audit = next(
        item for item in GENERAL_PLUGIN.operations if item.operation_id == OPERATION_ID
    )
    assert audit.limits is not None
    recoverable_audit = audit.model_copy(
        update={"limits": audit.limits.model_copy(update={"max_attempts": 2})}
    )
    plugin = GENERAL_PLUGIN.model_copy(
        update={
            "operations": tuple(
                recoverable_audit if item.operation_id == OPERATION_ID else item
                for item in GENERAL_PLUGIN.operations
            )
        }
    )
    return compile_catalog((CORE_PLUGIN, plugin))


def _root(runtime, instance_id: str, catalog) -> RootMCPRouter:
    return RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance_id,
            operation_catalog=catalog,
        )
    )


def _invoke(root: RootMCPRouter, name: str, *, resume_from: str | None = None):
    request = {
        "name": name,
        "operation_id": OPERATION_ID,
        "inputs": [
            {"port": "scientific_foundation", "artifact_names": ["foundation"]},
            {"port": "source_material", "artifact_names": ["source"]},
        ],
        "instruction": "Audit only the exact bound source.",
    }
    if resume_from is not None:
        request["resume_from"] = resume_from
    return root.call_tool("operation_invoke", request)


def _result() -> bytes:
    return canonical_json(
        {
            "schema_version": 1,
            "handoff": {
                "verdict": "pass",
                "summary": "The bounded statement is faithful to the exact source.",
            },
            "payload": {
                "schema_version": 1,
                "checks": [
                    {
                        "check_key": "source_fidelity",
                        "subject": "The statement is bounded to the supplied line.",
                        "status": "pass",
                        "basis": "The exact frozen line is available.",
                        "evidence_keys": ["source_material"],
                    }
                ],
                "evidence": [
                    {
                        "source_key": "source_material",
                        "source_type": "frozen_input",
                        "locator": "source_material:line-1",
                    }
                ],
            },
        }
    )


def _open(paths: argparse.Namespace, catalog):
    project = paths.case_root / "project"
    project.mkdir(parents=True, exist_ok=True)
    agents = project / "AGENTS.md"
    if not agents.exists():
        agents.write_text("# Installed generation probe\n", encoding="utf-8")
    runtime = open_runtime(
        project_root=project,
        state_root=paths.case_root / "state",
        worker_backend="local",
        local_workspace_root=project / ".scidiscovery-runs",
    )
    runtime.runs.operation_catalog = catalog
    return runtime


def prepare(paths: argparse.Namespace) -> None:
    catalog = _catalog()
    runtime = _open(paths, catalog)
    instance = runtime.scheduler_bindings.create_instance(
        name=f"installed_generation_{paths.mode}",
        title="Installed generation probe",
        objective="Keep old and new installed Operation generations separate.",
    )
    foundation = canonical_json(
        {
            "title": "Bounded foundation",
            "objective": "Audit one bounded premise.",
            "summary": "The premise is explicitly marked as an assumption.",
            "items": [
                {
                    "item_key": "premise",
                    "item_type": "assumption",
                    "epistemic_status": "assumption",
                    "statement": "The supplied line is the bounded context.",
                    "scope": "Installed generation probe only.",
                    "rationale": "The audit remains tied to one frozen input.",
                }
            ],
        }
    )
    for name, content, kind, schema_id, media_type in (
        (
            "foundation",
            foundation,
            "scientific_foundation",
            "scidiscovery.scientific-foundation.v1",
            "application/json",
        ),
        ("source", b"bounded source\n", "paper_source", "opaque", "text/plain"),
    ):
        artifact = runtime.artifacts.register(
            content,
            ArtifactRegistration(
                kind=kind,
                schema_id=schema_id,
                payload_schema_version=1,
                media_type=media_type,
                creator=runtime.actor,
            ),
            idempotency_key=f"installed-generation:{paths.mode}:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=artifact.artifact_id,
        )

    root = _root(runtime, instance.instance_id, catalog)
    name = f"old_{paths.mode}"
    assert _invoke(root, name)["result"]["state"] == "queued"
    compiled = catalog.operation(OPERATION_ID)
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=OPERATION_ID,
        operation_digest=compiled.digest,
    )
    if paths.mode != "queued":
        opened = worker.call_tool("worker_open_assignment", {})
        Path(opened["output_directory"], "result.json").write_bytes(_result())
        if paths.mode == "failed":
            status = root.call_tool("run_status", {"name": name})
            failed = root.call_tool(
                "run_record_failure",
                {
                    "name": name,
                    "reason": "Create one exact recovery draft.",
                    "expected_state": "running",
                    "expected_last_activity_at": status["last_activity_at"],
                },
            )
            assert failed["state"] == "failed"
            assert failed["recovery_available"] is True
        elif paths.mode == "completed":
            assert worker.call_tool("worker_submit_result", {})["state"] == "completed"

    run_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="run", name=name
    )
    if paths.mode == "expired":
        with sqlite3.connect(runtime.runs.database_path) as connection:
            connection.execute(
                "UPDATE runs SET deadline_at = ? WHERE run_id = ?",
                ("2000-01-01T00:00:00.000000Z", run_id),
            )
    status = runtime.runs.status(run_id)
    paths.record.write_text(
        json.dumps(
            {
                "artifact_count": len(runtime.artifacts.list_artifacts(limit=1000)),
                "instance_id": instance.instance_id,
                "mode": paths.mode,
                "old_digest": compiled.digest,
                "run_id": run_id,
                "run_status": _status_payload(status),
                "unaffected_digest": catalog.operation(
                    UNAFFECTED_OPERATION_ID
                ).digest,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"phase": "prepare", "mode": paths.mode, "state": status.state}))


def verify(paths: argparse.Namespace) -> None:
    record = json.loads(paths.record.read_text(encoding="utf-8"))
    catalog = _catalog()
    runtime = _open(paths, catalog)
    instance = runtime.scheduler_bindings.get_instance(
        instance_id=record["instance_id"]
    )
    root = _root(runtime, instance.instance_id, catalog)
    name = f"old_{paths.mode}"
    compiled = catalog.operation(OPERATION_ID)
    assert compiled.digest != record["old_digest"]
    assert (
        catalog.operation(UNAFFECTED_OPERATION_ID).digest
        == record["unaffected_digest"]
    )
    before = runtime.runs.status(record["run_id"])
    assert _status_payload(before) == record["run_status"]
    artifact_count = len(runtime.artifacts.list_artifacts(limit=1000))

    current_worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=OPERATION_ID,
        operation_digest=compiled.digest,
    )
    if paths.mode in {"queued", "running", "expired"}:
        try:
            current_worker.call_tool("worker_open_assignment", {})
        except Exception as error:
            assert "no exact queued Run" in str(error)
        else:
            raise AssertionError("the new Worker claimed an old-generation Run")
        try:
            LocalWorkerMCPRouter(
                runtime.runs,
                operation_id=OPERATION_ID,
                operation_digest=record["old_digest"],
            )
        except ValueError as error:
            assert "operation identity is invalid" in str(error)
        else:
            raise AssertionError("the new install accepted an old Worker identity")
        expected = {
            "queued": "Run is not running: queued",
            "running": "Run operation contract changed",
            "expired": "Run deadline expired",
        }[paths.mode]
        try:
            runtime.runs.submit(record["run_id"])
        except Exception as error:
            assert expected in str(error)
        else:
            raise AssertionError("the new install submitted an old active Run")
        status = root.call_tool("run_status", {"name": name})
        try:
            root.call_tool(
                "run_record_failure",
                {
                    "name": name,
                    "reason": "A new contract cannot close an old active Run.",
                    "expected_state": (
                        "queued" if paths.mode == "queued" else "running"
                    ),
                    "expected_last_activity_at": status["last_activity_at"],
                    "timed_out": paths.mode == "expired",
                },
            )
        except Exception as error:
            assert "Run operation contract changed" in str(error)
        else:
            raise AssertionError("the new install mutated an old active Run")
    elif paths.mode == "failed":
        retired = root.call_tool("run_status", {"name": name})
        assert retired["recovery_available"] is False
        before_runs = root.call_tool("run_list", {})
        rejected = root.call_tool(
            "operation_preflight",
            {
                "name": "retired_resume",
                "operation_id": OPERATION_ID,
                "inputs": [
                    {
                        "port": "scientific_foundation",
                        "artifact_names": ["foundation"],
                    },
                    {"port": "source_material", "artifact_names": ["source"]},
                ],
                "instruction": "Do not resume across a contract generation.",
                "resume_from": name,
            },
        )
        assert rejected["admissible"] is False
        assert rejected["reason_code"] == "recovery_source_unavailable"
        assert root.call_tool("run_list", {}) == before_runs
    else:
        retired = root.call_tool("run_status", {"name": name})
        assert retired["sealed_output_status"] == "contract_retired"
        assert retired["sealed_output"] is None
        assert retired["scheduler_signal"] is None
        assert runtime.runs.submit(record["run_id"]) == ("completed", ())

    assert runtime.runs.status(record["run_id"]) == before
    assert len(runtime.artifacts.list_artifacts(limit=1000)) == artifact_count
    assert _invoke(root, f"new_after_{paths.mode}")["result"]["state"] == "queued"
    print(
        json.dumps(
            {
                "phase": "verify",
                "mode": paths.mode,
                "old_digest": record["old_digest"],
                "new_digest": compiled.digest,
                "unchanged_digest": record["unaffected_digest"],
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "verify"))
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("queued", "running", "expired", "failed", "completed"),
        required=True,
    )
    paths = parser.parse_args()
    if paths.phase == "prepare":
        prepare(paths)
    else:
        verify(paths)


if __name__ == "__main__":
    main()
