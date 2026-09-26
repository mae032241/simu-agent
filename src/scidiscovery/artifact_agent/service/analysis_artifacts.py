"""Tool-owned analysis files and reference-only consumption of their receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...operation_contract import declared_violation
from ...operations.input_validation import prior_analysis_sources
from ..schema.common import canonical_json
from .calculation_proof import ControlledCalculationRecord as CalculationRecord, controlled_calculation, scientific_calculation
from .local_workspace import write_control_workspace_file


def publish_analysis_file(context, raw, *, media_type, kind, sources, suffix, metadata=None):
    """Register immutable bytes first; expose only a task-local preview path."""
    accepted = context.accept_evidence(raw=raw, media_type=media_type, derived_from=tuple(sources),
        metadata={**(metadata or {}), "kind": kind})
    write_control_workspace_file(context.workspace,
        Path(".operation-tools/analysis") / (accepted["alias"] + suffix), raw,
        replace=False, mode=0o400, create_parents=True)
    return {"evidence_alias": accepted["alias"]}


def retain_calculation(context, response, *, summary=False):
    """Keep the existing tool reply readable, but remove the need to copy it.

    The complete record is a tool output. The added alias is a transport hint,
    excluded by CalculationRecord from receipt identity and historical replay.
    """
    record = CalculationRecord.model_validate_json(canonical_json(response))
    saved = publish_analysis_file(context, canonical_json(scientific_calculation(record)), media_type="application/json",
        kind="calculation_record", sources=tuple(record.input_digests) or context.input_names_for_port("experiment_results") or context.input_names_for_port("execution_result"),
        suffix=".json", metadata={"record_key": record.record_key, "calculation_proof": record.model_dump(mode="json")})
    response = scientific_calculation(record)
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
        "limitations": report.get("limitations", []),
    }
    return {**result, "calculation_ref": saved["evidence_alias"]}


def analysis_source_claims(source_key, locator, input_alias, sources, calculation_aliases=None):
    """Use the same source identities for validation and mechanical completion."""
    claims = {source_key} if source_key in sources else set()
    if input_alias is not None:
        claims.add(input_alias)
    if locator.split(":", 1)[0] in sources:
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

    Reports cite current registered scientific files or exact originals from a
    paired prior analysis. The service verifies their private sealed receipts.
    """
    records = []
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
        is_current = any(item["alias"] == alias and item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                         for item in current)
        proof = current_proof
        if not is_current and any(item["alias"] == alias
                and item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json")
                for item in current_proof.get("accesses", ())):
            # An accessed calculation keeps its producer's proof namespace. The
            # control resolver verifies that exact receipt, without binding its
            # internal sources as new Worker inputs or current products.
            original_sources = sources.reference_calculation_sources(alias)
            receipt = next(item for item in json.loads(original_sources.tool_snapshot)["records"]
                if item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json"))
            record = controlled_calculation(sources[alias], receipt)
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
        receipt = next(item for item in proof.get("records", ())
            if item["artifact_ref"] == descriptor.artifact_ref.model_dump(mode="json"))
        record = controlled_calculation(sources[alias], receipt)
        if not is_current and record.attempt is not None:
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
