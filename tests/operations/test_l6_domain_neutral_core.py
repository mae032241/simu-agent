from __future__ import annotations

import json

from pydantic import TypeAdapter

from scidiscovery.artifact_agent.schema.research_cycle import (
    ArtifactKind,
)
def test_core_scientific_kinds_accept_plugin_identifiers() -> None:
    assert TypeAdapter(ArtifactKind).validate_python(
        "protein_sequence_review", strict=True
    ) == "protein_sequence_review"
    schemas = json.dumps(
        {
            "artifact_kind": TypeAdapter(ArtifactKind).json_schema(),
        },
        sort_keys=True,
    ).lower()
    assert "deck" not in schemas
    assert "tcad" not in schemas
