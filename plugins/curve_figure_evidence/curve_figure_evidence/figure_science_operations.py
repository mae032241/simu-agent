"""One complete figure author, followed by independent scientific audit."""
from __future__ import annotations

import hashlib
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.cognitive import EvidenceAudit
from scidiscovery.operation_declaration import (OPERATION_AGENT_PREAMBLE, schema_resource,
    scientific_agent_operation, scientific_semantic_contract)
from scidiscovery.operations.spec import (CallableComponent, CollectionSpec, ComponentRef,
    ComponentSpec, InputDerivationSpec, InputPortSpec, InputValidationSpec, OutputPortSpec, ReviewSpec)
from .figure_digitization_contract import ScientificFigureRequest

AUTHOR_OPERATION = "science.evidence.extract.figure.v3"
AUDIT_OPERATION = "science.figure.evidence.audit.v2"
BUNDLE_OPERATION = "scidiscovery.curve-bundle.figure-evidence.v3"

def _general(name):
    return ComponentRef(name, plugin_id="general_science")

BASE_TOOLS = tuple(ComponentRef(name, plugin_id="builtin") for name in (
    "file_write_begin_tool", "file_write_chunk_tool", "file_write_commit_tool", "file_apply_patch_tool"))
PDF_TOOL = _general("pdf_extract_tool")

AUTHOR_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the ScientificIntake required by
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

Before saving a ready request, call worker_curve_figure_preview with the complete
draft. View both returned images: the source-pixel overlay and the plot redrawn only
from calibrated CSV values. If either image follows the wrong pixels, crosses a real
gap, uses the wrong calibration or has the wrong series identity, correct the visible
description or guide points and preview again. Call worker_curve_figure_save with only the exact request whose
preview you inspected. This explicitly selects and seals the complete family. The deterministic program creates curve points, statistics,
CSV and shared-pixel markings; never hand-write them.

If the page, image, calibration or series identity cannot be established visibly,
save request_status unresolved with bounded unresolved_reasons. Preserve the
original source identity and any known partial fields; omit unknown recovery metadata. Do not grant qualification or approval.
After saving, inspect the returned local files and compose the ScientificIntake in
this same task. Use the returned exact tool evidence aliases in evidence keys.
Preserve unresolved identity, occlusion, gap and quantitative limits. Distinguish
digitized observations from author-supplied raw data. Save selects one family;
preview as often as needed before selection. Another selection requires a new Run.
When prior_draft is bound, inspect its original scientific figure materials and any feedback. For wording or limitations-only corrections, call
worker_curve_figure_reuse with the bound source name; its original materials are restored by the service. This preserves original request/file identities and original evidence
aliases without redigitization. Preserve unchallenged content and submit a complete
new Intake; any formal audit applies to this new Intake. Never inherit the prior verdict.
If that review requires new extraction, explicitly preview and save a new family
instead of calling reuse. Do not mix a reused family with a new selection. The workspace finalizer copies the objective from the foundation.
"""


AUDIT_PROMPT = OPERATION_AGENT_PREAMBLE + """Return exactly one
RoleResultEnvelope whose payload is the EvidenceAudit required by
the schema identified by assignment.output.schema_path. Independently audit the exact ScientificIntake against its
bound paper source and all original scientific figure materials.
The selected material list identifies the scientific request, deterministic report, source panel, overlays and tables. Inspect every selected member using
its current assignment alias (the provenance records retain original aliases). Check source/object identity,
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


FIGURE_REQUEST_SCHEMA = schema_resource(ScientificFigureRequest, "scidiscovery.curve-figure-digitization-request.v2")
FIGURE_SEMANTIC_CONTRACT = scientific_semantic_contract(
    "curve.figure", "One author delivers source-bound Intake and an explicitly selected immutable figure family.",
    "Selected request, algorithm identity, file hashes and original source must match controlled tool evidence.",
    "Only independent audit can review the author; a revision never inherits a verdict.",
    payload_rule_id="intake.internal_closure", context_rule_id="curve.figure.evidence_binding")

