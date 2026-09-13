"""Single-source helpers for compiled Agent output contracts."""

from __future__ import annotations

import json
import re
from pydantic import ValidationError
from .artifact_agent.schema.common import ContractDiagnostic
from collections.abc import Iterable
from typing import Any, Mapping

from .operations.spec import (
    CompiledOperation,
    freeze_json,
    json_projection,
    input_validation_projection,
    OperationSpec,
    OutputPortSpec,
    SemanticContractSpec,
    SemanticRuleSpec,
)


class SemanticRuleViolation(ValueError):
    """An intentional Worker-correctable rejection by a bound semantic checker."""

    def __init__(self, message: str, *, details: tuple[dict[str, Any], ...] = ()):
        super().__init__(message)
        self.details = details


class DiagnosticError(RuntimeError):
    """Transport a typed, already-safe diagnostic without stringifying it."""
    def __init__(self, message: str, *, details: tuple[dict[str, Any], ...] = ()):
        super().__init__(message)
        self.details = details


class DeclaredDiagnostic(dict):
    """In-process marker for explicitly declared safe details; never a wire field."""


def contract_diagnostic(code: str, *, phase: str, affected_action: str,
                        path: str = "$", repairable: bool = False,
                        message: str = "The declared requirement was not satisfied.",
                        rule_id: str | None = None, error_type: str | None = None) -> dict[str, Any]:
    return DeclaredDiagnostic(ContractDiagnostic(code=code, phase=phase, path=path, message=message,
        repairable=repairable, affected_action=affected_action, rule_id=rule_id,
        type=error_type).model_dump(mode="json", exclude_none=True))


def declared_violation(message: str, *, path: str = "$") -> SemanticRuleViolation:
    """Declare a static relationship error at its owner, without reflecting input."""
    return SemanticRuleViolation(message, details=(contract_diagnostic("output_invalid",
        phase="output_payload", affected_action="submit", repairable=True,
        path=path, message=message, error_type="value_error"),))


def validate_evidence_source_aliases(payload: Mapping[str, Any], sources: Iterable[str]) -> None:
    """Check scientific source references against bound aliases, not a copied ledger.

    Source-alias forms pass exact bound aliases. Analysis owners first resolve
    their optional local citations and verify calculation receipts, then include
    those local identities in the known set. This helper never creates bindings.
    """
    known = set(sources)
    pending = [(payload, "$")]
    while pending:
        value, path = pending.pop()
        if isinstance(value, Mapping):
            for index, key in enumerate(value.get("evidence_keys", ())):
                if key not in known:
                    raise declared_violation("Evidence reference must name a source bound to this task.",
                        path=f"{path}.evidence_keys[{index}]")
            for index, citation in enumerate(value.get("evidence", ())):
                if isinstance(citation, Mapping) and citation.get("source_key") not in known:
                    raise declared_violation("Evidence citation must name a source bound to this task.",
                        path=f"{path}.evidence[{index}].source_key")
            pending.extend((child, f"{path}.{key}") for key, child in value.items()
                           if isinstance(child, (Mapping, list, tuple)))
        elif isinstance(value, (list, tuple)):
            pending.extend((child, f"{path}[{index}]") for index, child in enumerate(value)
                           if isinstance(child, (Mapping, list, tuple)))


def schema_field_names(schema: Any) -> frozenset[str]:
    names = set()
    def visit(value):
        if isinstance(value, Mapping):
            names.update(value.get("properties", ()))
            for child in value.values(): visit(child)
        elif isinstance(value, (tuple, list)):
            for child in value: visit(child)
    visit(schema)
    return frozenset(names)


def diagnostic_path(parts: Iterable[Any], names: Iterable[str], *, root: str = "$") -> str:
    allowed = set(names)
    path = root
    for part in tuple(parts)[:32]:
        token = (f"[{part}]" if isinstance(part, int) and 0 <= part <= 1000000
                 else f".{part}" if isinstance(part, str) and part in allowed
                 and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,95}", part) else "[key]")
        if len(path) + len(token) > 512: break
        path += token
    return path


