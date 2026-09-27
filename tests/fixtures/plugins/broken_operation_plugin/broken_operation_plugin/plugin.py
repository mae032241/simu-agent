from scidiscovery.operations import ComponentSpec, PluginDefinition


PLUGIN = PluginDefinition(
    plugin_id="broken",
    version="0.0.1",
    protocol_version="1",
    components=(
        ComponentSpec(
            component_id="broken_transform",
            kind="transform",
            implementation="broken_operation_plugin.runtime:TRANSFORM",
        ),
    ),
    operations=(),
)
