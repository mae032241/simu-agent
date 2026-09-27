"""Single-entry blind plugin: CSV observation plus independent review."""

from __future__ import annotations

from scidiscovery.operation_declaration import (
    OPERATION_AGENT_PREAMBLE,
    scientific_agent_operation,
    semantic_contract,
)
from scidiscovery.operations.spec import (
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    InputPortSpec,
    OutputPortSpec,
    PLUGIN_PROTOCOL_VERSION,
    PluginDefinition,
    PluginDependency,
    ReviewSpec,
    SemanticRuleSpec,
)

from .contracts import (
    OBSERVATION_SCHEMA,
    OBSERVATION_VALIDATOR,
    REVIEW_SCHEMA,
    REVIEW_VALIDATOR,
    validate_observation_context,
    validate_review_context,
)
from .worker_tool import CSV_SUMMARY_TOOL

GENERAL = "general_science"
BUILTIN = "builtin"
JSON_CODEC = ComponentRef("json_codec", plugin_id=GENERAL)
OPAQUE_CODEC = ComponentRef("opaque_codec", plugin_id=GENERAL)
WORKSPACE = ComponentRef("workspace", plugin_id=GENERAL)
FILE_TOOLS = tuple(
    ComponentRef(name, plugin_id=BUILTIN)
    for name in (
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
    )
)
SEMANTIC_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="blind.payload_consistency",
        description="Cross-field CSV observation values must be internally consistent.",
    ),
    SemanticRuleSpec(
        rule_id="blind.context_binding",
        description="The result must bind to the exact declared CSV context.",
    ),
    SemanticRuleSpec(
        rule_id="blind.binding",
        description="Bind structural facts to exact inputs.",
    ),
    SemanticRuleSpec(
        rule_id="blind.missing_data",
        description="Do not invent missing data.",
    ),
)
OPAQUE_SCHEMA = '{"$id":"blind.opaque.v1","type":["string","object","array"]}'
AUTHOR_PROMPT = OPERATION_AGENT_PREAMBLE + """Call worker_csv_summarize on the
exact source_table. Return one blind.csv-observation.v1 payload with the exact
structure, a bounded scientific interpretation, and explicit limitations.
"""
REVIEW_PROMPT = OPERATION_AGENT_PREAMBLE + """Independently review the exact
csv_observation against source_table. Return one blind.csv-review.v1 payload;
bind subject_sha256 to the exact canonical observation bytes.
"""

def _agent() -> None:
    return None

def _input(
    name: str,
    description: str,
    schema: str,
    schema_resource: ComponentRef,
    *,
    codec: ComponentRef = JSON_CODEC,
    media_types: tuple[str, ...] = ("application/json",),
    usage: str = "prior_signal",
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=codec,
        schema_resource=schema_resource,
        max_item_bytes=2 * 1024 * 1024,
        usage=usage,
        exposure="full",
    )

def _output(
    name: str,
    kind: str,
    schema: str,
    schema_resource: ComponentRef,
    validator: str,
    context_validator: str,
    context_sources: tuple[str, ...],
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description="One validated blind CSV result.",
        schema=schema,
        media_types=("application/json",),
        codec=JSON_CODEC,
        schema_resource=schema_resource,
        kind=kind,
        validator=ComponentRef(validator),
        validator_rule_id="blind.payload_consistency",
        semantic_contract=ComponentRef("semantic_contract"),
        context_validator=ComponentRef(context_validator),
        context_rule_id="blind.context_binding",
        context_sources=context_sources,
        max_item_bytes=64 * 1024,
    )

