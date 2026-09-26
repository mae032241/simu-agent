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
    "science.result.diagnose.v1",
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
