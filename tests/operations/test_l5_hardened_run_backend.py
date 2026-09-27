from __future__ import annotations

import json
import hashlib
import importlib.metadata
import os
import sqlite3
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path

import pytest

from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
from blind_csv_plugin.plugin import HARDENED_PLUGIN, PLUGIN as BLIND_CSV_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import (
    HardenedWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.hardened_workspace import (
    HardenedWorkerBackend,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import ComponentRef
from scidiscovery.operations.tooling import (
    operation_agent_type,
    operation_worker_server_name,
)
from scidiscovery.platforms.codex import initialize, validate_installation_profile


RAW = b"sample,value\na,1\nb,3\n"


def _system(
    tmp_path: Path,
    *,
    with_text_patch: bool = False,
    with_json_patch: bool = False,
    blind_plugin=BLIND_CSV_PLUGIN,
    worker_backend="hardened",
):
    if worker_backend == "hardened":
        # This transport fixture needs an available review edge, even though it
        # exercises only the author Run. The shared review fixture requires a
        # local native shell unless narrowed for this backend.
        if blind_plugin is BLIND_CSV_PLUGIN:
            blind_plugin = HARDENED_PLUGIN
        else:
            operations = []
            for operation in blind_plugin.operations:
                if operation.operation_id == "blind.csv.review.v1":
                    native = operation.executor.native_tools.model_copy(update={"shell": "none"})
                    operation = operation.model_copy(update={"executor":
                        operation.executor.model_copy(update={"native_tools": native})})
                operations.append(operation)
            blind_plugin = blind_plugin.model_copy(update={"operations": tuple(operations)})
    if with_text_patch or with_json_patch:
        author = blind_plugin.operations[0]
        patch_tools = tuple(
            ComponentRef(name, plugin_id="builtin")
            for name, enabled in (
                ("file_apply_patch_tool", with_text_patch),
                ("file_json_patch_tool", with_json_patch),
            )
            if enabled
        )
        executor = author.executor.model_copy(
            update={
                "tools": (
                    *author.executor.tools,
                    *patch_tools,
                )
            }
        )
        blind_plugin = blind_plugin.model_copy(
            update={
                "operations": (
                    author.model_copy(update={"executor": executor}),
                    *blind_plugin.operations[1:],
                )
            }
        )
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, blind_plugin))
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend=worker_backend,
    )
    assert runtime.runs is not None
    if worker_backend == "hardened":
        assert runtime.hardened_backend is not None
    assert not hasattr(runtime, "tasks") and not hasattr(runtime, "tokens")
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="l5_hardened",
        title="L5 hardened Run",
        objective="Prove the optional transport consumes the same Run authority.",
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
        idempotency_key="l5:hardened:source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="source_csv",
        object_id=source.artifact_id,
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
    return catalog, runtime, instance, root


def _invoke(root: RootMCPRouter, name: str = "observation") -> None:
    value = root.call_tool(
        "operation_invoke",
        {
            "name": name,
            "operation_id": "blind.csv.observe.v1",
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]}
            ],
            "instruction": "Make one bounded observation from the exact CSV.",
        },
    )
    assert value["result"]["state"] == "queued"


def _worker(catalog, runtime) -> HardenedWorkerMCPRouter:
    compiled = catalog.operation("blind.csv.observe.v1")
    return HardenedWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )


