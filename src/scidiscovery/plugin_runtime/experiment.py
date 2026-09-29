"""Task-scoped experiment tool contract; no coordinator or service ownership."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
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
    def source_alias(self, context, ref: ArtifactRef) -> str: ...
    def diagnostic_context(self, context, *, service_name: str): ...
    def cancel_diagnostics(self, context, *, service_name: str, name: str) -> bool: ...
    def command(self, context, request) -> dict: ...


def progress_summary(progress: dict, *, include_log_text: bool = False) -> dict:
    """Timing and log metadata; only UI callers opt into bounded log text."""
    from .diagnostics import redact
    if not isinstance(progress, dict):
        return {}

    def text(value):
        # Redact before truncating so a partial path/credential cannot lose its context.
        value = redact(value)
        return re.sub(r"\b(?:run|exe|apr|art|sch)_[A-Za-z0-9_-]+\b", "[control-id]", value)

    result = {}
    for key in ("observed_at", "started_at", "completed_at"):
        if isinstance(progress.get(key), str):
            result[key] = text(progress[key])[:64]
    elapsed = progress.get("elapsed_seconds")
    if type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0:
        result["elapsed_seconds"] = elapsed
    if progress.get("log_cache_state") == "released":
        result["log_cache_state"] = "released"
    logs = progress.get("log_tails")
    if isinstance(logs, list):
        result["log_activity"] = []
        result["log_count"] = len(logs)
        result["log_details_omitted"] = bool(logs)
        for index, log in enumerate(logs[:2]):
            if not isinstance(log, dict):
                continue
            item = {"log_index": index}
            for key in ("source", "updated_at"):
                if isinstance(log.get(key), str):
                    item[key] = text(log[key])[:64]
            if type(log.get("size_bytes")) is int and log["size_bytes"] >= 0:
                item["size_bytes"] = log["size_bytes"]
            if include_log_text and isinstance(log.get("tail"), str):
                lines = text(log["tail"]).splitlines()
                last = next((line for line in reversed(lines) if line.strip()), "")
                item.update(last_line=last[:256], last_line_truncated=len(last) > 256)
            result["log_activity"].append(item)
    return result


__all__ = ["ExperimentMethod", "SealedImplementation", "ExperimentTools", "progress_summary"]