def validation_diagnostics(error: ValidationError, *, schema: Any,
                           phase: str = "tool_arguments", action: str = "tool_call") -> tuple[dict[str, Any], ...]:
    messages = {
        "missing": "Required field is missing.",
        "dict_type": "Expected a JSON object.", "model_type": "Expected a JSON object.",
        "string_type": "Expected a string.", "int_type": "Expected an integer.",
        "float_type": "Expected a number.", "bool_type": "Expected a boolean.",
        "tuple_type": "Expected a JSON array.", "list_type": "Expected a JSON array.",
        "extra_forbidden": "An undeclared field was supplied.",
        "literal_error": "Use a value from the declared enumeration.",
        "union_tag_invalid": "Use a source kind from the declared enumeration.",
        "union_tag_not_found": "The declared discriminator field is missing.",
    }
    names = schema_field_names(schema)
    result = []
    errors = error.errors(include_input=True, include_context=True, include_url=False)
    for item in errors[:32]:
        kind = item["type"]
        # Invalid children can make Pydantic's validated array look empty even
        # when the supplied array meets min_length. Report the child failures.
        if (kind == "too_short" and isinstance(item.get("input"), (list, tuple))
                and len(item["input"]) >= item.get("ctx", {}).get("min_length", 1)
                and any(len(child["loc"]) > len(item["loc"])
                        and child["loc"][:len(item["loc"])] == item["loc"] for child in errors)):
            continue
        cause = item.get("ctx", {}).get("error")
        explicit = cause.details if isinstance(cause, SemanticRuleViolation) else ()
        if explicit and all(isinstance(detail, DeclaredDiagnostic) for detail in explicit):
            for detail in explicit:
                result.append(contract_diagnostic("invalid_arguments" if phase == "tool_arguments" else detail["code"],
                    phase=phase, affected_action=action, repairable=True,
                    path=diagnostic_path(item["loc"], names) + detail["path"].removeprefix("$"),
                    message=detail["message"], error_type=kind))
            continue
        message = messages.get(kind, "Value violates the declared type, bounds, or field relationship.")
        if kind == "value_error" and isinstance(cause, ValueError):
            # Pydantic has already classified this as a declared model rejection.
            # Keep its bounded reason, without serializing the supplied value,
            # exception context or traceback. Ordinary runtime exceptions are not
            # handled here and remain engineering failures.
            message = str(cause)[:512] or message
            supplied = item.get("input")
            if isinstance(supplied, str) and 0 < len(supplied) <= 512:
                # Retain the rule's explanation while removing an echoed value.
                # Merely omitting Pydantic's input field does not remove echoes
                # embedded by a custom validator in its exception message.
                message = re.sub(r"(?<!\w)" + re.escape(supplied) + r"(?!\w)",
                    "[redacted input]", message)
        # These two values are generated from the declared literal/tag schema;
        # the supplied input and arbitrary custom error context are never copied.
        if kind in {"literal_error", "union_tag_invalid"}:
            expected = item.get("ctx", {}).get("expected" if kind == "literal_error" else "expected_tags")
            if isinstance(expected, str):
                message = ("Supported values: " + expected)[:512]
        bounds = {
            "less_than_equal": ("le", "Value must be at most {}."),
            "less_than": ("lt", "Value must be less than {}."),
            "greater_than_equal": ("ge", "Value must be at least {}."),
            "greater_than": ("gt", "Value must be greater than {}."),
            "too_long": ("max_length", "Maximum length is {}."),
            "too_short": ("min_length", "Minimum length is {}."),
            "string_too_long": ("max_length", "Maximum length is {}."),
            "string_too_short": ("min_length", "Minimum length is {}."),
        }
        if kind in bounds:
            key, template = bounds[kind]
            value = item.get("ctx", {}).get(key)
            if type(value) in (int, float):
                message = template.format(value)[:512]
        result.append(contract_diagnostic(
            "invalid_arguments" if phase == "tool_arguments" else "output_invalid",
            phase=phase, affected_action=action, repairable=True,
            path=diagnostic_path(item["loc"], names), error_type=kind, message=message))
    return tuple(result)



