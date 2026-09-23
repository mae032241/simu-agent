"""Single-output figure Agents owned by the optional figure plugin."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.cognitive import EvidenceAudit
from scidiscovery.operation_contract import contract_diagnostic, SemanticRuleViolation
from scidiscovery.operation_declaration import (
    OPERATION_AGENT_PREAMBLE,
    payload_validator,
    schema_resource,
    scientific_agent_operation,
    scientific_semantic_contract,
)
from scidiscovery.operations.spec import (
    CallableComponent,
    ComponentRef,
    ComponentSpec,
    CompleteTransformFamilySpec,
    InputAdmissionSpec,
    InputPortSpec,
    OutputPortSpec,
    ReviewSpec,
)

from .figure_digitization_contract import (
    FigureDigitizationRequest,
    materialize_figure_request,
)


GENERAL = "general_science"
BUILTIN = "builtin"


def _general(name: str) -> ComponentRef:
    return ComponentRef(name, plugin_id=GENERAL)


BASE_TOOLS = tuple(
    ComponentRef(name, plugin_id=BUILTIN)
    for name in (
        "file_write_begin_tool",
        "file_write_chunk_tool",
        "file_write_commit_tool",
    )
) + (ComponentRef("file_apply_patch_tool", plugin_id=BUILTIN),)
PDF_TOOL = _general("pdf_extract_tool")


REQUEST_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the FigureDigitizationRequest required by
the schema identified by assignment.output.schema_path. Inspect the bound paper_source and optional research_objective.
If the research objective or assignment instruction identifies an exact figure,
that target is fixed: do not substitute another figure. For PDFs first call
worker_extract_pdf_text to locate the target's PDF page from original text and
captions. Then call worker_curve_figure_inspect_source with the bound source name
and that source_page, then view every returned original image. For a raster source
use source_page null. The inspection tool does not run OCR or identify plots.

Describe only what you can judge from the original figure: selected image identity,
figure and panel, plot box, linear or log10 axes, visible pixel/value calibration
pairs, units, series labels and identities, colors and line styles, legend or
annotation boxes, a small number of guide points on each curve, and explicit
non-data exclusion boxes. For each axis, put exactly two visible
[pixel_coordinate, tick_value] pairs in ticks; their order has no meaning and
the program normalizes them. They do not describe the extracted curve's range.
Omit color tolerances, pixel ranges, eligibility ranges, declared gaps,
shared_support, tracking thresholds, point counts, coverage and result statistics.

The program fills recovered image hashes, dimensions, recovery versions and PDF object
metadata from the bound source. Choose page and document_image_index for a PDF;
these mechanical metadata fields may be omitted from the draft.

Before submitting a ready request, call worker_curve_figure_preview with the complete
draft. View both returned images: the source-pixel overlay and the plot redrawn only
from calibrated CSV values. If either image follows the wrong pixels, crosses a real
gap, uses the wrong calibration or has the wrong series identity, correct the visible
description or guide points and preview again. Submit only the exact request whose
preview you inspected. The deterministic program creates curve points, statistics,
CSV and shared-pixel markings; never hand-write them.

If the page, image, calibration or series identity cannot be established visibly,
submit request_status unresolved with bounded unresolved_reasons. Preserve the
original source identity and any known partial fields; omit unknown recovery metadata. Do not produce scientific claims, qualification or approval.
"""


INTAKE_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the ScientificIntake required by
the schema identified by assignment.output.schema_path. Consume the exact paper_source, typed figure_request,
manifest, deterministic validation report, source panel, audit overlay, and
curve tables as one immutable family. State only what the supplied family
supports, preserve every unresolved identity, occlusion, gap, and qualification
limit, and distinguish digitized observations from author-supplied raw data.
The declared family may contain zero tables, or zero recovered images and tables.
These are complete unresolved results; preserve their limits in a full Intake.
Workspace finalizers copy objective text from objective_contract.statement, or the
foundation objective when absent; the draft may omit problem_frame.objective.

Use exact assignment source names in evidence keys. Do not create or modify
curve points, reinterpret a failed deterministic report, grant qualification,
or select a scientific hypothesis.

