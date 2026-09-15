"""Execution preferences; independent of scientific contracts and qualifications."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["zh-CN", "en"]
ReasoningEffort = Literal["low", "medium", "high", "xhigh", "max", "ultra"]

# These exact ALTER definitions also delimit old archive compatibility.
EXECUTION_SETTINGS_COLUMNS = {
    "scheduler_instances": {
        "agent_settings_json": ("TEXT DEFAULT NULL", None),
        "agent_settings_revision": ("INTEGER DEFAULT 0", 0),
        "agent_settings_updated_at": ("TEXT DEFAULT NULL", None),
    },
    "runs": {"execution_profile_json": ("TEXT DEFAULT NULL", None)},
}


class SettingsValue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OperationSettings(SettingsValue):
    model: str | None = Field(default=None, min_length=1, max_length=256)
    reasoning_effort: ReasoningEffort | None = None
    max_attempts: int | None = Field(default=None, ge=1)


class DefaultSettings(OperationSettings):
    narrative_language: Language | None = None


class AgentSettings(SettingsValue):
    schema_version: Literal[1] = 1
    defaults: DefaultSettings = Field(default_factory=DefaultSettings)
    operations: dict[str, OperationSettings] = Field(default_factory=dict)

    def sparse(self) -> dict:
        return self.model_dump(exclude_none=True, exclude_defaults=True)


class ExecutionProfile(SettingsValue):
    model: str = Field(min_length=1, max_length=256)
    reasoning_effort: ReasoningEffort
    narrative_language: Language


def parse_settings(value: dict, *, label: str = "agent settings") -> AgentSettings:
    """Missing fields inherit; explicit null is never another spelling of missing."""
    def reject_null(item, path):
        if item is None:
            raise ValueError(f"{label}:{path}: omit an override to inherit; null is invalid")
        if isinstance(item, dict):
            for key, child in item.items():
                reject_null(child, f"{path}.{key}")
    reject_null(value, "$")
    try:
        return AgentSettings.model_validate(value)
    except ValueError as error:
        raise ValueError(f"{label}: {error}") from error


def load_settings(path: Path | str | None) -> AgentSettings:
    if path is None:
        return AgentSettings()
    source = Path(path).expanduser()
    try:
        raw = source.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AgentSettings()
    except UnicodeError as error:
        raise ValueError(f"{source}: {error}") from error
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise ValueError(f"{source}: {error}") from error
    return parse_settings(value, label=str(source))


def resolve_settings(global_settings: AgentSettings, instance_settings: AgentSettings,
                     *, operation_id: str, operation_model: str,
                     operation_max_attempts: int) -> dict:
    values = dict(model=operation_model, reasoning_effort="medium",
                  narrative_language="en", max_attempts=operation_max_attempts)
    sources = {key: "operation_default" if key in {"model", "max_attempts"}
               else "compatibility_default" for key in values}
    for source, settings in (("global", global_settings), ("instance", instance_settings)):
        for suffix, item in (("defaults", settings.defaults),
                             ("operation", settings.operations.get(operation_id))):
            if item is not None:
                for key, value in item.model_dump(exclude_none=True).items():
                    values[key] = value
                    sources[key] = source + "." + suffix
    return {"profile": ExecutionProfile(**{key: values[key] for key in ExecutionProfile.model_fields}),
            "max_attempts": values["max_attempts"], "sources": sources}


def narrative_instruction(profile: dict | None) -> str | None:
    if profile is None:
        return None
    language = "简体中文" if profile["narrative_language"] == "zh-CN" else "English"
    return (f"Write newly authored goals, summaries, conclusions, reasons, limitations and suggestions in {language}. "
            "Preserve field names, enums, identifiers, formulas, code, units, quotations and any text "
            "the scientific contract requires copying exactly. Do not translate historical inputs or "
            "produce a second report. Language is a writing preference, not an output acceptance rule.")
