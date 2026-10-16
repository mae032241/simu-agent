"""Pure execution contracts shared by registered implementations and callers."""
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
from .runtime_plugins import RuntimePluginFactory

LOCAL_RESULT_PROTOCOL = 'scidiscovery.local-result.v1'


@dataclass(frozen=True)
class AdapterCapability:
    key: str
    kind: str
    schema_id: str
    payload_schema_version: int
    media_type: str
    content: bytes
    public_summary: Mapping[str, object]


@dataclass(frozen=True)
class LifecycleCapabilities:
    lookup_submission: bool = False
    query: bool = False
    cancel: bool = False
    collect: bool = False
    resume_original: bool = False
    atomic_admission: bool = False

    def __post_init__(self):
        if any(type(value) is not bool for value in vars(self).values()):
            raise ValueError('Lifecycle capabilities require explicit boolean declarations')


@dataclass(frozen=True)
class ExecutionInterfaceRegistration:
    """CLI discovery of the existing runtime factory contract; no daemon startup."""
    plugin_id: str
    version: str
    factory: RuntimePluginFactory


class ExecutionAdapter(Protocol):
    def capabilities(self) -> tuple[AdapterCapability, ...]: ...
    def prepare(self, payload: LocalFileDescriptor, *, preparation_profile: str,
                exchange_directory: Path) -> LocalFileDescriptor: ...
    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]: ...
    def lookup_submission(self, submission: LocalFileDescriptor) -> tuple[str, str] | None: ...
    def status(self, external_run_id: str) -> str: ...
    def cancel(self, external_run_id: str) -> str: ...
    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]: ...


class ManagedExecutionInterface(ExecutionAdapter, Protocol):
    """Explicit thin-loop binding, common receipt owner and public observation seam.

    Descriptor inputs may be source files or opaque job packages. CLI --script is
    a convenience of the bundled local implementations, not a backend constraint.
    status_details and result validate the backend's original terminal evidence;
    result retains exact proof descriptors. Control freezes their consistent
    terminal projection and collect_original descriptors before scientific sealing.
    Scientific readers never re-query a backend. Local implementations declare
    terminal_evidence_kind='local_process' and retain cleanup/transport/exit proofs;
    other implementations use their own terminal evidence without POSIX receipts.
    result_protocol is an optional explicit declaration frozen by control; private
    result fields never imply the local result/candidate protocol. The CLI's
    explicit reconcile action freezes an original async terminal observation using
    query and optional declared collection; query itself does not collect or submit.
    """
    def lifecycle_capabilities(self) -> LifecycleCapabilities: ...
    def code_assets(self) -> tuple[str, ...]: ...
    def acceptance_metadata(self, payload: LocalFileDescriptor, *, parent=None, new=False, change=None) -> dict: ...
    def dispatch_lease(self, accepted: dict) -> None: ...
    def status_details(self, call_id: str) -> dict: ...
    def result(self, call_id: str) -> dict: ...
    def collect_original(self, call_id: str) -> tuple[LocalFileDescriptor, ...]: ...
    def cancel_original(self, call_id: str) -> str: ...
    def public_result(self, result: dict) -> dict: ...


MANAGED_METHODS = ('capabilities','prepare','submit','lookup_submission','status','cancel','collect',
    'code_assets','acceptance_metadata','dispatch_lease','status_details','result','public_result',
    'collect_original','cancel_original')


def lifecycle_capabilities(adapter):
    """Missing declarations grant no lifecycle operation; never probe a backend."""
    declaration = getattr(adapter, 'lifecycle_capabilities', None)
    value = declaration() if callable(declaration) else LifecycleCapabilities()
    if not isinstance(value, LifecycleCapabilities):
        raise ValueError('Registered execution lifecycle declaration is invalid')
    return value