When prior_draft and change_request are present, this is a complete-object
copy-on-write revision. Read the prefilled output/result.json and the exact
independent review before editing. Change only content required by that review,
preserve every unchallenged source, identity, uncertainty, limitation and
global objective, and submit one complete new ScientificIntake. Do not inherit
the prior verdict or qualification and do not turn a wording correction into
new evidence or redigitization.
"""


AUDIT_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the EvidenceAudit required by
the schema identified by assignment.output.schema_path. Independently audit the exact ScientificIntake against its
bound paper source, typed request, manifest, deterministic validation report,
source panel, overlays, and every curve table. Check source/object identity,
axis calibration, legend or annotation binding, visible support, gaps,
occlusion, per-series status, and whether the Intake overstates digitized data.

Use exact assignment source names in evidence keys. Do not redigitize, mutate
the Intake or attachments, grant qualification, or hide an unresolved series
to make the bundle pass. Judge whether the Intake is faithful to the exact
figure family, not whether that family is sufficient for a broader scientific
objective. Use pass when a statement is supported or faithfully preserves a
limitation, local gap, detection limit, shared dependency, or unresolved
identity. Use fail when the Intake treats an ineligible point as eligible,
hides a source limitation, binds identity incorrectly, or makes an unsupported
affirmative claim. Use unknown only when required material is missing,
unreadable, or cannot be compared, and not_applicable only when the check does
not apply. A faithful statement of limited evidence can pass this audit without
granting quantitative qualification.
Explicitly declared zero-table or zero-image families can be faithfully audited;
absence of an attachment declared by the manifest is a different integrity defect.
The workspace finalizer derives only handoff.verdict. Author the handoff summary
and needed next actions; do not omit the entire handoff.
"""


FIGURE_REQUEST_SCHEMA = schema_resource(
    FigureDigitizationRequest,
    "scidiscovery.curve-figure-digitization-request.v2",
)
FIGURE_REQUEST_SEMANTIC_CONTRACT = scientific_semantic_contract(
    "curve.figure.request",
    "The Agent visibly identifies and calibrates one exact figure; deterministic code extracts every curve point.",
    "The source hash must equal the frozen paper_source bytes.",
    "A ready request must be previewed with the same deterministic digitizer before submission.",
    "Point counts, curve ranges, gaps, CSV values and shared pixels are program outputs, not Agent declarations.",
    payload_rule_id="curve.figure.request.internal_consistency",
    context_rule_id="curve.figure.request.source_binding",
)


def _validate_request(value: dict[str, object]) -> None:
    FigureDigitizationRequest.model_validate_json(canonical_json(value), strict=True)


def _validate_request_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    paper_source = sources["paper_source"]
    try:
        request = FigureDigitizationRequest.model_validate_json(
            canonical_json(payload), strict=True
        )
        if hashlib.sha256(paper_source).hexdigest() != request.source.source_sha256:
            raise ValueError("figure source hash differs from the typed request")
        if request.request_status == "ready":
            request.require_ready()
    except (ValidationError, ValueError) as error:
        raise SemanticRuleViolation(str(error)) from error


def _finalize_request(request):
    from scidiscovery.artifact_agent.service.result_materialization import finalize_result
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    def project(value):
        try:
            value["payload"] = materialize_figure_request(value["payload"], request.input_paths["paper_source"].read_bytes())
        except ValueError as error:
            raise WorkspaceProtocolError("figure request cannot resolve its selected image", details=(
                contract_diagnostic("output_invalid", phase="output_payload", affected_action="submit",
                    path="$.payload.source", repairable=True,
                    message="Select an available image from the bound source, or record an unresolved request."),)) from error
    return finalize_result(request, project)


FIGURE_REQUEST_FINALIZER = CallableComponent("workspace_finalizer", _finalize_request)


FIGURE_REQUEST_VALIDATOR = CallableComponent(
    "validator", payload_validator(_validate_request)
)
FIGURE_REQUEST_CONTEXT = CallableComponent("validator", _validate_request_context)


FIGURE_FAMILY_INPUT_PORTS = ("paper_source", "figure_request")
FIGURE_FAMILY_OUTPUT_PORTS = (
    "figure_manifest",
    "validation_report",
    "source_panels",
    "audit_overlays",
    "curve_tables",
)
FIGURE_FAMILY_PORTS = (*FIGURE_FAMILY_INPUT_PORTS, *FIGURE_FAMILY_OUTPUT_PORTS)


