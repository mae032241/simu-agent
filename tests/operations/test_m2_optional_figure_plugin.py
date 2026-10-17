from __future__ import annotations


import pytest

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import direct_revision_ports
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