def _write_result(worker: HardenedWorkerMCPRouter) -> None:
    structure = worker.call_tool("worker_csv_summarize", {})
    content = canonical_json(
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
    worker.call_tool("worker_file_write_chunk", {"content": content})
    worker.call_tool("worker_file_write_commit", {})


def test_hardened_transport_completes_the_same_run_without_task_science(
    tmp_path: Path,
) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    assert opened["write_protocol"] == "server_file_tools"
    assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
    assignment_tools = tuple(sorted(assignment["tools"]))
    router_tools = tuple(sorted(item["name"] for item in worker.list_tools()))
    assert assignment_tools == router_tools

    profile_root = tmp_path / "profile"
    profile_root.mkdir()
    initialize(
        profile_root,
        python_executable=Path(sys.executable),
        python_path=Path(__file__).resolve().parents[2] / "src",
        control_socket=tmp_path / "control.sock",
        state_root=runtime.state_root,
        worker_backend="hardened",
        operation_catalog=catalog,
    )
    compiled = catalog.operation("blind.csv.observe.v1")
    profile = tomllib.loads(
        profile_root.joinpath(
            ".codex/agents", f"{operation_agent_type(compiled)}.toml"
        ).read_text("utf-8")
    )
    assert not profile.get("mcp_servers")
    assert "scid_call" in profile["developer_instructions"]
    assert {
        "worker_file_write_begin",
        "worker_file_write_chunk",
        "worker_file_write_commit",
    }.issubset(assignment_tools)
    _write_result(worker)
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    status = root.call_tool("run_status", {'name': "observation", "intent": 'full'})
    assert "backend" not in status
    assert runtime.runs.status(worker._run_id).backend_id == "hardened_worker"
    assert status["state"] == "completed"
    with pytest.raises(ValueError, match="namespace is invalid"):
        runtime.scheduler_bindings.list(
            instance=instance.instance_id, namespace="task"
        )

    with sqlite3.connect(runtime.runs.database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(runs)")
        }
    assert not columns & {
        "qualification",
        "cohort",
        "approval_id",
        "execution_id",
        "session_id",
        "token",
        "attempt",
        "lease_deadline_at",
        "finalization_deadline_at",
    }


def test_hardened_rejects_missing_server_file_creation_before_run(
    tmp_path: Path,
) -> None:
    author = BLIND_CSV_PLUGIN.operations[0]
    executor = author.executor.model_copy(
        update={
            "tools": tuple(
                item
                for item in author.executor.tools
                if item.component_id != "file_write_commit_tool"
            )
        }
    )
    plugin = BLIND_CSV_PLUGIN.model_copy(
        update={
            "operations": (
                author.model_copy(update={"executor": executor}),
                *BLIND_CSV_PLUGIN.operations[1:],
            )
        }
    )
    catalog, runtime, instance, root = _system(tmp_path, blind_plugin=plugin)
    compiled = catalog.operation("blind.csv.observe.v1")
    assert HardenedWorkerBackend.unsupported_requirements(compiled) == (
        "server_file_create",
    )
    result = root.call_tool(
        "operation_preflight",
        {
            "name": "missing_file_tool",
            "operation_id": compiled.spec.operation_id,
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]}
            ],
            "instruction": "This must fail before Run creation.",
        },
    )
    assert result["admissible"] is False
    assert result["reason_code"] == "runtime_backend_capability_missing"
    assert runtime.runs.list(instance_id=instance.instance_id) == ()


def test_hardened_transport_rejects_concurrent_owner_and_recovers_after_lease(
    tmp_path: Path,
) -> None:
    catalog, runtime, _, root = _system(tmp_path)
    _invoke(root)
    first = _worker(catalog, runtime)
    first.call_tool("worker_open_assignment", {})
    second = _worker(catalog, runtime)
    with pytest.raises(Exception, match="already active"):
        second.call_tool("worker_open_assignment", {})

    run_id = first._run_id
    assert run_id is not None
    with sqlite3.connect(runtime.hardened_backend.dispatch_database) as connection:
        connection.execute(
            "UPDATE active_transport SET lease_deadline_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00+00:00", run_id),
        )
    restarted = _worker(catalog, runtime)
    assert restarted.call_tool("worker_open_assignment", {})["state"] == "opened"
    with pytest.raises(Exception, match="control diagnostic"):
        first.call_tool("worker_csv_summarize", {})
    with pytest.raises(Exception, match="control diagnostic"):
        first.call_tool(
            "worker_file_write_begin",
            {"relative_path": "output/result.json", "operation": "create"},
        )
    with pytest.raises(Exception, match="control diagnostic"):
        first.call_tool("worker_submit_result", {})
    _write_result(restarted)
    assert restarted.call_tool("worker_submit_result", {})["state"] == "completed"