def figure_revision_parentage(
    inputs: tuple[Any, ...], parameters: Mapping[str, Any]
) -> bool:
    """Bind one revision to the exact family used by its base and review."""

    if parameters:
        return False
    grouped: dict[str, list[Any]] = {}
    for item in inputs:
        grouped.setdefault(item.port_name, []).append(item)
    prior_items = grouped.get("prior_draft", ())
    review_items = grouped.get("change_request", ())
    if not prior_items and not review_items:
        return True
    if (
        len(prior_items) != 1
        or len(review_items) != 1
        or any(len(grouped.get(name, ())) != 1 for name in
               ("paper_source", "figure_request", "figure_manifest", "validation_report"))
    ):
        return False
    prior = prior_items[0].artifact
    review = review_items[0].artifact
    family_refs = {
        item.artifact.ref
        for name in FIGURE_FAMILY_PORTS
        for item in grouped.get(name, ())
    }
    return bool(
        family_refs <= set(prior.parent_refs)
        and {prior.ref, *family_refs} <= set(review.parent_refs)
    )


def figure_audit_progress_fingerprint(raw: bytes) -> str:
    """Fingerprint unresolved audit dimensions without reviewer prose."""

    audit = EvidenceAudit.model_validate_json(raw, strict=True)
    unresolved = tuple(
        sorted(
            (
                item.check_key,
                item.status,
                tuple(sorted(item.evidence_keys)),
                tuple(sorted(item.hypothesis_keys)),
            )
            for item in audit.checks
            if item.status != "pass"
        )
    )
    return hashlib.sha256(canonical_json({"unresolved": unresolved})).hexdigest()


FIGURE_REVISION_PARENTAGE = CallableComponent("guard", figure_revision_parentage)
FIGURE_AUDIT_PROGRESS_FINGERPRINT = CallableComponent(
    "transform", figure_audit_progress_fingerprint
)


COMPONENT_SPECS = (
    ComponentSpec("figure_request_finalizer", "workspace_finalizer", "curve_figure_evidence.figure_science_operations:FIGURE_REQUEST_FINALIZER"),
    ComponentSpec("figure_request_workspace", "workspace", "scidiscovery.general_science_components:WORKSPACE",
                  resources=(ComponentRef("figure_request_finalizer"),)),
    ComponentSpec(
        "figure_source_inspection_tool",
        "worker_tool",
        "curve_figure_evidence.figure_worker_tool:FIGURE_SOURCE_INSPECTION_TOOL",
        configuration_identity="figure.inspection-summary:v1",
    ),
    ComponentSpec(
        "figure_digitization_preview_tool",
        "worker_tool",
        "curve_figure_evidence.figure_worker_tool:FIGURE_DIGITIZATION_PREVIEW_TOOL",
        configuration_identity="figure.preview-summary:v1",
    ),
    ComponentSpec(
        "figure_request_schema",
        "resource",
        "curve_figure_evidence.figure_science_operations:FIGURE_REQUEST_SCHEMA",
        public=True,
    ),
    ComponentSpec(
        "figure_request_semantic_contract",
        "resource",
        "curve_figure_evidence.figure_science_operations:FIGURE_REQUEST_SEMANTIC_CONTRACT",
    ),
    ComponentSpec(
        "figure_request_validator",
        "validator",
        "curve_figure_evidence.figure_science_operations:FIGURE_REQUEST_VALIDATOR",
        resources=(ComponentRef("figure_request_semantic_contract"),),
    ),
    ComponentSpec(
        "figure_request_context",
        "validator",
        "curve_figure_evidence.figure_science_operations:FIGURE_REQUEST_CONTEXT",
        configuration_identity="input-boundary-r4:v1",
        resources=(ComponentRef("figure_request_semantic_contract"),),
    ),
    ComponentSpec(
        "figure_revision_parentage",
        "guard",
        "curve_figure_evidence.figure_science_operations:FIGURE_REVISION_PARENTAGE",
    ),
    ComponentSpec(
        "figure_audit_progress_fingerprint",
        "transform",
        "curve_figure_evidence.figure_science_operations:FIGURE_AUDIT_PROGRESS_FINGERPRINT",
    ),
    ComponentSpec(
        "figure_request_prompt",
        "resource",
        "curve_figure_evidence.figure_science_operations:REQUEST_PROMPT",
    ),
    ComponentSpec(
        "figure_intake_prompt",
        "resource",
        "curve_figure_evidence.figure_science_operations:INTAKE_PROMPT",
    ),
    ComponentSpec(
        "figure_audit_prompt",
        "resource",
        "curve_figure_evidence.figure_science_operations:AUDIT_PROMPT",
    ),
)


