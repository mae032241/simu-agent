"""One bounded collection process; no scientific Run or background task queue."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import selectors
import subprocess
import sys
import threading
import time
from typing import Callable

from .engineering_diagnostics import EngineeringDiagnostics, atomic_json, read_json

QUERY_SECONDS = 5.0
COLLECTION_SECONDS = 600.0
FILE_SECONDS = 120.0
IDLE_SECONDS = 30.0
_OWNED_GROUP_ENV = "_SCID_COLLECTION_PROCESS_GROUP"


def run_bounded(command, *, input: bytes, timeout: float, env=None, sink=None,
                idle_seconds=None, max_output_bytes=8 * 1024 * 1024, context=None, process_group=True,
                timeout_kind="operation_total", pass_fds=(), input_stream=None,
                transfer_chunk_bytes=1024 * 1024):
    """Drain both pipes, bound retained bytes, and reap this call's process group."""
    # A private collector already owns the whole transfer tree. Nested command
    # transports must stay in that group so forced exit cannot orphan writers.
    private_group = os.environ.get(_OWNED_GROUP_ENV) == str(os.getpgrp())
    process_group = process_group and not private_group
    if private_group:
        env = dict(os.environ if env is None else env)
        env[_OWNED_GROUP_ENV] = os.environ[_OWNED_GROUP_ENV]
    start = last_progress = time.monotonic()
    stdout, stderr = bytearray(), bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, start_new_session=process_group, pass_fds=pass_fds)
    try:
        # Header bytes stay bounded; an optional scientific body is streamed.
        os.set_blocking(process.stdin.fileno(), False)
        pending = memoryview(input)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            for name in ("stdout", "stderr"):
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map() or process.poll() is None:
                if context is not None:
                    context.remaining_seconds()
                now = time.monotonic()
                kind = timeout_kind if now - start >= timeout else "transfer_no_progress" if idle_seconds and now - last_progress >= idle_seconds else None
                if kind:
                    error = subprocess.TimeoutExpired(command, idle_seconds if kind == "transfer_no_progress" else timeout,
                        output=bytes(stdout), stderr=bytes(stderr))
                    error.timeout_kind = kind
                    error.elapsed_seconds = now - start
                    raise error
                for key, _ in selector.select(min(.05, max(.001, timeout - (now - start)))):
                    if key.data == "stdin":
                        if not pending and input_stream is not None:
                            pending = memoryview(input_stream.read(transfer_chunk_bytes))
                        if pending:
                            try:
                                sent = os.write(key.fileobj.fileno(), pending[:65536])
                                pending = pending[sent:]
                                if sent:
                                    last_progress = time.monotonic()
                            except BrokenPipeError:
                                pending = pending[:0]
                                input_stream = None
                        if not pending:
                            if input_stream is not None:
                                pending = memoryview(input_stream.read(transfer_chunk_bytes))
                            if not pending:
                                selector.unregister(key.fileobj); key.fileobj.close()
                        continue
                    raw = os.read(key.fileobj.fileno(), 65536)
                    if not raw:
                        selector.unregister(key.fileobj); key.fileobj.close()
                    elif key.data == "stdout":
                        last_progress = time.monotonic()
                        if sink is not None:
                            sink(raw)
                        else:
                            if len(stdout) + len(raw) > max_output_bytes:
                                raise ValueError("transport response exceeds its byte bound")
                            stdout.extend(raw)
                    else:
                        stderr.extend(raw[:max(0, max_output_bytes - len(stderr))])
        return subprocess.CompletedProcess(command, process.wait(), bytes(stdout), bytes(stderr))
    except BaseException as error:
        # Preserve bytes already observed even when parsing or the sink failed.
        if not getattr(error, "stdout", None):
            error.stdout = bytes(stdout)
        if not getattr(error, "stderr", None):
            error.stderr = bytes(stderr)
        try:
            if process_group:
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.wait()
        raise
    finally:
        if process_group:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


