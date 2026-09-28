"""Derived experiment children. No new tasks, approvals or mutable UI bindings."""
from ..schema.refs import ArtifactRef


PHASES = {"design": "实验方案", "implementation": "实验实现", "debug": "诊断",
          "execution": "执行结果", "validity": "有效性判断"}
KINDS = {"experiment_implementation": "implementation", "experiment_debug": "debug",
         "experiment_execution": "execution"}


def parent_binding(model, instance_id, binding):
    """Only a frozen execution request establishes an execution/approval owner."""
    if binding.namespace == "execution":
        requests = [model.artifacts.get_by_id(model.executions.request_artifact_id(binding.object_id))]
    elif binding.namespace == "approval":
        approval = model.approvals.status(binding.object_id)
        envelope = model.artifacts.catalog(approval.approval_request_ref)
        requests = [model.artifacts.catalog(ref) for ref in envelope.parent_refs
                    if ref.schema_id == "scidiscovery.execution-request"]
    else:
        return None
    owners = {request.labels.get("experiment_run") for request in requests}
    if len(owners) != 1 or None in owners:
        return None
    owner = owners.pop()
    name = model.bindings.find_name(instance=instance_id, namespace="run", object_id=owner)
    if name is None:
        return None
    run = model._run(instance_id, owner)
    if run.operation_id != "science.experiment.v1":
        return None
    return model.bindings.get_binding(instance=instance_id, namespace="run", name=name)


def read_children(model, run, *, offset=0, limit=8):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("invalid experiment child page")
    items, gaps, versions = [], [], {}
    name = model.bindings.find_name(instance=run.instance_id, namespace="run", object_id=run.run_id)
    parent_key = "run:" + name
    try:
        for record in model.runs.tool_evidence(run.run_id):
            metadata = record.get("metadata", {})
            kind = metadata.get("kind")
            phase = metadata.get("stage") if kind == "experiment_stage" else KINDS.get(kind)
            if phase not in PHASES:
                continue
            versions[kind, phase] = versions.get((kind, phase), 0) + 1
            envelope = model.artifacts.catalog(ArtifactRef.model_validate(record["artifact_ref"]))
            items.append({"kind": "stage", "reference": record["alias"], "parent_key": parent_key,
                "title": PHASES[phase] + ("结论" if kind == "experiment_stage" else "材料"),
                "version": versions[kind, phase], "state": "sealed", "source_time": envelope.created_at})
            if model.presentation_summaries is not None:
                copy = model.presentation_summaries.read(run.instance_id, envelope.ref)
                if copy:
                    items[-1]["display_copy"] = {"state": copy["state"], "retry": copy.get("retry")}
                if copy and copy["state"] == "ready":
                    text = next((item for item in copy["items"] if item["source"] == "/conclusion"), None)
                    if text:
                        items[-1]["display_title"] = text["title"]
    except Exception:
        gaps.append("stage_children_unavailable")
    try:
        origin = model.runs.task_lineage(run.run_id)[-1].run_id
        prefix = "experiment-" + origin + "-"
        bindings = model.bindings.list(instance=run.instance_id, namespace="execution", name_prefix=prefix)
        if len(bindings) > 64:
            gaps.append("execution_children_limited")
        for binding in bindings[:64]:
            owner = parent_binding(model, run.instance_id, binding)
            if owner is None or owner.object_id != origin:
                continue
            node = model._metadata(run.instance_id, binding)
            items.append({key: node[key] for key in ("key", "kind", "state", "source_time")}
                | {"title": binding.name[len(prefix):], "parent_key": "run:" + owner.name,
                   "source_time": binding.created_at})
            approval_name = model.bindings.find_name(instance=run.instance_id, namespace="approval",
                object_id="apr_" + binding.object_id)
            if approval_name is None:
                continue
            approval = model.bindings.get_binding(instance=run.instance_id, namespace="approval", name=approval_name)
            if parent_binding(model, run.instance_id, approval) != owner:
                continue
            node = model._metadata(run.instance_id, approval)
            items.append({key: node[key] for key in ("key", "kind", "state", "source_time")}
                | {"title": binding.name[len(prefix):] + " · 执行审批", "parent_key": "run:" + owner.name,
                   "source_time": approval.created_at})
    except Exception:
        gaps.append("execution_children_unavailable")
    # Newest first; stage versions are assigned in original receipt order.
    items.sort(key=lambda item: item.get("source_time") or "", reverse=True)
    end = offset + limit
    return {"items": items[offset:end], "offset": offset, "total": len(items),
        "pending_approvals": sum(item["kind"] == "approval" and item["state"] == "pending" for item in items),
        "next_offset": end if end < len(items) else None, "gaps": gaps}
