"""Content-bound reference schemas."""

from __future__ import annotations

from .common import Identifier, SchemaModel, Sha256


class ActorRef(SchemaModel):
    """Stable identity of the human, service, or agent that performed an action."""

    actor_id: Identifier
    actor_type: Identifier


class ArtifactRef(SchemaModel):
    """Complete identity required to resolve one immutable artifact payload."""

    artifact_id: Identifier
    sha256: Sha256
    kind: Identifier
    schema_id: Identifier
