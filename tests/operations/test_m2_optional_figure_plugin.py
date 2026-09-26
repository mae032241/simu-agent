from __future__ import annotations

import os

import pytest

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    active_direct_revision_ports,
    direct_revision_ports,
)
from scidiscovery.operations.tooling import operation_worker_tools
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


FIGURE_OPERATIONS = {
    "scidiscovery.curve-bundle.figure-evidence.v3",
    "science.evidence.extract.figure.v3",
    "science.figure.evidence.audit.v2",
}


@pytest.mark.parametrize("extra_plugins", ((), (TCAD_PLUGIN,)))
def test_optional_plugin_adds_the_complete_figure_vertical_slice(extra_plugins) -> None:
    plugins = (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, *extra_plugins)
    default = compile_catalog(plugins)
    optional = compile_catalog((*plugins, FIGURE_PLUGIN))

    assert set(optional.operation_ids()) - set(default.operation_ids()) == (
        FIGURE_OPERATIONS
    )
    assert {
        optional.operation(operation_id).plugin_id
        for operation_id in FIGURE_OPERATIONS
    } == {"curve_figure_evidence"}
    assert "science.evidence.extract.figure.v1" not in optional.operation_ids()
    extraction = optional.operation("science.evidence.extract.figure.v3")
    primary_outputs = tuple(port for port in extraction.spec.outputs if port.collection is None)
    assert len(primary_outputs) == 1
    intake_output = primary_outputs[0]
    assert intake_output.validator.component_id == "figure_intake_validator"
    assert intake_output.semantic_contract.component_id == "figure_semantic_contract"
    assert intake_output.context_validator is not None
    assert intake_output.context_validator.component_id == "figure_intake_context"
    assert intake_output.context_rule_id == "curve.figure.evidence_binding"
    assert intake_output.context_sources == ("paper_source", "tool_evidence", "figure_provenance", "figure_family", "user_context")
    assert {item.name for item in operation_worker_tools(extraction)} >= {
        "worker_curve_figure_inspect_source", "worker_curve_figure_preview", "worker_curve_figure_save", "worker_curve_figure_reuse", "worker_extract_pdf_text"}
    assert optional.operation("science.figure.evidence.audit.v2").spec.input_validation is not None
    assert extraction.spec.review is not None
    assert extraction.spec.review.reviewer_operation == (
        "science.figure.evidence.audit.v2"
    )
    assert extraction.spec.review.subject_outputs == ("scientific_intake",)
    assert extraction.spec.review.max_revisions == 0
    assert extraction.spec.review.progress_fingerprint is None
    assert extraction.spec.input_admission is None
    assert direct_revision_ports(extraction) is None
    assert "science.intake.revise.figure.v1" not in optional.operation_ids()
    assert all(
        LocalTrustedBackend.unsupported_requirements(optional.operation(operation_id))
        == ()
        for operation_id in FIGURE_OPERATIONS
    )


def test_public_and_support_views_expose_one_runnable_figure_topology(
    tmp_path,
) -> None:
    catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN)
    )
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="optional_figure",
        title="Optional figure capability",
        objective="Verify the scheduler and diagnostic catalog projections.",
    )
    root = RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )

    public_ids = {
        item["operation_id"]
        for item in root.operation_catalog(scope="public")["operations"]
    }
    assert public_ids >= {
        "science.evidence.extract.figure.v3",
        "science.figure.evidence.audit.v2",
    }
    support_ids = {
        item["operation_id"]
        for item in root.operation_catalog(scope="support")["operations"]
    }
    assert support_ids >= {
        "scidiscovery.curve-bundle.figure-evidence.v3",
    }
    all_items = {
        item["operation_id"]: item
        for item in root.operation_catalog(scope="all")["operations"]
    }
    assert "science.evidence.extract.figure.v1" not in all_items
    assert all_items["science.evidence.extract.figure.v3"].get("complete_transform_family") is None
    assert "science.figure.request.prepare.v1" not in all_items
    assert "science.figure.evidence.materialize.v1" not in all_items
    assert all(
        all_items[operation_id].get("runtime_binding", {}).get(
            "status", "available"
        )
        == "available"
        for operation_id in FIGURE_OPERATIONS
    )
