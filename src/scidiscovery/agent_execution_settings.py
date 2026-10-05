"""Execution preferences; independent of scientific contracts and qualifications."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Language = Literal["zh-CN", "en"]
ReasoningEffort = Literal["low", "medium", "high", "xhigh", "max", "ultra"]


def canonical_model_id(value: str | None) -> str | None:
    """Use the platform's case-insensitive model identity without changing punctuation."""
    return value.casefold() if value is not None else None

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


class HelperProfileSettings(SettingsValue):
    model: str | None = Field(default=None, min_length=1, max_length=256)
    reasoning_effort: ReasoningEffort | None = None
    max_calls: int | None = Field(default=None, ge=0, le=32)
    max_input_bytes: int | None = Field(default=None, ge=512, le=262144)


def packaged_helper_profiles() -> dict:
    source = Path(__file__).with_name("default_agent_settings.json")
    values = json.loads(source.read_text(encoding="utf-8"))["helpers"]["profiles"]
    return {name: HelperProfileSettings.model_validate(value) for name, value in values.items()}


class HelperSettings(SettingsValue):
    """Run tool admissions and frozen model choices, not native token hard limits."""
    default_profile: Literal["inherit", "lightweight"] = "inherit"
    profiles: dict[Literal["lightweight"], HelperProfileSettings] = Field(default_factory=packaged_helper_profiles)
    max_depth: Literal[0, 1] = 1
    max_active: Literal[0, 1] = 1
    max_calls: int = Field(default=4, ge=0, le=32)
    max_input_bytes: int = Field(default=32768, ge=512, le=262144)


def merge_helper_settings(base: dict, override: dict) -> dict:
    """Instance profile fields inherit global values; explicit empty profiles disables them."""
    result = {**base, **{key:value for key,value in override.items() if key != "profiles"}}
    if "profiles" in override:
        profiles = dict(base.get("profiles", {})) if override["profiles"] else {}
        for name, value in override["profiles"].items():
            profiles[name] = {**profiles.get(name, {}), **value}
        result["profiles"] = profiles
    return HelperSettings.model_validate(result).model_dump()


class ExecutionIOSettings(SettingsValue):
    """Transfer limits frozen per Run; separate from solver authorization and RAM."""
    max_export_bytes: int = Field(default=2_000_000_000, ge=1)
    read_page_bytes: int = Field(default=16384, ge=512, le=262144)
    collection_timeout_seconds: int = Field(default=600, ge=1)
    file_timeout_seconds: int = Field(default=120, ge=1)
    idle_timeout_seconds: int = Field(default=30, ge=1)
    submission_response_wait_seconds: float = Field(default=0.25, ge=0, le=2, allow_inf_nan=False)
    approval_wait_budget_seconds: int = Field(default=86400, ge=0)


class BudgetExtensionSettings(SettingsValue):
    """Administrator limits on new human time grants; historical decisions persist."""
    max_seconds_per_decision: int = Field(default=21600, ge=0, le=2**53-1)
    max_total_seconds_per_pool: int = Field(default=86400, ge=0, le=2**53-1)


class LifecycleSettings(SettingsValue):
    """Control daemon reconciliation; global settings, no model calls or submissions."""
    interval_seconds: int = Field(default=30, ge=1, le=3600)
    batch_size: int = Field(default=32, ge=1, le=256)
    terminal_observation_failure_limit: int = Field(default=3, ge=1, le=1000)


class MaterialInputSettings(SettingsValue):
    """Stored material budgets are separate from in-memory delivery thresholds."""
    max_item_bytes: int = Field(default=2_000_000_000, ge=1)
    max_total_bytes: int = Field(default=2_000_000_000, ge=1)
    inline_max_bytes: int = Field(default=1048576, ge=1)
    inline_total_bytes: int = Field(default=8388608, ge=1)
    transfer_chunk_bytes: int = Field(default=1048576, ge=1, le=8388608)
    original_read_page_bytes: int = Field(default=16384, ge=512, le=262144)
    startup_read_page_bytes: int = Field(default=16384, ge=512, le=262144)


class AttachmentSettings(SettingsValue):
    """Streamed scientific deliverables, independent of prompt and solver budgets."""
    max_item_bytes: int = Field(default=2_000_000_000, ge=1)
    max_total_bytes: int = Field(default=2_000_000_000, ge=1)
    max_files: int = Field(default=64, ge=1, le=128)
    chunk_bytes: int = Field(default=1048576, ge=4096, le=8388608)


