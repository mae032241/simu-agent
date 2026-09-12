"""Read-only TCAD correspondence projection from the exact bound cohort."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from curve_score import analysis_workspace
from scidiscovery.artifact_agent.service.local_workspace import (
    read_control_workspace_file, write_control_workspace_file,
)
from scidiscovery.artifact_agent.service.result_materialization import finalize_result
from scidiscovery.operations.input_validation import ValidationSources, prior_analysis_sources
from scidiscovery.operations.spec import CallableComponent


JSON_PORTS = {"experiment_plan", "reviewed_package", "prior_analysis",
    "prior_analysis_manifest", "recovery_manifest"}
VIEW_PATH = "analysis-bindings.json"


def source_bindings(sources):
    """Project metadata, retaining historical mappings as conditional claims.

    This consumes admission's immutable identity facts; it does not select heads
    or renew qualification. Raw source bytes are not needed for this projection.
    """
    descriptors = sources.binding_descriptors
    by_port = {d.port_name: alias for alias, d in descriptors.items() if d.port_name in JSON_PORTS}
    package = json.loads(sources[by_port["reviewed_package"]])
    plan = json.loads(sources[by_port["experiment_plan"]])
    expected = {item["name"]: item for item in package["project"]["expected_outputs"]}
    cases = {(p["experiment_key"], c["case_key"]) for p in plan["proposals"] for c in p["cases"]}
    view = {"sources": {}, "unavailable": []}
    for alias, descriptor in descriptors.items():
        if descriptor.port_name not in {"solver_outputs", "tool_evidence"} or descriptor.output_name is None:
            continue
        item = {"output_name": descriptor.output_name}
        declaration = expected.get(descriptor.output_name, {})
        if declaration.get("case_key") is not None:
            item.update(experiment_key=declaration.get("experiment_key"), case_key=declaration["case_key"],
                origin={"input_alias": by_port["reviewed_package"], "kind": "declared"})
        view["sources"][alias] = item
    prior = prior_analysis_sources(sources)
    if prior is None:
        return view
    mapped = prior["source_bindings"]
    manifest = json.loads(sources[prior["manifest_alias"]])
    for port in ("experiment_plan", "reviewed_package"):
        old = [alias for alias, binding in manifest.get("bindings", {}).items() if binding.get("port_name") == port]
        if len(old) != 1 or mapped.get(old[0]) != by_port[port]:
            view["unavailable"].append({"reason": "prior_execution_cohort_not_bound"})
            return view
    historical = json.loads(sources[prior["analysis_alias"]])
    candidates = {}
    for index, reference in enumerate(historical.get("source_references", ())):
        alias = mapped.get(reference.get("input_alias"))
        current = view["sources"].get(alias)
        if current is None or current.get("case_key") is not None:
            continue
        pair = (reference.get("experiment_key"), reference.get("case_key"))
        basis = deepcopy(reference.get("case_mapping_basis"))
        if (pair not in cases or reference.get("output_name") not in (None, current["output_name"])
                or not basis or basis.get("kind") != "evidence" or not basis.get("evidence_refs")):
            continue
        complete = True
        for evidence in basis["evidence_refs"]:
            old = evidence["input_alias"]
            if old not in mapped:
                complete = False
                break
            evidence["input_alias"] = mapped[old]
            locator = evidence["locator"]
            if locator == old or locator.startswith(old + ":"):
                evidence["locator"] = mapped[old] + locator[len(old):]
        if not complete:
            view["unavailable"].append({"input_alias": alias, "reason": "prior_basis_source_not_bound"})
            continue
        candidates.setdefault(alias, []).append({**current,
            "experiment_key": pair[0], "case_key": pair[1], "case_mapping_basis": basis,
            "origin": {"kind": "prior_conditional_claim", "input_alias": prior["analysis_alias"],
                "pointer": f"/source_references/{index}"}})
    for alias, values in candidates.items():
        if len({(item["experiment_key"], item["case_key"]) for item in values}) == 1:
            view["sources"][alias] = values[0]
        else:
            view["unavailable"].append({"input_alias": alias, "reason": "prior_case_ambiguous"})
    return view


def workspace_sources(request):
    # Paths are already scoped to this workspace; descriptors contain no new
    # file capabilities. Only the small declared JSON sources are read here.
    contents = {alias: read_control_workspace_file(request.workspace,
        path.relative_to(request.workspace), max_bytes=request.binding_descriptors[alias].size_bytes)
        for alias, path in request.input_paths.items()
        if request.binding_descriptors[alias].port_name in JSON_PORTS}
    return ValidationSources(contents, request.binding_descriptors)


def materialize(request):
    result = analysis_workspace.materialize(request)
    view = source_bindings(workspace_sources(request))
    write_control_workspace_file(request.workspace, Path(VIEW_PATH),
        (json.dumps(view, ensure_ascii=False) + "\n").encode(), replace=False, mode=0o400)
    # A pointer keeps the start entry bounded even for a large historical basis.
    path = Path(analysis_workspace.START)
    start = json.loads(read_control_workspace_file(request.workspace, path, max_bytes=analysis_workspace.START_LIMIT))
    start["source_bindings"] = {"relative_path": VIEW_PATH,
        "meaning": "Declared metadata and prior conditional mappings; no renewed scientific qualification. New tool evidence uses its current descriptor."}
    write_control_workspace_file(request.workspace, path,
        (json.dumps(start, ensure_ascii=False) + "\n").encode(), replace=True, mode=0o400)
    return replace(result, paths={**result.paths, "source_bindings": VIEW_PATH},
        read_paths=(*result.read_paths, VIEW_PATH))


def materialize_references(payload, view):
    evidence = payload.get("evidence", [])
    references = payload.get("source_references", [])
    if not isinstance(evidence, list) or not isinstance(references, list):
        return  # The output schema reports malformed new content.
    references = deepcopy(references)
    by_key = {item["source_key"]: item for item in references
        if isinstance(item, dict) and isinstance(item.get("source_key"), str)}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("locator"), str) or not isinstance(item.get("source_key"), str):
            continue
        alias = item["locator"].split(":", 1)[0]
        known = view["sources"].get(alias)
        if known is None:
            continue
        reference = by_key.get(item["source_key"])
        if reference is None:
            if len(references) >= 64:
                continue  # No second table is required for a plain bound locator.
            reference = {"source_key": item["source_key"], "input_alias": alias}
            references.append(reference)
            by_key[item["source_key"]] = reference
        elif reference.get("input_alias", alias) != alias:
            continue  # Never hide an explicit source conflict.
        reference.setdefault("input_alias", alias)
    for reference in references:
        if not isinstance(reference, dict) or not isinstance(reference.get("input_alias"), str):
            continue
        known = view["sources"].get(reference["input_alias"])
        if known is None:
            continue
        if reference.get("output_name") is None:
            reference["output_name"] = known["output_name"]
        compatible = all(reference.get(key) in (None, known.get(key)) for key in ("experiment_key", "case_key"))
        # An explicit new scientific basis remains the Agent's claim.
        if compatible and reference.get("case_mapping_basis") is None:
            for key in ("experiment_key", "case_key", "case_mapping_basis"):
                if reference.get(key) is None and key in known:
                    reference[key] = deepcopy(known[key])
    # Do not cause an optional mechanical projection to exceed the report bound.
    candidate = {**payload, "source_references": references}
    from scidiscovery.artifact_agent.schema.common import canonical_json
    if len(canonical_json(candidate)) <= 128 * 1024:
        payload["source_references"] = references


def finalize(request):
    view = source_bindings(workspace_sources(request))
    return finalize_result(request, lambda value: materialize_references(value["payload"], view))


MATERIALIZER = CallableComponent("workspace_materializer", materialize)
FINALIZER = CallableComponent("workspace_finalizer", finalize)

WORKSPACE = analysis_workspace.WORKSPACE
SNAPSHOTTER = analysis_workspace.SNAPSHOTTER