COMPONENT_SPECS = (
    ComponentSpec("figure_source_inspection_tool", "worker_tool", "curve_figure_evidence.figure_worker_tool:FIGURE_SOURCE_INSPECTION_TOOL"),
    ComponentSpec("figure_digitization_preview_tool", "worker_tool", "curve_figure_evidence.figure_worker_tool:FIGURE_DIGITIZATION_PREVIEW_TOOL"),
    ComponentSpec("figure_save_tool", "worker_tool", "curve_figure_evidence.figure_worker_tool:FIGURE_SAVE_TOOL"),
    ComponentSpec("figure_reuse_tool", "worker_tool", "curve_figure_evidence.figure_worker_tool:FIGURE_REUSE_TOOL"),
    ComponentSpec("figure_revision_inputs", "validator", "curve_figure_evidence.figure_family:FIGURE_REVISION_INPUT_VALIDATOR"),
    ComponentSpec("figure_request_schema", "resource", "curve_figure_evidence.figure_science_operations:FIGURE_REQUEST_SCHEMA", public=True),
    ComponentSpec("figure_intake_validator", "validator", "scidiscovery.general_science_components:Components.intake_validator", resources=(ComponentRef("figure_semantic_contract"),)),
    ComponentSpec("figure_intake_context", "validator", "curve_figure_evidence.figure_family:FIGURE_INTAKE_CONTEXT", resources=(ComponentRef("figure_semantic_contract"),)),
    ComponentSpec("figure_family_inputs", "validator", "curve_figure_evidence.figure_family:FIGURE_FAMILY_INPUT_VALIDATOR"),
    ComponentSpec("figure_audit_parentage", "guard", "curve_figure_evidence.figure_family:FIGURE_AUDIT_PARENTAGE"),
    ComponentSpec("figure_author_prompt", "resource", "curve_figure_evidence.figure_science_operations:AUTHOR_PROMPT"),
    ComponentSpec("figure_audit_prompt", "resource", "curve_figure_evidence.figure_science_operations:AUDIT_PROMPT"),
)

def _input(name, description, schema="opaque", *, resource="opaque_schema", media_types=("application/json",),
           min_items=1, max_items=1, max_item_bytes=1024*1024, usage="evidence_inventory", exposure="full"):
    return InputPortSpec(name=name, description=description, schema=schema, media_types=media_types,
        codec=_general("opaque_codec" if schema == "opaque" else "json_codec"), schema_resource=_general(resource),
        min_items=min_items, max_items=max_items, max_item_bytes=max_item_bytes, usage=usage, exposure=exposure)

PAPER_SOURCE_INPUT = _input("paper_source", "Exact original PDF or raster source.",
    media_types=("application/pdf", "image/png", "image/jpeg", "image/webp"), max_item_bytes=32*1024*1024)
FIGURE_FAMILY_INPUTS = (
    PAPER_SOURCE_INPUT,
    _input("figure_provenance", "Exact control manifest parent of the selected Intake; includes all saved family identities.",
        "scidiscovery.tool-evidence-manifest.v1", resource="tool_evidence_schema"),
    _input("figure_family", "Original saved scientific request, figures, tables and uncertainty report.",
        media_types=("application/json", "image/png", "text/csv"), min_items=2, max_items=40,
        max_item_bytes=32*1024*1024, exposure="on_demand"),
)
FAMILY_VALIDATION = InputValidationSpec(ComponentRef("figure_family_inputs"), "curve.figure.selected_family",
    "Bind the complete selected family from the Intake control manifest, rejecting missing, extra, altered or cross-Run members.")

INTAKE_OUTPUT = OutputPortSpec(name="scientific_intake", description="ScientificIntake bound to one explicitly selected saved figure family.",
    kind="scientific_intake", schema="scidiscovery.scientific-intake.v1", media_types=("application/json",),
    codec=_general("json_codec"), schema_resource=_general("scientific_intake_schema"), max_item_bytes=64*1024,
    validator=ComponentRef("figure_intake_validator"), validator_rule_id="intake.internal_closure",
    semantic_contract=ComponentRef("figure_semantic_contract"),
    context_validator=ComponentRef("figure_intake_context"), context_rule_id="curve.figure.evidence_binding",
    context_sources=("paper_source", "tool_evidence", "figure_provenance", "figure_family"), evidence_paths=("/scientific_foundation/evidence",))
# Ancillary records are registered only through the controlled save tool, never Worker file writes.
FAMILY_OUTPUT = OutputPortSpec(name="tool_evidence", description="Selected figure request, deterministic files and selection manifest.",
    kind="figure_evidence_file", schema="opaque", media_types=("application/json", "image/png", "text/csv"),
    codec=_general("opaque_codec"), schema_resource=_general("opaque_schema"), min_items=0, max_items=40,
    max_item_bytes=32*1024*1024, collection=CollectionSpec(max_total_bytes=320*1024*1024))
