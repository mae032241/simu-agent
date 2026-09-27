"""Assemble registered Worker services for both gateway and standalone hosts."""
from ..operations.tooling import operation_local_worker_tools
from .runtime_plugin_bindings import load_runtime_plugin_contributions


def load_operation_services(catalog, operation_id, assignments, state_root):
    tools = operation_local_worker_tools(catalog.operation(operation_id))
    required = {name.partition(':')[0] for tool in tools for name in tool.required_services}
    optional = {name.partition(':')[0] for tool in tools for name in tool.optional_services}
    services = {}
    for plugin_id, path in assignments.items():
        if plugin_id not in required | optional:
            continue
        try:
            loaded = load_runtime_plugin_contributions(catalog, {plugin_id: path},
                mode='local_worker', state_root=state_root)
        except Exception:
            if plugin_id not in optional or plugin_id in required:
                raise
            # Preserve the concrete configuration/adapter error in MCP stderr;
            # unavailable optional tooling must not prevent opening the analysis.
            import logging
            logging.getLogger(__name__).exception('Optional Worker service unavailable: %s', plugin_id)
        else:
            services.update(loaded.tool_services)
    return services
