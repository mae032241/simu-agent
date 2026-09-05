from __future__ import annotations

import re
from pathlib import Path

import pytest

from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt


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


def test_production_agent_operations_use_the_selected_codex_model() -> None:
    catalog = compile_installed_catalog()
    agent_models = {
        catalog.operation(operation_id).spec.executor.model
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
    }

    assert agent_models == {"gpt-5.6-sol"}


def test_scheduler_prompt_has_no_retired_generic_creation_path() -> None:
    prompt = load_scheduler_prompt()
    for retired in (
        'output_profile="scientific-paper-evidence"',
        'output_profile="curve-error-analysis"',
        'output_profile="structured-revision"',
        "scidiscovery.evidence-audit.figure-extraction.v1",
        "scidiscovery.scientific-revision.figure-extraction.v1",
        "ready_capabilities",
    ):
        assert retired not in prompt
    assert "scientific_inventory" in prompt
    assert "operation_catalog" in prompt
    assert "operation_preflight" in prompt
    assert "science.evidence.extract.figure.v1" not in prompt
    assert "tcad.parameter.evidence.extract.v1" not in prompt
    assert "device_parameter_evidence_auditor" not in prompt


def test_deleted_static_topology_and_context_tables_cannot_return() -> None:
    repository = Path(__file__).resolve().parents[2]
    deleted = (
        repository / "src/scidiscovery/scheduler_topology.py",
        repository / "src/scidiscovery/artifact_agent/core_context_policies.py",
        repository / "src/scidiscovery/artifact_agent/context_policy.py",
        repository / "plugins/tcad_artifact/tcad_artifact/context_policies.py",
    )
    assert all(not path.exists() for path in deleted)

    production_roots = (repository / "src", repository / "plugins")
    retired_authorities = (
        "scheduler_topology",
        "core_context_policies",
        "RoleRuntimeProfile",
        "role_runtime_profile",
    )
    for root in production_roots:
        for path in root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            assert all(name not in content for name in retired_authorities), path


def test_retired_tcad_cross_artifact_patch_protocol_cannot_return() -> None:
    repository = Path(__file__).resolve().parents[2]
    plugin_root = repository / "plugins/tcad_artifact"
    retired = (
        "DeckFilePatch",
        "ParameterBindingPatch",
        "DeckProjectPatch",
        "apply_deck_project_patch",
        "validate_deck_project_patch",
        "DECK_PATCH_PROFILE",
        "tcad.deck-project-apply-patch.v1",
    )
    for path in plugin_root.rglob("*"):
        if path.suffix not in {".py", ".md"}:
            continue
        content = path.read_text(encoding="utf-8")
        assert all(name not in content for name in retired), path


def test_scheduler_prompt_is_domain_neutral_and_catalog_driven() -> None:
    prompt = load_scheduler_prompt()
    operation_id = re.compile(
        r"\b(?:science|tcad|scidiscovery)\.[a-z0-9_.-]+\.v\d+\b"
    )

    assert operation_id.search(prompt) is None
    assert "operation_catalog" in prompt
    assert "operation_preflight" in prompt
    assert "operation_invoke" in prompt
    assert "scientific_inventory" in prompt
    for domain_token in (
        "TCAD",
        "InGaAs",
        "device parameter",
        "figure extraction",
        "curve score",
    ):
        assert domain_token.casefold() not in prompt.casefold()


def test_device_parameter_audit_is_owned_only_by_the_compiled_tcad_plugin() -> None:
    catalog = compile_installed_catalog()
    extraction = catalog.operation("tcad.parameter.evidence.extract.v1")
    expansion = catalog.operation("tcad.parameter.evidence.expand.v1")
    audit = catalog.operation("tcad.parameter.evidence.audit.v1")

    assert extraction.plugin_id == expansion.plugin_id == audit.plugin_id == "tcad_artifact"
    assert extraction.spec.executor.kind == audit.spec.executor.kind == "agent"
    assert expansion.spec.executor.kind == "transform"
    assert tuple(port.name for port in extraction.spec.outputs) == (
        "parameter_evidence_package",
    )
    assert all(port.collection is None for port in extraction.spec.outputs)
    assert tuple(port.name for port in expansion.spec.outputs) == (
        "scientific_intake",
        "parameter_requirements",
        "device_parameters",
        "source_catalog",
    )
    assert extraction.spec.review is None
    assert expansion.spec.review is not None
    assert expansion.spec.review.reviewer_operation == audit.spec.operation_id
    assert expansion.spec.review.reviewer_input_port == "scientific_intake"
    assert expansion.spec.review.subject_outputs == ("scientific_intake",)
    assert tuple(port.name for port in audit.spec.inputs) == (
        "parameter_evidence_package",
        "scientific_intake",
        "required_parameter_checklist",
        "parameter_requirements",
        "device_parameters",
        "source_catalog",
        "parameter_coverage",
        "source_material",
    )
    assert audit.spec.review is None
    assert "device_parameter_evidence_auditor" not in {
        item.operation_id for item in catalog.scheduler_projection()
    }
