"""Single-entry non-curve observation plugin used as an extensibility proof."""

from __future__ import annotations

import json
from typing import Any

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.research_cycle import (
    ScientificReview,
    validate_scientific_review,
)
from scidiscovery.operation_declaration import (
    OPERATION_AGENT_PREAMBLE,
    payload_validator,
    schema_resource,
    semantic_contract,
    scientific_agent_operation,
)
from scidiscovery.operation_contract import SemanticRuleViolation
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

from .analysis import TableObservation, summarize_csv
from .worker_tool import TABLE_SUMMARY_TOOL


_GENERAL = "general_science"
_BASE_TOOLS = tuple(
    ComponentRef(name, plugin_id="builtin")
    for name in (
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
    )
)
_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="table.payload_consistency",
        description="Cross-field table observation values must be internally consistent.",
    ),
    SemanticRuleSpec(
        rule_id="table.binding",
        description="Bind every structural value to the exact supplied CSV.",
    ),
    SemanticRuleSpec(
        rule_id="table.ownership",
        description=(
            "The Agent owns interpretation; deterministic code owns table structure."
        ),
    ),
    SemanticRuleSpec(
        rule_id="table.review",
        description="A scientific review is not human approval.",
    ),
)
_ANALYZE_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the TableObservation required by
output.schema.json. Call worker_table_summarize first and copy its exact
structure. Interpret only the bounded observation relevant to the supplied
experiment; state limitations and do not invent missing rows or causal claims.
"""
_REVIEW_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the ScientificReview required by
output.schema.json. Use review_target observation. Independently assess whether
the finding follows from the exact table and experiment, without modifying the
observation or granting approval.
"""


def _agent() -> None:
    return None


def _json_codec(raw: bytes) -> bytes:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("table plugin JSON must be an object")
    return canonical_json(value)


def _opaque_codec(raw: bytes) -> bytes:
    return raw


def _observation_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    observation = TableObservation.model_validate_json(
        canonical_json(payload), strict=True
    )
    plan = ExperimentPortfolio.model_validate_json(
        sources["experiment_plan"], strict=True
    )
    if observation.experiment_key not in {
        item.experiment_key for item in plan.proposals
    }:
        raise SemanticRuleViolation("table observation names an unknown experiment")
    expected = summarize_csv(sources["observation_table"])
    if observation.structure != expected:
        raise SemanticRuleViolation("table observation structure differs from the exact CSV")


def _review_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    _observation_context(
        TableObservation.model_validate_json(
            sources["table_observation"], strict=True
        ).model_dump(mode="json"),
        {
            "experiment_plan": sources["experiment_plan"],
            "observation_table": sources["observation_table"],
        },
        {},
    )
    review = ScientificReview.model_validate_json(
        canonical_json(payload), strict=True
    )
    if review.review_target != "observation":
        raise SemanticRuleViolation("table review_target must be observation")
    expected_verdict = "blocked" if review.verdict == "reject" else review.verdict
    if handoff.get("verdict") != expected_verdict:
        raise SemanticRuleViolation("table review handoff differs from payload verdict")


JSON_CODEC = CallableComponent("codec", _json_codec)
OPAQUE_CODEC = CallableComponent("codec", _opaque_codec)
OBSERVATION_VALIDATOR = CallableComponent(
    "validator",
    payload_validator(lambda value: TableObservation.model_validate(value, strict=True)),
)
REVIEW_VALIDATOR = CallableComponent(
    "validator", payload_validator(validate_scientific_review)
)
OBSERVATION_CONTEXT = CallableComponent("validator", _observation_context)
REVIEW_CONTEXT = CallableComponent("validator", _review_context)
ANALYST = CallableComponent("agent", _agent)
REVIEWER = CallableComponent("agent", _agent)
OBSERVATION_SCHEMA = schema_resource(
    TableObservation, "scidiscovery.table-observation.v1"
)


def _input(
    name: str,
    description: str,
    schema: str,
    resource: ComponentRef,
    *,
    media_types: tuple[str, ...] = ("application/json",),
    max_bytes: int = 16 * 1024 * 1024,
    exposure: str = "full",
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=ComponentRef(
            "json_codec" if media_types == ("application/json",) else "opaque_codec"
        ),
        schema_resource=resource,
        max_item_bytes=max_bytes,
        exposure=exposure,
        usage="prior_signal",
    )


def _output(
    schema: str,
    resource: ComponentRef,
    validator: str,
    context: str,
    context_sources: tuple[str, ...],
    *,
    kind: str,
    max_bytes: int,
) -> OutputPortSpec:
    return OutputPortSpec(
        name="table_observation" if kind == "observation" else "scientific_review",
        description="Validated table-domain scientific output.",
        schema=schema,
        media_types=("application/json",),
        codec=ComponentRef("json_codec"),
        schema_resource=resource,
        kind=kind,
        validator=ComponentRef(validator),
        validator_rule_id="table.payload_consistency",
        semantic_contract=ComponentRef("semantic_contract"),
        context_validator=ComponentRef(context),
        context_rule_id="table.binding",
        context_sources=context_sources,
        max_item_bytes=max_bytes,
    )


