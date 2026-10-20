"""Small UI-only snapshot cache and bounded same-origin SSE transport.

The cache stores canonical shared reads, never browser credentials or rendered
forms. Transport subscriptions do not run, resume or qualify scientific work.
"""
from __future__ import annotations

import json
import threading
import time


INTERVAL = 2.0
MAX_EVENT_BYTES = 262144
MAX_CLIENTS = 16
STREAM_SECONDS = 24.0


class SnapshotCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.checked = self.loaded = 0.0
        self.value = None

    def read(self, root, load, *, force=False):
        with self.lock:
            now = time.monotonic()
            if not force and self.value is not None and now - self.checked < INTERVAL:
                return self.value
            value = load()
            self.value, self.checked, self.loaded = value, now, now
            return self.value


class Stream:
    """One finite connection; EventSource reconnects with a fresh full snapshot."""
    def __init__(self, snapshot, *, stop, gate):
        self.snapshot = snapshot
        self.stop = stop
        self.gate = gate
        self.mount = ''

    def write(self, destination):
        if not self.gate.acquire(blocking=False):
            # Headers are already sent: retry via the browser's ordinary SSE
            # reconnect, without spawning any background watcher.
            destination.write(b'retry: 4000\n\n')
            destination.flush()
            return
        try:
            deadline = time.monotonic() + STREAM_SECONDS
            previous = None
            destination.write(b'retry: 1500\n\n')
            while not self.stop.is_set() and time.monotonic() < deadline:
                value = self.snapshot(self.mount, force=previous is None)
                encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
                if len(encoded) > MAX_EVENT_BYTES:
                    raise ValueError('Public workbench snapshot exceeds its transport budget')
                if encoded != previous:
                    destination.write(b'event: snapshot\ndata: ' + encoded + b'\n\n')
                    previous = encoded
                else:
                    destination.write(b': connected\n\n')
                destination.flush()
                if self.stop.wait(INTERVAL):
                    break
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except (PermissionError, ValueError, OSError, KeyError, TypeError, RuntimeError):
            # After headers, report only a generic public failure. Private
            # paths, cookies and control originals never enter stream errors.
            try:
                destination.write(b'event: unavailable\ndata: {}\n\n')
                destination.flush()
            except (OSError, TimeoutError):
                pass
        finally:
            self.gate.release()
