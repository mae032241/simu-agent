from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from blind_csv_plugin.contracts import (
    CSV_SCHEMA_PROBE,
    CsvObservation,
    CsvReview,
    summarize_csv,
)
from blind_csv_plugin.plugin import (
    AUTHOR,
    FILE_TOOLS,
    JSON_CODEC,
    OBSERVATION,
    PLUGIN,
    REVIEWER,
    TABLE,
    WORKSPACE,
)
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import (
    HardenedWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.hardened_workspace import (
    HardenedWorkerBackend,
)
from scidiscovery.artifact_agent.service.runs import _revision_workspace_mode
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operation_declaration import scientific_agent_operation
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
from scidiscovery.operations.invoke import (
    active_direct_revision_ports,
    direct_revision_ports,
)
from scidiscovery.operations.spec import (
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    InputAdmissionSpec,
    InputPortSpec,
    ReviewSpec,
)


RAW = b"sample,value\na,1\nb,3\n"


def _input(
    name: str,
    description: str,
    schema: str,
    schema_resource: str,
    *,
    usage: str,
    codec: ComponentRef = JSON_CODEC,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=codec,
        schema_resource=ComponentRef(schema_resource),
        max_item_bytes=2 * 1024 * 1024,
        min_items=min_items,
        usage=usage,
        exposure="full",
    )


REVISION = scientific_agent_operation(
    "blind.csv.revise.v1",
    "Revise one exact bounded CSV observation.",
    "An independently reviewed observation requires a correction.",
    "Changing the source table or inheriting the review verdict.",
    agent=ComponentRef("author"),
    workspace=WORKSPACE,
    prompt=ComponentRef("author_prompt"),
    tools=(
        *FILE_TOOLS,
        ComponentRef("file_json_patch_tool", plugin_id="builtin"),
    ),
    inputs=(
        _input(
            "prior_draft",
            "Exact observation revision base.",
            "blind.csv-observation.v1",
            "observation_schema",
            usage="revision_base",
        ),
        _input(
            "change_request",
            "Exact independent review requesting correction.",
            "blind.csv-review.v1",
            "review_schema",
            usage="change_request",
        ),
        _input(
            "source_table",
            "Exact source table.",
            "blind.opaque.v1",
            "opaque_schema",
            usage="claim_evidence",
            codec=ComponentRef("opaque_codec", plugin_id="general_science"),
            media_types=("text/csv",),
        ),
    ),
    outputs=(OBSERVATION,),
    timeout=300,
    max_input_bytes=4 * 1024 * 1024,
    max_output_bytes=64 * 1024,
    max_files=1,
    native_shell="none",
    review=ReviewSpec(
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        subject_outputs=("csv_observation",),
    ),
)


def _blind_progress_fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


BLIND_PROGRESS = CallableComponent("transform", _blind_progress_fingerprint)
OPTIONAL_REVISION_INPUTS = (
    _input(
        "prior_draft",
        "Optional immutable observation revision base.",
        "blind.csv-observation.v1",
        "observation_schema",
        usage="revision_base",
        min_items=0,
    ),
    _input(
        "change_request",
        "Optional exact independent review requesting correction.",
        "blind.csv-review.v1",
        "review_schema",
        usage="change_request",
        min_items=0,
    ),
)
OPTIONAL_REVISION_ADMISSION = InputAdmissionSpec(
    cohort_id="observation_revision",
    member_ports=("prior_draft", "change_request"),
)
DUAL_AUTHOR = scientific_agent_operation(
    AUTHOR.operation_id,
    AUTHOR.description.purpose,
    AUTHOR.description.applies_when,
    AUTHOR.description.not_for,
    agent=AUTHOR.executor.component,
    workspace=AUTHOR.executor.workspace,
    prompt=AUTHOR.executor.prompt,
    tools=AUTHOR.executor.tools,
    inputs=(TABLE, *OPTIONAL_REVISION_INPUTS),
    outputs=AUTHOR.outputs,
    timeout=AUTHOR.limits.timeout_seconds,
    max_input_bytes=AUTHOR.limits.max_input_bytes + 3 * 1024 * 1024,
    max_output_bytes=AUTHOR.limits.max_output_bytes,
    max_files=AUTHOR.limits.max_files,
    max_attempts=AUTHOR.limits.max_attempts,
    native_shell=AUTHOR.executor.native_tools.shell,
    input_admission=OPTIONAL_REVISION_ADMISSION,
    review=ReviewSpec(
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        subject_outputs=("csv_observation",),
        max_revisions=2,
        progress_fingerprint=ComponentRef("blind_progress"),
    ),
)


def _catalog(*, hardened: bool = False):
    operations = PLUGIN.operations if hardened else (DUAL_AUTHOR, REVIEWER)
    if hardened:
        operations = tuple(
            operation.model_copy(
                update={
                    "executor": operation.executor.model_copy(
                        update={
                            "native_tools": operation.executor.native_tools.model_copy(
                                update={"shell": "none"}
                            )
                        }
                    )
                }
            )
            for operation in operations
        )
    plugin = PLUGIN.model_copy(
        update={
            "components": (
                *PLUGIN.components,
                *(
                    (
                        ComponentSpec(
                            "blind_progress",
                            "transform",
                            "tests.operations.test_incremental_revision_runtime:BLIND_PROGRESS",
                        ),
                    )
                    if not hardened
                    else ()
                ),
            ),
            "operations": (*operations, REVISION),
        }
    )
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, plugin))


