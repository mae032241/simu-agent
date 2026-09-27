#!/usr/bin/env python3
"""Prepare and verify a persistent, directly Agent-driven L2 Run probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE_PLUGIN = REPOSITORY / "tests/fixtures/plugins/blind_csv_operation_plugin"
for candidate in (REPOSITORY / "src", FIXTURE_PLUGIN):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN  # noqa: E402
from scidiscovery.artifact_agent.interfaces.mcp_root import (  # noqa: E402
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime  # noqa: E402
from scidiscovery.artifact_agent.schema.artifact import (  # noqa: E402
    ArtifactRegistration,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN  # noqa: E402
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN  # noqa: E402
from scidiscovery.operations.catalog import compile_catalog  # noqa: E402
from scidiscovery.operations.tooling import (  # noqa: E402
    operation_agent_type,
    operation_worker_server_name,
)
from scidiscovery.platforms.codex import initialize  # noqa: E402


RAW = b"sample,value\na,1\nb,3\n"
OPERATION_ID = "blind.csv.observe.v1"


def _catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN))


def _runtime(root: Path):
    runtime = open_runtime(
        project_root=root / "project",
        state_root=root / "state",
        worker_backend="local",
    )
    assert runtime.runs is not None
    runtime.runs.operation_catalog = _catalog()
    return runtime


def _control(root: Path) -> dict[str, str]:
    return json.loads((root / "control.json").read_text("utf-8"))


def _standalone_python_path(root: Path) -> Path:
    """Create a non-temporary import root usable by the generated profile."""

    target = root / "pythonpath"
    target.mkdir()
    os.symlink(
        REPOSITORY / "src/scidiscovery",
        target / "scidiscovery",
        target_is_directory=True,
    )
    os.symlink(
        FIXTURE_PLUGIN / "blind_csv_plugin",
        target / "blind_csv_plugin",
        target_is_directory=True,
    )
    metadata = target / "scidiscovery_l2_probe-0.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: scidiscovery-l2-probe\nVersion: 0.0\n",
        "utf-8",
    )
    (metadata / "entry_points.txt").write_text(
        "[scidiscovery.plugins]\n"
        "builtin = scidiscovery.builtin_plugin:CORE_PLUGIN\n"
        "general_science = scidiscovery.general_science_plugin:PLUGIN\n"
        "blind_csv = blind_csv_plugin.plugin:PLUGIN\n",
        "utf-8",
    )
    return target


def prepare(root: Path) -> None:
    if root.exists():
        raise SystemExit(f"refusing to overwrite existing probe: {root}")
    (root / "project").mkdir(parents=True)
    (root / "project/AGENTS.md").write_text("# L2 direct Agent probe\n", "utf-8")
    python_path = _standalone_python_path(root)
    runtime = _runtime(root)
    catalog = runtime.runs.operation_catalog
    compiled = catalog.operation(OPERATION_ID)
    instance = runtime.scheduler_bindings.create_instance(
        name="l2_direct_agent_probe",
        title="L2 direct Agent probe",
        objective="Verify that a real spawned Agent directly drives the exact Worker MCP.",
    )
    source = runtime.artifacts.register(
        RAW,
        ArtifactRegistration(
            kind="blind_csv_input",
            schema_id="blind.opaque.v1",
            payload_schema_version=1,
            media_type="text/csv",
            creator=runtime.actor,
        ),
        idempotency_key="l2:direct-agent:source",
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
            "name": "direct_observation",
            "operation_id": OPERATION_ID,
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]}
            ],
            "instruction": "Make one bounded observation from the exact CSV.",
        },
    )
    agent_type = operation_agent_type(compiled)
    initialize(
        root / "project",
        python_executable=Path(sys.executable),
        python_path=python_path,
        control_socket=root / "unused-control.sock",
        state_root=root / "state",
        operation_catalog=catalog,
    )
    profile = root / "project/.codex/agents" / f"{agent_type}.toml"
    control = {
        "instance_id": instance.instance_id,
        "operation_digest": compiled.digest,
        "run_name": "direct_observation",
        "agent_type": agent_type,
        "worker_server": operation_worker_server_name(compiled),
    }
    (root / "control.json").write_text(
        json.dumps(control, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    (root / "agent-dispatch.json").write_text(
        json.dumps(
            {
                "generated_profile": str(profile),
                "expected_agent_type": agent_type,
                "environment": {
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(python_path),
                },
                "mcp_command": [
                    sys.executable,
                    "-m",
                    "scidiscovery.artifact_agent.interfaces.mcp_local_worker",
                    "--state-root",
                    str(root / "state"),
                    "--operation-id",
                    OPERATION_ID,
                    "--operation-digest",
                    compiled.digest,
                ],
                "required_direct_calls": [
                    "worker_open_assignment",
                    "worker_csv_summarize",
                    "worker_submit_result",
                ],
                "instruction": (
                    "Start this exact stdio MCP yourself. Send JSON-RPC calls directly; "
                    "do not use a bridge. After open, read only the returned workspace, "
                    "assignment, exact input and Schema. Call the registered CSV tool "
                    "yourself, write output/result.json with native file tools, then "
                    "call submit yourself. Do not relay scientific content through chat."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )
    (root / "prepare-result.json").write_text(
        json.dumps(
            {"state": invoked["result"]["state"], "generated_profile": str(profile)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "utf-8",
    )


def status(root: Path) -> None:
    control = _control(root)
    runtime = _runtime(root)
    run_id = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"], namespace="run", name=control["run_name"]
    )
    value = runtime.runs.status(run_id)
    if value.state != "completed" or value.output_ref is None:
        raise SystemExit(f"probe Run is not complete: {value.state}")
    artifact = runtime.artifacts.get_by_id(value.output_ref.artifact_id)
    runtime.artifacts.verify(artifact.ref)
    bound_output = runtime.scheduler_bindings.resolve(
        instance=control["instance_id"],
        namespace="artifact",
        name=value.output_binding_name,
    )
    evidence = {
        "state": value.state,
        "operation_id": value.operation_id,
        "backend": value.backend_id,
        "candidate_bound": value.accepted_candidate_digest is not None,
        "completion_receipt": value.completion_receipt is not None,
        "registered_tool_succeeded": "worker_csv_summarize"
        in runtime.runs.successful_tools(run_id),
        "artifact_verified": True,
        "artifact_parent_count": len(artifact.parent_refs),
        "output_bound_before_status": bound_output == artifact.artifact_id,
        "generated_agent_type": control["agent_type"],
        "generated_worker_server": control["worker_server"],
        "bridge_used": False,
    }
    (root / "final-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    print(json.dumps(evidence, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "status"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    prepare(root) if args.action == "prepare" else status(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
