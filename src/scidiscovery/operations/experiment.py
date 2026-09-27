"""The single compiled contribution boundary for a complete experiment task."""
from dataclasses import dataclass

from .spec import ComponentRef


@dataclass(frozen=True, slots=True)
class ExperimentCapability:
    """Installed domain code; selection is configuration, never a Worker choice."""

    tools: tuple[ComponentRef, ...]
    instructions: str
    execution_operation: str
    execution_package_schema_version: int


EXPERIMENT_PROTOCOL = "scidiscovery.complete-experiment.v1"