def _optional_catalog(operation=DUAL_AUTHOR):
    plugin = PLUGIN.model_copy(
        update={
            "components": (
                *PLUGIN.components,
                ComponentSpec(
                    "blind_progress",
                    "transform",
                    "tests.operations.test_incremental_revision_runtime:BLIND_PROGRESS",
                ),
            ),
            "operations": (operation, REVIEWER),
        }
    )
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, plugin))


def _envelope(payload: object, *, verdict: str, summary: str) -> bytes:
    return canonical_json(
        {
            "schema_version": 1,
            "handoff": {"verdict": verdict, "summary": summary},
            "payload": payload,
        }
    )


def _worker(catalog, runtime, operation_id: str):
    compiled = catalog.operation(operation_id)
    router = (
        HardenedWorkerMCPRouter
        if runtime.hardened_backend is not None
        else LocalWorkerMCPRouter
    )
    return router(
        runtime.runs,
        operation_id=operation_id,
        operation_digest=compiled.digest,
    )


def _system(tmp_path: Path, *, worker_backend: str = "local"):
    catalog = _catalog(hardened=worker_backend == "hardened")
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend=worker_backend,
        local_workspace_root=project / ".scidiscovery-runs",
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="incremental_revision",
        title="Incremental revision",
        objective="Prove copy-on-write revision semantics.",
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
        idempotency_key="incremental:source",
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


def _create_reviewed_base(
    catalog, runtime, instance, root
) -> tuple[bytes, CsvObservation]:
    root.call_tool(
        "operation_invoke",
        {
            "name": "base",
            "operation_id": "blind.csv.observe.v1",
            "inputs": [{"port": "source_table", "artifact_names": ["source_csv"]}],
            "instruction": "Create one bounded observation.",
        },
    )
    author = _worker(catalog, runtime, "blind.csv.observe.v1")
    opened = author.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
    assert assignment["revision"] is None
    assert not Path(opened["output_directory"], "result.json").exists()
    observation = CsvObservation(
        schema_probe=CSV_SCHEMA_PROBE,
        structure=summarize_csv(RAW),
        interpretation="The bounded arithmetic mean is two.",
        limitations=("Two rows do not establish causality.",),
    )
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(
            observation.model_dump(mode="json"),
            verdict="pass",
            summary="Initial bounded observation.",
        )
    )
    assert author.call_tool("worker_submit_result", {})["state"] == "completed"
    base_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name="base.output",
        )
    ).ref
    base_content = runtime.artifacts.read(base_ref)

    root.call_tool(
        "operation_invoke",
        {
            "name": "review",
            "operation_id": "blind.csv.review.v1",
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]},
                {"port": "csv_observation", "artifact_names": ["base.output"]},
            ],
            "instruction": "Request one bounded wording correction.",
        },
    )
    reviewer = _worker(catalog, runtime, "blind.csv.review.v1")
    opened = reviewer.call_tool("worker_open_assignment", {})
    review = CsvReview(
        subject_sha256=hashlib.sha256(base_content).hexdigest(),
        verdict="revise",
        rationale="Clarify that the interpretation is descriptive only.",
    )
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(
            review.model_dump(mode="json"),
            verdict="blocked",
            summary="One bounded correction is required.",
        )
    )
    assert reviewer.call_tool("worker_submit_result", {})["state"] == "completed"
    return base_content, observation


def test_optional_direct_revision_shape_is_one_bounded_operation() -> None:
    compiled = _optional_catalog().operation("blind.csv.observe.v1")
    direct = direct_revision_ports(compiled)

    assert direct is not None
    assert direct[0].name == "prior_draft"
    assert active_direct_revision_ports(compiled, ("source_table",)) is None
    assert active_direct_revision_ports(
        compiled, ("source_table", "prior_draft", "change_request")
    ) == direct

    from scidiscovery.operation_contract import operation_output_validation_contract

    contract = operation_output_validation_contract(compiled, direct[1])
    revision_rule = next(
        item for item in contract["rules"] if item["rule_id"] == "runtime.revision"
    )
    assert revision_rule["required_inputs"] == ["prior_draft"]
    assert revision_rule["description"].startswith(
        "When the assignment binds the optional revision base"
    )