def sanitize_diagnostic_details(items: Iterable[Any], *, schema: Any,
                                rules: Iterable[str] = (), phase: str = "output_payload",
                                action: str = "submit", rule_phases: Mapping[str, str] | None = None) -> tuple[dict[str, Any], ...]:
    names = schema_field_names(schema) | {"payload", "handoff", "schema_version"}
    allowed_rules = set(rules)
    result = []
    for item in tuple(items)[:16]:
        if not isinstance(item, Mapping): continue
        rule = item.get("rule_id")
        if rule is not None and rule not in allowed_rules: continue
        parts = re.findall(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+|key)\]", str(item.get("path", "$"))[:512])
        # Explicit details have already bounded their schema fields at the owner;
        # they may include a declared workspace prefix outside the payload schema.
        path_names = names | {field for field, _ in parts} if isinstance(item, DeclaredDiagnostic) else names
        path = diagnostic_path((int(index) if index.isdigit() else field or "[key]" for field,index in parts), path_names)
        code = item.get("code", "output_invalid" if action == "submit" else "runtime_failure")
        if not isinstance(code,str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}",code): code="runtime_failure"
        error_type = item.get("type")
        if not isinstance(error_type,str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}",error_type): error_type=None
        resolved_phase = (rule_phases or {}).get(rule, phase)
        # Only the explicit in-process constructor marks a message as safe. An
        # arbitrary error dictionary passing the wire schema does not do so.
        description = rules.get(rule) if isinstance(rules, Mapping) else None
        if isinstance(item, DeclaredDiagnostic):
            message = item["message"]
            if description and message == "Value violates the declared type, bounds, or field relationship.":
                message = description
        else:
            message = description or ("Required field is missing." if error_type == "missing" else
                "Value violates the declared type, bounds, or field relationship." if error_type else
                "The declared requirement was not satisfied.")
        result.append(contract_diagnostic(code, phase=resolved_phase, affected_action=action,
            path=path, repairable=(item.get("repairable", resolved_phase in {"input_admission","tool_arguments","output_payload","output_context"}) if isinstance(item, DeclaredDiagnostic) else
                                  resolved_phase in {"input_admission","tool_arguments","output_payload","output_context"}),
            message=message[:512], rule_id=rule, error_type=error_type))
    return tuple(result)


def semantic_contract(*rules: SemanticRuleSpec) -> str:
    contract = SemanticContractSpec(rules=rules)
    issue = contract.issue()
    if issue is not None:
        raise ValueError(issue)
    return json.dumps(
        contract.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def parse_semantic_contract(raw: str | bytes) -> SemanticContractSpec:
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"schema_version", "rules"}:
        raise ValueError("semantic contract shape is invalid")
    raw_rules = value["rules"]
    if not isinstance(raw_rules, list):
        raise ValueError("semantic contract rules must be an array")
    rules = []
    for raw_rule in raw_rules:
        fields = {"rule_id", "description", "output_paths", "required_inputs"}
        if not isinstance(raw_rule, dict) or set(raw_rule) != fields:
            raise ValueError("semantic rule shape is invalid")
        paths, required = raw_rule["output_paths"], raw_rule["required_inputs"]
        if not isinstance(paths, list) or not isinstance(required, list):
            raise ValueError("semantic rule collections must be arrays")
        rules.append(
            SemanticRuleSpec(
                rule_id=raw_rule["rule_id"],
                description=raw_rule["description"],
                output_paths=tuple(paths),
                required_inputs=tuple(required),
            )
        )
    return SemanticContractSpec(
        schema_version=value["schema_version"], rules=tuple(rules)
    )


def semantic_contract_issue(
    raw: str | bytes, input_min_items: Mapping[str, int]
) -> tuple[str, str | None] | None:
    try:
        contract = parse_semantic_contract(raw)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return "semantic_contract_invalid", None
    issue = contract.issue()
    if issue is not None:
        return issue, None
    for rule in contract.rules:
        if not set(rule.required_inputs) <= set(input_min_items):
            return "semantic_rule_input_unknown", rule.rule_id
        if any(input_min_items[name] == 0 for name in rule.required_inputs):
            return "semantic_rule_optional_input_required", rule.rule_id
    return None


