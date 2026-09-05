from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import fields, replace
from pathlib import Path

from blind_csv_plugin.contracts import (
    CSV_SCHEMA_PROBE,
    CsvObservation,
    CsvReview,
    summarize_csv,
)
from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN
from architecture_operation_test_plugin.plugin import (
    ARCHITECTURE_TEST_PLUGIN,
)
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.service.local_workspace import (
    SealedFile,
    SealedWorkspace,
)
from scidiscovery.artifact_agent.service.run_outputs import (
    RunCheckerError,
    RunOutputError,
    validate_run_output,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameConflict
import pytest


def _catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN))


def _envelope(
    payload: object,
    *,
    verdict: str = "pass",
    next_action_kind: str | None = None,
) -> bytes:
    handoff = {"verdict": verdict, "summary": "Bounded local result."}
    if next_action_kind is not None:
        handoff["next_action_kind"] = next_action_kind
    return canonical_json(
        {
            "schema_version": 1,
            "handoff": handoff,
            "payload": payload,
        }
    )


def test_missing_optional_context_is_a_checker_fault_not_worker_rejection(
    tmp_path: Path,
) -> None:
    author = ARCHITECTURE_TEST_PLUGIN.operations[0]
    optional_input = author.inputs[0].model_copy(update={"min_items": 0})
    plugin = ARCHITECTURE_TEST_PLUGIN.model_copy(
        update={
            "operations": (
                author.model_copy(update={"inputs": (optional_input,)}),
                *ARCHITECTURE_TEST_PLUGIN.operations[1:],
            )
        }
    )
    compiled = compile_catalog((plugin,)).operation("builtin.test.agent")
    implementations = dict(compiled.implementations)

    def broken_context_checker(*_args: object) -> None:
        raise ValueError("checker implementation defect")

    implementations["architecture_fixture:context_validator"] = (
        broken_context_checker
    )
    compiled = replace(compiled, implementations=implementations)
    content = _envelope(
        {
            "input_seen": True,
            "network_denied": True,
            "sibling_read_denied": True,
            "tool_result": "fixture-inspected:registered-domain-tool",
        }
    )
    root = tmp_path / "sealed"
    root.mkdir()
    (root / "result.json").write_bytes(content)
    sealed = SealedWorkspace(
        backend="test",
        backend_version="1",
        run_id="optional-context",
        digest=hashlib.sha256(content).hexdigest(),
        root=root,
        files=(
            SealedFile(
                relative_path="result.json",
                media_type="application/json",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            ),
        ),
    )
    # An untyped exception is an implementation fault, never a Worker rule
    # violation, even when an optional input happens to be absent.
    with pytest.raises(RunCheckerError, match="context checker failed"):
        validate_run_output(compiled, sealed, input_source_ports={}, input_bytes={})
    with pytest.raises(RunCheckerError, match="context checker failed"):
        validate_run_output(
            compiled,
            sealed,
            input_source_ports={"agent_input": "agent_input"},
            input_bytes={"agent_input": b"{}"},
        )


def test_worker_visible_json_schema_precedes_a_deliberately_weak_validator(
    tmp_path: Path,
) -> None:
    agent = ARCHITECTURE_TEST_PLUGIN.operations[0]
    output = agent.outputs[0].model_copy(
        update={
            "validator": agent.outputs[0].validator.model_copy(
                update={"component_id": "nonempty_validator"}
            ),
            "context_validator": None,
            "context_rule_id": None,
            "context_sources": (),
        }
    )
    plugin = ARCHITECTURE_TEST_PLUGIN.model_copy(
        update={
            "components": tuple(
                item
                for item in ARCHITECTURE_TEST_PLUGIN.components
                if item.component_id
                not in {"agent_result_validator", "context_validator"}
            ),
            "operations": (
                agent.model_copy(update={"outputs": (output,)}),
                *ARCHITECTURE_TEST_PLUGIN.operations[1:],
            )
        }
    )
    compiled = compile_catalog((plugin,)).operation("builtin.test.agent")
    content = _envelope({"anything": "the weak validator accepts this"})
    root = tmp_path / "schema-first"
    root.mkdir()
    (root / "result.json").write_bytes(content)
    sealed = SealedWorkspace(
        backend="test",
        backend_version="1",
        run_id="schema-first",
        digest=hashlib.sha256(content).hexdigest(),
        root=root,
        files=(
            SealedFile(
                relative_path="result.json",
                media_type="application/json",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            ),
        ),
    )
    with pytest.raises(RunOutputError) as caught:
        validate_run_output(
            compiled,
            sealed,
            input_source_ports={"agent_input": "agent_input"},
            input_bytes={"agent_input": b"{}"},
        )
    assert {item["rule_id"] for item in caught.value.details} == {
        "runtime.schema"
    }


