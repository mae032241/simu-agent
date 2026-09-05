from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from ingaas_fig4.plugin import PLUGIN as INGAAS_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tcad_artifact.execution_control import ExpectedOutput, ResourceLimits
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.project_packager import (
    ProjectExpectedOutput,
    ProjectResourceLimits,
)


PLUGINS = (
    CORE_PLUGIN,
    GENERAL_PLUGIN,
    CURVE_PLUGIN,
    TCAD_PLUGIN,
    INGAAS_PLUGIN,
    FIGURE_PLUGIN,
)
FILE_TOOLS = {
    "file_write_begin_tool",
    "file_write_chunk_tool",
    "file_write_commit_tool",
    "file_apply_patch_tool",
    "file_json_patch_tool",
    "file_delete_tool",
    "file_move_tool",
}
FIGURE_OPERATIONS = {
    "scidiscovery.curve-bundle.figure-evidence.v2",
    "science.figure.request.prepare.v1",
    "science.figure.evidence.materialize.v1",
    "science.evidence.extract.figure.v2",
    "science.figure.evidence.audit.v1",
}


def _resource_value(implementation: str) -> object:
    module_name, separator, attribute_path = implementation.partition(":")
    assert separator
    value = importlib.import_module(module_name)
    for attribute in attribute_path.split("."):
        value = getattr(value, attribute)
    return value


def test_common_file_tools_are_registered_once_without_implicit_authority() -> None:
    assert FILE_TOOLS.issubset(
        {item.component_id for item in CORE_PLUGIN.components if item.public}
    )
    assert FILE_TOOLS.isdisjoint(
        item.component_id
        for plugin in PLUGINS[1:]
        for item in plugin.components
    )
    catalog = compile_catalog(PLUGINS[:4])
    author = catalog.operation("tcad.deck.author.initial.v1")
    reviewer = catalog.operation("tcad.deck.review.v1")
    assert "builtin:file_delete_tool" in author.permission_template.tools
    assert "builtin:file_delete_tool" not in reviewer.permission_template.tools


def test_installed_schema_ids_have_one_registration_owner() -> None:
    owners: dict[str, list[tuple[str, str]]] = {}
    for plugin in PLUGINS:
        for component in plugin.components:
            if component.kind != "resource":
                continue
            value = _resource_value(component.implementation)
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            try:
                payload = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("$id"), str):
                owners.setdefault(payload["$id"], []).append(
                    (plugin.plugin_id, component.component_id)
                )
    assert {schema_id: values for schema_id, values in owners.items() if len(values) > 1} == {}


def test_optional_figure_plugin_owns_its_complete_vertical_slice() -> None:
    default = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )
    optional = compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, FIGURE_PLUGIN)
    )
    assert FIGURE_OPERATIONS.isdisjoint(default.operation_ids())
    assert set(optional.operation_ids()) - set(default.operation_ids()) == FIGURE_OPERATIONS
    assert {
        optional.operation(operation_id).plugin_id
        for operation_id in FIGURE_OPERATIONS
    } == {"curve_figure_evidence"}


def test_project_and_execution_resource_contracts_share_one_type() -> None:
    assert ProjectExpectedOutput is ExpectedOutput
    assert ProjectResourceLimits is ResourceLimits


def test_default_imports_do_not_load_optional_runtime_products() -> None:
    source = """
import sys
from scidiscovery.artifact_agent.interfaces import cli
from scidiscovery.artifact_agent import runtime
from scidiscovery.platforms import codex
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
for name in (
    'scidiscovery.artifact_agent.portable_bundle',
    'scidiscovery.artifact_agent.service.hardened_files',
    'scidiscovery.artifact_agent.service.hardened_workspace',
    'scidiscovery.artifact_agent.interfaces.mcp_hardened_worker',
    'tcad_artifact.command_adapter',
    'tcad_artifact.execution_adapter',
    'tcad_artifact.execution_daemon',
    'tcad_artifact.remote_runner_py36',
    'tcad_artifact.ssh_transport',
):
    assert name not in sys.modules, name
"""
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert completed.returncode == 0, completed.stderr


def test_tcad_runtime_loads_only_the_selected_transport(tmp_path: Path) -> None:
    command_config = tmp_path / "command.json"
    command_config.write_text(
        json.dumps(
            {
                "executable": sys.executable,
                "arguments": [],
                "environment": {},
                "operation_timeout_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    command_config.chmod(0o600)
    configurations = (
        (
            {"transport": "socket", "socket_path": "/tmp/scid-m5-unused.sock"},
            "tcad_artifact.execution_adapter",
            "tcad_artifact.command_adapter",
        ),
        (
            {
                "transport": "command",
                "command_config_path": str(command_config),
            },
            "tcad_artifact.command_adapter",
            "tcad_artifact.execution_adapter",
        ),
    )
    source = """
import sys
from pathlib import Path
from scidiscovery.operations.runtime_plugins import RuntimePluginContext
from tcad_artifact.runtime_plugin import build_runtime
config = sys.argv[1].encode('utf-8')
contribution = build_runtime(RuntimePluginContext(
    plugin_id='tcad_artifact', mode='control',
    config_path=Path(sys.argv[2]), config_bytes=config,
    state_root=Path(sys.argv[3]),
))
assert set(contribution.execution_adapters) == {'tcad'}
assert sys.argv[4] in sys.modules
assert sys.argv[5] not in sys.modules
"""
    for index, (config, selected, forbidden) in enumerate(configurations):
        state_root = tmp_path / f"state-{index}"
        state_root.mkdir()
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                source,
                json.dumps(config),
                str(tmp_path / f"plugin-{index}.json"),
                str(state_root),
                selected,
                forbidden,
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        )
        assert completed.returncode == 0, completed.stderr
