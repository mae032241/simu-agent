"""Operation-bound Worker tools and stable Codex agent identities."""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from pydantic import BaseModel

from .spec import CompiledOperation, OperationSpec, freeze_json, json_projection
from .lifecycle import AGENT_LIFECYCLE_PROTOCOL, AgentLifecycleInput
from ..artifact_agent.operation_tool_context import OperationToolContext


_TOOL_NAME = re.compile(r"^worker_[a-z][a-z0-9_]{0,95}$")
_LOCAL_SERVICE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_LIFECYCLE_INPUT_SCHEMA = freeze_json(AgentLifecycleInput.model_json_schema())
_LOCAL_NATIVE_EQUIVALENT_TOOLS = frozenset(
    {
        "worker_file_write_begin",
        "worker_file_write_chunk",
        "worker_file_write_commit",
        "worker_file_apply_patch",
        "worker_file_json_patch",
        "worker_file_delete",
        "worker_file_move",
    }
)


@dataclass(frozen=True, slots=True)
class WorkerToolDefinition:
    """One registered tool; lifecycle tools may use the existing Worker router."""

    name: str
    description: str
    input_model: type[BaseModel]
    capability: str
    handler: Callable[[BaseModel], Any] | None = None
    contextual_handler: Callable[[BaseModel, OperationToolContext], Any] | None = None
    local_contextual_handler: Callable[[BaseModel, OperationToolContext], Any] | None = None
    required_services: tuple[str, ...] = ()
    optional_services: tuple[str, ...] = ()
    evidence_ports: tuple[str, ...] = ()
    network_access: bool = False
    record_attempts: bool = False
    _input_schema: Any = field(default=None, repr=False, compare=False)

    def issue(self) -> str | None:
        if not _TOOL_NAME.fullmatch(self.name) or not self.description:
            return "worker_tool_definition_invalid"
        if not isinstance(self.input_model, type) or not issubclass(
            self.input_model, BaseModel
        ):
            return "worker_tool_definition_invalid"
        if (
            not self.capability
            or not isinstance(self.network_access, bool)
            or not isinstance(self.record_attempts, bool)
            or (self.handler is not None and not callable(self.handler))
            or (
                self.contextual_handler is not None
                and not callable(self.contextual_handler)
            )
            or self.handler is not None
            and self.contextual_handler is not None
            or self.handler is not None
            and self.local_contextual_handler is not None
            or len(self.evidence_ports) != len(set(self.evidence_ports))
            or (self.evidence_ports or self.optional_services) and self.contextual_handler is None
            or len(self.optional_services) != len(set(self.optional_services))
            or set(self.optional_services) & set(self.required_services)
            or any(not _LOCAL_SERVICE.fullmatch(name) for name in (*self.optional_services, *self.evidence_ports))
            or len(self.required_services) != len(set(self.required_services))
            or any(
                _LOCAL_SERVICE.fullmatch(name) is None
                for name in self.required_services
            )
            or self.required_services and self.contextual_handler is None
        ):
            return "worker_tool_definition_invalid"
        return None

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": (json_projection(self._input_schema) if self._input_schema is not None
                            else self.input_model.model_json_schema()),
        }


def parse_tool_arguments(model: type[BaseModel], arguments: Any) -> BaseModel:
    """Use JSON semantics consistently with the model-visible tool Schema."""
    return model.model_validate_json(
        json.dumps({} if arguments is None else arguments, allow_nan=False), strict=True
    )


def operation_agent_type(compiled: CompiledOperation) -> str:
    """Return the precompiled Codex type tied to one exact operation digest."""

    stem = re.sub(r"[^a-z0-9_]+", "_", compiled.spec.operation_id.lower()).strip("_")
    return f"op_{stem[:72]}_{compiled.digest[:12]}"


def operation_worker_server_name(compiled: CompiledOperation) -> str:
    """Return the sole Worker MCP namespace authorized for this Operation."""

    stem = operation_agent_type(compiled)[3:].rsplit("_", 1)[0]
    return f"scid_worker_{stem[:32]}_{compiled.digest[:12]}"


def compile_worker_tools(
    plugin_id: str, spec: OperationSpec, implementations: dict[str, Any],
) -> tuple[WorkerToolDefinition, ...]:
    values: list[WorkerToolDefinition] = []
    seen: set[str] = set()
    for reference in spec.executor.tools:
        key = f"{reference.plugin_id or plugin_id}:{reference.component_id}"
        value = implementations[key]
        if not isinstance(value, WorkerToolDefinition) or value.issue() is not None:
            raise ValueError("compiled worker tool definition is invalid")
        if value.name in seen:
            raise ValueError("compiled operation exposes a duplicate worker tool name")
        seen.add(value.name)
        provider = key.partition(":")[0]
        values.append(
            replace(
                value,
                optional_services=tuple(f"{provider}:{name}" for name in value.optional_services),
                required_services=tuple(
                    f"{provider}:{name}" for name in value.required_services
                ),
            )
        )
    return tuple(values)


def operation_worker_tools(compiled: CompiledOperation) -> tuple[WorkerToolDefinition, ...]:
    """Read the tools resolved once by this exact catalog construction."""
    return compiled.worker_tools


def operation_lifecycle_protocol(compiled: CompiledOperation):
    template = compiled.permission_template
    if template is None:
        raise ValueError("compiled operation has no Agent lifecycle protocol")
    protocol = template.lifecycle
    if protocol != AGENT_LIFECYCLE_PROTOCOL:
        raise ValueError("compiled Agent lifecycle protocol is unsupported")
    return protocol