def output_checker_contract_issue(
    raw: str | bytes | None,
    port: OutputPortSpec,
    input_min_items: Mapping[str, int],
    *,
    agent_output: bool,
) -> tuple[str, str | None] | None:
    if raw is None:
        return ("agent_semantic_contract_missing", port.name) if agent_output else None
    issue = semantic_contract_issue(raw, input_min_items)
    if issue is not None:
        return issue
    rules = {rule.rule_id: rule for rule in parse_semantic_contract(raw).rules}
    for checker, rule_id, phase in (
        (port.validator, port.validator_rule_id, "payload"),
        (port.context_validator, port.context_rule_id, "context"),
    ):
        if agent_output and checker is not None and rule_id is None:
            return "checker_rule_missing", port.name
        if rule_id is None:
            continue
        rule = rules.get(rule_id)
        if rule is None:
            return "checker_rule_unknown", rule_id
        if phase == "payload" and rule.required_inputs:
            return "payload_rule_input_invalid", rule_id
        if phase == "context" and not set(rule.required_inputs) <= set(
            port.context_sources
        ):
            return "context_rule_input_invalid", rule_id
    return None


def direct_revision_ports(
    compiled: CompiledOperation | OperationSpec,
    *, plugin_id: str | None = None,
) -> tuple[Any, OutputPortSpec] | None:
    """Recognize the complete-object revision shape declared by OperationSpec."""

    spec = compiled if isinstance(compiled, OperationSpec) else compiled.spec
    owner = plugin_id if isinstance(compiled, OperationSpec) else compiled.plugin_id
    bases = tuple(port for port in spec.inputs if port.usage == "revision_base")
    primary = tuple(port for port in spec.outputs if port.collection is None)
    review = spec.review
    base_cardinality = (
        (bases[0].min_items, bases[0].max_items) if len(bases) == 1 else None
    )
    if (
        spec.executor.kind != "agent"
        or spec.consequence != "scientific"
        or len(bases) != 1
        or base_cardinality not in {(0, 1), (1, 1)}
        or bases[0].exposure == "handoff_only"
        or len(primary) != 1
        or any(port.collection is not None for port in spec.outputs)
        or review is None
        or review.reviewer_operation is None
        or review.reviewer_input_port is None
        or review.subject_outputs != (primary[0].name,)
    ):
        return None
    base = bases[0]
    output = primary[0]

    if base_cardinality == (0, 1):
        requests = tuple(
            port for port in spec.inputs if port.usage == "change_request"
        )
        admission = spec.input_admission
        if (
            len(requests) != 1
            or (requests[0].min_items, requests[0].max_items) != (0, 1)
            or admission is None
            or set(admission.member_ports) != {base.name, requests[0].name}
            or len(admission.member_ports) != 2
            or admission.approval_kind is not None
            or admission.approval_subject_ports
            or admission.accepted_options
            or admission.accepted_provider_operations
            or review.max_revisions <= 0
            or review.progress_fingerprint is None
        ):
            return None

    def component_key(reference: Any) -> str:
        return f"{reference.plugin_id or owner}:{reference.component_id}"

    if (
        output.min_items != 1
        or output.max_items != 1
        or output.schema_id != base.schema_id
        or output.media_types != base.media_types
        or component_key(output.codec) != component_key(base.codec)
        or component_key(output.schema_resource)
        != component_key(base.schema_resource)
    ):
        return None
    return base, output


def active_direct_revision_ports(
    compiled: CompiledOperation,
    actual_bound_port_names: Iterable[str],
) -> tuple[Any, OutputPortSpec] | None:
    """Return the direct-revision contract only when this call binds its base."""

    direct = direct_revision_ports(compiled)
    if direct is None:
        return None
    return direct if direct[0].name in set(actual_bound_port_names) else None


def operation_input_validation_contract(
    operation: CompiledOperation | OperationSpec,
) -> dict[str, Any] | None:
    """Same admission description in the scheduler catalog and frozen Worker schema."""
    spec = operation.spec if isinstance(operation, CompiledOperation) else operation
    return input_validation_projection(spec)


