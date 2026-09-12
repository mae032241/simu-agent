from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from pydantic import ValidationError
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tcad_artifact.parameter_operations import (
    AUDIT_OPERATION,
    AUDIT_CONTEXT_VALIDATOR,
    AUDIT_INPUT_VALIDATOR,
    COVERAGE_OPERATION,
    EXPAND_OPERATION,
    PASS_APPROVAL_OPERATION,
    ParameterEvidencePackage,
)
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


def _package(source_key: str = "source_a") -> ParameterEvidencePackage:
    objective = "Validate one bounded TCAD parameter."
    return ParameterEvidencePackage.model_validate_json(
        canonical_json(
            {
                "scientific_intake": {
                    "problem_frame": {
                        "title": "Parameter frame",
                        "scientific_question": "Is the declared scale source-bound?",
                        "objective": objective,
                        "current_contradiction": "The scale is not yet frozen.",
                        "scope": "One dimensionless fixture parameter.",
                        "foundation_item_keys": ["parameter_fact"],
                        "observables": [
                            {
                                "observable_key": "scale",
                                "description": "The declared fixture scale.",
                                "role": "target",
                                "foundation_item_keys": ["parameter_fact"],
                                "acceptance_relevance": "It fixes the bounded input.",
                            }
                        ],
                        "claim_boundary": {
                            "allowed_claim": "Only the frozen scale is supported.",
                            "required_conditions": ["The exact source remains bound."],
                        },
                        "stop_conditions": ["Stop after deterministic expansion."],
                    },
                    "scientific_foundation": {
                        "title": "Parameter foundation",
                        "objective": objective,
                        "summary": "One user source declares the scale.",
                        "evidence": [
                            {
                                "source_key": source_key,
                                "source_type": "frozen_input",
                                "title": "Frozen source A",
                                "locator": f"{source_key}:line-1",
                            }
                        ],
                        "items": [
                            {
                                "item_key": "parameter_fact",
                                "item_type": "parameter",
                                "epistemic_status": "user_defined",
                                "statement": "The fixture scale is one.",
                                "value": "1e+0",
                                "unit": "1",
                                "scope": "The bounded fixture only.",
                                "evidence_keys": [source_key],
                            }
                        ],
                    },
                },
                "parameter_requirements": {
                    "requirement_set_key": "fixture_requirements",
                    "title": "Fixture requirements",
                    "device_key": "fixture_device",
                    "objective": objective,
                    "parameters": [
                        {
                            "parameter_key": "scale",
                            "display_name": "Scale",
                            "category": "geometry",
                            "device_scope": "Fixture",
                            "canonical_unit": "1",
                            "criticality": "required",
                            "minimum_independent_sources": 1,
                            "allow_authoritative_single": True,
                            "assumption_policy": "forbidden",
                            "agreement_rule": {"kind": "exact"},
                            "required_condition_names": [],
                        }
                    ],
                },
                "device_parameters": {
                    "parameter_set_key": "fixture_parameters",
                    "requirement_set_key": "fixture_requirements",
                    "title": "Fixture parameters",
                    "objective": objective,
                    "claims": [
                        {
                            "parameter_key": "scale",
                            "selected_value": "1e+0",
                            "unit": "1",
                            "conditions": [],
                            "epistemic_status": "user_defined",
                            "observations": [
                                {
                                    "source_key": source_key,
                                    "reported_value": "1e+0",
                                    "reported_unit": "1",
                                    "conditions": [],
                                    "locator": f"{source_key}:line-1",
                                    "evidence_mode": "direct_report",
                                }
                            ],
                            "selection_rationale": "Use the exact frozen declaration.",
                        }
                    ],
                },
                "source_catalog": {
                    "catalog_key": "fixture_sources",
                    "sources": [
                        {
                            "source_key": source_key,
                            "source_type": "frozen_input",
                            "title": "Frozen source A",
                            "source_class": "user_source",
                            "work_key": f"user:{source_key}",
                        }
                    ],
                },
            }
        ),
        strict=True,
    )


