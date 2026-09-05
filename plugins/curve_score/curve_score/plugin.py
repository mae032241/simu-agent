"""Single compiled plugin declaration for deterministic curve capabilities."""

from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    PluginDefinition,
    PluginDependency,
)

from .operation_transforms import COMPONENT_SPECS, OPERATIONS
from .science_operations import (
    COMPONENT_SPECS as SCIENCE_COMPONENT_SPECS,
    OPERATIONS as SCIENCE_OPERATIONS,
)


PLUGIN = PluginDefinition(
    plugin_id="curve_score",
    version="0.2.1",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
    ),
    components=COMPONENT_SPECS + SCIENCE_COMPONENT_SPECS,
    operations=OPERATIONS + SCIENCE_OPERATIONS,
)


__all__ = ["PLUGIN"]
