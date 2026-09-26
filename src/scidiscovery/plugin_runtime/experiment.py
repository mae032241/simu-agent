"""Task-scoped experiment tool contract; no coordinator or service ownership."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from ..artifact_agent.schema.refs import ArtifactRef


class ExperimentMethod(Protocol):
    key: str
    content: bytes


@dataclass(frozen=True, slots=True)
class SealedImplementation:
    """Exact control-verified package bytes and their immutable reference."""
    artifact_ref: ArtifactRef
    content: bytes


class ExperimentTools(Protocol):
    def capabilities(self, context) -> tuple[ExperimentMethod, ...]: ...
    def seal_implementation(self, context, *, payload: bytes, scientific_material: bytes,
                            sources: tuple[str, ...], private_outputs: tuple[str, ...] = ()) -> dict: ...
    def read_implementation(self, context, alias: str) -> SealedImplementation: ...
    def diagnostic_context(self, context, *, service_name: str): ...
    def cancel_diagnostics(self, context, *, service_name: str, name: str) -> bool: ...
    def command(self, context, request) -> dict: ...


__all__ = ["ExperimentMethod", "SealedImplementation", "ExperimentTools"]
