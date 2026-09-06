"""Single registration entry for optional paper-figure evidence Operations."""

from .figure_science_operations import (
    COMPONENT_SPECS as FIGURE_AGENT_COMPONENT_SPECS,
    OPERATIONS as FIGURE_AGENT_OPERATIONS,
)
from .operation_transforms import (
    FIGURE_COMPONENT_SPECS as FIGURE_NORMALIZATION_COMPONENT_SPECS,
    FIGURE_OPERATIONS as FIGURE_NORMALIZATION_OPERATIONS,
)
from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ComponentRef,
    ComponentSpec,
    PluginDefinition,
    PluginDependency,
)


SHARED_IMPLEMENTATION_COMPONENTS = (
    ComponentSpec(
        "figure_semantic_contract",
        "resource",
        "curve_figure_evidence.figure_science_operations:FIGURE_SEMANTIC_CONTRACT",
    ),
    ComponentSpec(
        "nonempty_validator",
        "validator",
        "curve_score.science_operations:_NONEMPTY_COMPONENT",
        resources=(ComponentRef("figure_semantic_contract"),),
    ),
)


PLUGIN = PluginDefinition(
    plugin_id="curve_figure_evidence",
    version="0.1.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
        PluginDependency("curve_score", "0.2.1"),
    ),
    components=(
        SHARED_IMPLEMENTATION_COMPONENTS
        + FIGURE_NORMALIZATION_COMPONENT_SPECS
        + FIGURE_AGENT_COMPONENT_SPECS
    ),
    operations=FIGURE_NORMALIZATION_OPERATIONS + FIGURE_AGENT_OPERATIONS,
)


__all__ = ["PLUGIN"]