def test_untyped_payload_checker_exception_is_a_checker_fault(tmp_path: Path) -> None:
    compiled = compile_catalog((ARCHITECTURE_TEST_PLUGIN,)).operation(
        "builtin.test.agent"
    )
    implementations = dict(compiled.implementations)

    def broken_payload_checker(_raw: bytes) -> None:
        raise ValueError("checker implementation defect")

    implementations["architecture_fixture:agent_result_validator"] = (
        broken_payload_checker
    )
    compiled = replace(compiled, implementations=implementations)
    content = _envelope(
        {
            "input_seen": True,
            "network_denied": True,
            "sibling_read_denied": True,
            "tool_result": "fixture-inspected:registered-domain-tool",
        }
    )
    root = tmp_path / "payload-checker-fault"
    root.mkdir()
    (root / "result.json").write_bytes(content)
    sealed = SealedWorkspace(
        backend="test",
        backend_version="1",
        run_id="payload-checker-fault",
        digest=hashlib.sha256(content).hexdigest(),
        root=root,
        files=(
            SealedFile(
                relative_path="result.json",
                media_type="application/json",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            ),
        ),
    )
    with pytest.raises(RunCheckerError, match="payload checker failed"):
        validate_run_output(
            compiled,
            sealed,
            input_source_ports={"agent_input": "agent_input"},
            input_bytes={"agent_input": b"{}"},
        )