def _schema_ref(schema: str) -> ComponentRef:
    local = {
        "scidiscovery.curve-figure-digitization-request.v2": "figure_request_schema",
        "scidiscovery.figure-evidence-manifest.v1": "figure_manifest_schema",
        "scidiscovery.figure-evidence-validation-report.v1": "figure_report_schema",
    }
    if schema in local:
        return ComponentRef(local[schema])
    return _general(
        {
            "opaque": "opaque_schema",
            "scidiscovery.scientific-intake.v1": "scientific_intake_schema",
            "scidiscovery.evidence-audit.v1": "evidence_audit_schema",
            "scidiscovery.research-objective.v1": "research_objective_schema",
        }[schema]
    )


def _input(
    name: str,
    description: str,
    schema: str,
    *,
    media_types: tuple[str, ...] = ("application/json",),
    min_items: int = 1,
    max_items: int = 1,
    max_item_bytes: int = 1024 * 1024,
    exposure: str = "full",
    usage: str = "claim_evidence",
) -> InputPortSpec:
    return InputPortSpec(
        name=name,
        description=description,
        schema=schema,
        media_types=media_types,
        codec=_general("opaque_codec" if schema == "opaque" else "json_codec"),
        schema_resource=_schema_ref(schema),
        min_items=min_items,
        max_items=max_items,
        max_item_bytes=max_item_bytes,
        exposure=exposure,
        usage=usage,
    )


PAPER_SOURCE_INPUT = _input(
    "paper_source",
    "Exact frozen paper PDF or supplied raster source.",
    "opaque",
    media_types=("application/pdf", "image/png", "image/jpeg", "image/webp"),
    max_item_bytes=32 * 1024 * 1024,
    usage="evidence_inventory",
)
REQUEST_INPUT = _input(
    "figure_request",
    "Typed source selection, calibration, and visible series anchors.",
    "scidiscovery.curve-figure-digitization-request.v2",
    usage="evidence_inventory",
)
MANIFEST_INPUT = _input(
    "figure_manifest",
    "Exact deterministic figure-evidence manifest.",
    "scidiscovery.figure-evidence-manifest.v1",
    usage="evidence_inventory",
)
REPORT_INPUT = _input(
    "validation_report",
    "Exact deterministic figure-evidence validation report.",
    "scidiscovery.figure-evidence-validation-report.v1",
    usage="evidence_inventory",
)
SOURCE_PANELS_INPUT = _input(
    "source_panels",
    "Canonical source-panel images recovered by the materializer.",
    "opaque",
    media_types=("image/png",),
    min_items=0,
    max_items=1,
    max_item_bytes=16 * 1024 * 1024,
    exposure="on_demand",
    usage="evidence_inventory",
)
AUDIT_OVERLAYS_INPUT = _input(
    "audit_overlays",
    "Pixel-level deterministic audit overlays.",
    "opaque",
    media_types=("image/png",),
    min_items=0,
    max_items=2,
    max_item_bytes=16 * 1024 * 1024,
    exposure="on_demand",
    usage="evidence_inventory",
)
CURVE_TABLES_INPUT = _input(
    "curve_tables",
    "Traceable per-series curve tables.",
    "opaque",
    media_types=("text/csv",),
    min_items=0,
    max_items=32,
    max_item_bytes=8 * 1024 * 1024,
    exposure="on_demand",
    usage="evidence_inventory",
)
FIGURE_FAMILY_INPUTS = (
    PAPER_SOURCE_INPUT,
    REQUEST_INPUT,
    MANIFEST_INPUT,
    REPORT_INPUT,
    SOURCE_PANELS_INPUT,
    AUDIT_OVERLAYS_INPUT,
    CURVE_TABLES_INPUT,
)
FIGURE_FAMILY_REQUIREMENT = CompleteTransformFamilySpec(
    output_ports=FIGURE_FAMILY_OUTPUT_PORTS,
    input_ports=FIGURE_FAMILY_INPUT_PORTS,
)