def test_hardened_transport_fences_per_run_without_global_tool_serialization(
    tmp_path: Path,
) -> None:
    backend = HardenedWorkerBackend(tmp_path / "hardened", lease_seconds=10)
    backend.claim_transport("run_a", "owner_a")
    backend.claim_transport("run_b", "owner_b")
    entered = threading.Event()
    release = threading.Event()

    def hold_first_run() -> None:
        with backend.transport_guard("run_a", "owner_a"):
            entered.set()
            assert release.wait(3)

    thread = threading.Thread(target=hold_first_run)
    thread.start()
    assert entered.wait(1)
    started = time.monotonic()
    with backend.transport_guard("run_b", "owner_b"):
        pass
    elapsed = time.monotonic() - started
    release.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert elapsed < 0.25


def test_hardened_takeover_waits_for_same_run_inflight_call(tmp_path: Path) -> None:
    backend = HardenedWorkerBackend(tmp_path / "hardened", lease_seconds=10)
    backend.claim_transport("run_a", "owner_a")
    entered = threading.Event()
    release = threading.Event()
    takeover_done = threading.Event()

    def hold_call() -> None:
        with backend.transport_guard("run_a", "owner_a"):
            entered.set()
            assert release.wait(3)

    def takeover() -> None:
        backend.claim_transport("run_a", "owner_b")
        takeover_done.set()

    active = threading.Thread(target=hold_call)
    active.start()
    assert entered.wait(1)
    with sqlite3.connect(backend.dispatch_database) as connection:
        connection.execute(
            "UPDATE active_transport SET lease_deadline_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00+00:00", "run_a"),
        )
    replacement = threading.Thread(target=takeover)
    replacement.start()
    assert not takeover_done.wait(0.15)
    release.set()
    assert takeover_done.wait(2)
    active.join(timeout=2)
    replacement.join(timeout=2)
    with pytest.raises(Exception, match="ownership is stale"):
        with backend.transport_guard("run_a", "owner_a"):
            pass


def test_hardened_exact_text_patch_is_real_for_a_shell_free_operation(
    tmp_path: Path,
) -> None:
    catalog, runtime, _, root = _system(tmp_path, with_text_patch=True)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    worker.call_tool(
        "worker_file_write_begin",
        {"relative_path": "output/result.json", "operation": "create"},
    )
    worker.call_tool("worker_file_write_chunk", {"content": '{"draft":true}\n'})
    worker.call_tool("worker_file_write_commit", {})
    patched = worker.call_tool(
        "worker_file_apply_patch",
        {
            "relative_path": "output/result.json",
            "patch": (
                "*** Begin Patch\n"
                "*** Update File: output/result.json\n"
                "@@\n"
                "-{\"draft\":true}\n"
                "+{\"draft\":false}\n"
                "*** End Patch\n"
            ),
        },
    )
    assert patched["state"] == "patched"
    assert Path(opened["workspace_path"], "output/result.json").read_text(
        encoding="utf-8"
    ) == '{"draft":false}\n'
    with pytest.raises(Exception, match="server-side workspace edit failed"):
        worker.call_tool(
            "worker_file_apply_patch",
            {
                "relative_path": "output/result.json",
                "patch": (
                    "*** Begin Patch\n"
                    "*** Update File: output/result.json\n"
                    "@@\n"
                    "-{\"draft\":true}\n"
                    "+{\"draft\":false}\n"
                    "*** End Patch\n"
                ),
            },
        )