@pytest.mark.parametrize(
    "operation",
    (
        DUAL_AUTHOR.model_copy(update={"input_admission": None}),
        DUAL_AUTHOR.model_copy(
            update={
                "input_admission": OPTIONAL_REVISION_ADMISSION.model_copy(
                    update={
                        "member_ports": (
                            "prior_draft",
                            "change_request",
                            "source_table",
                        )
                    }
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "input_admission": OPTIONAL_REVISION_ADMISSION.model_copy(
                    update={"approval_kind": "revision_approval"}
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "inputs": tuple(
                    item.model_copy(update={"max_items": 2})
                    if item.usage == "revision_base"
                    else item
                    for item in DUAL_AUTHOR.inputs
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "inputs": tuple(
                    item.model_copy(update={"min_items": 1})
                    if item.usage == "change_request"
                    else item
                    for item in DUAL_AUTHOR.inputs
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "inputs": tuple(
                    item
                    for item in DUAL_AUTHOR.inputs
                    if item.usage != "change_request"
                )
            }
        ),
        DUAL_AUTHOR.model_copy(update={"review": None}),
        DUAL_AUTHOR.model_copy(
            update={
                "review": DUAL_AUTHOR.review.model_copy(
                    update={"max_revisions": 0, "progress_fingerprint": None}
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "review": DUAL_AUTHOR.review.model_copy(
                    update={"progress_fingerprint": None}
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "outputs": (
                    DUAL_AUTHOR.outputs[0].model_copy(
                        update={"media_types": ("text/plain",)}
                    ),
                )
            }
        ),
    ),
)
def test_optional_direct_revision_shape_fails_closed_at_compile(operation) -> None:
    with pytest.raises(CatalogCompileError):
        _optional_catalog(operation)


def _revision_request(name: str, *, resume_from: str | None = None):
    request = {
        "name": name,
        "operation_id": "blind.csv.revise.v1",
        "inputs": [
            {"port": "prior_draft", "artifact_names": ["base.output"]},
            {"port": "change_request", "artifact_names": ["review.output"]},
            {"port": "source_table", "artifact_names": ["source_csv"]},
        ],
        "instruction": "Apply only the exact reviewed correction.",
    }
    if resume_from is not None:
        request["resume_from"] = resume_from
    return request


def _invoke_revision(root, name: str, *, resume_from: str | None = None):
    return root.call_tool(
        "operation_invoke", _revision_request(name, resume_from=resume_from)
    )


def test_revision_workspace_is_copy_on_write_and_publishes_new_snapshot(
    tmp_path: Path,
) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    base_content, observation = _create_reviewed_base(
        catalog, runtime, instance, root
    )
    assert catalog.operation("blind.csv.revise.v1").spec.limits.max_attempts == 2
    _invoke_revision(root, "revision")
    worker = _worker(catalog, runtime, "blind.csv.revise.v1")
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
    assert assignment["revision"] == {
        "mode": "copy_on_write",
        "base_source_name": "prior_draft",
        "editable_target": "output/result.json",
        "publication": "complete_immutable_snapshot",
    }
    output = Path(opened["output_directory"], "result.json")
    draft = json.loads(output.read_text("utf-8"))
    assert draft["payload"] == observation.model_dump(mode="json")
    assert draft["handoff"] == {"summary": "", "verdict": ""}

    draft["handoff"] = {
        "verdict": "pass",
        "summary": "Revision handoff authored by the Worker.",
    }
    output.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    unchanged = worker.call_tool("worker_submit_result", {})
    assert unchanged["state"] == "rejected"
    assert unchanged["diagnostics"] == [
        {
            "path": "$.payload",
            "message": "change at least one reviewed scientific field",
            "type": "revision_unchanged",
            "rule_id": "runtime.revision",
        }
    ]

    draft["payload"]["interpretation"] = (
        "The bounded arithmetic mean is two; this is descriptive, not causal."
    )
    output.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    revised_name = root.call_tool("run_status", {"name": "revision"})[
        "output_artifact_name"
    ]
    revised_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name=revised_name,
        )
    ).ref
    revised = json.loads(runtime.artifacts.read(revised_ref))
    assert revised["structure"] == observation.structure.model_dump(mode="json")
    assert revised["limitations"] == list(observation.limitations)
    assert revised["interpretation"].endswith("not causal.")
    base_ref = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name="base.output",
        )
    ).ref
    assert runtime.artifacts.read(base_ref) == base_content


def test_same_operation_revises_its_own_created_output(tmp_path: Path) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    base_content, observation = _create_reviewed_base(
        catalog, runtime, instance, root
    )
    request = {
        "name": "same_operation_revision",
        "operation_id": "blind.csv.observe.v1",
        "inputs": [
            {"port": "source_table", "artifact_names": ["source_csv"]},
            {"port": "prior_draft", "artifact_names": ["base.output"]},
            {"port": "change_request", "artifact_names": ["review.output"]},
        ],
        "instruction": "Revise only the exact independently reviewed wording.",
    }
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    root.call_tool("operation_invoke", request)
    worker = _worker(catalog, runtime, "blind.csv.observe.v1")
    opened = worker.call_tool("worker_open_assignment", {})
    assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
    assert assignment["revision"] == {
        "mode": "copy_on_write",
        "base_source_name": "prior_draft",
        "editable_target": "output/result.json",
        "publication": "complete_immutable_snapshot",
    }
    output = Path(opened["output_directory"], "result.json")
    draft = json.loads(output.read_text("utf-8"))
    assert draft["payload"] == observation.model_dump(mode="json")
    draft["handoff"] = {
        "verdict": "pass",
        "summary": "One bounded wording correction was applied.",
    }
    draft["payload"]["interpretation"] = (
        "The bounded arithmetic mean is two; this is descriptive only."
    )
    output.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    status = root.call_tool("run_status", {"name": "same_operation_revision"})
    revised = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name=status["output_artifact_name"],
        )
    )
    base = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name="base.output",
        )
    )
    review = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name="review.output",
        )
    )
    assert revised.ref != base.ref
    assert {base.ref, review.ref} <= set(revised.parent_refs)
    assert runtime.artifacts.read(base.ref) == base_content


