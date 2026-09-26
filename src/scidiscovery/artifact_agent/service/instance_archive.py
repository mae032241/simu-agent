"""Confirmed whole-instance archive and restore with durable maintenance recovery.

The journal is storage authority only. No operation admission, scientific
validation, execution replay, process termination, or session selection occurs.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from .instance_archive_files import (Files, check_path, cleanup, copy_verified, discard_restore_stages, durable_json,
    finish_permissions, fsync_directory, hash_file, recovery_trees, retained_recovery_digests, restore_recovery_trees, roots, safe_id, verify_tree, verify_tree_inventory)
from .instance_archive_records import (ArchiveError, Records, ReadTicket, build_database, canonical, decode,
    digest, encode, quote, readonly, row_where, transfer_records, attached, schema,
    execution_settings_restore_view, execution_settings_tombstone, RETAINED_EXECUTION_TABLES)
from .instance_maintenance import InstanceMaintenance, InstanceMaintenanceBusy, backend_writer_guards


class InstanceArchive:
    def __init__(self, runtime, *, gate=None, plugin_configs=None):
        self.runtime = runtime
        self.project_root = check_path(runtime.project_root)
        self.state_root = check_path(runtime.state_root)
        self.root = self.project_root / ".scidiscovery-archive" / "instances"
        self.maintenance_root = self.state_root / "maintenance" / "archive"
        self.gate = gate or InstanceMaintenance(self.state_root, maintenance=runtime.maintenance)
        self.plugin_configs = dict(plugin_configs or {})
        self._fault = lambda point: None  # deterministic isolated fault injection

    def _index_path(self, instance_id):
        return self.maintenance_root / "index" / (safe_id(instance_id) + ".json")

    def _index(self, instance_id):
        path = check_path(self._index_path(instance_id))
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        if value.get("instance_id") != instance_id or value.get("version") != 1:
            raise ArchiveError("maintenance index identity differs")
        return value

    def _save(self, index):
        durable_json(self._index_path(index["instance_id"]), index)

    def _job_root(self, index):
        return check_path(self.maintenance_root / "jobs" / safe_id(index["job_id"]))

    @contextmanager
    def _job_lock(self, instance_id):
        directory = check_path(self.maintenance_root / "locks")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(directory / (safe_id(instance_id) + ".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ArchiveError("this instance already has an active maintenance action") from error
            yield
        finally:
            os.close(descriptor)

    def _snapshot(self, instance_id):
        safe_id(instance_id)
        records = Records(self.runtime)
        selected = records.select(instance_id)
        instance = selected["databases"]["scheduler"]["tables"]["scheduler_instances"]
        if len(instance) != 1:
            raise ArchiveError("research instance does not exist")
        files = Files(self.runtime, records, selected, instance_id).collect()
        files["unsupported"].extend(self._plugin_scope(selected))
        return {"version": 1, "instance_id": instance_id, "project_root": str(self.project_root),
                "state_root": str(self.state_root), "backend_id": self.runtime.runs.backend.backend_id,
                "backend_version": self.runtime.runs.backend.backend_version,
                "database_paths": {key: str(path) for key, path in records.paths.items()},
                **selected, **{key: value for key, value in files.items() if key != "gaps"},
                "gaps": selected["gaps"] + files["gaps"]}

    def _plugin_scope(self, selected):
        executions = selected["databases"].get("executions", {}).get("tables", {}).get("executions", [])
        if not any(row["executor"] == "tcad" for row in executions):
            return []
        candidates = []
        for plugin, path in self.plugin_configs.items():
            if "tcad" in plugin:
                source = check_path(path)
                if source.stat().st_size > 1024 * 1024:
                    raise ArchiveError("plugin configuration exceeds bounded read")
                candidates.append(json.loads(source.read_bytes()))
        if len(candidates) != 1:
            return [{"code": "tcad_local_root_configuration_unavailable"}]
        config = candidates[0]
        if config.get("transport") != "command":
            return [{"code": "tcad_daemon_local_root_and_writer_not_managed"}]
        source = check_path(config["command_config_path"])
        if source.stat().st_size > 1024 * 1024:
            raise ArchiveError("command configuration exceeds bounded read")
        command = json.loads(source.read_bytes())
        configured = command.get("environment", {}).get("SCIDISCOVERY_TCAD_RESULT_ROOT", "/var/lib/scidiscovery/transport-results")
        if Path(configured).absolute() != self.state_root / "executor-results":
            return [{"code": "tcad_transport_result_root_differs_from_managed_root"}]
        return []

    def _counts(self, snapshot):
        files = [item for item in snapshot["files"] if item["kind"] == "file"]
        total = sum(item["size_bytes"] for item in files)
        shared = sum(item["size_bytes"] for item in files if item["shared"])
        record_bytes = len(canonical(encode(snapshot["databases"])))
        return {"records": sum(len(rows) for data in snapshot["databases"].values() for rows in data["tables"].values()),
                "files": len(files), "bytes": total, "exclusive_bytes": total - shared,
                "shared_bytes": shared, "temporary_bytes": total + record_bytes * 2 + 1024 * 1024,
                "missing_files": len([item for item in snapshot["gaps"] if "missing" in item["code"] or "absent" in item["code"]])}

    @staticmethod
    def _fingerprint(snapshot):
        value = encode(snapshot)
        # The global activity allocator is retained metadata. Another instance's
        # event must not invalidate this target's confirmed immutable selection.
        value["databases"]["runs"]["tables"].pop("run_activity_sequence", None)
        return digest(value)

    def _require_paused_clients(self, instance_id):
        if self.runtime.scheduler_bindings.active_clients(instance_id=instance_id):
            raise InstanceMaintenanceBusy("请先在工作台暂停关联科研会话，再归档实例。",
                details=({"kind": "research_client", "reason": "client_scheduling_enabled",
                    "message": "关联科研会话仍允许调度；请先在首页的科研会话管理中暂停，再归档。"},))

    def preview(self, instance_id):
        busy, unsupported = [], []
        try:
            with self.runtime.maintenance.shared(), ReadTicket(self.runtime) as ticket:
                index = self._index(instance_id)
                if index and (index["storage_state"] not in {"active", "restored"} or index.get("can_resume")):
                    raise ArchiveError("instance already has a durable archive maintenance record")
                if self.gate.status(instance_id) is not None:
                    raise ArchiveError("instance maintenance has not been finalized")
                snapshot = self._snapshot(instance_id)
                try:
                    self._require_paused_clients(instance_id)
                    with backend_writer_guards(self.runtime, snapshot["run_ids"], snapshot["execution_ids"]):
                        pass
                except InstanceMaintenanceBusy as error:
                    busy.extend(error.details or ({"code": str(error)},))
                ticket.validate()
            counts = self._counts(snapshot)
            anchor = self.root if self.root.exists() else self.project_root
            if shutil.disk_usage(anchor).free < counts["temporary_bytes"]:
                unsupported.append({"code": "insufficient_archive_disk_space"})
            unsupported.extend(snapshot["unsupported"])
            return {"instance_id": instance_id, "action": "archive", "instance": snapshot["databases"]["scheduler"]["tables"]["scheduler_instances"][0],
                    "fingerprint": self._fingerprint(snapshot), "ready": not busy and not unsupported,
                    "busy": busy, "gaps": snapshot["gaps"], "unsupported": unsupported, "unowned": snapshot["unowned"],
                    "counts": counts, "archive_path": str(self.root / instance_id),
                    "files": [{key: entry[key] for key in ("archive_path", "kind", "shared")} for entry in snapshot["files"]],
                    "remote_scope": "remote VM bytes remain at their original location"}
        except (ArchiveError, OSError, ValueError, sqlite3.Error) as error:
            return {"instance_id": instance_id, "action": "archive", "fingerprint": None, "ready": False,
                    "busy": busy, "gaps": [], "unsupported": [{"code": "inventory_unavailable", "detail": str(error)}],
                    "unowned": [], "counts": {}, "archive_path": str(self.root / safe_id(instance_id))}

    def status(self, instance_id):
        index = self._index(instance_id)
        if index is None:
            instance = self.runtime.scheduler_bindings.get_instance(instance_id=instance_id)
            from dataclasses import asdict
            return {"instance_id": instance_id, "instance": asdict(instance), "storage_state": "active", "phase": "idle",
                    "browser_epoch": 0.0, "fingerprint": None, "archive_path": str(self.root / instance_id),
                    "can_resume": False, "can_rollback": False, "archived_readable": False}
        result = {key: index[key] for key in ("instance_id", "instance", "storage_state", "phase", "browser_epoch", "fingerprint",
                    "archive_path", "can_resume", "can_rollback", "error", "counts", "released_bytes", "restore_gaps") if key in index}
        result["archived_readable"] = bool(index.get("manifest_sha256") and index["storage_state"] not in {"active", "restored"})
        if result["archived_readable"]:
            self._manifest(index)
        return result

    def owner(self, namespace, object_id):
        if namespace not in {"artifact", "run", "approval", "execution"} or not isinstance(object_id, str):
            raise ArchiveError("invalid archive owner lookup")
        directory = check_path(self.maintenance_root / "index")
        if not directory.exists():
            return None
        owners = set()
        paths = sorted(directory.glob("*.json"))
        if len(paths) > 10000:
            raise ArchiveError("archive ownership index read limit")
        for path in paths:
            index = self._index(path.stem)
            if index["storage_state"] in {"active", "restored"}:
                continue
            if object_id in index.get("owners", {}).get(namespace, ()):
                if index.get("manifest_sha256"):
                    self._manifest(index)
                owners.add(index["instance_id"])
        if len(owners) > 1:
            raise ArchiveError("archived object has multiple instance owners")
        return next(iter(owners), None)

    def archive(self, instance_id, fingerprint):
        with self._job_lock(instance_id), ReadTicket(self.runtime) as ticket:
            with self.runtime.maintenance.shared():
                snapshot = self._snapshot(instance_id)
            ticket.validate()
            if not isinstance(fingerprint, str) or self._fingerprint(snapshot) != fingerprint:
                raise ArchiveError("archive preview changed; inspect a new preview")
            if snapshot["unsupported"]:
                raise ArchiveError("archive has unsupported ownership or writer scope")
            prior = self._index(instance_id)
            if prior and (prior["storage_state"] not in {"active", "restored"} or prior.get("can_resume")):
                raise ArchiveError("instance already has a maintenance action")
            job = "archive_" + uuid.uuid4().hex
            instance = snapshot["databases"]["scheduler"]["tables"]["scheduler_instances"][0]
            tombstone = {**instance, "state": "closed", "closed_at": datetime.now(timezone.utc).isoformat()}
            index = {"version": 1, "instance_id": instance_id, "instance": instance, "job_id": job,
                     "storage_state": "archiving", "phase": "preparing", "browser_epoch": (prior or {}).get("browser_epoch", 0.0),
                     "fingerprint": fingerprint, "archive_path": str(self.root / instance_id),
                     "can_resume": True, "can_rollback": True, "tombstone": tombstone, "counts": self._counts(snapshot),
                     "owners": {key: snapshot[field] for key, field in (("artifact", "artifact_ids"), ("run", "run_ids"),
                              ("approval", "approval_ids"), ("execution", "execution_ids"))}}
            snapshot["tombstone"] = tombstone
            snapshot_path = self._job_root(index) / "snapshot.json"
            # Save the original state/session bytes before installing the gate.
            durable_json(snapshot_path, encode(snapshot))
            index["snapshot_sha256"] = hash_file(snapshot_path)["sha256"]
            try:
                self._fault("after_archive_scan")
                with self.gate.exclusive(instance_id):
                    ticket.validate()
                    self.gate.ensure_available(instance_id)
                    self._require_paused_clients(instance_id)
                    with backend_writer_guards(self.runtime, snapshot["run_ids"], snapshot["execution_ids"]):
                        self._check_files(snapshot, diagnostics=False)
                        self._save(index)
                        self.gate.begin(instance_id, job, "archive")
                        self._freeze(snapshot)
                self._fault("after_freeze")
                self._continue_archive(index, snapshot)
            except BaseException as error:
                current = self._index(instance_id)
                if current and current["job_id"] == job:
                    self._interrupted(index, error)
                raise
            return self.status(instance_id)

    def _freeze(self, snapshot):
        connection = sqlite3.connect(snapshot["database_paths"]["scheduler"], timeout=2)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE scheduler_instances SET state=?,closed_at=? WHERE instance_id=?",
                               ("closed", snapshot["tombstone"]["closed_at"], snapshot["instance_id"]))
            connection.execute("DELETE FROM scheduler_sessions WHERE instance_id=?", (snapshot["instance_id"],))
            connection.commit()
        finally:
            connection.close()

    def _check_control(self, snapshot, *, frozen):
        current = Records(self.runtime).select(snapshot["instance_id"])
        expected = decode(encode(snapshot["databases"]))
        if frozen:
            expected["scheduler"]["tables"]["scheduler_instances"] = [snapshot["tombstone"]]
            expected["scheduler"]["tables"]["scheduler_sessions"] = []
        expected["runs"]["tables"].pop("run_activity_sequence", None)
        current_comparison = decode(encode(current["databases"]))
        current_comparison["runs"]["tables"].pop("run_activity_sequence", None)
        if encode(current_comparison) != encode(expected):
            raise ArchiveError("exact control records changed after archive preview")
        return current

    def _check_files(self, snapshot, *, diagnostics=True):
        """Fast frozen inventory check; large-file hashing stays outside EX."""
        expected_paths = {entry["archive_path"] for entry in snapshot["files"]}
        directories = []
        for entry in snapshot["files"]:
            path = check_path(Path(snapshot["roots"][entry["root"]]) / entry["relative_path"])
            if not path.exists():
                raise ArchiveError("source disappeared after archive preview")
            metadata = path.stat()
            if entry["kind"] == "directory":
                if not path.is_dir() or metadata.st_mode & 0o7777 != entry["mode"]:
                    raise ArchiveError("source directory changed after preview")
                if not any(path.is_relative_to(prior) for _, prior in directories):
                    directories.append((entry["root"], path))
            elif ([metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, metadata.st_ctime_ns] != entry["source_stat"]
                    or metadata.st_size != entry["size_bytes"] or metadata.st_mode & 0o7777 != entry["mode"]):
                raise ArchiveError("source file changed after archive preview")
        for key, directory in directories:
            for current, child_dirs, files in os.walk(directory, followlinks=False):
                for name in child_dirs + files:
                    path = check_path(Path(current) / name)
                    if key + "/" + path.relative_to(snapshot["roots"][key]).as_posix() not in expected_paths:
                        raise ArchiveError("source tree acquired unpreviewed files")
        for gap in snapshot["gaps"]:
            if gap["code"] == "historical_file_missing" and "path" in gap:
                for key, root in snapshot["roots"].items():
                    if gap["path"].startswith(key + "/") and (Path(root) / gap["path"][len(key) + 1:]).exists():
                        raise ArchiveError("previously missing source appeared after preview")
        diagnostic_root = Path(snapshot["roots"]["diagnostics"])
        diagnostic_scopes = {"instance:" + snapshot["instance_id"]} | {"execution:" + value for value in snapshot["execution_ids"]}
        if diagnostics and diagnostic_root.exists():
            for path in diagnostic_root.glob("diag_*.json"):
                if "diagnostics/" + path.name not in expected_paths:
                    check_path(path)
                    if path.stat().st_size <= 512 * 1024:
                        try:
                            value = json.loads(path.read_bytes())
                        except (ValueError, UnicodeError):
                            continue
                        if isinstance(value, dict) and isinstance(value.get("scope"), str) and value["scope"] in diagnostic_scopes:
                            raise ArchiveError("instance acquired an unpreviewed diagnostic")

    def _continue_archive(self, index, snapshot):
        package = self.root / index["instance_id"]
        stage = self.root / (".staging_" + index["job_id"])
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        check_path(self.root)
        if index["phase"] in {"preparing", "interrupted"} and not index.get("manifest_sha256"):
            stage.mkdir(mode=0o700, exist_ok=True)
            for entry in snapshot["files"]:
                copy_verified(Path(snapshot["roots"][entry["root"]]) / entry["relative_path"], stage / entry["archive_path"], entry)
            self._fault("after_file_copy")
            records = stage / "records"
            records.mkdir(mode=0o700, exist_ok=True)
            # Partial databases from interrupted preparation are disposable
            # derived copies. Preserve them in the job history before rebuilding.
            for key, data in snapshot["databases"].items():
                destination = records / (key + ".sqlite3")
                partials = [destination.with_name(destination.name + suffix) for suffix in ("", "-journal", "-wal", "-shm")]
                if any(path.exists() for path in partials):
                    history = self.root / ".history" / ("partial_" + index["job_id"] + "_" + uuid.uuid4().hex)
                    history.mkdir(parents=True, mode=0o700)
                    for path in partials:
                        if path.exists():
                            check_path(path)
                            os.rename(path, history / path.name)
                    fsync_directory(history)
                    fsync_directory(history.parent)
                    fsync_directory(records)
                build_database(destination, data)
                descriptor = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            durable_json(records / "snapshot.json", encode(snapshot))
            finish_permissions(stage, snapshot["files"])
            verify_tree(stage, snapshot["files"])
            for current, _, _ in os.walk(stage, topdown=False):
                fsync_directory(Path(current))
            fsync_directory(self.root)
            fsync_directory(self.root.parent)
            fsync_directory(self.project_root)
            self._fault("before_publish")
            with ReadTicket(self.runtime) as ticket:
                current = self._check_control(snapshot, frozen=True)
                self._check_files(snapshot)
                # Shared reachability and every record hash are computed before
                # the short switch. The same RO handles detect intervening commits.
                exclusive = sorted(set(snapshot["exclusive_artifact_ids"]) & set(current["exclusive_artifact_ids"]))
                shared = set(snapshot["shared_digests"]) | set(current["shared_digests"])
                for entry in snapshot["files"]:
                    if entry["root"] == "objects" and entry.get("sha256") in shared:
                        entry["shared"] = True
                snapshot["exclusive_artifact_ids"] = exclusive
                snapshot["shared_digests"] = sorted(shared)
                durable_json(records / "snapshot.json", encode(snapshot))
                manifest = {"version": 1, "instance_id": index["instance_id"], "job_id": index["job_id"],
                            "project_root": snapshot["project_root"], "state_root": snapshot["state_root"],
                            "files": snapshot["files"], "roots": snapshot["roots"], "gaps": snapshot["gaps"],
                            "unowned": snapshot["unowned"], "records": {path.name: hash_file(path) for path in sorted(records.iterdir())}}
                durable_json(stage / "manifest.json", manifest)
                manifest_sha256 = hash_file(stage / "manifest.json")["sha256"]
                fsync_directory(records)
                fsync_directory(stage)
                ticket.validate()
                self._fault("after_archive_publish_scan")
                with self.gate.exclusive(index["instance_id"]), backend_writer_guards(self.runtime, snapshot["run_ids"], snapshot["execution_ids"]):
                    ticket.validate()
                    self._check_files(snapshot, diagnostics=False)
                    if package.exists():
                        history = self.root / ".history"
                        history.mkdir(mode=0o700, exist_ok=True)
                        os.rename(package, history / (index["instance_id"] + "." + uuid.uuid4().hex))
                        fsync_directory(history)
                    os.rename(stage, package)
                    fsync_directory(self.root)
                    index["manifest_sha256"] = manifest_sha256
                    index["phase"] = "published"
                    self._save(index)
            self._fault("after_publish")
        manifest = self._manifest(index)
        snapshot = self._package_snapshot(index, manifest)
        if not self._migrated(snapshot):
            with ReadTicket(self.runtime) as ticket:
                current = self._check_control(snapshot, frozen=True)
                ticket.validate()
                self._fault("after_archive_switch_scan")
                with self.gate.exclusive(index["instance_id"]), backend_writer_guards(self.runtime, snapshot["run_ids"], snapshot["execution_ids"]):
                    ticket.validate()
                    exclusive = sorted(set(snapshot["exclusive_artifact_ids"]) & set(current["exclusive_artifact_ids"]))
                    # Keep newly shared bytes even when referenced after publication.
                    index["active_exclusive_artifact_ids"] = exclusive
                    index["active_shared_digests"] = sorted(set(snapshot["shared_digests"]) | set(current["shared_digests"]))
                    index["phase"] = "switching"
                    self._save(index)
                    transfer_records(snapshot["database_paths"], snapshot["databases"], direction="archive",
                                     exclusive_ids=exclusive, tombstone=snapshot["tombstone"], fault=self._fault)
        index["phase"] = "cleanup"
        self._save(index)
        self._fault("before_cleanup")
        entries = decode(encode(snapshot["files"]))
        for entry in entries:
            if entry["root"] == "objects" and entry.get("sha256") in index.get("active_shared_digests", ()):
                entry["shared"] = True
        retired = self._retire_recovery_trees(index, snapshot, entries)
        cleanup([entry for entry in entries if entry["archive_path"] not in retired], snapshot["roots"],
                unlink_guard=lambda entry, path: self._cleanup_guard(index["instance_id"], entry, path))
        self._fault("after_cleanup")
        index.update(storage_state="archived", phase="completed", can_resume=False, can_rollback=False,
                     released_bytes=sum(entry["size_bytes"] for entry in entries if entry["kind"] == "file" and not entry["shared"]
                                        and entry["archive_path"] not in retired)
                         + sum(value.get("released_bytes", 0) for value in index.get("recovery_retirements", {}).values()
                               if value["job_id"] == index["job_id"]))
        index.pop("error", None)
        self._save(index)

    def _retire_recovery_trees(self, index, snapshot, entries, *, missing_ok=False):
        """Remove the published name atomically, then clean only that old inode."""
        handled = set()
        for root_entry, selected, relative_entries in recovery_trees(entries):
            handled.update(entry["archive_path"] for entry in selected)
            key = index["job_id"] + ":" + root_entry["archive_path"]
            recorded = index.get("recovery_retirements", {}).get(key)
            if recorded is None and root_entry["shared"]:
                continue
            root = Path(snapshot["roots"][root_entry["root"]])
            source = check_path(root / root_entry["relative_path"])
            retired_relative = "recovery/.archive-retired_" + source.name + "_" + index["job_id"]
            retired = check_path(root / retired_relative)
            if recorded is None:
                if not source.exists():
                    if missing_ok:
                        continue
                    raise ArchiveError("unrecorded recovery tree disappeared before retirement")
                verify_tree(source, relative_entries)
                info = source.stat()
                with self._cleanup_guard(index["instance_id"], root_entry, source) as allowed:
                    if not allowed:
                        for entry in selected:
                            entry["shared"] = True
                        continue
                    if retired.exists():
                        raise ArchiveError("unregistered recovery retirement path exists")
                    recorded = {"job_id": index["job_id"], "root": root_entry["root"], "source_relative": root_entry["relative_path"],
                                "retired_relative": retired_relative, "source_identity": [info.st_dev, info.st_ino],
                                "phase": "planned", "original_bytes": sum(entry["size_bytes"] for entry in selected if entry["kind"] == "file")}
                    index.setdefault("recovery_retirements", {})[key] = recorded
                    self._save(index)
                    os.rename(source, retired)
                    fsync_directory(source.parent)
                    self._fault("after_recovery_retire_rename")
                    recorded["phase"] = "retired"
                    self._save(index)
            elif (recorded["job_id"], recorded["root"], recorded["source_relative"], recorded["retired_relative"]) != (
                    index["job_id"], root_entry["root"], root_entry["relative_path"], retired_relative):
                raise ArchiveError("recovery retirement journal identity differs")
            elif recorded["phase"] == "planned" and not retired.exists():
                with self._cleanup_guard(index["instance_id"], root_entry, source) as allowed:
                    info = source.stat()
                    if [info.st_dev, info.st_ino] != recorded["source_identity"]:
                        raise ArchiveError("original recovery inode changed before retirement")
                    if not allowed:
                        for entry in selected:
                            entry["shared"] = True
                        continue
                    os.rename(source, retired)
                    fsync_directory(source.parent)
                    self._fault("after_recovery_retire_rename")
                    recorded["phase"] = "retired"
                    self._save(index)
            # After a crash, never inspect/delete a replacement source name.
            # The exact durable retired name is the sole remaining cleanup target.
            self._fault("after_recovery_retire")
            if retired.exists():
                cleanup([{**entry, "root": "retired", "relative_path": entry["archive_path"], "shared": False}
                         for entry in relative_entries], {"retired": retired})
            recorded.update(phase="completed", released_bytes=recorded["original_bytes"])
            self._save(index)
        return handled

    def _cleanup_recorded_retirements(self, index, snapshot):
        groups = {(entry["root"], entry["relative_path"]): relative
                  for entry, _, relative in recovery_trees(snapshot["files"])}
        for recorded in index.get("recovery_retirements", {}).values():
            if recorded["phase"] in {"completed", "cancelled"}:
                continue
            relative = groups.get((recorded["root"], recorded["source_relative"]))
            expected = "recovery/.archive-retired_" + Path(recorded["source_relative"]).name + "_" + safe_id(recorded["job_id"])
            if relative is None or recorded["retired_relative"] != expected:
                raise ArchiveError("retired recovery identity is outside the registered archive")
            retired = check_path(Path(snapshot["roots"][recorded["root"]]) / expected)
            if recorded["phase"] == "planned" and not retired.exists():
                # Rollback may cancel a durable intention that never renamed.
                recorded.update(phase="cancelled", released_bytes=0)
            else:
                if retired.exists():
                    cleanup([{**entry, "root": "retired", "relative_path": entry["archive_path"], "shared": False}
                             for entry in relative], {"retired": retired})
                recorded.update(phase="completed", released_bytes=recorded["original_bytes"])
            self._save(index)

    @contextmanager
    def _cleanup_guard(self, instance_id, entry, path):
        relative = Path(entry["relative_path"]).parts
        recovery = entry["root"] in {"workspaces/local", "workspaces/hardened"} and len(relative) > 1 and relative[0] == "recovery"
        execution_result = entry["root"] == "executions/results" and len(relative) > 1 and relative[0] in {"runs", "inspection"}
        if entry["root"] != "objects" and not recovery and not execution_result:
            yield True
            return
        # Retention scans stay outside EX. Keep their original RO connection's
        # data_version ticket alive until the guarded unlink/rmdir.
        database = "runs" if recovery else "executions" if execution_result else "artifacts"
        with ReadTicket(self.runtime, databases=(database,)) as ticket:
            retained = False
            if recovery:
                candidate = relative[1]
                if candidate.startswith(".staging_"):
                    candidate = candidate[len(".staging_"):].split("_", 1)[0]
                backend = "local_trusted" if entry["root"] == "workspaces/local" else "hardened_worker"
                digests, _ = retained_recovery_digests(self.runtime.runs.database_path, instance_id, backend, {candidate})
                retained = candidate in digests
            elif execution_result:
                with readonly(self.runtime.executions.database_path) as connection:
                    retained = bool(connection.execute("SELECT 1 FROM executions WHERE external_run_id=? LIMIT 1", (relative[1],)).fetchone())
            else:
                with readonly(self.runtime.artifacts.registry.database_path) as connection:
                    retained = bool(connection.execute("SELECT 1 FROM artifact_envelopes WHERE payload_sha256=? LIMIT 1", (entry["sha256"],)).fetchone())
            ticket.validate()
            with self.gate.exclusive(instance_id):
                ticket.validate()
                yield not retained

    def _migrated(self, snapshot):
        # This is the crash boundary detector. ATTACH makes the multi-library
        # state entirely before or after the switch; no Run state is inferred.
        index = self._index(snapshot["instance_id"])
        exclusive = set(index.get("active_exclusive_artifact_ids", snapshot["exclusive_artifact_ids"]))
        inspected = False
        for database, data in snapshot["databases"].items():
            if database == "views":
                continue
            with readonly(snapshot["database_paths"][database]) as connection:
                for table, rows in data["tables"].items():
                    if table in {"scheduler_instances", "scheduler_sessions", "run_activity_sequence"} or (database == "views" and table == "metadata"):
                        continue
                    if database == "executions" and table in RETAINED_EXECUTION_TABLES:
                        continue
                    for row in rows:
                        if database == "artifacts" and row["source_artifact_id" if table == "artifact_links" else "artifact_id"] not in exclusive:
                            continue
                        inspected = True
                        where, values = row_where(row, data["schema"]["tables"][table])
                        if connection.execute(f"SELECT 1 FROM {quote(table)} WHERE {where}", values).fetchone():
                            return False
        if inspected:
            return True
        if index["storage_state"] == "restoring":
            with readonly(snapshot["database_paths"]["scheduler"]) as connection:
                row = connection.execute("SELECT * FROM scheduler_instances WHERE instance_id=?", (snapshot["instance_id"],)).fetchone()
                return row is not None and dict(row) == execution_settings_tombstone(snapshot["tombstone"])
        return index["phase"] in {"switching", "cleanup", "completed"}

    def _manifest(self, index):
        path = check_path(self.root / index["instance_id"] / "manifest.json")
        if not index.get("manifest_sha256") or hash_file(path)["sha256"] != index["manifest_sha256"]:
            raise ArchiveError("archive is not registered or its manifest digest differs")
        value = json.loads(path.read_bytes())
        if value.get("version") != 1 or value.get("instance_id") != index["instance_id"]:
            raise ArchiveError("registered archive identity or version differs")
        return value

    def _package_snapshot(self, index, manifest=None):
        manifest = manifest or self._manifest(index)
        path = self.root / index["instance_id"] / "records" / "snapshot.json"
        if hash_file(path)["sha256"] != manifest["records"]["snapshot.json"]["sha256"]:
            raise ArchiveError("raw record snapshot digest differs")
        return decode(json.loads(path.read_bytes()))

    def _restore_validation(self, index, *, capture=None, capture_objects=None, verified_files=None, verified_objects=None):
        if verified_objects is None:
            manifest = self._manifest(index)
            snapshot = self._package_snapshot(index, manifest)
        else:
            manifest, snapshot = verified_objects["manifest"], verified_objects["snapshot"]
        if capture_objects is not None:
            capture_objects.update(manifest=manifest, snapshot=snapshot)
        package = self.root / index["instance_id"]
        if (snapshot["project_root"] != str(self.project_root) or snapshot["state_root"] != str(self.state_root)
                or snapshot["roots"] != {key: str(value) for key, value in roots(self.runtime).items()}
                or snapshot["backend_id"] != self.runtime.runs.backend.backend_id
                or snapshot["backend_version"] != self.runtime.runs.backend.backend_version):
            raise ArchiveError("restore requires the original configured roots and backend")
        def verify_file(path, expected):
            path = check_path(path)
            if verified_files is None:
                actual = hash_file(path)
            else:
                actual = verified_files.get(str(path))
                metadata = path.stat()
                if (actual is None or actual["source_stat"] != [metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, metadata.st_ctime_ns]
                        or actual["size_bytes"] != metadata.st_size or actual["mode"] != metadata.st_mode & 0o7777):
                    raise ArchiveError("verified restore file changed before database switch")
                # Full hashes precede EX. The gate excludes controlled writers;
                # CAS and published recovery trees use immutable publication.
                # Concurrent raw writes outside those protocols are unsupported
                # (coarse timestamps cannot authenticate arbitrary bare writes).
            if any(actual[key] != expected[key] for key in ("sha256", "size_bytes", "mode")):
                raise ArchiveError("restore file content or permissions differ")
            if capture is not None:
                capture[str(path)] = actual

        manifest_path = package / "manifest.json"
        if verified_files is not None:
            verify_file(manifest_path, verified_files[str(manifest_path)])
        elif capture is not None:
            actual = hash_file(manifest_path)
            if actual["sha256"] != index["manifest_sha256"]:
                raise ArchiveError("registered archive manifest changed during restore scan")
            capture[str(manifest_path)] = actual

        for entry in manifest["files"]:
            path = check_path(package / entry["archive_path"])
            if entry["kind"] == "directory":
                if not path.is_dir() or path.stat().st_mode & 0o7777 != entry["mode"]:
                    raise ArchiveError("archive directory is missing or its permissions changed")
            else:
                verify_file(path, entry)
        for name, expected in manifest["records"].items():
            if "/" in name or "\\" in name:
                raise ArchiveError("invalid archive record filename")
            verify_file(package / "records" / name, expected)
        conflicts = []
        for root_entry, _, relative_entries in recovery_trees(snapshot["files"]):
            directory = check_path(Path(snapshot["roots"][root_entry["root"]]) / root_entry["relative_path"])
            if directory.exists():
                try:
                    verify_tree_inventory(directory, relative_entries)
                except ArchiveError:
                    conflicts.append({"code": "published_recovery_tree_conflict", "path": root_entry["archive_path"]})
        for entry in snapshot["files"]:
            if not entry["restore"]:
                continue
            path = check_path(Path(snapshot["roots"][entry["root"]]) / entry["relative_path"])
            if verified_files is not None and not path.exists():
                conflicts.append({"code": "verified_restore_file_disappeared", "path": entry["archive_path"]})
                continue
            if path.exists():
                if entry["kind"] == "directory":
                    if not path.is_dir() or path.stat().st_mode & 0o7777 != entry["mode"]:
                        conflicts.append({"code": "restore_directory_conflict", "path": entry["archive_path"]})
                else:
                    try:
                        verify_file(path, entry)
                    except ArchiveError:
                        conflicts.append({"code": "restore_file_conflict", "path": entry["archive_path"]})
        _, restore_databases, _ = self._restore_components(snapshot)
        for key, data in restore_databases.items():
            path = Path(snapshot["database_paths"][key])
            if not path.is_file():
                raise ArchiveError("original active database is missing")
            with readonly(path) as connection:
                objects = [dict(row) for row in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
                if schema(connection) != data["schema"]:
                    raise ArchiveError("restore schema differs: " + key)
                for table, rows in data["tables"].items():
                    if table in {"scheduler_sessions", "run_activity_sequence"} or key == "dispatch" or (key == "views" and table == "metadata"):
                        continue
                    for row in rows:
                        where, values = row_where(row, data["schema"]["tables"][table])
                        columns = "rowid AS __archive_rowid__,*" if table == "run_activity" else "*"
                        found = connection.execute(f"SELECT {columns} FROM {quote(table)} WHERE {where}", values).fetchone()
                        expected = execution_settings_tombstone(snapshot["tombstone"]) if table == "scheduler_instances" else row
                        if found is not None and dict(found) != expected and not (table == "scheduler_instances" and dict(found) == row):
                            conflicts.append({"code": "restore_record_identity_conflict", "database": key, "table": table})
        return snapshot, conflicts

    def _restore_components(self, snapshot):
        """UI cache generation is optional display data, not science admission."""
        paths = dict(snapshot["database_paths"])
        databases = {key: execution_settings_restore_view(data) for key, data in snapshot["databases"].items()}
        gaps = []
        if "views" not in databases:
            return paths, databases, gaps
        data = databases["views"]
        try:
            with readonly(paths["views"]) as connection:
                objects = [dict(row) for row in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
                metadata = [dict(row) for row in connection.execute("SELECT * FROM metadata ORDER BY rowid")]
                if objects != data["schema"]["objects"] or metadata != data["tables"]["metadata"]:
                    raise ArchiveError("view generation or schema changed")
                for table, rows in data["tables"].items():
                    if table == "metadata":
                        continue
                    for row in rows:
                        where, values = row_where(row, data["schema"]["tables"][table])
                        found = connection.execute(f"SELECT * FROM {quote(table)} WHERE {where}", values).fetchone()
                        if found is not None and dict(found) != row:
                            raise ArchiveError("view cache row identity changed")
        except (OSError, sqlite3.Error, ArchiveError):
            paths.pop("views")
            databases.pop("views")
            gaps.append({"code": "active_view_cache_rebuild_required", "history": "verified_archive_views_preserved",
                         "scope": "UI observations and preferences; scientific records restore unchanged"})
        return paths, databases, gaps

    def restore_preview(self, instance_id):
        try:
            with self.runtime.maintenance.shared():
                index = self._index(instance_id)
                if index is None or index["storage_state"] != "archived":
                    raise ArchiveError("instance has no completed archive")
                snapshot, conflicts = self._restore_validation(index)
            counts = self._counts(snapshot)
            if shutil.disk_usage(self.state_root).free < counts["temporary_bytes"]:
                conflicts.append({"code": "insufficient_restore_disk_space"})
            _, _, cache_gaps = self._restore_components(snapshot)
            fingerprint = digest({"manifest": index["manifest_sha256"], "browser_epoch": index["browser_epoch"], "conflicts": conflicts, "cache_gaps": cache_gaps,
                                  "roots": snapshot["roots"], "database_paths": snapshot["database_paths"]})
            return {"instance_id": instance_id, "action": "restore", "fingerprint": fingerprint, "ready": not conflicts,
                    "busy": [], "gaps": snapshot["gaps"] + cache_gaps, "unsupported": conflicts, "unowned": snapshot["unowned"],
                    "counts": counts, "archive_path": str(self.root / instance_id)}
        except (ArchiveError, ValueError, OSError, sqlite3.Error) as error:
            return {"instance_id": instance_id, "action": "restore", "fingerprint": None, "ready": False,
                    "busy": [], "gaps": [], "unsupported": [{"code": "restore_unavailable", "detail": str(error)}],
                    "counts": {}, "archive_path": str(self.root / safe_id(instance_id))}

    def restore(self, instance_id, fingerprint):
        with self._job_lock(instance_id):
            preview = self.restore_preview(instance_id)
            if not preview["ready"] or not isinstance(fingerprint, str) or preview["fingerprint"] != fingerprint:
                raise ArchiveError("restore preview changed or has unresolved conflicts")
            index = self._index(instance_id)
            with self.gate.exclusive(instance_id):
                old_job = index["job_id"]
                index.update(job_id="restore_" + uuid.uuid4().hex, storage_state="restoring", phase="preparing",
                             fingerprint=fingerprint, can_resume=True, can_rollback=True, previous_job_id=old_job)
                self._save(index)
                self.gate.handoff(instance_id, old_job, index["job_id"], "restore")
            try:
                self._continue_restore(index)
            except BaseException as error:
                self._interrupted(index, error)
                raise
            return self.status(instance_id)

    def _continue_restore(self, index):
        snapshot, conflicts = self._restore_validation(index)
        if conflicts:
            raise ArchiveError("restore has exact identity conflicts")
        self._cleanup_recorded_retirements(index, snapshot)
        package = self.root / index["instance_id"]
        recovery_paths = restore_recovery_trees(package, snapshot["files"], snapshot["roots"], job_id=index["job_id"],
            publish_guard=lambda: self.gate.exclusive(index["instance_id"]), fault=self._fault)
        for entry in snapshot["files"]:
            if entry["restore"] and entry["archive_path"] not in recovery_paths:
                copy_verified(package / entry["archive_path"], Path(snapshot["roots"][entry["root"]]) / entry["relative_path"], entry)
        for entry in reversed(snapshot["files"]):
            if entry["restore"] and entry["kind"] == "directory" and entry["archive_path"] not in recovery_paths:
                directory = Path(snapshot["roots"][entry["root"]]) / entry["relative_path"]
                os.chmod(directory, entry["mode"])
                fsync_directory(directory)
                fsync_directory(directory.parent)
        self._fault("after_restore_copy")
        with ReadTicket(self.runtime) as ticket:
            verified_files, verified_objects = {}, {}
            snapshot, conflicts = self._restore_validation(index, capture=verified_files, capture_objects=verified_objects)
            if conflicts:
                raise ArchiveError("restored files have exact identity conflicts")
            ticket.validate()
            self._fault("before_restore_switch")
            with self.gate.exclusive(index["instance_id"]):
                ticket.validate()
                self._finish_restore(index, verified_files, verified_objects)

    def _finish_restore(self, index, verified_files, verified_objects):
        snapshot, conflicts = self._restore_validation(index, verified_files=verified_files, verified_objects=verified_objects)
        if conflicts:
            raise ArchiveError("restore conflicts changed before database switch")
        index["phase"] = "switching"
        self._save(index)
        # Idempotent retry after a committed restore uses the original row as
        # the expected exact tombstone, without altering immutable records.
        with readonly(snapshot["database_paths"]["scheduler"]) as connection:
            instance = dict(connection.execute("SELECT * FROM scheduler_instances WHERE instance_id=?", (index["instance_id"],)).fetchone())
        original = execution_settings_restore_view(snapshot["databases"]["scheduler"])["tables"]["scheduler_instances"][0]
        if instance not in (execution_settings_tombstone(snapshot["tombstone"]), original):
            raise ArchiveError("restore instance row changed")
        paths, databases, cache_gaps = self._restore_components(snapshot)
        transfer_records(paths, databases, direction="restore", tombstone=instance, fault=self._fault)
        index["restore_gaps"] = cache_gaps
        index.update(storage_state="restored", phase="finalizing", browser_epoch=time.time(), can_resume=True, can_rollback=False)
        index.pop("error", None)
        self._save(index)
        self._fault("before_restore_gate_finish")
        self.gate.finish(index["instance_id"], index["job_id"])
        index.update(phase="completed", can_resume=False)
        self._save(index)

    def _interrupted(self, index, error):
        # Do not erase the last durable phase: it identifies a possible committed
        # database switch even when an injected/process error followed COMMIT.
        index["error"] = {"code": "maintenance_interrupted", "type": type(error).__name__, "detail": str(error)}
        index["can_resume"], index["can_rollback"] = True, True
        if index["storage_state"] == "restored":
            index["can_rollback"] = False
        self._save(index)

    def resume(self, instance_id, fingerprint=None):
        with self._job_lock(instance_id):
            index = self._index(instance_id)
            if not index or not index["can_resume"] or (fingerprint is not None and fingerprint != index["fingerprint"]):
                raise ArchiveError("no matching interrupted maintenance action")
            try:
                if index["storage_state"] == "restored":
                    with self.gate.exclusive(instance_id):
                        self.gate.finish(instance_id, index["job_id"])
                        index.update(phase="completed", can_resume=False, can_rollback=False)
                        index.pop("error", None)
                        self._save(index)
                elif index["storage_state"] == "restoring":
                    snapshot = self._package_snapshot(index)
                    with self.gate.exclusive(instance_id):
                        marker = self.gate.status(instance_id)
                        if marker is None:
                            self.gate.begin(instance_id, index["job_id"], "restore")
                        elif marker["job_id"] != index["job_id"]:
                            if marker["job_id"] != index.get("previous_job_id"):
                                raise ArchiveError("restore marker belongs to another exact job")
                            self.gate.handoff(instance_id, marker["job_id"], index["job_id"], "restore")
                        self._recover_databases(snapshot)
                    self._continue_restore(index)
                else:
                    path = self._job_root(index) / "snapshot.json"
                    if hash_file(path)["sha256"] != index["snapshot_sha256"]:
                        raise ArchiveError("maintenance snapshot hash differs")
                    snapshot = decode(json.loads(path.read_bytes()))
                    with self.gate.exclusive(instance_id):
                        self._recover_databases(snapshot)
                        self.gate.begin(instance_id, index["job_id"], "archive")
                        # Resume can have interrupted immediately after writing
                        # the durable marker but before closing the instance.
                        if not self._migrated(snapshot):
                            with backend_writer_guards(self.runtime, snapshot["run_ids"], snapshot["execution_ids"]):
                                self._freeze(snapshot)
                    self._continue_archive(index, snapshot)
            except BaseException as error:
                self._interrupted(index, error)
                raise
            return self.status(instance_id)

    def _recover_databases(self, snapshot):
        # SQLite needs a writable maintenance connection to recover hot rollback
        # journals; a read-only inventory connection must not attempt that work.
        paths, _, _ = self._restore_components(snapshot)
        connection = attached(paths)
        try:
            for key in paths:
                alias = "main" if key == "scheduler" else key
                connection.execute(f"SELECT COUNT(*) FROM {quote(alias)}.sqlite_master").fetchone()
        finally:
            connection.close()

    def rollback(self, instance_id, fingerprint=None):
        with self._job_lock(instance_id):
            index = self._index(instance_id)
            if not index or not index["can_rollback"] or (fingerprint is not None and fingerprint != index["fingerprint"]):
                raise ArchiveError("no matching maintenance rollback")
            if index["storage_state"] == "restoring":
                # A restore rollback preserves all archive bytes. Remove copied
                # exclusive active files only while records remain archived.
                snapshot = self._package_snapshot(index)
                if not self._migrated(snapshot):
                    raise ArchiveError("restore database switch committed; resume is required")
                verify_tree(self.root / instance_id, snapshot["files"])
                discard_restore_stages(snapshot["files"], snapshot["roots"], index["job_id"])
                retired = self._retire_recovery_trees(index, snapshot, snapshot["files"], missing_ok=True)
                cleanup([entry for entry in snapshot["files"] if entry["archive_path"] not in retired], snapshot["roots"],
                        unlink_guard=lambda entry, path: self._cleanup_guard(instance_id, entry, path))
                with self.gate.exclusive(instance_id):
                    index.update(storage_state="archived", phase="completed", can_resume=False, can_rollback=False)
                    index.pop("error", None)
                    self._save(index)
                return self.status(instance_id)
            if index.get("manifest_sha256"):
                index["storage_state"] = "restoring"
                self._save(index)
                self._continue_restore(index)
            else:
                snapshot = decode(json.loads((self._job_root(index) / "snapshot.json").read_bytes()))
                with self.gate.exclusive(instance_id):
                    original = snapshot["databases"]["scheduler"]["tables"]["scheduler_instances"][0]
                    connection = sqlite3.connect(snapshot["database_paths"]["scheduler"])
                    try:
                        connection.execute("UPDATE scheduler_instances SET state=?,closed_at=? WHERE instance_id=?",
                                           (original["state"], original["closed_at"], instance_id))
                        connection.commit()
                    finally:
                        connection.close()
                    index.update(storage_state="restored", phase="finalizing", browser_epoch=time.time(), can_resume=True, can_rollback=False)
                    index.pop("error", None)
                    self._save(index)
                    self._fault("before_restore_gate_finish")
                    self.gate.finish(instance_id, index["job_id"])
                    index.update(phase="completed", can_resume=False)
                    self._save(index)
            return self.status(instance_id)

    def archived_model(self, instance_id):
        index = self._index(instance_id)
        if index is None or not index.get("manifest_sha256"):
            raise ArchiveError("no registered archive read model")
        manifest = self._manifest(index)
        from .instance_archive_reader import archived_model
        return archived_model(self.runtime, self.root / instance_id, manifest)

    def archived_views_path(self, instance_id):
        index = self._index(instance_id)
        manifest = self._manifest(index)
        if "views.sqlite3" not in manifest["records"]:
            return None
        path = self.root / instance_id / "records" / "views.sqlite3"
        if hash_file(path)["sha256"] != manifest["records"]["views.sqlite3"]["sha256"]:
            raise ArchiveError("archive view database hash differs")
        return path


__all__ = ["ArchiveError", "InstanceArchive"]