def operation_worker_tool_names(compiled: CompiledOperation) -> tuple[str, ...]:
    lifecycle = operation_lifecycle_protocol(compiled)
    return tuple(item.name for item in lifecycle.tools) + tuple(
        item.name for item in operation_worker_tools(compiled)
    )


def operation_tool_contracts(
    compiled: CompiledOperation, tool_names: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Deliver each allowed tool's complete Schema with its own reference root."""
    contracts = {
        item.name: {"description": item.description,
                    "inputSchema": json_projection(_LIFECYCLE_INPUT_SCHEMA)}
        for item in operation_lifecycle_protocol(compiled).tools
    }
    for tool in operation_worker_tools(compiled):
        schema = tool.schema()
        contracts[tool.name] = {key: schema[key] for key in ("description", "inputSchema")}
    return {name: contracts[name] for name in tool_names}


def operation_local_worker_tools(
    compiled: CompiledOperation,
) -> tuple[WorkerToolDefinition, ...]:
    """Project tools executable by the direct local Worker exactly once."""

    tools = operation_worker_tools(compiled)
    missing = tuple(
        item.name
        for item in tools
        if item.handler is None
        and item.contextual_handler is None
        and item.local_contextual_handler is None
        and item.name not in _LOCAL_NATIVE_EQUIVALENT_TOOLS
    )
    if missing:
        raise ValueError(
            "local backend cannot execute declared Operation tools: "
            + ", ".join(missing)
        )
    return tuple(
        replace(
            item,
            contextual_handler=(
                item.local_contextual_handler or item.contextual_handler
            ),
        )
        for item in tools
        if item.handler is not None
        or item.contextual_handler is not None
        or item.local_contextual_handler is not None
    )


def operation_local_worker_missing_tools(
    compiled: CompiledOperation,
) -> tuple[str, ...]:
    return tuple(
        item.name
        for item in operation_worker_tools(compiled)
        if item.handler is None
        and item.contextual_handler is None
        and item.local_contextual_handler is None
        and item.name not in _LOCAL_NATIVE_EQUIVALENT_TOOLS
    )


def operation_local_worker_tool_names(
    compiled: CompiledOperation,
) -> tuple[str, ...]:
    lifecycle = operation_lifecycle_protocol(compiled)
    return tuple(item.name for item in lifecycle.tools) + tuple(
        item.name for item in operation_local_worker_tools(compiled)
    )


def operation_native_tool_instruction(compiled: CompiledOperation) -> str:
    """Render the prototype allow/forbid notice from one compiled operation."""

    native = compiled.spec.executor.native_tools
    server_name = operation_worker_server_name(compiled)
    tools = operation_worker_tool_names(compiled)
    allowed = ["Worker tools: " + ", ".join(tools)]
    if native.shell != "none":
        allowed.append("Codex code tools for task-local reading and bounded checks")
    if native.view_image:
        allowed.append("native view_image for declared task-local images")
    forbidden = [
        "native file writes or patches that bypass the Worker file lifecycle",
        "native network access",
        "Root/control-plane MCP tools",
        "delegation, skills, apps, plugins, and any undeclared Worker tool",
    ]
    if native.shell == "none":
        forbidden.append("native shell or code execution")
    if not native.view_image:
        forbidden.append("native view_image")
    return (
        "\n\nYou are the spawned Operation worker, not the interactive scheduler. "
        "Scheduler instructions found in the project AGENTS.md apply to the parent "
        "session, not to this assignment. Do not inspect instances, schedule tasks, "
        "or call Root/control-plane tools. The only authorized Worker MCP server is "
        f"`{server_name}`. Start by calling `worker_open_assignment` from exactly that "
        "server. Every other visible Worker MCP server is forbidden: do not probe "
        "it. If the exact claim unexpectedly fails, stop without native filesystem "
        "inspection instead of searching for another queue.\n"
        "After `worker_open_assignment`, take its exact `workspace_path` as "
        "the sole native filesystem root and set every native shell/code call's "
        "workdir to that path or one of its descendants. Read only returned paths below that root or "
        "relative paths declared by `assignment.json`. Never guess a path from the "
        "parent current directory; never search a repository root, sibling run, "
        "historical deliverable, installed package, test, or framework source. "
        "A missing task-local input is a bounded gap, not permission to find an "
        "example elsewhere. Native tools are read-only even when the runtime cannot "
        "technically hide their write capability.\n"
        "This Operation's prototype capability policy follows. Tools may remain "
        "visible because Codex 0.150.1 child Agents inherit parent capabilities; "
        "visibility is not authorization.\nAllowed: "
        + "; ".join(allowed)
        + ".\nForbidden: "
        + "; ".join(forbidden)
        + ".\nScientific output must be written, validated, and finalized only through "
        "the declared Worker tools.\n"
    )


__all__ = [
    "WorkerToolDefinition",
    "operation_agent_type",
    "operation_lifecycle_protocol",
    "operation_local_worker_tool_names",
    "operation_local_worker_missing_tools",
    "operation_local_worker_tools",
    "operation_native_tool_instruction",
    "operation_worker_server_name",
    "operation_worker_tool_names",
    "operation_worker_tools",
    "operation_tool_contracts",
]


def declared_tool_output_names(tools):
    """Ancillary output authority is declared separately from raw-byte access."""
    names = {name for tool in tools for name in tool.evidence_ports}
    if any(tool.record_attempts for tool in tools):
        names.add("recovery_manifest_output")
    return names


def tool_evidence_ports(compiled):
    ports = {p.name: p for p in compiled.spec.outputs if p.collection is not None}
    enabled = declared_tool_output_names(operation_worker_tools(compiled))
    return ports if enabled and enabled == set(ports) and enabled <= {"tool_evidence", "recovery_manifest_output"} else {}