@pytest.mark.parametrize("op", ["add", "replace", "remove", "test"])
def test_hardened_json_patch_rejects_invalid_paths_atomically(tmp_path: Path, op: str) -> None:
    catalog, runtime, _, root = _system(tmp_path, with_json_patch=True)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    original = b'{"items":[{"value":1},{"value":2}],"empty":[],"marker":0}\n'
    worker.call_tool("worker_file_write_begin", {"relative_path": "output/result.json"})
    worker.call_tool("worker_file_write_chunk", {"content": original.decode()})
    worker.call_tool("worker_file_write_commit", {})
    target = Path(opened["workspace_path"], "output/result.json")
    invalid_indices = ["-1", "+1", "01", "1.0", " 1", "١", "100"]
    paths = [f"/items/{index}" for index in invalid_indices]
    paths += [f"/items/{index}/value" for index in [*invalid_indices, "2", "-"]]
    paths += ["/missing/value", "/marker/value", "/items/~2"]
    if op != "add":
        paths += ["/items/2", "/items/-", "/empty/0", "/missing"]
    else:
        paths += ["/empty/1"]
    for path in paths:
        operation = {"op": op, "path": path}
        if op != "remove":
            operation["value"] = {"value": 2} if path.count("/") == 2 else 2
        with pytest.raises(WorkerToolError, match="server-side workspace edit failed") as rejected:
            worker.call_tool("worker_file_json_patch", {
                "relative_path": "output/result.json",
                "expected_digest": hashlib.sha256(original).hexdigest(),
                "operations": [
                    {"op": "replace", "path": "/marker", "value": 1},
                    operation,
                ],
            })
        assert str(rejected.value.__cause__) == "JSON patch is invalid"
        assert rejected.value.details[0]["repairable"] is True
        assert target.read_bytes() == original, path
        assert runtime.runs.status(worker._run_id).state == "running"
    repaired = worker.call_tool("worker_file_json_patch", {
        "relative_path": "output/result.json",
        "expected_digest": hashlib.sha256(original).hexdigest(),
        "operations": [{"op": "replace", "path": "/items/1/value", "value": 3}],
    })
    assert repaired["state"] == "patched"
    assert json.loads(target.read_bytes())["items"][1]["value"] == 3


def test_hardened_json_patch_accepts_array_bounds_and_object_pointer_keys(tmp_path: Path) -> None:
    catalog, runtime, _, root = _system(tmp_path, with_json_patch=True)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    original = '{"items":[],"01":1,"-1":2,"+1":3,"":4,"a/b":{"~":5},"-":6}\n'
    worker.call_tool("worker_file_write_begin", {"relative_path": "output/result.json"})
    worker.call_tool("worker_file_write_chunk", {"content": original})
    worker.call_tool("worker_file_write_commit", {})
    patched = worker.call_tool("worker_file_json_patch", {
        "relative_path": "output/result.json",
        "operations": [
            {"op": "test", "path": "/01", "value": 1},
            {"op": "test", "path": "/-1", "value": 2},
            {"op": "test", "path": "/+1", "value": 3},
            {"op": "test", "path": "/", "value": 4},
            {"op": "test", "path": "/a~1b/~0", "value": 5},
            {"op": "test", "path": "/-", "value": 6},
            {"op": "add", "path": "/items/0", "value": 10},
            {"op": "add", "path": "/items/1", "value": 20},
            {"op": "add", "path": "/items/-", "value": 30},
            {"op": "add", "path": "/items/1", "value": 15},
            {"op": "replace", "path": "/items/0", "value": 11},
            {"op": "test", "path": "/items/3", "value": 30},
            {"op": "remove", "path": "/items/3"},
            {"op": "replace", "path": "/", "value": 40},
            {"op": "add", "path": "/new", "value": None},
        ],
    })
    assert patched["state"] == "patched"
    assert json.loads(Path(opened["workspace_path"], "output/result.json").read_bytes()) == {
        "items": [11, 15, 20], "01": 1, "-1": 2, "+1": 3, "": 40, "a/b": {"~": 5}, "-": 6, "new": None,
    }