REQUEST_OUTPUT = OutputPortSpec(
    name="figure_request",
    description="Source-bound visible calibration and series guidance for deterministic extraction.",
    kind="figure_digitization_request",
    schema="scidiscovery.curve-figure-digitization-request.v2",
    media_types=("application/json",),
    codec=_general("json_codec"),
    schema_resource=ComponentRef("figure_request_schema"),
    max_item_bytes=1024 * 1024,
    validator=ComponentRef("figure_request_validator"),
    validator_rule_id="curve.figure.request.internal_consistency",
    semantic_contract=ComponentRef("figure_request_semantic_contract"),
    context_validator=ComponentRef("figure_request_context"),
    context_rule_id="curve.figure.request.source_binding",
    context_sources=("paper_source",),
)


def _scientific_output(
    *,
    name: str,
    description: str,
    kind: str,
    schema: str,
    validator: str,
    contract: str,
    payload_rule: str,
    context_validator: str,
    context_rule: str,
    context_sources: tuple[str, ...],
    max_item_bytes: int,
) -> OutputPortSpec:
    return OutputPortSpec(
        name=name,
        description=description,
        kind=kind,
        schema=schema,
        media_types=("application/json",),
        codec=_general("json_codec"),
        schema_resource=_schema_ref(schema),
        max_item_bytes=max_item_bytes,
        validator=_general(validator),
        validator_rule_id=payload_rule,
        semantic_contract=_general(contract),
        context_validator=_general(context_validator),
        context_rule_id=context_rule,
        context_sources=context_sources,
        evidence_paths=("/scientific_foundation/evidence",)
        if schema == "scidiscovery.scientific-intake.v1"
        else ("/evidence",),
    )


INTAKE_OUTPUT = _scientific_output(
    name="scientific_intake",
    description="One source-bound scientific intake for the exact figure family.",
    kind="scientific_intake",
    schema="scidiscovery.scientific-intake.v1",
    validator="intake_validator",
    contract="intake_semantic_contract",
    payload_rule="intake.internal_closure",
    context_validator="intake_source_context",
    context_rule="intake.source_binding",
    context_sources=tuple(port.name for port in FIGURE_FAMILY_INPUTS),
    max_item_bytes=64 * 1024,
)

AUDIT_INPUTS = (
    _input(
        "scientific_intake",
        "Provisional Intake produced from the exact figure family.",
        "scidiscovery.scientific-intake.v1",
        usage="prior_signal",
    ),
    *FIGURE_FAMILY_INPUTS,
)
REVISION_CONTEXT_INPUTS = (
    _input(
        "prior_draft",
        "Exact immutable figure ScientificIntake to revise.",
        "scidiscovery.scientific-intake.v1",
        min_items=0,
        usage="revision_base",
    ),
    _input(
        "change_request",
        "Exact non-passing independent figure audit requesting correction.",
        "scidiscovery.evidence-audit.v1",
        min_items=0,
        usage="change_request",
    ),
)
FIGURE_REVISION_ADMISSION = InputAdmissionSpec(
    cohort_id="figure_intake_revision",
    member_ports=("prior_draft", "change_request"),
)
AUDIT_OUTPUT = _scientific_output(
    name="evidence_audit",
    description="Independent audit of one Intake and its complete figure family.",
    kind="evidence_audit",
    schema="scidiscovery.evidence-audit.v1",
    validator="audit_validator",
    contract="evidence_audit_semantic_contract",
    payload_rule="evidence.audit.check_consistency",
    context_validator="evidence_audit_context",
    context_rule="evidence.audit.source_binding",
    context_sources=tuple(port.name for port in AUDIT_INPUTS),
    max_item_bytes=32 * 1024,
)


