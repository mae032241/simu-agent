"""Deterministic task-context policies enforced before worker dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


ContextExposure = Literal["full", "on_demand", "handoff_only"]
ContextUsage = Literal[
    "claim_evidence",
    "revision_base",
    "change_request",
    "prior_signal",
    "cached_excerpt",
    "unchanged_set_receipt",
    "evidence_inventory",
]


@dataclass(frozen=True)
class ContextInputRule:
    source_name: str
    exposure: ContextExposure
    required: bool = True
    schemas: tuple[str, ...] = ()
    max_bytes: int | None = None
    usage: ContextUsage | None = None

    def __post_init__(self) -> None:
        if not self.source_name:
            raise ValueError("context input source name is required")
        if self.exposure not in {"full", "on_demand", "handoff_only"}:
            raise ValueError("context input exposure is invalid")
        if self.max_bytes is not None and self.max_bytes < 1:
            raise ValueError("context input byte limit is invalid")
        if self.usage is not None and self.usage not in {
            "claim_evidence",
            "revision_base",
            "change_request",
            "prior_signal",
            "cached_excerpt",
            "unchanged_set_receipt",
            "evidence_inventory",
        }:
            raise ValueError("context input usage is invalid")


@dataclass(frozen=True)
class TaskContextPolicy:
    rules: tuple[ContextInputRule, ...] = ()
    allow_additional: bool = True
    max_inputs: int = 32
    max_readable_bytes: int = 64 * 1024 * 1024
    additional_usages: tuple[ContextUsage, ...] | None = None

    def __post_init__(self) -> None:
        names = tuple(rule.source_name for rule in self.rules)
        if len(names) != len(set(names)):
            raise ValueError("context policy source names must be unique")
        if self.max_inputs < 0 or self.max_readable_bytes < 0:
            raise ValueError("context policy limits are invalid")
        if self.additional_usages is not None and len(
            self.additional_usages
        ) != len(set(self.additional_usages)):
            raise ValueError("additional context usages must be unique")


@dataclass(frozen=True)
class RoleContextPolicies:
    profiles: Mapping[str, TaskContextPolicy]
    default_profile: str | None = None

    def __post_init__(self) -> None:
        frozen = MappingProxyType(dict(self.profiles))
        if not frozen:
            raise ValueError("role context policies require at least one profile")
        if self.default_profile is not None and self.default_profile not in frozen:
            raise ValueError("default context profile is not registered")
        object.__setattr__(self, "profiles", frozen)

    def resolve(self, requested: str | None) -> tuple[str, TaskContextPolicy]:
        profile = requested if requested is not None else self.default_profile
        if profile is None:
            raise ValueError("role requires an explicit context profile")
        try:
            return profile, self.profiles[profile]
        except KeyError as error:
            raise ValueError(f"unsupported context profile: {profile}") from error


DEFAULT_CONTEXT_POLICIES = RoleContextPolicies(
    profiles={"default": TaskContextPolicy()}, default_profile="default"
)


__all__ = [
    "ContextExposure",
    "ContextInputRule",
    "ContextUsage",
    "DEFAULT_CONTEXT_POLICIES",
    "RoleContextPolicies",
    "TaskContextPolicy",
]
