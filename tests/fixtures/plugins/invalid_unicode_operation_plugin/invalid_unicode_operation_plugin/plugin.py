from scidiscovery.operations import ComponentSpec, PluginDefinition


PLUGIN = PluginDefinition(
    plugin_id="invalid_unicode",
    version="0.0.1",
    protocol_version="1",
    components=(
        ComponentSpec(
            component_id="invalid_resource",
            kind="resource",
            implementation="invalid_unicode_operation_plugin.runtime:INVALID_RESOURCE",
        ),
    ),
    operations=(),
)
