from __future__ import annotations

from pathlib import Path

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from ingaas_fig4.plugin import PLUGIN as INGAAS_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.artifact_agent.schema.validation import ValidationReport
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


REPOSITORY = Path(__file__).resolve().parents[2]
REMOVED_OPERATIONS = {
    "science.knowledge.update.diagnosis.v1",
    "science.knowledge.update.validation.v1",
}
REMOVED_SCHEMAS = {
    "scidiscovery.knowledge-update.v1",
    "scidiscovery.knowledge-state-projection.v1",
}
REMOVED_COMPONENTS = {
    "curve_knowledge_update",
    "knowledge_update",
    "knowledge_update_schema",
    "knowledge_update_validator",
    "knowledge_state_schema",
    "knowledge_state_validator",
}


def _catalog():
    return compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, INGAAS_PLUGIN)
    )


def test_unconsumed_scientific_state_reducer_is_absent_from_the_catalog() -> None:
    catalog = _catalog()
    assert REMOVED_OPERATIONS.isdisjoint(catalog.operation_ids())
    for operation_id in catalog.operation_ids():
        operation = catalog.operation(operation_id).spec
        assert REMOVED_SCHEMAS.isdisjoint(
            port.schema_id for port in (*operation.inputs, *operation.outputs)
        )
    assert REMOVED_COMPONENTS.isdisjoint(
        component.component_id
        for plugin in (
            CORE_PLUGIN,
            GENERAL_PLUGIN,
            CURVE_PLUGIN,
            TCAD_PLUGIN,
            INGAAS_PLUGIN,
        )
        for component in plugin.components
    )


def test_no_parallel_scientific_state_model_or_default_promotion_bridge_remains() -> None:
    schema_root = REPOSITORY / "src/scidiscovery/artifact_agent/schema"
    assert not (schema_root / "knowledge.py").exists()
    assert not (schema_root / "hypothesis.py").exists()
    transform_source = (
        REPOSITORY / "src/scidiscovery/artifact_agent/transforms.py"
    ).read_text(encoding="utf-8")
    for text in (
        "_knowledge_portfolio_view",
        '"status": "testable"',
        '"support_level": "unassessed"',
        '"parameters": []',
    ):
        assert text not in transform_source
    assert "knowledge_update_applicability" not in ValidationReport.model_fields


def test_diagnosis_artifacts_and_mechanical_experiment_materialization_remain() -> None:
    catalog = _catalog()
    assert {
        "science.result.diagnose.v1",
        "science.result.diagnose.curve-error.v1",
        "science.experiment.materialize.v1",
    }.issubset(catalog.operation_ids())
    materialize = catalog.operation("science.experiment.materialize.v1").spec
    assert materialize.executor.kind == "transform"
    assert [port.schema_id for port in materialize.outputs] == [
        "scidiscovery.experiment-portfolio.v1",
        "scidiscovery.experiment-plan-materialization.v1",
    ]