@pytest.mark.parametrize("failure", ["byte_count", "patch", "existing_file"])
def test_hardened_failed_commit_releases_upload_for_fresh_write(tmp_path: Path, failure: str) -> None:
    catalog, runtime, _, root = _system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    target = Path(opened["workspace_path"], "output/result.json")
    original = b'{"original":true}\n'
    if failure == "patch":
        target.write_bytes(original)
    worker.call_tool("worker_file_write_begin", {
        "relative_path": "output/result.json",
        "operation": "patch" if failure == "patch" else "create",
        "expected_bytes": 100 if failure == "byte_count" else 2,
    })
    worker.call_tool("worker_file_write_chunk", {"content": "{}"})
    if failure == "existing_file":
        target.write_bytes(original)
    buffer = worker._editor._upload.content
    with pytest.raises(WorkerToolError, match="server-side workspace edit failed"):
        worker.call_tool("worker_file_write_commit", {})
    if failure == "byte_count":
        assert not target.exists()
    else:
        assert target.read_bytes() == original
    assert worker._editor._upload is None
    assert not buffer
    assert runtime.runs.status(worker._run_id).state == "running"
    destination = "output/collections/fresh.json"
    worker.call_tool("worker_file_write_begin", {"relative_path": destination, "expected_bytes": 2})
    worker.call_tool("worker_file_write_chunk", {"content": "{}"})
    assert worker.call_tool("worker_file_write_commit", {})["state"] == "committed"
    fresh = Path(opened["workspace_path"], destination)
    assert fresh.read_bytes() == b"{}"
    assert fresh.stat().st_mode & 0o777 == 0o600
    assert worker._editor._upload is None


def test_hardened_server_write_rejects_parent_symlink_escape(tmp_path: Path) -> None:
    catalog, runtime, _, root = _system(tmp_path)
    _invoke(root)
    worker = _worker(catalog, runtime)
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(opened["workspace_path"])
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "output").rmdir()
    (workspace / "output").symlink_to(outside, target_is_directory=True)
    worker.call_tool(
        "worker_file_write_begin",
        {"relative_path": "output/result.json", "operation": "create"},
    )
    worker.call_tool("worker_file_write_chunk", {"content": "{}"})
    with pytest.raises(Exception, match="server-side workspace edit failed"):
        worker.call_tool("worker_file_write_commit", {})
    assert list(outside.iterdir()) == []
    assert runtime.runs.status(worker._run_id).state == "running"


@pytest.mark.process_e2e
def test_hardened_stdio_process_recovers_the_exact_running_run(
    tmp_path: Path,
) -> None:
    catalog, runtime, _, root = _system(tmp_path)
    _invoke(root)
    compiled = catalog.operation("blind.csv.observe.v1")
    site = tmp_path / "site"
    metadata = site / "l5_hardened_plugins-0.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: l5-hardened-plugins\nVersion: 0.0\n",
        encoding="utf-8",
    )
    blind_fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures/plugins/blind_csv_operation_plugin"
    )
    blind_fixture_has_metadata = any(blind_fixture.glob("*.egg-info/entry_points.txt"))
    installed = {
        entry.name
        for entry in importlib.metadata.entry_points(group="scidiscovery.plugins")
    }
    entry_points = "[scidiscovery.plugins]\n"
    if "builtin" not in installed:
        entry_points += "builtin = scidiscovery.builtin_plugin:CORE_PLUGIN\n"
    if "general_science" not in installed:
        entry_points += "general_science = scidiscovery.general_science_plugin:PLUGIN\n"
    if "blind_csv" not in installed and not blind_fixture_has_metadata:
        entry_points += "blind_csv = blind_csv_plugin.plugin:PLUGIN\n"
    (metadata / "entry_points.txt").write_text(entry_points, encoding="utf-8")
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "SCID_TEST_HARDENED_CSV_PLUGIN": "1",
            "PYTHONPATH": os.pathsep.join(
                (
                        str(site),
                        str(Path(__file__).resolve().parents[2] / "src"),
                        str(blind_fixture),
                )
            ),
        }
    )
    command = [
        sys.executable,
        "-m",
        "scidiscovery.artifact_agent.interfaces.mcp_hardened_worker",
        "--state-root",
        str(runtime.state_root),
        "--operation-id",
        compiled.spec.operation_id,
        "--operation-digest",
        compiled.digest,
    ]

    def request(identifier: int, name: str, arguments: dict[str, object]):
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": identifier,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            separators=(",", ":"),
        )

    first = subprocess.run(
        command,
        input=request(1, "worker_open_assignment", {}) + "\n",
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    opened = json.loads(first.stdout)["result"]["structuredContent"]
    assert opened["state"] == "opened"
    run_id = runtime.scheduler_bindings.resolve(
        instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
        namespace="run",
        name="observation",
    )
    with sqlite3.connect(runtime.hardened_backend.dispatch_database) as connection:
        connection.execute(
            "UPDATE active_transport SET lease_deadline_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00+00:00", run_id),
        )
    result = canonical_json(
        {
            "schema_version": 1,
            "handoff": {"verdict": "pass", "summary": "Process result."},
            "payload": {
                "schema_probe": CSV_SCHEMA_PROBE,
                "structure": {
                    "source_sha256": hashlib.sha256(RAW).hexdigest(),
                    "row_count": 2,
                    "columns": ["sample", "value"],
                    "numeric_means": {"value": 2.0},
                },
                "interpretation": "The bounded arithmetic mean is two.",
                "limitations": ["Two rows do not establish causality."],
            },
        }
    ).decode("utf-8")
    calls = (
        request(2, "worker_open_assignment", {}),
        request(3, "worker_csv_summarize", {}),
        request(
            4,
            "worker_file_write_begin",
            {"relative_path": "output/result.json", "operation": "create"},
        ),
        request(5, "worker_file_write_chunk", {"content": result}),
        request(6, "worker_file_write_commit", {}),
        request(7, "worker_submit_result", {}),
    )
    restarted = subprocess.run(
        command,
        input="\n".join(calls) + "\n",
        text=True,
        capture_output=True,
        env=environment,
        check=True,
    )
    responses = [json.loads(line) for line in restarted.stdout.splitlines()]
    assert responses[1]["result"]["structuredContent"]["numeric_means"] == {
        "value": 2.0
    }
    assert responses[-1]["result"]["structuredContent"]["state"] == "completed"
    assert root.call_tool("run_status", {"name": "observation"})["state"] == "completed"