TABLE = _input(
    "source_table",
    "Exact opaque CSV under observation.",
    "blind.opaque.v1",
    ComponentRef("opaque_schema"),
    codec=OPAQUE_CODEC,
    media_types=("text/csv",),
    usage="claim_evidence",
)
OBSERVATION = _output(
    "csv_observation",
    "observation",
    "blind.csv-observation.v1",
    ComponentRef("observation_schema"),
    "observation_validator",
    "observation_context",
    ("source_table",),
)
REVIEW = _output(
    "csv_review",
    "scientific_review",
    "blind.csv-review.v1",
    ComponentRef("review_schema"),
    "review_validator",
    "review_context",
    ("source_table", "csv_observation"),
)
AUTHOR = scientific_agent_operation(
    "blind.csv.observe.v1",
    "Interpret one bounded CSV after deterministic structural analysis.",
    "A CSV requires a traceable observation.",
    "Changing data, causal inference, or approval.",
    agent=ComponentRef("author"), workspace=WORKSPACE,
    prompt=ComponentRef("author_prompt"), tools=(*FILE_TOOLS, ComponentRef("csv_tool")),
    inputs=(TABLE,), outputs=(OBSERVATION,), timeout=300,
    max_input_bytes=2 * 1024 * 1024, max_output_bytes=64 * 1024, max_files=1,
    max_attempts=2,
    native_shell="none",
    review=ReviewSpec(
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        subject_outputs=("csv_observation",),
    ),
)
REVIEWER = scientific_agent_operation(
    "blind.csv.review.v1",
    "Independently review one exact CSV observation.",
    "A CSV observation requires review.",
    "Editing the observation or granting approval.",
    agent=ComponentRef("reviewer"), workspace=WORKSPACE,
    prompt=ComponentRef("review_prompt"), tools=FILE_TOOLS,
    inputs=(TABLE, _input(
        "csv_observation", "Exact observation under review.",
        "blind.csv-observation.v1", ComponentRef("observation_schema")
    )), outputs=(REVIEW,), timeout=300,
    max_input_bytes=3 * 1024 * 1024, max_output_bytes=64 * 1024, max_files=1,
    # The reviewer must inspect both immutable bound inputs.  In the trusted-local
    # prototype that read path is Codex's task-workspace tools; no separate global
    # input-reader registry is introduced.
    native_shell="inherited_prototype",
)

COMPONENTS = (
    ComponentSpec("author", "agent", "blind_csv_plugin.plugin:AUTHOR_AGENT"),
    ComponentSpec("reviewer", "agent", "blind_csv_plugin.plugin:REVIEWER_AGENT"),
    ComponentSpec("csv_tool", "worker_tool", "blind_csv_plugin.worker_tool:CSV_SUMMARY_TOOL"),
    ComponentSpec("observation_validator", "validator", "blind_csv_plugin.plugin:OBSERVATION_COMPONENT", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("review_validator", "validator", "blind_csv_plugin.plugin:REVIEW_COMPONENT", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("observation_context", "validator", "blind_csv_plugin.plugin:OBSERVATION_CONTEXT", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("review_context", "validator", "blind_csv_plugin.plugin:REVIEW_CONTEXT", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("semantic_contract", "resource", "blind_csv_plugin.plugin:SEMANTIC_CONTRACT"),
    ComponentSpec("opaque_schema", "resource", "blind_csv_plugin.plugin:OPAQUE_SCHEMA"),
    ComponentSpec("observation_schema", "resource", "blind_csv_plugin.plugin:OBSERVATION_SCHEMA"),
    ComponentSpec("review_schema", "resource", "blind_csv_plugin.plugin:REVIEW_SCHEMA"),
    ComponentSpec("author_prompt", "resource", "blind_csv_plugin.plugin:AUTHOR_PROMPT"),
    ComponentSpec("review_prompt", "resource", "blind_csv_plugin.plugin:REVIEW_PROMPT"),
)
AUTHOR_AGENT = CallableComponent("agent", _agent)
REVIEWER_AGENT = CallableComponent("agent", _agent)
OBSERVATION_COMPONENT = CallableComponent("validator", OBSERVATION_VALIDATOR)
REVIEW_COMPONENT = CallableComponent("validator", REVIEW_VALIDATOR)
OBSERVATION_CONTEXT = CallableComponent("validator", validate_observation_context)
REVIEW_CONTEXT = CallableComponent("validator", validate_review_context)

PLUGIN = PluginDefinition(
    plugin_id="blind_csv", version="0.1.0", protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(PluginDependency(BUILTIN, "0.1.0"), PluginDependency(GENERAL, "0.1.0")),
    components=COMPONENTS, operations=(AUTHOR, REVIEWER),
)

_hardened_native = REVIEWER.executor.native_tools.model_copy(update={"shell": "none"})
HARDENED_PLUGIN = PLUGIN.model_copy(update={"operations": (
    AUTHOR,
    REVIEWER.model_copy(update={
        "outputs": tuple(p for p in REVIEWER.outputs if p.name != "attachments"),
        "executor": REVIEWER.executor.model_copy(update={"native_tools": _hardened_native,
            "tools": tuple(t for t in REVIEWER.executor.tools
                if t.component_id not in {"publish_files_tool", "materialize_input_tool"})})}),
)})

# The stdio transport regression imports this fixture in a fresh interpreter.
# Select the exact same test contract there as in its parent process.
import os as _os
if _os.environ.get("SCID_TEST_HARDENED_CSV_PLUGIN") == "1":
    PLUGIN = HARDENED_PLUGIN

__all__ = ["PLUGIN", "HARDENED_PLUGIN"]
