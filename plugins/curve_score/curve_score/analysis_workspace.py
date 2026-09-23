"""Bounded provisional analysis files; recovery is never scientific evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path

from scidiscovery.artifact_agent.service.local_workspace import (
    WorkspaceError, _media_type, _validate_publication_content,
    read_control_workspace_file,
    write_control_workspace_file,
)
from scidiscovery.artifact_agent.service import local_process_observation
from scidiscovery.operations.spec import CallableComponent, WorkspaceContract
from scidiscovery.operations.workspace import WorkspaceMaterializationResult, WorkspaceSnapshotFile


FORMAT = "analysis-work-v1"
MANIFEST = "analysis-recovery.json"
MAX_FILES = 132
MAX_BYTES = 32 * 1024 * 1024
_SUFFIXES = {".py", ".csv", ".json", ".txt", ".log", ".png"}
START = "analysis-start.json"
START_LIMIT = 24 * 1024
READ_VIEW_LIMIT = 32 * 1024
REPORT_GUIDANCE = """Concentrate the scientific conclusion in payload.summary and overall_verdict.
Cite key evidence; use optional limitations for restrictions and actual anomalies.
Write remaining_contradiction and next_action only when needed. Gates and separate
hypothesis assessments are optional, not a required six-layer form. For a new
diagnosis, use its exact scoped plan (the bound experiment_plan, or the plan inside
the fixed curve-analysis package): when objective_key is non-null, include
objective_assessment with that exact key; when it is null, the assessment is optional
and no key may be invented. not_evaluable is valid when the evidence or task scope
cannot assess the objective. next_action is non-authoritative Worker advice.
Keep claim_allowed explicit; no omitted gate implies success. Detailed numbers,
scripts and plots belong in controlled evidence files. For a LayeredDiagnosisReport
draft, handoff may be omitted: the finalizer generates its verdict and a short
reference to payload.summary. Do not repeat the conclusion or next action there.
The sealed envelope schema includes these generated fields; domain-workspace.json
patch_contract identifies them. Other handoff explanations remain optional.
"""
GUIDANCE = """If the workspace provides analysis-start.json, read it first. It contains
bounded verbatim excerpts and exact source pointers, not a new scientific authority.
Check the current input index and read this Run's user_context originals first.
Each artifact_name is navigation-only context; tools, evidence and reports must use
the corresponding source_name. An artifact_name never grants access as a second alias.
If the index omits inputs, follow omission_source to the complete assignment input
index. Then follow the bound objective, current method and
relevant progress to their originals as needed. Do not print complete packages or
data files merely to acknowledge their bindings. Truncated excerpts are navigation,
not complete formulas or decision rules; read the referenced original before use.
Inputs with unknown schemas remain indexed without generated excerpts.
Read only the selected tool's complete assignment.json tool_contracts entry
before calling it. Restored scratch files are editable provisional work; check their
assumptions against this Run's inputs. Reuse valid saved numbers for plot-only repairs.
Historical runtime observations remain in recovery-draft, separate from this Run.
When the manifest's local_compute launcher is available, use it for analysis
scripts and preparation/check commands so failures and bounded logs remain visible.
Its --command mode runs an argv command from the workspace root and returns a short
observation with log paths; --display raw is for stdout data consumers; script mode keeps paths relative to scratch/. Direct platform calls
are outside this observation coverage. Missing telemetry never blocks submission.
"""


def view_bytes(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def append_view(view, section, item, limit):
    """Bound only presentation, retaining a pointer to the full input index."""
    view[section].append(item)
    if len(view_bytes(view)) > limit - 512:
        view[section].pop()
        view["omitted"] += 1


def _json_file(root, relative, limit=2 * 1024 * 1024):
    return json.loads(read_control_workspace_file(root, Path(relative), max_bytes=limit))


def _restore_scratch(request):
    restored, omitted = [], []
    for root in request.provisional_roots:
        # The snapshotter already owns the bounded safe-file selection. Original
        # recovery coverage remains available even when this copy is incomplete.
        for item in snapshot(root):
            path = Path(item.relative_path)
            if not item.relative_path.startswith("scratch/"):
                continue
            if path.is_relative_to(local_process_observation.RECORD_DIR):
                continue  # Never make an old latest.json the new Run's observation.
            try:
                write_control_workspace_file(request.workspace, path, item.content,
                    replace=False, mode=0o600, create_parents=True)
                restored.append(item.relative_path)
            except WorkspaceError:
                omitted.append({"relative_path": item.relative_path,
                    "reason": "working_copy_write_failed_or_conflicting"})
    coverage = None
    if request.provisional_roots:
        try:
            saved = _json_file(request.provisional_roots[-1], MANIFEST, 64 * 1024)
            coverage = {key: saved.get(key) for key in
                ("saved_count", "saved_bytes", "saved_by_scope", "omitted_count", "normalized_count", "complete")}
        except (ValueError, WorkspaceError):
            pass
    return {"scientific_evidence": False, "restored": restored, "copy_omissions": omitted,
        "coverage": coverage, "restored_count": len(restored), "copy_omitted_count": len(omitted),
        "coverage_path": "recovery-draft/" + MANIFEST if coverage is not None else None,
        "historical_runtime_path": "recovery-draft/" + str(local_process_observation.RECORD_DIR)
            if request.provisional_roots and (request.provisional_roots[-1] / local_process_observation.RECORD_DIR).is_dir() else None}


def _excerpts(value, schema):
    """Only named fields from supported schemas; unknown progress remains indexed."""
    if not isinstance(value, dict):
        return
    fields = {
        "scidiscovery.experiment-portfolio.v1": ("objective", "priority_rationale"),
        "scidiscovery.layered-diagnosis.v1": ("summary", "limitations", "remaining_contradiction", "next_action", "analysis_method", "method_changes"),
        "scidiscovery.research-objective.v1": ("statement",),
        "scidiscovery.scientific-review.v1": ("summary",),
    }.get(schema, ())
    for name in fields:
        if name in value:
            yield "/" + name, value[name]
    if schema == "scidiscovery.experiment-portfolio.v1":
        for index, proposal in enumerate(value.get("proposals", ())):
            if isinstance(proposal, dict):
                for name in ("objectives", "current_objectives", "stop_conditions"):
                    if name in proposal:
                        yield f"/proposals/{index}/{name}", proposal[name]


def _plan_index(value):
    """Exact field locations and rosters, with verbatim observable deduplication."""
    yield {"pointer": "", "fields": list(value), "proposal_count": len(value.get("proposals", ())),
        "validation_plan_count": len(value.get("validation_plans", ()))}
    observables = {}
    for index, proposal in enumerate(value.get("proposals", ())):
        if not isinstance(proposal, dict):
            continue
        pointer = f"/proposals/{index}"
        yield {"pointer": pointer, "experiment_key": proposal.get("experiment_key"),
            "fields": list(proposal), "case_count": len(proposal.get("cases", ())),
            "cases": [{"case_key": case.get("case_key"), "scientific_role": case.get("scientific_role"),
                "pointer": f"{pointer}/cases/{number}"} for number, case in enumerate(proposal.get("cases", ()))
                if isinstance(case, dict)]}
        contract = proposal.get("comparison_contract")
        if isinstance(contract, dict):
            yield {"pointer": pointer + "/comparison_contract", "fields": list(contract),
                "variable_count": len(contract.get("variables", ()))}
        for parent, content in ((pointer, proposal), (pointer + "/comparison_contract", contract)):
            if not isinstance(content, dict):
                continue
            for number, observable in enumerate(content.get("required_observables", ())):
                if isinstance(observable, str):
                    observables.setdefault(observable, []).append(f"{parent}/required_observables/{number}")
    for text, pointers in observables.items():
        yield {"observable": text[:768], "excerpt_omitted": len(text) > 768, "pointers": pointers}
    for index, validation in enumerate(value.get("validation_plans", ())):
        if isinstance(validation, dict):
            yield {"pointer": f"/validation_plans/{index}", "fields": list(validation)}


def _start_file(request, restored, limit=START_LIMIT):
    assignment = _json_file(request.workspace, "assignment.json",
        (request.workspace / "assignment.json").stat().st_size)
    instruction = assignment.get("instruction", "")
    start = {"schema_version": 1, "instruction": instruction[:2048],
        "instruction_omitted": len(instruction) > 2048,
        "instruction_source": {"relative_path": "assignment.json", "pointer": "/instruction"},
        "budget": assignment.get("budget"), "output": assignment.get("output"),
        "inputs": [], "ports": [], "plan_index": [], "excerpts": [], "omitted": 0,
        "omission_source": {"relative_path": "assignment.json", "pointer": "/inputs"},
        "full_assignment": "assignment.json", "tool_contracts": {
            name: ({"relative_path": "assignment.json", "pointer": "/tool_contracts/" + name}
                if "tool_contracts" in assignment else {"open_reply_pointer": "/tool_contracts/" + name})
            for name in assignment.get("tools", ())},
        "recovery": {key: value for key, value in restored.items() if key not in {"restored", "copy_omissions"}},
        "restored_files": [], "copy_omissions": [], "guidance": GUIDANCE}

    def append(section, item):
        append_view(start, section, item, limit)

    inputs = assignment.get("inputs", ())
    # Index all visible originals before excerpts; no current-head ranking.
    for item in inputs:
        descriptor = request.binding_descriptors.get(item["source_name"])
        append("inputs", {**{key: item[key] for key in
            ("source_name", "artifact_name", "artifact_name_usage", "port", "relative_path",
             "historical", "media_type", "source_origin") if key in item},
            "schema_id": descriptor.artifact_ref.schema_id if descriptor else None,
            "size_bytes": descriptor.size_bytes if descriptor else None})
    # Purpose is a port declaration, shared by its files; do not repeat it per curve.
    seen_ports = set()
    for item in inputs:
        if item["port"] not in seen_ports:
            append("ports", {key: item[key] for key in ("port", "description", "usage", "exposure") if key in item})
            seen_ports.add(item["port"])
    observables = []
    for item in inputs:
        descriptor = request.binding_descriptors.get(item["source_name"])
        if descriptor is None or item["port"] not in {
                "objective", "current_progress", "experiment_plan", "prior_analysis"}:
            continue
        try:
            value = _json_file(request.workspace, item["relative_path"])
        except (ValueError, OSError, WorkspaceError):
            continue  # The exact original remains indexed, never a new admission gate.
        if descriptor.artifact_ref.schema_id == "scidiscovery.experiment-portfolio.v1" and isinstance(value, dict):
            for entry in _plan_index(value):
                indexed = {"source_name": item["source_name"], **entry}
                if "observable" in entry:
                    observables.append(indexed)
                else:
                    append("plan_index", indexed)
        for pointer, content in _excerpts(value, descriptor.artifact_ref.schema_id):
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            append("excerpts", {"source_name": item["source_name"], "pointer": pointer,
                "text": text[:768], "omitted": len(text) > 768})
    for entry in observables:
        append("plan_index", entry)
    for path in restored["restored"]:
        append("restored_files", path)
    for item in restored["copy_omissions"]:
        append("copy_omissions", item)
    write_control_workspace_file(request.workspace, Path(START),
        view_bytes(start), replace=False, mode=0o400)


def materialize(request, *, start_limit=START_LIMIT):
    (request.workspace / "scratch").mkdir(exist_ok=True, mode=0o700)
    restored = _restore_scratch(request)
    _start_file(request, restored, start_limit)
    tool = "tools/local_process_observation.py"
    available = False
    if request.edit_protocol == "native":
        try:
            local_process_observation.materialize_launcher(request.workspace, analysis_policy=True)
            available = True
        except (OSError, WorkspaceError):
            pass  # Optional telemetry must not prevent the actual analysis task.
    return WorkspaceMaterializationResult(
        manifest_name=FORMAT,
        manifest={"recovery_format": FORMAT, "retain_original_on_failure": True,
            "instruction": "Recovery originals are read-only. Safe scratch files have editable copies; inspect analysis-start.json for coverage and original errors. Missing files are not completed."},
        paths={"start_here": START, "scratch": "scratch", "recovery_manifest": restored["coverage_path"],
            "local_compute": {"path": tool if available else None, "available": available,
                "example": "python tools/local_process_observation.py --timeout 240 --submission-reserve 120 analysis.py",
                "command_example": "python tools/local_process_observation.py --timeout 20 --display raw --command cat analysis-start.json",
                "script_base": "scratch", "optional": True,
                "budget": "Timeout is clipped to the Run deadline minus the selected submission reserve. Reserve is adjustable; timing is not required to submit."}},
        read_paths=(START, "scratch", "recovery-draft", "tools"),
        patch_contract={"target": "output/result.json", "schema": "scidiscovery.layered-diagnosis.v1",
            "generated_fields": {"/handoff/verdict": "/payload/overall_verdict",
                "/handoff/summary": "short reference to /payload/summary"},
            "draft_may_omit": ["/handoff"],
            "instruction": REPORT_GUIDANCE},
    )


def snapshot(root):
    files = []
    omitted = []
    omitted_count = normalized_count = scanned = total = 0

    def omit(relative, reason):
        nonlocal omitted_count
        omitted_count += 1
        if len(omitted) < 64:
            # Names, too, can carry secrets; never echo rejected content.
            safe = relative[:240]
            try:
                _validate_publication_content("name.txt", safe.encode(), "text/plain")
            except WorkspaceError:
                safe = "[redacted-name]"
            omitted.append({"relative_path": safe, "reason": reason})

    for scope in ("output", "scratch"):
        directory = root / scope
        if directory.is_symlink():
            omit(scope, "symlink"); continue
        if not directory.exists():
            continue
        for current, directories, names in os.walk(directory, followlinks=False):
            directories.sort()
            for name in list(directories):
                path = Path(current) / name
                if path.is_symlink() or name == "__pycache__":
                    omit(path.relative_to(root).as_posix(), "symlink" if path.is_symlink() else "bytecode_cache")
                    directories.remove(name)
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                scanned += 1
                if scanned > 4096:
                    omit(scope, "scan_limit"); break
                if path.suffix.lower() not in _SUFFIXES:
                    omit(relative, "unsupported_type"); continue
                if len(files) >= MAX_FILES - 1:
                    omit(relative, "file_limit"); continue
                try:
                    before = path.lstat()
                    # Reserve space for bounded coverage metadata and normalization.
                    raw = read_control_workspace_file(root, Path(relative),
                        max_bytes=MAX_BYTES - 64 * 1024 - total)
                    after = path.lstat()
                    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                            after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        omit(relative, "changed_during_copy"); continue
                    normalized = path.suffix.lower() == ".log"
                    if normalized and not raw.startswith(b"[normalized log copy; original retained]"):
                        raw = local_process_observation.normalize_log(raw, root)
                    media = _media_type(relative)
                    if media == "application/octet-stream":
                        media = "text/plain"
                    _validate_publication_content(relative, raw, media)
                    if total + len(raw) > MAX_BYTES - 64 * 1024:
                        omit(relative, "byte_limit"); continue
                except (WorkspaceError, OSError, ValueError):
                    omit(relative, "unsafe_unreadable_or_oversized"); continue
                files.append(WorkspaceSnapshotFile(relative, media, raw))
                total += len(raw)
                normalized_count += int(normalized)
            if scanned > 4096:
                break
    coverage = {"format": FORMAT, "scope": ["output", "scratch"],
        "saved_count": len(files), "saved_bytes": total,
        "saved_by_scope": {scope: sum(f.relative_path.startswith(scope + "/") for f in files)
            for scope in ("output", "scratch")},
        "omitted_count": omitted_count, "omitted": omitted,
        "normalized_count": normalized_count, "writers_stopped": "unknown",
        "original_retained": True, "complete": False}
    files.append(WorkspaceSnapshotFile(MANIFEST, "application/json",
        (json.dumps(coverage, sort_keys=True) + "\n").encode()))
    return tuple(files)


WORKSPACE = WorkspaceContract()
MATERIALIZER = CallableComponent("workspace_materializer", materialize)
SNAPSHOTTER = CallableComponent("workspace_snapshotter", snapshot)