def test_optional_policies_are_compiled_only_for_declaring_operations() -> None:
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN))
    ordinary = catalog.operation("blind.csv.observe.v1")
    assert ordinary.spec.input_admission is None
    assert ordinary.spec.review is not None
    assert ordinary.spec.review.approval is None
    assert ordinary.spec.executor.kind == "agent"


def test_hardened_codex_profile_uses_run_worker_not_legacy_proxy(
    tmp_path: Path,
) -> None:
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN))
    project = tmp_path / "project"
    project.mkdir()
    workspace = project / "workspace"
    workspace.mkdir()
    initialize(
        project,
        python_executable=Path(os.sys.executable),
        python_path=Path(__file__).resolve().parents[2] / "src",
        control_socket=tmp_path / "control.sock",
        state_root=tmp_path / "state",
        worker_backend="hardened",
        operation_catalog=catalog,
    )
    validate_installation_profile(
        project,
        workspace=workspace,
        python_path=Path(__file__).resolve().parents[2] / "src",
        operation_catalog=catalog,
        state_root=tmp_path / "state",
        worker_backend="hardened",
    )
    config = (project / ".codex/config.toml").read_text(encoding="utf-8")
    assert "mcp_proxy" in config
    assert "scid_worker_" not in config
    assert "mcp_worker_proxy" not in config
    generated = {
        path.stem: path.read_text(encoding="utf-8")
        for path in project.joinpath(".codex/agents").glob("*.toml")
    }
    compatible = {
        operation_agent_type(catalog.operation(operation_id))
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
        and HardenedWorkerBackend.supports_operation(
            catalog.operation(operation_id)
        )
    }
    assert set(generated) == compatible
    assert generated
    for profile in generated.values():
        assert "shell_tool = false" in profile
        assert "unified_exec = false" in profile
        assert "view_image = false" in profile
        assert "Native shell, code execution, file tools" in profile
        assert "cannot technically hide" not in profile