class ProgressionSettings(SettingsValue):
    """Administrator opt-in and bounded background Root execution."""
    enabled: bool = True
    max_rounds: int = Field(default=12, ge=1)
    max_tasks: int = Field(default=8, ge=1)
    max_reviews: int = Field(default=2, ge=0)
    # Per-read/write memory capacity is independent of granted task budgets.
    # 300 research + 300 reviews, four helpers and 600 Root rounds fits.
    detail_capacity: int = Field(default=4096, ge=1, le=65536)
    detail_record_bytes: int = Field(default=65536, ge=1024, le=1048576)
    detail_read_bytes: int = Field(default=67108864, ge=4096, le=67108864)
    # Bounds the still-hydrated scope history; every scope needs separate UI consent.
    max_loop_scopes: int = Field(default=8, ge=1, le=64)
    max_elapsed_seconds: int = Field(default=3600, ge=1)
    # Natural lifetime starts at explicit loop authorization, including pauses.
    max_calendar_seconds: int = Field(default=3600, ge=1)
    max_attempts: int = Field(default=2, ge=1, le=10)
    # Recovery is inside the frozen loop budget; native recovery also retains
    # max_attempts. Failed turns require explicit UI consent to this policy.
    max_recoveries: int = Field(default=8, ge=0, le=1000)
    recovery_failure_threshold: int = Field(default=3, ge=1, le=100)
    recovery_backoff_seconds: float = Field(default=1., gt=0, le=300)
    recovery_backoff_max_seconds: float = Field(default=60., gt=0, le=3600)
    recover_failed_turns: bool = False
    poll_seconds: int = Field(default=5, ge=1, le=300)
    event_wait_seconds: float = Field(default=.2, gt=0, le=1)
    resource_sample_seconds: float = Field(default=1., gt=0, le=5)
    budget_snapshot_seconds: float = Field(default=30., gt=0, le=300)
    observation_retries: int = Field(default=3, ge=0, le=10)
    observation_backoff_seconds: float = Field(default=.1, gt=0, le=1)
    observation_retry_seconds: float = Field(default=2., gt=0, le=5)
    sqlite_busy_wait_seconds: float = Field(default=.1, ge=0, le=1)
    related_source_limit: int = Field(default=128, ge=1, le=4096)
    progress_mode: Literal["off", "shadow", "assist"] = "shadow"
    unverified_progress_threshold: int = Field(default=3, ge=1, le=100,
        description="Consumed research tasks without a newly verified predeclared test resolution; a direction checkpoint, not a claim of scientific stagnation.")
    no_progress_threshold: int = Field(default=3, ge=1, le=100)
    refinement_threshold: int = Field(default=4, ge=1, le=100)
    observation_gap_threshold: int = Field(default=3, ge=1, le=100)
    progress_read_bytes: int = Field(default=16384, ge=16384, le=65536)
    context_bytes: int = Field(default=49152, ge=4096, le=262144)
    max_tokens: int = Field(default=2000000, ge=1)
    closeout_reserve_tokens: int = Field(default=100000, ge=0)
    token_policy: Literal["strict", "bounded_fallback"] = "bounded_fallback"
    max_rss_bytes: int = Field(default=1000000000, ge=1048576)
    frame_bytes: int = Field(default=1048576, ge=4096, le=8388608)
    log_bytes: int = Field(default=1048576, ge=4096)
    rpc_timeout_seconds: int = Field(default=30, ge=1, le=120)
    # Root model selection is independent of Worker defaults and frozen with the goal.
    root_model: str = Field(default="gpt-5.6-sol", min_length=1, max_length=256)
    root_reasoning_effort: ReasoningEffort = "high"
    # Zero disables each trigger. Input is cumulative (cached input included),
    # not a measurement of the current native context window.
    root_rotate_after_rounds: int = Field(default=8, ge=0,
        description="Completed decision rounds on this Root thread before safe rotation; 0 disables this trigger.")
    root_rotate_after_input_tokens: int = Field(default=500000, ge=0,
        description="Cumulative native input usage on this Root thread, including cached input; not current context size. 0 disables this trigger.")
    root_rotation_check_limit: int = Field(default=16, ge=1, le=128,
        description="Maximum total native resume and read RPCs per rotation attempt. Exact control-bound participants, including terminal participants from a prior connection, may resume without a turn or permission override; unconfirmed subscriptions defer. Exact terminal proof is reusable only on its subscribed connection and event version.")
    # Native Workers inherit Root permissions; validate their catalog requirements.
    root_approval_policy: Literal["never"] = "never"
    root_sandbox: Literal["read-only", "workspace-write"] = "workspace-write"
    root_network_access: bool = True

    @model_validator(mode="after")
    def _declarable_root_network(self):
        if self.root_sandbox == "read-only" and self.root_network_access:
            raise ValueError("root_network_access requires root_sandbox workspace-write: Codex declares "
                             "thread network only through sandbox_workspace_write.network_access")
        return self


