from __future__ import annotations

import os

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
    "scidiscovery.curve-bundle.figure-evidence.v2",
    "science.figure.request.prepare.v1",
    "science.figure.evidence.materialize.v1",
    "science.evidence.extract.figure.v2",
    "science.figure.evidence.audit.v1",
}


def test_default_tcad_catalog_has_no_paper_figure_operations() -> None:
    catalog = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )

    assert not FIGURE_OPERATIONS.intersection(catalog.operation_ids())


def test_optional_plugin_adds_the_complete_figure_vertical_slice() -> None:
    default = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN))
    optional = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN)
    )

    assert set(optional.operation_ids()) - set(default.operation_ids()) == (
        FIGURE_OPERATIONS
    )
    assert {
        optional.operation(operation_id).plugin_id
        for operation_id in FIGURE_OPERATIONS
    } == {"curve_figure_evidence"}
    assert "science.evidence.extract.figure.v1" not in optional.operation_ids()
    request = optional.operation("science.figure.request.prepare.v1")
    assert request.spec.outputs[0].schema_id == (
        "scidiscovery.figure-extraction-intent.v1"
    )
    assert {
        item.name for item in operation_worker_tools(request)
    } >= {"worker_curve_figure_inspect_source", "worker_extract_pdf_text"}

    extraction = optional.operation("science.evidence.extract.figure.v2")
    assert len(extraction.spec.outputs) == 1
    intake_output = extraction.spec.outputs[0]
    assert intake_output.context_validator is not None
    assert intake_output.context_validator.component_id == "intake_source_context"
    assert intake_output.context_rule_id == "intake.source_binding"
    assert intake_output.context_sources == (
        "paper_source",
        "figure_request",
        "figure_manifest",
        "validation_report",
        "source_panels",
        "audit_overlays",
        "curve_tables",
    )
    assert extraction.spec.review is not None
    assert extraction.spec.review.reviewer_operation == (
        "science.figure.evidence.audit.v1"
    )
    assert extraction.spec.review.subject_outputs == ("scientific_intake",)
    assert extraction.spec.review.max_revisions == 2
    assert extraction.spec.review.progress_fingerprint is not None
    assert {
        port.name: (port.min_items, port.max_items, port.usage)
        for port in extraction.spec.inputs
        if port.usage in {"revision_base", "change_request"}
    } == {
        "prior_draft": (0, 1, "revision_base"),
        "change_request": (0, 1, "change_request"),
    }
    assert extraction.spec.input_admission is not None
    assert extraction.spec.input_admission.member_ports == (
        "prior_draft",
        "change_request",
    )
    direct = direct_revision_ports(extraction)
    assert direct is not None
    assert active_direct_revision_ports(
        extraction, (port.name for port in extraction.spec.inputs[:-2])
    ) is None
    assert active_direct_revision_ports(
        extraction, (port.name for port in extraction.spec.inputs)
    ) == direct
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
        "science.figure.request.prepare.v1",
        "science.evidence.extract.figure.v2",
        "science.figure.evidence.audit.v1",
    }
    support_ids = {
        item["operation_id"]
        for item in root.operation_catalog(scope="support")["operations"]
    }
    assert support_ids >= {
        "science.figure.evidence.materialize.v1",
        "scidiscovery.curve-bundle.figure-evidence.v2",
    }
    all_items = {
        item["operation_id"]: item
        for item in root.operation_catalog(scope="all")["operations"]
    }
    assert "science.evidence.extract.figure.v1" not in all_items
    assert all_items["science.evidence.extract.figure.v2"][
        "complete_transform_family"
    ] == {
        "output_ports": [
            "figure_manifest",
            "validation_report",
            "source_panels",
            "audit_overlays",
            "curve_tables",
        ],
        "input_ports": ["paper_source", "figure_request"],
    }
    assert all(
        all_items[operation_id].get("runtime_binding", {}).get(
            "status", "available"
        )
        == "available"
        for operation_id in FIGURE_OPERATIONS
    )