def _agent(
    operation_id: str,
    purpose: str,
    applies_when: str,
    not_for: str,
    *,
    prompt: ComponentRef,
    inputs: tuple[InputPortSpec, ...],
    outputs: tuple[OutputPortSpec, ...],
    tools: tuple[ComponentRef, ...],
    timeout: int,
    max_input_bytes: int,
    review: ReviewSpec | None = None,
    input_admission: InputAdmissionSpec | None = None,
    complete_transform_family: CompleteTransformFamilySpec | None = None,
    guards: tuple[ComponentRef, ...] = (),
    workspace: ComponentRef | None = None,
) -> Any:
    return scientific_agent_operation(
        operation_id,
        purpose,
        applies_when,
        not_for,
        agent=_general("evidence_agent")
        if operation_id != "science.figure.evidence.audit.v1"
        else _general("auditor_agent"),
        workspace=workspace or _general("workspace"),
        prompt=prompt,
        tools=tools,
        inputs=inputs,
        outputs=outputs,
        timeout=timeout,
        max_input_bytes=max_input_bytes,
        max_output_bytes=sum(port.max_item_bytes for port in outputs),
        max_files=1,
        native_view_image=True,
        review=review,
        input_admission=input_admission,
        complete_transform_family=complete_transform_family,
        guards=guards,
    )


OPERATIONS = (
    _agent(
        "science.figure.request.prepare.v1",
        "Select and describe one exact, visibly anchored quantitative paper figure.",
        "A frozen PDF or raster may contain a quantitative figure needed as evidence.",
        "Producing curve points, qualifying evidence, or inferring an ambiguous identity.",
        prompt=ComponentRef("figure_request_prompt"),
        workspace=ComponentRef("figure_request_workspace"),
        inputs=(PAPER_SOURCE_INPUT, _input("research_objective", "Explicit scientific objective for semantic selection.",
            "scidiscovery.research-objective.v1", min_items=0, usage="prior_signal")),
        outputs=(REQUEST_OUTPUT,),
        tools=BASE_TOOLS + (
            PDF_TOOL,
            ComponentRef("figure_source_inspection_tool"),
            ComponentRef("figure_digitization_preview_tool"),
        ),
        timeout=900,
        max_input_bytes=33 * 1024 * 1024,
    ),
    _agent(
        "science.evidence.extract.figure.v2",
        "Create or revise one ScientificIntake from a complete deterministic figure family.",
        "A complete figure family is available, optionally with its exact Intake and non-passing audit.",
        "Digitizing pixels, changing the source family, producing a patch, or qualifying the Intake.",
        prompt=ComponentRef("figure_intake_prompt"),
        inputs=(*FIGURE_FAMILY_INPUTS, *REVISION_CONTEXT_INPUTS),
        outputs=(INTAKE_OUTPUT,),
        tools=BASE_TOOLS + (PDF_TOOL,),
        timeout=600,
        max_input_bytes=325 * 1024 * 1024,
        input_admission=FIGURE_REVISION_ADMISSION,
        complete_transform_family=FIGURE_FAMILY_REQUIREMENT,
        guards=(ComponentRef("figure_revision_parentage"),),
        review=ReviewSpec(
            reviewer_operation="science.figure.evidence.audit.v1",
            reviewer_input_port="scientific_intake",
            subject_outputs=("scientific_intake",),
            max_revisions=2,
            progress_fingerprint=ComponentRef(
                "figure_audit_progress_fingerprint"
            ),
        ),
    ),
    _agent(
        "science.figure.evidence.audit.v1",
        "Independently audit one Intake against its complete figure family.",
        "A provisional figure Intake and every exact sibling attachment exist.",
        "Digitizing, revising, or qualifying the figure evidence.",
        prompt=ComponentRef("figure_audit_prompt"),
        inputs=AUDIT_INPUTS,
        outputs=(AUDIT_OUTPUT,),
        tools=BASE_TOOLS + (PDF_TOOL,),
        timeout=600,
        max_input_bytes=325 * 1024 * 1024,
        complete_transform_family=FIGURE_FAMILY_REQUIREMENT,
    ),
)


__all__ = ["COMPONENT_SPECS", "FIGURE_REQUEST_SCHEMA", "OPERATIONS"]


FIGURE_SEMANTIC_CONTRACT = scientific_semantic_contract(
    "curve.figure",
    "Curve-analysis images are deterministic supporting outputs, not evidence by themselves.",
    "Figure manifests, attachments, media types, hashes, and deterministic reports must bind exactly.",
    "Series identity, calibration, and missing visual support must never be inferred silently.",
    payload_rule_id="curve.figure.manifest_consistency",
    context_rule_id="curve.figure.evidence_binding",
)