def test_same_operation_revision_context_is_all_or_none(tmp_path: Path) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    _create_reviewed_base(catalog, runtime, instance, root)
    before_runs = len(
        runtime.scheduler_bindings.list(
            instance=instance.instance_id, namespace="run"
        )
    )
    for port, name in (
        ("prior_draft", "base.output"),
        ("change_request", "review.output"),
    ):
        request = {
            "name": f"half_revision_{port}",
            "operation_id": "blind.csv.observe.v1",
            "inputs": [
                {"port": "source_table", "artifact_names": ["source_csv"]},
                {"port": port, "artifact_names": [name]},
            ],
            "instruction": "This incomplete revision context must be rejected.",
        }
        result = root.call_tool("operation_preflight", request)
        assert result["admissible"] is False
        assert result["reason_code"] == "input_cohort_incomplete"
    assert len(
        runtime.scheduler_bindings.list(
            instance=instance.instance_id, namespace="run"
        )
    ) == before_runs


def test_revision_recovery_status_matches_exact_resume_preflight(tmp_path: Path) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    _create_reviewed_base(catalog, runtime, instance, root)
    _invoke_revision(root, "failed_revision")
    worker = _worker(catalog, runtime, "blind.csv.revise.v1")
    worker.call_tool("worker_open_assignment", {})
    before = root.call_tool("run_status", {"name": "failed_revision"})
    root.call_tool(
        "run_record_failure",
        {
            "name": "failed_revision",
            "reason": "bounded recovery probe",
            "expected_state": "running",
            "expected_last_activity_at": before["last_activity_at"],
        },
    )
    failed = root.call_tool("run_status", {"name": "failed_revision"})
    assert failed["state"] == "failed"
    assert failed["recovery_available"] is True
    resumed = _invoke_revision(
        root, "resumed_revision", resume_from="failed_revision"
    )
    assert resumed["result"]["state"] == "queued"
    resumed_worker = _worker(catalog, runtime, "blind.csv.revise.v1")
    resumed_worker.call_tool("worker_open_assignment", {})
    before = root.call_tool("run_status", {"name": "resumed_revision"})
    root.call_tool(
        "run_record_failure",
        {
            "name": "resumed_revision",
            "reason": "bounded recovery attempt exhausted",
            "expected_state": "running",
            "expected_last_activity_at": before["last_activity_at"],
        },
    )
    exhausted = root.call_tool("run_status", {"name": "resumed_revision"})
    assert exhausted["state"] == "failed"
    assert exhausted["recovery_available"] is False
    preflight = root.call_tool(
        "operation_preflight",
        {
            "name": "exhausted_revision",
            "operation_id": "blind.csv.revise.v1",
            "inputs": [
                {"port": "prior_draft", "artifact_names": ["base.output"]},
                {"port": "change_request", "artifact_names": ["review.output"]},
                {"port": "source_table", "artifact_names": ["source_csv"]},
            ],
            "instruction": "Apply only the exact reviewed correction.",
            "resume_from": "resumed_revision",
        },
    )
    assert preflight["admissible"] is False
    assert preflight["reason_code"] == "recovery_source_unavailable"