def test_local_run_uses_native_files_one_domain_tool_and_one_terminal_authority(
    tmp_path: Path,
) -> None:
    catalog = _catalog()
    project = tmp_path / "project"
    project.mkdir()
    local_workspace_root = project / ".scidiscovery-runs"
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="local",
        local_workspace_root=local_workspace_root,
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="l2_local",
        title="L2 local Run",
        objective="Prove the minimal default Run runtime.",
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
        idempotency_key="l2:source",
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

    internal_observe = catalog.operation("blind.csv.observe.v1").spec.model_copy(
        update={"catalog_scope": "internal"}
    )
    internal_plugin = BLIND_CSV_PLUGIN.model_copy(
        update={
            "operations": tuple(
                internal_observe
                if item.operation_id == internal_observe.operation_id
                else item
                for item in BLIND_CSV_PLUGIN.operations
            )
        }
    )
    root.facade._operation_catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, internal_plugin)
    )
    scope_rejected = root.call_tool(
        "operation_preflight",
        {
            "name": "internal_observe",
            "operation_id": "blind.csv.observe.v1",
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": "This internal action must not be schedulable.",
        },
    )
    assert scope_rejected["admissible"] is False
    assert scope_rejected["reason_code"] == "operation_scope_forbidden"
    root.facade._operation_catalog = catalog

    backend = runtime.runs.backend

    class ReviewerUnavailable:
        @staticmethod
        def supports_operation(value):
            return value.spec.operation_id != "blind.csv.review.v1"

        @staticmethod
        def unsupported_requirements(value):
            return (
                ("reviewer_fixture_unavailable",)
                if value.spec.operation_id == "blind.csv.review.v1"
                else ()
            )

    runtime.runs.backend = ReviewerUnavailable()
    try:
        unavailable_ids = {
            item["operation_id"]
            for item in root.call_tool("operation_catalog", {"scope": "public"})[
                "operations"
            ]
        }
        assert "blind.csv.observe.v1" not in unavailable_ids
        assert "blind.csv.review.v1" not in unavailable_ids
        unavailable = root.call_tool(
            "operation_preflight",
            {
                "name": "unavailable_observe",
                "operation_id": "blind.csv.observe.v1",
                "inputs": [
                    {"port": "source_table", "artifact_names": ["source_csv"]}
                ],
                "instruction": "The unavailable review edge must close this action.",
            },
        )
        assert unavailable["admissible"] is False
        assert unavailable["reason_code"] == "operation_runtime_unavailable"
    finally:
        runtime.runs.backend = backend

    observe_view = next(
        item
        for item in root.call_tool("operation_catalog", {"scope": "public"})[
            "operations"
        ]
        if item["operation_id"] == "blind.csv.observe.v1"
    )
    assert observe_view["review_edge"] == {
        "reviewer_operation": "blind.csv.review.v1",
        "reviewer_input_port": "csv_observation",
        "subject_outputs": ["csv_observation"],
        "accepted_verdicts": ["pass"],
    }
    created = root.call_tool(
        "operation_invoke",
        {
            "name": "observe",
            "operation_id": "blind.csv.observe.v1",
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": "Make one bounded observation.",
        },
    )
    assert created["result"]["state"] == "queued"
    assert not hasattr(runtime, "tasks") and not hasattr(runtime, "tokens")

    compiled = catalog.operation("blind.csv.observe.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )
    tools = {item["name"] for item in worker.list_tools()}
    assert tools == {
        "worker_open_assignment",
        "worker_heartbeat",
        "worker_submit_result",
        "worker_csv_summarize",
    }
    opened = worker.call_tool("worker_open_assignment", {})
    workspace = Path(opened["workspace_path"])
    assert workspace.is_relative_to(local_workspace_root)
    assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
    assert assignment["output"]["semantic_contract_pointer"] == (
        "/properties/payload/x-scidiscovery-semantic-constraints"
    )
    assert assignment["output"]["validation_contract_pointer"] == (
        "/properties/payload/x-scidiscovery-validation-contract"
    )
    result_schema = json.loads(
        (workspace / assignment["output"]["schema_path"]).read_text("utf-8")
    )
    payload_schema = result_schema["properties"]["payload"]
    assert payload_schema["x-scidiscovery-semantic-constraints"][
        "schema_version"
    ] == 1
    validation_contract = payload_schema["x-scidiscovery-validation-contract"]
    assert {
        item["rule_id"]
        for item in validation_contract["rules"]
    } == {"runtime.files", "runtime.envelope", "runtime.schema", "runtime.size"}
    assert {item["phase"]: item["rule_id"] for item in validation_contract["checkers"]} == {
        "payload": "blind.payload_consistency",
        "context": "blind.context_binding",
    }
    input_path = workspace / assignment["inputs"][0]["relative_path"]
    assert input_path.read_bytes() == raw
    summary = worker.call_tool("worker_csv_summarize", {})
    assert summary["numeric_means"] == {"value": 2.0}

    output = workspace / "output/result.json"
    output.write_text("{}", encoding="utf-8")
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected" and rejected["diagnostics"]
    assert {item["rule_id"] for item in rejected["diagnostics"]} == {
        "runtime.envelope"
    }
    observation = CsvObservation(
        schema_probe=CSV_SCHEMA_PROBE,
        structure=summarize_csv(raw),
        interpretation="The two bounded values have an arithmetic mean of two.",
        limitations=("Two rows do not establish a causal relationship.",),
    )
    invalid_payload = observation.model_dump(mode="json")
    invalid_payload["schema_probe"] = "undeclared-schema-probe"
    output.write_bytes(_envelope(invalid_payload))
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert {item["rule_id"] for item in rejected["diagnostics"]} == {
        "runtime.schema"
    }
    wrong_structure = observation.model_copy(
        update={
            "structure": observation.structure.model_copy(update={"row_count": 3})
        }
    )
    output.write_bytes(_envelope(wrong_structure.model_dump(mode="json")))
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert {item["rule_id"] for item in rejected["diagnostics"]} == {
        "blind.context_binding"
    }
    running = root.call_tool("run_status", {"name": "observe"})
    assert running["state"] == "running"
    assert running["sealed_output_status"] == "unavailable"
    assert running["sealed_output"] is None
    running_summary = root.call_tool(
        "run_list", {"state": "running", "limit": 10}
    )["runs"][0]
    assert "sealed_output" not in running_summary
    assert "scheduler_signal" not in running_summary

    output.write_bytes(
        _envelope(
            observation.model_dump(mode="json"),
            next_action_kind="not a registered operation",
        )
    )
    completed = worker.call_tool("worker_submit_result", {})
    assert completed["state"] == "completed"
    assert completed["receipt"]["head_advance"] == "not_requested"
    author_status = root.call_tool("run_status", {"name": "observe"})
    assert author_status["state"] == "completed"
    assert author_status["output_artifact_name"] == "observe.output"
    assert author_status["sealed_output_status"] == "available"
    assert author_status["sealed_output"] == {
        "artifact_name": "observe.output",
        "kind": "observation",
        "schema": "blind.csv-observation.v1",
        "payload": observation.model_dump(mode="json"),
    }
    assert author_status["scheduler_signal"]["next_action_kind"] == (
        "not a registered operation"
    )

    review_created = root.call_tool(
        "operation_invoke",
        {
            "name": "review",
            "operation_id": "blind.csv.review.v1",
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]},
                {"port": "csv_observation", "artifact_names": ["observe.output"]},
            ],
            "instruction": "Independently review the exact observation.",
        },
    )
    assert review_created["result"]["state"] == "queued"
    review_compiled = catalog.operation("blind.csv.review.v1")
    reviewer = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=review_compiled.spec.operation_id,
        operation_digest=review_compiled.digest,
    )
    assert "worker_csv_summarize" not in {item["name"] for item in reviewer.list_tools()}
    review_open = reviewer.call_tool("worker_open_assignment", {})
    review_output = Path(review_open["output_directory"]) / "result.json"
    observation_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name="observe.output",
        )
    ).ref
    review = CsvReview(
        subject_sha256=hashlib.sha256(runtime.artifacts.read(observation_ref)).hexdigest(),
        verdict="pass",
        rationale="The exact source structure supports the bounded observation.",
    )
    review_output.write_bytes(_envelope(review.model_dump(mode="json")))
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "completed"
    review_status = root.call_tool("run_status", {"name": "review"})
    review_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name=review_status["output_artifact_name"],
        )
    ).ref
    assert runtime.runs.is_exact_reviewer_output(
        review_ref,
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        accepted_verdicts=("pass",),
        subject_ref=observation_ref,
    )
    assert not runtime.runs.is_exact_reviewer_output(
        review_ref,
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        accepted_verdicts=("revise", "blocked", "inconclusive"),
        subject_ref=observation_ref,
    )

    retired_observe = compiled.spec.model_copy(update={"version": "retired"})
    retired_plugin = BLIND_CSV_PLUGIN.model_copy(
        update={
            "operations": tuple(
                retired_observe
                if item.operation_id == retired_observe.operation_id
                else item
                for item in BLIND_CSV_PLUGIN.operations
            )
        }
    )
    retired_catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, retired_plugin)
    )
    root.facade._operation_catalog = retired_catalog
    runtime.runs.operation_catalog = retired_catalog
    retired_compatible = root.call_tool("run_status", {"name": "observe"})
    assert retired_compatible["sealed_output_status"] == "contract_retired"
    assert retired_compatible["sealed_output"] is None
    assert retired_compatible["scheduler_signal"] is None
    retired_inventory = root.call_tool("scientific_inventory", {})
    retired_observation = next(
        item
        for item in retired_inventory["objects"]
        if item["artifact_name"] == "observe.output"
    )
    assert retired_observation["producer_handoff"] is None
    run_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="run",
        name="observe",
    )
    with sqlite3.connect(runtime.runs.database_path) as connection:
        connection.execute(
            "UPDATE runs SET signal_json = ? WHERE run_id = ?",
            (
                canonical_json(
                    {
                        "schema_version": 1,
                        "verdict": "pass",
                        "summary": "Legacy ABI signal.",
                        "assumptions": [],
                        "missing_inputs": [],
                        "next_actions": [],
                        "next_action_kind": "legacy.route",
                    }
                ),
                run_id,
            ),
        )
    retired = root.call_tool("run_status", {"name": "observe"})
    assert retired["state"] == "completed"
    assert retired["sealed_output_status"] == "contract_retired"
    assert retired["sealed_output"] is None
    assert retired["scheduler_signal"] is None


