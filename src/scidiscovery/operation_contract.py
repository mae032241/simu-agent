"""Single-source helpers for compiled Agent output contracts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, Mapping

from .operations.spec import (
    CompiledOperation,
    OperationSpec,
    OutputPortSpec,
    SemanticContractSpec,
    SemanticRuleSpec,
)


class SemanticRuleViolation(ValueError):
    """An intentional Worker-correctable rejection by a bound semantic checker."""


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
    compiled: CompiledOperation,
) -> tuple[Any, OutputPortSpec] | None:
    """Recognize the complete-object revision shape declared by OperationSpec."""

    spec = compiled.spec
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
        return f"{reference.plugin_id or compiled.plugin_id}:{reference.component_id}"

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


def operation_output_validation_contract(
    compiled: CompiledOperation, port: OutputPortSpec
) -> dict[str, Any]:
    inputs = {item.name: item for item in compiled.spec.inputs}
    source_projection = _evidence_source_projection_version(compiled.spec, port)
    context_sources = tuple(
        {
            "port": name,
            "required": inputs[name].min_items > 0,
            **(
                {"usage": inputs[name].usage}
                if source_projection is not None
                else {}
            ),
        }
        for name in port.context_sources
    )
    rules = [
        _rule("runtime.files", "Submit exactly output/result.json."),
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
    direct_revision = direct_revision_ports(compiled)
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
        "operation_id": compiled.spec.operation_id,
        "operation_version": compiled.spec.version,
        "operation_digest": compiled.digest,
        "output_port": port.name,
        "max_output_bytes": min(
            port.max_item_bytes, compiled.spec.limits.max_output_bytes
        ),
        "context_sources": context_sources,
        "checkers": checkers,
        "rules": rules,
    }


def operation_port_json_schema(
    compiled: CompiledOperation,
    port: OutputPortSpec,
    *,
    input_source_ports: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the exact Worker-visible schema and its derived contracts."""

    reference = port.schema_resource
    key = f"{reference.plugin_id or compiled.plugin_id}:{reference.component_id}"
    schema = json.loads(compiled.implementations[key])
    projection = _evidence_source_projection_version(compiled.spec, port)
    if projection is not None:
        inputs = {item.name: item for item in compiled.spec.inputs}
        allowed_sources: tuple[str, ...] | None = None
        if input_source_ports is not None:
            unknown = set(input_source_ports.values()) - set(inputs)
            if unknown:
                raise ValueError("source binding references an unknown input port")
            allowed_sources = tuple(
                sorted(
                    source_name
                    for source_name, port_name in input_source_ports.items()
                    if inputs[port_name].usage == "evidence_inventory"
                    and inputs[port_name].exposure != "handoff_only"
                )
            )
        _project_evidence_source_schema(
            schema, port.evidence_paths, allowed_sources=allowed_sources
        )
    if port.semantic_contract is not None:
        reference = port.semantic_contract
        key = f"{reference.plugin_id or compiled.plugin_id}:{reference.component_id}"
        contract = parse_semantic_contract(compiled.implementations[key])
        schema["x-scidiscovery-semantic-constraints"] = contract.model_dump(
            mode="json"
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
        return "evidence-source-enum.v1"
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
    "operation_port_json_schema",
    "output_checker_contract_issue",
    "parse_semantic_contract",
    "semantic_contract",
    "semantic_contract_issue",
]
