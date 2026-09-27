"""Durable instance storage maintenance, independent of scientific lifecycle.

Writers take global SH, instance SH, then their backend locks and databases.
Archive freeze/switch takes nonblocking global EX and instance EX briefly. Its
marker survives lock release, process exit and restart until the same job clears
it. No clock or process identity can reopen an instance.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import stat
import threading
import uuid

from .maintenance import MaintenanceBusy, StateMaintenanceLock

_LOCAL = threading.local()
_LOG = logging.getLogger(__name__)


class InstanceMaintenanceBusy(MaintenanceBusy):
    def __init__(self, message="instance storage has active or unconfirmed writers", *, details=()):
        super().__init__(message)
        self.details = tuple(details)


class InstanceMaintenanceUnavailable(RuntimeError):
    """Maintenance rejection; never a scientific Run failure."""


def _key(value):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("instance identity is invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _held():
    if not hasattr(_LOCAL, "locks"):
        _LOCAL.locks = {}
    return _LOCAL.locks


def _open_lock(path, mode, operation, *, create=True):
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    if create:
        flags |= os.O_CREAT
    descriptor = os.open(path, flags, mode)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InstanceMaintenanceUnavailable("maintenance lock is not a regular file")
        fcntl.flock(descriptor, operation)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class WriterLease:
    """Independent shared descriptors transferable to a collection supervisor.

