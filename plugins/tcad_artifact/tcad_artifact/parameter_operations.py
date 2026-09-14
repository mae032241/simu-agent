"""TCAD-owned device-parameter Operation vertical slice.

The generic platform supplies lifecycle, approval, and Worker primitives.  This
module owns the parameter vocabulary, deterministic decisions, Agent contracts,
and approval projection that give those primitives their TCAD meaning.
"""

from __future__ import annotations

from scidiscovery.operations.input_validation import ValidationSources, parse_bound_json

from scidiscovery.operations.input_validation import OperationInvocationError
from scidiscovery.operations.spec import InputValidationSpec

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ValidationError, model_validator

from scidiscovery.artifact_agent.schema.approval import (
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.artifact_agent.schema.cognitive import (
    EvidenceAudit,
    validate_evidence_audit,
)
from scidiscovery.artifact_agent.schema.common import SchemaModel, canonical_json
from scidiscovery.artifact_agent.schema.research_cycle import (
    ScientificIntake,
    validate_scientific_intake,
)
from scidiscovery.artifact_agent.schema.scientific_foundation import ScientificFoundation
from scidiscovery.operations.invoke import ApprovalProjectorContext, ApprovalSubjectSnapshot
from scidiscovery.operation_contract import SemanticRuleViolation, declared_violation, validate_evidence_source_aliases
from scidiscovery.operation_declaration import RESEARCH_WORK_CONTEXT, semantic_contract, with_user_context
from scidiscovery.operations.spec import (
    ApprovalContract,
    ApprovalOption,
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputAdmissionSpec,
    InputPortSpec,
    LimitsSpec,
    NativeToolPolicy,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
    ReviewSpec,
    SemanticRuleSpec,
)

from .device_parameters import (
    DeviceParameterCoverageReport,
    DeviceParameterRequirementSet,
    DeviceParameterSet,
    EvidenceSourceCatalog,
    ParameterUncertaintyProjection,
    evaluate_device_parameter_coverage,
    project_parameter_uncertainty,
)


EXTRACT_OPERATION = "tcad.parameter.evidence.extract.v1"
EXPAND_OPERATION = "tcad.parameter.evidence.expand.v1"
AUDIT_OPERATION = "tcad.parameter.evidence.audit.v1"
COVERAGE_OPERATION = "science.parameter.coverage.v1"
UNCERTAINTY_OPERATION = "science.parameter.uncertainty.v1"
PASS_APPROVAL_OPERATION = "science.parameters.qualify.pass.v1"
EXCEPTION_APPROVAL_OPERATION = "science.parameters.qualify.exception.v1"
APPROVAL_PROVIDERS = (PASS_APPROVAL_OPERATION, EXCEPTION_APPROVAL_OPERATION)
PARAMETER_ADMISSION = InputAdmissionSpec(
    cohort_id="approved_parameters",
    member_ports=(
        "parameter_requirements",
        "device_parameters",
        "parameter_coverage",
    ),
    approval_subject_ports=(
        "parameter_requirements",
        "device_parameters",
        "parameter_coverage",
    ),
    approval_kind="scientific_foundation",
    accepted_options=("approve", "approve_with_exception"),
    accepted_provider_operations=APPROVAL_PROVIDERS,
)
_REVIEW_DETAIL_LIMIT = 64

_ROLE_ROOT = Path(__file__).with_name("roles")
_TOOL_PREAMBLE = RESEARCH_WORK_CONTEXT + """This is one compiled TCAD parameter Operation. Claim only
the queued assignment, materialize its controlled workspace, and read the exact
assignment and output schemas. Use only declared tools and inputs. Write and
finalize only the declared primary file. A successful Worker
result is provisional scientific content, never approval or qualification.
"""
EXTRACT_PROMPT = _TOOL_PREAMBLE + (_ROLE_ROOT / "parameter_evidence_extractor.md").read_text(
    encoding="utf-8"
)
AUDIT_PROMPT = _TOOL_PREAMBLE + (_ROLE_ROOT / "parameter_evidence_auditor.md").read_text(
    encoding="utf-8"
)
PARAMETER_SEMANTIC_CONTRACT = semantic_contract(
    SemanticRuleSpec(
        rule_id="parameter.reference_and_unit_closure",
        description=(
            "Cross-field parameter keys, units, conditions, and source references "
            "must be internally consistent."
        ),
    ),
    SemanticRuleSpec(
        rule_id="parameter.source_binding",
        description=(
            "Output references must agree with every exact declared context source "
            "that is present."
        ),
    ),
    SemanticRuleSpec(
        rule_id="parameter.package",
        description="The Agent emits one indivisible provisional parameter package.",
    ),
    SemanticRuleSpec(
        rule_id="parameter.expansion",
        description=(
            "Only the declared deterministic expansion may split its typed members."
        ),
    ),
    SemanticRuleSpec(
        rule_id="parameter.references",
        description=(
            "All objectives, source keys, units, conditions, and requirement keys "
            "close exactly."
        ),
    ),
    SemanticRuleSpec(
        rule_id="parameter.conflicts",
        description="Conflicting sources are preserved and never averaged.",
    ),
    SemanticRuleSpec(
        rule_id="parameter.qualification",
        description=(
            "Qualification is performed only by the declared approval Operations."
        ),
    ),
)


def _schema(model: type[BaseModel], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class ParameterEvidencePackage(SchemaModel):
    """One Agent-owned scientific judgment package before mechanical expansion."""

    scientific_intake: ScientificIntake
    parameter_requirements: DeviceParameterRequirementSet
    device_parameters: DeviceParameterSet
    source_catalog: EvidenceSourceCatalog

    @model_validator(mode="after")
    def _family_is_closed(self) -> ParameterEvidencePackage:
        _validate_parameter_family(
            self.scientific_intake,
            self.parameter_requirements,
            self.device_parameters,
            self.source_catalog,
        )
        return self


def _finalize_parameter_result(request):
    from scidiscovery.artifact_agent.service.result_materialization import (
        finalize_result, materialize_general_result, materialize_intake,
    )
    def project(value):
        materialize_general_result(value, request.output_schema_id)
        if request.output_schema_id != "scidiscovery.parameter-evidence-package.v1":
            return
        payload = value["payload"]
        if isinstance(payload.get("scientific_intake"), dict):
            materialize_intake(payload["scientific_intake"])
        catalog = payload.get("source_catalog")
        if isinstance(catalog, dict) and isinstance(catalog.get("sources"), list):
            for source in catalog["sources"]:
                if isinstance(source, dict) and isinstance(source.get("doi"), str):
                    source["work_key"] = "doi:" + source["doi"].lower().removeprefix("https://doi.org/")
    return finalize_result(request, project)


PARAMETER_RESULT_FINALIZER = CallableComponent("workspace_finalizer", _finalize_parameter_result)


PARAMETER_PACKAGE_SCHEMA = _schema(
    ParameterEvidencePackage, "scidiscovery.parameter-evidence-package.v1"
)


def _strict(model: type[BaseModel]):
    def validate(raw: bytes) -> None:
        try:
            model.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise SemanticRuleViolation(str(error)) from error

    return validate


def _payload(
    function: Callable[[dict[str, object]], Any],
) -> Callable[[bytes], None]:
    def validate(raw: bytes) -> None:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise SemanticRuleViolation("parameter scientific payload must be an object")
        try:
            function(value)
        except ValidationError as error:
            raise SemanticRuleViolation(str(error)) from error

    return validate


def _audit_inputs(sources: dict[str, bytes]) -> None:
    required_family = {
        "parameter_evidence_package",
        "scientific_intake",
        "parameter_requirements",
        "device_parameters",
        "source_catalog",
    }
    if not required_family.issubset(sources):
        raise OperationInvocationError("input_parameter_family_incomplete", port="parameter_evidence_package")
    package = parse_bound_json(ParameterEvidencePackage, sources["parameter_evidence_package"],
                              admission_port="parameter_evidence_package")
    expanded = {
        "scientific_intake": package.scientific_intake.canonical_json(),
        "parameter_requirements": package.parameter_requirements.canonical_json(),
        "device_parameters": package.device_parameters.canonical_json(),
        "source_catalog": package.source_catalog.canonical_json(),
    }
    if any(sources[name] != raw for name, raw in expanded.items()):
        raise OperationInvocationError("input_parameter_expansion_mismatch", port="parameter_evidence_package")


def _audit_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    audit = EvidenceAudit.model_validate_json(canonical_json(payload), strict=True)
    if not audit.checks:
        raise SemanticRuleViolation(
            "parameter evidence audit requires at least one check"
        )
    validate_evidence_source_aliases(payload, sources)
    for check in audit.checks:
        if check.status in {"pass", "fail"} and not check.evidence_keys:
            raise SemanticRuleViolation(
                "decisive parameter audit checks require evidence"
            )
    statuses = tuple(item.status for item in audit.checks)
    expected = (
        "blocked"
        if "fail" in statuses
        else "inconclusive"
        if "unknown" in statuses
        else "pass"
    )
    if handoff.get("verdict") != expected:
        raise SemanticRuleViolation(
            "parameter audit handoff differs from its checks"
        )


def _agent_marker() -> None:
    return None


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"parameter transform input {name} must contain exactly one item")
    return items[0]


def parameter_coverage(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    report = evaluate_device_parameter_coverage(
        DeviceParameterRequirementSet.model_validate_json(
            _one(values, "parameter_requirements"), strict=True
        ),
        DeviceParameterSet.model_validate_json(
            _one(values, "device_parameters"), strict=True
        ),
        EvidenceSourceCatalog.model_validate_json(
            _one(values, "source_catalog"), strict=True
        ),
    )
    return {"parameter_coverage": (report.canonical_json(),)}


def parameter_uncertainty(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    projection = project_parameter_uncertainty(
        DeviceParameterRequirementSet.model_validate_json(
            _one(values, "parameter_requirements"), strict=True
        ),
        DeviceParameterSet.model_validate_json(
            _one(values, "device_parameters"), strict=True
        ),
        DeviceParameterCoverageReport.model_validate_json(
            _one(values, "parameter_coverage"), strict=True
        ),
    )
    return {"parameter_uncertainty": (projection.canonical_json(),)}


def parameter_uncertainty_lineage(
    inputs: tuple[Any, ...], parameters: Mapping[str, Any]
) -> bool:
    del parameters
    by_port = {item.port_name: item.artifact for item in inputs}
    coverage = by_port.get("parameter_coverage")
    requirements = by_port.get("parameter_requirements")
    selected = by_port.get("device_parameters")
    return bool(
        coverage
        and requirements
        and selected
        and requirements.ref in coverage.parent_refs
        and selected.ref in coverage.parent_refs
    )


def _scientific_requirement_fields(
    value: DeviceParameterRequirementSet,
) -> dict[str, Any]:
    result = value.model_dump(mode="json")
    for item in result["parameters"]:
        item.pop("display_name", None)
    return result


def _validate_parameter_family(
    intake: ScientificIntake,
    requirements: DeviceParameterRequirementSet,
    selected: DeviceParameterSet,
    catalog: EvidenceSourceCatalog,
) -> None:
    """Validate scientific closure without storage or control-plane knowledge."""

    evaluate_device_parameter_coverage(requirements, selected, catalog)
    if not (
        intake.scientific_foundation.objective
        == requirements.objective
        == selected.objective
    ):
        raise ValueError("parameter family does not share one exact objective")
    catalog_by_key = {item.source_key: item for item in catalog.sources}
    observed_keys = {
        observation.source_key
        for claim in selected.claims
        for observation in claim.observations
    }
    if not observed_keys.issubset(catalog_by_key):
        raise ValueError("a parameter observation references an undeclared source")
    foundation_evidence = intake.scientific_foundation.evidence
    if any(
        item.source_type != catalog_by_key[item.source_key].source_type
        for item in foundation_evidence if item.source_key in catalog_by_key
    ):
        raise ValueError("parameter source type differs from the intake foundation")


def expand_parameter_evidence(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    package = ParameterEvidencePackage.model_validate_json(
        _one(values, "parameter_evidence_package"), strict=True
    )
    return {
        "scientific_intake": (package.scientific_intake.canonical_json(),),
        "parameter_requirements": (package.parameter_requirements.canonical_json(),),
        "device_parameters": (package.device_parameters.canonical_json(),),
        "source_catalog": (package.source_catalog.canonical_json(),),
    }


def validate_extract_context(
    payload: dict[str, Any], sources: ValidationSources, handoff: dict[str, Any]
) -> None:
    del handoff
    package = ParameterEvidencePackage.model_validate_json(
        canonical_json(payload), strict=True
    )
    source_aliases = {name for name, descriptor in sources.binding_descriptors.items()
                      if descriptor.port_name == "source_material"}
    for index, source in enumerate(package.source_catalog.sources):
        if source.source_key not in source_aliases:
            raise declared_violation("Parameter source must name a bound source input.",
                path=f"$.source_catalog.sources[{index}].source_key")
    validate_evidence_source_aliases(payload, sources)
    raw = sources.get("required_parameter_checklist")
    if raw is None:
        return
    required = parse_bound_json(DeviceParameterRequirementSet, raw)
    if _scientific_requirement_fields(package.parameter_requirements) != (
        _scientific_requirement_fields(required)
    ):
        raise SemanticRuleViolation(
            "parameter package requirements differ from the supplied checklist"
        )


def _subjects_by_port(
    context: ApprovalProjectorContext,
) -> dict[str, tuple[ApprovalSubjectSnapshot, ...]]:
    grouped: dict[str, list[ApprovalSubjectSnapshot]] = {}
    if len({item.ref for item in context.subjects}) != len(context.subjects):
        raise OperationInvocationError("approval_subject_invalid", message="approval subjects must be distinct exact artifacts")
    for item in context.subjects:
        grouped.setdefault(item.port_name, []).append(item)
    return {name: tuple(values) for name, values in grouped.items()}


def _one_subject(
    grouped: dict[str, tuple[ApprovalSubjectSnapshot, ...]], name: str
) -> ApprovalSubjectSnapshot:
    values = grouped.get(name, ())
    if len(values) != 1:
        raise OperationInvocationError("approval_subject_invalid", message=f"approval port {name} requires exactly one subject")
    return values[0]


def _optional_subject(
    grouped: dict[str, tuple[ApprovalSubjectSnapshot, ...]], name: str
) -> ApprovalSubjectSnapshot | None:
    values = grouped.get(name, ())
    if len(values) > 1:
        raise OperationInvocationError("approval_subject_invalid", message=f"approval port {name} accepts at most one subject")
    return values[0] if values else None


def _review_item(
    kind: str,
    label: str,
    subject: ApprovalSubjectSnapshot,
    pointer: str,
) -> ReviewDocumentItem:
    return ReviewDocumentItem(
        kind=kind,
        label=label,
        subject_index=subject.subject_index,
        json_pointer=pointer,
    )


def _labels(subject: ApprovalSubjectSnapshot) -> dict[str, str]:
    return dict(subject.labels)


def _require_transform_output(
    subject: ApprovalSubjectSnapshot,
    *,
    operation_id: str,
    port_name: str,
    parent_refs: tuple[object, ...],
) -> None:
    labels = _labels(subject)
    if (
        labels.get("operation_id") != operation_id
        or labels.get("transform_profile") != operation_id
        or labels.get("operation_output_port") != port_name
        or subject.parent_refs != parent_refs
    ):
        raise OperationInvocationError("approval_subject_invalid", message="approval subject has invalid deterministic lineage")


_AUDIT_CHECKS = frozenset(
    {
        "parameter_completeness",
        "source_traceability",
        "source_independence",
        "unit_condition_consistency",
    }
)


def _validate_parameter_qualification(
    context: ApprovalProjectorContext, expected_status: str
) -> tuple:
    grouped = _subjects_by_port(context)
    foundation_subject = _one_subject(grouped, "scientific_foundation")
    package_subject = _one_subject(grouped, "parameter_evidence_package")
    primary_subject = _one_subject(grouped, "extraction_primary")
    required_checklist_subject = _optional_subject(
        grouped, "required_parameter_checklist"
    )
    requirements_subject = _one_subject(grouped, "parameter_requirements")
    parameters_subject = _one_subject(grouped, "device_parameters")
    catalog_subject = _one_subject(grouped, "source_catalog")
    coverage_subject = _one_subject(grouped, "parameter_coverage")
    audit_subject = _one_subject(grouped, "parameter_audit")
    expanded_families = tuple(
        item
        for item in context.producer_families
        if item.primary_ref == primary_subject.ref
        and item.operation_id == EXPAND_OPERATION
    )
    extraction_families = tuple(
        item
        for item in context.producer_families
        if item.primary_ref == package_subject.ref
        and item.operation_id == EXTRACT_OPERATION
    )
    if len(expanded_families) != 1 or len(extraction_families) != 1:
        raise OperationInvocationError("approval_subject_invalid", message="parameter approval requires exact extraction and expansion families")
    family = expanded_families[0]
    extraction_family = extraction_families[0]
    if (
        family.reviewer_operation != AUDIT_OPERATION
        or family.review_subject_outputs != ("scientific_intake",)
    ):
        raise OperationInvocationError("approval_subject_invalid", message="parameter expansion has an invalid review contract")
    if (
        len(extraction_family.members) != 1
        or extraction_family.members[0].port_name != "parameter_evidence_package"
        or extraction_family.members[0].ref != package_subject.ref
    ):
        raise OperationInvocationError("approval_subject_invalid", message="parameter package does not belong to the extraction Run")
    expected_members = {
        "parameter_requirements": requirements_subject.ref,
        "device_parameters": parameters_subject.ref,
        "source_catalog": catalog_subject.ref,
    }
    member_by_port = {item.port_name: item for item in family.members[1:]}
    if set(member_by_port) != set(expected_members) or any(
        member_by_port[name].ref != ref for name, ref in expected_members.items()
    ):
        raise OperationInvocationError("approval_subject_invalid", message="parameter approval does not bind the complete output family")
    for name, subject in (
        ("scientific_intake", primary_subject),
        ("parameter_requirements", requirements_subject),
        ("device_parameters", parameters_subject),
        ("source_catalog", catalog_subject),
    ):
        if subject.parent_refs != (package_subject.ref,):
            raise OperationInvocationError("approval_subject_invalid", message=f"{name} is not an exact deterministic expansion")
    unexpected_source_kinds = {
        source.source_kind
        for source in extraction_family.evidence_sources
        if source.source_kind != "run_input"
    }
    if unexpected_source_kinds:
        raise OperationInvocationError("approval_subject_invalid", message="parameter extraction has an unsupported evidence-source kind")
    frozen_sources = extraction_family.evidence_sources
    frozen_refs = tuple(source.ref for source in frozen_sources)
    expected_source_keys = {source.source_name for source in frozen_sources}
    if (
        len(expected_source_keys) != len(frozen_sources)
        or len(set(frozen_refs)) != len(frozen_refs)
    ):
        raise OperationInvocationError("approval_subject_invalid", message="parameter extraction source identities must be unique")
    if tuple(item.ref for item in grouped.get("frozen_sources", ())) != frozen_refs:
        raise OperationInvocationError("approval_subject_invalid", message="parameter approval omits or adds a frozen source")
    checklist_refs = (
        ()
        if required_checklist_subject is None
        else (required_checklist_subject.ref,)
    )
    extraction_inputs = extraction_family.producer_inputs
    if extraction_inputs is None:
        raise OperationInvocationError("input_producer_metadata_unavailable", port="parameter_evidence_package",
            message="The exact completed extraction's saved input bindings are unavailable.")
    if (tuple(ref for _, ref in extraction_inputs) != package_subject.parent_refs
        or tuple(ref for port, ref in extraction_inputs
                 if port in {"required_parameter_checklist", "source_material"})
        != (*checklist_refs, *frozen_refs)):
        raise OperationInvocationError("approval_subject_invalid", message="parameter package does not preserve its exact extraction inputs")

    package = parse_bound_json(ParameterEvidencePackage, package_subject.content, admission_port=package_subject.port_name)
    intake = parse_bound_json(ScientificIntake, primary_subject.content, admission_port=primary_subject.port_name)
    foundation = parse_bound_json(ScientificFoundation, foundation_subject.content, admission_port=foundation_subject.port_name)
    requirements = parse_bound_json(DeviceParameterRequirementSet, requirements_subject.content, admission_port=requirements_subject.port_name)
    if required_checklist_subject is not None:
        required_checklist = parse_bound_json(DeviceParameterRequirementSet, required_checklist_subject.content, admission_port=required_checklist_subject.port_name)
        if _scientific_requirement_fields(required_checklist) != (
            _scientific_requirement_fields(requirements)
        ):
            raise OperationInvocationError("approval_subject_invalid", message="extracted parameter requirements differ from the supplied checklist")
    selected = parse_bound_json(DeviceParameterSet, parameters_subject.content, admission_port=parameters_subject.port_name)
    catalog = parse_bound_json(EvidenceSourceCatalog, catalog_subject.content, admission_port=catalog_subject.port_name)
    if not {item.source_key for item in catalog.sources}.issubset(expected_source_keys):
        raise OperationInvocationError("approval_subject_invalid", message="parameter source catalog differs from frozen Run inputs")
    supplied_coverage = parse_bound_json(DeviceParameterCoverageReport, coverage_subject.content, admission_port=coverage_subject.port_name)
    if (
        package.scientific_intake != intake
        or package.parameter_requirements != requirements
        or package.device_parameters != selected
        or package.source_catalog != catalog
    ):
        raise OperationInvocationError("approval_subject_invalid", message="expanded parameter objects differ from the Agent package")
    if foundation != intake.scientific_foundation:
        raise OperationInvocationError("approval_subject_invalid", message="parameter foundation differs from extraction primary")
    _require_transform_output(
        foundation_subject,
        operation_id="science.intake.split.v1",
        port_name="scientific_foundation",
        parent_refs=(primary_subject.ref, audit_subject.ref),
    )
    if not (foundation.objective == requirements.objective == selected.objective):
        raise OperationInvocationError("approval_subject_invalid", message="parameter review subjects have different objectives")
    _require_transform_output(
        coverage_subject,
        operation_id=COVERAGE_OPERATION,
        port_name="parameter_coverage",
        parent_refs=(requirements_subject.ref, parameters_subject.ref, catalog_subject.ref),
    )
    recomputed = evaluate_device_parameter_coverage(requirements, selected, catalog)
    if supplied_coverage != recomputed or coverage_subject.content != recomputed.canonical_json():
        raise OperationInvocationError("approval_subject_invalid", message="parameter coverage differs from deterministic recomputation")
    if recomputed.status != expected_status:
        raise OperationInvocationError("approval_subject_invalid", message="parameter coverage does not match this approval Operation")
    audit_labels = _labels(audit_subject)
    if (
        audit_labels.get("operation_id") != AUDIT_OPERATION
        or audit_subject.handoff_verdict != "pass"
    ):
        raise OperationInvocationError("approval_subject_invalid", message="parameter audit is not an independent passing Operation result")
    expected_audit_inputs = (
        package_subject.ref,
        primary_subject.ref,
        *((required_checklist_subject.ref,) if required_checklist_subject is not None else ()),
        requirements_subject.ref,
        parameters_subject.ref,
        catalog_subject.ref,
        coverage_subject.ref,
        *frozen_refs,
    )
    audit_families = tuple(family for family in context.producer_families
        if family.primary_ref == audit_subject.ref and family.operation_id == AUDIT_OPERATION)
    if len(audit_families) != 1 or audit_families[0].producer_inputs is None:
        raise OperationInvocationError("input_producer_metadata_unavailable", port="parameter_audit",
            message="The exact completed parameter audit's saved input bindings are unavailable.")
    audit_inputs = audit_families[0].producer_inputs
    if (tuple(ref for _, ref in audit_inputs) != audit_subject.parent_refs
        or tuple(ref for port, ref in audit_inputs if port in {item.name for item in AUDIT_INPUTS})
        != expected_audit_inputs):
        raise OperationInvocationError("approval_subject_invalid", message="parameter audit does not bind the exact ordered review set")
    audit = parse_bound_json(EvidenceAudit, audit_subject.content, admission_port=audit_subject.port_name)
    checks = {item.check_key: item for item in audit.checks}
    if not _AUDIT_CHECKS.issubset(checks) or any(
        checks[name].status != "pass" for name in _AUDIT_CHECKS
    ):
        raise OperationInvocationError("approval_subject_invalid", message="parameter audit lacks a required passing check")
    return (foundation_subject, parameters_subject, catalog_subject, coverage_subject,
            audit_subject, selected, catalog, recomputed, audit)


def _parameter_qualification_document(context: ApprovalProjectorContext, expected_status: str) -> ReviewDocument:
    facts = _validate_parameter_qualification(context, expected_status)
    return _render_parameter_qualification(expected_status, *facts)


def _render_parameter_qualification(expected_status, foundation_subject, parameters_subject,
        catalog_subject, coverage_subject, audit_subject, selected, catalog, recomputed, audit):
    if len(selected.claims) > _REVIEW_DETAIL_LIMIT:
        claim_items = (
            _review_item(
                "json_tree", f"全部参数主张（{len(selected.claims)} 项）",
                parameters_subject, "/claims",
            ),
        )
    else:
        claim_items = tuple(
            item
            for index, _claim in enumerate(selected.claims, start=1)
            for item in (
                _review_item(
                    "json_value", f"参数 {index}：参数键",
                    parameters_subject, f"/claims/{index - 1}/parameter_key",
                ),
                _review_item(
                    "json_value", f"参数 {index}：选定值",
                    parameters_subject, f"/claims/{index - 1}/selected_value",
                ),
                _review_item(
                    "json_value", f"参数 {index}：单位",
                    parameters_subject, f"/claims/{index - 1}/unit",
                ),
                _review_item(
                    "status", f"参数 {index}：认识状态",
                    parameters_subject, f"/claims/{index - 1}/epistemic_status",
                ),
            )
        )
    coverage_issues = tuple(
        (index, item)
        for index, item in enumerate(recomputed.items)
        if item.status not in {"confirmed", "authoritative_single"}
    )
    if len(coverage_issues) > _REVIEW_DETAIL_LIMIT:
        coverage_items = (
            _review_item(
                "json_tree", f"全部覆盖明细（{len(recomputed.items)} 项）",
                coverage_subject, "/items",
            ),
        )
    else:
        coverage_items = tuple(
            _review_item(
                "json_tree", f"覆盖项 {display_index}",
                coverage_subject, f"/items/{item_index}",
            )
            for display_index, (item_index, _item) in enumerate(
                coverage_issues, start=1
            )
        )
    source_items = tuple(
        item
        for index, _source in enumerate(catalog.sources, start=1)
        for item in (
            _review_item(
                "json_value", f"来源 {index}：来源键",
                catalog_subject, f"/sources/{index - 1}/source_key",
            ),
            _review_item(
                "json_tree", f"来源 {index}：详情",
                catalog_subject, f"/sources/{index - 1}",
            ),
        )
    )
    audit_items = tuple(
        _review_item("status", item.check_key, audit_subject, f"/checks/{index}/status")
        for index, item in enumerate(audit.checks)
        if item.check_key in _AUDIT_CHECKS
    )
    return ReviewDocument(
        title=("器件参数资格审查" if expected_status == "pass" else "器件参数例外资格审查"),
        description="审查完整参数输出族、来源目录、确定性覆盖和独立审核。",
        sections=(
            ReviewDocumentSection(
                title="资格结论",
                description="确定性覆盖结果；人工审批不改写这些冻结值。",
                items=(
                    _review_item("status", "资格状态", coverage_subject, "/status"),
                    _review_item(
                        "json_value", "已确认参数数",
                        coverage_subject, "/confirmed_count",
                    ),
                    _review_item(
                        "json_value", "待复核参数数",
                        coverage_subject, "/review_count",
                    ),
                    _review_item(
                        "json_value", "阻断参数数",
                        coverage_subject, "/blocking_count",
                    ),
                ),
            ),
            ReviewDocumentSection(
                title="研究目标与参数",
                description=f"共 {len(selected.claims)} 项参数主张。",
                items=(
                    _review_item(
                        "json_value", "冻结研究目标",
                        foundation_subject, "/objective",
                    ),
                    _review_item(
                        "json_value", "科学依据摘要",
                        foundation_subject, "/summary",
                    ),
                    *claim_items,
                ),
            ),
            ReviewDocumentSection(
                title="限制与待处理项",
                description="缺失输入、开放问题和未确认覆盖项。",
                items=(
                    _review_item(
                        "json_tree", "缺失输入",
                        foundation_subject, "/missing_inputs",
                    ),
                    _review_item(
                        "json_tree", "开放问题",
                        foundation_subject, "/open_questions",
                    ),
                    *coverage_items,
                ),
            ),
            ReviewDocumentSection(
                title="来源与独立审查",
                description=f"共 {len(catalog.sources)} 个来源；以下检查均来自冻结审计。",
                items=(
                    *source_items,
                    *audit_items,
                ),
            ),
        ),
    )


EXTRACT_AGENT = CallableComponent("agent", _agent_marker)
AUDIT_AGENT = CallableComponent("agent", _agent_marker)
INTAKE_VALIDATOR = CallableComponent(
    "validator", _payload(validate_scientific_intake)
)
PACKAGE_VALIDATOR = CallableComponent(
    "validator", _strict(ParameterEvidencePackage)
)
AUDIT_VALIDATOR = CallableComponent(
    "validator", _payload(validate_evidence_audit)
)
AUDIT_CONTEXT_VALIDATOR = CallableComponent("validator", _audit_context)
REQUIREMENTS_VALIDATOR = CallableComponent("validator", _strict(DeviceParameterRequirementSet))
PARAMETERS_VALIDATOR = CallableComponent("validator", _strict(DeviceParameterSet))
CATALOG_VALIDATOR = CallableComponent("validator", _strict(EvidenceSourceCatalog))
COVERAGE_VALIDATOR = CallableComponent("validator", _strict(DeviceParameterCoverageReport))
UNCERTAINTY_VALIDATOR = CallableComponent("validator", _strict(ParameterUncertaintyProjection))
EXTRACT_CONTEXT_VALIDATOR = CallableComponent("validator", validate_extract_context)
EXPAND_TRANSFORM = CallableComponent("transform", expand_parameter_evidence)
COVERAGE_TRANSFORM = CallableComponent("transform", parameter_coverage)
UNCERTAINTY_TRANSFORM = CallableComponent("transform", parameter_uncertainty)
UNCERTAINTY_LINEAGE = CallableComponent("guard", parameter_uncertainty_lineage)
PASS_PROJECTOR = CallableComponent(
    "projector", lambda context: _parameter_qualification_document(context, "pass")
)
EXCEPTION_PROJECTOR = CallableComponent(
    "projector", lambda context: _parameter_qualification_document(context, "review_required")
)


def _ref(name: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)


def _input(
    name: str,
    description: str,
    schema: str,
    resource: str | ComponentRef,
    *,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
    max_items: int = 1,
    max_item_bytes: int = 2 * 1024 * 1024,
    exposure: str = "full",
    usage: str = "claim_evidence",
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=_ref(
            "opaque_codec" if schema in {"opaque", "*"} else "json_codec",
            "general_science",
        ),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        exposure=exposure,
        usage=usage,
    )


def _output(
    name: str,
    description: str,
    kind: str,
    schema: str,
    resource: str | ComponentRef,
    validator: str,
    *,
    max_item_bytes: int = 2 * 1024 * 1024,
    context_validator: str | None = None,
    context_sources: tuple[str, ...] = (),
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=description,
        kind=kind,
        schema=schema,
        media_types=("application/json",),
        codec=_ref("json_codec", "general_science"),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        min_items=1,
        max_items=1,
        max_item_bytes=max_item_bytes,
        validator=_ref(validator),
        validator_rule_id="parameter.reference_and_unit_closure",
        semantic_contract=_ref("parameter_semantic_contract"),
        context_validator=_ref(context_validator) if context_validator else None,
        context_rule_id="parameter.source_binding" if context_validator else None,
        context_sources=context_sources,
        evidence_paths=(
            ("/scientific_foundation/evidence",)
            if name == "scientific_intake"
            else ("/scientific_intake/scientific_foundation/evidence",)
            if name == "parameter_evidence_package"
            else ()
        ),
    )


_BUILTIN_TOOLS = tuple(
    _ref(name, "builtin")
    for name in (
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
    )
)
_PARAMETER_TOOLS = _BUILTIN_TOOLS + (
    _ref("file_apply_patch_tool", "builtin"),
    _ref("pdf_extract_tool", "general_science"),
)


def _agent(
    operation_id: str,
    description: OperationDescription,
    *,
    agent: str,
    prompt: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    timeout: int,
    max_input_bytes: int,
    max_output_bytes: int,
    max_files: int,
    review: ReviewSpec | None = None,
    input_validation: InputValidationSpec | None = None,
) -> OperationSpec:
    return with_user_context(OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="public",
        description=description,
        executor=ExecutorRef(
            kind="agent",
            component=_ref(agent),
            workspace=_ref("parameter_workspace"),
            tools=_PARAMETER_TOOLS,
            prompt=_ref(prompt),
            model="gpt-5.6-sol",
            native_tools=NativeToolPolicy(shell="inherited_prototype", view_image=True),
        ),
        inputs=inputs,
        outputs=outputs,
        consequence="scientific",
        review=review,
        input_validation=input_validation,
        limits=LimitsSpec(
            timeout_seconds=timeout,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_files=max_files,
        ),
    ))


EXTRACT_OUTPUTS = (
    _output(
        "parameter_evidence_package",
        "One source-bound TCAD parameter package before deterministic expansion.",
        "parameter_evidence_package",
        "scidiscovery.parameter-evidence-package.v1",
        "parameter_package_schema",
        "parameter_package_validator",
        max_item_bytes=7 * 1024 * 1024,
        context_validator="parameter_extract_context",
        context_sources=("required_parameter_checklist", "source_material"),
    ),
)


EXTRACT_INPUTS = (
    _input(
        "required_parameter_checklist",
        "Optional immutable TCAD parameter checklist whose scientific fields must be preserved.",
        "scidiscovery.device-parameter-requirements.v1",
        "parameter_requirements_schema",
        min_items=0,
        usage="prior_signal",
    ),
    _input(
        "source_material",
        "Exact frozen device description, paper, table, or user source.",
        "opaque",
        _ref("opaque_schema", "general_science"),
        media_types=(
            "application/json",
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "text/plain",
            "text/plain; charset=utf-8",
            "text/csv",
        ),
        min_items=1,
        max_items=32,
        max_item_bytes=32 * 1024 * 1024,
        usage="evidence_inventory",
    ),
)


EXPAND_INPUTS = (
    _input(
        "parameter_evidence_package",
        "Exact provisional TCAD parameter package.",
        "scidiscovery.parameter-evidence-package.v1",
        "parameter_package_schema",
        usage="prior_signal",
        max_item_bytes=7 * 1024 * 1024,
    ),
)


EXPAND_OUTPUTS = (
    _output(
        "scientific_intake",
        "Parameter-scoped scientific intake and source-bound foundation.",
        "scientific_intake",
        "scidiscovery.scientific-intake.v1",
        _ref("scientific_intake_schema", "general_science"),
        "intake_validator",
        max_item_bytes=64 * 1024,
    ),
    _output(
        "parameter_requirements",
        "Exact TCAD parameter checklist.",
        "device_parameter_requirements",
        "scidiscovery.device-parameter-requirements.v1",
        "parameter_requirements_schema",
        "parameter_requirements_validator",
    ),
    _output(
        "device_parameters",
        "Selected values and all competing source observations.",
        "device_parameters",
        "scidiscovery.device-parameter-set.v1",
        "device_parameters_schema",
        "device_parameters_validator",
    ),
    _output(
        "source_catalog",
        "Exact catalog of every parameter evidence source.",
        "evidence_source_catalog",
        "scidiscovery.evidence-source-catalog.v1",
        "source_catalog_schema",
        "source_catalog_validator",
    ),
)


AUDIT_INPUTS = (
    _input("parameter_evidence_package", "Exact Agent package under review.", "scidiscovery.parameter-evidence-package.v1", "parameter_package_schema", usage="prior_signal", max_item_bytes=7 * 1024 * 1024),
    _input("scientific_intake", "Extraction primary under review.", "scidiscovery.scientific-intake.v1", _ref("scientific_intake_schema", "general_science"), usage="prior_signal"),
    _input("required_parameter_checklist", "Optional immutable checklist supplied to extraction.", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema", min_items=0, usage="evidence_inventory"),
    _input("parameter_requirements", "Exact extracted checklist.", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema", usage="evidence_inventory"),
    _input("device_parameters", "Exact selected parameter set.", "scidiscovery.device-parameter-set.v1", "device_parameters_schema", usage="evidence_inventory"),
    _input("source_catalog", "Exact source catalog.", "scidiscovery.evidence-source-catalog.v1", "source_catalog_schema", usage="evidence_inventory"),
    _input("parameter_coverage", "Deterministic coverage report.", "scidiscovery.device-parameter-coverage.v1", "parameter_coverage_schema", usage="prior_signal"),
    _input(
        "source_material",
        "Every exact frozen source declared by the extraction family.",
        "opaque",
        _ref("opaque_schema", "general_science"),
        media_types=(
            "application/json",
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "text/plain",
            "text/plain; charset=utf-8",
            "text/csv",
        ),
        min_items=1,
        max_items=32,
        max_item_bytes=32 * 1024 * 1024,
        exposure="on_demand",
        usage="evidence_inventory",
    ),
)


def _transform(
    operation_id: str,
    component: str,
    purpose: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    *,
    input_admission: InputAdmissionSpec | None = None,
    guards: tuple[ComponentRef, ...] = (),
    review: ReviewSpec | None = None,
    max_output_bytes: int = 2 * 1024 * 1024,
    max_files: int = 1,
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="support",
        description=OperationDescription(
            purpose=purpose,
            applies_when="All exact typed inputs are available.",
            not_for="Scientific interpretation, source invention, or qualification.",
        ),
        executor=ExecutorRef(kind="transform", component=_ref(component)),
        inputs=inputs,
        outputs=outputs,
        consequence="scientific",
        input_admission=input_admission,
        guards=guards,
        review=review,
        limits=LimitsSpec(
            timeout_seconds=300,
            max_input_bytes=8 * 1024 * 1024,
            max_output_bytes=max_output_bytes,
            max_files=max_files,
        ),
    )


def _approval_input(
    name: str,
    description: str,
    schema: str,
    resource: str | ComponentRef,
    *,
    min_items: int = 1,
    max_items: int = 1,
    media_types: tuple[str, ...] = ("application/json",),
    max_item_bytes: int = 32 * 1024 * 1024,
) -> InputPortSpec:
    return _input(
        name,
        description,
        schema,
        resource,
        min_items=min_items,
        max_items=max_items,
        media_types=media_types,
        max_item_bytes=max_item_bytes,
        exposure="handoff_only" if schema == "*" else "full",
        usage="evidence_inventory" if name not in {"scientific_foundation", "extraction_primary", "parameter_coverage", "parameter_audit"} else "prior_signal",
    )


PARAMETER_APPROVAL_INPUTS = (
    _approval_input("scientific_foundation", "Exact foundation split from the extraction primary.", "scidiscovery.scientific-foundation.v1", _ref("scientific_foundation_schema", "general_science")),
    _approval_input("parameter_evidence_package", "Exact Agent-produced parameter package.", "scidiscovery.parameter-evidence-package.v1", "parameter_package_schema", max_item_bytes=7 * 1024 * 1024),
    _approval_input("extraction_primary", "Exact parameter extraction primary.", "scidiscovery.scientific-intake.v1", _ref("scientific_intake_schema", "general_science")),
    _approval_input("required_parameter_checklist", "Optional immutable checklist supplied to extraction.", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema", min_items=0),
    _approval_input("parameter_requirements", "Complete parameter requirement set.", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema"),
    _approval_input("device_parameters", "Complete selected parameter set.", "scidiscovery.device-parameter-set.v1", "device_parameters_schema"),
    _approval_input("source_catalog", "Complete source catalog.", "scidiscovery.evidence-source-catalog.v1", "source_catalog_schema"),
    _approval_input("parameter_coverage", "Deterministic parameter coverage.", "scidiscovery.device-parameter-coverage.v1", "parameter_coverage_schema"),
    _approval_input("parameter_audit", "Independent parameter audit.", "scidiscovery.evidence-audit.v1", _ref("evidence_audit_schema", "general_science")),
    _approval_input("frozen_sources", "Complete frozen source set.", "*", _ref("wildcard_schema", "general_science"), min_items=1, max_items=32, media_types=("*/*",)),
)


def _approval_operation(
    operation_id: str,
    projector: str,
    description: OperationDescription,
    question: str,
    options: tuple[ApprovalOption, ...],
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="2",
        catalog_scope="public",
        description=description,
        executor=ExecutorRef(kind="approval", component=_ref(projector)),
        inputs=PARAMETER_APPROVAL_INPUTS,
        outputs=(),
        consequence="scientific",
        review=ReviewSpec(
            approval=ApprovalContract(
                subject_ports=tuple(port.name for port in PARAMETER_APPROVAL_INPUTS),
                question=question,
                options=options,
                projector=_ref(projector),
                kind="scientific_foundation",
            )
        ),
        limits=LimitsSpec(
            timeout_seconds=60,
            max_input_bytes=512 * 1024 * 1024,
            max_output_bytes=512 * 1024,
            max_files=1,
        ),
    )


AUDIT_INPUT_VALIDATOR = CallableComponent("validator", _audit_inputs)

COMPONENT_SPECS = (
    ComponentSpec("parameter_result_finalizer", "workspace_finalizer", "tcad_artifact.parameter_operations:PARAMETER_RESULT_FINALIZER"),
    ComponentSpec("parameter_workspace", "workspace", "scidiscovery.general_science_components:WORKSPACE",
                  resources=(_ref("parameter_result_finalizer"),)),
    ComponentSpec("parameter_audit_inputs", "validator", "tcad_artifact.parameter_operations:AUDIT_INPUT_VALIDATOR"),
    ComponentSpec("parameter_extract_agent", "agent", "tcad_artifact.parameter_operations:EXTRACT_AGENT"),
    ComponentSpec("parameter_audit_agent", "agent", "tcad_artifact.parameter_operations:AUDIT_AGENT"),
    ComponentSpec("parameter_extract_prompt", "resource", "tcad_artifact.parameter_operations:EXTRACT_PROMPT"),
    ComponentSpec("parameter_audit_prompt", "resource", "tcad_artifact.parameter_operations:AUDIT_PROMPT"),
    ComponentSpec("parameter_semantic_contract", "resource", "tcad_artifact.parameter_operations:PARAMETER_SEMANTIC_CONTRACT"),
    ComponentSpec("parameter_package_schema", "resource", "tcad_artifact.parameter_operations:PARAMETER_PACKAGE_SCHEMA"),
    ComponentSpec("intake_validator", "validator", "tcad_artifact.parameter_operations:INTAKE_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("parameter_package_validator", "validator", "tcad_artifact.parameter_operations:PACKAGE_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("audit_validator", "validator", "tcad_artifact.parameter_operations:AUDIT_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("evidence_audit_context", "validator", "tcad_artifact.parameter_operations:AUDIT_CONTEXT_VALIDATOR", configuration_identity="input-boundary-r4:v1", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("parameter_requirements_validator", "validator", "tcad_artifact.parameter_operations:REQUIREMENTS_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("device_parameters_validator", "validator", "tcad_artifact.parameter_operations:PARAMETERS_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("source_catalog_validator", "validator", "tcad_artifact.parameter_operations:CATALOG_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("parameter_coverage_validator", "validator", "tcad_artifact.parameter_operations:COVERAGE_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("parameter_uncertainty_validator", "validator", "tcad_artifact.parameter_operations:UNCERTAINTY_VALIDATOR", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("parameter_extract_context", "validator", "tcad_artifact.parameter_operations:EXTRACT_CONTEXT_VALIDATOR", configuration_identity="parameter.source-material-aliases:v2", resources=(_ref("parameter_semantic_contract"),)),
    ComponentSpec("parameter_expand", "transform", "tcad_artifact.parameter_operations:EXPAND_TRANSFORM"),
    ComponentSpec("parameter_coverage", "transform", "tcad_artifact.parameter_operations:COVERAGE_TRANSFORM"),
    ComponentSpec("parameter_uncertainty", "transform", "tcad_artifact.parameter_operations:UNCERTAINTY_TRANSFORM"),
    ComponentSpec("parameter_uncertainty_lineage", "guard", "tcad_artifact.parameter_operations:UNCERTAINTY_LINEAGE"),
    ComponentSpec("parameter_pass_projector", "projector", "tcad_artifact.parameter_operations:PASS_PROJECTOR", configuration_identity="parameter.producer-inputs:v2"),
    ComponentSpec("parameter_exception_projector", "projector", "tcad_artifact.parameter_operations:EXCEPTION_PROJECTOR", configuration_identity="parameter.producer-inputs:v2"),
)


OPERATIONS = (
    _agent(
        EXTRACT_OPERATION,
        OperationDescription(
            purpose="Extract one complete source-bound TCAD device-parameter family.",
            applies_when="A bounded TCAD objective and exact frozen sources are available.",
            not_for="Generic evidence extraction, figure digitization, or parameter qualification.",
        ),
        agent="parameter_extract_agent",
        prompt="parameter_extract_prompt",
        inputs=EXTRACT_INPUTS,
        outputs=EXTRACT_OUTPUTS,
        timeout=1200,
        max_input_bytes=1025 * 1024 * 1024,
        max_output_bytes=7 * 1024 * 1024,
        max_files=1,
    ),
    _transform(
        EXPAND_OPERATION,
        "parameter_expand",
        "Mechanically expand one validated TCAD parameter package into typed objects.",
        EXPAND_INPUTS,
        EXPAND_OUTPUTS,
        review=ReviewSpec(
            reviewer_operation=AUDIT_OPERATION,
            reviewer_input_port="scientific_intake",
            subject_outputs=("scientific_intake",),
        ),
        max_output_bytes=7 * 1024 * 1024,
        max_files=4,
    ),
    _agent(
        AUDIT_OPERATION,
        OperationDescription(
            purpose="Independently audit one exact TCAD parameter family and all frozen sources.",
            applies_when="Extraction and deterministic coverage are complete.",
            not_for="Extracting, repairing, qualifying, or averaging parameter evidence.",
        ),
        input_validation=InputValidationSpec(_ref("parameter_audit_inputs"), "tcad.parameter.audit.inputs", "The exact parameter package must equal every bound expanded family member."),
        agent="parameter_audit_agent",
        prompt="parameter_audit_prompt",
        inputs=AUDIT_INPUTS,
        outputs=(
            _output(
                "evidence_audit",
                "Independent parameter completeness, traceability, independence, and unit audit.",
                "evidence_audit",
                "scidiscovery.evidence-audit.v1",
                _ref("evidence_audit_schema", "general_science"),
                "audit_validator",
                max_item_bytes=32 * 1024,
                context_validator="evidence_audit_context",
                context_sources=tuple(port.name for port in AUDIT_INPUTS),
            ),
        ),
        timeout=900,
        max_input_bytes=1032 * 1024 * 1024,
        max_output_bytes=32 * 1024,
        max_files=1,
    ),
    _transform(
        COVERAGE_OPERATION,
        "parameter_coverage",
        "Evaluate exact TCAD parameter evidence coverage without selecting values.",
        (
            _input("parameter_requirements", "Exact parameter requirements.", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema", usage="evidence_inventory"),
            _input("device_parameters", "Exact selected parameter evidence.", "scidiscovery.device-parameter-set.v1", "device_parameters_schema", usage="evidence_inventory"),
            _input("source_catalog", "Exact source catalog.", "scidiscovery.evidence-source-catalog.v1", "source_catalog_schema", usage="evidence_inventory"),
        ),
        (
            _output("parameter_coverage", "Deterministic coverage report.", "device_parameter_coverage", "scidiscovery.device-parameter-coverage.v1", "parameter_coverage_schema", "parameter_coverage_validator"),
        ),
    ),
    _transform(
        UNCERTAINTY_OPERATION,
        "parameter_uncertainty",
        "Project an approved TCAD parameter set into a deterministic use gate.",
        tuple(
            _input(
                name,
                description,
                schema,
                resource,
                usage="evidence_inventory" if name != "parameter_coverage" else "prior_signal",
            )
            for name, description, schema, resource in (
                ("parameter_requirements", "Exact parameter requirements.", "scidiscovery.device-parameter-requirements.v1", "parameter_requirements_schema"),
                ("device_parameters", "Exact selected parameter evidence.", "scidiscovery.device-parameter-set.v1", "device_parameters_schema"),
                ("parameter_coverage", "Exact deterministic coverage.", "scidiscovery.device-parameter-coverage.v1", "parameter_coverage_schema"),
            )
        ),
        (
            _output("parameter_uncertainty", "Fixed, bounded, or blocking use projection.", "parameter_uncertainty", "scidiscovery.parameter-uncertainty.v1", "parameter_uncertainty_schema", "parameter_uncertainty_validator"),
        ),
        input_admission=PARAMETER_ADMISSION,
        guards=(_ref("parameter_uncertainty_lineage"),),
    ),
    _approval_operation(
        PASS_APPROVAL_OPERATION,
        "parameter_pass_projector",
        OperationDescription(
            purpose="Create one human qualification review for a passing TCAD parameter set.",
            applies_when="Coverage and the exact independent parameter audit pass.",
            not_for="Review-required or blocking parameter coverage.",
        ),
        "是否批准这组覆盖通过且已独立审核的器件参数？",
        (
            ApprovalOption("批准", "accept"),
            ApprovalOption("要求修订", "revise", requires_reason=True),
        ),
    ),
    _approval_operation(
        EXCEPTION_APPROVAL_OPERATION,
        "parameter_exception_projector",
        OperationDescription(
            purpose="Create one rationale-required exception review for a bounded TCAD parameter set.",
            applies_when="Coverage requires review and the exact independent audit passes.",
            not_for="Passing or blocking parameter coverage.",
        ),
        "是否在明确记录理由后例外批准这组有界器件参数？",
        (
            ApprovalOption("带理由例外批准", "accept_with_exception", requires_reason=True),
            ApprovalOption("要求修订", "revise", requires_reason=True),
        ),
    ),
)


__all__ = [
    "APPROVAL_PROVIDERS",
    "COMPONENT_SPECS",
    "EXPAND_OPERATION",
    "OPERATIONS",
    "ParameterEvidencePackage",
    "expand_parameter_evidence",
]
