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
GUIDANCE = """If the workspace provides analysis-start.json, read it first. It contains
bounded verbatim excerpts and exact source pointers, not a new scientific authority.
Follow the bound objective, current method and relevant progress to their originals
as needed. Read only the selected tool's complete assignment.json tool_contracts entry
before calling it. Restored scratch files are editable provisional work; check their
assumptions against this Run's inputs. Reuse valid saved numbers for plot-only repairs.
Historical runtime observations remain in recovery-draft, separate from this Run.
When the manifest's local_compute launcher is available, use it for analysis
scripts and preparation/check commands so failures and bounded logs remain visible.
Its --command mode runs an argv command from the workspace root and returns bounded
stdout/stderr; script mode keeps paths relative to scratch/. Direct platform calls
are outside this observation coverage. Missing telemetry never blocks submission.
"""


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
        "scidiscovery.layered-diagnosis.v1": ("summary", "remaining_contradiction", "next_action", "analysis_method", "method_changes"),
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


def _start_file(request, restored):
    assignment = _json_file(request.workspace, "assignment.json",
        (request.workspace / "assignment.json").stat().st_size)
    instruction = assignment.get("instruction", "")
    start = {"schema_version": 1, "instruction": instruction[:2048],
        "instruction_omitted": len(instruction) > 2048,
        "instruction_source": {"relative_path": "assignment.json", "pointer": "/instruction"},
        "budget": assignment.get("budget"), "output": assignment.get("output"),
        "inputs": [], "excerpts": [], "omitted": 0,
        "full_assignment": "assignment.json", "tool_contracts": {
            name: ({"relative_path": "assignment.json", "pointer": "/tool_contracts/" + name}
                if "tool_contracts" in assignment else {"open_reply_pointer": "/tool_contracts/" + name})
            for name in assignment.get("tools", ())},
        "recovery": {key: value for key, value in restored.items() if key not in {"restored", "copy_omissions"}},
        "restored_files": [], "copy_omissions": [], "guidance": GUIDANCE}

    def append(section, item):
        start[section].append(item)
        if len(json.dumps(start, ensure_ascii=False).encode()) > START_LIMIT - 512:
            start[section].pop()
            start["omitted"] += 1

    inputs = assignment.get("inputs", ())
    # Index all visible originals before excerpts; no current-head ranking.
    for item in inputs:
        append("inputs", {key: item[key] for key in
            ("source_name", "port", "relative_path", "historical") if key in item})
    for item in inputs:
        descriptor = request.binding_descriptors.get(item["source_name"])
        if descriptor is None or item["port"] not in {
                "objective", "current_progress", "experiment_plan", "prior_analysis"}:
            continue
        try:
            value = _json_file(request.workspace, item["relative_path"])
        except (ValueError, OSError, WorkspaceError):
            continue  # The exact original remains indexed, never a new admission gate.
        for pointer, content in _excerpts(value, descriptor.artifact_ref.schema_id):
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            append("excerpts", {"source_name": item["source_name"], "pointer": pointer,
                "text": text[:768], "omitted": len(text) > 768})
    for path in restored["restored"]:
        append("restored_files", path)
    for item in restored["copy_omissions"]:
        append("copy_omissions", item)
    write_control_workspace_file(request.workspace, Path(START),
        (json.dumps(start, ensure_ascii=False) + "\n").encode(), replace=False, mode=0o400)


def materialize(request):
    (request.workspace / "scratch").mkdir(exist_ok=True, mode=0o700)
    restored = _restore_scratch(request)
    _start_file(request, restored)
    tool = "tools/local_process_observation.py"
    available = False
    if request.edit_protocol == "native":
        try:
            write_control_workspace_file(request.workspace, Path(tool),
                Path(local_process_observation.__file__).read_bytes(), replace=False, mode=0o400,
                create_parents=True)
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
                "command_example": "python tools/local_process_observation.py --timeout 20 --command cat analysis-start.json",
                "script_base": "scratch", "optional": True,
                "budget": "Timeout is clipped to the Run deadline minus the selected submission reserve. Reserve is adjustable; timing is not required to submit."}},
        read_paths=(START, "scratch", "recovery-draft", "tools"),
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