Close, rather than LOCK_UN, preserves ownership in an inherited guard process
until its final writes and exit. The lease does not depend on thread locals.
"""
    def __init__(self, descriptors):
        self.descriptors = tuple(descriptors)
        self._close_lock = threading.Lock()

    def close(self):
        with self._close_lock:
            descriptors, self.descriptors = self.descriptors, ()
        for descriptor in reversed(descriptors):
            os.close(descriptor)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class InstanceMaintenance:
    def __init__(self, state_root, *, maintenance=None):
        self.state_root = Path(state_root).expanduser().absolute()
        global_path = self.state_root / "maintenance.lock"
        shared = global_path.exists() and bool(global_path.stat().st_mode & 0o060)
        self.maintenance = maintenance or StateMaintenanceLock(global_path, shared_group=shared)
        self.root = self.state_root / "maintenance"
        self.mode = self.maintenance.mode
        for directory in (self.root, self.root / "instances", self.root / "locks"):
            if directory.is_symlink():
                raise InstanceMaintenanceUnavailable("maintenance directory is a symlink")
            directory.mkdir(parents=True, exist_ok=True, mode=0o770 if self.mode & 0o060 else 0o700)
        self._global_key = str(self.maintenance.path)

    def _marker(self, instance_id):
        return self.root / "instances" / (_key(instance_id) + ".json")

    def _lock_path(self, instance_id):
        return self.root / "locks" / (_key(instance_id) + ".lock")

    @contextmanager
    def global_guard(self):
        held = _held()
        if self._global_key in held:
            yield
            return
        with self.maintenance.shared():
            held[self._global_key] = "shared"
            try:
                yield
            finally:
                del held[self._global_key]

    @contextmanager
    def guard(self, instance_id):
        path = self._lock_path(instance_id)
        with self.global_guard():
            held = _held()
            key = str(path)
            descriptor = None
            if key not in held:
                descriptor = _open_lock(path, self.mode, fcntl.LOCK_SH)
                held[key] = "shared"
            try:
                self.ensure_available(instance_id)
                yield
            finally:
                if descriptor is not None:
                    del held[key]
                    os.close(descriptor)

    def acquire_writer(self, instance_id=None):
        """Acquire independent ownership that can outlive this request/thread."""
        # Call before backend locks. Never borrow an outer request's short SH FD.
        if _held().get(self._global_key) == "exclusive":
            raise InstanceMaintenanceBusy("cannot start a writer during a maintenance switch")
        descriptors = []
        try:
            descriptors.append(_open_lock(self.maintenance.path, self.mode, fcntl.LOCK_SH))
            if instance_id is not None:
                descriptors.append(_open_lock(self._lock_path(instance_id), self.mode, fcntl.LOCK_SH))
                self.ensure_available(instance_id)
            return WriterLease(descriptors)
        except BaseException:
            WriterLease(descriptors).close()
            raise

    @contextmanager
    def exclusive(self, instance_id):
        """Short nonblocking freeze/switch; never hold across staging or copy."""
        held = _held()
        if self._global_key in held:
            raise InstanceMaintenanceBusy("maintenance switch cannot upgrade an existing guard")
        try:
            with self.maintenance.exclusive(blocking=False):
                held[self._global_key] = "exclusive"
                path = self._lock_path(instance_id)
                try:
                    descriptor = _open_lock(path, self.mode, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BaseException:
                    del held[self._global_key]
                    raise
                held[str(path)] = "exclusive"
                try:
                    yield
                finally:
                    del held[str(path)]
                    del held[self._global_key]
                    os.close(descriptor)
        except (BlockingIOError, MaintenanceBusy) as error:
            if isinstance(error, InstanceMaintenanceBusy):
                raise
            raise InstanceMaintenanceBusy("control state is busy; maintenance did not wait") from error

    def status(self, instance_id):
        path = self._marker(instance_id)
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise InstanceMaintenanceUnavailable("maintenance marker cannot be read") from error
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("marker is not regular")
            raw = os.read(descriptor, 4097)
            if len(raw) > 4096:
                raise ValueError("marker is too large")
            value = json.loads(raw)
            if (not isinstance(value, dict) or value.get("instance_id") != instance_id
                    or not isinstance(value.get("job_id"), str) or not value["job_id"]
                    or value.get("action") not in {"archive", "restore"}):
                raise ValueError("marker identity is invalid")
            return value
        except (ValueError, UnicodeError, OSError) as error:
            raise InstanceMaintenanceUnavailable("maintenance marker is invalid; instance stays blocked") from error
        finally:
            os.close(descriptor)

    def ensure_available(self, instance_id):
        value = self.status(instance_id)
        if value is not None:
            _LOG.warning("Instance storage maintenance rejected a writer: %s (%s)", instance_id, value["action"])
            raise InstanceMaintenanceUnavailable("instance storage maintenance is in progress")

    def _require_exclusive(self, instance_id):
        if (_held().get(self._global_key) != "exclusive"
                or _held().get(str(self._lock_path(instance_id))) != "exclusive"):
            raise InstanceMaintenanceBusy("maintenance marker changes require the short exclusive guard")

    def begin(self, instance_id, job_id, action):
        self._require_exclusive(instance_id)
        _key(job_id)
        if action not in {"archive", "restore"}:
            raise ValueError("maintenance action is invalid")
        value = {"instance_id": instance_id, "job_id": job_id, "action": action}
        prior = self.status(instance_id)
        if prior is not None:
            if prior != value:
                raise InstanceMaintenanceBusy("instance belongs to another maintenance job")
            return prior
        return self._write_marker(instance_id, value)

    def handoff(self, instance_id, old_job_id, new_job_id, action):
        """Replace an owning job atomically; never remove its durable fence."""
        self._require_exclusive(instance_id)
        _key(old_job_id)
        _key(new_job_id)
        if action not in {"archive", "restore"}:
            raise ValueError("maintenance action is invalid")
        prior = self.status(instance_id)
        if prior is None or prior["job_id"] != old_job_id:
            raise InstanceMaintenanceBusy("maintenance handoff requires the exact owning job")
        value = {"instance_id": instance_id, "job_id": new_job_id, "action": action}
        return self._write_marker(instance_id, value)

    def _write_marker(self, instance_id, value):
        path = self._marker(instance_id)
        temporary = path.with_name(".new_" + uuid.uuid4().hex)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, self.mode)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(json.dumps(value, sort_keys=True).encode("utf-8"))
                stream.flush()
                os.fsync(descriptor)
            os.replace(temporary, path)
            self._sync_markers()
        finally:
            os.close(descriptor)
            temporary.unlink(missing_ok=True)
        return value

    def finish(self, instance_id, job_id):
        self._require_exclusive(instance_id)
        value = self.status(instance_id)
        if value is None:
            return
        if value["job_id"] != job_id:
            raise InstanceMaintenanceBusy("only the owning maintenance job may clear its marker")
        self._marker(instance_id).unlink()
        self._sync_markers()

    def _sync_markers(self):
        descriptor = os.open(self.root / "instances", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@contextmanager
def backend_writer_guards(runtime, run_ids=(), execution_ids=()):
    """Read-only, fail-closed proof under the caller's short maintenance EX.

