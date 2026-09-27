"""Pure validation of one sealed compiled-Operation result."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import ValidationError

from ...operations.invoke import (
    active_direct_revision_ports,
    operation_output_validation_contract,
    operation_port_json_schema,
    operation_primary_output,
)
from ...operation_contract import (SemanticRuleViolation, DeclaredDiagnostic, validation_diagnostics, diagnostic_path,
                                  schema_field_names, contract_diagnostic)
from ...operations.spec import CompiledOperation
from ..schema.common import canonical_json
from ..schema.role_result import RoleResultEnvelope, parse_role_result
from ..schema.run_signal import SchedulerSignal
from .local_workspace import SealedWorkspace, WorkspaceError
from ...plugin_runtime.diagnostics import RunOutputError, RunCheckerError


from ...operations.input_validation import InputBindingDescriptor, ValidationSources, BoundSourceError


@dataclass(frozen=True, slots=True)
class ValidatedRunOutput:
    content: bytes
    signal: SchedulerSignal
    media_type: str
    kind: str
    schema_id: str
    payload_schema_version: int
    output_port: str


def validate_run_output(
    compiled: CompiledOperation,
    sealed: SealedWorkspace,
    *,
    input_source_ports: Mapping[str, str],
    input_bytes: Mapping[str, bytes],
    input_binding_descriptors: Mapping[str, InputBindingDescriptor] | None = None,
    validation_deadline: float | None = None,
    tool_snapshot: bytes | None = None,
    reference_calculation_resolver=None,
) -> ValidatedRunOutput:
    """Validate the one primary result without changing control state."""

    if set(input_source_ports) != set(input_bytes):
        raise RunCheckerError("input source bindings differ from the exact Run inputs")
    if input_binding_descriptors is not None:
        if set(input_binding_descriptors) != set(input_bytes):
            raise RunCheckerError("input binding descriptors differ from the exact Run inputs")
        if any(not isinstance(descriptor, InputBindingDescriptor)
               or descriptor.source_name != name
               or descriptor.port_name != input_source_ports[name]
               for name, descriptor in input_binding_descriptors.items()):
            raise RunCheckerError("output context descriptor wiring is invalid")
    input_port_names = tuple(input_source_ports.values())
    if sealed.run_id == "" or sealed.backend == "":
        raise RunCheckerError("sealed workspace identity is invalid", category="integrity_failure")
    port = operation_primary_output(compiled)
    contract = operation_output_validation_contract(compiled, port)
    declared_rule_ids = frozenset(
        item["rule_id"] for item in contract["rules"] + contract["checkers"]
    )
    paths = {item.relative_path for item in sealed.files}
    expected_paths = {"result.json"} | ({"tool-evidence.json"} if tool_snapshot is not None else set())
    if paths != expected_paths:
        raise RunOutputError(
            "Keep output/result.json and runtime receipts only. Move derived files to scratch/ and publish them with worker_publish_files when available; do not embed files in narrative fields.",
            details=_with_rule(
                ({"path": "$.files", "message": "unexpected output file set: " + ", ".join(sorted(paths - expected_paths))[:512], "type": "value_error"},),
                "runtime.files",
                declared_rule_ids,
            ),
        )
    if tool_snapshot is not None:
        from .tool_evidence import scientific_evidence_projection
        expected_snapshot = scientific_evidence_projection(tool_snapshot)
        if (sealed.root / "tool-evidence.json").read_bytes() != expected_snapshot:
            raise RunCheckerError("tool evidence snapshot differs", category="integrity_failure")
    descriptor = next(item for item in sealed.files if item.relative_path == "result.json")
    path = sealed.root / descriptor.relative_path
    try:
        raw_envelope = path.read_bytes()
    except OSError as error:
        raise WorkspaceError("sealed result is unreadable") from error
    try:
        decoded = json.loads(raw_envelope.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        reason = (f"Invalid JSON: {error.msg} (line {error.lineno}, column {error.colno})."
                  if isinstance(error, json.JSONDecodeError) else
                  f"Invalid UTF-8 at byte {error.start}: {error.reason}.")
        raise RunOutputError(
            "worker output is not valid UTF-8 JSON",
            details=_with_rule(
                ({"path": "$", "message": reason, "type": "json_invalid"},),
                "runtime.envelope",
                declared_rule_ids,
            ),
        ) from error
    try:
        result = parse_role_result(decoded)
    except ValidationError as error:
        raise RunOutputError(
            "worker output must use the role result envelope",
            details=_with_rule(
                _validation_details(error, schema=RoleResultEnvelope.model_json_schema()), "runtime.envelope", declared_rule_ids
            ),
        ) from error
    if not isinstance(result.payload, dict):
        raise RunOutputError(
            "operation JSON output payload must be an object",
            details=_with_rule(
                (
                    {
                        "path": "$.payload",
                        "message": "payload must be an object",
                        "type": "object_type",
                    },
                ),
                "runtime.schema",
                declared_rule_ids,
            ),
        )
    _validate_payload_schema(
        result.payload,
        compiled,
        port,
        declared_rule_ids,
        input_source_ports=input_source_ports,
    )
    raw = canonical_json(result.payload)
    codec_key = f"{port.codec.plugin_id or compiled.plugin_id}:{port.codec.component_id}"
    try:
        encoded = compiled.implementations[codec_key](raw)
    except Exception as error:
        raise RunCheckerError("output codec rejected a schema-valid payload") from error
    if type(encoded) is not bytes:
        raise RunCheckerError("output codec returned non-bytes")
    direct_revision = active_direct_revision_ports(compiled, input_port_names)
    if direct_revision is not None:
        base_content = input_bytes.get(direct_revision[0].name)
        if base_content is None:
            raise RunCheckerError("revision base is absent from the exact Run inputs", category="admission_defect")
        if encoded == base_content:
            raise RunOutputError(
                "revision payload is unchanged",
                details=(
                    {
                        "path": "$.payload",
                        "message": "change at least one reviewed scientific field",
                        "type": "revision_unchanged",
                        "rule_id": "runtime.revision",
                    },
                ),
            )
    if port.validator is not None:
        key = (
            f"{port.validator.plugin_id or compiled.plugin_id}:"
            f"{port.validator.component_id}"
        )
        try:
            compiled.implementations[key](encoded)
        except SemanticRuleViolation as error:
            if port.validator_rule_id is None:
                raise RunCheckerError("payload checker has no compiled rule") from error
            raise RunOutputError(
                "operation output validator rejected the payload",
                details=_with_rule(
                    _prefix(_validation_details(error, schema=compiled.output_contracts[port.name]), "$.payload"),
                    port.validator_rule_id,
                    declared_rule_ids,
                ),
            ) from error
        except Exception as error:
            raise RunCheckerError("payload checker failed") from error
    try:
        normalized = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunCheckerError("output codec returned invalid JSON") from error
    if canonical_json(normalized) != encoded:
        raise RunCheckerError("output codec returned non-canonical JSON")
    assert compiled.spec.limits is not None
    if len(encoded) > min(port.max_item_bytes, compiled.spec.limits.max_output_bytes):
        raise RunOutputError(
            "scientific output exceeds its compiled byte limit",
            details=_with_rule(
                ({"path": "$.payload", "message": "payload exceeds compiled byte limit", "type": "too_long"},),
                "runtime.size",
                declared_rule_ids,
            ),
        )
    if port.context_validator is not None:
        key = (
            f"{port.context_validator.plugin_id or compiled.plugin_id}:"
            f"{port.context_validator.component_id}"
        )
        from ...operations.tooling import reference_source_ports
        readable_tool_ports = reference_source_ports(compiled)
        source_bytes = {
            name: content
            for name, content in input_bytes.items()
            if input_source_ports[name] in port.context_sources or input_source_ports[name] in readable_tool_ports
        }
        sources = ValidationSources(
            source_bytes,
            {
                name: descriptor
                for name, descriptor in (input_binding_descriptors or {}).items()
                if name in source_bytes
            },
            validation_deadline=validation_deadline,
            tool_snapshot=tool_snapshot,
            reference_calculation_resolver=reference_calculation_resolver,
        )
        try:
            compiled.implementations[key](
                result.payload,
                sources,
                result.handoff.model_dump(mode="json"),
            )
        except SemanticRuleViolation as error:
            if port.context_rule_id is None:
                raise RunCheckerError("context checker has no compiled rule") from error
            raise RunOutputError(
                "operation contextual output validator rejected the payload",
                details=_with_rule(
                    _prefix(_validation_details(error, schema=compiled.output_contracts[port.name], phase="output_context"), "$.payload"),
                    port.context_rule_id,
                    declared_rule_ids,
                ),
            ) from error
        except RunCheckerError:
            raise
        except TimeoutError as error:
            raise RunCheckerError("output checking tool timed out", category="tool_timeout") from error
        except BoundSourceError as error:
            raise RunCheckerError("accepted source could not be parsed", category="admission_defect") from error
        except Exception as error:
            raise RunCheckerError("context checker failed") from error
    handoff = result.handoff
    return ValidatedRunOutput(
        content=encoded,
        signal=SchedulerSignal(
            verdict=handoff.verdict,
            summary=handoff.summary,
            assumptions=handoff.assumptions,
            missing_inputs=handoff.missing_inputs,
            next_actions=handoff.next_actions,
        ),
        media_type=port.media_types[0],
        kind=port.kind,
        schema_id=port.schema_id,
        payload_schema_version=port.payload_schema_version,
        output_port=port.name,
    )


def _validation_details(error: Exception, *, schema: Any = None, phase: str = "output_payload") -> tuple[dict[str, Any], ...]:
    current = error
    semantic_reason = None
    for _ in range(4):
        if isinstance(current, SemanticRuleViolation) and current.details:
            return tuple((DeclaredDiagnostic if isinstance(item, DeclaredDiagnostic) else dict)(
                {**item, "phase":item.get("phase", phase) if isinstance(item, DeclaredDiagnostic)
                 and item.get("rule_id") else phase}) for item in current.details)
        if isinstance(current, ValidationError):
            return validation_diagnostics(current, schema=schema or {}, phase=phase, action="submit")
        if isinstance(current, SemanticRuleViolation) and semantic_reason is None:
            semantic_reason = str(current)[:512]
        if current.__cause__ is None:
            break
        current = current.__cause__
    if semantic_reason:
        return (contract_diagnostic("output_invalid", phase=phase, affected_action="submit",
            repairable=True, message=semantic_reason, error_type="value_error"),)
    return ({"path": "$", "message": "Declared semantic rule requires correction.", "type": "value_error", "phase":phase},)


def _validate_payload_schema(
    payload: dict[str, Any],
    compiled: CompiledOperation,
    port: Any,
    declared_rule_ids: frozenset[str],
    *,
    input_source_ports: Mapping[str, str],
) -> None:
    try:
        from jsonschema.validators import validator_for
        schema = operation_port_json_schema(
            compiled, port, input_source_ports=input_source_ports
        )
        validator_type = validator_for(schema)
        validator_type.check_schema(schema)
        errors = sorted(
            validator_type(schema).iter_errors(payload),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    except ImportError as error:
        raise RunCheckerError("JSON Schema runtime is unavailable") from error
    except Exception as error:
        module = type(error).__module__
        if module.startswith("jsonschema"):
            raise RunCheckerError("compiled output schema is invalid") from error
        raise RunCheckerError("compiled output schema projection failed") from error
    if not errors:
        return
    details = []
    names = schema_field_names(schema)
    for error in errors[:15]:
        parts = list(error.absolute_path)
        message = "Value does not satisfy the declared JSON Schema constraint."
        if error.validator == "required" and isinstance(error.instance, dict):
            missing = next((name for name in error.validator_value if name not in error.instance), None)
            if missing is not None:
                parts.append(missing)
            message = "Required field is missing."
        elif error.validator == "type":
            message = f"Expected JSON type: {error.validator_value}."
        elif error.validator in {"enum", "const"}:
            message = "Supported values: " + json.dumps(error.validator_value, ensure_ascii=False)
        elif error.validator in {"minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength"}:
            message = f"Declared {error.validator}: {error.validator_value}."
        elif error.validator == "additionalProperties":
            message = "An undeclared field was supplied."
        details.append(DeclaredDiagnostic({
            "path": diagnostic_path(parts, names, root="$.payload"),
            "message": message[:512], "type": f"json_schema.{error.validator}",
        }))
    from ...operation_contract import bounded_diagnostics
    details = bounded_diagnostics(details, total=len(errors), phase="output_payload", action="submit",
        deferred="Cross-field and source-reference checks were not evaluated.")
    raise RunOutputError(
        "operation payload does not satisfy its JSON Schema",
        details=_with_rule(tuple(details), "runtime.schema", declared_rule_ids),
    )


def _prefix(
    details: tuple[dict[str, str], ...], prefix: str
) -> tuple[dict[str, str], ...]:
    return tuple(
        (DeclaredDiagnostic if isinstance(item, DeclaredDiagnostic) else dict)({
            **item,
            "path": (
                prefix
                if item["path"] == "$"
                else prefix + item["path"][1:]
            ),
        })
        for item in details
    )


def _with_rule(
    details: tuple[dict[str, str], ...],
    rule_id: str,
    declared_rule_ids: frozenset[str],
) -> tuple[dict[str, str], ...]:
    if rule_id not in declared_rule_ids:
        raise RunCheckerError("validator used an undeclared compiled rule")
    # These details are created by this validation owner, not accepted from a
    # Worker error dictionary. Preserve their concrete reason through Run logging.
    result = []
    for item in details:
        owner = item.get("rule_id", rule_id) if isinstance(item, DeclaredDiagnostic) else rule_id
        if owner not in declared_rule_ids:
            raise RunCheckerError("validator used an undeclared compiled rule")
        result.append(DeclaredDiagnostic({**item, "rule_id": owner}))
    return tuple(result)


__all__ = [
    "InputBindingDescriptor",
    "ValidationSources",
    "RunCheckerError",
    "RunOutputError",
    "ValidatedRunOutput",
    "validate_run_output",
]
