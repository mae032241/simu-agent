"""Backend-neutral capabilities exposed to one registered Operation tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping, MutableMapping

from .schema.refs import ArtifactRef


@dataclass(frozen=True, slots=True)
class OperationToolContext:
    services: Mapping[str, object]
    state: MutableMapping[str, object]
    workspace: Path
    output_directory: Path
    output_collections: tuple[str, ...]
    remaining_seconds: int
    _read_input: Callable[[str], bytes]
    _input_path: Callable[[str], Path]
    _input_media_type: Callable[[str], str]
    _input_ref: Callable[[str], ArtifactRef]
    _validate_outputs: Callable[[], None]
    _record_activity: Callable[[str], None]
    _candidate_snapshot: Callable[[], tuple[str, ...]]

    _read_evidence: Callable[[str], bytes] | None = None
    _accept_evidence: Callable[..., dict] | None = None
    _list_evidence: Callable[[], list[dict]] | None = None
    _execution_scope: Callable[[str], dict] | None = None
    _io_budget: Callable[..., dict] | None = None
    _source_read: Callable[[str], None] | None = None
    _source_descriptor: Callable[[str], object] | None = None
    _finish_attempt: Callable[..., tuple[dict, tuple[dict, ...]] | None] | None = None
    _prior_source_bindings: Callable[[], Mapping[str, str]] | None = None

    @property
    def prior_source_bindings(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self._prior_source_bindings())) if self._prior_source_bindings else MappingProxyType({})

    def source_descriptor(self, name: str):
        if self._source_descriptor is None:
            raise ValueError("tool has no source descriptor projection")
        return self._source_descriptor(name)

    def finish_attempt(self, **values) -> tuple[dict, tuple[dict, ...]] | None:
        return self._finish_attempt(**values) if self._finish_attempt else None

    def io_budget(self, **values):
        if self._io_budget is None:
            raise ValueError("tool has no evidence budget")
        return self._io_budget(**values)

    def evidence(self) -> list[dict]:
        return self._list_evidence() if self._list_evidence else []

    def read_evidence(self, name: str) -> bytes:
        raw = self._read_evidence(name) if self._read_evidence else self.read_input(name)
        if self._source_read: self._source_read(name)
        return raw

    def accept_evidence(self, **values) -> dict:
        if self._accept_evidence is None:
            raise ValueError("tool has no evidence collection permission")
        return self._accept_evidence(**values)

    def execution_scope(self, alias: str) -> dict:
        if self._execution_scope is None:
            raise ValueError("tool has no execution inspection permission")
        return self._execution_scope(alias)

    def __post_init__(self) -> None:
        object.__setattr__(self, "services", MappingProxyType(dict(self.services)))

    def require_service(self, name: str) -> object:
        try:
            return self.services[name]
        except KeyError as error:
            raise RuntimeError(
                f"registered Operation service is unavailable: {name}"
            ) from error

    def read_input(self, name: str) -> bytes:
        raw = self._read_input(name)
        if self._source_read: self._source_read(name)
        return raw

    def input_path(self, name: str) -> Path:
        return self._input_path(name)

    def input_media_type(self, name: str) -> str:
        return self._input_media_type(name)

    def input_ref(self, name: str) -> ArtifactRef:
        """Return the immutable scientific identity of one declared input."""

        return self._input_ref(name)

    def validate_outputs(self) -> None:
        self._validate_outputs()

    def record_activity(self, activity: str) -> None:
        self._record_activity(activity)

    def candidate_snapshot(self) -> tuple[str, ...]:
        return self._candidate_snapshot()


__all__ = ["OperationToolContext"]
