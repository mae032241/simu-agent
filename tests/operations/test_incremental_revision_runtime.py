from __future__ import annotations


import hashlib

import pytest

from blind_csv_plugin.plugin import AUTHOR, FILE_TOOLS, JSON_CODEC, OBSERVATION, PLUGIN, REVIEWER, TABLE, WORKSPACE
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operation_declaration import scientific_agent_operation
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
from scidiscovery.operations.invoke import (
    active_direct_revision_ports,
    direct_revision_ports,
)
from scidiscovery.operations.spec import CallableComponent, ComponentRef, ComponentSpec, InputAdmissionSpec, InputPortSpec, ReviewSpec


def _input(
    name: str,
    description: str,
    schema: str,
    schema_resource: str,
    *,
    usage: str,
    codec: ComponentRef = JSON_CODEC,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=codec,
        schema_resource=ComponentRef(schema_resource),
        max_item_bytes=2 * 1024 * 1024,
        min_items=min_items,
        usage=usage,
        exposure="full",
    )

def _blind_progress_fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

BLIND_PROGRESS = CallableComponent("transform", _blind_progress_fingerprint)


REVISION = scientific_agent_operation(
    "blind.csv.revise.v1",
    "Revise one exact bounded CSV observation.",
    "An independently reviewed observation requires a correction.",
    "Changing the source table or inheriting the review verdict.",
    agent=ComponentRef("author"),
    workspace=WORKSPACE,
    prompt=ComponentRef("author_prompt"),
    tools=(
        *FILE_TOOLS,
    ),
    inputs=(
        _input(
            "prior_draft",
            "Exact observation revision base.",
            "blind.csv-observation.v1",
            "observation_schema",
            usage="revision_base",
        ),
        _input(
            "change_request",
            "Exact independent review requesting correction.",
            "blind.csv-review.v1",
            "review_schema",
            usage="change_request",
        ),
        _input(
            "source_table",
            "Exact source table.",
            "blind.opaque.v1",
            "opaque_schema",
            usage="claim_evidence",
            codec=ComponentRef("opaque_codec", plugin_id="general_science"),
            media_types=("text/csv",),
        ),
    ),
    outputs=(OBSERVATION,),
    timeout=300,
    max_input_bytes=4 * 1024 * 1024,
    max_output_bytes=64 * 1024,
    max_files=1,
    native_shell="none",
    review=ReviewSpec(
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        subject_outputs=("csv_observation",),
    ),
)


OPTIONAL_REVISION_INPUTS = (
    _input(
        "prior_draft",
        "Optional immutable observation revision base.",
        "blind.csv-observation.v1",
        "observation_schema",
        usage="revision_base",
        min_items=0,
    ),
    _input(
        "change_request",
        "Optional exact independent review requesting correction.",
        "blind.csv-review.v1",
        "review_schema",
        usage="change_request",
        min_items=0,
    ),
)
OPTIONAL_REVISION_ADMISSION = InputAdmissionSpec(
    cohort_id="observation_revision",
    member_ports=("prior_draft", "change_request"),
)
DUAL_AUTHOR = scientific_agent_operation(
    AUTHOR.operation_id,
    AUTHOR.description.purpose,
    AUTHOR.description.applies_when,
    AUTHOR.description.not_for,
    agent=AUTHOR.executor.component,
    workspace=AUTHOR.executor.workspace,
    prompt=AUTHOR.executor.prompt,
    tools=AUTHOR.executor.tools,
    inputs=(TABLE, *OPTIONAL_REVISION_INPUTS),
    outputs=AUTHOR.outputs,
    timeout=AUTHOR.limits.timeout_seconds,
    max_input_bytes=AUTHOR.limits.max_input_bytes + 3 * 1024 * 1024,
    max_output_bytes=AUTHOR.limits.max_output_bytes,
    max_files=AUTHOR.limits.max_files,
    max_attempts=AUTHOR.limits.max_attempts,
    native_shell=AUTHOR.executor.native_tools.shell,
    input_admission=OPTIONAL_REVISION_ADMISSION,
    review=ReviewSpec(
        reviewer_operation="blind.csv.review.v1",
        reviewer_input_port="csv_observation",
        subject_outputs=("csv_observation",),
        max_revisions=2,
        progress_fingerprint=ComponentRef("blind_progress"),
    ),
)


