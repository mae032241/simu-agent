import re
import json
from hashlib import sha256
from functools import lru_cache
from importlib import import_module
from importlib.metadata import entry_points
from types import MappingProxyType
from typing import Any, Iterable, Mapping
from ..operation_contract import output_checker_contract_issue
from .spec import (
    OPERATION_ABI_VERSION, PLUGIN_PROTOCOL_VERSION, CallableComponent,
    ApprovalProviderIdentity, CompiledComponent, CompiledDigestEnvelope,
    CompiledOperation, ComponentRef,
    ComponentSpec, OperationSpec, OutputPortSpec,
    PermissionTemplate, PluginDefinition,
    SchedulerOperationView, WorkspaceContract, canonical_digest,
    scheduler_operation_view)
from .tooling import WorkerToolDefinition
from .lifecycle import AGENT_LIFECYCLE_PROTOCOL
from .workspace import WORKSPACE_HOOK_KINDS
from .runtime_plugins import RuntimePluginFactory
PLUGIN_ENTRY_POINT_GROUP = "scidiscovery.plugins"
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_COMPONENT_KINDS = frozenset({"codec", "validator", "guard", "agent", "transform", "effect", "workspace", "worker_tool", "projector", "resource", "runtime_factory"}) | WORKSPACE_HOOK_KINDS
_CompiledParts = dict[str, tuple[str, OperationSpec, set[str], PermissionTemplate | None]]
class CatalogCompileError(ValueError):
    def __init__(
        self, reason_code: str, *, plugin_id: str | None = None,
        operation_id: str | None = None, field: str | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.plugin_id = plugin_id
        self.operation_id = operation_id
        self.field = field
        location = "/".join(value for value in (plugin_id, operation_id, field) if value)
        super().__init__(f"{reason_code}: {location or 'catalog'}")
class CompiledCatalog:
    __slots__ = (
        "_operations",
        "_runtime_factories",
        "_runtime_configuration_digests",
        "_runtime_identity_digests",
    )
    def __init__(
        self,
        operations: Mapping[str, CompiledOperation],
        runtime_factories: Mapping[str, RuntimePluginFactory] | None = None,
        runtime_configuration_digests: Mapping[str, str] | None = None,
        runtime_identity_digests: Mapping[str, str] | None = None,
    ) -> None:
        self._operations = MappingProxyType(dict(operations))
        self._runtime_factories = MappingProxyType(dict(runtime_factories or {}))
        self._runtime_configuration_digests = MappingProxyType(
            dict(runtime_configuration_digests or {})
        )
        self._runtime_identity_digests = MappingProxyType(
            dict(runtime_identity_digests or {})
        )
        if not (
            set(self._runtime_factories)
            == set(self._runtime_configuration_digests)
            == set(self._runtime_identity_digests)
        ):
            raise ValueError("runtime plugin catalog metadata is incomplete")
    def operation(self, operation_id: str) -> CompiledOperation: return self._operations[operation_id]
    def operation_ids(self) -> tuple[str, ...]: return tuple(self._operations)
    def scheduler_projection(self) -> tuple[SchedulerOperationView, ...]: return tuple(scheduler_operation_view(item.spec) for item in self._operations.values())
    def runtime_factory(self, plugin_id: str) -> RuntimePluginFactory:
        try: return self._runtime_factories[plugin_id]
        except KeyError as error: raise ValueError("plugin has no compiled runtime factory") from error
    def runtime_plugin_ids(self) -> tuple[str, ...]: return tuple(sorted(self._runtime_factories))
    def runtime_configuration_digest(self, plugin_id: str) -> str:
        try: return self._runtime_configuration_digests[plugin_id]
        except KeyError as error: raise ValueError("plugin has no compiled runtime configuration") from error
    def digest(self) -> str:
        payload = {
            "operations": [
                (operation_id, self._operations[operation_id].digest)
                for operation_id in sorted(self._operations)
            ],
            "runtime_plugins": [
                (
                    plugin_id,
                    self._runtime_configuration_digests[plugin_id],
                    self._runtime_identity_digests[plugin_id],
                )
                for plugin_id in sorted(self._runtime_configuration_digests)
            ],
        }
        return sha256(
            json.dumps(
                payload,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
def _fail(
    code: str, plugin: str | None = None, operation: str | None = None,
    field: str | None = None) -> None:
    raise CatalogCompileError(code, plugin_id=plugin, operation_id=operation, field=field)
def _load_implementation(spec: ComponentSpec, plugin_id: str) -> Any:
    module_name, separator, attribute_path = spec.implementation.partition(":")
    if not separator or not module_name or not attribute_path: _fail("component_implementation_invalid", plugin_id, field=spec.component_id)
    try:
        value: Any = import_module(module_name)
        for attribute in attribute_path.split("."):
            value = getattr(value, attribute)
    except (ImportError, AttributeError):
        _fail("component_implementation_missing", plugin_id, field=spec.component_id)
    except Exception:
        _fail("component_implementation_error", plugin_id, field=spec.component_id)
    if spec.kind == "resource":
        if not isinstance(value, (str, bytes)): _fail("component_protocol_invalid", plugin_id, field=spec.component_id)
        return value
    if spec.kind == "workspace":
        if not isinstance(value, WorkspaceContract) or value != WorkspaceContract(): _fail("component_protocol_invalid", plugin_id, field=spec.component_id)
        return value
    if spec.kind == "worker_tool":
        if not isinstance(value, WorkerToolDefinition) or value.issue() is not None:
            _fail("component_protocol_invalid", plugin_id, field=spec.component_id)
        return value
    if spec.kind == "runtime_factory":
        if not isinstance(value, RuntimePluginFactory):
            _fail("component_protocol_invalid", plugin_id, field=spec.component_id)
        return value
    if not isinstance(value, CallableComponent) or value.kind != spec.kind: _fail("component_protocol_invalid", plugin_id, field=spec.component_id)
    if not callable(value.implementation): _fail("component_protocol_invalid", plugin_id, field=spec.component_id)
    return value.implementation
def _resource_digest(spec: ComponentSpec, implementation: Any, plugin_id: str) -> str | None:
    try:
        if spec.kind == "workspace":
            return canonical_digest(implementation)
        if spec.kind == "resource":
            content = implementation if isinstance(implementation, bytes) else implementation.encode("utf-8")
            return sha256(content).hexdigest()
        return None
    except Exception: _fail("component_resource_digest_invalid", plugin_id, field=spec.component_id)
def _qualified(owner: str, reference: ComponentRef) -> str:
    return f"{reference.plugin_id or owner}:{reference.component_id}"
def _approval_option_id(decision: str) -> str:
    return {
        "accept": "approve",
        "accept_with_exception": "approve_with_exception",
        "reject": "reject",
        "revise": "revise",
    }[decision]
def _normalize_declarations(plugins: Iterable[PluginDefinition]) -> tuple[dict[str, PluginDefinition], dict[str, CompiledComponent]]:
    try:
        declared_plugins = tuple(plugins)
    except Exception:
        _fail("plugin_set_invalid")
    normalized: list[PluginDefinition] = []
    for raw_plugin in declared_plugins:
        if not isinstance(raw_plugin, PluginDefinition): _fail("plugin_definition_invalid")
        try:
            normalized.append(PluginDefinition.model_validate(
                raw_plugin.model_dump(mode="python", warnings=False), strict=True
            ))
        except Exception:
            _fail("declaration_structure_invalid", getattr(raw_plugin, "plugin_id", None))
    plugin_map: dict[str, PluginDefinition] = {}
    components: dict[str, CompiledComponent] = {}
    for plugin in sorted(normalized, key=lambda item: item.plugin_id):
        if (not isinstance(plugin.plugin_id, str) or not _ID.fullmatch(plugin.plugin_id)
                or not isinstance(plugin.version, str) or not plugin.version):
            _fail("plugin_id_invalid", plugin.plugin_id)
        if plugin.plugin_id in plugin_map: _fail("plugin_duplicate", plugin.plugin_id)
        if plugin.protocol_version != PLUGIN_PROTOCOL_VERSION: _fail("plugin_protocol_unsupported", plugin.plugin_id)
        plugin_map[plugin.plugin_id] = plugin
        local_ids: set[str] = set()
        for component in plugin.components:
            if component.component_id in local_ids: _fail("component_duplicate", plugin.plugin_id, field=component.component_id)
            if not _ID.fullmatch(component.component_id) or component.kind not in _COMPONENT_KINDS: _fail("component_invalid", plugin.plugin_id, field=component.component_id)
            if component.protocol_version != "1": _fail("component_protocol_unsupported", plugin.plugin_id, field=component.component_id)
            local_ids.add(component.component_id)
            key = f"{plugin.plugin_id}:{component.component_id}"
            implementation = _load_implementation(component, plugin.plugin_id)
            components[key] = CompiledComponent(
                plugin.plugin_id,
                component,
                implementation,
                _resource_digest(component, implementation, plugin.plugin_id),
            )
    for plugin in plugin_map.values():
        for dependency in plugin.dependencies:
            target = plugin_map.get(dependency.plugin_id)
            if target is None or (dependency.version and target.version != dependency.version): _fail("plugin_dependency_missing", plugin.plugin_id, field=dependency.plugin_id)
    return plugin_map, components
def _resolve_component(plugin_map: Mapping[str, PluginDefinition], components: Mapping[str, CompiledComponent], used: set[str], owner: str, ref: ComponentRef, kind: str | None = None, reachable: set[str] | None = None) -> CompiledComponent:
    key = _qualified(owner, ref)
    component = components.get(key)
    if component is None: _fail("component_reference_missing", owner, field=key)
    if component.plugin_id != owner:
        dependencies = {item.plugin_id for item in plugin_map[owner].dependencies}
        if component.plugin_id not in dependencies or not component.spec.public: _fail("component_cross_plugin_forbidden", owner, field=key)
    if kind is not None and component.spec.kind != kind: _fail("component_kind_mismatch", owner, field=key)
    first_global_use = key not in used
    used.add(key)
    first_operation_use = reachable is not None and key not in reachable
    if reachable is not None:
        reachable.add(key)
    if first_global_use or first_operation_use:
        hook_kinds: set[str] = set()
        for resource in component.spec.resources:
            dependency = _resolve_component(
                plugin_map, components, used,
                component.plugin_id, resource,
                None if component.spec.kind == "workspace" else "resource",
                reachable)
            if (component.spec.kind == "workspace"
                    and dependency.spec.kind not in WORKSPACE_HOOK_KINDS):
                _fail("workspace_hook_kind_invalid", owner, field=key)
            if component.spec.kind == "workspace":
                if dependency.spec.kind in hook_kinds: _fail("workspace_hook_duplicate", owner, field=key)
                hook_kinds.add(dependency.spec.kind)
    return component
def _validate_operation_contracts(plugin_map: dict[str, PluginDefinition], components: dict[str, CompiledComponent]) -> tuple[_CompiledParts, dict[str, RuntimePluginFactory], dict[str, str], dict[str, str], set[str]]:
    used: set[str] = set()
    compiled_parts: _CompiledParts = {}
    runtime_factories: dict[str, RuntimePluginFactory] = {}
    runtime_configuration_digests: dict[str, str] = {}
    runtime_identity_digests: dict[str, str] = {}
    runtime_refs: dict[str, tuple[ComponentRef, ...]] = {}
    for plugin in plugin_map.values():
        refs: list[ComponentRef] = []
        runtime_scope: set[str] = set()
        if plugin.configuration_schema is not None:
            configuration = _resolve_component(plugin_map, components, used, plugin.plugin_id, plugin.configuration_schema, "resource", runtime_scope)
            if configuration.resource_digest is None:
                _fail("plugin_runtime_configuration_digest_missing", plugin.plugin_id)
            try:
                configuration_schema = json.loads(configuration.implementation)
            except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
                _fail("plugin_runtime_configuration_schema_invalid", plugin.plugin_id)
            if (
                not isinstance(configuration_schema, dict)
                or not isinstance(configuration_schema.get("$id"), str)
                or not configuration_schema["$id"]
            ):
                _fail("plugin_runtime_configuration_schema_invalid", plugin.plugin_id)
            runtime_configuration_digests[plugin.plugin_id] = configuration.resource_digest
            refs.append(plugin.configuration_schema)
        if plugin.runtime_factory is not None:
            if plugin.configuration_schema is None:
                _fail("plugin_runtime_configuration_missing", plugin.plugin_id)
            component = _resolve_component(plugin_map, components, used, plugin.plugin_id, plugin.runtime_factory, "runtime_factory", runtime_scope)
            runtime_factories[plugin.plugin_id] = component.implementation
            configuration = components[
                _qualified(plugin.plugin_id, plugin.configuration_schema)
            ]
            runtime_identity_digests[plugin.plugin_id] = canonical_digest(
                {
                    "plugin_id": plugin.plugin_id,
                    "plugin_version": plugin.version,
                    "components": tuple(
                        (
                            key,
                            plugin_map[components[key].plugin_id].version,
                            components[key].spec,
                            components[key].resource_digest,
                        )
                        for key in sorted(runtime_scope)
                    ),
                }
            )
            refs.append(plugin.runtime_factory)
        elif plugin.configuration_schema is not None:
            _fail("plugin_runtime_factory_missing", plugin.plugin_id)
        runtime_refs[plugin.plugin_id] = tuple(refs)
        for operation in plugin.operations:
            reachable: set[str] = set()
            for runtime_ref in runtime_refs[plugin.plugin_id]:
                _resolve_component(plugin_map, components, used, plugin.plugin_id, runtime_ref, None, reachable)
            op_id = operation.operation_id
            if (not isinstance(op_id, str) or not _ID.fullmatch(op_id)
                    or not isinstance(operation.version, str) or not operation.version):
                _fail("operation_invalid", plugin.plugin_id, op_id)
            if not all((operation.description.purpose,
                        operation.description.applies_when,
                        operation.description.not_for)):
                _fail("operation_description_invalid", plugin.plugin_id, op_id)
            if op_id in compiled_parts: _fail("operation_duplicate", plugin.plugin_id, op_id)
            if operation.executor.kind == "approval" and (
                operation.catalog_scope != "public"
                or operation.consequence == "external"
                or operation.outputs
                or operation.review is None
                or operation.review.approval is None
                or operation.executor.component
                != operation.review.approval.projector
                or set(operation.review.approval.subject_ports)
                != {port.name for port in operation.inputs}
            ):
                _fail("approval_operation_invalid", plugin.plugin_id, op_id, "review")
            if not operation.inputs or (
                not operation.outputs and operation.executor.kind != "approval"
            ):
                _fail("operation_ports_empty", plugin.plugin_id, op_id)
            names = [port.name for port in (*operation.inputs, *operation.outputs)]
            if len(names) != len(set(names)): _fail("operation_port_duplicate", plugin.plugin_id, op_id)
            for port in (*operation.inputs, *operation.outputs):
                issue = port.issue()
                if issue: _fail(issue, plugin.plugin_id, op_id, port.name)
                _resolve_component(plugin_map, components, used, plugin.plugin_id, port.codec, "codec", reachable)
                schema_component = _resolve_component(plugin_map, components, used, 
                    plugin.plugin_id, port.schema_resource, "resource", reachable
                )
                try:
                    schema = json.loads(schema_component.implementation)
                except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
                    _fail("schema_resource_invalid", plugin.plugin_id, op_id, port.name)
                if not isinstance(schema, dict) or schema.get("$id") != port.schema_id: _fail("schema_resource_mismatch", plugin.plugin_id, op_id, port.name)
                if isinstance(port, OutputPortSpec):
                    validators = (
                        port.validator,
                        port.collection.bundle_validator if port.collection else None,
                        port.context_validator,
                    )
                    for validator in validators:
                        if validator:
                            _resolve_component(plugin_map, components, used, plugin.plugin_id, validator, "validator", reachable)
                    contract_implementation = None
                    if port.semantic_contract is not None:
                        contract = _resolve_component(plugin_map, components, used, plugin.plugin_id, port.semantic_contract,
                                           "resource", reachable)
                        contract_implementation = contract.implementation
                    checker_issue = output_checker_contract_issue(
                        contract_implementation, port,
                        {item.name: item.min_items for item in operation.inputs},
                        agent_output=operation.executor.kind == "agent",
                    )
                    if checker_issue: _fail(checker_issue[0], plugin.plugin_id, op_id,
                                            checker_issue[1] or port.name)
                    input_names = {item.name for item in operation.inputs}
                    if ((port.context_sources and not port.context_validator)
                            or not set(port.context_sources) <= input_names):
                        _fail("output_context_invalid", plugin.plugin_id, op_id, port.name)
                    if operation.executor.kind == "agent" and any(
                        item.exposure == "handoff_only"
                        and item.name in port.context_sources
                        for item in operation.inputs
                    ):
                        # context_sources grants the checker full input bytes.
                        # Lineage-only inputs may stay hidden outside this set.
                        _fail("output_context_input_hidden", plugin.plugin_id, op_id, port.name)
                    if port.collection is not None and port.evidence_paths:
                        _fail("output_evidence_path_invalid", plugin.plugin_id, op_id, port.name)
            admission = operation.input_admission
            if admission is not None:
                issue = admission.issue()
                if issue:
                    _fail(issue, plugin.plugin_id, op_id, "input_admission")
                input_ports = {port.name: port for port in operation.inputs}
                if (
                    not set(admission.member_ports) <= set(input_ports)
                    or any(
                        input_ports[name].max_items != 1
                        for name in admission.member_ports
                        if name in input_ports
                    )
                ):
                    _fail(
                        "input_admission_invalid",
                        plugin.plugin_id,
                        op_id,
                        "input_admission",
                    )
            complete_family = operation.complete_transform_family
            if complete_family is not None:
                issue = complete_family.issue()
                input_names = {port.name for port in operation.inputs}
                if (
                    issue is not None
                    or not set(complete_family.output_ports) <= input_names
                    or not set(complete_family.input_ports) <= input_names
                ):
                    _fail(
                        issue or "complete_transform_family_invalid",
                        plugin.plugin_id,
                        op_id,
                        "complete_transform_family",
                    )
            change_request_count = sum(port.usage == "change_request" for port in operation.inputs)
            if change_request_count and (change_request_count != 1 or sum(port.usage == "revision_base" for port in operation.inputs) != 1):
                _fail("change_request_without_revision_base", plugin.plugin_id, op_id, "inputs")
            if operation.consequence not in {"explore", "scientific", "external"}: _fail("consequence_invalid", plugin.plugin_id, op_id)
            if operation.review is not None:
                issue = operation.review.issue()
                if issue:
                    _fail(issue, plugin.plugin_id, op_id, "review")
            issue = operation.limits.issue() if operation.limits else "limits_invalid"
            if issue: _fail(issue, plugin.plugin_id, op_id, "limits")
            issue = operation.bounds_issue()
            if issue: _fail(issue, plugin.plugin_id, op_id, "limits")
            executor = operation.executor
            if executor.kind not in {"agent", "transform", "effect", "approval"}: _fail("executor_invalid", plugin.plugin_id, op_id)
            if operation.catalog_scope == "support" and executor.kind != "transform": _fail("support_executor_invalid", plugin.plugin_id, op_id, "catalog_scope")
            if operation.catalog_scope == "support" and operation.review and operation.review.approval: _fail("support_approval_forbidden", plugin.plugin_id, op_id, "review")
            _resolve_component(plugin_map, components, used, 
                plugin.plugin_id,
                executor.component,
                "projector" if executor.kind == "approval" else executor.kind,
                reachable,
            )
            declared_refs = (
                executor.component,
                *((executor.workspace,) if executor.workspace else ()),
                *executor.tools,
                *executor.resources,
                *((executor.prompt,) if executor.prompt else ()),
                *operation.guards,
                *((operation.review.progress_fingerprint,)
                  if operation.review and operation.review.progress_fingerprint
                  else ()),
            )
            if len({_qualified(plugin.plugin_id, ref) for ref in declared_refs}) != len(
                declared_refs
            ):
                _fail("component_reference_duplicate", plugin.plugin_id, op_id)
            for guard in operation.guards:
                _resolve_component(plugin_map, components, used, plugin.plugin_id, guard, "guard", reachable)
            if operation.review and operation.review.progress_fingerprint:
                _resolve_component(
                    plugin_map,
                    components,
                    used,
                    plugin.plugin_id,
                    operation.review.progress_fingerprint,
                    "transform",
                    reachable,
                )
            permission: PermissionTemplate | None = None
            if executor.kind == "agent":
                if not executor.workspace or not executor.prompt or not executor.model: _fail("agent_authority_incomplete", plugin.plugin_id, op_id)
                primary = tuple(port for port in operation.outputs if port.collection is None)
                if (len(primary) != 1 or primary[0].min_items != 1
                        or primary[0].max_items != 1
                        or primary[0].media_types != ("application/json",)
                        or any(port.validator is None for port in operation.outputs)):
                    _fail("agent_output_contract_invalid", plugin.plugin_id, op_id)
                if any(port.semantic_contract is None for port in operation.outputs):
                    _fail("agent_semantic_contract_missing", plugin.plugin_id,
                          op_id, "outputs")
                for port in operation.outputs:
                    contract_key = _qualified(plugin.plugin_id, port.semantic_contract)
                    for validator in (port.validator, port.context_validator,
                                      port.collection.bundle_validator if port.collection else None):
                        if validator and contract_key not in {_qualified(validator.plugin_id or plugin.plugin_id, item) for item in components[_qualified(plugin.plugin_id, validator)].spec.resources}: _fail("validator_semantic_contract_mismatch", plugin.plugin_id, op_id, port.name)
                native_issue = executor.native_tools.issue()
                if native_issue: _fail(native_issue, plugin.plugin_id, op_id, "native_tools")
                worker_scope: set[str] = set()
                worker_components = (
                    (executor.component, "agent"),
                    (executor.workspace, "workspace"),
                    (executor.prompt, "resource"),
                    *((item, "worker_tool") for item in executor.tools),
                    *((item, "resource") for item in executor.resources),
                )
                for reference, kind in worker_components:
                    _resolve_component(plugin_map, components, used, plugin.plugin_id, reference, kind, worker_scope)
                reachable.update(worker_scope)
                prompt_resource = _qualified(plugin.plugin_id, executor.prompt)
                resource_scope = {key for key in worker_scope
                                  if components[key].spec.kind == "resource"}
                if resource_scope != {prompt_resource}: _fail("agent_resources_unsupported", plugin.plugin_id, op_id, "resources")
                network_bound = any(
                    components[_qualified(plugin.plugin_id, ref)].implementation.network_access
                    for ref in executor.tools)
                if network_bound != (operation.limits.network.mode == "restricted"):
                    code = ("network_tool_scope_missing" if network_bound
                            else "network_scope_without_tool")
                    _fail(code, plugin.plugin_id, op_id, "limits")
                lifecycle_names = {
                    item.name for item in AGENT_LIFECYCLE_PROTOCOL.tools
                }
                registered_names = {
                    components[
                        _qualified(plugin.plugin_id, ref)
                    ].implementation.name
                    for ref in executor.tools
                }
                if lifecycle_names & registered_names:
                    _fail(
                        "agent_lifecycle_tool_collision",
                        plugin.plugin_id,
                        op_id,
                        "tools",
                    )
                workspace = _qualified(plugin.plugin_id, executor.workspace)
                permission = PermissionTemplate(
                    inputs=tuple((p.name, p.exposure, p.max_items, p.max_item_bytes)
                                 for p in operation.inputs),
                    workspace=workspace,
                    tools=tuple(_qualified(plugin.plugin_id, item)
                                for item in executor.tools),
                    resources=(prompt_resource,),
                    model=executor.model,
                    native_tools=executor.native_tools,
                    limits=operation.limits,
                    lifecycle=AGENT_LIFECYCLE_PROTOCOL,
                )
            elif any((
                executor.workspace,
                executor.tools,
                executor.resources,
                executor.prompt,
                executor.model,
                executor.native_tools.shell != "none",
                executor.native_tools.view_image,
            )):
                _fail("executor_authority_forbidden", plugin.plugin_id, op_id)
            if (executor.kind == "effect") != (operation.consequence == "external"): _fail("effect_consequence_invalid", plugin.plugin_id, op_id)
            compiled_parts[op_id] = (plugin.plugin_id, operation, reachable, permission)
    return compiled_parts, runtime_factories, runtime_configuration_digests, runtime_identity_digests, used
def _validate_review_graph(plugin_map: Mapping[str, PluginDefinition], components: Mapping[str, CompiledComponent], compiled_parts: _CompiledParts, used: set[str]) -> dict[str, tuple[str, ...]]:
    review_edges: dict[str, str] = {}
    for op_id, (plugin_id, operation, _, _) in compiled_parts.items():
        review = operation.review
        if operation.consequence == "external" and not (review and review.approval): _fail("external_approval_missing", plugin_id, op_id)
        if review is None:
            continue
        if review.approval is not None:
            issue = review.approval.issue(
                {port.name for port in (*operation.inputs, *operation.outputs)},
                operation.consequence == "external",
            )
            if issue: _fail(issue, plugin_id, op_id, "review")
            subject_ports = {
                port.name: port for port in (*operation.inputs, *operation.outputs)
            }
            if sum(
                subject_ports[name].max_items
                for name in review.approval.subject_ports
            ) > 256:
                _fail("approval_subject_limit_invalid", plugin_id, op_id, "review")
            if operation.consequence == "external" and (
                len(operation.inputs) != 1
                or len(operation.outputs) != 1
                or review.approval.subject_ports
                != (operation.outputs[0].name, operation.inputs[0].name)
                or operation.outputs[0].kind != "execution_request"
                or operation.outputs[0].schema_id
                != "scidiscovery.execution-request"
            ):
                _fail("effect_approval_contract_mismatch", plugin_id, op_id, "review")
            _resolve_component(plugin_map, components, used, plugin_id, review.approval.projector, "projector",
                    compiled_parts[op_id][2])
        if review.reviewer_operation is None:
            if review.reviewer_input_port or review.subject_outputs: _fail("reviewer_contract_incomplete", plugin_id, op_id, "review")
            continue
        reviewer_entry = compiled_parts.get(review.reviewer_operation)
        if reviewer_entry is None: _fail("reviewer_operation_missing", plugin_id, op_id, "review")
        reviewer_plugin, reviewer, _, _ = reviewer_entry
        dependencies = {item.plugin_id for item in plugin_map[plugin_id].dependencies}
        if reviewer_plugin != plugin_id and reviewer_plugin not in dependencies: _fail("reviewer_cross_plugin_forbidden", plugin_id, op_id, "review")
        if reviewer.executor.kind != "agent" or reviewer.operation_id == op_id: _fail("reviewer_not_independent", plugin_id, op_id, "review")
        if operation.catalog_scope == "public" and reviewer.catalog_scope != "public": _fail("reviewer_not_public", plugin_id, op_id, "review")
        if _qualified(plugin_id, operation.executor.component) == _qualified(
            reviewer_plugin, reviewer.executor.component
        ):
            _fail("reviewer_not_independent", plugin_id, op_id, "review")
        subject_names = set(review.subject_outputs)
        source_ports = [port for port in operation.outputs if port.name in subject_names]
        target = next((port for port in reviewer.inputs
                       if port.name == review.reviewer_input_port), None)
        missing_port = (not source_ports or target is None
                        or len(review.subject_outputs) != len(subject_names)
                        or len(source_ports) != len(subject_names))
        if missing_port: _fail("reviewer_port_missing", plugin_id, op_id, "review")
        producer_min = sum(port.min_items for port in source_ports)
        producer_max = sum(port.max_items for port in source_ports)
        target_schema = components[
            _qualified(reviewer_plugin, target.schema_resource)
        ].resource_digest
        incompatible = any(
            port.schema_id != target.schema_id
            or not set(port.media_types) <= set(target.media_types)
            or _qualified(plugin_id, port.codec)
            != _qualified(reviewer_plugin, target.codec)
            or components[_qualified(plugin_id, port.schema_resource)].resource_digest
            != target_schema
            for port in source_ports
        )
        if incompatible or not (
            target.min_items <= producer_min and producer_max <= target.max_items
        ):
            _fail("reviewer_port_incompatible", plugin_id, op_id, "review")
        review_edges[op_id] = reviewer.operation_id
    approval_provider_ids: dict[str, tuple[str, ...]] = {}
    for op_id, (plugin_id, operation, _, _) in compiled_parts.items():
        admission = operation.input_admission
        if admission is None or admission.approval_kind is None:
            continue
        provider_ids = admission.accepted_provider_operations
        accepted_options = set(admission.accepted_options)
        accepted_provider_options: set[str] = set()
        for provider_id in provider_ids:
            provider_entry = compiled_parts.get(provider_id)
            if provider_entry is None:
                _fail(
                    "approval_provider_missing",
                    plugin_id,
                    op_id,
                    admission.cohort_id,
                )
            provider_plugin, provider, _, _ = provider_entry
            dependency_versions = {
                dependency.plugin_id: dependency.version
                for dependency in plugin_map[plugin_id].dependencies
            }
            if provider_plugin != plugin_id and provider_plugin not in dependency_versions:
                _fail(
                    "approval_provider_cross_plugin_forbidden",
                    plugin_id,
                    op_id,
                    admission.cohort_id,
                )
            provider_review = provider.review
            provider_contract = (
                provider_review.approval if provider_review is not None else None
            )
            provider_admission = provider.input_admission
            if (
                provider.catalog_scope != "public"
                or provider.executor.kind != "approval"
                or provider_contract is None
                or provider_contract.kind != admission.approval_kind
                or (
                    provider_admission is not None
                    and provider_admission.approval_kind is not None
                )
            ):
                _fail(
                    "approval_provider_invalid",
                    plugin_id,
                    op_id,
                    admission.cohort_id,
                )
            accepted_provider_options.update(
                _approval_option_id(option.decision)
                for option in provider_contract.options
            )
        if not accepted_options <= accepted_provider_options:
            _fail(
                "approval_provider_options_invalid",
                plugin_id,
                op_id,
                admission.cohort_id,
            )
        approval_provider_ids[op_id] = provider_ids
    for origin in review_edges:
        seen: set[str] = set()
        current = origin
        while current in review_edges:
            if current in seen:
                owner = compiled_parts[origin][0]
                _fail("reviewer_cycle", owner, origin, "review")
            seen.add(current)
            current = review_edges[current]
    return approval_provider_ids
def _build_compiled_catalog(plugin_map: Mapping[str, PluginDefinition], components: Mapping[str, CompiledComponent], compiled_parts: _CompiledParts, approval_provider_ids: Mapping[str, tuple[str, ...]], runtime_factories: Mapping[str, RuntimePluginFactory], runtime_configuration_digests: Mapping[str, str], runtime_identity_digests: Mapping[str, str], used: set[str]) -> CompiledCatalog:
    unused = sorted(key for key, component in components.items() if key not in used and not component.spec.public)
    if unused:
        plugin_id, component_id = unused[0].split(":", 1)
        _fail("component_unused", plugin_id, field=component_id)
    digests: dict[str, str] = {}
    digest_stack: set[str] = set()
    def approval_contract_digest(op_id: str) -> str | None:
        review = compiled_parts[op_id][1].review
        return (
            canonical_digest(review.approval)
            if review is not None and review.approval is not None
            else None
        )
    def provider_identity(provider_id: str) -> ApprovalProviderIdentity:
        provider = compiled_parts[provider_id][1]
        contract_digest = approval_contract_digest(provider_id)
        return ApprovalProviderIdentity(
            operation_id=provider.operation_id,
            version=provider.version,
            operation_digest=operation_digest(provider_id),
            approval_contract_digest=contract_digest,
        )
    def operation_digest(op_id: str) -> str:
        if op_id in digests:
            return digests[op_id]
        if op_id in digest_stack:
            plugin_id = compiled_parts[op_id][0]
            _fail("operation_digest_cycle", plugin_id, op_id, "digest")
        digest_stack.add(op_id)
        plugin_id, operation, references, permission = compiled_parts[op_id]
        reachable = tuple(sorted(references))
        component_specs = tuple((components[key].plugin_id,
                                 plugin_map[components[key].plugin_id].version,
                                 components[key].spec, components[key].resource_digest)
                                for key in reachable)
        reviewer_id = operation.review and operation.review.reviewer_operation
        reviewer_digest = operation_digest(reviewer_id) if reviewer_id else None
        provider_identities = tuple(
            provider_identity(provider_id)
            for provider_id in approval_provider_ids.get(op_id, ())
        )
        try:
            digest = canonical_digest(
                CompiledDigestEnvelope(
                    OPERATION_ABI_VERSION, plugin_id, plugin_map[plugin_id].version,
                    operation, component_specs, permission, reviewer_digest,
                    provider_identities,
                )
            )
        except Exception: _fail("operation_digest_invalid", plugin_id, op_id, "digest")
        finally:
            digest_stack.discard(op_id)
        digests[op_id] = digest
        return digest
    compiled: dict[str, CompiledOperation] = {}
    for op_id, (plugin_id, operation, references, permission) in compiled_parts.items():
        reachable = tuple(sorted(references))
        implementations = MappingProxyType({key: components[key].implementation for key in reachable})
        component_specs = MappingProxyType({key: components[key].spec for key in reachable})
        contract_digest = approval_contract_digest(op_id)
        approval_identity = (
            ApprovalProviderIdentity(
                operation_id=operation.operation_id,
                version=operation.version,
                operation_digest=operation_digest(op_id),
                approval_contract_digest=contract_digest,
            )
            if contract_digest is not None else None
        )
        approval_providers = tuple(
            provider_identity(provider_id)
            for provider_id in approval_provider_ids.get(op_id, ())
        )
        compiled[op_id] = CompiledOperation(
            plugin_id, operation, reachable, implementations, component_specs, permission,
            operation_digest(op_id), approval_identity, approval_providers)
        if any(port.usage == "revision_base" for port in operation.inputs):
            from .invoke import direct_revision_ports
            if direct_revision_ports(compiled[op_id]) is None:
                _fail(
                    "direct_revision_contract_invalid",
                    plugin_id,
                    op_id,
                    "inputs",
                )
        elif operation.review and operation.review.max_revisions:
            _fail(
                "review_revision_policy_without_revision",
                plugin_id,
                op_id,
                "review",
            )
        if operation.executor.kind == "agent":
            primary = tuple(
                port for port in operation.outputs if port.collection is None
            )
            if len(primary) != 1:
                _fail("agent_primary_output_invalid", plugin_id, op_id, "outputs")
    return CompiledCatalog(
        dict(sorted(compiled.items())),
        runtime_factories,
        runtime_configuration_digests,
        runtime_identity_digests,
    )
def compile_catalog(plugins: Iterable[PluginDefinition]) -> CompiledCatalog:
    plugin_map, components = _normalize_declarations(plugins)
    compiled_parts, runtime_factories, runtime_configuration_digests, runtime_identity_digests, used = _validate_operation_contracts(plugin_map, components)
    approval_provider_ids = _validate_review_graph(plugin_map, components, compiled_parts, used)
    return _build_compiled_catalog(plugin_map, components, compiled_parts, approval_provider_ids, runtime_factories, runtime_configuration_digests, runtime_identity_digests, used)
@lru_cache(maxsize=1)
def compile_installed_catalog() -> CompiledCatalog:
    selected = tuple(entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP))
    names: set[str] = set()
    plugins: list[PluginDefinition] = []
    for entry_point in sorted(selected, key=lambda item: item.name):
        if entry_point.name in names: _fail("plugin_entry_point_duplicate", entry_point.name)
        names.add(entry_point.name)
        try:
            plugin = entry_point.load()
        except Exception:
            _fail("plugin_entry_point_unloadable", entry_point.name)
        if not isinstance(plugin, PluginDefinition): _fail("plugin_definition_invalid", entry_point.name)
        if plugin.plugin_id != entry_point.name: _fail("plugin_entry_point_mismatch", plugin.plugin_id)
        plugins.append(plugin)
    return compile_catalog(plugins)
