"""Runtime-factory protocol referenced by the immutable Operation catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Literal, Mapping


@dataclass(frozen=True, slots=True)
class RuntimePluginContext:
    """Startup context for installed trusted control-runtime code."""

    plugin_id: str
    mode: Literal["control", "local_worker"]
    config_path: Path
    config_bytes: bytes
    state_root: Path


@dataclass(frozen=True, slots=True)
class RuntimePluginContribution:
    execution_adapters: Mapping[str, Any] = field(default_factory=dict)
    tool_services: Mapping[str, Any] = field(default_factory=dict)
    reconcilers: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        adapters = dict(self.execution_adapters)
        services = dict(self.tool_services)
        if any(
            not key or value is None
            for key, value in (*adapters.items(), *services.items())
        ):
            raise ValueError("runtime plugin contribution contains an invalid binding")
        if len(self.reconcilers) != len({id(item) for item in self.reconcilers}):
            raise ValueError("runtime plugin contribution repeats a reconciler")
        object.__setattr__(self, "execution_adapters", MappingProxyType(adapters))
        object.__setattr__(self, "tool_services", MappingProxyType(services))


@dataclass(frozen=True, slots=True)
class RuntimePluginFactory:
    """One installed, trusted startup factory; not an Agent capability."""

    build: Callable[[RuntimePluginContext], RuntimePluginContribution]
    def __post_init__(self) -> None:
        if not callable(self.build):
            raise TypeError("runtime plugin factory must be callable")


__all__ = [
    "RuntimePluginContext",
    "RuntimePluginContribution",
    "RuntimePluginFactory",
]
