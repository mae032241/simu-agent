"""Tool-owned analysis files and reference-only consumption of their receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...operation_contract import declared_violation
from ...operations.input_validation import prior_analysis_sources
from ..schema.common import canonical_json
from ..schema.layered_diagnosis import CalculationRecord
from .local_workspace import write_control_workspace_file


def publish_analysis_file(context, raw, *, media_type, kind, sources, suffix, metadata=None):
    """Register immutable bytes first; expose only a task-local preview path."""
    accepted = context.accept_evidence(raw=raw, media_type=media_type, derived_from=tuple(sources),
        metadata={**(metadata or {}), "kind": kind})
    digest = hashlib.sha256(raw).hexdigest()
    path = write_control_workspace_file(context.workspace,
        Path(".operation-tools/analysis") / (digest + suffix), raw,
        replace=False, mode=0o400, create_parents=True)
    return {"evidence_alias": accepted["alias"], "path": str(path), "sha256": digest}


def retain_calculation(context, response):
    """Keep the existing tool reply readable, but remove the need to copy it.

    The complete record is a tool output. The added alias is a transport hint,
    excluded by CalculationRecord from receipt identity and historical replay.
    """
    record = CalculationRecord.model_validate_json(canonical_json(response))
    saved = publish_analysis_file(context, canonical_json(record.model_dump(mode="json")), media_type="application/json",
        kind="calculation_record", sources=tuple(record.input_digests) or ("experiment_plan",),
        suffix=".json", metadata={"record_key": record.record_key})
    return {**response, "calculation_ref": saved["evidence_alias"]}


def analysis_calculations(report, sources):
    """Resolve cited tool records without changing scientific output or rerunning tools.

    Old inline reports retain their exact validation path. New reports cite a
    current registered file, or an explicitly bound file from their paired prior
    analysis. Provenance and the existing calculation receipt are both checked.
    """
    records = list(report.calculation_records)
    descriptors = getattr(sources, "binding_descriptors", {})
    current_raw = getattr(sources, "tool_snapshot", None)
    current_proof = json.loads(current_raw) if current_raw else {}
    current = current_proof.get("records", ())
    for evidence in report.evidence:
        alias = evidence.locator
        descriptor = descriptors.get(alias)
        if descriptor is None or dict(descriptor.labels).get("analysis_artifact_kind") != "calculation_record":
            continue
        record = CalculationRecord.model_validate_json(sources[alias])
        is_current = any(item["alias"] == alias and item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                         for item in current)
        proof = current_proof
        if not is_current:
            prior = prior_analysis_sources(sources)
            if prior is None:
                raise declared_violation("historical calculation reference needs its paired prior analysis manifest", path="$.evidence")
            proof = json.loads(sources[prior["manifest_alias"]])
            if not any(item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                       for item in proof.get("records", ())):
                raise declared_violation("calculation reference is not in the paired prior manifest", path="$.evidence")
            if record.attempt is not None:
                record = record.model_copy(update={"attempt": record.attempt.model_copy(
                    update={"manifest_alias": prior["manifest_alias"]})})
        recovery = proof.get("recovery") or {}
        if record.attempt is not None and any(binding["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                for binding in recovery.get("bindings", {}).values()):
            record = record.model_copy(update={"attempt": record.attempt.model_copy(update={"proof_kind": "recovery"})})
        # Saved files have distinct artifact identities. Their human-chosen
        # record names need not form another namespace across calls or Runs.
        records.append(record)
    return tuple(records)
