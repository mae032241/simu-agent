"""Small scientific handoff signal emitted by one completed Agent Run."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import SchemaModel


class SchedulerSignal(SchemaModel):
    """Bounded handoff metadata; scientific content remains in the Artifact."""

    verdict: Literal["pass", "revise", "blocked", "inconclusive"]
    summary: Annotated[str, Field(min_length=1, max_length=2048)]
    assumptions: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    next_actions: Annotated[tuple[str, ...], Field(max_length=32)] = ()


__all__ = ["SchedulerSignal"]