def _root(tmp_path: Path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="parameter_package",
        title="Parameter package expansion",
        objective="Verify one Agent package and deterministic expansion.",
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            runs=runtime.runs,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            operation_catalog=catalog,
        )
    )
    return catalog, runtime, instance, root


def _envelope(payload: object, *, verdict: str = "pass") -> bytes:
    return canonical_json(
        {
            "schema_version": 1,
            "handoff": {
                "verdict": verdict,
                "summary": "Bounded M2 parameter result.",
            },
            "payload": payload,
        }
    )


def _complete_agent(
    catalog,
    runtime,
    operation_id: str,
    payload: object,
    *,
    verdict: str = "pass",
) -> str:
    compiled = catalog.operation(operation_id)
    instance_id = runtime.scheduler_bindings.list_instances()[0].instance_id
    pending = next(
        item
        for item in runtime.runs.list(instance_id=instance_id)
        if item.operation_id == operation_id and item.state == "queued"
    )
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(payload, verdict=verdict)
    )
    completed = worker.call_tool("worker_submit_result", {})
    assert completed["state"] == "completed"
    return runtime.runs.status(pending.run_id).output_binding_name


def test_parameter_agent_is_local_runnable_and_has_one_package_output() -> None:
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    extraction = catalog.operation("tcad.parameter.evidence.extract.v1")

    assert tuple(port.name for port in extraction.spec.outputs) == (
        "parameter_evidence_package",
    )
    assert LocalTrustedBackend.supports_operation(extraction)
    assert LocalTrustedBackend.unsupported_requirements(extraction) == ()


def test_parameter_catalog_and_preflight_share_local_capability(tmp_path) -> None:
    _, runtime, instance, root = _root(tmp_path)
    source = runtime.artifacts.register(
        b"scale = 1\n",
        ArtifactRegistration(
            kind="parameter_source",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="text/plain",
            creator=runtime.actor,
        ),
        idempotency_key="m2:parameter-source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="parameter_source",
        object_id=source.artifact_id,
    )
    item = next(
        value
        for value in root.call_tool("operation_catalog", {"scope": "public"})[
            "operations"
        ]
        if value["operation_id"] == "tcad.parameter.evidence.extract.v1"
    )

    assert "runtime_binding" not in item
    assert root.call_tool(
        "operation_preflight",
        {
            "name": "extract_parameters",
            "operation_id": "tcad.parameter.evidence.extract.v1",
            "inputs": [
                {
                    "port": "source_material",
                    "artifact_names": ["parameter_source"],
                }
            ],
            "instruction": "Extract the exact frozen parameter declaration.",
        },
    )["admissible"] is True
    assert runtime.runs.list(instance_id=instance.instance_id) == ()


