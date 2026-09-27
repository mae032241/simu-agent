"""Bounded adapter process IO and supplied deadlines; no Run or supervisor authority."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import os
import signal
import selectors
import subprocess
import threading
import time
from typing import Callable

__all__ = ["CollectionContext", "run_bounded", "watch_parent", "QUERY_SECONDS", "COLLECTION_SECONDS", "FILE_SECONDS", "IDLE_SECONDS"]

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