def task_network_policy(disabled: bool, *, web_search: str = "disabled") -> dict:
    """Effective managed-task policy; model-provider traffic is outside this gate."""
    return {"debug_disabled": disabled, "native_network": not disabled,
            "web_search": "disabled" if disabled else web_search,
            "host_requests": not disabled}


def root_permission_conflicts(progression: dict, catalog, *, debug_disable_task_network=False) -> list[str]:
    """Worker capabilities a frozen background Root policy would silently remove.

    Native Workers inherit Root sandbox and network. Hosted web_search is counted
    as a network need until its independence from sandbox network is verified."""
    agents = [catalog.operation(item).spec for item in catalog.operation_ids()]
    agents = [spec for spec in agents if spec.executor.kind == "agent"]
    default = ProgressionSettings()
    issues = []
    writers = sorted(spec.operation_id for spec in agents if spec.executor.native_tools.shell == "inherited_prototype")
    if progression.get("root_sandbox", default.root_sandbox) != "workspace-write" and writers:
        issues.append("root_sandbox read-only removes workspace writes from Workers that inherit Root "
                      "permissions (inherited native shell): " + ", ".join(writers))
    policy = task_network_policy(debug_disable_task_network)
    if debug_disable_task_network and progression.get("root_network_access", default.root_network_access):
        issues.append("debug_disable_task_network requires effective root_network_access false")
    network = sorted(spec.operation_id for spec in agents if
                     (policy["host_requests"] and spec.limits.network.mode != "none")
                     or task_network_policy(debug_disable_task_network,
                         web_search=spec.executor.native_tools.web_search)["web_search"] != "disabled")
    if not progression.get("root_network_access", default.root_network_access) and network:
        issues.append("root_network_access false removes network from Workers that inherit Root "
                      "permissions (declared network or web_search): " + ", ".join(network))
    return issues


def progression_usage_capacity(settings: dict) -> int:
    """Every task, including review, may use its frozen helper allowance."""
    limits = settings['progression']
    return ((limits['max_tasks'] + limits['max_reviews']) *
        (1 + settings['helpers']['max_calls']) + limits['max_rounds'])


def require_progression_capacity(settings: dict):
    limits = settings['progression']
    identities = progression_usage_capacity(settings)
    if identities > limits['detail_capacity']:
        raise ValueError('Configured task, review, helper and Root identity capacity exceeds '
            'progression.detail_capacity; retain the original loop and explicitly configure capacity before authorization.')
    # Actual serialized totals are checked transactionally, independently of
    # task quotas. Current + one original loop must fit the read byte bound.
    if 2 * limits['detail_record_bytes'] > limits['detail_read_bytes']:
        raise ValueError('progression.detail_read_bytes must hold current and late original '
            'records at detail_record_bytes; retain the original loop and explicitly configure bounded capacity.')

class PresentationSettings(SettingsValue):
    """Opt-in, serial post-seal copy editing; never scientific admission."""
    enabled: bool = False
    command: list[str] = Field(default_factory=lambda: ["codex"], min_length=1, max_length=16)
    codex_home: str | None = None
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    interval_seconds: int = Field(default=5, ge=1, le=3600)
    max_source_bytes: int = Field(default=1048576, ge=1024, le=8388608)
    max_input_bytes: int = Field(default=16384, ge=1024, le=262144)
    max_output_bytes: int = Field(default=32768, ge=1024, le=262144)
    memory_limit_bytes: int = Field(default=2147483648, ge=268435456)


class MCPReadSettings(SettingsValue):
    """Global JSON page budgets for Root task and scientific-object lists."""
    summary_max_bytes: int = Field(default=4096, ge=1024, le=262144)
    detail_max_bytes: int = Field(default=32768, ge=1024, le=1048576)


class DiagnosticsSettings(SettingsValue):
    """Retention of expendable engineering traces, never sealed scientific evidence."""
    max_records: int = Field(default=1024, ge=1)
    max_total_bytes: int = Field(default=67108864, ge=1024)
    retention_seconds: int = Field(default=604800, ge=1)


