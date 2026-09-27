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


def materialize(request):
    (request.workspace / "scratch").mkdir(exist_ok=True, mode=0o700)
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
            "instruction": "Recovery is a read-only provisional subset. Copy needed files to new scratch; check new bound inputs. Missing files remain unavailable, not completed."},
        paths={"scratch": "scratch", "recovery_manifest": "recovery-draft/" + MANIFEST,
            "local_compute": {"path": tool if available else None, "available": available,
                "example": "python tools/local_process_observation.py --timeout 240 --submission-reserve 120 analysis.py",
                "script_base": "scratch", "optional": True,
                "budget": "Timeout is clipped to the Run deadline minus the selected submission reserve. Reserve is adjustable; timing is not required to submit."}},
        read_paths=("scratch", "recovery-draft", "tools"),
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
