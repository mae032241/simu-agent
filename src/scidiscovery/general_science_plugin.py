"""Single installation entry point for domain-neutral scientific Operations."""

from .general_science_agent_operations import AGENT_OPERATIONS
from .general_science_components import COMPONENTS
from .general_science_control_operations import CONTROL_OPERATIONS
from .general_science_experiment_components import (
    COMPONENTS as EXPERIMENT_COMPONENTS,
)
from .general_science_experiment_operations import (
    OPERATIONS as EXPERIMENT_OPERATIONS,
)
from .operations.spec import PLUGIN_PROTOCOL_VERSION, PluginDefinition, PluginDependency


PLUGIN = PluginDefinition(
    plugin_id="general_science",
    version="0.1.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    components=COMPONENTS + EXPERIMENT_COMPONENTS,
    operations=AGENT_OPERATIONS + CONTROL_OPERATIONS + EXPERIMENT_OPERATIONS,
    dependencies=(PluginDependency(plugin_id="builtin", version="0.1.0"),),
)


__all__ = ["PLUGIN"]