def _static_output_validation_contract(
    spec: OperationSpec, port: OutputPortSpec, plugin_id: str
) -> dict[str, Any]:
    inputs = {item.name: item for item in spec.inputs}
    source_projection = _evidence_source_projection_version(spec, port)
    context_sources = tuple(
        {
            "port": name,
            "required": inputs[name].min_items > 0 if name in inputs else False,
            **(
                {"usage": inputs[name].usage if name in inputs else "tool_evidence"}
                if source_projection is not None
                else {}
            ),
        }
        for name in port.context_sources
    )
    rules = [
        _rule("runtime.files", "Submit output/result.json; declared tool evidence is added only by the runtime." if any(p.collection is not None for p in spec.outputs) else "Submit exactly output/result.json."),
        _rule(
            "runtime.envelope",
            "The result file must be a valid RoleResultEnvelope JSON object.",
        ),
        _rule("runtime.schema", "The payload must satisfy this exact JSON Schema."),
        _rule(
            "runtime.size",
            "The canonical payload must fit the compiled output byte limit.",
        ),
    ]
    checkers = []
    if port.validator is not None:
        checkers.append(
            {
                "phase": "payload",
                "rule_id": port.validator_rule_id,
                "required_inputs": [],
                "optional_inputs": [],
            }
        )
    if port.context_validator is not None:
        checkers.append(
            {
                "phase": "context",
                "rule_id": port.context_rule_id,
                "required_inputs": [
                    item["port"] for item in context_sources if item["required"]
                ],
                "optional_inputs": [
                    item["port"] for item in context_sources if not item["required"]
                ],
            }
        )
    direct_revision = direct_revision_ports(spec, plugin_id=plugin_id)
    if direct_revision is not None:
        base = direct_revision[0]
        description = (
            "When the assignment binds the optional revision base, the complete "
            "revision must differ from that immutable base."
            if base.min_items == 0
            else "A complete revision must differ from its immutable base."
        )
        rules.append(
            _rule(
                "runtime.revision",
                description,
                (base.name,),
            )
        )
    return {
        "schema_version": 1,
        "operation_id": spec.operation_id,
        "operation_version": spec.version,
        "output_port": port.name,
        "max_output_bytes": min(
            port.max_item_bytes, spec.limits.max_output_bytes
        ),
        "context_sources": context_sources,
        "checkers": checkers,
        "rules": rules,
    }


def compile_output_contract(
    spec: OperationSpec, port: OutputPortSpec, *, plugin_id: str,
    implementations: Mapping[str, Any], evidence_ports: Iterable[str],
) -> Mapping[str, Any]:
    """Build static material before computing its Operation identity."""
    def resource(reference):
        return implementations[f"{reference.plugin_id or plugin_id}:{reference.component_id}"]
    schema = json.loads(resource(port.schema_resource))
    if port.collection is not None and port.name in evidence_ports:
        schema["x-scidiscovery-produced-by"] = "registered_tool"
    if _evidence_source_projection_version(spec, port) is not None:
        _project_evidence_source_schema(schema, port.evidence_paths, allowed_sources=None)
    if port.semantic_contract is not None:
        schema["x-scidiscovery-semantic-constraints"] = parse_semantic_contract(
            resource(port.semantic_contract)
        ).model_dump(mode="json")
    input_contract = operation_input_validation_contract(spec)
    if input_contract is not None:
        schema["x-scidiscovery-input-validation-contract"] = input_contract
    schema["x-scidiscovery-validation-contract"] = _static_output_validation_contract(
        spec, port, plugin_id
    )
    return freeze_json(schema)


def operation_output_validation_contract(
    compiled: CompiledOperation, port: OutputPortSpec
) -> dict[str, Any]:
    contract = json_projection(compiled.output_contracts[port.name][
        "x-scidiscovery-validation-contract"
    ])
    contract["operation_digest"] = compiled.digest
    return contract


