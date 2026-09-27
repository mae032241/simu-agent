"""Minimal built-in plugin for shared Worker tools."""

from .operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ComponentSpec,
    PluginDefinition,
)


CORE_PLUGIN = PluginDefinition(
    plugin_id="builtin",
    version="0.1.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    components=(ComponentSpec("reference_read_tool", "worker_tool",
        "scidiscovery.reference_tools:REFERENCE_READ_TOOL", public=True),
        ComponentSpec("helper_tool", "worker_tool",
        "scidiscovery.helper_tool:HELPER_TOOL", public=True),
        ComponentSpec("materialize_input_tool", "worker_tool", "scidiscovery.attachment_tools:INPUT_TOOL", public=True),
        ComponentSpec("publish_files_tool", "worker_tool",
        "scidiscovery.attachment_tools:PUBLISH_FILES_TOOL", public=True)),
    operations=(),
)


__all__ = ["CORE_PLUGIN"]