PLAN_INPUT = _input(
    "experiment_plan",
    "Exact generic experiment portfolio.",
    "scidiscovery.experiment-portfolio.v1",
    ComponentRef("experiment_portfolio_schema", plugin_id=_GENERAL),
    max_bytes=2 * 1024 * 1024,
)
TABLE_INPUT = _input(
    "observation_table",
    "Exact CSV observation table.",
    "opaque",
    ComponentRef("opaque_schema"),
    media_types=("text/csv",),
)
PLAN_REVIEW_INPUT = _input(
    "experiment_review",
    "Exact independent review of the generic experiment portfolio.",
    "scidiscovery.scientific-review.v1",
    ComponentRef("scientific_review_schema", plugin_id=_GENERAL),
    max_bytes=64 * 1024,
    exposure="handoff_only",
)


ANALYZE_OPERATION = scientific_agent_operation(
    "science.table.observation.analyze.v1",
    "Interpret one bounded non-curve observation table against an experiment.",
    "A generic experiment and immutable CSV observation are available.",
    "Curve scoring, causal inference, or changing the experiment plan.",
    agent=ComponentRef("analyst"),
    workspace=ComponentRef("workspace", plugin_id=_GENERAL),
    prompt=ComponentRef("analyze_prompt"),
    tools=(*_BASE_TOOLS, ComponentRef("table_summary_tool")),
    inputs=(PLAN_INPUT, PLAN_REVIEW_INPUT, TABLE_INPUT),
    outputs=(
        _output(
            "scidiscovery.table-observation.v1",
            ComponentRef("observation_schema"),
            "observation_validator",
            "observation_context",
            ("experiment_plan", "observation_table"),
            kind="observation",
            max_bytes=128 * 1024,
        ),
    ),
    timeout=600,
    max_input_bytes=18 * 1024 * 1024,
    max_output_bytes=128 * 1024,
    max_files=1,
    review=ReviewSpec(
        reviewer_operation="science.table.observation.review.v1",
        reviewer_input_port="table_observation",
        subject_outputs=("table_observation",),
    ),
)
REVIEW_OPERATION = scientific_agent_operation(
    "science.table.observation.review.v1",
    "Independently review one table observation.",
    "A table observation needs scientific review.",
    "Editing the observation or granting human approval.",
    agent=ComponentRef("reviewer"),
    workspace=ComponentRef("workspace", plugin_id=_GENERAL),
    prompt=ComponentRef("review_prompt"),
    tools=_BASE_TOOLS,
    inputs=(
        PLAN_INPUT,
        PLAN_REVIEW_INPUT,
        TABLE_INPUT,
        _input(
            "table_observation",
            "Exact table observation under review.",
            "scidiscovery.table-observation.v1",
            ComponentRef("observation_schema"),
            max_bytes=128 * 1024,
        ),
    ),
    outputs=(
        _output(
            "scidiscovery.scientific-review.v1",
            ComponentRef("scientific_review_schema", plugin_id=_GENERAL),
            "review_validator",
            "review_context",
            ("experiment_plan", "observation_table", "table_observation"),
            kind="scientific_review",
            max_bytes=64 * 1024,
        ),
    ),
    timeout=600,
    max_input_bytes=18 * 1024 * 1024,
    max_output_bytes=64 * 1024,
    max_files=1,
)


COMPONENTS = (
    ComponentSpec("json_codec", "codec", "table_observation.plugin:JSON_CODEC"),
    ComponentSpec("opaque_codec", "codec", "table_observation.plugin:OPAQUE_CODEC"),
    ComponentSpec("analyst", "agent", "table_observation.plugin:ANALYST"),
    ComponentSpec("reviewer", "agent", "table_observation.plugin:REVIEWER"),
    ComponentSpec("table_summary_tool", "worker_tool", "table_observation.worker_tool:TABLE_SUMMARY_TOOL"),
    ComponentSpec("observation_validator", "validator", "table_observation.plugin:OBSERVATION_VALIDATOR", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("review_validator", "validator", "table_observation.plugin:REVIEW_VALIDATOR", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("observation_context", "validator", "table_observation.plugin:OBSERVATION_CONTEXT", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("review_context", "validator", "table_observation.plugin:REVIEW_CONTEXT", resources=(ComponentRef("semantic_contract"),)),
    ComponentSpec("semantic_contract", "resource", "table_observation.plugin:_CONTRACT"),
    ComponentSpec("analyze_prompt", "resource", "table_observation.plugin:_ANALYZE_PROMPT"),
    ComponentSpec("review_prompt", "resource", "table_observation.plugin:_REVIEW_PROMPT"),
    ComponentSpec("observation_schema", "resource", "table_observation.plugin:OBSERVATION_SCHEMA"),
    ComponentSpec("opaque_schema", "resource", "table_observation.plugin:OPAQUE_SCHEMA"),
)
OPAQUE_SCHEMA = '{"$id":"opaque","type":["string","object","array"]}'


PLUGIN = PluginDefinition(
    plugin_id="table_observation",
    version="0.1.0",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(
        PluginDependency("builtin", "0.1.0"),
        PluginDependency("general_science", "0.1.0"),
    ),
    components=COMPONENTS,
    operations=(ANALYZE_OPERATION, REVIEW_OPERATION),
)


__all__ = ["PLUGIN"]
