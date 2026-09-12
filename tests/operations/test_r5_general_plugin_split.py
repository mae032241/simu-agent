from __future__ import annotations

import tomllib
from pathlib import Path

from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN
from scidiscovery.operations.catalog import compile_catalog


def test_general_science_entry_point_compiles_unique_declarations() -> None:
    repository = Path(__file__).resolve().parents[2]
    project = tomllib.loads((repository / "pyproject.toml").read_text())
    assert project["project"]["entry-points"]["scidiscovery.plugins"]["general_science"] == "scidiscovery.general_science_plugin:PLUGIN"
    assert len(PLUGIN.components) == len({item.component_id for item in PLUGIN.components})
    assert len(PLUGIN.operations) == len({item.operation_id for item in PLUGIN.operations})
    compiled = compile_catalog((CORE_PLUGIN, PLUGIN))
    assert set(compiled.operation_ids()) == {item.operation_id for item in PLUGIN.operations}


def test_general_science_public_component_api() -> None:
    expected = {
        "json_codec",
        "opaque_codec",
        "intake_validator",
        "intake_source_context",
        "audit_validator",
        "evidence_audit_context",
        "evidence_agent",
        "auditor_agent",
        "workspace",
        "pdf_extract_tool",
        "wildcard_schema",
        "opaque_schema",
        "intake_semantic_contract",
        "evidence_audit_semantic_contract",
        "scientific_intake_schema",
        "scientific_foundation_schema",
        "hypothesis_schema",
        "critic_review_schema",
        "evidence_audit_schema",
        "auditor_prompt",
        "experiment_portfolio_schema",
        "research_objective_schema",
        "scientific_review_schema",
    }
    assert expected <= {item.component_id for item in PLUGIN.components if item.public}
