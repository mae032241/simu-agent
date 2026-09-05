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
from ...operation_contract import SemanticRuleViolation
from ...operations.spec import CompiledOperation
from ..schema.common import canonical_json
from ..schema.role_result import parse_role_result
from ..schema.run_signal import SchedulerSignal
from .local_workspace import SealedWorkspace, WorkspaceError


class RunOutputError(RuntimeError):
    def __init__(
        self, message: str, *, details: tuple[dict[str, str], ...] = ()
    ) -> None:
        super().__init__(message)
        self.details = details


class RunCheckerError(RuntimeError):
    """A compiled plugin checker contradicted its declared output contract."""


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
) -> ValidatedRunOutput:
    """Validate the one primary result without changing control state."""

    if set(input_source_ports) != set(input_bytes):
        raise RunCheckerError("input source bindings differ from the exact Run inputs")
    input_port_names = tuple(input_source_ports.values())
    if sealed.run_id == "" or sealed.backend == "":
        raise RunOutputError("sealed workspace identity is invalid")
    port = operation_primary_output(compiled)
    contract = operation_output_validation_contract(compiled, port)
    declared_rule_ids = frozenset(
        item["rule_id"] for item in contract["rules"] + contract["checkers"]
    )
    paths = {item.relative_path for item in sealed.files}
    if paths != {"result.json"}:
        raise RunOutputError(
            "this minimal Run accepts exactly output/result.json",
            details=_with_rule(
                ({"path": "$.files", "message": "unexpected output file set", "type": "value_error"},),
                "runtime.files",
                declared_rule_ids,
            ),
        )
    descriptor = sealed.files[0]
    path = sealed.root / descriptor.relative_path
    try:
        raw_envelope = path.read_bytes()
    except OSError as error:
        raise WorkspaceError("sealed result is unreadable") from error
    try:
        decoded = json.loads(raw_envelope.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunOutputError(
            "worker output is not valid UTF-8 JSON",
            details=_with_rule(
                ({"path": "$", "message": str(error), "type": "json_invalid"},),
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
                _validation_details(error), "runtime.envelope", declared_rule_ids
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
            raise RunOutputError("revision base is absent from the exact Run inputs")
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
                    _prefix(_validation_details(error), "$.payload"),
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
        sources = {
            name: content
            for name, content in input_bytes.items()
            if input_source_ports[name] in port.context_sources
        }
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
                    _prefix(_validation_details(error), "$.payload"),
                    port.context_rule_id,
                    declared_rule_ids,
                ),
            ) from error
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
            next_action_kind=handoff.next_action_kind,
        ),
        media_type=port.media_types[0],
        kind=port.kind,
        schema_id=port.schema_id,
        payload_schema_version=port.payload_schema_version,
        output_port=port.name,
    )


def _validation_details(error: Exception) -> tuple[dict[str, str], ...]:
    if isinstance(error, ValidationError):
        return tuple(
            {
                "path": ".".join(str(part) for part in item["loc"]) or "$",
                "message": str(item["msg"]),
                "type": str(item["type"]),
            }
            for item in error.errors(include_url=False)[:32]
        )
    return ({"path": "$", "message": str(error), "type": "value_error"},)


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
    details = tuple(
        {
            "path": _json_path(error.absolute_path),
            "message": error.message,
            "type": f"json_schema.{error.validator}",
        }
        for error in errors[:32]
    )
    raise RunOutputError(
        "operation payload does not satisfy its JSON Schema",
        details=_with_rule(details, "runtime.schema", declared_rule_ids),
    )


def _json_path(parts: Any) -> str:
    path = "$.payload"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _prefix(
    details: tuple[dict[str, str], ...], prefix: str
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            **item,
            "path": (
                prefix
                if item["path"] == "$"
                else f"{prefix}.{item['path'].removeprefix('$.')}"
            ),
        }
        for item in details
    )


def _with_rule(
    details: tuple[dict[str, str], ...],
    rule_id: str,
    declared_rule_ids: frozenset[str],
) -> tuple[dict[str, str], ...]:
    if rule_id not in declared_rule_ids:
        raise RunCheckerError("validator used an undeclared compiled rule")
    return tuple({**item, "rule_id": rule_id} for item in details)


__all__ = [
    "RunCheckerError",
    "RunOutputError",
    "ValidatedRunOutput",
    "validate_run_output",
]
