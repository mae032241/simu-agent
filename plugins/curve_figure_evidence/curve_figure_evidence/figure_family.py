"""Exact selected tool-family binding shared by author, audit and bundle admission."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.tool_evidence import ToolEvidenceManifest
from scidiscovery.general_science_components import _intake_source_context
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations.input_validation import OperationInvocationError
from scidiscovery.operations.spec import CallableComponent
from .figure_digitization_contract import FigureDigitizationRequest
from .scientific_files import restore_figure_file
from .figure_evidence_validation import build_figure_evidence_validation_report

AUTHOR_OPERATION = "science.evidence.extract.figure.v3"
AUDIT_OPERATION = "science.figure.evidence.audit.v2"
SAVE_TOOL = "worker_curve_figure_save"
SELECTION_ITEM = "selected_family/selection.json"
REQUEST_ITEM = "figure_request/request.json"
ALGORITHM = "curve-figure-digitizer.v1"


class FigureFamilyMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_item: str = Field(min_length=1, max_length=512)
    artifact_ref: ArtifactRef
    media_type: Literal["application/json", "image/png", "text/csv"]
    size_bytes: int = Field(ge=1)


class SelectedFigureFamily(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["scidiscovery.selected-figure-family.v1"] = "scidiscovery.selected-figure-family.v1"
    source_ref: ArtifactRef
    algorithm: Literal["curve-figure-digitizer.v1"] = ALGORITHM
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[FigureFamilyMember, ...] = Field(min_length=1, max_length=38)


def selected_family_files(proof, records_by_ref, source_ref):
    """Read exact controlled bytes, never select the last attempt or rerun extraction."""
    records = proof.records
    selected = [r for r in records if r.get("metadata", {}).get("data_item") == SELECTION_ITEM]
    if len(selected) != 1:
        raise ValueError("exactly one explicitly saved figure family is required")
    expected_refs = [ArtifactRef.model_validate(r["artifact_ref"]) for r in records]
    if len(set(expected_refs)) != len(expected_refs) or set(expected_refs) != set(records_by_ref):
        raise ValueError("figure family has missing, extra or duplicate controlled files")
    for record in records:
        ref = ArtifactRef.model_validate(record["artifact_ref"])
        raw = records_by_ref[ref]
        if (record.get("tool_name") != SAVE_TOOL or record.get("source_ref") != source_ref.model_dump(mode="json")
                or hashlib.sha256(raw).hexdigest() != ref.sha256 or len(raw) != record["size_bytes"]):
            raise ValueError("figure file source, tool, size or identity differs")
    records_by_ref = {ArtifactRef.model_validate(record["artifact_ref"]): restore_figure_file(
        records_by_ref[ArtifactRef.model_validate(record["artifact_ref"])], record["metadata"]) for record in records}
    selection = SelectedFigureFamily.model_validate_json(records_by_ref[ArtifactRef.model_validate(selected[0]["artifact_ref"])], strict=True)
    if selection.source_ref != source_ref:
        raise ValueError("selected figure source differs")
    member_refs = [member.artifact_ref for member in selection.members]
    if (len(set(member_refs)) != len(member_refs)
            or set(member_refs) != set(expected_refs) - {ArtifactRef.model_validate(selected[0]["artifact_ref"])}
            or len({m.data_item for m in selection.members}) != len(selection.members)):
        raise ValueError("selected figure membership differs from complete controlled family")
    by_ref = {ArtifactRef.model_validate(r["artifact_ref"]): r for r in records}
    files = {}
    for member in selection.members:
        record = by_ref[member.artifact_ref]
        if (record["metadata"].get("data_item") != member.data_item
                or record["media_type"] != member.media_type or record["size_bytes"] != member.size_bytes
                or record["metadata"].get("request_sha256") != selection.request_sha256):
            raise ValueError("selected member metadata differs")
        files[member.data_item] = (records_by_ref[member.artifact_ref], member.media_type)
    if REQUEST_ITEM not in files:
        raise ValueError("selected figure request is missing")
    request_raw = files[REQUEST_ITEM][0]
    request = FigureDigitizationRequest.model_validate_json(request_raw, strict=True)
    if hashlib.sha256(request_raw).hexdigest() != selection.request_sha256 or request.source.source_sha256 != source_ref.sha256:
        raise ValueError("selected request or original source hash differs")
    if request.request_status != "ready":
        if set(files) != {REQUEST_ITEM}:
            raise ValueError("an unresolved request cannot assert extracted figure files")
        return files
    request.require_ready()
    manifest_name, report_name = "figure_manifest/evidence.json", "validation_reports/validation_report.json"
    if not {manifest_name, report_name} <= files.keys():
        raise ValueError("selected extraction is missing its manifest or report")
    siblings = {name: value for name, value in files.items() if name not in {REQUEST_ITEM, manifest_name, report_name}}
    manifest = json.loads(files[manifest_name][0])
    if manifest["provenance"]["spec_sha256"] != selection.request_sha256:
        raise ValueError("figure manifest belongs to a different extraction request")
    replay = build_figure_evidence_validation_report(manifest_data_item=manifest_name,
        manifest_content=files[manifest_name][0], sibling_files=siblings)
    if canonical_json(replay) != files[report_name][0]:
        raise ValueError("figure deterministic report differs from exact saved files")
    return files


def _bound_family(sources):
    descriptors = sources.binding_descriptors
    def one(port):
        names = [name for name, d in descriptors.items() if d.port_name == port]
        if len(names) != 1:
            raise ValueError(f"figure family requires one {port}")
        return names[0]
    source = descriptors[one("paper_source")].artifact_ref
    proof = ToolEvidenceManifest.model_validate_json(sources[one("figure_provenance")], strict=True)
    files = {d.artifact_ref: sources[name] for name, d in descriptors.items() if d.port_name == "figure_family"}
    if len(files) != sum(d.port_name == "figure_family" for d in descriptors.values()):
        raise ValueError("duplicate figure member binding")
    return selected_family_files(proof, files, source)


def validate_family_inputs(sources):
    try:
        _bound_family(sources)
    except (ValueError, KeyError, TypeError) as error:
        raise OperationInvocationError("input_figure_family_mismatch", port="figure_family", message=str(error)) from error


def validate_intake_context(payload, sources, handoff):
    _intake_source_context(payload, sources, handoff)
    try:
        if sources.tool_snapshot is None:
            raise ValueError("figure Intake requires controlled tool evidence")
        proof = ToolEvidenceManifest.model_validate_json(sources.tool_snapshot, strict=True)
        descriptors = sources.binding_descriptors
        source = next(d.artifact_ref for d in descriptors.values() if d.port_name == "paper_source")
        files = {d.artifact_ref: sources[name] for name, d in descriptors.items() if d.port_name == "tool_evidence"}
        selected_family_files(proof, files, source)
    except (ValueError, KeyError, TypeError, StopIteration) as error:
        raise SemanticRuleViolation(str(error)) from error


def figure_audit_parentage(inputs, parameters, *, intake_port="scientific_intake"):
    if parameters:
        return False
    groups = {}
    for item in inputs:
        groups.setdefault(item.port_name, []).append(item.artifact)
    if any(len(groups.get(p, ())) != 1 for p in ("paper_source", intake_port, "figure_provenance")):
        return False
    source, intake, proof = (groups[p][0] for p in ("paper_source", intake_port, "figure_provenance"))
    intake_labels, proof_labels = dict(intake.labels), dict(proof.labels)
    members = groups.get("figure_family", ())
    return bool(members and intake.producer_run_id
        and intake_labels.get("operation_id") == AUTHOR_OPERATION
        and intake_labels.get("operation_output_port") == "scientific_intake"
        and proof_labels.get("operation_id") == AUTHOR_OPERATION
        and proof_labels.get("operation_output_port") == "recovery_manifest_output"
        and proof_labels.get("tool_producer_run") == intake.producer_run_id
        and {source.ref, proof.ref} <= set(intake.parent_refs)
        and {source.ref, *(item.ref for item in members)} <= set(proof.parent_refs)
        and all(source.ref in item.parent_refs and dict(item.labels).get("tool_name") == SAVE_TOOL for item in members))


def figure_revision_parentage(inputs, parameters):
    if parameters:
        return False
    grouped = {item.port_name: item.artifact for item in inputs}
    prior, review = grouped.get("prior_draft"), grouped.get("change_request")
    family_present = bool({"figure_provenance", "figure_family"} & grouped.keys())
    if prior is None and review is None and not family_present:
        return True
    if prior is None or review is None or not figure_audit_parentage(inputs, parameters, intake_port="prior_draft"):
        return False
    expected = {item.artifact.ref for item in inputs if item.port_name in
        {"paper_source", "prior_draft", "figure_provenance", "figure_family"}}
    return bool(dict(review.labels).get("operation_id") == AUDIT_OPERATION
        and review.handoff_verdict != "pass" and expected <= set(review.parent_refs))


def validate_revision_inputs(sources):
    if any(d.port_name == "prior_draft" for d in sources.binding_descriptors.values()):
        validate_family_inputs(sources)


FIGURE_INTAKE_CONTEXT = CallableComponent("validator", validate_intake_context)
FIGURE_FAMILY_INPUT_VALIDATOR = CallableComponent("validator", validate_family_inputs)
FIGURE_AUDIT_PARENTAGE = CallableComponent("guard", figure_audit_parentage)
FIGURE_REVISION_PARENTAGE = CallableComponent("guard", figure_revision_parentage)

FIGURE_REVISION_INPUT_VALIDATOR = CallableComponent("validator", validate_revision_inputs)
