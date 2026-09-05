"""Compiled R5 evaluation-only historical replay Effect Operation."""

from __future__ import annotations

from scidiscovery.operations.spec import (
    PLUGIN_PROTOCOL_VERSION,
    ApprovalContract,
    ApprovalOption,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    PluginDefinition,
    PluginDependency,
    ReviewSpec,
)


def _ref(component_id: str) -> ComponentRef:
    return ComponentRef(component_id)


PLUGIN = PluginDefinition(
    plugin_id="r5_e2e_fixture",
    version="0.0.1",
    protocol_version=PLUGIN_PROTOCOL_VERSION,
    dependencies=(PluginDependency("ingaas_fig4", "0.2.0"),),
    configuration_schema=_ref("configuration_schema"),
    runtime_factory=_ref("runtime_factory"),
    components=(
        ComponentSpec(
            "json_codec",
            "codec",
            "r5_e2e_tcad_plugin.runtime:JSON_CODEC",
        ),
        ComponentSpec(
            "replay_request_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:REPLAY_REQUEST_SCHEMA",
        ),
        ComponentSpec(
            "execution_request_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:EXECUTION_REQUEST_SCHEMA",
        ),
        ComponentSpec(
            "configuration_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:CONFIGURATION_SCHEMA",
        ),
        ComponentSpec(
            "runtime_factory",
            "runtime_factory",
            "r5_e2e_tcad_plugin.runtime:RUNTIME_FACTORY",
            configuration_identity="r5.fixture.runtime-factory.v1",
        ),
        ComponentSpec(
            "replay_effect",
            "effect",
            "r5_e2e_tcad_plugin.runtime:EXECUTE_EFFECT",
        ),
        ComponentSpec(
            "execution_projector",
            "projector",
            "r5_e2e_tcad_plugin.runtime:EXECUTION_PROJECTOR",
        ),
        ComponentSpec(
            "opaque_codec",
            "codec",
            "r5_e2e_tcad_plugin.runtime:OPAQUE_CODEC",
        ),
        ComponentSpec(
            "opaque_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:OPAQUE_SCHEMA",
        ),
        ComponentSpec(
            "plx_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:PLX_SCHEMA",
        ),
        ComponentSpec(
            "qualify_replay_profile",
            "transform",
            "r5_e2e_tcad_plugin.runtime:QUALIFY_REPLAY_PROFILE",
        ),
        ComponentSpec(
            "replay_profile_validator",
            "validator",
            "r5_e2e_tcad_plugin.runtime:REPLAY_PROFILE_VALIDATOR",
        ),
        ComponentSpec(
            "metric_report_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:RESULT_SCHEMA",
        ),
        ComponentSpec(
            "curve_table_schema",
            "resource",
            "r5_e2e_tcad_plugin.runtime:CURVE_TABLE_SCHEMA",
        ),
        ComponentSpec(
            "project_science_sources",
            "transform",
            "r5_e2e_tcad_plugin.runtime:PROJECT_SCIENCE_SOURCES",
        ),
        ComponentSpec(
            "metric_source_validator",
            "validator",
            "r5_e2e_tcad_plugin.runtime:METRIC_SOURCE_VALIDATOR",
        ),
        ComponentSpec(
            "curve_source_validator",
            "validator",
            "r5_e2e_tcad_plugin.runtime:CURVE_SOURCE_VALIDATOR",
        ),
    ),
    operations=(
        OperationSpec(
            operation_id="r5.fixture.fig4-replay.v1",
            version="1",
            catalog_scope="public",
            description=OperationDescription(
                purpose="Replay four exact frozen historical Fig.4 output files.",
                applies_when=(
                    "The R5 evaluation fixture requests its pre-frozen historical "
                    "output bytes."
                ),
                not_for="Running a solver or producing new scientific evidence.",
            ),
            executor=ExecutorRef(
                kind="effect", component=_ref("replay_effect")
            ),
            inputs=(
                InputPortSpec(
                    name="replay_request",
                    description="Exact immutable historical replay request.",
                    schema="r5.fixture.fig4-replay-request.v1",
                    media_types=("application/json",),
                    codec=_ref("json_codec"),
                    schema_resource=_ref("replay_request_schema"),
                    max_item_bytes=4096,
                    usage="prior_signal",
                    exposure="full",
                ),
            ),
            outputs=(
                OutputPortSpec(
                    name="execution_request",
                    description="Controlled request for the frozen replay.",
                    schema="scidiscovery.execution-request",
                    media_types=("application/json",),
                    codec=_ref("json_codec"),
                    schema_resource=_ref("execution_request_schema"),
                    max_item_bytes=64 * 1024,
                    kind="execution_request",
                ),
            ),
            consequence="external",
            review=ReviewSpec(
                approval=ApprovalContract(
                    subject_ports=("execution_request", "replay_request"),
                    question="是否授权复制这四个已冻结的历史输出？",
                    options=(
                        ApprovalOption("授权重放", "accept"),
                        ApprovalOption("拒绝重放", "reject"),
                    ),
                    projector=_ref("execution_projector"),
                )
            ),
            limits=LimitsSpec(
                timeout_seconds=60,
                max_input_bytes=4096,
                max_output_bytes=64 * 1024,
                max_files=1,
            ),
        ),
        OperationSpec(
            operation_id="r5.fixture.fig4-replay-profile.qualify.v1",
            version="1",
            catalog_scope="support",
            description=OperationDescription(
                purpose=(
                    "Validate one collected historical replay profile against "
                    "the frozen fixture identity and expose its domain type."
                ),
                applies_when=(
                    "The exact replay request and its collected opaque PLX output "
                    "are available."
                ),
                not_for=(
                    "Typing arbitrary execution output, accepting new solver "
                    "evidence, or changing profile bytes."
                ),
            ),
            executor=ExecutorRef(
                kind="transform", component=_ref("qualify_replay_profile")
            ),
            inputs=(
                InputPortSpec(
                    name="replay_request",
                    description="Exact immutable historical replay request.",
                    schema="r5.fixture.fig4-replay-request.v1",
                    media_types=("application/json",),
                    codec=_ref("json_codec"),
                    schema_resource=_ref("replay_request_schema"),
                    max_item_bytes=4096,
                    usage="prior_signal",
                    exposure="full",
                ),
                InputPortSpec(
                    name="replay_profile",
                    description="Opaque PLX collected by the frozen replay Effect.",
                    schema="opaque",
                    media_types=("application/x-synopsys-plx",),
                    codec=_ref("opaque_codec"),
                    schema_resource=_ref("opaque_schema"),
                    max_item_bytes=128 * 1024,
                    usage="evidence_inventory",
                    exposure="full",
                ),
            ),
            outputs=(
                OutputPortSpec(
                    name="candidate_profile",
                    description=(
                        "The byte-identical frozen replay PLX after exact domain "
                        "identity validation."
                    ),
                    schema="ingaas.fig4-zinc-profile-plx.v1",
                    media_types=("application/x-synopsys-plx",),
                    codec=_ref("opaque_codec"),
                    schema_resource=_ref("plx_schema"),
                    max_item_bytes=128 * 1024,
                    kind="solver_output",
                    validator=_ref("replay_profile_validator"),
                ),
            ),
            consequence="scientific",
            limits=LimitsSpec(
                timeout_seconds=30,
                max_input_bytes=132 * 1024,
                max_output_bytes=128 * 1024,
                max_files=1,
            ),
        ),
        OperationSpec(
            operation_id="r5.fixture.fig4-science-source-view.v1",
            version="1",
            catalog_scope="support",
            description=OperationDescription(
                purpose=(
                    "Expose the exact typed Fig.4 metric and frozen curve table "
                    "as byte-identical evidence-intake source views."
                ),
                applies_when=(
                    "The R5 scientific chain must inspect the already registered "
                    "typed deterministic result and curve table."
                ),
                not_for=(
                    "Computing metrics, changing scientific bytes, accepting "
                    "arbitrary schemas, or creating evidence claims."
                ),
            ),
            executor=ExecutorRef(
                kind="transform", component=_ref("project_science_sources")
            ),
            inputs=(
                InputPortSpec(
                    name="metric_report",
                    description="Exact deterministic Fig.4 baseline-recovery report.",
                    schema="ingaas.fig4-baseline-recovery.v2",
                    media_types=("application/json",),
                    codec=_ref("json_codec"),
                    schema_resource=_ref("metric_report_schema"),
                    max_item_bytes=8 * 1024 * 1024,
                    usage="prior_signal",
                    exposure="full",
                ),
                InputPortSpec(
                    name="curve_bundle",
                    description="Exact frozen Fig.4 curve comparison table.",
                    schema="ingaas.fig4-frozen-curve-table.v1",
                    media_types=("text/csv",),
                    codec=_ref("opaque_codec"),
                    schema_resource=_ref("curve_table_schema"),
                    max_item_bytes=64 * 1024 * 1024,
                    usage="evidence_inventory",
                    exposure="full",
                ),
            ),
            outputs=(
                OutputPortSpec(
                    name="metric_source",
                    description="Byte-identical opaque JSON view of the metric report.",
                    schema="opaque",
                    media_types=("application/json",),
                    codec=_ref("opaque_codec"),
                    schema_resource=_ref("opaque_schema"),
                    max_item_bytes=8 * 1024 * 1024,
                    kind="source_material",
                    validator=_ref("metric_source_validator"),
                ),
                OutputPortSpec(
                    name="curve_source",
                    description="Byte-identical opaque CSV view of the curve table.",
                    schema="opaque",
                    media_types=("text/csv",),
                    codec=_ref("opaque_codec"),
                    schema_resource=_ref("opaque_schema"),
                    max_item_bytes=64 * 1024 * 1024,
                    kind="source_material",
                    validator=_ref("curve_source_validator"),
                ),
            ),
            consequence="scientific",
            limits=LimitsSpec(
                timeout_seconds=30,
                max_input_bytes=72 * 1024 * 1024,
                max_output_bytes=72 * 1024 * 1024,
                max_files=2,
            ),
        ),
    ),
)


__all__ = ["PLUGIN"]
