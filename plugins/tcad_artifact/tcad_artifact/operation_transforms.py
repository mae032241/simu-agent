"""Operation components for the existing deterministic TCAD transforms."""

from __future__ import annotations

import json
import hashlib
from scidiscovery.operations.input_validation import parse_bound_json, OperationInvocationError
from types import MappingProxyType
from typing import Any, Mapping

from scidiscovery.artifact_agent.schema.comparison import (
    RealizationSnapshot,
    StudyControlEquivalenceReport,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.execution_context import ExecutionContext
from scidiscovery.artifact_agent.schema.experiment import (
    ComparisonContract,
    ExperimentPortfolio,
)
from scidiscovery.operations.spec import (
    CallableComponent,
    CollectionSpec,
    ComponentRef,
    ComponentSpec,
    ExecutorRef,
    InputPortSpec,
    InputValidationSpec,
    LimitsSpec,
    OperationDescription,
    OperationSpec,
    OutputPortSpec,
)

from .project_packager import (
    DeckProjectDraft,
    DeckReviewReport,
    ReviewedDeckPackage,
    RuntimeAttestation,
    TCADRuntimeManifest,
)
from .execution_control import SolverCapabilitySnapshot
from .debug_contract import DEVELOPMENT_ARTIFACT_LIMIT_BYTES
from .transform_adapter import (
    attest_runtime as attest_runtime_payload,
    compare_projects,
    evaluate_control_equivalence_outputs,
    materialize_realization_snapshot,
    package_reviewed_project,
    validate_review_payload,
)


DECK_COMPARE_OPERATION = "tcad.deck-project-compare.v1"
DECK_REVIEW_VALIDATION_OPERATION = "tcad.deck-review-validate.v1"
REVIEWED_DECK_PACKAGE_OPERATION = "tcad.reviewed-deck-package.v2"
RUNTIME_ATTESTATION_OPERATION = "tcad.runtime-attestation.v1"
REALIZATION_SNAPSHOT_OPERATION = "tcad.realization-snapshot-materialize.v1"
CONTROL_EQUIVALENCE_OPERATION = "tcad.control-equivalence.v1"
EXECUTION_CONTEXT_OPERATION = "tcad.execution-context.project.v1"


def _schema(model: type[Any], schema_id: str) -> str:
    value = model.model_json_schema(mode="validation")
    value["$id"] = schema_id
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _object_schema(schema_id: str) -> str:
    return json.dumps(
        {"$id": schema_id, "type": "object"},
        separators=(",", ":"),
        sort_keys=True,
    )


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"TCAD transform input {name} must contain exactly one item")
    return items[0]


def compare(values: Mapping[str, tuple[bytes, ...]]) -> dict[str, tuple[bytes, ...]]:
    return compare_projects(
        {
            "base_project": _one(values, "base_project"),
            "revised_project": _one(values, "revised_project"),
        },
    )