@pytest.mark.parametrize("with_checklist", (False, True), ids=("no-checklist", "checklist"))
def test_real_parameter_run_reaches_expansion_audit_and_qualification(
    tmp_path, with_checklist: bool,
) -> None:
    catalog, runtime, instance, root = _root(tmp_path)
    source = runtime.artifacts.register(
        b"scale = 1\n",
        ArtifactRegistration(
            kind="parameter_source",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="text/plain",
            creator=runtime.actor,
        ),
        idempotency_key="m2:real-parameter-source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="parameter_source",
        object_id=source.artifact_id,
    )
    checklist_name = None
    if with_checklist:
        checklist_name = "required_parameter_checklist"
        checklist = runtime.artifacts.register(
            _package().parameter_requirements.canonical_json(),
            ArtifactRegistration(
                kind="device_parameter_requirements",
                schema_id="scidiscovery.device-parameter-requirements.v1",
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key="m2:required-parameter-checklist",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=checklist_name,
            object_id=checklist.artifact_id,
        )
    extraction_inputs = [
        {"port": "source_material", "artifact_names": ["parameter_source"]}
    ]
    if checklist_name is not None:
        extraction_inputs.insert(
            0,
            {
                "port": "required_parameter_checklist",
                "artifact_names": [checklist_name],
            },
        )
    root.call_tool(
        "operation_invoke",
        {
            "name": "extract_parameters",
            "operation_id": "tcad.parameter.evidence.extract.v1",
            "inputs": extraction_inputs,
            "instruction": "Extract the exact frozen parameter declaration.",
        },
    )
    package_name = _complete_agent(
        catalog,
        runtime,
        "tcad.parameter.evidence.extract.v1",
        _package("source_material").model_dump(mode="json"),
    )
    expand_request = {
        "name": "expanded_parameters",
        "operation_id": EXPAND_OPERATION,
        "inputs": [
            {
                "port": "parameter_evidence_package",
                "artifact_names": [package_name],
            }
        ],
    }
    assert root.call_tool("operation_preflight", expand_request)["admissible"] is True
    expanded = root.call_tool("operation_invoke", expand_request)["result"]["outputs"]
    expanded_names = {item["output_label"]: item["artifact_name"] for item in expanded}
    coverage_name = root.call_tool(
        "operation_invoke",
        {
            "name": "parameter_coverage",
            "operation_id": COVERAGE_OPERATION,
            "inputs": [
                {
                    "port": "parameter_requirements",
                    "artifact_names": [expanded_names["parameter_requirements"]],
                },
                {
                    "port": "device_parameters",
                    "artifact_names": [expanded_names["device_parameters"]],
                },
                {
                    "port": "source_catalog",
                    "artifact_names": [expanded_names["source_catalog"]],
                },
            ],
        },
    )["result"]["outputs"][0]["artifact_name"]
    audit_inputs = [
        {
            "port": "parameter_evidence_package",
            "artifact_names": [package_name],
        },
        {
            "port": "scientific_intake",
            "artifact_names": [expanded_names["primary"]],
        },
        {
            "port": "parameter_requirements",
            "artifact_names": [expanded_names["parameter_requirements"]],
        },
        {
            "port": "device_parameters",
            "artifact_names": [expanded_names["device_parameters"]],
        },
        {
            "port": "source_catalog",
            "artifact_names": [expanded_names["source_catalog"]],
        },
        {"port": "parameter_coverage", "artifact_names": [coverage_name]},
        {"port": "source_material", "artifact_names": ["parameter_source"]},
    ]
    if checklist_name is not None:
        audit_inputs.insert(
            2,
            {
                "port": "required_parameter_checklist",
                "artifact_names": [checklist_name],
            },
        )
    audit_request = {
        "name": "parameter_audit",
        "operation_id": AUDIT_OPERATION,
        "inputs": audit_inputs,
        "instruction": "Audit the exact package, expansion, coverage, and source.",
    }
    assert root.call_tool("operation_preflight", audit_request)["admissible"] is True
    root.call_tool("operation_invoke", audit_request)
    audit_payload = {
        "schema_version": 1,
        "checks": [
            {
                "check_key": check_key,
                "subject": "The bounded parameter family is exact.",
                "status": "pass",
                "basis": "The frozen source and deterministic objects agree.",
                "evidence_keys": ["source_material"],
            }
            for check_key in (
                "parameter_completeness",
                "source_traceability",
                "source_independence",
                "unit_condition_consistency",
            )
        ],
        "evidence": [
            {
                "source_key": "source_material",
                "source_type": "frozen_input",
                "locator": "source_material:line-1",
            }
        ],
    }
    audit_name = _complete_agent(catalog, runtime, AUDIT_OPERATION, audit_payload)
    split = root.call_tool(
        "operation_invoke",
        {
            "name": "parameter_frame",
            "operation_id": "science.intake.split.v1",
            "inputs": [
                {
                    "port": "scientific_intake",
                    "artifact_names": [expanded_names["primary"]],
                },
                {"port": "evidence_audit", "artifact_names": [audit_name]},
            ],
        },
    )["result"]["outputs"]
    split_names = {item["output_label"]: item["artifact_name"] for item in split}
    approval_inputs = [
        {
            "port": "scientific_foundation",
            "artifact_names": [split_names["scientific_foundation"]],
        },
        {
            "port": "parameter_evidence_package",
            "artifact_names": [package_name],
        },
        {
            "port": "extraction_primary",
            "artifact_names": [expanded_names["primary"]],
        },
        {
            "port": "parameter_requirements",
            "artifact_names": [expanded_names["parameter_requirements"]],
        },
        {
            "port": "device_parameters",
            "artifact_names": [expanded_names["device_parameters"]],
        },
        {
            "port": "source_catalog",
            "artifact_names": [expanded_names["source_catalog"]],
        },
        {"port": "parameter_coverage", "artifact_names": [coverage_name]},
        {"port": "parameter_audit", "artifact_names": [audit_name]},
        {"port": "frozen_sources", "artifact_names": ["parameter_source"]},
    ]
    if checklist_name is not None:
        approval_inputs.insert(
            3,
            {
                "port": "required_parameter_checklist",
                "artifact_names": [checklist_name],
            },
        )
    approval_request = {
        "name": "qualify_parameters",
        "operation_id": PASS_APPROVAL_OPERATION,
        "inputs": approval_inputs,
    }
    assert root.call_tool("operation_preflight", approval_request)["admissible"] is True
    approval = root.call_tool("operation_invoke", approval_request)
    assert approval["result"]["status"] == "pending"

    # The saved audit is history after its contract changes, not a new approval witness.
    from scidiscovery.operations.input_validation import OperationInvocationError
    from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
    typed = OperationCallInput.model_validate(approval_request)
    values = {**typed.model_dump(exclude={"inputs"}), "inputs": typed.inputs}
    bound = root.facade._prepare_operation_call(**values)
    changed = TCAD_PLUGIN.model_copy(update={"operations": tuple(
        op.model_copy(update={"version": "auditor-upgrade"})
        if op.operation_id == AUDIT_OPERATION else op for op in TCAD_PLUGIN.operations)})
    upgraded = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, changed))
    runtime.runs.operation_catalog = root.facade._operation_catalog = upgraded
    with pytest.raises(OperationInvocationError, match="approval_subject_invalid") as failure:
        root.facade._prepare_approval_projection(bound)
    assert failure.value.details[0]["phase"] == "input_admission"
    assert "independent passing" in failure.value.details[0]["message"]
    old_request = {**approval_request, "name": "old_audit_parameters"}
    before = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval")
    assert not root.call_tool("operation_preflight", old_request)["admissible"]
    with pytest.raises(Exception):
        root.call_tool("operation_invoke", old_request)
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace="approval") == before
    runtime.runs.operation_catalog = root.facade._operation_catalog = catalog

    alternate_requirements = _package().parameter_requirements.model_copy(deep=True)
    alternate_payload = alternate_requirements.model_dump(mode="json")
    alternate_payload["parameters"][0]["display_name"] = "Alternate display label"
    alternate_checklist = runtime.artifacts.register(
        canonical_json(alternate_payload),
        ArtifactRegistration(
            kind="device_parameter_requirements",
            schema_id="scidiscovery.device-parameter-requirements.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key=f"m2:alternate-checklist:{with_checklist}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="alternate_parameter_checklist",
        object_id=alternate_checklist.artifact_id,
    )
    wrong_checklist_inputs = [
        (
            {
                **item,
                "artifact_names": ["alternate_parameter_checklist"],
            }
            if item["port"] == "required_parameter_checklist"
            else item
        )
        for item in approval_request["inputs"]
    ]
    if not with_checklist:
        wrong_checklist_inputs.insert(
            3,
            {
                "port": "required_parameter_checklist",
                "artifact_names": ["alternate_parameter_checklist"],
            },
        )
    approval_count = len(runtime.approvals.list_requests(limit=100))
    wrong_checklist = root.call_tool(
        "operation_preflight",
        {
            **approval_request,
            "name": "qualify_with_wrong_checklist",
            "inputs": wrong_checklist_inputs,
        },
    )
    assert wrong_checklist["admissible"] is False
    assert wrong_checklist["reason_code"] == "approval_subject_invalid"
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count

    missing_source_request = {
        **approval_request,
        "name": "qualify_without_source",
        "inputs": [
            item
            for item in approval_request["inputs"]
            if item["port"] != "frozen_sources"
        ],
    }
    missing_source = root.call_tool("operation_preflight", missing_source_request)
    assert missing_source["admissible"] is False
    assert missing_source["port"] == "frozen_sources"

    extra_source = runtime.artifacts.register(
        b"unrelated source\n",
        ArtifactRegistration(
            kind="parameter_source",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="text/plain",
            creator=runtime.actor,
        ),
        idempotency_key="m2:extra-parameter-source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="extra_parameter_source",
        object_id=extra_source.artifact_id,
    )
    extra_source_request = {
        **approval_request,
        "name": "qualify_with_extra_source",
        "inputs": [
            (
                {
                    **item,
                    "artifact_names": [
                        "parameter_source",
                        "extra_parameter_source",
                    ],
                }
                if item["port"] == "frozen_sources"
                else item
            )
            for item in approval_request["inputs"]
        ],
    }
    approval_count = len(runtime.approvals.list_requests(limit=100))
    extra_source_preflight = root.call_tool(
        "operation_preflight", extra_source_request
    )
    assert extra_source_preflight["admissible"] is False
    assert extra_source_preflight["reason_code"] == "approval_subject_invalid"
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count
    with pytest.raises(RootToolError, match="approval_subject_invalid"):
        root.call_tool("operation_invoke", extra_source_request)
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count

    requirements_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=expanded_names["parameter_requirements"],
    )
    requirements = runtime.artifacts.get_by_id(requirements_id)
    fake_requirements = runtime.artifacts.register(
        runtime.artifacts.read(requirements.ref),
        ArtifactRegistration(
            kind=requirements.kind,
            schema_id=requirements.schema_id,
            payload_schema_version=requirements.payload_schema_version,
            media_type=requirements.media_type,
            creator=runtime.actor,
        ),
        idempotency_key="m2:fake-parameter-requirements",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="fake_parameter_requirements",
        object_id=fake_requirements.artifact_id,
    )
    wrong_family_request = {
        **approval_request,
        "name": "qualify_wrong_family",
        "inputs": [
            (
                {**item, "artifact_names": ["fake_parameter_requirements"]}
                if item["port"] == "parameter_requirements"
                else item
            )
            for item in approval_request["inputs"]
        ],
    }
    wrong_family_preflight = root.call_tool(
        "operation_preflight", wrong_family_request
    )
    assert wrong_family_preflight["admissible"] is False
    assert wrong_family_preflight["reason_code"] == "approval_subject_invalid"
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count
    with pytest.raises(RootToolError, match="approval_subject_invalid"):
        root.call_tool("operation_invoke", wrong_family_request)
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count

    root.call_tool(
        "operation_invoke",
        {**audit_request, "name": "failed_parameter_audit"},
    )
    failed_audit_payload = {
        **audit_payload,
        "checks": [
            {
                **item,
                "status": "fail" if index == 0 else item["status"],
            }
            for index, item in enumerate(audit_payload["checks"])
        ],
    }
    failed_audit_name = _complete_agent(
        catalog,
        runtime,
        AUDIT_OPERATION,
        failed_audit_payload,
        verdict="blocked",
    )
    failed_review_request = {
        **approval_request,
        "name": "qualify_failed_audit",
        "inputs": [
            (
                {**item, "artifact_names": [failed_audit_name]}
                if item["port"] == "parameter_audit"
                else item
            )
            for item in approval_request["inputs"]
        ],
    }
    failed_review = root.call_tool("operation_preflight", failed_review_request)
    assert failed_review["admissible"] is False
    assert failed_review["reason_code"] == "input_independent_review_missing"

    root.call_tool(
        "operation_invoke",
        {
            "name": "extract_parameters",
            "operation_id": "tcad.parameter.evidence.extract.v1",
            "inputs": [
                {
                    "port": "source_material",
                    "artifact_names": ["parameter_source"],
                }
            ],
            "instruction": "Intentionally revise the parameter package.",
            "on_conflict": "create_revision",
        },
    )
    revised_payload = _package("source_material").model_dump(mode="json")
    revised_payload["scientific_intake"]["problem_frame"]["title"] = (
        "Revised parameter frame"
    )
    revised_package_name = _complete_agent(
        catalog,
        runtime,
        "tcad.parameter.evidence.extract.v1",
        revised_payload,
    )
    revised_expansion = root.call_tool(
        "operation_invoke",
        {
            "name": "expanded_parameters",
            "operation_id": EXPAND_OPERATION,
            "inputs": [
                {
                    "port": "parameter_evidence_package",
                    "artifact_names": [revised_package_name],
                }
            ],
            "on_conflict": "create_revision",
        },
    )["result"]["outputs"]
    revised_primary = next(
        item["artifact_name"]
        for item in revised_expansion
        if item["output_label"] == "primary"
    )
    stale_review = root.call_tool(
        "operation_preflight",
        {
            "name": "revised_parameter_frame",
            "operation_id": "science.intake.split.v1",
            "inputs": [
                {
                    "port": "scientific_intake",
                    "artifact_names": [revised_primary],
                },
                {"port": "evidence_audit", "artifact_names": [audit_name]},
            ],
        },
    )
    assert stale_review["admissible"] is False
    assert stale_review["reason_code"] == "input_independent_review_missing"


