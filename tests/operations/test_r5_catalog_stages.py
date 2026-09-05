from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations import catalog as catalog_module


REPOSITORY = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY / "src/scidiscovery/operations/catalog.py"
STAGES = (
    "_normalize_declarations",
    "_resolve_component",
    "_validate_operation_contracts",
    "_validate_review_graph",
    "_build_compiled_catalog",
)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _digest_map(catalog: object) -> str:
    payload = json.dumps(
        {
            operation_id: catalog.operation(operation_id).digest
            for operation_id in catalog.operation_ids()
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def test_catalog_compile_is_only_a_five_stage_coordinator() -> None:
    tree = ast.parse(CATALOG_PATH.read_text())
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(STAGES) <= functions.keys()
    coordinator = functions["compile_catalog"]
    assert [type(node) for node in coordinator.body] == [
        ast.Assign,
        ast.Assign,
        ast.Assign,
        ast.Return,
    ]
    called = [
        node.func.id
        for statement in coordinator.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert called == [
        "_normalize_declarations",
        "_validate_operation_contracts",
        "_validate_review_graph",
        "_build_compiled_catalog",
    ]

    constructor_calls = sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CompiledCatalog"
        for node in ast.walk(tree)
    )
    assert constructor_calls == 1
    assert sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CompiledCatalog"
        for node in ast.walk(functions["_build_compiled_catalog"])
    ) == 1
    cached = [
        node.name
        for node in functions.values()
        if any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "lru_cache"
            for decorator in node.decorator_list
        )
    ]
    assert cached == ["compile_installed_catalog"]


def test_catalog_stages_are_compile_local_and_compose_the_same_catalog() -> None:
    before = ARCHITECTURE_TEST_PLUGIN.model_dump(mode="python")
    plugin_map, components = catalog_module._normalize_declarations(
        (ARCHITECTURE_TEST_PLUGIN,)
    )
    assert tuple(plugin_map) == ("architecture_fixture",)
    assert plugin_map is not catalog_module._normalize_declarations(
        (ARCHITECTURE_TEST_PLUGIN,)
    )[0]
    (
        parts,
        runtime_factories,
        runtime_configuration_digests,
        runtime_identity_digests,
        used,
    ) = catalog_module._validate_operation_contracts(plugin_map, components)
    assert set(parts) == {
        "builtin.test.agent",
        "builtin.test.effect",
        "builtin.test.transform",
    }
    assert runtime_factories == {}
    assert runtime_configuration_digests == {}
    assert runtime_identity_digests == {}
    providers = catalog_module._validate_review_graph(
        plugin_map, components, parts, used
    )
    assert providers == {}
    staged = catalog_module._build_compiled_catalog(
        plugin_map,
        components,
        parts,
        providers,
        runtime_factories,
        runtime_configuration_digests,
        runtime_identity_digests,
        used,
    )
    direct = catalog_module.compile_catalog((ARCHITECTURE_TEST_PLUGIN,))
    assert staged.operation_ids() == direct.operation_ids()
    assert {
        item: staged.operation(item).digest for item in staged.operation_ids()
    } == {item: direct.operation(item).digest for item in direct.operation_ids()}
    assert ARCHITECTURE_TEST_PLUGIN.model_dump(mode="python") == before


def test_catalog_stage_refactor_matches_current_core_digest_summary() -> None:
    compiled = catalog_module.compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN))
    assert len(compiled.operation_ids()) == 15
    assert _digest_map(compiled) == (
        "7e4dd32ff8d3d22db307d085fa7c37f9934ce370a07e7d06f22c185272f440a3"
    )


def test_catalog_stages_add_no_second_registry_or_complexity_escape() -> None:
    tree = ast.parse(CATALOG_PATH.read_text())
    mutable_top_level = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if isinstance(value, (ast.Dict, ast.List, ast.Set)):
            mutable_top_level.append(node)
    assert mutable_top_level == []

    metrics = json.loads(
        subprocess.run(
            [sys.executable, "scripts/r5_current_metrics.py"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    catalog = metrics["responsibilities"][
        "src/scidiscovery/operations/catalog.py"
    ]
    assert catalog["successor_paths"] == [
        "src/scidiscovery/operations/catalog.py"
    ]
    # The catalog remains the sole compiled authority. Later simplification may
    # remove code, but must not grow a second file, registry, or projection.
    assert catalog["total_lines"] <= 765
    # Local tool availability and workspace policy remain in the same immutable
    # catalog package. Removing the runtime convenience projection may shrink it.
    assert metrics["operations_package"]["files"] == 8
    assert metrics["operations_package"]["lines"] <= 2150
    # H5 established these upper bounds.  Later evidence-backed deletions must
    # not fail merely because the production tree became smaller.
    # L2 replaces the default central controller with deliberately separated
    # Run records/current/workspace/output/router boundaries.  The small-file
    # split is preferred to another giant service module.
    # L5 isolates its optional transport in exactly three narrow modules:
    # workspace ownership, server-side editing and one MCP adapter. L6 must
    # recover this temporary allowance by deleting the legacy Task transport.
    assert metrics["production_python"]["files"] <= 159
    # L5's exact-context hardened text editor closes a previously advertised
    # but unusable TCAD capability. L6 must recover this temporary allowance
    # by removing the complete legacy Task transport.
    assert metrics["production_python"]["lines"] <= 62100


def test_current_metrics_tracks_run_and_worker_successors_once() -> None:
    metrics = json.loads(
        subprocess.run(
            [sys.executable, "scripts/r5_current_metrics.py"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    responsibilities = metrics["responsibilities"]
    expected = {
        "src/scidiscovery/scheduler_topology.py": {
            "src/scidiscovery/platforms/scheduler_prompt.py",
        },
        "src/scidiscovery/platforms/roles.py": {
            "src/scidiscovery/platforms/codex.py",
        },
        "src/scidiscovery/artifact_agent/service/tasks.py": {
            "src/scidiscovery/artifact_agent/service/runs.py",
            "src/scidiscovery/artifact_agent/service/run_assignment.py",
            "src/scidiscovery/artifact_agent/service/run_current.py",
            "src/scidiscovery/artifact_agent/service/run_outputs.py",
            "src/scidiscovery/artifact_agent/service/run_records.py",
            "src/scidiscovery/artifact_agent/service/local_workspace.py",
            "src/scidiscovery/artifact_agent/service/hardened_workspace.py",
            "src/scidiscovery/artifact_agent/service/hardened_files.py",
            "src/scidiscovery/artifact_agent/service/local_pdf_tool.py",
            "src/scidiscovery/artifact_agent/operation_tool_context.py",
        },
        "src/scidiscovery/artifact_agent/interfaces/mcp_worker.py": {
            "src/scidiscovery/artifact_agent/interfaces/mcp_worker_protocol.py",
            "src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py",
            "src/scidiscovery/artifact_agent/interfaces/mcp_hardened_worker.py",
        },
    }
    for owner, paths in expected.items():
        assert set(responsibilities[owner]["successor_paths"]) == paths
        assert responsibilities[owner]["total_lines"] == sum(
            responsibilities[owner]["lines_by_path"].values()
        )

    all_paths = [
        path
        for item in responsibilities.values()
        for path in item["successor_paths"]
    ]
    assert len(all_paths) == len(set(all_paths))
    assert all((REPOSITORY / path).is_file() for path in all_paths)
