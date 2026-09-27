"""Read-only receipt resolution for explicitly available immutable materials.

An input alias belongs to the consumer; receipt aliases belong to its producer.
Neither receipt adoption nor a new artifact is needed to read a bound material.
"""
from ..schema.refs import ArtifactRef
from ...operation_contract import DiagnosticError, contract_diagnostic


def material_error(code, message, *, path="$.implementation"):
    return DiagnosticError(message, details=(contract_diagnostic(code,
        phase="tool_execution", affected_action="tool_call", path=path,
        repairable=True, message=message),))


def source_aliases(runs, value):
    aliases = {}
    for item in value.inputs:
        aliases.setdefault(item.artifact_ref, item.source_name)
    for item in (*runs.tool_evidence(value.run_id), *runs.reference_access_records(value.run_id)):
        aliases.setdefault(ArtifactRef.model_validate(item["artifact_ref"]), item["alias"])
    return aliases


def resolve_material(runs, value, alias):
    """Return a verified receipt view, or None for an ordinary non-tool input."""
    bound = next((i for i in value.inputs if i.source_name == alias), None)
    current = next((r for r in runs.tool_evidence(value.run_id) if r["alias"] == alias), None)
    if bound is None and current is None:
        return None
    ref = bound.artifact_ref if bound else ArtifactRef.model_validate(current["artifact_ref"])
    envelope = runs.artifacts.catalog(ref)
    producer_id = envelope.labels.get("tool_producer_run")
    if producer_id is None or envelope.labels.get("tool_name") is None:
        return None
    producer = runs.status(producer_id)
    if producer.instance_id != value.instance_id:
        raise material_error("material_origin_mismatch", "The sealed material belongs to another instance.")
    # A failed owner may have sealed useful evidence before interruption. Exact
    # input binding authorizes reuse; owner completion is not a material identity.
    records = [r for r in runs.tool_evidence(producer_id)
               if ArtifactRef.model_validate(r["artifact_ref"]) == ref]
    if len(records) != 1:
        raise material_error("material_receipt_mismatch", "The exact material has no unique original tool receipt.")
    record = records[0]
    if (record["tool_name"] != envelope.labels.get("tool_name")
            or record["size_bytes"] != envelope.size_bytes or record["media_type"] != envelope.media_type
            or (current is not None and current != record)):
        raise material_error("material_receipt_mismatch", "The material differs from its original control receipt.")
    runs.artifacts.verify(ref)
    # Keep the original alias namespace with its receipt. Consumers compare refs,
    # not text copied from the previous task's metadata or scientific JSON.
    sources = {i.source_name: i.artifact_ref for i in producer.inputs}
    sources.update({r["alias"]: ArtifactRef.model_validate(r["artifact_ref"])
                    for r in (*runs.tool_evidence(producer_id), *runs.reference_access_records(producer_id))})
    return {**record, "alias": alias, "origin_alias": record["alias"],
            "producer_run_id": producer_id, "source_refs": sources}


def available_materials(runs, value):
    names = dict.fromkeys([i.source_name for i in value.inputs] +
                          [r["alias"] for r in runs.tool_evidence(value.run_id)])
    return [record for alias in names if (record := resolve_material(runs, value, alias)) is not None]