def test_parameter_run_rejects_package_with_invented_source_alias(tmp_path) -> None:
    catalog, runtime, instance, root = _root(tmp_path)
    source = runtime.artifacts.register(
        b"scale = 1\n",
        ArtifactRegistration(
            kind="parameter_source",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="text/plain",
            creator=runtime.actor,
        ),
        idempotency_key="m2:alias-source",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="parameter_source",
        object_id=source.artifact_id,
    )
    root.call_tool(
        "operation_invoke",
        {
            "name": "extract_parameters",
            "operation_id": "tcad.parameter.evidence.extract.v1",
            "inputs": [
                {
                    "port": "source_material",
                    "artifact_names": ["parameter_source"],
                }
            ],
            "instruction": "Exercise exact source alias validation.",
        },
    )
    compiled = catalog.operation("tcad.parameter.evidence.extract.v1")
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    result_schema = json.loads(
        Path(opened["workspace_path"], "schema", "result.schema.json").read_text(
            "utf-8"
        )
    )
    package_schema = result_schema["properties"]["payload"]
    intake_ref = package_schema["properties"]["scientific_intake"]["$ref"]
    intake_schema = package_schema["$defs"][intake_ref.removeprefix("#/$defs/")]
    foundation_ref = intake_schema["properties"]["scientific_foundation"]["$ref"]
    foundation_schema = package_schema["$defs"][
        foundation_ref.removeprefix("#/$defs/")
    ]
    projected_source = foundation_schema["properties"]["evidence"]["items"][
        "allOf"
    ][-1]["properties"]["source_key"]
    assert projected_source["enum"] == ["source_material"]
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(_package("invented_source").model_dump(mode="json"))
    )

    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert len(rejected["diagnostics"]) == 1
    diagnostic = rejected["diagnostics"][0]
    assert {key: diagnostic[key] for key in ("path", "type", "rule_id", "code", "phase", "repairable")} == {
        "path": (
            "$.payload.scientific_intake.scientific_foundation."
            "evidence[0].source_key"
        ),
        "type": "json_schema.enum",
        "rule_id": "runtime.schema",
        "code": "output_invalid",
        "phase": "output_payload",
        "repairable": True,
    }
    active = tuple(
        item
        for item in runtime.runs.list(instance_id=instance.instance_id)
        if item.operation_id == "tcad.parameter.evidence.extract.v1"
    )
    assert len(active) == 1 and active[0].state == "running"
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(_package("source_material").model_dump(mode="json"))
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"


