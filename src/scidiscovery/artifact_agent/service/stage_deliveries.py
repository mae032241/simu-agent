"""Read-only scientific views of the experiment's existing immutable receipts.

No workspace drafts, execution calls, binding writes or currentness admission.
Versions are positions among receipts of the same kind/phase, never task states.
"""
from __future__ import annotations

import json
from pydantic import BaseModel, ConfigDict, Field

from ..schema.common import canonical_json


class StageReadQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    stage_offset: int | None = Field(default=None, ge=0,
        description="Explicit 0 reads the first page of sealed experiment deliveries, including running Runs. Continue at next_offset. Omitted means no stage read.")
    stage_limit: int = Field(default=4, ge=1, le=8)
    stage_reference: str | None = Field(default=None, max_length=128,
        description="Exact reference returned by sealed_stages, scoped to this Run. Reads a bounded scientific material text segment, never a private control manifest.")
    stage_text_offset: int = Field(default=0, ge=0,
        description="Character offset for stage_reference; continue at material.next_text_offset.")


_KINDS = {"experiment_stage": None, "experiment_implementation": "implementation",
          "experiment_debug": "debug", "experiment_execution": "execution"}
_TEXT_LIMIT = 8192
_PAGE_BYTES = 32 * 1024


def _content(runs, run, record):
    # Read the sealed CAS original, with its existing integrity verification.
    from ..schema.refs import ArtifactRef
    body = json.loads(runs.artifacts.read(ArtifactRef.model_validate(record["artifact_ref"])))
    aliases = runs.material_source_aliases(run)
    def current(alias):
        return aliases.get(record["source_refs"].get(alias))
    kind = record["metadata"]["kind"]
    if kind == "experiment_stage":
        from ...general_science_experiment_task import StageSubmission
        body["materials"] = [current(alias) for alias in body.get("materials", ())]
        return {key: body[key] for key in StageSubmission.model_fields if key in body}
    if kind == "experiment_implementation":
        body["scientific_files"] = {name: current(alias) for name, alias in body.get("scientific_files", {}).items()}
        return {key: body[key] for key in ("implementation", "scientific_files") if key in body}
    # Adapter observations contain facts. Debug's workspace log path is not a
    # scientific reference and is deliberately absent from this projection.
    keys = ("state", "mode", "summary", "exit_code", "missing_outputs") if kind == "experiment_debug" else (
        "name", "state", "terminal_state", "outputs")
    return {key: body[key] for key in keys if key in body}


def read_stage_deliveries(runs, run, *, instance_id, **arguments):
    query = StageReadQuery.model_validate(arguments)
    if run.instance_id != instance_id:
        raise PermissionError("Run is not owned by the current instance.")
    result = {"run_state": run.state, "qualification": "not_evaluated",
        "final_selection": "pending", "adopted_references": [], "items": [],
        "offset": query.stage_offset or 0, "next_offset": None, "total": 0}
    if run.operation_id != "science.experiment.v1":
        return {**result, "availability": "not_applicable"}
    records = [record for record in runs.available_material_records(run)
        if record.get("metadata", {}).get("kind") in _KINDS]
    selected = set()
    if run.state == "completed" and run.output_ref is not None:
        payload = json.loads(runs.artifacts.read(run.output_ref))
        result["final_selection"] = "sealed"
        result["adopted_references"] = payload.get("adopted_stages", [])
        selected = set(result["adopted_references"])
    inputs = {item.source_name: item.artifact_name for item in run.inputs}
    aliases = runs.material_source_aliases(run)
    sealed = {record["alias"] for record in records}
    versions, entries = {}, []
    for record in records:
        metadata = record["metadata"]
        kind = metadata["kind"]
        stage = metadata.get("stage") if kind == "experiment_stage" else _KINDS[kind]
        key = (kind, stage)
        versions[key] = versions.get(key, 0) + 1
        derived = [aliases.get(record["source_refs"].get(alias)) for alias in metadata.get("derived_from", [])]
        entries.append((record, {"reference": record["alias"], "stage": stage,
            "version": versions[key], "delivery_kind": "author_conclusion" if kind == "experiment_stage" else (
                "scientific_material" if kind == "experiment_implementation" else "executor_observation"),
            "adopted": record["alias"] in selected if result["final_selection"] == "sealed" else None,
            "origin": "reused" if record["producer_run_id"] != run.run_id else "created_here",
            **({"source_artifact_name": inputs[record["alias"]]} if record["alias"] in inputs else {}),
            "unavailable_materials": derived.count(None),
            "materials": [{"reference": alias, "source_kind": "sealed_material" if alias in sealed else "input",
                **({"artifact_name": inputs[alias]} if alias in inputs else {})}
                for alias in derived if alias is not None], "size_bytes": record["size_bytes"]}))
    result.update(availability="available", total=len(entries))
    if query.stage_reference is not None:
        pair = next((pair for pair in entries if pair[0]["alias"] == query.stage_reference), None)
        if pair is None:
            raise ValueError("No sealed experiment material has that reference in this Run.")
        record, item = pair
        text = canonical_json(_content(runs, run, record)).decode("utf-8")
        offset = query.stage_text_offset
        end = min(offset + _TEXT_LIMIT, len(text))
        result["material"] = {**item, "text": text[offset:end], "text_offset": offset,
            "total_characters": len(text), "next_text_offset": end if end < len(text) else None}
        return result
    used = len(canonical_json(result)) + 256  # separators and continuation metadata
    for record, item in entries[result["offset"]:result["offset"] + query.stage_limit]:
        body = _content(runs, run, record)
        omitted = []
        # Exact bounded excerpts; full scientific projection remains addressable
        # by the same Run and material name with character pagination.
        for field in ("conclusion", "remaining_question", "summary"):
            if field in body:
                item[field] = body[field][:2048]
                if len(body[field]) > 2048:
                    omitted.append(field)
        if "limitations" in body:
            item["limitations"] = [value[:512] for value in body["limitations"][:8]]
            if item["limitations"] != body["limitations"]:
                omitted.append("limitations")
        if item["delivery_kind"] == "executor_observation":
            for field in ("state", "mode", "exit_code", "terminal_state"):
                if field in body:
                    item[field] = body[field]
        if "missing_outputs" in body:
            item["missing_outputs"] = [value[:512] for value in body["missing_outputs"][:8]]
            if item["missing_outputs"] != body["missing_outputs"]:
                omitted.append("missing_outputs")
        if "outputs" in body:
            item["outputs"] = body["outputs"][:8]
            if len(body["outputs"]) > 8:
                omitted.append("outputs")
        if "implementation" in body:
            project = body["implementation"]
            item["files"] = [value["relative_path"] for value in project.get("files", [])[:8]]
            item["file_count"] = len(project.get("files", []))
            omitted.append("implementation")
        item["omitted_fields"] = omitted
        size = len(canonical_json(item))
        if used + size > _PAGE_BYTES:
            # Legacy/unexpectedly large field names still retain a navigable item.
            if result["items"]:
                break
            item = {key: item[key] for key in ("reference", "stage", "version", "delivery_kind", "adopted", "size_bytes")}
            item["omitted_fields"] = ["content"]
            size = len(canonical_json(item))
        result["items"].append(item)
        used += size
    end = result["offset"] + len(result["items"])
    result["next_offset"] = end if end < len(entries) else None
    return result
