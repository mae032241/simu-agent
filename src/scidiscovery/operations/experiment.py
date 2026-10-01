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
    # Optional collected JSON inventory: outputs[{name, relative_path,
    # sha256, size_bytes, media_type}]. Only verified relative filenames are
    # projected to scientific receipts; the original stays control-owned.
    output_inventory_name: str | None = None


EXPERIMENT_PROTOCOL = "scidiscovery.complete-experiment.v1"