def test_parameter_package_expands_deterministically_and_idempotently(tmp_path) -> None:
    catalog, runtime, instance, root = _root(tmp_path)
    package = _package()
    envelope = runtime.artifacts.register(
        package.canonical_json(),
        ArtifactRegistration(
            kind="parameter_evidence_package",
            schema_id="scidiscovery.parameter-evidence-package.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="m2:parameter-package",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="parameter_package",
        object_id=envelope.artifact_id,
    )
    request = {
        "name": "expanded_parameters",
        "operation_id": EXPAND_OPERATION,
        "inputs": [
            {
                "port": "parameter_evidence_package",
                "artifact_names": ["parameter_package"],
            }
        ],
    }

    first = root.call_tool("operation_invoke", request)
    assert root.call_tool("operation_invoke", request) == first
    assert [item["output_label"] for item in first["result"]["outputs"]] == [
        "primary",
        "parameter_requirements",
        "device_parameters",
        "source_catalog",
    ]
    expected = (
        ("expanded_parameters", package.scientific_intake.canonical_json()),
        (
            "expanded_parameters.parameter_requirements",
            package.parameter_requirements.canonical_json(),
        ),
        (
            "expanded_parameters.device_parameters",
            package.device_parameters.canonical_json(),
        ),
        (
            "expanded_parameters.source_catalog",
            package.source_catalog.canonical_json(),
        ),
    )
    for name, content in expected:
        artifact_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
        )
        output = runtime.artifacts.get_by_id(artifact_id)
        assert output.parent_refs == (envelope.ref,)
        assert output.labels["operation_id"] == EXPAND_OPERATION
        assert runtime.artifacts.read(output.ref) == content
    assert catalog.operation(EXPAND_OPERATION).spec.catalog_scope == "support"