class AgentSettings(SettingsValue):
    schema_version: Literal[1] = 1
    experiment_provider: str = Field(default="auto",
        pattern=r"^(auto|none|[a-z][a-z0-9_.-]{0,127}:[a-z][a-z0-9_.-]{0,127})$",
        description="Deployment startup-only remote provider: auto uses zero or one installed candidate and rejects ambiguity; none disables remote experiment tools; plugin:component selects one. Regenerate Worker profiles and restart hosts after changes; existing Run identities cannot resume under a different selection. Existing executions retain their original executor for recovery and collection.")
    debug_disable_task_network: bool = Field(default=False, description=(
        "Deployment startup-only debug restriction: managed Root/Worker/helper native network, "
        "web search and declared host network tools are disabled; model API traffic is unchanged. "
        "Stop all existing hosts and agents before enabling and restart with matching installed roles. "
        "Old tasks/loops with different frozen policy cannot execute or resume; originals remain readable. "
        "This is not an OS network boundary for arbitrary plugins or external MCP servers."))
    defaults: DefaultSettings = Field(default_factory=DefaultSettings)
    operations: dict[str, OperationSettings] = Field(default_factory=dict)
    progression: ProgressionSettings = Field(default_factory=ProgressionSettings)
    helpers: HelperSettings = Field(default_factory=HelperSettings)
    execution_io: ExecutionIOSettings = Field(default_factory=ExecutionIOSettings)
    budget_extensions: BudgetExtensionSettings = Field(default_factory=BudgetExtensionSettings)
    lifecycle: LifecycleSettings = Field(default_factory=LifecycleSettings)
    diagnostics: DiagnosticsSettings = Field(default_factory=DiagnosticsSettings)
    input_materials: MaterialInputSettings = Field(default_factory=MaterialInputSettings)
    attachments: AttachmentSettings = Field(default_factory=AttachmentSettings)
    presentation: PresentationSettings = Field(default_factory=PresentationSettings)
    mcp_read: MCPReadSettings = Field(default_factory=MCPReadSettings)

    def sparse(self) -> dict:
        return self.model_dump(exclude_none=True, exclude_unset=True)

    def experiment_capability_selections(self) -> dict[str, str]:
        return ({} if self.experiment_provider == "auto" else
            {"general_science:experiment_task_protocol": self.experiment_provider})


class ExecutionProfile(SettingsValue):
    model: str = Field(min_length=1, max_length=256)
    reasoning_effort: ReasoningEffort
    narrative_language: Language

    @field_validator("model")
    @classmethod
    def normalize_model_identity(cls, value: str) -> str:
        return canonical_model_id(value) or value


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


@lru_cache(maxsize=1)
def packaged_default_model() -> str:
    source = Path(__file__).with_name("default_agent_settings.json")
    settings = parse_settings(json.loads(source.read_text(encoding="utf-8")), label=str(source))
    if settings.defaults.model is None:
        raise ValueError(f"{source}: defaults.model is required")
    return settings.defaults.model


def resolve_settings(global_settings: AgentSettings, instance_settings: AgentSettings,
                     *, operation_id: str, operation_model: str | None,
                     operation_max_attempts: int) -> dict:
    values = dict(model=operation_model or packaged_default_model(), reasoning_effort="medium",
                  narrative_language="en", max_attempts=operation_max_attempts)
    sources = dict(model="operation_default" if operation_model else "package_default",
                   reasoning_effort="compatibility_default",
                   narrative_language="compatibility_default", max_attempts="operation_default")
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


def effective_settings(global_settings: AgentSettings, instance_settings: dict) -> dict:
    """One effective snapshot, including inherited defaults, with no live drift."""
    def merge(base, override):
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                merge(base[key], value)
            else:
                base[key] = value
        return base
    for field in ("debug_disable_task_network", "experiment_provider"):
        if field in instance_settings:
            raise ValueError(f"{field} is deployment-only, not an instance override")
    value = merge(global_settings.model_dump(exclude_none=True), instance_settings)
    if global_settings.debug_disable_task_network:
        value["progression"]["root_network_access"] = False
    for key, default in dict(model=packaged_default_model(), reasoning_effort="medium", narrative_language="en").items():
        value["defaults"].setdefault(key, default)
    # Instance preferences cannot enable a deployment-wide background runtime.
    value["progression"]["enabled"] = global_settings.progression.enabled and value["progression"]["enabled"]
    if global_settings.progression.progress_mode == "off":
        value["progression"]["progress_mode"] = "off"
    return parse_settings(value).model_dump(exclude_none=True)