def _optional_catalog(operation=DUAL_AUTHOR):
    plugin = PLUGIN.model_copy(
        update={
            "components": (
                *PLUGIN.components,
                ComponentSpec(
                    "blind_progress",
                    "transform",
                    "tests.operations.test_incremental_revision_runtime:BLIND_PROGRESS",
                ),
            ),
            "operations": (operation, REVIEWER),
        }
    )
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, plugin))


def test_optional_direct_revision_shape_is_one_bounded_operation() -> None:
    compiled = _optional_catalog().operation("blind.csv.observe.v1")
    direct = direct_revision_ports(compiled)

    assert direct is not None
    assert direct[0].name == "prior_draft"
    assert active_direct_revision_ports(compiled, ("source_table",)) is None
    assert active_direct_revision_ports(
        compiled, ("source_table", "prior_draft", "change_request")
    ) == direct

    from scidiscovery.operation_contract import operation_output_validation_contract

    contract = operation_output_validation_contract(compiled, direct[1])
    revision_rule = next(
        item for item in contract["rules"] if item["rule_id"] == "runtime.revision"
    )
    assert revision_rule["required_inputs"] == ["prior_draft"]
    assert revision_rule["description"].startswith(
        "When the assignment binds the optional revision base"
    )


@pytest.mark.parametrize(
    "operation",
    (
        DUAL_AUTHOR.model_copy(update={"input_admission": None}),
        DUAL_AUTHOR.model_copy(
            update={
                "input_admission": OPTIONAL_REVISION_ADMISSION.model_copy(
                    update={
                        "member_ports": (
                            "prior_draft",
                            "change_request",
                            "source_table",
                        )
                    }
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "input_admission": OPTIONAL_REVISION_ADMISSION.model_copy(
                    update={"approval_kind": "revision_approval"}
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "inputs": tuple(
                    item.model_copy(update={"max_items": 2})
                    if item.usage == "revision_base"
                    else item
                    for item in DUAL_AUTHOR.inputs
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "inputs": tuple(
                    item.model_copy(update={"min_items": 1})
                    if item.usage == "change_request"
                    else item
                    for item in DUAL_AUTHOR.inputs
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "inputs": tuple(
                    item
                    for item in DUAL_AUTHOR.inputs
                    if item.usage != "change_request"
                )
            }
        ),
        DUAL_AUTHOR.model_copy(update={"review": None}),
        DUAL_AUTHOR.model_copy(
            update={
                "review": DUAL_AUTHOR.review.model_copy(
                    update={"max_revisions": 0, "progress_fingerprint": None}
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "review": DUAL_AUTHOR.review.model_copy(
                    update={"progress_fingerprint": None}
                )
            }
        ),
        DUAL_AUTHOR.model_copy(
            update={
                "outputs": (
                    DUAL_AUTHOR.outputs[0].model_copy(
                        update={"media_types": ("text/plain",)}
                    ),
                )
            }
        ),
    ),
)
def test_optional_direct_revision_shape_fails_closed_at_compile(operation) -> None:
    with pytest.raises(CatalogCompileError):
        _optional_catalog(operation)


def test_revision_base_must_be_materializable() -> None:
    hidden_base = REVISION.inputs[0].model_copy(update={"exposure": "handoff_only"})
    hidden_revision = REVISION.model_copy(
        update={"inputs": (hidden_base, *REVISION.inputs[1:])}
    )
    hidden_plugin = PLUGIN.model_copy(
        update={"operations": (*PLUGIN.operations, hidden_revision)}
    )
    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, hidden_plugin))
    assert caught.value.reason_code == "direct_revision_contract_invalid"