@dataclass
class CollectionContext:
    deadline_monotonic: float
    stop_deadline_monotonic: float
    file_timeout_seconds: float = FILE_SECONDS
    idle_timeout_seconds: float = IDLE_SECONDS
    report_progress: Callable[[dict], None] = field(default=lambda _: None, repr=False)
    stopped: Callable[[], bool] = field(default=lambda: False, repr=False)
    progress_path: str | None = None

    @classmethod
    def for_seconds(cls, seconds: float, **kwargs):
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("collection budget must be finite and positive")
        now = time.monotonic()
        return cls(now + seconds - min(2.0, seconds * .1), now + seconds, **kwargs)

    def remaining_seconds(self) -> float:
        if self.stopped():
            raise InterruptedError("collection stop requested")
        remaining = self.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            error = TimeoutError("collection working budget exhausted")
            error.timeout_kind = "collection_total"
            raise error
        return remaining

    def wire(self) -> dict:
        return {key: getattr(self, key) for key in ("deadline_monotonic", "stop_deadline_monotonic",
            "file_timeout_seconds", "idle_timeout_seconds")}


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def watch_parent(descriptor: int, stop: threading.Event) -> None:
    """A private collector cannot outlive the process owning its pipe."""
    os.environ[_OWNED_GROUP_ENV] = str(os.getpgrp())
    def parent_lost():
        with os.fdopen(descriptor, "rb") as stream:
            stream.read()
        stop.set()
        time.sleep(1)
        os.killpg(os.getpgrp(), signal.SIGKILL)
    threading.Thread(target=parent_lost, daemon=True).start()


def _group_running(group: int, *, report_error=None) -> bool:
    """Observe only our created group; zombies cannot compute or retain FDs."""
    def unknown(error):
        if report_error is not None:
            try:
                report_error(error)
            except Exception:
                pass  # A diagnostic failure never establishes process exit.
        return True
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except OSError as error:
        return unknown(error)
    try:
        if not Path("/proc").is_dir():
            return unknown(OSError("process observation directory is unavailable"))
        with os.scandir("/proc") as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                try:
                    with open(entry.path + "/stat") as stream:
                        fields = stream.read(8192).rsplit(")", 1)[1].split()
                    if int(fields[2]) == group and fields[0] not in {"Z", "X"}:
                        return True
                except (FileNotFoundError, ProcessLookupError):
                    continue
                except (OSError, ValueError, IndexError) as error:
                    return unknown(error)
    except OSError as error:
        return unknown(error)
    return False


def _read_stop(directory: Path) -> dict:
    try:
        value = read_json(directory / "stop.json")
    except FileNotFoundError:
        return {}
    return {target: value[key] for key, target in (("reason", "stop_reason"),
        ("observation_error", "stop_observation_error")) if key in value}


def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except BlockingIOError:
        os.close(descriptor)
        return None