def operation_port_json_schema(
    compiled: CompiledOperation,
    port: OutputPortSpec,
    *,
    input_source_ports: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the exact Worker-visible schema and its derived contracts."""

    schema = json_projection(compiled.output_contracts[port.name])
    from .operations.tooling import tool_evidence_ports
    evidence_ports = tool_evidence_ports(compiled)
    if evidence_ports and input_source_ports is not None:
        schema['x-scidiscovery-readable-evidence'] = [
            {'alias': name, 'port': source_port,
             'origin': 'registered_tool' if source_port in evidence_ports else 'bound_artifact'}
            for name, source_port in sorted(input_source_ports.items())]
    projection = _evidence_source_projection_version(compiled.spec, port)
    if projection is not None:
        inputs = {item.name: item for item in compiled.spec.inputs}
        allowed_sources: tuple[str, ...] | None = None
        if input_source_ports is not None:
            unknown = set(input_source_ports.values()) - set(inputs) - set(evidence_ports)
            if unknown:
                raise ValueError("source binding references an unknown input port")
            allowed_sources = tuple(
                sorted(
                    source_name
                    for source_name, port_name in input_source_ports.items()
                    if port_name in evidence_ports or (port_name in port.context_sources
                    and inputs[port_name].exposure != "handoff_only")
                )
            )
        _project_evidence_source_schema(
            schema, port.evidence_paths, allowed_sources=allowed_sources
        )
    schema["x-scidiscovery-validation-contract"] = (
        operation_output_validation_contract(compiled, port)
    )
    return schema


def _evidence_source_projection_version(
    spec: OperationSpec, port: OutputPortSpec
) -> str | None:
    """Select the one source-enum projection from declarative port semantics."""

    if (
        spec.executor.kind == "agent"
        and port.collection is None
        and port.evidence_paths
        and any(
            item.usage == "evidence_inventory"
            and item.exposure != "handoff_only"
            for item in spec.inputs
        )
    ):
        return "evidence-source-enum.v2"
    return None


def _project_evidence_source_schema(
    schema: dict[str, Any],
    evidence_paths: tuple[str, ...],
    *,
    allowed_sources: tuple[str, ...] | None,
) -> None:
    """Validate evidence paths and optionally bind their source-key domain."""

    def pointer_tokens(pointer: str) -> tuple[str, ...]:
        return tuple(
            token.replace("~1", "/").replace("~0", "~")
            for token in pointer.removeprefix("/").split("/")
        )

    def resolve(node: Any, seen: frozenset[str] = frozenset()) -> dict[str, Any]:
        if not isinstance(node, dict):
            raise ValueError("evidence schema node is not an object")
        reference = node.get("$ref")
        if reference is None:
            return node
        if (
            not isinstance(reference, str)
            or not reference.startswith("#/$defs/")
            or reference in seen
        ):
            raise ValueError("evidence schema reference is invalid")
        current: Any = schema
        for token in pointer_tokens(reference.removeprefix("#")):
            if not isinstance(current, dict) or token not in current:
                raise ValueError("evidence schema reference is unresolved")
            current = current[token]
        return resolve(current, seen | {reference})

    for pointer in evidence_paths:
        current: Any = schema
        for token in pointer_tokens(pointer):
            resolved = resolve(current)
            properties = resolved.get("properties")
            if not isinstance(properties, dict) or token not in properties:
                raise ValueError("evidence path is absent from the output schema")
            current = properties[token]
        evidence = resolve(current)
        items = evidence.get("items")
        if evidence.get("type") != "array" or not isinstance(items, dict):
            raise ValueError("evidence path must identify an object array")
        item_schema = resolve(items)
        properties = item_schema.get("properties")
        if not isinstance(properties, dict) or "source_key" not in properties:
            raise ValueError("evidence items must declare source_key")
        source_key = resolve(properties["source_key"])
        if source_key.get("type") != "string":
            raise ValueError("evidence source_key must be a string")
        if allowed_sources is None:
            continue
        if not allowed_sources:
            evidence["maxItems"] = 0
            continue
        evidence["items"] = {
            "allOf": [
                items,
                {
                    "properties": {
                        "source_key": {"enum": list(allowed_sources)},
                    },
                    "required": ["source_key"],
                    "type": "object",
                },
            ]
        }


def _rule(
    rule_id: str, description: str, required_inputs: tuple[str, ...] = ()
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "description": description,
        "output_paths": ["/"],
        "required_inputs": list(required_inputs),
    }


__all__ = [
    "SemanticRuleViolation",
    "active_direct_revision_ports",
    "direct_revision_ports",
    "operation_output_validation_contract",
    "operation_input_validation_contract",
    "operation_port_json_schema",
    "output_checker_contract_issue",
    "parse_semantic_contract",
    "semantic_contract",
    "semantic_contract_issue",
]
