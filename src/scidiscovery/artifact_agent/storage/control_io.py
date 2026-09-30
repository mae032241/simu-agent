"""Opt-in nonblocking control observation across synchronous storage calls."""
from contextlib import contextmanager
from contextvars import ContextVar


# Only the coordinator opts in. Request/maintenance callers retain their usual
# blocking semantics; nested service calls inherit the same observation policy.
_CONTROL_NONBLOCKING = ContextVar('control_nonblocking', default=False)


@contextmanager
def nonblocking_control_io():
    token = _CONTROL_NONBLOCKING.set(True)
    try:
        yield
    finally:
        _CONTROL_NONBLOCKING.reset(token)


def control_io_nonblocking():
    return _CONTROL_NONBLOCKING.get()