def test_revision_recovery_is_unavailable_after_backend_change(tmp_path: Path) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    _create_reviewed_base(catalog, runtime, instance, root)
    _invoke_revision(root, "failed_before_backend_change")
    worker = _worker(catalog, runtime, "blind.csv.revise.v1")
    worker.call_tool("worker_open_assignment", {})
    before = root.call_tool(
        "run_status", {"name": "failed_before_backend_change"}
    )
    root.call_tool(
        "run_record_failure",
        {
            "name": "failed_before_backend_change",
            "reason": "bounded backend identity probe",
            "expected_state": "running",
            "expected_last_activity_at": before["last_activity_at"],
        },
    )
    assert root.call_tool(
        "run_status", {"name": "failed_before_backend_change"}
    )["recovery_available"] is True
    runtime.runs.backend = HardenedWorkerBackend(tmp_path / "replacement-backend")
    assert root.call_tool(
        "run_status", {"name": "failed_before_backend_change"}
    )["recovery_available"] is False


def test_hardened_revision_is_rejected_without_a_controlled_read_tool(
    tmp_path: Path,
) -> None:
    catalog, runtime, instance, root = _system(tmp_path, worker_backend="hardened")
    _create_reviewed_base(catalog, runtime, instance, root)
    preflight = root.call_tool(
        "operation_preflight", _revision_request("hardened_revision")
    )
    assert preflight["admissible"] is False
    assert preflight["reason_code"] == "runtime_backend_capability_missing"
    assert HardenedWorkerBackend.unsupported_requirements(
        catalog.operation("blind.csv.revise.v1")
    ) == ("server_file_read",)


def test_materializer_without_finalizer_keeps_the_generic_revision_draft() -> None:
    from scidiscovery.operations.invoke import direct_revision_ports

    compiled = _catalog().operation("blind.csv.revise.v1")
    direct = direct_revision_ports(compiled)
    assert direct is not None
    assert _revision_workspace_mode(
        direct, {"workspace_materializer": object()}
    ) == "result_copy"
    assert _revision_workspace_mode(
        direct,
        {
            "workspace_materializer": object(),
            "workspace_finalizer": object(),
        },
    ) == "domain_workspace"


def test_every_installed_revision_uses_one_compiled_workspace_contract() -> None:
    from curve_score.plugin import PLUGIN as CURVE
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.invoke import direct_revision_ports
    from tcad_artifact.plugin import PLUGIN as TCAD

    catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD))
    revision_ids = {
        operation_id
        for operation_id in catalog.operation_ids()
        if direct_revision_ports(catalog.operation(operation_id)) is not None
    }
    assert revision_ids == {
        "science.evidence.revise-from-critic.v1",
        "science.experiment.revise.v1",
        "science.hypothesis.revise.v1",
        "science.intake.revise.v1",
        "tcad.deck.author.revise.v1",
        "tcad.deck.author.runtime-failure.v1",
    }
    for operation_id in revision_ids:
        compiled = catalog.operation(operation_id)
        assert direct_revision_ports(compiled) is not None
        assert compiled.spec.limits.max_attempts == 2


def test_revision_base_must_be_materializable_and_hardened_requires_patch_tool() -> None:
    hidden_base = REVISION.inputs[0].model_copy(update={"exposure": "handoff_only"})
    hidden_revision = REVISION.model_copy(
        update={"inputs": (hidden_base, *REVISION.inputs[1:])}
    )
    hidden_plugin = PLUGIN.model_copy(
        update={"operations": (*PLUGIN.operations, hidden_revision)}
    )
    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, hidden_plugin))
    assert caught.value.reason_code == "direct_revision_contract_invalid"

    no_patch_revision = REVISION.model_copy(
        update={
            "executor": REVISION.executor.model_copy(update={"tools": FILE_TOOLS})
        }
    )
    no_patch_plugin = PLUGIN.model_copy(
        update={"operations": (*PLUGIN.operations, no_patch_revision)}
    )
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, no_patch_plugin))
    assert HardenedWorkerBackend.unsupported_requirements(
        catalog.operation("blind.csv.revise.v1")
    ) == ("server_file_read", "server_file_patch")