def validate_review(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    return validate_review_payload(
        {"project": _one(values, "project"), "review": _one(values, "review")},
    )


def package(values: Mapping[str, tuple[bytes, ...]]) -> dict[str, tuple[bytes, ...]]:
    inputs = {
        name: _one(values, name)
        for name in ("project", "review", "capability", "experiment_plan")
    }
    return package_reviewed_project(inputs)


def project_execution_plan(values):
    project = DeckProjectDraft.model_validate_json(_one(values, "project"), strict=True)
    if project.execution_plan is None:
        raise ValueError("Only a sealed project with an embedded execution_plan can be projected")
    return {"experiment_plan": (canonical_json(project.execution_plan.model_dump(mode="json")),)}


def require_skeleton_project_origin(descriptor, *, port="project"):
    labels = dict(descriptor.labels)
    if (descriptor.producer_run_id is None
        or labels.get("operation_id") not in {"tcad.deck.author.initial.v1", "tcad.deck.author.revise.v1", "tcad.deck.author.runtime-failure.v1"}
        or labels.get("operation_version") != "3"):
        raise OperationInvocationError("input_skeleton_project_producer_required", port=port,
            message="A new skeleton project must be the sealed output of a completed supported author Run; added fields or labels cannot upgrade legacy/imported projects.")


def projection_inputs(sources):
    project = parse_bound_json(DeckProjectDraft, sources["project"], admission_port="project")
    if project.execution_plan is None:
        raise OperationInvocationError("input_embedded_plan_missing", port="project")
    require_skeleton_project_origin(sources.binding_descriptors["project"])


def package_inputs(sources):
    project = parse_bound_json(DeckProjectDraft, sources["project"], admission_port="project")
    plan = parse_bound_json(ExperimentPortfolio, sources["experiment_plan"], admission_port="experiment_plan")
    if project.execution_plan is None:
        if dict(sources.binding_descriptors["experiment_plan"].labels).get("operation_id") == "tcad.execution-plan.project.v1":
            raise OperationInvocationError("input_projected_plan_legacy_mismatch", port="experiment_plan")
        if "scientific_skeleton" in sources:
            raise OperationInvocationError("input_package_plan_branch_mismatch", port="scientific_skeleton")
        return
    if "scientific_skeleton" not in sources or "experiment_review" in sources:
        raise OperationInvocationError("input_package_review_branch_mismatch", port="scientific_skeleton")
    if project.execution_plan != plan:
        raise OperationInvocationError("input_project_execution_plan_mismatch", port="experiment_plan")
    report = parse_bound_json(DeckReviewReport, sources["review"], admission_port="review")
    if report.verdict != "pass" or report.scientific_assessment != "pass":
        raise OperationInvocationError("input_comprehensive_review_required", port="review")
    descriptors = sources.binding_descriptors
    projected = descriptors["experiment_plan"]
    subject = descriptors["project"]
    require_skeleton_project_origin(subject)
    skeleton = descriptors["scientific_skeleton"]
    review = descriptors["review"]
    skeleton_labels = dict(skeleton.labels)
    if (skeleton.producer_run_id is None
        or skeleton_labels.get("operation_id") != "science.experiment.skeleton.v1"):
        raise OperationInvocationError("input_skeleton_objective_source_required", port="scientific_skeleton",
            message="A skeleton project can be packaged only when its skeleton came from the completed design Operation that sealed the exact research objective source.")
    if subject.artifact_ref not in projected.parent_refs or dict(projected.labels).get("operation_id") != "tcad.execution-plan.project.v1":
        raise OperationInvocationError("input_execution_plan_projection_mismatch", port="experiment_plan")
    if skeleton.artifact_ref not in subject.parent_refs or skeleton.artifact_ref not in review.parent_refs:
        raise OperationInvocationError("input_project_skeleton_mismatch", port="scientific_skeleton")
    if review.producer_run_id is None or dict(review.labels).get("operation_version") != "3":
        raise OperationInvocationError("input_comprehensive_review_contract_required", port="review")


def runtime_inputs(sources: Mapping[str, bytes]) -> None:
    manifest = parse_bound_json(TCADRuntimeManifest, sources["runtime_manifest"], admission_port="runtime_manifest")
    parse_bound_json(ReviewedDeckPackage, sources["reviewed_package"], admission_port="reviewed_package")
    descriptors = sources.binding_descriptors
    outputs = [name for name, descriptor in descriptors.items() if descriptor.port_name == "runtime_outputs"]
    if len(outputs) != len(manifest.outputs):
        raise OperationInvocationError("input_runtime_collection_mismatch", port="runtime_outputs",
                                       message="Bind the complete output collection declared by the runtime manifest.")
    for name, record in zip(outputs, manifest.outputs, strict=True):
        if len(sources[name]) != record.size_bytes or hashlib.sha256(sources[name]).hexdigest() != record.sha256:
            raise OperationInvocationError("input_runtime_output_mismatch", port="runtime_outputs",
                                           message="Each runtime output must match its exact manifest record and order.")


RUNTIME_INPUT_VALIDATOR = CallableComponent("validator", runtime_inputs)


def attest_runtime(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    manifest_raw = _one(values, "runtime_manifest")
    manifest = TCADRuntimeManifest.model_validate_json(manifest_raw, strict=True)
    payloads = values.get("runtime_outputs", ())
    if len(payloads) != len(manifest.outputs):
        raise ValueError("runtime output collection differs from its exact manifest")
    inputs = {
        "reviewed_package": _one(values, "reviewed_package"),
        "runtime_manifest": manifest_raw,
        **{
            f"output__{record.name}": payload
            for record, payload in zip(manifest.outputs, payloads, strict=True)
        },
    }
    return attest_runtime_payload(inputs)


def materialize_realization(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    return materialize_realization_snapshot(
        {
            "comparison_contract": _one(values, "comparison_contract"),
            "reviewed_package": _one(values, "reviewed_package"),
            "case": _one(values, "case"),
        },
    )


def control_equivalence(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    packages = values.get("reviewed_packages", ())
    if not packages:
        raise ValueError("control equivalence requires at least one reviewed package")
    inputs = {"experiment_plan": _one(values, "experiment_plan")}
    for index, raw in enumerate(packages):
        name = "reviewed_package" if len(packages) == 1 else f"reviewed_package__{index:04d}"
        inputs[name] = raw
    return evaluate_control_equivalence_outputs(inputs)


def project_execution_context(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    snapshot = SolverCapabilitySnapshot.model_validate_json(
        _one(values, "capability"), strict=True
    )
    context = ExecutionContext(
        domain="tcad",
        implementation_backend=snapshot.launch_name,
        implementation_kind=snapshot.solver_kind,
        release_label=snapshot.public_release_label,
        public_arguments=snapshot.public_arguments,
        capability_statements=None,
        limitations=None,
    )
    return {"execution_context": (canonical_json(context),)}


def _has_parent(child: Any, parent: Any) -> bool:
    return parent.artifact.ref in child.artifact.parent_refs


def package_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    by_port = {item.port_name: item for item in inputs}
    review = by_port["review"]
    if not all(
        _has_parent(review, by_port[name])
        for name in ("project", "capability", "experiment_plan")
    ):
        return False
    return True


def runtime_parentage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    del parameters
    by_port: dict[str, list[Any]] = {}
    for item in inputs:
        by_port.setdefault(item.port_name, []).append(item)
    package = by_port["reviewed_package"][0]
    manifest = by_port["runtime_manifest"][0]
    if not _has_parent(manifest, package):
        return False
    execution_parents = manifest.artifact.parent_refs
    return all(
        item.artifact.parent_refs == execution_parents
        for item in by_port.get("runtime_outputs", ())
    )


COMPARE_COMPONENT = CallableComponent("transform", compare)
REVIEW_VALIDATION_COMPONENT = CallableComponent("transform", validate_review)
PACKAGE_COMPONENT = CallableComponent("transform", package)
RUNTIME_ATTEST_COMPONENT = CallableComponent("transform", attest_runtime)
REALIZATION_COMPONENT = CallableComponent("transform", materialize_realization)
CONTROL_EQUIVALENCE_COMPONENT = CallableComponent("transform", control_equivalence)
EXECUTION_CONTEXT_COMPONENT = CallableComponent("transform", project_execution_context)
PACKAGE_PARENTAGE_GUARD = CallableComponent("guard", package_parentage)
RUNTIME_PARENTAGE_GUARD = CallableComponent("guard", runtime_parentage)

PROJECT_DIFF_SCHEMA = _object_schema("tcad.deck-project-diff.v1")
REVIEW_ATTESTATION_SCHEMA = _object_schema("tcad.deck-review-attestation.v1")
REVIEWED_PACKAGE_SCHEMA = _schema(ReviewedDeckPackage, "tcad.reviewed-deck-package.v2")
COMPARISON_CONTRACT_SCHEMA = _schema(
    ComparisonContract, "scidiscovery.comparison-contract.v1"
)
CASE_BINDING_SCHEMA = _object_schema("tcad.realization-case-binding.v1")
REALIZATION_SCHEMA = _schema(RealizationSnapshot, "tcad.realization-snapshot.v1")
CONTROL_EQUIVALENCE_SCHEMA = _schema(
    StudyControlEquivalenceReport, "tcad.study-control-equivalence.v1"
)
CONTROL_AUDIT_SCHEMA = _object_schema("tcad.control-equivalence-audit.v1")
REVIEWED_PACKAGE_INPUT_SCHEMA = REVIEWED_PACKAGE_SCHEMA


def _ref(name: str, plugin_id: str | None = None) -> ComponentRef:
    return ComponentRef(name, plugin_id=plugin_id)


def _input(
    name: str,
    schema: str,
    resource: str | ComponentRef,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 32 * 1024 * 1024,
    usage: str = "claim_evidence",
    exposure: str = "full",
    media_types: tuple[str, ...] = ("application/json",),
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=f"Exact deterministic TCAD transform input: {name}.",
        schema=schema,
        media_types=media_types,
        codec=_ref(
            "json_codec" if media_types == ("application/json",) else "opaque_codec",
            "general_science",
        ),
        schema_resource=resource if isinstance(resource, ComponentRef) else _ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        usage=usage,
        exposure=exposure,
    )


def _output(
    name: str,
    kind: str,
    schema: str,
    resource: str,
    *,
    min_items: int = 1,
    max_items: int = 1,
    max_bytes: int = 32 * 1024 * 1024,
    collection_bytes: int | None = None,
    payload_schema_version: int = 1,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=f"Deterministic TCAD transform output: {name}.",
        schema=schema,
        media_types=("application/json",),
        codec=_ref("json_codec", "general_science"),
        schema_resource=_ref(resource),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_bytes,
        kind=kind,
        payload_schema_version=payload_schema_version,
        collection=(
            CollectionSpec(max_total_bytes=collection_bytes)
            if collection_bytes is not None
            else None
        ),
    )


def _operation(
    operation_id: str,
    component: str,
    purpose: str,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    *,
    guards: tuple[ComponentRef, ...] = (),
    input_validation: InputValidationSpec | None = None,
    max_input_bytes: int = 256 * 1024 * 1024,
    max_output_bytes: int = 64 * 1024 * 1024,
    max_files: int = 8,
) -> OperationSpec:
    return OperationSpec(
        operation_id=operation_id,
        version="1",
        catalog_scope="support",
        description=OperationDescription(
            purpose=purpose,
            applies_when="All declared immutable inputs are available.",
            not_for="Open-ended scientific judgment or external execution.",
        ),
        executor=ExecutorRef(kind="transform", component=_ref(component)),
        inputs=inputs,
        outputs=outputs,
        consequence="scientific",
        guards=guards,
        input_validation=input_validation,
        limits=LimitsSpec(
            timeout_seconds=300,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_files=max_files,
        ),
    )


EXECUTION_PLAN_COMPONENT = CallableComponent("transform", project_execution_plan)
PROJECTION_INPUTS_COMPONENT = CallableComponent("validator", projection_inputs)
PACKAGE_INPUTS_COMPONENT = CallableComponent("validator", package_inputs)

COMPONENT_SPECS = (
    ComponentSpec("execution_plan_project", "transform", "tcad_artifact.operation_transforms:EXECUTION_PLAN_COMPONENT", configuration_identity="tcad.execution-plan.project:v1"),
    ComponentSpec("execution_plan_inputs", "validator", "tcad_artifact.operation_transforms:PROJECTION_INPUTS_COMPONENT"),
    ComponentSpec("package_inputs", "validator", "tcad_artifact.operation_transforms:PACKAGE_INPUTS_COMPONENT"),
    ComponentSpec("runtime_inputs", "validator", "tcad_artifact.operation_transforms:RUNTIME_INPUT_VALIDATOR"),
    ComponentSpec("deck_compare", "transform", "tcad_artifact.operation_transforms:COMPARE_COMPONENT"),
    ComponentSpec("review_validate", "transform", "tcad_artifact.operation_transforms:REVIEW_VALIDATION_COMPONENT"),
    ComponentSpec("reviewed_package", "transform", "tcad_artifact.operation_transforms:PACKAGE_COMPONENT"),
    ComponentSpec("runtime_attest", "transform", "tcad_artifact.operation_transforms:RUNTIME_ATTEST_COMPONENT"),
    ComponentSpec("realization_materialize", "transform", "tcad_artifact.operation_transforms:REALIZATION_COMPONENT"),
    ComponentSpec("control_equivalence", "transform", "tcad_artifact.operation_transforms:CONTROL_EQUIVALENCE_COMPONENT"),
    ComponentSpec(
        "execution_context_project",
        "transform",
        "tcad_artifact.operation_transforms:EXECUTION_CONTEXT_COMPONENT",
        resources=(
            _ref("capability_schema"),
            _ref("execution_context_schema", "general_science"),
        ),
        configuration_identity="tcad.execution-context-project.v1",
    ),
    ComponentSpec("package_parentage", "guard", "tcad_artifact.operation_transforms:PACKAGE_PARENTAGE_GUARD"),
    ComponentSpec("runtime_parentage", "guard", "tcad_artifact.operation_transforms:RUNTIME_PARENTAGE_GUARD"),
    *tuple(
        ComponentSpec(name, "resource", f"tcad_artifact.operation_transforms:{attribute}")
        for name, attribute in (
            ("project_diff_schema", "PROJECT_DIFF_SCHEMA"),
            ("review_attestation_schema", "REVIEW_ATTESTATION_SCHEMA"),
            ("reviewed_package_schema", "REVIEWED_PACKAGE_SCHEMA"),
            ("comparison_contract_schema", "COMPARISON_CONTRACT_SCHEMA"),
            ("case_binding_schema", "CASE_BINDING_SCHEMA"),
            ("realization_schema", "REALIZATION_SCHEMA"),
            ("control_equivalence_schema", "CONTROL_EQUIVALENCE_SCHEMA"),
            ("control_audit_schema", "CONTROL_AUDIT_SCHEMA"),
        )
    ),
)


OPERATIONS = (
    _operation(
        "tcad.execution-plan.project.v1", "execution_plan_project",
        "Extract the sealed project's sole execution plan unchanged; grants no scientific or execution qualification.",
        (_input("project", "tcad.deck-project.v1", "project_schema", usage="evidence_inventory", max_bytes=DEVELOPMENT_ARTIFACT_LIMIT_BYTES),),
        (_output("experiment_plan", "experiment_portfolio", "scidiscovery.experiment-portfolio.v1", "project_schema", max_bytes=2 * 1024 * 1024).model_copy(update={"schema_resource": _ref("experiment_portfolio_schema", "general_science")}),),
        input_validation=InputValidationSpec(_ref("execution_plan_inputs"), "tcad.execution_plan.project.inputs", "Only a sealed project with a concrete embedded Portfolio; gaps and legacy projects cannot be projected."),
    ).model_copy(update={"catalog_scope": "public", "consequence": "explore"}),
    _operation(
        EXECUTION_CONTEXT_OPERATION,
        "execution_context_project",
        "Project one public TCAD capability snapshot into a domain-neutral execution context.",
        (
            _input(
                "capability",
                "tcad.solver-capability.v2",
                "capability_schema",
                max_bytes=64 * 1024,
                usage="prior_signal",
            ),
        ),
        (
            OutputPortSpec(
                name="execution_context",
                description="Domain-neutral execution context projected from one TCAD capability snapshot.",
                schema="scidiscovery.execution-context.v1",
                media_types=("application/json",),
                codec=_ref("json_codec", "general_science"),
                schema_resource=_ref("execution_context_schema", "general_science"),
                min_items=1,
                max_items=1,
                max_item_bytes=64 * 1024,
                kind="execution_context",
                payload_schema_version=1,
            ),
        ),
        max_input_bytes=64 * 1024,
        max_output_bytes=64 * 1024,
        max_files=1,
    ),
    _operation(
        DECK_COMPARE_OPERATION,
        "deck_compare",
        "Compare two exact TCAD project revisions deterministically.",
        (_input("base_project", "tcad.deck-project.v1", "project_schema", max_bytes=DEVELOPMENT_ARTIFACT_LIMIT_BYTES), _input("revised_project", "tcad.deck-project.v1", "project_schema", max_bytes=DEVELOPMENT_ARTIFACT_LIMIT_BYTES)),
        (_output("project_diff", "tcad_project_diff", "tcad.deck-project-diff.v1", "project_diff_schema"),),
    ),
    _operation(
        DECK_REVIEW_VALIDATION_OPERATION,
        "review_validate",
        "Validate one independent TCAD review against its exact project.",
        (_input("project", "tcad.deck-project.v1", "project_schema", max_bytes=DEVELOPMENT_ARTIFACT_LIMIT_BYTES), _input("review", "tcad.deck-review-report.v1", "review_schema", usage="prior_signal")),
        (_output("review_attestation", "tcad_deck_review_attestation", "tcad.deck-review-attestation.v1", "review_attestation_schema"),),
    ),
    _operation(
        REVIEWED_DECK_PACKAGE_OPERATION,
        "reviewed_package",
        "Package one qualified reviewed TCAD project for controlled execution.",
        (
            _input("project", "tcad.deck-project.v1", "project_schema", max_bytes=DEVELOPMENT_ARTIFACT_LIMIT_BYTES),
            _input("review", "tcad.deck-review-report.v1", "review_schema", usage="prior_signal"),
            _input("capability", "tcad.solver-capability.v2", "capability_schema", usage="prior_signal"),
            _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", "general_science"), usage="prior_signal"),
            _input("experiment_review", "scidiscovery.scientific-review.v1", _ref("scientific_review_schema", "general_science"), min_items=0, usage="prior_signal"),
            _input("scientific_skeleton", "scidiscovery.experiment-scientific-skeleton.v1", _ref("experiment_skeleton_schema", "general_science"), min_items=0, max_bytes=64 * 1024),
        ),
        (_output(
            "reviewed_package",
            "packaged_project",
            "tcad.reviewed-deck-package.v2",
            "reviewed_package_schema",
            max_bytes=64 * 1024 * 1024,
            payload_schema_version=2,
        ),),
        guards=(_ref("package_parentage"),),
        input_validation=InputValidationSpec(_ref("package_inputs"), "tcad.package.inputs", "Legacy plan review witness or exact project-derived plan and comprehensive independent review; skeleton, project, plan and review must share exact lineage."),
    ),
    _operation(
        RUNTIME_ATTESTATION_OPERATION,
        "runtime_attest",
        "Attest raw execution outputs against one exact reviewed TCAD package.",
        (
            _input("reviewed_package", "tcad.reviewed-deck-package.v2", "reviewed_package_schema", usage="prior_signal", max_bytes=64 * 1024 * 1024),
            _input(
                "runtime_manifest",
                "opaque",
                _ref("opaque_schema", "general_science"),
                usage="prior_signal",
                media_types=("application/json",),
            ),
            _input(
                "runtime_outputs",
                "opaque",
                _ref("opaque_schema", "general_science"),
                min_items=0,
                max_items=4096,
                max_bytes=256 * 1024 * 1024,
                usage="evidence_inventory",
                media_types=(
                    "application/octet-stream",
                    "application/x-synopsys-plx",
                    "application/json",
                    "text/plain",
                    "text/csv",
                    "image/png",
                ),
            ),
        ),
        (_output("runtime_attestation", "runtime_attestation", "tcad.runtime-attestation.v1", "runtime_attestation_schema"),),
        guards=(_ref("runtime_parentage"),),
        input_validation=InputValidationSpec(_ref("runtime_inputs"), "tcad.runtime.inputs",
            "The supplied runtime outputs must match the manifest collection, order, sizes and digests before attestation."),
        max_input_bytes=512 * 1024 * 1024,
    ),
    _operation(
        REALIZATION_SNAPSHOT_OPERATION,
        "realization_materialize",
        "Materialize one exact TCAD case realization from a reviewed package.",
        (
            _input("comparison_contract", "scidiscovery.comparison-contract.v1", "comparison_contract_schema"),
            _input("reviewed_package", "tcad.reviewed-deck-package.v2", "reviewed_package_schema", usage="prior_signal", max_bytes=64 * 1024 * 1024),
            _input("case", "tcad.realization-case-binding.v1", "case_binding_schema", usage="prior_signal"),
        ),
        (_output("realization_snapshot", "realization_snapshot", "tcad.realization-snapshot.v1", "realization_schema"),),
    ),
    _operation(
        CONTROL_EQUIVALENCE_OPERATION,
        "control_equivalence",
        "Evaluate study controls over one or more reviewed TCAD packages.",
        (
            _input("experiment_plan", "scidiscovery.experiment-portfolio.v1", _ref("experiment_portfolio_schema", "general_science")),
            _input("reviewed_packages", "tcad.reviewed-deck-package.v2", "reviewed_package_schema", min_items=1, max_items=4096, max_bytes=64 * 1024 * 1024, usage="prior_signal"),
        ),
        (
            _output("control_equivalence", "control_equivalence_report", "tcad.study-control-equivalence.v1", "control_equivalence_schema", max_bytes=16 * 1024 * 1024),
            _output("realization_snapshots", "realization_snapshot", "tcad.realization-snapshot.v1", "realization_schema", min_items=0, max_items=4096, max_bytes=1024 * 1024, collection_bytes=256 * 1024 * 1024),
            _output("control_audit", "control_equivalence_audit", "tcad.control-equivalence-audit.v1", "control_audit_schema", max_bytes=4 * 1024 * 1024),
        ),
        max_input_bytes=512 * 1024 * 1024,
        max_output_bytes=276 * 1024 * 1024,
        max_files=4098,
    ),
)


__all__ = [
    "COMPONENT_SPECS",
    "EXECUTION_CONTEXT_OPERATION",
    "OPERATIONS",
]
