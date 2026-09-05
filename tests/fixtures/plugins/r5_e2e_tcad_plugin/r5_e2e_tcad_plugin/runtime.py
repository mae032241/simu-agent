"""Evaluation-only runtime closure for exact frozen Fig.4 output replay."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal, Mapping, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ingaas_fig4.plugin import CURVE_TABLE_SCHEMA, RESULT_SCHEMA
from scidiscovery.artifact_agent.execution_bridge import AdapterCapability
from scidiscovery.artifact_agent.schema.approval import (
    ReviewDocument,
    ReviewDocumentItem,
    ReviewDocumentSection,
)
from scidiscovery.artifact_agent.schema.execution import (
    ExecutionRequest,
    LocalFileDescriptor,
)
from scidiscovery.operations.invoke import (
    ApprovalProjectorContext,
    EffectExecutorPlan,
)
from scidiscovery.operations.runtime_plugins import (
    RuntimePluginContext,
    RuntimePluginContribution,
    RuntimePluginFactory,
)
from scidiscovery.operations.spec import CallableComponent


FIXTURE_ID = "r5-e2e-fig4-baseline-recovery-v1"
ADAPTER_BINDING = "replay"
QUALIFIED_ADAPTER_ID = "r5_e2e_fixture:replay"
ADAPTER_VERSION = "1"
PREPARATION_PROFILE = "r5.fig4-historical-replay.v1"
ACTIVE_BUNDLE_SHA256 = (
    "684d106dac3baa3026051300c8112d7fecd79cb41d96ed6212b59e511be018e3"
)
SOURCE_PROJECT_SHA256 = (
    "e07da8714fe6423688f14b181f058b7cadaa4be6aa7c845e7ff7acaee997357e"
)
REPLAY_REQUEST_SHA256 = (
    "7a83623203369b829c4fc513028fefa5dde0eb9e0098bbb8603cd05543f4ea69"
)
REPLAY_REQUEST_SIZE_BYTES = 267
REPLAY_PROFILE_SHA256 = (
    "62dbca930c64d14868617e8982d0fe4a6e2b6f5b7a04f11dcdbe4c5356be06d7"
)
REPLAY_PROFILE_SIZE_BYTES = 91063
_OUTPUT_ROLES = (
    "replay_solver_plx",
    "replay_solver_structure",
    "replay_solver_log",
    "replay_runtime_manifest",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReplayRequest(_StrictModel):
    schema_version: Literal[1]
    fixture_id: Literal[FIXTURE_ID]
    active_bundle_sha256: Literal[ACTIVE_BUNDLE_SHA256]
    source_project_sha256: Literal[SOURCE_PROJECT_SHA256]


class ReplayRuntimeConfig(_StrictModel):
    repository_root: str = Field(min_length=1, max_length=4096)
    manifest_path: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def _paths_are_absolute(self) -> Self:
        if not Path(self.repository_root).is_absolute():
            raise ValueError("replay repository root must be absolute")
        if not Path(self.manifest_path).is_absolute():
            raise ValueError("replay manifest path must be absolute")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class FrozenFig4ReplayAdapter:
    """Return only bytes whose identities were frozen before the R5 run."""

    def __init__(self, repository: Path, manifest_path: Path) -> None:
        self.repository = repository.resolve()
        self.manifest_path = manifest_path.resolve()
        if not self.manifest_path.is_relative_to(self.repository):
            raise ValueError("replay manifest escapes the repository")
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if self.manifest.get("fixture_id") != FIXTURE_ID:
            raise ValueError("replay manifest has a different fixture identity")
        self.exchange_directory: Path | None = None
        self.submission: tuple[str, str] | None = None

    @staticmethod
    def supports_preparation_profile(profile: str) -> bool:
        return profile == PREPARATION_PROFILE

    @staticmethod
    def capabilities() -> tuple[AdapterCapability, ...]:
        content = _canonical(
            {
                "schema_version": 1,
                "kind": "historical_replay",
                "fixture_id": FIXTURE_ID,
                "adapter_version": ADAPTER_VERSION,
                "forbidden_claim": "This capability does not execute a solver.",
            }
        )
        return (
            AdapterCapability(
                key="fig4_historical_replay",
                kind="historical_replay",
                schema_id="r5.fixture.historical-replay-capability.v1",
                payload_schema_version=1,
                media_type="application/json",
                content=content,
                public_summary={
                    "kind": "historical_replay",
                    "fixture_id": FIXTURE_ID,
                    "adapter_version": ADAPTER_VERSION,
                },
            ),
        )

    def validate_preparation_payload(
        self, raw: bytes, *, preparation_profile: str
    ) -> None:
        if preparation_profile != PREPARATION_PROFILE:
            raise ValueError("unsupported replay profile")
        request = validate_replay_request(raw)
        expected = ReplayRequest.model_validate(
            self.manifest["replay_adapter"]["exact_request"], strict=True
        )
        if request != expected:
            raise ValueError("replay request differs from the frozen identity")

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        raw = Path(payload.local_path).read_bytes()
        self.validate_preparation_payload(
            raw, preparation_profile=preparation_profile
        )
        self.exchange_directory = exchange_directory.resolve()
        return payload

    def submit(self, _submission: LocalFileDescriptor) -> tuple[str, str]:
        self.submission = ("r5-frozen-fig4-replay", "accepted")
        return self.submission

    def lookup_submission(
        self, _submission: LocalFileDescriptor
    ) -> tuple[str, str] | None:
        return self.submission

    @staticmethod
    def status(external_run_id: str) -> str:
        if external_run_id != "r5-frozen-fig4-replay":
            raise ValueError("unknown replay run")
        return "succeeded"

    @staticmethod
    def cancel(external_run_id: str) -> str:
        if external_run_id != "r5-frozen-fig4-replay":
            raise ValueError("unknown replay run")
        return "cancelled"

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]:
        if external_run_id != "r5-frozen-fig4-replay":
            raise ValueError("unknown replay run")
        if self.exchange_directory is None:
            raise RuntimeError("replay was not prepared")
        by_role = {item["role"]: item for item in self.manifest["files"]}
        descriptors: list[LocalFileDescriptor] = []
        output_root = self.exchange_directory / "frozen-replay-outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        for role in _OUTPUT_ROLES:
            item = by_role[role]
            source = (self.repository / item["path"]).resolve()
            if not source.is_relative_to(self.repository):
                raise ValueError("frozen replay source escapes the repository")
            raw = source.read_bytes()
            if (
                len(raw) != item["size_bytes"]
                or hashlib.sha256(raw).hexdigest() != item["sha256"]
            ):
                raise ValueError(f"frozen replay source changed: {role}")
            target = output_root / item["logical_name"]
            shutil.copyfile(source, target)
            descriptors.append(
                LocalFileDescriptor(
                    name=item["logical_name"],
                    local_path=str(target),
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    media_type=item["media_type"],
                )
            )
        return tuple(descriptors)


def build_runtime(context: RuntimePluginContext) -> RuntimePluginContribution:
    config = ReplayRuntimeConfig.model_validate_json(
        context.config_bytes, strict=True
    )
    if context.mode == "worker":
        return RuntimePluginContribution()
    adapter = FrozenFig4ReplayAdapter(
        Path(config.repository_root), Path(config.manifest_path)
    )
    return RuntimePluginContribution(
        execution_adapters={ADAPTER_BINDING: adapter}
    )


def execute_effect() -> EffectExecutorPlan:
    return EffectExecutorPlan(
        executor=ADAPTER_BINDING,
        preparation_profile=PREPARATION_PROFILE,
        payload_port="replay_request",
    )


def execution_projector(
    context: ApprovalProjectorContext,
) -> ReviewDocument:
    if (
        context.operation_id != "r5.fixture.fig4-replay.v1"
        or tuple(item.port_name for item in context.subjects)
        != ("execution_request", "replay_request")
    ):
        raise ValueError("Fig.4 replay review has different subjects")
    request = ExecutionRequest.model_validate_json(
        context.subjects[0].content, strict=True
    )
    ReplayRequest.model_validate_json(context.subjects[1].content, strict=True)
    if (
        request.executor != QUALIFIED_ADAPTER_ID
        or request.preparation_profile != PREPARATION_PROFILE
        or request.compiled_identity is None
        or request.compiled_identity.operation_id != context.operation_id
        or request.compiled_identity.operation_version != context.operation_version
        or request.compiled_identity.operation_digest != context.operation_digest
    ):
        raise ValueError("Fig.4 replay request has a different compiled identity")
    return ReviewDocument(
        title="R5 冻结 Fig.4 历史输出重放审批",
        description="只授权复制已冻结历史输出；不执行 Sentaurus。",
        sections=(
            ReviewDocumentSection(
                title="重放边界",
                items=(
                    ReviewDocumentItem(
                        kind="json_value",
                        label="执行器",
                        subject_index=0,
                        json_pointer="/executor",
                    ),
                    ReviewDocumentItem(
                        kind="json_value",
                        label="准备合同",
                        subject_index=0,
                        json_pointer="/preparation_profile",
                    ),
                    ReviewDocumentItem(
                        kind="json_tree",
                        label="冻结请求",
                        subject_index=1,
                        json_pointer="",
                    ),
                ),
            ),
        ),
    )


def json_codec(raw: bytes) -> bytes:
    return raw


def opaque_codec(raw: bytes) -> bytes:
    return raw


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"Fig.4 replay qualification input {name} must contain one item")
    return items[0]


def qualify_replay_profile(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    request_raw = _one(values, "replay_request")
    request = validate_replay_request(request_raw)
    if (
        request.active_bundle_sha256 != ACTIVE_BUNDLE_SHA256
        or request.source_project_sha256 != SOURCE_PROJECT_SHA256
    ):
        raise ValueError("Fig.4 replay request differs from the frozen identity")
    profile = _one(values, "replay_profile")
    validate_replay_profile(profile)
    return {"candidate_profile": (profile,)}


def project_science_sources(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    """Expose exact typed fixture results as source views without changing bytes."""

    metric = _one(values, "metric_report")
    curve = _one(values, "curve_bundle")
    validate_metric_source(metric)
    validate_curve_source(curve)
    return {"metric_source": (metric,), "curve_source": (curve,)}


def validate_replay_request(raw: bytes) -> ReplayRequest:
    if (
        len(raw) != REPLAY_REQUEST_SIZE_BYTES
        or hashlib.sha256(raw).hexdigest() != REPLAY_REQUEST_SHA256
    ):
        raise ValueError("Fig.4 replay request differs from the frozen bytes")
    return ReplayRequest.model_validate_json(raw, strict=True)


def validate_replay_profile(raw: bytes) -> None:
    if (
        len(raw) != REPLAY_PROFILE_SIZE_BYTES
        or hashlib.sha256(raw).hexdigest() != REPLAY_PROFILE_SHA256
    ):
        raise ValueError("Fig.4 replay profile differs from the frozen output")
    if b'"ZnTotal"' not in raw or b"\n" not in raw:
        raise ValueError("Fig.4 replay profile lacks the frozen PLX structure")


def validate_metric_source(raw: bytes) -> None:
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Fig.4 metric source view must be one versioned JSON object")


def validate_curve_source(raw: bytes) -> None:
    if not raw or b"," not in raw or b"\n" not in raw:
        raise ValueError("Fig.4 curve source view must be a non-empty CSV table")


_request_schema = ReplayRequest.model_json_schema(mode="validation")
_request_schema["$id"] = "r5.fixture.fig4-replay-request.v1"
REPLAY_REQUEST_SCHEMA = json.dumps(
    _request_schema, ensure_ascii=True, separators=(",", ":"), sort_keys=True
)
_execution_schema = ExecutionRequest.model_json_schema(mode="validation")
_execution_schema["$id"] = "scidiscovery.execution-request"
EXECUTION_REQUEST_SCHEMA = json.dumps(
    _execution_schema, ensure_ascii=True, separators=(",", ":"), sort_keys=True
)
_configuration_schema = ReplayRuntimeConfig.model_json_schema(mode="validation")
_configuration_schema["$id"] = "r5.fixture.runtime-config.v1"
CONFIGURATION_SCHEMA = json.dumps(
    _configuration_schema,
    ensure_ascii=True,
    separators=(",", ":"),
    sort_keys=True,
)
OPAQUE_SCHEMA = json.dumps(
    {"$id": "opaque", "type": "string"},
    ensure_ascii=True,
    separators=(",", ":"),
    sort_keys=True,
)
PLX_SCHEMA = json.dumps(
    {"$id": "ingaas.fig4-zinc-profile-plx.v1", "type": "string"},
    ensure_ascii=True,
    separators=(",", ":"),
    sort_keys=True,
)
JSON_CODEC = CallableComponent("codec", json_codec)
OPAQUE_CODEC = CallableComponent("codec", opaque_codec)
QUALIFY_REPLAY_PROFILE = CallableComponent("transform", qualify_replay_profile)
REPLAY_PROFILE_VALIDATOR = CallableComponent("validator", validate_replay_profile)
PROJECT_SCIENCE_SOURCES = CallableComponent("transform", project_science_sources)
METRIC_SOURCE_VALIDATOR = CallableComponent("validator", validate_metric_source)
CURVE_SOURCE_VALIDATOR = CallableComponent("validator", validate_curve_source)
EXECUTE_EFFECT = CallableComponent("effect", execute_effect)
EXECUTION_PROJECTOR = CallableComponent("projector", execution_projector)
RUNTIME_FACTORY = RuntimePluginFactory(build_runtime)


__all__ = [
    "ADAPTER_VERSION",
    "CONFIGURATION_SCHEMA",
    "EXECUTE_EFFECT",
    "EXECUTION_PROJECTOR",
    "EXECUTION_REQUEST_SCHEMA",
    "FrozenFig4ReplayAdapter",
    "JSON_CODEC",
    "OPAQUE_CODEC",
    "OPAQUE_SCHEMA",
    "PLX_SCHEMA",
    "PREPARATION_PROFILE",
    "QUALIFY_REPLAY_PROFILE",
    "REPLAY_PROFILE_SHA256",
    "REPLAY_PROFILE_SIZE_BYTES",
    "REPLAY_PROFILE_VALIDATOR",
    "REPLAY_REQUEST_SHA256",
    "REPLAY_REQUEST_SIZE_BYTES",
    "REPLAY_REQUEST_SCHEMA",
    "RUNTIME_FACTORY",
    "ReplayRequest",
]
