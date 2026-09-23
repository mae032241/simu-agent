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


def retain_calculation(context, response, *, summary=False):
    """Keep the existing tool reply readable, but remove the need to copy it.

    The complete record is a tool output. The added alias is a transport hint,
    excluded by CalculationRecord from receipt identity and historical replay.
    """
    record = CalculationRecord.model_validate_json(canonical_json(response))
    saved = publish_analysis_file(context, canonical_json(record.model_dump(mode="json")), media_type="application/json",
        kind="calculation_record", sources=tuple(record.input_digests) or ("experiment_plan",),
        suffix=".json", metadata={"record_key": record.record_key})
    if not summary:
        return {**response, "calculation_ref": saved["evidence_alias"]}
    result = {key: response[key] for key in
              ("record_key", "status", "reason_code", "algorithm_version", "diagnostics") if key in response}
    report = response.get("result") or {}
    metric_report = report.get("metric_report", report)
    comparisons = metric_report.get("comparisons", [])
    result["summary"] = {
        "aggregate_status": metric_report.get("aggregate_status"),
        "comparison_count": len(comparisons),
        "comparisons": [{"comparison_key": item["comparison_key"], "status": item["status"],
            "metrics": [{key: metric[key] for key in ("operator_key", "kind", "status", "value", "unit", "reason_code") if key in metric}
                        for metric in item.get("metrics", [])[:4]],
            "omitted_metrics": max(0, len(item.get("metrics", []))-4)} for item in comparisons[:4]],
        "omitted_comparisons": max(0, len(comparisons)-4),
        "interpretation_boundary": "deterministic_metrics_only_no_physical_interpretation",
    }
    return {**result, "calculation_ref": saved["evidence_alias"], "calculation_path": saved["path"]}


def calculation_reference_aliases(records, sources):
    """Join inline/file representations of one complete controlled receipt.

    Manifest scope and artifact identity distinguish identical bytes from
    different Runs. Receipt owners still verify consumed records before sealing.
    """
    from .tool_evidence import ToolEvidenceManifest, _recovery_origins

    if not records:
        return {}
    descriptors = getattr(sources, "binding_descriptors", {})
    prior = prior_analysis_sources(sources)
    proofs = {}
    aliases = {}
    for record in records:
        if not isinstance(record, CalculationRecord) or record.attempt is None:
            continue
        manifest_alias = record.attempt.manifest_alias
        if manifest_alias not in proofs:
            raw = (getattr(sources, "tool_snapshot", None) if manifest_alias == "tool_recovery_manifest"
                   else sources[manifest_alias] if prior and manifest_alias == prior["manifest_alias"] else None)
            # Missing/unpaired receipts retain their original identities; the
            # existing receipt consumer owns the resulting diagnostic.
            proofs[manifest_alias] = ToolEvidenceManifest.model_validate_json(raw) if raw else None
        proof = proofs[manifest_alias]
        if proof is None:
            continue
        recovered_refs = {canonical_json(binding.artifact_ref) for origin in _recovery_origins(proof.recovery)
                          for binding in origin.bindings.values()}
        scope = (recovered_refs if record.attempt.proof_kind == "recovery" else
                 {canonical_json(item.get("artifact_ref")) for item in proof.records} - recovered_refs)
        # These two fields are transport projections of the selected proof.
        # The stored tool record uses its original current-manifest spelling.
        original = record.model_copy(update={"attempt": record.attempt.model_copy(update={
            "manifest_alias": "tool_recovery_manifest", "proof_kind": "current"})})
        digest = hashlib.sha256(canonical_json(original.model_dump(mode="json"))).hexdigest()
        matches = sorted(alias for alias, descriptor in descriptors.items()
                         if dict(descriptor.labels).get("analysis_artifact_kind") == "calculation_record"
                         and descriptor.sha256 == digest and canonical_json(descriptor.artifact_ref) in scope)
        identities = {canonical_json(descriptors[alias].artifact_ref) for alias in matches}
        if len(identities) == 1:
            aliases.update({alias: matches[0] for alias in matches})
            aliases["calculation_records:" + record.record_key] = matches[0]
    return aliases


def analysis_source_claims(source_key, locator, input_alias, sources, calculation_aliases=None):
    """Use the same source identities for validation and mechanical completion."""
    claims = {source_key} if source_key in sources else set()
    if input_alias is not None:
        claims.add(input_alias)
    if locator.startswith("calculation_records:"):
        claims.add(locator)
    elif locator.split(":", 1)[0] in sources:
        claims.add(locator.split(":", 1)[0])
    aliases = calculation_aliases or {}
    return {aliases.get(claim, claim) for claim in claims}


def analysis_evidence_aliases(evidence, references, sources, calculation_aliases=None):
    """Resolve optional citations without letting a generated mapping hide a conflict."""
    resolved = {}
    for index, reference in enumerate(references):
        claims = analysis_source_claims(reference.source_key, "", reference.input_alias, sources, calculation_aliases)
        claims.update(resolved.get(reference.source_key, ()))
        if len(claims) != 1:
            raise declared_violation("analysis source key has conflicting source mappings",
                path=f"$.source_references[{index}].source_key")
        resolved[reference.source_key] = claims
    for index, item in enumerate(evidence):
        claims = analysis_source_claims(item.source_key, item.locator, None, sources, calculation_aliases)
        claims.update(resolved.get(item.source_key, ()))
        if len(claims) > 1:
            raise declared_violation("analysis source key has conflicting source mappings",
                path=f"$.evidence[{index}].source_key")
        resolved[item.source_key] = claims
    return {key: next(iter(claims)) if claims else key for key, claims in resolved.items()}


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
    # Accept direct citations as well as optional local citation mappings. A
    # copied evidence row is not required to consume a tool-owned receipt.
    aliases = list(dict.fromkeys(
        [item.input_alias for item in report.source_references]
        + [item.source_key for item in report.evidence]
        + [item.locator.split(":", 1)[0] for item in report.evidence]))
    pending = [report.model_dump(mode="json")]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for alias in value.get("evidence_keys", ()):
                if alias not in aliases:
                    aliases.append(alias)
            pending.extend(child for child in value.values() if isinstance(child, (dict, list)))
        elif isinstance(value, list):
            pending.extend(child for child in value if isinstance(child, (dict, list)))
    for alias in aliases:
        descriptor = descriptors.get(alias)
        if descriptor is None or dict(descriptor.labels).get("analysis_artifact_kind") != "calculation_record":
            continue
        record = CalculationRecord.model_validate_json(sources[alias])
        is_current = any(item["alias"] == alias and item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                         for item in current)
        proof = current_proof
        if not is_current and any(item["alias"] == alias
                and item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                for item in current_proof.get("accesses", ())):
            # An accessed calculation keeps its producer's proof namespace. The
            # control resolver verifies that exact receipt, without binding its
            # internal sources as new Worker inputs or current products.
            records.append(record.model_copy(update={"calculation_ref": alias}))
            continue
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
