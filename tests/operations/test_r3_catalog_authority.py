from __future__ import annotations

import re
from pathlib import Path

import pytest

from scidiscovery.operations.catalog import compile_installed_catalog


def test_public_actions_are_a_direct_projection_of_the_compiled_catalog() -> None:
    catalog = compile_installed_catalog()
    projection = catalog.scheduler_projection()
    public = tuple(item for item in projection if item.catalog_scope == "public")

    assert public
    assert {item.operation_id for item in public} == {
        operation_id
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.catalog_scope == "public"
    }
    assert not {item.operation_id for item in public}.intersection(
        {"ideator", "critic", "evidence_auditor", "experiment_designer"}
    )


def test_production_agent_operations_resolve_model_from_settings() -> None:
    catalog = compile_installed_catalog()
    agent_models = {
        catalog.operation(operation_id).spec.executor.model
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
    }

    assert agent_models == {None}


def test_complete_parameter_evidence_task_is_owned_by_tcad_plugin() -> None:
    catalog = compile_installed_catalog()
    extraction = catalog.operation("tcad.parameter.evidence.extract.v1")
    assert extraction.plugin_id == "tcad_artifact"
    assert extraction.spec.executor.kind == "agent"
    assert tuple(port.name for port in extraction.spec.outputs if port.kind == "parameter_evidence_package") == ("parameter_evidence_package",)
    assert extraction.spec.review is None
    assert {"tcad.parameter.evidence.expand.v1", "tcad.parameter.evidence.audit.v1"}.isdisjoint(catalog.operation_ids())
    assert tuple(port.name for port in extraction.spec.inputs) == (
        "required_parameter_checklist", "source_material", "previous_evidence", "user_context")
