"""Minimal built-in plugin for the Worker file lifecycle."""

from .operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ComponentSpec,
    PluginDefinition,
)


CORE_PLUGIN = PluginDefinition(
    plugin_id="builtin",
    version="0.1.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    components=tuple(
        ComponentSpec(
            component_id,
            "worker_tool",
            "scidiscovery.artifact_agent.interfaces.mcp_worker_protocol:"
            + implementation,
            public=True,
        )
        for component_id, implementation in (
            ("file_write_begin_tool", "FILE_WRITE_BEGIN_TOOL"),
            ("file_write_chunk_tool", "FILE_WRITE_CHUNK_TOOL"),
            ("file_write_commit_tool", "FILE_WRITE_COMMIT_TOOL"),
            ("file_apply_patch_tool", "FILE_APPLY_PATCH_TOOL"),
            ("file_json_patch_tool", "FILE_JSON_PATCH_TOOL"),
            ("file_delete_tool", "FILE_DELETE_TOOL"),
            ("file_move_tool", "FILE_MOVE_TOOL"),
        )
    ) + (ComponentSpec("reference_read_tool", "worker_tool",
        "scidiscovery.reference_tools:REFERENCE_READ_TOOL", public=True),
        ComponentSpec("helper_tool", "worker_tool",
        "scidiscovery.helper_tool:HELPER_TOOL", public=True),
        ComponentSpec("materialize_input_tool", "worker_tool", "scidiscovery.attachment_tools:INPUT_TOOL", public=True),
        ComponentSpec("publish_files_tool", "worker_tool",
        "scidiscovery.attachment_tools:PUBLISH_FILES_TOOL", public=True)),
    operations=(),
)


__all__ = ["CORE_PLUGIN"]
