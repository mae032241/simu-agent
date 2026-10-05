from __future__ import annotations

import pytest
from pydantic import ValidationError

from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN as PLUGIN
from scidiscovery.artifact_agent.schema.role_result import RoleHandoff
from scidiscovery.artifact_agent.schema.run_signal import SchedulerSignal
from scidiscovery.operations.spec import InputDerivationSpec, OperationSpec, canonical_digest, canonical_json, json_projection


def test_operation_spec_is_the_frozen_declarative_contract() -> None:
    with pytest.raises(ValidationError):
        PLUGIN.operations[0].operation_id = "changed"  # type: ignore[misc]


def test_canonical_json_and_digest_are_stable_and_content_sensitive() -> None:
    operation = PLUGIN.operations[0]
    assert canonical_json(operation) == canonical_json(operation)
    assert canonical_digest(operation) == canonical_digest(operation)
    revised = operation.model_copy(update={"version": "2"})
    assert canonical_digest(revised) != canonical_digest(operation)


def test_extra_input_defaults_are_not_representable() -> None:
    values = PLUGIN.operations[0].model_dump(mode="python")
    with pytest.raises(ValidationError):
        OperationSpec(**values, allow_additional_inputs=True)  # type: ignore[call-arg]


def test_original_text_opt_in_preserves_existing_derivation_projection() -> None:
    rule = InputDerivationSpec(anchor_port='subject', source_paths=((),), source_schemas=('goal',))
    previous = rule.model_dump(mode='json', exclude={'source_original_text'})
    assert json_projection(rule) == previous
    assert canonical_digest(rule) == canonical_digest(previous)
    enabled = rule.model_copy(update={'source_original_text': True})
    assert json_projection(enabled)['source_original_text'] is True
    assert canonical_digest(enabled) != canonical_digest(rule)


def test_worker_handoff_items_are_transport_metadata_not_control_fields() -> None:
    for model in (RoleHandoff, SchedulerSignal):
        for field in ("assumptions", "missing_inputs", "next_actions"):
            value = model(
                verdict="revise",
                summary="A bounded correction is needed.",
                **{field: ("", "x" * 513)},
            )
            assert getattr(value, field) == ("", "x" * 513)
