from __future__ import annotations

import ast
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_agent_operations import AGENT_OPERATIONS
from scidiscovery.general_science_components import COMPONENTS
from scidiscovery.general_science_control_operations import CONTROL_OPERATIONS
from scidiscovery.general_science_experiment_components import (
    COMPONENTS as EXPERIMENT_COMPONENTS,
)
from scidiscovery.general_science_experiment_operations import (
    OPERATIONS as EXPERIMENT_OPERATIONS,
)
from scidiscovery.general_science_plugin import PLUGIN
from scidiscovery.operations.catalog import compile_catalog


REPOSITORY = Path(__file__).resolve().parents[2]
DECLARATION_MODULES = (
    "src/scidiscovery/general_science_resources.py",
    "src/scidiscovery/general_science_components.py",
    "src/scidiscovery/general_science_agent_operations.py",
    "src/scidiscovery/general_science_control_operations.py",
    "src/scidiscovery/general_science_experiment_components.py",
    "src/scidiscovery/general_science_experiment_operations.py",
)
PLUGIN_OWNER = "src/scidiscovery/general_science_plugin.py"
PLUGIN_SUCCESSORS = {
    PLUGIN_OWNER,
    "src/scidiscovery/general_science_resources.py",
    "src/scidiscovery/general_science_agent_operations.py",
    "src/scidiscovery/general_science_experiment_operations.py",
}
TRANSFORM_OWNER = "src/scidiscovery/general_transform_operations.py"
TRANSFORM_SUCCESSORS = {
    "src/scidiscovery/general_science_components.py",
    "src/scidiscovery/general_science_control_operations.py",
    "src/scidiscovery/general_science_experiment_components.py",
}


def test_general_science_has_one_entry_point_and_one_plugin_definition() -> None:
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())
    entry_points = project["project"]["entry-points"]["scidiscovery.plugins"]
    assert entry_points["general_science"] == (
        "scidiscovery.general_science_plugin:PLUGIN"
    )
    plugin_tree = ast.parse((REPOSITORY / PLUGIN_OWNER).read_text())
    assert sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PluginDefinition"
        for node in ast.walk(plugin_tree)
    ) == 1
    for relative in DECLARATION_MODULES:
        source = (REPOSITORY / relative).read_text()
        tree = ast.parse(source)
        assert "PluginDefinition" not in source
        assert "compile_catalog" not in source
        assert "entry_points" not in source
        assert all(
            not isinstance(node, (ast.Assign, ast.AnnAssign))
            or not any(
                isinstance(target, ast.Name) and target.id == "PLUGIN"
                for target in (
                    node.targets if isinstance(node, ast.Assign) else (node.target,)
                )
            )
            for node in tree.body
        )
    assert not (REPOSITORY / TRANSFORM_OWNER).exists()


def test_general_science_composition_is_complete_unique_and_frozen() -> None:
    assert isinstance(COMPONENTS, tuple)
    assert isinstance(AGENT_OPERATIONS, tuple)
    assert isinstance(CONTROL_OPERATIONS, tuple)
    assert isinstance(EXPERIMENT_COMPONENTS, tuple)
    assert isinstance(EXPERIMENT_OPERATIONS, tuple)
    assert PLUGIN.components == COMPONENTS + EXPERIMENT_COMPONENTS
    assert PLUGIN.operations == AGENT_OPERATIONS + CONTROL_OPERATIONS + EXPERIMENT_OPERATIONS
    # Lifecycle actions are compiler-owned, so the plugin no longer repeats
    # the former heartbeat component.
    assert len(PLUGIN.components) == len({item.component_id for item in PLUGIN.components}) == 61
    assert len(PLUGIN.operations) == len({item.operation_id for item in PLUGIN.operations}) == 15
    assert sum(item.catalog_scope == "public" for item in PLUGIN.operations) == 12
    assert sum(item.catalog_scope == "support" for item in PLUGIN.operations) == 3
    assert sum(item.executor.kind == "agent" for item in PLUGIN.operations) == 11
    assert sum(item.executor.kind == "transform" for item in PLUGIN.operations) == 3
    assert sum(item.executor.kind == "approval" for item in PLUGIN.operations) == 1

    compiled = compile_catalog((CORE_PLUGIN, PLUGIN))
    assert set(compiled.operation_ids()) == {
        item.operation_id for item in PLUGIN.operations
    }


def test_general_science_component_paths_match_their_actual_owner() -> None:
    for component in PLUGIN.components:
        module, separator, _ = component.implementation.partition(":")
        assert separator == ":"
        if component.kind == "resource":
            assert module in {
                "scidiscovery.general_science_resources",
                "scidiscovery.general_science_experiment_components",
            }
        elif component.kind == "worker_tool":
            assert module == "scidiscovery.artifact_agent.interfaces.mcp_worker_protocol"
        else:
            assert module in {
                "scidiscovery.general_science_components",
                "scidiscovery.general_science_experiment_components",
            }
    assert {item.component_id for item in PLUGIN.components if item.public} == {
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


def test_current_metrics_count_general_declaration_successors_once() -> None:
    metrics = json.loads(
        subprocess.run(
            [sys.executable, "scripts/r5_current_metrics.py"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    plugin = metrics["responsibilities"][PLUGIN_OWNER]
    transform = metrics["responsibilities"][TRANSFORM_OWNER]
    assert set(plugin["successor_paths"]) == PLUGIN_SUCCESSORS
    assert set(transform["successor_paths"]) == TRANSFORM_SUCCESSORS
    assert PLUGIN_SUCCESSORS.isdisjoint(TRANSFORM_SUCCESSORS)
    assert plugin["total_lines"] == sum(plugin["lines_by_path"].values())
    assert transform["total_lines"] == sum(transform["lines_by_path"].values())
    # These are complexity ceilings, not compatibility identities: later
    # evidence-backed deletion must remain allowed.
    assert plugin["total_lines"] <= 1130
    # ABI 14 adds explicit Worker-visible checker identities and descriptions;
    # these contract declarations are not new control branches or registries.
    assert transform["total_lines"] <= 1180
    assert plugin["total_lines"] + transform["total_lines"] <= 2310