def test_parameter_package_rejects_cross_object_objective_drift() -> None:
    raw = _package().model_dump(mode="json")
    raw["device_parameters"]["objective"] = "A different objective."

    with pytest.raises(ValidationError, match="one exact objective"):
        ParameterEvidencePackage.model_validate_json(canonical_json(raw), strict=True)


def test_parameter_audit_rejects_noncanonical_expansion() -> None:
    package = _package()
    sources = {
        "parameter_evidence_package": package.canonical_json(),
        "scientific_intake": package.scientific_intake.canonical_json(),
        "parameter_requirements": package.parameter_requirements.canonical_json(),
        "device_parameters": package.device_parameters.canonical_json(),
        "source_catalog": package.source_catalog.canonical_json(),
        "source_material": b"scale = 1",
    }
    payload = {
        "schema_version": 1,
        "checks": [
            {
                "check_key": "source_traceability",
                "subject": "The frozen declaration is present.",
                "status": "pass",
                "basis": "The exact source is bound to this audit.",
                "evidence_keys": ["source_material"],
            }
        ],
        "evidence": [
            {
                "source_key": "source_material",
                "source_type": "frozen_input",
                "locator": "source_material:line-1",
            }
        ],
    }
    validator = AUDIT_CONTEXT_VALIDATOR.implementation

    validator(payload, sources, {"verdict": "pass"})
    drifted = dict(sources)
    drifted["scientific_intake"] += b"\n"
    AUDIT_INPUT_VALIDATOR.implementation(sources)
    with pytest.raises(ValueError, match="input_parameter_expansion_mismatch"):
        AUDIT_INPUT_VALIDATOR.implementation(drifted)
    # Output acceptance does not retry input admission.
    validator(payload, drifted, {"verdict": "pass"})