class ExecutionCollection:
    def __init__(self, executions, *, plugin_configs: dict[str, str], child_command=None):
        self.executions = executions
        self.state_root = executions.database_path.parent.parent
        self.plugin_configs = plugin_configs
        self.child_command = child_command or [sys.executable, "-m", __name__]
        self._mutex = threading.RLock()
        self._active = None
        self._closed = False

    def directory(self, execution_id):
        # Caller resolves an existing Execution through the service, never a user path.
        self.executions.status(execution_id)
        return self.executions.exchange_root / execution_id / "collection"

    def summary(self, execution_id):
        directory = self.directory(execution_id)
        try:
            result = read_json(directory / "status.json")
        except FileNotFoundError:
            return {"state": "not_started"}
        except (OSError, ValueError) as error:
            from .engineering_diagnostics import exception_facts
            return {"state": "unknown", "record_error": exception_facts(error,
                layer="collection_status", action="read")}
        try:
            result.update(read_json(directory / "progress.json"))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            from .engineering_diagnostics import exception_facts
            result["progress_error"] = exception_facts(error, layer="collection_progress", action="read")
        try:
            result.update(_read_stop(directory))
        except (OSError, ValueError) as error:
            from .engineering_diagnostics import exception_facts
            result["stop_record_error"] = exception_facts(error, layer="collection_stop", action="read")
        if result.get("state") in {"running", "stopping", "stop_pending"}:
            # Inspect the existing lock without creating a record or starting work.
            try:
                fd = os.open(directory / "active.lock", os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                return {**result, "state": "interrupted", "recovery_pending": False}
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    result.update(state="interrupted", recovery_pending=False)
                except BlockingIOError:
                    result["recovery_pending"] = True
            finally:
                os.close(fd)
        return result

    def collect(self, execution_id, *, scope, total_seconds=COLLECTION_SECONDS,
                file_timeout_seconds=FILE_SECONDS, idle_timeout_seconds=IDLE_SECONDS):
        gate = getattr(self.executions, "instance_maintenance", None)
        lease = None
        if gate is not None:
            with gate.global_guard():
                owner = self.executions.scheduler_bindings.find_owner(namespace="execution", object_id=execution_id)
                # `scope` is a diagnostic label, not an ownership credential.
                # Existing internal callers may use an unscoped label. Exact
                # bindings govern the gate; unowned legacy objects retain only
                # global writer protection and gain no inferred instance.
                lease = gate.acquire_writer(owner[0].instance_id if owner else None)
                if owner is not None:
                    scope = "instance:" + owner[0].instance_id
                    try:
                        self.executions.scheduler_bindings.require_active_instance(instance_id=owner[0].instance_id)
                    except BaseException:
                        lease.close()
                        raise
        try:
            return self._collect_owned(execution_id, scope=scope, total_seconds=total_seconds, maintenance_lease=lease,
                file_timeout_seconds=file_timeout_seconds, idle_timeout_seconds=idle_timeout_seconds)
        finally:
            # Accepted work transfers the independent lease to its supervisor;
            # the request guard may now finish without exposing a write window.
            if lease is not None:
                with self._mutex:
                    transferred = self._active is not None and self._active[-1] is lease
                if not transferred:
                    lease.close()

    def _collect_owned(self, execution_id, *, scope, total_seconds, maintenance_lease,
                       file_timeout_seconds=FILE_SECONDS, idle_timeout_seconds=IDLE_SECONDS):
        with self._mutex:
            status = self.executions.status(execution_id)
            if status.state == "collected":
                return {**self.summary(execution_id), "state": "completed", "accepted": False}
            if status.state not in {"succeeded", "failed", "cancelled"}:
                raise ValueError("collection requires a terminal execution")
            if self._closed:
                raise RuntimeError("collection service is stopping")
            if self._active and self._active[0] == execution_id:
                return {**self.summary(execution_id), "accepted": False}
            directory = self.directory(execution_id)
            owned = _lock(directory / "active.lock")
            if owned is None:
                return {**self.summary(execution_id), "accepted": False}
            try:
                slot = _lock(self.state_root / "collection.lock")
            except BaseException:
                os.close(owned)
                raise
            if slot is None:
                os.close(owned)
                return {"state": "busy", "accepted": False}
            reader = writer = None
            process = None
            try:
                reader, writer = os.pipe()
                context = CollectionContext.for_seconds(total_seconds, file_timeout_seconds=file_timeout_seconds,
                    idle_timeout_seconds=idle_timeout_seconds)
                record = {"state": "running", "started_at": _now(), "updated_at": _now(),
                    "total_seconds": total_seconds, "working_seconds": total_seconds - min(2, total_seconds * .1),
                    "file_timeout_seconds": context.file_timeout_seconds, "idle_timeout_seconds": context.idle_timeout_seconds}
                if (directory / "status.json").exists():
                    previous = "attempt-" + str(time.time_ns())
                    atomic_json(directory / (previous + ".json"), self.summary(execution_id))
                    for name in ("stdout", "stderr"):
                        log = directory / ("process." + name + ".log")
                        if log.exists():
                            log.rename(directory / (previous + "." + name + ".log"))
                atomic_json(directory / "status.json", record)
                (directory / "progress.json").unlink(missing_ok=True)
                (directory / "stop.json").unlink(missing_ok=True)
                atomic_json(directory / "request.json", {"execution_id": execution_id, "scope": scope,
                    "state_root": str(self.state_root), "plugin_configs": self.plugin_configs,
                    "actor": self.executions.service_actor.model_dump(mode="json"), "budget": context.wire(),
                    "parent_fd": reader, "work_command": self.child_command})
                process = subprocess.Popen([sys.executable, "-m", __name__, "--guard", str(directory / "request.json")],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                    pass_fds=(reader, owned, slot) + (maintenance_lease.descriptors if maintenance_lease else ()))
                self._active = (execution_id, process, context, writer, owned, slot, maintenance_lease)
                threading.Thread(target=self._watch, args=(self._active, scope), daemon=True).start()
                return {**record, "accepted": True}
            except BaseException as error:
                if process is not None:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass  # The guard retains both locks until work really stops.
                    process.stdout.close(); process.stderr.close()
                    self._active = None
                if writer is not None:
                    os.close(writer)
                os.close(owned); os.close(slot)
                facts = EngineeringDiagnostics(self.state_root / "engineering-diagnostics").capture(
                    error, scope=scope, layer="collection_process", action="start")
                try:
                    atomic_json(directory / "status.json", {"state": "stop_pending" if process is not None and process.poll() is None else "failed", "updated_at": _now(), "error": facts})
                except (OSError, ValueError):
                    pass  # The original failure retains any diagnostic-storage failure.
                raise
            finally:
                if reader is not None:
                    os.close(reader)

    def _watch(self, active, scope):
        execution_id, process, context, writer, owned, slot = active[:6]
        maintenance_lease = active[6] if len(active) > 6 else None
        directory = self.executions.exchange_root / execution_id / "collection"
        signalled = False
        logs = {"stdout": bytearray(), "stderr": bytearray()}
        streams = {key: getattr(process, key) for key in logs}
        def drain():
            for key, stream in streams.items():
                try:
                    raw = os.read(stream.fileno(), 65536)
                    logs[key].extend(raw[:max(0, 256 * 1024 - len(logs[key]))])
                except BlockingIOError:
                    pass
        try:
            for stream in streams.values():
                os.set_blocking(stream.fileno(), False)
            while process.poll() is None:
                drain()
                now = time.monotonic()
                if self._closed or now >= context.deadline_monotonic:
                    if not signalled:
                        os.killpg(process.pid, signal.SIGTERM)
                        signalled = True
                        reserve = context.stop_deadline_monotonic - context.deadline_monotonic
                        stop_at = min(context.stop_deadline_monotonic, now + reserve / 2)
                    elif now >= stop_at:
                        # The lock owner must survive while its worker is being
                        # killed (OpenSSH does not retain extra inherited FDs).
                        record = read_json(directory / "status.json")
                        record.update(state="stop_pending", updated_at=_now())
                        atomic_json(directory / "status.json", record)
                time.sleep(.02)
            process.wait()
            drain()
            while _group_running(process.pid):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    break
                record = read_json(directory / "status.json")
                record.update(state="stop_pending", updated_at=_now())
                atomic_json(directory / "status.json", record)
                time.sleep(.02)
            record = read_json(directory / "status.json")
            record.update(_read_stop(directory))
            if self.executions.status(execution_id).state == "collected":
                record.update(state="completed", stopped=signalled)
            elif record.get("stop_reason") == "collection_total":
                record.update(state="timed_out", process_stopped=True)
            elif signalled:
                record.update(state="interrupted" if self._closed else "timed_out", process_stopped=True)
            elif record["state"] in {"running", "stop_pending"}:
                record.update(state="failed", exit_code=process.returncode)
            record["updated_at"] = _now()
            if record["state"] in {"failed", "timed_out", "interrupted"} and not record.get("error"):
                error = TimeoutError("collection process exceeded its working budget") if record["state"] == "timed_out" else RuntimeError(
                    f"collection process exited with code {process.returncode}; see bounded process log")
                if isinstance(error, TimeoutError):
                    error.timeout_kind = "collection_total"
                    error.timeout = record["working_seconds"]
                error.stdout, error.stderr = bytes(logs["stdout"]), bytes(logs["stderr"])
                record["error"] = EngineeringDiagnostics(self.state_root / "engineering-diagnostics").capture(
                    error, scope=scope, layer="collection_process", action="collect")
            atomic_json(directory / "status.json", record)
        except Exception as error:
            # A broken progress/log store must never leave unowned work alive.
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            process.wait()
            facts = EngineeringDiagnostics(self.state_root / "engineering-diagnostics").capture(
                error, scope=scope, layer="collection_supervisor", action="stop_and_record")
            try:
                completed = self.executions.status(execution_id).state == "collected"
                atomic_json(directory / "status.json", {"state": "completed" if completed else "failed",
                    "updated_at": _now(), "process_stopped": True, "error": facts})
            except (OSError, ValueError):
                pass
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
            for key, stream in streams.items():
                stream.close()
                try:
                    fd = os.open(directory / ("process." + key + ".log"),
                        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, "wb") as saved:
                        saved.write(logs[key])
                except OSError as error:
                    EngineeringDiagnostics(self.state_root / "engineering-diagnostics").capture(
                        error, scope=scope, layer="collection_supervisor", action="save_process_log")
            if process.poll() is not None:
                os.close(writer); os.close(owned); os.close(slot)
                with self._mutex:
                    if self._active is active:
                        self._active = None
                if maintenance_lease is not None:
                    maintenance_lease.close()

    def close(self):
        self._closed = True
        deadline = time.monotonic() + 2
        with self._mutex:
            active = self._active
        if active:
            try:
                active[1].wait(timeout=max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                # Keep ownership until the supervisor observes actual process exit.
                return False
            # Shutdown includes draining logs and releasing ownership, not just exit.
            while time.monotonic() < deadline:
                with self._mutex:
                    if self._active is None:
                        return True
                time.sleep(.01)
            return False
        return True


def open_collection_executions(state_root: Path, *, actor=None, context=None):
    from .artifacts import ArtifactService
    from .executions import ExecutionService
    from ..schema.refs import ActorRef
    artifacts = ArtifactService.open(cas_root=state_root / "artifacts",
        database_path=state_root / "database/artifact_agent.sqlite3", shared_group=True,
        deadline_monotonic=context.deadline_monotonic if context else None)
    executions = ExecutionService(artifacts=artifacts, approvals=None,
        database_path=state_root / "database/executions.sqlite3", exchange_root=state_root / "execution-exchange",
        service_actor=ActorRef.model_validate(actor or {"actor_id": "root_orchestrator", "actor_type": "service"}),
        deadline_monotonic=context.deadline_monotonic if context else None)
    from .instance_maintenance import InstanceMaintenance
    from .scheduler_bindings import SchedulerBindingService
    executions.instance_maintenance = InstanceMaintenance(state_root)
    executions.scheduler_bindings = SchedulerBindingService(state_root / "database/scheduler-bindings.sqlite3")
    return executions


def _guard(request_path: Path) -> int:
    """Keep control locks outside the group that may need forced termination."""
    request = read_json(request_path)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    def parent_lost():
        with os.fdopen(request["parent_fd"], "rb", closefd=False) as stream:
            stream.read()
        stop.set()
    threading.Thread(target=parent_lost, daemon=True).start()
    context = CollectionContext(**request["budget"], stopped=stop.is_set)
    stop_record = {}
    def record_stop(**facts):
        stop_record.update(facts, observed_at=_now())
        try:
            atomic_json(request_path.parent / "stop.json", stop_record)
        except OSError as error:
            EngineeringDiagnostics(Path(request["state_root"]) / "engineering-diagnostics").capture(
                error, scope=request["scope"], layer="collection_guard", action="save_stop_reason")
    def observation_failed(error):
        if "observation_error" not in stop_record:
            facts = EngineeringDiagnostics(Path(request["state_root"]) / "engineering-diagnostics").capture(
                error, scope=request["scope"], layer="collection_guard", action="observe_stop")
            record_stop(observation_error=facts)
    try:
        context.remaining_seconds()
    except TimeoutError:
        record_stop(reason="collection_total")
        return 1
    # Only the guard inherits the daemon's two flock descriptors. Work and
    # native transports may close any extra FD without releasing ownership.
    process = subprocess.Popen([*request["work_command"], str(request_path)],
        stdin=subprocess.DEVNULL, start_new_session=True, pass_fds=(request["parent_fd"],))
    stopping_at = None
    try:
        while process.poll() is None or _group_running(process.pid, report_error=observation_failed):
            now = time.monotonic()
            if stop.is_set() or now >= context.deadline_monotonic or process.poll() is not None:
                if stopping_at is None:
                    stopping_at = now + (context.stop_deadline_monotonic - context.deadline_monotonic) / 2
                    if stop.is_set() or now >= context.deadline_monotonic:
                        # A single-writer receipt preserves the actual stopping
                        # cause even when the daemon watcher is scheduled late.
                        record_stop(reason="collection_total" if now >= context.deadline_monotonic else "control_stop")
                sig = signal.SIGTERM if now < stopping_at and process.poll() is None else signal.SIGKILL
                try:
                    os.killpg(process.pid, sig)
                except OSError:
                    pass
            time.sleep(.02)
        return process.wait()
    finally:
        # This small control owner never executes adapter code. On any internal
        # failure it still retains its locks until its actual group has stopped.
        while process.poll() is None or _group_running(process.pid, report_error=observation_failed):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            time.sleep(.02)
        process.wait()


def _child(request_path: Path) -> int:
    request = read_json(request_path)
    directory = request_path.parent
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    watch_parent(request["parent_fd"], stop)
    state_root = Path(request["state_root"])
    context = CollectionContext(**request["budget"], stopped=stop.is_set,
        report_progress=lambda value: atomic_json(directory / "progress.json", {**value, "updated_at": _now()}),
        progress_path=str(directory / "progress.json"))
    from .maintenance import StateMaintenanceLock
    from ..schema.execution import LocalFileDescriptor
    from ..runtime_plugin_bindings import load_runtime_plugin_contributions
    from scidiscovery.operations.catalog import compile_installed_catalog
    try:
        with StateMaintenanceLock(state_root / "maintenance.lock", shared_group=True).shared():
            context.remaining_seconds()
            executions = open_collection_executions(state_root, actor=request["actor"], context=context)
            current = executions.status(request["execution_id"])
            checkpoint = directory / "outputs.json"
            if checkpoint.exists():
                frozen = read_json(checkpoint, max_bytes=4 * 1024 * 1024)
                outputs = tuple(LocalFileDescriptor.model_validate(x) for x in frozen["outputs"])
            else:
                runtime = load_runtime_plugin_contributions(compile_installed_catalog(),
                    {k: Path(v) for k, v in request["plugin_configs"].items()}, mode="control", state_root=state_root)
                adapter = runtime.execution_adapters[current.executor]
                collect = getattr(adapter, "collect_with_budget", None)
                outputs = collect(current.external_run_id, context=context) if callable(collect) else adapter.collect(current.external_run_id)
                context.remaining_seconds()
                frozen = {"outputs": [x.model_dump(mode="json") for x in outputs], "collected_at": _now()}
                atomic_json(checkpoint, frozen)
            executions.ingest_result(execution_id=current.execution_id, external_run_id=current.external_run_id,
                outputs=outputs, collected_at=frozen["collected_at"], context=context)
        return 0
    except Exception as error:
        record = read_json(directory / "status.json")
        record.update(state="timed_out" if isinstance(error, TimeoutError) else "interrupted" if isinstance(error, InterruptedError) else "failed",
            error=EngineeringDiagnostics(state_root / "engineering-diagnostics").capture(error,
                scope=request["scope"], layer="collection", action="collect"), updated_at=_now())
        atomic_json(directory / "status.json", record)
        return 1


if __name__ == "__main__":
    raise SystemExit(_guard(Path(sys.argv[2])) if sys.argv[1] == "--guard" else _child(Path(sys.argv[1])))
