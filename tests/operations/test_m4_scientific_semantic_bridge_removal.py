from __future__ import annotations

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


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
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, FIGURE_PLUGIN)
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
        )
        for component in plugin.components
    )
