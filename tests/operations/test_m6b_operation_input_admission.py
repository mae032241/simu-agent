from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import (
    RootOperationRoutes,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
from scidiscovery.operations.invoke import OperationInvocationError
from scidiscovery.operations.spec import InputAdmissionSpec
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


def _replace_general(operation_id: str, **changes):
    operations = tuple(
        operation.model_copy(update=changes)
        if operation.operation_id == operation_id
        else operation
        for operation in GENERAL_PLUGIN.operations
    )
    return GENERAL_PLUGIN.model_copy(update={"operations": operations})


def _expect_compile_error(code: str, plugin) -> None:
    with pytest.raises(CatalogCompileError) as caught:
        compile_catalog((CORE_PLUGIN, plugin))
    assert caught.value.reason_code == code


def _full_catalog():
    return compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )


def test_admission_is_one_operation_fact_not_repeated_on_ports() -> None:
    catalog = _full_catalog()
    operation = catalog.operation("science.hypothesis.propose.v1")
    admission = operation.spec.input_admission

    assert admission is not None
    assert admission.member_ports == ("scientific_foundation",)
    assert admission.approval_subject_ports == admission.member_ports
    assert len(operation.approval_providers) == 1
    assert all(
        "cohort_id" not in type(port).model_fields
        and "approval_kind" not in type(port).model_fields
        for port in operation.spec.inputs
    )

    view = next(
        item
        for item in catalog.scheduler_projection()
        if item.operation_id == operation.spec.operation_id
    )
    assert "input_admission" not in type(view).model_fields
    assert all("cohort_id" not in type(port).model_fields for port in view.inputs)


@pytest.mark.parametrize(
    "admission",
    (
        InputAdmissionSpec(
            cohort_id="qualified_foundation",
            member_ports=("missing",),
            approval_subject_ports=("missing",),
            approval_kind="scientific_foundation",
            accepted_options=("approve",),
            accepted_provider_operations=("science.evidence.qualify.v1",),
        ),
        InputAdmissionSpec(
            cohort_id="qualified_foundation",
            member_ports=("scientific_foundation",),
            approval_subject_ports=("missing",),
            approval_kind="scientific_foundation",
            accepted_options=("approve",),
            accepted_provider_operations=("science.evidence.qualify.v1",),
        ),
    ),
)
def test_compiler_rejects_unknown_or_nonmember_admission_ports(admission) -> None:
    _expect_compile_error(
        "input_admission_invalid",
        _replace_general(
            "science.hypothesis.propose.v1", input_admission=admission
        ),
    )


def test_compiler_rejects_non_singular_admission_member() -> None:
    target = next(
        operation
        for operation in GENERAL_PLUGIN.operations
        if operation.operation_id == "science.hypothesis.propose.v1"
    )
    ports = tuple(
        port.model_copy(update={"max_items": 2})
        if port.name == "scientific_foundation"
        else port
        for port in target.inputs
    )
    _expect_compile_error(
        "input_admission_invalid",
        _replace_general(
            target.operation_id,
            inputs=ports,
            limits=target.limits.model_copy(
                update={"max_input_bytes": target.limits.max_input_bytes * 2}
            ),
        ),
    )


def test_compiler_rejects_unknown_provider_and_digest_covers_admission() -> None:
    target = next(
        operation
        for operation in GENERAL_PLUGIN.operations
        if operation.operation_id == "science.hypothesis.propose.v1"
    )
    missing = target.input_admission.model_copy(
        update={"accepted_provider_operations": ("science.missing.qualify.v1",)}
    )
    _expect_compile_error(
        "approval_provider_missing",
        _replace_general(target.operation_id, input_admission=missing),
    )

    baseline = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN)).operation(
        target.operation_id
    ).digest
    renamed = target.input_admission.model_copy(
        update={"cohort_id": "renamed_foundation"}
    )
    changed = compile_catalog(
        (
            CORE_PLUGIN,
            _replace_general(target.operation_id, input_admission=renamed),
        )
    ).operation(target.operation_id).digest
    assert changed != baseline


def test_compiler_rejects_unavailable_options_and_nested_provider_gate() -> None:
    consumer = next(
        operation
        for operation in GENERAL_PLUGIN.operations
        if operation.operation_id == "science.hypothesis.propose.v1"
    )
    unsupported = consumer.input_admission.model_copy(
        update={"accepted_options": ("defer",)}
    )
    _expect_compile_error(
        "approval_provider_options_invalid",
        _replace_general(consumer.operation_id, input_admission=unsupported),
    )

    provider = next(
        operation
        for operation in GENERAL_PLUGIN.operations
        if operation.operation_id == "science.evidence.qualify.v1"
    )
    nested = InputAdmissionSpec(
        cohort_id="nested_qualification",
        member_ports=("scientific_foundation",),
        approval_subject_ports=("scientific_foundation",),
        approval_kind="scientific_foundation",
        accepted_options=("approve",),
        accepted_provider_operations=(provider.operation_id,),
    )
    operations = tuple(
        operation.model_copy(update={"input_admission": nested})
        if operation.operation_id == provider.operation_id
        else operation
        for operation in GENERAL_PLUGIN.operations
    )
    _expect_compile_error(
        "approval_provider_invalid",
        GENERAL_PLUGIN.model_copy(update={"operations": operations}),
    )


def _bound(operation, present_ports: tuple[str, ...]):
    inputs = tuple(
        SimpleNamespace(
            port_name=name,
            artifact=SimpleNamespace(ref=f"ref:{name}"),
        )
        for name in present_ports
    )
    return SimpleNamespace(compiled=operation, inputs=inputs)


def test_root_consumes_compiled_member_and_subject_sets_without_reaggregation() -> None:
    operation = _full_catalog().operation("science.hypothesis.propose.v1")
    admission = operation.spec.input_admission
    assert admission is not None
    approvals = Mock()
    approvals.are_subjects_approved_by_provider.return_value = True
    routes = object.__new__(RootOperationRoutes)
    routes.approvals = approvals

    routes._validate_compiled_input_admission(
        _bound(operation, admission.member_ports)
    )

    call = approvals.are_subjects_approved_by_provider.call_args
    assert call.args[0] == tuple(
        f"ref:{name}" for name in admission.approval_subject_ports
    )
    assert call.kwargs["kind"] == admission.approval_kind
    assert call.kwargs["accepted_options"] == admission.accepted_options
    assert len(call.kwargs["accepted_providers"]) == 1


def test_root_preserves_fail_closed_approval_behavior_after_structural_binding() -> None:
    operation = _full_catalog().operation("science.hypothesis.propose.v1")
    admission = operation.spec.input_admission
    assert admission is not None
    routes = object.__new__(RootOperationRoutes)
    routes.approvals = Mock()
    routes.approvals.are_subjects_approved_by_provider.return_value = False

    with pytest.raises(OperationInvocationError) as unapproved:
        routes._validate_compiled_input_admission(
            _bound(operation, admission.member_ports)
        )
    assert unapproved.value.reason_code == "input_cohort_approval_missing"