@pytest.mark.parametrize("backend", ["local", "hardened"])
def test_one_tool_model_change_reaches_schema_call_and_identity(tmp_path, monkeypatch, backend):
    from dataclasses import replace
    from typing import Literal
    from pydantic import BaseModel, field_validator
    import blind_csv_plugin.plugin as plugin_module
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.operations.spec import ComponentSpec
    from scidiscovery.operations.tooling import WorkerToolDefinition

    class NumberInput(BaseModel):
        value: int

    class ChoiceInput(BaseModel):
        value: Literal["ready"]

    class DynamicErrorInput(BaseModel):
        value: str

        @field_validator("value")
        @classmethod
        def check_value(cls, value):
            if value != "ready":
                raise ValueError("Unsupported value: " + value)
            return value

    original = BLIND_CSV_PLUGIN.operations[0]
    # This fixture probes a tool interface, not a scientific review workflow.
    observe = original.model_copy(update={"review": None, "executor": original.executor.model_copy(update={
        "tools": (*original.executor.tools, ComponentRef("declaration_tool")),
    })})
    plugin = BLIND_CSV_PLUGIN.model_copy(update={
        "components": (*BLIND_CSV_PLUGIN.components, ComponentSpec(
            "declaration_tool", "worker_tool", "blind_csv_plugin.plugin:DECLARATION_TOOL",
        )),
        "operations": (observe, *BLIND_CSV_PLUGIN.operations[1:]),
    })
    calls = []
    tool = WorkerToolDefinition(
        name="worker_declaration_probe", description="Read the one declared value.",
        input_model=NumberInput, capability="fixture.declaration",
        handler=lambda value: calls.append(value.value) or {"value": value.value},
    )
    identities = []
    for index, (model, good, bad, expected_type) in enumerate((
        (NumberInput, 7, "7", "integer"), (ChoiceInput, "ready", 7, "string"),
        (DynamicErrorInput, "ready", "SECRET_INPUT_SENTINEL", "string"),
    )):
        # Only the referenced model changes; no per-consumer Schema or parser edit.
        monkeypatch.setattr(plugin_module, "DECLARATION_TOOL", replace(tool, input_model=model), raising=False)
        case = tmp_path / str(index); case.mkdir()
        catalog, runtime, _, root = _system(case, blind_plugin=plugin, worker_backend=backend)
        _invoke(root)
        compiled = catalog.operation(observe.operation_id)
        identities.append(compiled.digest)
        cls = HardenedWorkerMCPRouter if backend == "hardened" else LocalWorkerMCPRouter
        router = cls(runtime.runs, operation_id=observe.operation_id, operation_digest=compiled.digest)
        mcp = MCPRouter(router, name="declared-test")
        def call(name, args):
            return mcp.handle({"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{"name":name,"arguments":args}})
        assert "result" in call("worker_open_assignment", {})
        schema = next(t for t in router.list_tools() if t['name'] == tool.name)
        assert schema['inputSchema']['properties']['value']['type'] == expected_type
        before = len(calls)
        rejection = call(tool.name, {"value":bad})
        diagnostic = rejection["error"]["data"]["diagnostics"][0]
        assert diagnostic["code"] == "invalid_arguments"
        assert diagnostic["path"] == "$.value"
        assert diagnostic["phase"] == "tool_arguments"
        summary = runtime.runs.diagnostic_summary(runtime.runs.status(router._run_id))
        assert "SECRET_INPUT_SENTINEL" not in json.dumps(rejection) + json.dumps(summary)
        assert summary["latest_tool_error"]["details"][0]["path"] == "$.value"
        assert len(calls) == before
        assert call(tool.name, {"value":good})['result']['structuredContent'] == {"value":good}
        assert calls[-1] == good
    assert len(set(identities)) == len(identities)


def test_root_mcp_argument_diagnostics_exclude_rejected_values():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    called = Mock()
    mcp = MCPRouter(RootMCPRouter(SimpleNamespace(runs=None, run_list=called)), name="root-test")
    response = mcp.handle({"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{
        "name":"run_list", "arguments":{"limit":"/tmp/secret-token-do-not-echo"},
    }})
    assert "secret-token" not in json.dumps(response)
    detail = response["error"]["data"]["diagnostics"][0]
    assert (detail["code"],detail["path"],detail["phase"]) == ("invalid_arguments","$.limit","tool_arguments")
    called.assert_not_called()
