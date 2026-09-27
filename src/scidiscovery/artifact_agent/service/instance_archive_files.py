"""Exact local file ownership, verified copy, and reversible active cleanup."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import nullcontext
from pathlib import Path

from .instance_archive_records import ArchiveError, exact_refs, json_value, readonly

MAX_FILES = 50000
_DIGEST = re.compile(r"[0-9a-f]{64}")
RECOVERY_SCAN_BYTES = 64 * 1024


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value) or value in {".", ".."}:
        raise ArchiveError("invalid storage identity")
    return value


def check_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ArchiveError("symbolic links are unsupported in managed archive paths")
    return path


def hash_file(path):
    check_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ArchiveError("archive source is not a regular file")
        sha = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
        after = os.fstat(fd)
        if (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ArchiveError("archive file changed while hashing")
        return {"size_bytes": info.st_size, "sha256": sha.hexdigest(), "mode": stat.S_IMODE(info.st_mode),
                "source_stat": [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns]}
    finally:
        os.close(fd)


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_json(path, value):
    from .instance_archive_records import canonical
    check_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    fsync_directory(path.parent)


def roots(runtime):
    state = Path(runtime.state_root)
    backend = getattr(runtime, "local_backend", None)
    local = Path(backend.root) if backend is not None else Path(runtime.project_root) / ".scidiscovery-runs"
    return {"objects": Path(runtime.artifacts.cas.root), "workspaces/local": local,
            "workspaces/hardened": state / "hardened-runs", "executions/exchange": state / "execution-exchange",
            "executions/results": state / "executor-results", "diagnostics": state / "engineering-diagnostics"}


def recovery_digests(row):
    found = []
    if row.get("recovery_candidate_digest"):
        found.append(row["recovery_candidate_digest"])
    if row.get("recovery_draft_json"):
        value = json_value(row["recovery_draft_json"], "Run recovery")
        if not isinstance(value, dict):
            raise ArchiveError("invalid controlled recovery metadata")
        for key in ("draft_digest", "complete_snapshot_digest"):
            if value.get(key):
                found.append(value[key])
    if any(not isinstance(item, str) or not _DIGEST.fullmatch(item) for item in found):
        raise ArchiveError("invalid controlled recovery digest")
    return set(found)


def retained_recovery_digests(database_path, instance_id, backend, candidates):
    """Stream bounded control carriers; uncertainty preserves the whole tree."""
    candidates, retained = set(candidates), set()
    if not candidates:
        return retained, False
    query = """SELECT
        CASE WHEN length(CAST(recovery_draft_json AS BLOB))<=? THEN recovery_draft_json END AS recovery_draft_json,
        CASE WHEN length(recovery_candidate_digest)<=64 THEN recovery_candidate_digest END AS recovery_candidate_digest,
        COALESCE(length(CAST(recovery_draft_json AS BLOB))>?,0)
          OR COALESCE(length(recovery_candidate_digest)>64,0) AS scan_incomplete
        FROM runs WHERE instance_id<>? AND backend_id=?"""
    with readonly(database_path) as connection:
        for row in connection.execute(query, (RECOVERY_SCAN_BYTES, RECOVERY_SCAN_BYTES, instance_id, backend)):
            if row["scan_incomplete"]:
                return candidates, True
            try:
                retained.update(recovery_digests(dict(row)) & candidates)
            except (ArchiveError, ValueError, UnicodeError):
                return candidates, True
    return retained, False


def run_locations(runtime, row):
    locations = []
    key = {"local_trusted": "workspaces/local", "hardened_worker": "workspaces/hardened"}.get(row["backend_id"])
    if key is None:
        raise ArchiveError("unsupported Run workspace backend: " + row["backend_id"])
    root = roots(runtime)[key]
    binding = root / ".bindings" / hashlib.sha256(row["run_id"].encode("ascii")).hexdigest()
    if binding.exists():
        check_path(binding)
        if binding.stat().st_size > 128:
            raise ArchiveError("workspace binding size is invalid")
        name = binding.read_text("ascii").strip()
        if not re.fullmatch(r"workspace_[0-9a-f]{32}", name):
            raise ArchiveError("workspace binding identity is invalid")
        locations.extend(root / sub / name for sub in ("workspaces", "quarantine"))
    locations.extend(root / "recovery" / value for value in sorted(recovery_digests(row)))
    return key, binding, locations


def workspace_refs(runtime, rows):
    result = []
    for row in rows:
        _, _, locations = run_locations(runtime, row)
        for directory in locations:
            for name in ("tool-evidence.json", "output/tool-evidence.json", "analysis-recovery.json"):
                path = directory / name
                if path.exists():
                    check_path(path)
                    if path.stat().st_size > 16 * 1024 * 1024:
                        raise ArchiveError("workspace control manifest exceeds reference scan budget")
                    result.extend(exact_refs(json_value(path.read_bytes(), "workspace control manifest")))
    return result


class Files:
    def __init__(self, runtime, records, selected, instance_id):
        self.runtime, self.records, self.selected, self.instance_id = runtime, records, selected, instance_id
        self.roots = roots(runtime)
        self.entries, self.gaps, self.unowned, self.unsupported = {}, [], [], []

    def add(self, root_key, path, *, shared=False, restore=True, expected=None, missing=True):
        root, path = check_path(self.roots[root_key]), check_path(path)
        relative = path.relative_to(root).as_posix()
        if relative == ".":
            raise ArchiveError("whole shared storage roots cannot be instance owned")
        archive = root_key + "/" + relative
        if not path.exists():
            if missing:
                self.gaps.append({"code": "historical_file_missing", "path": archive, **(expected or {})})
            return
        info = path.lstat()
        kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
        if expected and kind != "file":
            raise ArchiveError("a managed file descriptor points to a directory")
        entry = {"root": root_key, "relative_path": relative, "archive_path": archive,
                 "kind": kind, "mode": stat.S_IMODE(info.st_mode), "shared": shared, "restore": restore}
        if kind == "file":
            entry.update(hash_file(path))
            if expected and any(entry.get(key) != value for key, value in expected.items()):
                raise ArchiveError("managed file content differs from exact descriptor: " + archive)
        previous = self.entries.get(archive)
        if previous:
            entry["shared"] |= previous["shared"]
            entry["restore"] &= previous["restore"]
        self.entries[archive] = entry
        if len(self.entries) > MAX_FILES:
            raise ArchiveError("file inventory exceeds bounded file budget")
        if kind == "directory":
            for child in path.iterdir():
                history = (root_key == "executions/exchange" and child.name in {"request.json", "active.lock"}
                           and child.parent.name == "collection") or (root_key == "workspaces/hardened" and "transport-locks" in child.parts)
                self.add(root_key, child, shared=shared or child.name.endswith(".lock"), restore=restore and not history)

    def collect(self):
        for row in self.selected["databases"]["artifacts"]["tables"]["artifact_envelopes"]:
            sha = row["payload_sha256"]
            self.add("objects", self.runtime.artifacts.cas.path_for(sha), shared=sha in self.selected["shared_digests"],
                     expected={"sha256": sha, "size_bytes": row["size_bytes"]})
        target_runs = self.selected["databases"]["runs"]["tables"]["runs"]
        target_recovery = {}
        for row in target_runs:
            target_recovery.setdefault(row["backend_id"], set()).update(recovery_digests(row))
        retained_recovery = {}
        for backend, candidates in target_recovery.items():
            retained_recovery[backend], incomplete = retained_recovery_digests(
                self.records.paths["runs"], self.instance_id, backend, candidates)
            if incomplete:
                self.gaps.append({"code": "retained_recovery_scan_incomplete", "backend": backend,
                                  "retention": "all_selected_recovery_trees_preserved"})
        for row in target_runs:
            key, binding, locations = run_locations(self.runtime, row)
            self.add(key, binding, missing=row["state"] != "queued")
            retained = retained_recovery[row["backend_id"]]
            for directory in locations:
                recovery = directory.parent.name == "recovery"
                self.add(key, directory, shared=recovery and directory.name in retained,
                         missing=recovery)
                if recovery and directory.parent.exists():
                    for stage in sorted(directory.parent.glob(".staging_" + directory.name + "_*")):
                        self.add(key, stage, shared=directory.name in retained)
            if binding.exists() and not any(path.exists() for path in locations if path.parent.name != "recovery"):
                self.gaps.append({"code": "original_workspace_historically_absent", "run_id": row["run_id"]})
            if key == "workspaces/hardened":
                self.add(key, self.roots[key] / "transport-locks" / (hashlib.sha256(row["run_id"].encode()).hexdigest() + ".lock"),
                         shared=True, restore=False, missing=False)
        executions = self.selected["databases"].get("executions", {}).get("tables", {}).get("executions", [])
        target_external = {row["external_run_id"] for row in executions if row.get("external_run_id")}
        external_others = {row["external_run_id"] for row in self.records.rows("executions", "executions", columns=("execution_id", "external_run_id"))
                           if row["execution_id"] not in self.selected["execution_ids"] and row.get("external_run_id") in target_external}
        for row in executions:
            execution_id = safe_id(row["execution_id"])
            exchange = self.roots["executions/exchange"] / execution_id
            self.add("executions/exchange", exchange, missing=row["state"] not in {"created"})
            if row.get("external_run_id"):
                external = safe_id(row["external_run_id"])
                for sub in ("runs", "inspection"):
                    self.add("executions/results", self.roots["executions/results"] / sub / external,
                             shared=external in external_others, missing=False)
            if exchange.exists():
                for job in sorted((exchange / "prepared").glob("*/job.json")):
                    marker = self.roots["executions/results"] / "submissions" / (hash_file(job)["sha256"] + ".json")
                    if marker.exists():
                        value = json_value(marker.read_bytes(), "submission marker")
                        if not isinstance(value.get("remote_submission"), dict):
                            raise ArchiveError("submission marker has no controlled remote descriptor")
                        # Content-addressed markers may be referenced by an
                        # unowned exchange. Keep their active copy conservatively.
                        self.add("executions/results", marker, shared=True)
                output = exchange / "collection" / "outputs.json"
                if output.exists():
                    self._descriptors(json_value(output.read_bytes(), "collection outputs"))
                if row["state"] not in {"collected", "abandoned"}:
                    self.gaps.append({"code": "execution_outputs_not_collected", "execution_id": execution_id})
        diagnostics = self.roots["diagnostics"]
        diagnostic_scopes = {"instance:" + self.instance_id} | {"execution:" + value for value in self.selected["execution_ids"]}
        if diagnostics.exists():
            for path in diagnostics.glob("diag_*.json"):
                try:
                    check_path(path)
                    if path.stat().st_size > 512 * 1024:
                        raise ValueError("oversized diagnostic")
                    value = json.loads(path.read_bytes())
                    if not isinstance(value, dict) or not isinstance(value.get("scope"), str):
                        raise ValueError("diagnostic scope is unavailable")
                    if value.get("scope") in diagnostic_scopes:
                        self.add("diagnostics", path)
                        sections = value.get("sections", ())
                        if not isinstance(sections, (list, tuple)) or any(not isinstance(section, str) for section in sections):
                            self.gaps.append({"code": "diagnostic_sections_unavailable", "path": "diagnostics/" + path.name})
                            sections = ()
                        for section in ("stdout", "stderr"):
                            self.add("diagnostics", path.with_suffix("." + section), missing=section in sections)
                except (ValueError, UnicodeError):
                    if len(self.unowned) < 100:
                        self.unowned.append({"path": "diagnostics/" + path.name, "reason": "diagnostic_scope_unavailable"})
        debug = Path(self.runtime.state_root) / "local-tcad-debug"
        if debug.exists() and any(debug.iterdir()):
            self.unsupported.append({"code": "local_debug_ownership_and_writer_unknown", "path": "local-tcad-debug"})
        # System-wide residual trees are outside this exact instance selection.
        # Do not recursively inventory other instances merely to archive a small
        # target. Their unexpanded scope is explicit, never a fabricated zero.
        for key, root in self.roots.items():
            if not root.exists():
                continue
            self.unowned.append({"path": key, "reason": "unselected_remainder_retained", "expanded": False,
                                 "files": None, "bytes": None})
        return {"roots": {key: str(value) for key, value in self.roots.items()},
                "files": sorted(self.entries.values(), key=lambda item: item["archive_path"]),
                "gaps": self.gaps, "unowned": self.unowned, "unsupported": self.unsupported}

    def _descriptors(self, value):
        if isinstance(value, dict):
            if {"local_path", "sha256", "size_bytes"} <= value.keys():
                path = Path(value["local_path"])
                if path.is_absolute() and path.is_relative_to(self.roots["executions/results"]):
                    archive_path = "executions/results/" + path.relative_to(self.roots["executions/results"]).as_posix()
                    prior = self.entries.get(archive_path)
                    self.add("executions/results", path, shared=prior["shared"] if prior else True,
                             expected={"sha256": value["sha256"], "size_bytes": value["size_bytes"]})
                elif path.is_absolute() and path.is_relative_to(self.roots["executions/exchange"]):
                    # Whole exact execution exchanges are already selected; a
                    # descriptor cannot grant another execution's directory.
                    relative = path.relative_to(self.roots["executions/exchange"])
                    if relative.parts[0] not in self.selected["execution_ids"]:
                        self.unsupported.append({"code": "cross_execution_local_descriptor"})
                else:
                    self.unsupported.append({"code": "local_descriptor_outside_configured_managed_root"})
            for item in value.values():
                self._descriptors(item)
        elif isinstance(value, list):
            for item in value:
                self._descriptors(item)


def copy_verified(source, destination, entry):
    """Copy before unlink, including on the same filesystem, to preserve drafts."""
    check_path(source)
    check_path(destination)
    if entry["kind"] == "directory":
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        return
    if destination.exists():
        actual = hash_file(destination)
        if any(actual[key] != entry[key] for key in ("sha256", "size_bytes", "mode")):
            raise ArchiveError("destination file collision")
        return
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = destination.with_name(destination.name + ".archive-copy")
    parent_mode = stat.S_IMODE(destination.parent.stat().st_mode)
    descriptor = None
    try:
        os.chmod(destination.parent, parent_mode | 0o700)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as output, open(source, "rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                output.write(chunk)
            output.flush()
            os.fchmod(descriptor, entry["mode"])
            os.fsync(descriptor)
        actual = hash_file(temporary)
        if any(actual[key] != entry[key] for key in ("sha256", "size_bytes")):
            raise ArchiveError("copy verification failed")
        # CAS may acquire a new owner while this instance is restoring. Publish
        # without replacement, matching the CAS store's own immutable protocol.
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            actual = hash_file(destination)
            if any(actual[key] != entry[key] for key in ("sha256", "size_bytes", "mode")):
                raise ArchiveError("destination appeared with different content or permissions")
        fsync_directory(destination.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        finally:
            os.chmod(destination.parent, parent_mode)


def verify_tree(package, entries):
    for entry in entries:
        path = check_path(package / entry["archive_path"])
        if entry["kind"] == "directory":
            if not path.is_dir() or stat.S_IMODE(path.stat().st_mode) != entry["mode"]:
                raise ArchiveError("archive directory is missing or its permissions changed")
        else:
            actual = hash_file(path)
            if any(actual[key] != entry[key] for key in ("sha256", "size_bytes", "mode")):
                raise ArchiveError("archive file verification failed: " + entry["archive_path"])


def finish_permissions(package, entries):
    for entry in reversed(entries):
        if entry["kind"] == "directory":
            path = package / entry["archive_path"]
            os.chmod(path, entry["mode"])
            fsync_directory(path)


def recovery_trees(entries):
    groups, roots = {}, {}
    for entry in entries:
        parts = Path(entry["relative_path"]).parts
        if (entry["root"] not in {"workspaces/local", "workspaces/hardened"}
                or len(parts) < 2 or parts[0] != "recovery" or not _DIGEST.fullmatch(parts[1])):
            continue
        key = (entry["root"], parts[1])
        groups.setdefault(key, []).append(entry)
        if len(parts) == 2 and entry["kind"] == "directory":
            roots[key] = entry
    for key, root_entry in roots.items():
        prefix = root_entry["archive_path"]
        selected = groups[key]
        relative = [{**entry, "archive_path": "." if entry["archive_path"] == prefix else entry["archive_path"][len(prefix) + 1:]}
                    for entry in selected]
        yield root_entry, selected, relative


def _discard_restore_stage(stage):
    """Discard only a derived private stage selected by its exact restore job."""
    check_path(stage)
    if not stage.exists():
        return
    if not stage.is_dir():
        raise ArchiveError("private restore staging root is not a directory")
    directories, files = [stage], []
    for current, child_dirs, child_files in os.walk(stage, followlinks=False):
        for name in child_dirs + child_files:
            path = check_path(Path(current) / name)
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                directories.append(path)
            elif stat.S_ISREG(mode):
                files.append(path)
            else:
                raise ArchiveError("private restore stage contains a special file")
            if len(directories) + len(files) > MAX_FILES * 2 + 1:
                raise ArchiveError("private restore stage exceeds its derived file budget")
    # A hard exit can leave a partial *.archive-copy. It is disposable only in
    # this exact private stage; the complete verified archive remains intact.
    for path in directories:
        os.chmod(path, stat.S_IMODE(path.stat().st_mode) | 0o700)
    for path in files:
        path.unlink()
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        path.rmdir()
    fsync_directory(stage.parent)


def discard_restore_stages(entries, root_map, job_id):
    for root_entry, _, _ in recovery_trees(entries):
        destination = check_path(Path(root_map[root_entry["root"]]) / root_entry["relative_path"])
        _discard_restore_stage(destination.parent / (".staging_" + destination.name + "_" + safe_id(job_id)))


def verify_tree_inventory(directory, entries):
    expected, actual = {entry["archive_path"] for entry in entries}, {"."}
    if not check_path(directory).is_dir():
        raise ArchiveError("published recovery root is not a directory")
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            path = check_path(Path(current) / name)
            actual.add(path.relative_to(directory).as_posix())
            if len(actual) > len(expected):
                raise ArchiveError("published recovery tree differs from the complete archive")
    if actual != expected:
        raise ArchiveError("published recovery tree differs from the complete archive")


def restore_recovery_trees(package, entries, root_map, *, job_id, publish_guard, fault=lambda point: None):
    """Publish shared immutable recovery trees only after complete verification.

    A published digest directory is never filled in place: another Run can reuse
    it as soon as it exists. Private staging lives on the destination filesystem
    and follows the backend's existing staging/atomic-directory protocol.
    """
    handled = set()
    for root_entry, selected, relative_entries in recovery_trees(entries):
        parts = Path(root_entry["relative_path"]).parts
        handled.update(entry["archive_path"] for entry in selected)
        destination = check_path(Path(root_map[root_entry["root"]]) / root_entry["relative_path"])
        stage = check_path(destination.parent / (".staging_" + parts[1] + "_" + safe_id(job_id)))

        def verify_exact(directory):
            verify_tree(directory, relative_entries)
            verify_tree_inventory(directory, relative_entries)

        if destination.exists():
            verify_exact(destination)
            _discard_restore_stage(stage)
            continue
        # A hard exit after a child's atomic link but before temporary unlink
        # can leave both names. Rebuild this exact derived stage from verified
        # archive bytes; never interpret filename suffixes as ownership.
        _discard_restore_stage(stage)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        for source_entry, relative_entry in zip(selected, relative_entries):
            copy_verified(package / source_entry["archive_path"], stage / relative_entry["archive_path"], relative_entry)
            fault("during_recovery_restore_copy")
        finish_permissions(stage, relative_entries)
        verify_exact(stage)
        for current, _, _ in os.walk(stage, topdown=False):
            fsync_directory(Path(current))
        fsync_directory(stage.parent)
        fault("before_recovery_restore_publish")
        with publish_guard():
            if not destination.exists():
                os.rename(stage, destination)
                fsync_directory(destination.parent)
        # A concurrently finalized identical digest wins publication. It is
        # immutable; verify and reuse its whole tree without writing any child.
        verify_exact(destination)
        _discard_restore_stage(stage)
    return handled


def cleanup(entries, root_map, *, unlink_guard=None):
    released = 0
    for entry in reversed(entries):
        if entry["shared"]:
            continue
        path = check_path(Path(root_map[entry["root"]]) / entry["relative_path"])
        if not path.exists():
            continue
        if entry["kind"] == "directory":
            # A preserved lock or an unexpected file keeps this directory. Never
            # recursively delete an unenumerated active file.
            with (unlink_guard(entry, path) if unlink_guard else nullcontext(True)) as allowed:
                if not allowed:
                    entry["shared"] = True
                    continue
                prefix = entry["archive_path"] + "/"
                if any(child["shared"] and child["archive_path"].startswith(prefix) for child in entries):
                    continue
                parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
                try:
                    os.chmod(path.parent, parent_mode | 0o700)
                    path.rmdir()
                    fsync_directory(path.parent)
                except OSError as error:
                    raise ArchiveError("unpreviewed active files prevent archive cleanup") from error
                finally:
                    os.chmod(path.parent, parent_mode)
        else:
            actual = hash_file(path)
            if any(actual[key] != entry[key] for key in ("sha256", "size_bytes", "mode")):
                raise ArchiveError("active source changed before cleanup")
            before = path.stat()
            with (unlink_guard(entry, path) if unlink_guard else nullcontext(True)) as allowed:
                if not allowed:
                    entry["shared"] = True
                    continue
                after = path.stat()
                if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ArchiveError("active source changed at cleanup switch")
                parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
                try:
                    os.chmod(path.parent, parent_mode | 0o700)
                    path.unlink()
                    fsync_directory(path.parent)
                finally:
                    os.chmod(path.parent, parent_mode)
            released += entry["size_bytes"]
    return released
