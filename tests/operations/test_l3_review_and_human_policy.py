from __future__ import annotations

import hashlib
import os
from pathlib import Path

from blind_csv_plugin.contracts import (
    CSV_SCHEMA_PROBE,
    CsvObservation,
    CsvReview,
    summarize_csv,
)
from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN, REVIEWER

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
from scidiscovery.operations.spec import ComponentRef, OperationDescription


RAW = b"sample,value\na,1\nb,3\n"


def test_reviewer_declares_the_native_workspace_capability_needed_for_review():
    assert REVIEWER.executor.native_tools.shell == "inherited_prototype"


def _review_gate_catalog():
    reviewed_observation = REVIEWER.inputs[1]
    optional_review = REVIEWER.inputs[1].model_copy(
        update={
            "name": "independent_review",
            "description": "Exact independent review, when available.",
            "schema_id": "blind.csv-review.v1",
            "schema_resource": ComponentRef("review_schema"),
            "min_items": 0,
        }
    )
    output = REVIEWER.outputs[0].model_copy(update={"name": "consumption_result"})
    consumer = REVIEWER.model_copy(
        update={
            "operation_id": "blind.csv.consume.v1",
            "description": OperationDescription(
                purpose="Consume one independently reviewed observation.",
                applies_when="The exact observation has a passing exact review.",
                not_for="Creating or editing the observation or its review.",
            ),
            "inputs": (REVIEWER.inputs[0], reviewed_observation, optional_review,
                       *tuple(port for port in REVIEWER.inputs if port.name == "user_context")),
            "outputs": (output, *(port for port in REVIEWER.outputs if port.collection is not None)),
        }
    )
    plugin = BLIND_CSV_PLUGIN.model_copy(
        update={"operations": (*BLIND_CSV_PLUGIN.operations, consumer)}
    )
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, plugin))


def _system(tmp_path: Path, *, catalog=None):
    catalog = catalog or _review_gate_catalog()
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
        worker_backend="local",
    )
    assert runtime.runs is not None
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="l3_review",
        title="L3 exact review",
        objective="Prove that review gates bind one exact author result.",
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
        idempotency_key="l3:source",
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


def _envelope(payload: object, *, verdict: str = "pass") -> bytes:
    return canonical_json(
        {
            "schema_version": 1,
            "handoff": {"verdict": verdict, "summary": "Bounded L3 result."},
            "payload": payload,
        }
    )


def _complete_author(catalog, runtime, root, *, instruction: str, conflict: str, verdict="pass"):
    created = root.call_tool(
        "operation_invoke",
        {
            "name": "observation",
            "operation_id": "blind.csv.observe.v1",
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": instruction,
            "on_conflict": conflict,
        },
    )
    name = created["result"]["name"]
    compiled = catalog.operation("blind.csv.observe.v1")
    from tests.operations.worker_fixtures import attached_worker
    worker = attached_worker(runtime, root, name)
    opened = worker.call_tool("worker_open_assignment", {})
    observation = CsvObservation(
        schema_probe=CSV_SCHEMA_PROBE,
        structure=summarize_csv(RAW),
        interpretation=f"The bounded mean is two ({name}).",
        limitations=("Two rows do not establish causality.",),
    )
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(observation.model_dump(mode="json"), verdict=verdict)
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    return root.call_tool("run_status", {"name": name})["output_artifact_name"]


def _complete_review(catalog, runtime, root, *, name: str, subject_name: str):
    root.call_tool(
        "operation_invoke",
        {
            "name": name,
            "operation_id": "blind.csv.review.v1",
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]},
                {"port": "csv_observation", "artifact_names": [subject_name]},
            ],
            "instruction": "Independently review the exact observation.",
        },
    )
    compiled = catalog.operation("blind.csv.review.v1")
    from tests.operations.worker_fixtures import attached_worker
    worker = attached_worker(runtime, root, name)
    opened = worker.call_tool("worker_open_assignment", {})
    subject_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=runtime.scheduler_bindings.list_instances()[0].instance_id,
            namespace="artifact",
            name=subject_name,
        )
    ).ref
    review = CsvReview(
        subject_sha256=hashlib.sha256(runtime.artifacts.read(subject_ref)).hexdigest(),
        verdict="pass",
        rationale="The exact CSV supports the bounded structural observation.",
    )
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(review.model_dump(mode="json"))
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    return root.call_tool("run_status", {"name": name})["output_artifact_name"]


def _consumer_preflight(root, observation: str, review: str | None):
    inputs = [
        {"port": "source_table", "artifact_names": ["source_csv"]},
        {"port": "csv_observation", "artifact_names": [observation]},
    ]
    if review is not None:
        inputs.append(
            {"port": "independent_review", "artifact_names": [review]}
        )
    return root.call_tool(
        "operation_preflight",
        {
            "name": "consume",
            "operation_id": "blind.csv.consume.v1",
            "inputs": inputs,
            "instruction": "Consume only an exactly reviewed observation.",
        },
    )


def test_ordinary_downstream_use_does_not_require_a_fixed_review_stage(
    tmp_path: Path,
) -> None:
    catalog, runtime, _, root = _system(tmp_path)
    consumer = catalog.operation("blind.csv.consume.v1")
    assert next(
        port for port in consumer.spec.inputs if port.name == "csv_observation"
    ).usage == "prior_signal"
    assert "allowed_input_usages" not in type(
        catalog.operation("blind.csv.observe.v1").spec.outputs[0]
    ).model_fields
    first = _complete_author(
        catalog,
        runtime,
        root,
        instruction="Make the first bounded observation.",
        conflict="reject",
    )
    missing = _consumer_preflight(root, first, None)
    assert missing["admissible"] is True

    first_review = _complete_review(
        catalog, runtime, root, name="first_review", subject_name=first
    )
    assert _consumer_preflight(root, first, first_review)["admissible"] is True

    revised = _complete_author(
        catalog,
        runtime,
        root,
        instruction="Intentionally revise the bounded interpretation.",
        conflict="create_revision",
    )
    assert revised != first
    stale = _consumer_preflight(root, revised, first_review)
    assert stale["admissible"] is True  # Context is not a qualification grant.

    revised_review = _complete_review(
        catalog, runtime, root, name="revised_review", subject_name=revised
    )
    assert _consumer_preflight(root, revised, revised_review)["admissible"] is True


def test_default_local_exploration_has_no_qualification_or_approval_state(
    tmp_path: Path,
) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    _complete_author(
        catalog,
        runtime,
        root,
        instruction="Make one ordinary exploratory observation.",
        conflict="reject",
    )
    assert runtime.scheduler_bindings.list(
        instance=instance.instance_id, namespace="approval"
    ) == ()
    assert root.call_tool("approval_list", {}) == {"approvals": [], "next_before": None}
    root_tools = {tool["name"] for tool in root.list_tools()}
    assert "approval_status" in root_tools
    assert not any("decide" in name or "record_decision" in name for name in root_tools)
