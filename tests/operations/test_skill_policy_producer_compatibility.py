from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_score.curve_contract_compiler import (
    CurveContractCompileInput,
    compile_curve_contract,
)
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import (
    RootOperationRoutes,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_experiment_components import (
    EXPERIMENT_DESIGN_PROMPT,
    EXPERIMENT_PROMPT,
    ExperimentResources,
)
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operation_declaration import OPERATION_AGENT_PREAMBLE
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import InvocationArtifact, OperationInvocationError
from scidiscovery.operations.spec import ComponentRef
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.execution_control import SolverCapabilitySnapshot
from tests.operations.test_m2_curve_analysis_boundary import (
    _bundle,
    _compiler_objective,
    _compiler_plan,
    _plan,
)


HISTORICAL_SOURCE = "2edac5d317a74056869a567bd0daa7f556ecbc85"


def _catalog(*, general=GENERAL_PLUGIN, tcad=TCAD_PLUGIN, figure=False):
    plugins = (CORE_PLUGIN, general, CURVE_PLUGIN, tcad)
    return compile_catalog((*plugins, FIGURE_PLUGIN) if figure else plugins)


def _legacy_design_plugin():
    operations = []
    for operation in GENERAL_PLUGIN.operations:
        if operation.operation_id != "science.experiment.design.v1":
            operations.append(operation)
            continue
        operations.append(
            operation.model_copy(
                update={
                    "executor": operation.executor.model_copy(
                        update={"prompt": ComponentRef("experiment_prompt")}
                    ),
                    "inputs": tuple(
                        port
                        for port in operation.inputs
                        if port.name != "execution_context"
                    ),
                    "outputs": tuple(
                        port.model_copy(
                            update={
                                "context_sources": tuple(
                                    name
                                    for name in port.context_sources
                                    if name != "execution_context"
                                )
                            }
                        )
                        for port in operation.outputs
                    ),
                }
            )
        )
    components = tuple(
        component
        for component in GENERAL_PLUGIN.components
        if component.component_id != "experiment_design_prompt"
    )
    return GENERAL_PLUGIN.model_copy(
        update={"components": components, "operations": tuple(operations)}
    )


def _historical_operation_digests(tmp_path: Path) -> dict[str, str]:
    """Compile exact operation identities from the documented source commit."""

    repository = Path(__file__).resolve().parents[2]
    archive = subprocess.check_output(
        ("git", "archive", HISTORICAL_SOURCE), cwd=repository
    )
    source_root = tmp_path / "historical-source"
    source_root.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        bundle.extractall(source_root, filter="data")
    program = """
import json
from curve_score.plugin import PLUGIN as curve
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as general
from scidiscovery.operations.catalog import compile_catalog
from tcad_artifact.plugin import PLUGIN as tcad

catalog = compile_catalog((CORE_PLUGIN, general, curve, tcad))
names = (
    "science.experiment.revise.v1",
    "science.curve.contract.design.v1",
    "tcad.deck.author.initial.v1",
    "tcad.deck.review.v1",
)
print(json.dumps({name: catalog.operation(name).digest for name in names}, sort_keys=True))
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        str(source_root / path)
        for path in ("src", "plugins/curve_score", "plugins/tcad_artifact")
    )
    completed = subprocess.run(
        (sys.executable, "-c", program),
        cwd=source_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def _produced_plan(catalog, *, digest_catalog=None):
    operation = (digest_catalog or catalog).operation("science.experiment.revise.v1")
    port = operation.spec.outputs[0]
    ref = ArtifactRef(
        artifact_id="art_stable_experiment_plan",
        sha256="a" * 64,
        kind=port.kind,
        schema_id=port.schema_id,
    )
    artifact = InvocationArtifact(
        artifact_name="stable_experiment_plan",
        ref=ref,
        schema_id=port.schema_id,
        media_type=port.media_types[0],
        size_bytes=16,
    )
    envelope = SimpleNamespace(
        labels={
            "operation_id": operation.spec.operation_id,
            "operation_version": operation.spec.version,
            "operation_digest": operation.digest,
            "operation_output_port": port.name,
        }
    )
    routes = object.__new__(RootOperationRoutes)
    routes._operation_catalog = catalog
    routes.artifacts = SimpleNamespace(catalog=lambda _ref: envelope)
    bound = SimpleNamespace(
        compiled=catalog.operation("science.object.review.v1"),
        inputs=(
            SimpleNamespace(
                port_name="experiment_plan",
                usage="prior_signal",
                artifact=artifact,
            ),
        ),
    )
    return routes, bound


def _register_bound(
    runtime,
    instance,
    *,
    name: str,
    content: bytes,
    kind: str,
    schema_id: str,
    parents: tuple[ArtifactRef, ...] = (),
    labels: dict[str, str] | None = None,
):
    envelope = runtime.artifacts.register(
        content,
        ArtifactRegistration(
            kind=kind,
            schema_id=schema_id,
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
            parent_refs=parents,
            labels=labels or {},
        ),
        idempotency_key=f"producer-compatibility:{name}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=name,
        object_id=envelope.artifact_id,
    )
    return envelope


def _complete_scientific_review(
    runtime,
    root: RootMCPRouter,
    catalog,
    *,
    name: str,
    operation_id: str,
    inputs: tuple[tuple[str, str], ...],
    review_target: str,
) -> str:
    request = {
        "name": name,
        "operation_id": operation_id,
        "inputs": [
            {"port": port, "artifact_names": [artifact_name]}
            for port, artifact_name in inputs
        ],
        "instruction": "Review only the exact immutable subject.",
    }
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    operation = catalog.operation(operation_id)
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=operation.spec.operation_id,
        operation_digest=operation.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        canonical_json(
            {
                "schema_version": 1,
                "handoff": {
                    "verdict": "pass",
                    "summary": "The exact bounded subject passed review.",
                },
                "payload": {
                    "review_target": review_target,
                    "verdict": "pass",
                    "summary": "The exact bounded subject is internally consistent.",
                },
            }
        )
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
    return root.call_tool("run_status", {"name": name})["output_artifact_name"]


def test_design_and_revision_prompt_digest_isolation(monkeypatch) -> None:
    assert "current_objectives" in EXPERIMENT_PROMPT
    assert ExperimentResources.experiment_prompt == OPERATION_AGENT_PREAMBLE + EXPERIMENT_PROMPT
    assert "execution_context" not in EXPERIMENT_PROMPT
    assert "execution_context" in EXPERIMENT_DESIGN_PROMPT

    stable = _catalog()
    original_design = ExperimentResources.experiment_design_prompt
    monkeypatch.setattr(
        ExperimentResources,
        "experiment_design_prompt",
        original_design + "Design-only compatibility negative control.\n",
    )
    design_changed = _catalog()
    assert (
        design_changed.operation("science.experiment.design.v1").digest
        != stable.operation("science.experiment.design.v1").digest
    )
    assert (
        design_changed.operation("science.experiment.revise.v1").digest
        == stable.operation("science.experiment.revise.v1").digest
    )

    monkeypatch.setattr(ExperimentResources, "experiment_design_prompt", original_design)
    monkeypatch.setattr(
        ExperimentResources,
        "experiment_prompt",
        ExperimentResources.experiment_prompt
        + "Shared-prompt compatibility negative control.\n",
    )
    polluted = _catalog()
    assert (
        polluted.operation("science.experiment.revise.v1").digest
        != stable.operation("science.experiment.revise.v1").digest
    )

    routes, bound = _produced_plan(stable)
    routes._validate_producer_output_admission(bound)
    stale_routes, stale_bound = _produced_plan(stable, digest_catalog=polluted)
    stale_routes._validate_producer_output_admission(stale_bound)


def test_design_prompt_binding_isolation_under_the_current_contract() -> None:
    # This rewires only design within the current ABI; it is not an old catalog.
    rewired = _catalog(general=_legacy_design_plugin())
    repaired = _catalog()
    assert rewired.operation_ids() == repaired.operation_ids()
    changed = {
        operation_id
        for operation_id in repaired.operation_ids()
        if rewired.operation(operation_id).digest
        != repaired.operation(operation_id).digest
    }
    assert changed == {"science.experiment.design.v1"}
    assert (
        rewired.operation("science.experiment.revise.v1").digest
        == repaired.operation("science.experiment.revise.v1").digest
    )


def test_current_science_reaches_author_while_historical_contracts_retire(
    tmp_path,
) -> None:
    historical = _historical_operation_digests(tmp_path)
    repaired = _catalog()
    # The goal contract and Operation ABI intentionally retire old qualification.
    # Derive old identities from untouched archived source, not replacement hashes.
    assert all(
        digest != repaired.operation(operation_id).digest
        for operation_id, digest in historical.items()
    )

    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="local",
        local_workspace_root=project / ".scidiscovery-runs",
        approval_receipt_secret=os.urandom(32),
    )
    runtime.runs.operation_catalog = repaired
    instance = runtime.scheduler_bindings.create_instance(
        name="historical_contract_boundary",
        title="Historical contract boundary",
        objective="Accept current science and reject retired producer contracts.",
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
            operation_catalog=repaired,
        )
    )

    plan = _compiler_plan()
    objective = _compiler_objective()
    bundle = _bundle()
    contract = compile_curve_contract(
        CurveContractCompileInput.model_validate(
            {
                "experiment_key": "implementation_check",
                "target_bindings": [
                    {
                        "target_key": "target_implementation",
                        "reference_series_key": "reference",
                        "validation_check_keys": ["profile_rms"],
                    }
                ],
                "candidate_case_keys": ["baseline"],
                "comparison_metric": "residual_rms",
            }
        ),
        objective=objective,
        portfolio=plan,
        reference_bundle=bundle,
    )
    plan_producer = repaired.operation("science.experiment.revise.v1")
    curve_producer = repaired.operation("science.curve.contract.design.v1")
    retired_plan = _register_bound(
        runtime,
        instance,
        name="retired_plan",
        content=plan.canonical_json(),
        kind=plan_producer.spec.outputs[0].kind,
        schema_id=plan_producer.spec.outputs[0].schema_id,
        labels={
            "operation_id": plan_producer.spec.operation_id,
            "operation_version": plan_producer.spec.version,
            "operation_digest": historical["science.experiment.revise.v1"],
            "operation_output_port": plan_producer.spec.outputs[0].name,
        },
    )
    # A separate current fixture must obtain its own independent review.
    # The retired fixture and its producer labels remain unchanged.
    plan_artifact = _register_bound(
        runtime,
        instance,
        name="current_plan",
        content=plan.canonical_json(),
        kind=plan_producer.spec.outputs[0].kind,
        schema_id=plan_producer.spec.outputs[0].schema_id,
        labels={
            "operation_id": plan_producer.spec.operation_id,
            "operation_version": plan_producer.spec.version,
            "operation_digest": plan_producer.digest,
            "operation_output_port": plan_producer.spec.outputs[0].name,
        },
    )
    retired_review_request = {
        "name": "review_retired_plan", "operation_id": "science.object.review.v1",
        "inputs": [{"port": "experiment_plan", "artifact_names": ["retired_plan"]}],
        "instruction": "Review only the exact immutable subject.",
    }
    before_retired_review = root.call_tool("run_list", {})["runs"]
    accepted = root.call_tool("operation_preflight", retired_review_request)
    assert accepted["admissible"] is True
    assert root.call_tool("run_list", {})["runs"] == before_retired_review

    _register_bound(
        runtime,
        instance,
        name="research_objective",
        content=objective.canonical_json(),
        kind="research_objective",
        schema_id="scidiscovery.research-objective.v1",
    )
    _register_bound(
        runtime,
        instance,
        name="reference_bundle",
        content=bundle.canonical_json(),
        kind="curve_bundle",
        schema_id="scidiscovery.curve-bundle.v1",
    )
    curve_artifact = _register_bound(
        runtime,
        instance,
        name="current_curve_contract",
        content=contract.canonical_json(),
        kind=curve_producer.spec.outputs[0].kind,
        schema_id=curve_producer.spec.outputs[0].schema_id,
        labels={
            "operation_id": curve_producer.spec.operation_id,
            "operation_version": curve_producer.spec.version,
            "operation_digest": curve_producer.digest,
            "operation_output_port": curve_producer.spec.outputs[0].name,
        },
    )
    snapshot = SolverCapabilitySnapshot(
        profile_id="compatibility_sprocess",
        solver_kind="sprocess",
        launch_name="sprocess",
        public_arguments=("-i",),
        public_release_label="R-2020.09",
        private_fixed_argument_count=0,
        private_fixed_arguments_sha256="a" * 64,
        private_release_evidence_bytes=1,
        private_release_evidence_sha256="b" * 64,
        capability_sha256="c" * 64,
    )
    _register_bound(
        runtime,
        instance,
        name="execution_capability",
        content=json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
        kind="solver_capability",
        schema_id="tcad.solver-capability.v2",
    )

    experiment_review = _complete_scientific_review(
        runtime,
        root,
        repaired,
        name="current_plan_review",
        operation_id="science.object.review.v1",
        inputs=(("experiment_plan", "current_plan"),),
        review_target="experiment_portfolio",
    )
    curve_review = _complete_scientific_review(
        runtime,
        root,
        repaired,
        name="current_curve_contract_review",
        operation_id="science.curve.contract.review.v1",
        inputs=(
            ("research_objective", "research_objective"),
            ("experiment_plan", "current_plan"),
            ("experiment_review", experiment_review),
            ("curve_contract", "current_curve_contract"),
            ("reference_bundle", "reference_bundle"),
        ),
        review_target="domain_contract",
    )
    author_inputs = [
        {"port": "execution_capability", "artifact_names": ["execution_capability"]},
        {"port": "experiment_plan", "artifact_names": ["current_plan"]},
        {"port": "experiment_review", "artifact_names": [experiment_review]},
        {"port": "curve_contract", "artifact_names": ["current_curve_contract"]},
        {"port": "curve_contract_review", "artifact_names": [curve_review]},
    ]
    before = root.call_tool("run_list", {})["runs"]
    accepted = root.call_tool(
        "operation_preflight",
        {
            "name": "current_author_accepts_current_science",
            "operation_id": "tcad.deck.author.initial.v1",
            "inputs": author_inputs,
            "instruction": "Author only the exact bounded project.",
        },
    )
    assert accepted["admissible"] is True, accepted
    retired_author_inputs = [
        {**item, "artifact_names": ["retired_plan"]}
        if item["port"] == "experiment_plan" else item
        for item in author_inputs
    ]
    rejected = root.call_tool("operation_preflight", {
        "name": "current_author_rejects_retired_plan",
        "operation_id": "tcad.deck.author.initial.v1",
        "inputs": retired_author_inputs,
        "instruction": "Author only the exact bounded project.",
    })
    assert rejected["admissible"] is False
    assert rejected["reason_code"] == "input_independent_review_missing"
    assert runtime.artifacts.read(retired_plan.ref) == plan.canonical_json()
    assert runtime.artifacts.catalog(retired_plan.ref).labels["operation_digest"] == historical[
        "science.experiment.revise.v1"
    ]
    assert root.call_tool("run_list", {})["runs"] == before
    admission = repaired.operation("tcad.deck.author.initial.v1").spec.input_admission
    assert admission is not None
    assert not {item["port"] for item in author_inputs} & set(admission.member_ports)

    author = repaired.operation("tcad.deck.author.initial.v1")
    old_project = _register_bound(
        runtime,
        instance,
        name="pre_p2_project",
        content=b"{}",
        kind=author.spec.outputs[0].kind,
        schema_id=author.spec.outputs[0].schema_id,
        parents=(plan_artifact.ref, curve_artifact.ref),
        labels={
            "operation_id": author.spec.operation_id,
            "operation_version": author.spec.version,
            "operation_digest": historical["tcad.deck.author.initial.v1"],
            "operation_output_port": author.spec.outputs[0].name,
        },
    )
    old_review_operation = repaired.operation("tcad.deck.review.v1")
    review_subject = _register_bound(
        runtime,
        instance,
        name="review_contract_subject",
        content=b"{}",
        kind=author.spec.outputs[0].kind,
        schema_id=author.spec.outputs[0].schema_id,
    )
    _register_bound(
        runtime,
        instance,
        name="current_review_fixture",
        content=b"{}",
        kind=old_review_operation.spec.outputs[0].kind,
        schema_id=old_review_operation.spec.outputs[0].schema_id,
        parents=(review_subject.ref,),
        labels={
            "operation_id": old_review_operation.spec.operation_id,
            "operation_version": old_review_operation.spec.version,
            "operation_digest": old_review_operation.digest,
            "operation_output_port": old_review_operation.spec.outputs[0].name,
        },
    )
    _register_bound(
        runtime,
        instance,
        name="pre_p2_review",
        content=b"{}",
        kind=old_review_operation.spec.outputs[0].kind,
        schema_id=old_review_operation.spec.outputs[0].schema_id,
        parents=(review_subject.ref,),
        labels={
            "operation_id": old_review_operation.spec.operation_id,
            "operation_version": old_review_operation.spec.version,
            "operation_digest": historical["tcad.deck.review.v1"],
            "operation_output_port": old_review_operation.spec.outputs[0].name,
        },
    )
    rejected_review = root.call_tool(
        "operation_preflight",
        {
            "name": "review_pre_p2_project",
            "operation_id": "tcad.deck.review.v1",
            "inputs": [
                {"port": "project", "artifact_names": ["pre_p2_project"]},
                *author_inputs,
            ],
            "instruction": "Review only the exact bounded project.",
        },
    )
    assert rejected_review["admissible"] is False
    assert rejected_review["reason_code"] == "input_content_incompatible"
    assert rejected_review["port"] == "project"
    accepted_review_contract = root.call_tool(
        "operation_preflight",
        {
            "name": "validate_current_review_contract",
            "operation_id": "tcad.deck-review-validate.v1",
            "inputs": [
                {"port": "project", "artifact_names": ["review_contract_subject"]},
                {"port": "review", "artifact_names": ["current_review_fixture"]},
            ],
        },
    )
    assert accepted_review_contract["admissible"] is True, accepted_review_contract
    rejected_review_contract = root.call_tool(
        "operation_preflight",
        {
            "name": "validate_pre_p2_review_contract",
            "operation_id": "tcad.deck-review-validate.v1",
            "inputs": [
                {"port": "project", "artifact_names": ["review_contract_subject"]},
                {"port": "review", "artifact_names": ["pre_p2_review"]},
            ],
        },
    )
    assert rejected_review_contract["admissible"] is False
    assert rejected_review_contract["reason_code"] == "input_content_incompatible"
    assert rejected_review_contract["port"] == "review"
    assert root.call_tool("run_list", {})["runs"] == before


def test_root_review_preflight_accepts_historical_producer_after_prompt_change(
    tmp_path, monkeypatch
) -> None:
    stable = _catalog()
    producer = stable.operation("science.experiment.revise.v1")
    port = producer.spec.outputs[0]
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        worker_backend="local",
        local_workspace_root=project / ".scidiscovery-runs",
        approval_receipt_secret=os.urandom(32),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="producer_compatibility",
        title="Producer compatibility",
        objective="Test one exact compiled producer contract.",
    )
    envelope = runtime.artifacts.register(
        canonical_json(_plan()),
        ArtifactRegistration(
            kind=port.kind,
            schema_id=port.schema_id,
            payload_schema_version=port.payload_schema_version,
            media_type=port.media_types[0],
            creator=runtime.actor,
            labels={
                "operation_id": producer.spec.operation_id,
                "operation_version": producer.spec.version,
                "operation_digest": producer.digest,
                "operation_output_port": port.name,
            },
        ),
        idempotency_key="producer-compatibility:stable",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="stable_experiment_plan",
        object_id=envelope.artifact_id,
    )

    def root(catalog):
        assert runtime.runs is not None
        runtime.runs.operation_catalog = catalog
        return RootMCPRouter(
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

    request = {
        "name": "review_stable_plan",
        "operation_id": "science.object.review.v1",
        "inputs": [
            {
                "port": "experiment_plan",
                "artifact_names": ["stable_experiment_plan"],
            }
        ],
        "instruction": "Review the exact bounded experiment plan.",
    }
    assert root(stable).call_tool("operation_preflight", request)[
        "admissible"
    ] is True

    monkeypatch.setattr(
        ExperimentResources,
        "experiment_prompt",
        ExperimentResources.experiment_prompt
        + "Shared-prompt compatibility negative control.\n",
    )
    polluted = _catalog()
    accepted = root(polluted).call_tool("operation_preflight", request)
    assert accepted["admissible"] is True
    assert root(polluted).call_tool("operation_invoke", request)["result"]["state"] == "queued"