AUDIT_INPUTS = (_input("scientific_intake", "Exact provisional Intake to review.", "scidiscovery.scientific-intake.v1",
    resource="scientific_intake_schema", usage="prior_signal", max_item_bytes=64*1024), *(port.model_copy(update={
        "derivation": InputDerivationSpec(anchor_port="scientific_intake", **(
            {"producer_input_path": ("paper_source",)} if port.name == "paper_source" else
            {"producer_output_port": "recovery_manifest_output" if port.name == "figure_provenance" else "tool_evidence"})),
        "agent_visible": port.name != "figure_provenance"}) for port in FIGURE_FAMILY_INPUTS))
AUDIT_OUTPUT = OutputPortSpec(name="evidence_audit", description="Independent review of Intake against its selected complete family.",
    kind="evidence_audit", schema="scidiscovery.evidence-audit.v1", media_types=("application/json",),
    codec=_general("json_codec"), schema_resource=_general("evidence_audit_schema"), max_item_bytes=32*1024,
    validator=_general("audit_validator"), validator_rule_id="evidence.audit.check_consistency",
    semantic_contract=_general("evidence_audit_semantic_contract"), context_validator=_general("evidence_audit_context"),
    context_rule_id="evidence.audit.source_binding", context_sources=tuple(p.name for p in AUDIT_INPUTS), evidence_paths=("/evidence",))
REVISION_CONTEXT_INPUTS = (
    _input("prior_draft", "Exact Intake to revise.", "scidiscovery.scientific-intake.v1", resource="scientific_intake_schema", min_items=0, usage="evidence_inventory"),
    _input("change_request", "Optional exact scientific feedback.", "scidiscovery.evidence-audit.v1", resource="evidence_audit_schema", min_items=0, usage="evidence_inventory"),
    *(port.model_copy(update={"min_items": 0, "agent_visible": port.name != "figure_provenance",
        "derivation": InputDerivationSpec(anchor_port="prior_draft", producer_output_port=
            "recovery_manifest_output" if port.name == "figure_provenance" else "tool_evidence")})
        for port in FIGURE_FAMILY_INPUTS if port.name != "paper_source"),
)

OPERATIONS = (
    scientific_agent_operation(AUTHOR_OPERATION,
        "Inspect, extract, save, self-check and author one complete figure ScientificIntake in one task.",
        "A frozen raster or PDF contains the target scientific figure; exact prior Intake and review may request revision.",
        "Granting qualification or changing source identity.",
        decision_fields=("/scientific_foundation/summary", "/scientific_foundation/missing_inputs", "/scientific_foundation/open_questions", "/problem_frame/current_contradiction"),
        agent=_general("evidence_agent"), workspace=_general("workspace"), prompt=ComponentRef("figure_author_prompt"),
        tools=BASE_TOOLS+(PDF_TOOL, ComponentRef("figure_source_inspection_tool"), ComponentRef("figure_digitization_preview_tool"), ComponentRef("figure_save_tool"), ComponentRef("figure_reuse_tool")),
        inputs=(PAPER_SOURCE_INPUT, _input("research_objective", "Explicit scientific target.", "scidiscovery.research-objective.v1",
            resource="research_objective_schema", min_items=0, usage="prior_signal"), *REVISION_CONTEXT_INPUTS),
        outputs=(INTAKE_OUTPUT, FAMILY_OUTPUT), timeout=1500, max_input_bytes=355*1024*1024,
        max_output_bytes=321*1024*1024, max_files=41, native_view_image=True,
        input_validation=InputValidationSpec(ComponentRef("figure_revision_inputs"), "curve.figure.revision_family",
            "A prior Intake restores its original family; wording-only work can reuse those immutable files."),
        review=ReviewSpec(reviewer_operation=AUDIT_OPERATION, reviewer_input_port="scientific_intake", subject_outputs=("scientific_intake",))),
    scientific_agent_operation(AUDIT_OPERATION,
        "Independently audit one Intake against its complete selected figure family.",
        "A completed provisional author supplies Intake, exact provenance and all saved family files.",
        "Redigitizing, revising or qualifying evidence.",
        agent=_general("auditor_agent"), workspace=_general("workspace"), prompt=ComponentRef("figure_audit_prompt"),
        decision_fields=("checks",),
        tools=BASE_TOOLS+(PDF_TOOL,), inputs=AUDIT_INPUTS, outputs=(AUDIT_OUTPUT,), timeout=600,
        max_input_bytes=355*1024*1024, max_output_bytes=32*1024, max_files=1, native_view_image=True,
        input_validation=FAMILY_VALIDATION, guards=(ComponentRef("figure_audit_parentage"),)),
)
