"""Bounded SQLite waits and independent nonblocking control file locks."""
from contextlib import contextmanager
from contextvars import ContextVar
import sqlite3
import time


# Only the coordinator opts in. Request/maintenance callers retain their usual
# blocking semantics; nested service calls inherit the same observation policy.
_CONTROL_NONBLOCKING = ContextVar('control_nonblocking', default=False)
_DATABASE_WAIT = ContextVar('control_database_wait', default=None)
_CONTROL_REMAINING = ContextVar('control_remaining', default=None)


@contextmanager
def bounded_control_io(*, wait_seconds, remaining_seconds):
    """Inherit the tightest observation deadline without extending a parent."""
    parent = _DATABASE_WAIT.get()
    parent_remaining = _CONTROL_REMAINING.get()
    def remaining():
        return max(0., min(remaining_seconds(),
            parent_remaining() if parent_remaining is not None else float('inf')))
    def wait():
        return max(0., min(wait_seconds(), remaining(), parent() if parent is not None else float('inf')))
    token = _CONTROL_NONBLOCKING.set(True)
    database_token = _DATABASE_WAIT.set(wait)
    remaining_token = _CONTROL_REMAINING.set(remaining)
    try:
        yield
    finally:
        _CONTROL_REMAINING.reset(remaining_token)
        _DATABASE_WAIT.reset(database_token)
        _CONTROL_NONBLOCKING.reset(token)


def control_io_nonblocking():
    """File locks never inherit SQLite's short blocking wait."""
    return _CONTROL_NONBLOCKING.get()


def control_io_remaining():
    remaining = _CONTROL_REMAINING.get()
    return remaining() if remaining is not None else float('inf')


def connect_database(path, *, timeout=5., deadline_monotonic=None, **kwargs):
    """Use the normal caller timeout outside the coordinator's control scope."""
    wait = _DATABASE_WAIT.get()
    if wait is None:
        return sqlite3.connect(path, timeout=timeout, **kwargs)
    connection = sqlite3.connect(path, timeout=min(timeout, wait()), factory=_ControlConnection, **kwargs)
    connection._control_wait = wait
    connection._caller_timeout = timeout
    connection._deadline_monotonic = deadline_monotonic
    connection._busy_timeout_ms = None
    connection._refresh_wait()
    return connection


class _ControlConnection(sqlite3.Connection):
    def _refresh_wait(self):
        timeout = min(self._caller_timeout, self._control_wait())
        if self._deadline_monotonic is not None:
            timeout = min(timeout, self._deadline_monotonic - time.monotonic())
        milliseconds = max(0, int(timeout * 1000))
        if milliseconds != self._busy_timeout_ms:
            sqlite3.Connection.execute(self, f'PRAGMA busy_timeout = {milliseconds}')
            self._busy_timeout_ms = milliseconds

    def cursor(self, factory=None):
        return super().cursor(factory=factory or _ControlCursor)

    def execute(self, *args):
        return self.cursor().execute(*args)

    def executemany(self, *args):
        return self.cursor().executemany(*args)

    def commit(self):
        self._refresh_wait()
        return super().commit()

    def __exit__(self, *args):
        # SQLite's C context manager bypasses the Python commit override.
        # Expiry sets zero wait; it must not prevent rollback or cleanup.
        self._refresh_wait()
        return super().__exit__(*args)


class _ControlCursor(sqlite3.Cursor):
    def execute(self, *args):
        self.connection._refresh_wait()
        return super().execute(*args)

    def executemany(self, *args):
        self.connection._refresh_wait()
        return super().executemany(*args)

    def fetchone(self):
        self.connection._refresh_wait()
        return super().fetchone()

    def fetchmany(self, *args):
        self.connection._refresh_wait()
        return super().fetchmany(*args)

    def fetchall(self):
        self.connection._refresh_wait()
        return super().fetchall()

    def __next__(self):
        self.connection._refresh_wait()
        return super().__next__()
