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
        return self._read_input(name)

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
