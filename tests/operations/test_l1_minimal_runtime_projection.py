from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from architecture_operation_test_plugin.plugin import (
    ARCHITECTURE_TEST_PLUGIN,
)
from blind_csv_plugin.contracts import (
    CSV_SCHEMA_PROBE,
    CsvObservation,
    summarize_csv,
    validate_observation_context,
)
from blind_csv_plugin.plugin import PLUGIN as BLIND_CSV_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
from scidiscovery.operations.tooling import operation_worker_tools


def _catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, BLIND_CSV_PLUGIN))


def test_compiled_entry_is_the_single_runtime_authority() -> None:
    catalog = _catalog()
    compiled = catalog.operation("blind.csv.observe.v1")

    assert compiled.spec.operation_id == "blind.csv.observe.v1"
    assert len(compiled.digest) == 64
    assert compiled.spec.executor.component.plugin_id is None
    assert compiled.spec.executor.component.component_id == "author"
    assert compiled.permission_template is not None
    assert compiled.spec.review is not None
    assert compiled.spec.review.reviewer_operation == "blind.csv.review.v1"
    assert compiled.spec.review.subject_outputs == ("csv_observation",)
    assert compiled.spec.guards == ()
    assert compiled.spec.input_admission is None
    assert compiled.spec.review.approval is None
    assert compiled.spec.executor.kind == "agent"
    assert "_runtime_operations" not in type(catalog).__slots__
    projection = next(
        item
        for item in catalog.scheduler_projection()
        if item.operation_id == "blind.csv.observe.v1"
    )
    assert projection.review_edge is not None
    assert projection.review_edge.model_dump(mode="json") == {
        "reviewer_operation": "blind.csv.review.v1",
        "reviewer_input_port": "csv_observation",
        "subject_outputs": ["csv_observation"],
        "accepted_verdicts": ["pass"],
    }
    assert projection.requires_independent_review is True
    assert projection.accepts_actions == ()


def test_public_producer_cannot_hide_its_reviewer_from_the_scheduler() -> None:
    author, reviewer = BLIND_CSV_PLUGIN.operations
    hidden_reviewer = reviewer.model_copy(update={"catalog_scope": "internal"})
    malformed = BLIND_CSV_PLUGIN.model_copy(
        update={"operations": (author, hidden_reviewer)}
    )

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, malformed))

    assert caught.value.reason_code == "reviewer_not_public"


def test_change_request_requires_one_direct_revision_base() -> None:
    agent = ARCHITECTURE_TEST_PLUGIN.operations[0]
    request_only = agent.model_copy(
        update={
            "inputs": (
                agent.inputs[0].model_copy(update={"usage": "change_request"}),
            )
        }
    )
    malformed = ARCHITECTURE_TEST_PLUGIN.model_copy(
        update={
            "operations": (
                request_only,
                *ARCHITECTURE_TEST_PLUGIN.operations[1:],
            )
        }
    )

    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((malformed,))

    assert caught.value.reason_code == "change_request_without_revision_base"


def test_optional_governance_exists_only_on_declaring_compiled_specs() -> None:
    catalog = compile_catalog((ARCHITECTURE_TEST_PLUGIN,))
    ordinary = catalog.operation("builtin.test.agent")
    effect = catalog.operation("builtin.test.effect")

    assert ordinary.spec.review is None
    assert ordinary.spec.executor.kind == "agent"
    assert effect.spec.review is not None
    assert effect.spec.review.approval is not None
    assert effect.spec.executor.kind == "effect"
    assert effect.spec.executor.component.component_id == "test_effect"


def test_blind_plugin_registers_one_real_domain_tool_and_review_edge() -> None:
    catalog = _catalog()
    compiled = catalog.operation("blind.csv.observe.v1")
    tools = {item.name: item for item in operation_worker_tools(compiled)}
    assert set(tools) == {
        "worker_file_write_begin",
        "worker_file_write_chunk",
        "worker_file_write_commit",
        "worker_csv_summarize",
    }

    raw = b"sample,value\na,1\nb,3\n"

    class Context:
        def __init__(self) -> None:
            self.activities: list[str] = []

        def read_input(self, name: str) -> bytes:
            assert name == "source_table"
            return raw

        def record_activity(self, activity: str) -> None:
            self.activities.append(activity)

    context = Context()
    tool = tools["worker_csv_summarize"]
    result = tool.contextual_handler(
        tool.input_model(),
        context,
    )
    assert result == summarize_csv(raw).model_dump(mode="json")
    assert result["numeric_means"] == {"value": 2.0}
    assert context.activities == []

    observation = CsvObservation(
        schema_probe=CSV_SCHEMA_PROBE,
        structure=summarize_csv(raw),
        interpretation="The bounded values have an arithmetic mean of two.",
        limitations=("Two rows do not support causal inference.",),
    )
    validate_observation_context(
        observation.model_dump(mode="json"),
        {"source_table": raw},
        {"verdict": "pass"},
    )
    with pytest.raises(ValueError, match="exact CSV"):
        validate_observation_context(
            observation.model_dump(mode="json"),
            {"source_table": raw.replace(b"3", b"4")},
            {"verdict": "pass"},
        )


def test_blind_plugin_has_a_small_single_entry_and_no_core_name_branch() -> None:
    repository = Path(__file__).resolve().parents[2]
    plugin = (
        repository
        / "tests/fixtures/plugins/blind_csv_operation_plugin/blind_csv_plugin/plugin.py"
    )
    meaningful = tuple(
        line for line in plugin.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    assert len(meaningful) <= 250
    assert BLIND_CSV_PLUGIN.plugin_id == "blind_csv"
    assert len(BLIND_CSV_PLUGIN.operations) == 2
    assert all(operation.input_admission is None for operation in BLIND_CSV_PLUGIN.operations)
    for path in (repository / "src/scidiscovery").rglob("*.py"):
        assert "blind_csv" not in path.read_text(encoding="utf-8"), path


def test_clean_installed_blind_plugin_compiles_and_calls_its_tool(
    installed_probe,
) -> None:
    installed_probe(
        "blind_csv",
        r'''
from pathlib import Path
import sys

import blind_csv_plugin
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(blind_csv_plugin.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog = compile_installed_catalog()
assert "blind.csv.observe.v1" in catalog.operation_ids()
compiled = catalog.operation("blind.csv.observe.v1")
assert catalog.operation(compiled.spec.operation_id) is compiled
tool = {item.name: item for item in operation_worker_tools(compiled)}["worker_csv_summarize"]
class Context:
    def __init__(self): self.activities = []
    def read_input(self, name):
        assert name == "source_table"
        return b"sample,value\na,1\nb,3\n"
    def record_activity(self, value): self.activities.append(value)
context = Context()
result = tool.contextual_handler(
    tool.input_model(),
    context,
)
assert result["numeric_means"] == {"value": 2.0}
assert context.activities == []
''',
    )
