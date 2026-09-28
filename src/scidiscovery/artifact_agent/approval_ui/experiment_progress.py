"""Read experiment progress from existing control records, without polling solvers."""
import json

from ..schema.refs import ArtifactRef


_PHASES = {"experiment_implementation": "implementation", "experiment_debug": "debug",
           "experiment_execution": "execution"}


def read_progress(model, run, *, detail=False):
    result = {"last_activity_at": run.last_activity_at, "stages": [], "executions": [],
              "execution_count": 0, "omitted_executions": 0, "gaps": []}
    try:
        timing = model.runs.tool_timing(run.run_id)
        if timing:
            result["latest_activity"] = timing[-1]
    except Exception:
        result["gaps"].append("activity_progress_unavailable")
    try:
        records = model.runs.tool_evidence(run.run_id)
        phases = {}
        latest_conclusion = None
        for record in records:
            metadata = record.get("metadata", {})
            kind = metadata.get("kind")
            phase = metadata.get("stage") if kind == "experiment_stage" else _PHASES.get(kind)
            if phase not in {"design", "implementation", "debug", "execution", "validity"}:
                continue
            phases[phase] = {"stage": phase, "reference": record["alias"]}
            if kind == "experiment_stage":
                latest_conclusion = record
        result["stages"] = list(phases.values())
        if detail and latest_conclusion is not None:
            # Metadata/list views never load scientific payloads. The detail view
            # reads only the exact latest sealed author conclusion, not a draft.
            ref = ArtifactRef.model_validate(latest_conclusion["artifact_ref"])
            envelope = model.artifacts.catalog(ref)
            if envelope.size_bytes <= 128 * 1024:
                payload = json.loads(model.artifacts.read(ref))
                result["latest_conclusion"] = {"stage": latest_conclusion["metadata"]["stage"],
                    "reference": latest_conclusion["alias"],
                    "text": str(payload.get("conclusion", ""))[:1200],
                    "limitations": [str(item)[:512] for item in payload.get("limitations", [])[:4]],
                    "remaining_question": str(payload.get("remaining_question", ""))[:512],
                    "omitted": len(str(payload.get("conclusion", ""))) > 1200}
    except Exception:
        result["gaps"].append("stage_progress_unavailable")
    try:
        origin = model.runs.task_lineage(run.run_id)[-1].run_id
        prefix = "experiment-" + origin + "-"
        bindings = model.bindings.list(instance=run.instance_id, namespace="execution", name_prefix=prefix)
        owned = []
        # Inspect only a bounded recent set. Recovery ancestry is the owner;
        # sharing a scientific objective or package is not ownership.
        for binding in bindings[:32]:
            request = model.artifacts.get_by_id(model.executions.request_artifact_id(binding.object_id))
            if request.labels.get("experiment_run") == origin:
                status = model.executions.status(binding.object_id)
                owned.append((binding, status))
        active = {"created", "authorized", "submitted", "running", "cancelling"}
        owned.sort(key=lambda item: item[1].state not in active)
        result["execution_count"] = len(owned)
        result["omitted_executions"] = max(0, len(owned) - 4)
        if len(bindings) > 32:
            result["gaps"].append("execution_history_limited")
        for binding, _ in owned[:4]:
            node = model._metadata(run.instance_id, binding)
            result["executions"].append({key: node[key] for key in (
                "key", "state", "execution_progress", "collection_progress", "collection_status") if key in node}
                | {"name": binding.name[len(prefix):]})
    except Exception:
        result["gaps"].append("execution_progress_unavailable")
    return result