Launcher telemetry covers its registered child group only. A native-enabled
local Worker can also write directly, so a stopped launcher never establishes
quiescence for that Worker. Recovery integrity is likewise not liveness proof.
    """
    run_ids, execution_ids = tuple(run_ids), tuple(execution_ids)
    details = []
    with ExitStack() as stack:
        def lock(path, *, kind, identity):
            try:
                descriptor = _open_lock(path, 0o600, fcntl.LOCK_EX | fcntl.LOCK_NB, create=False)
            except FileNotFoundError:
                return True
            except (OSError, InstanceMaintenanceUnavailable):
                details.append({"kind": kind, "id": identity, "reason": "lock_busy_or_unreadable"})
                return False
            stack.callback(os.close, descriptor)
            return True

        for run_id in tuple(run_ids):
            try:
                value = runtime.runs.status(run_id)
                backend = runtime.runs.backend
                if (value.backend_id != backend.backend_id or value.backend_version != backend.backend_version
                        or tuple(value.backend_capabilities) != tuple(backend.capabilities)):
                    details.append({"kind": "run", "id": run_id, "reason": "backend_identity_unavailable"})
                    continue
                if value.state not in {"completed", "failed"}:
                    details.append({"kind": "run", "id": run_id, "reason": "run_nonterminal"})
                    continue
                paths = backend.exact_workspace_paths(run_id)
                for path in paths:
                    lock(path / "scratch" / ".analysis-process" / "lock", kind="launcher", identity=run_id)
                if "native_tools_disabled" not in value.backend_capabilities:
                    details.append({"kind": "run", "id": run_id, "reason": "native_writers_unconfirmed"})
                    continue
                from .hardened_workspace import HardenedWorkerBackend
                if not isinstance(backend, HardenedWorkerBackend):
                    details.append({"kind": "run", "id": run_id, "reason": "backend_quiescence_unavailable"})
                    continue
                try:
                    stack.enter_context(backend.quiescence_guard(run_id))
                except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
                    details.append({"kind": "transport", "id": run_id, "reason": "transport_busy_or_unconfirmed", "error_type": type(error).__name__})
            except (OSError, ValueError, RuntimeError, sqlite3.Error, AttributeError, TypeError) as error:
                details.append({"kind": "run", "id": run_id, "reason": "writer_identity_unavailable", "error_type": type(error).__name__})
        for execution_id in tuple(execution_ids):
            try:
                if runtime.executions is None:
                    raise ValueError("execution service unavailable")
                value = runtime.executions.status(execution_id)
                if value.state not in {"succeeded", "failed", "cancelled", "collected"}:
                    details.append({"kind": "execution", "id": execution_id, "reason": "execution_nonterminal"})
                directory = runtime.executions.exchange_root / execution_id / "collection"
                lock(directory / "active.lock", kind="collection", identity=execution_id)
            except (OSError, ValueError, RuntimeError, sqlite3.Error, AttributeError, TypeError) as error:
                details.append({"kind": "execution", "id": execution_id, "reason": "collection_identity_unavailable", "error_type": type(error).__name__})
        # The launcher/supervisor slot also covers collection finalization after
        # its Execution has already become collected.
        if execution_ids:
            lock(Path(runtime.state_root) / "collection.lock", kind="collection_slot", identity="global")
        if details:
            raise InstanceMaintenanceBusy(details=details)
        yield {"quiescent": True, "run_count": len(run_ids), "execution_count": len(execution_ids)}