def test_operation_tool_context_contains_no_control_identity() -> None:
    names = {item.name for item in fields(OperationToolContext)}
    assert not names.intersection(
        {"run", "run_id", "task", "task_id", "session", "session_token", "proxy", "worker_id", "database", "current"}
    )


def test_scientific_current_is_an_exact_compare_and_set_head(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="local",
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="current_cas",
        title="Exact current",
        objective="Keep recovery and stale-input checks exact.",
    )
    refs = []
    for index in range(2):
        refs.append(
            runtime.artifacts.register(
                canonical_json({"revision": index + 1}),
                ArtifactRegistration(
                    kind="research_objective",
                    schema_id="opaque",
                    payload_schema_version=1,
                    media_type="application/json",
                    creator=runtime.actor,
                ),
                idempotency_key=f"l2:current:{index}",
            ).ref
        )
    first = runtime.scheduler_bindings.select_scientific_object(
        instance=instance.instance_id,
        kind="research_objective",
        logical_name="objective",
        artifact_ref=refs[0],
    )
    assert first.artifact_ref == refs[0]
    second = runtime.scheduler_bindings.select_scientific_object(
        instance=instance.instance_id,
        kind="research_objective",
        logical_name="objective",
        artifact_ref=refs[1],
        expected_ref=refs[0],
    )
    assert second.artifact_ref == refs[1]
    with pytest.raises(SchedulerNameConflict, match="compare-and-set"):
        runtime.scheduler_bindings.select_scientific_object(
            instance=instance.instance_id,
            kind="research_objective",
            logical_name="objective",
            artifact_ref=refs[0],
            expected_ref=refs[0],
        )
