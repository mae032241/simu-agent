"""Bounded command adapter for administrator-provided TCAD transports."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scidiscovery.artifact_agent.execution_bridge import AdapterCapability
from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor

from .transport_logs import preserve_log
from scidiscovery.artifact_agent.service.execution_collection import CollectionContext, QUERY_SECONDS, run_bounded

from .execution_control import FileDescriptor, SolverCapabilitySnapshot, TCADJobSpec
from .project_packager import (
    PackagerError,
    package_reviewed_deck_json,
    validate_reviewed_deck_json,
)


class CommandAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    executable: str = Field(min_length=1, max_length=4096)
    arguments: tuple[str, ...] = Field(default=(), max_length=64)
    environment: dict[str, str] = Field(default_factory=dict)
    operation_timeout_seconds: int = Field(default=30, ge=1, le=300)
    query_timeout_seconds: float = Field(default=QUERY_SECONDS, gt=0)

    @field_validator("executable")
    @classmethod
    def _absolute_executable(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("transport executable must be absolute")
        return value


class CommandTCADExecutorAdapter:
    """Invoke one bounded external operation for each execution transition."""

    def __init__(
        self,
        config: CommandAdapterConfig,
        *,
        local_result_root: Path | str,
    ) -> None:
        executable = Path(config.executable).resolve(strict=True)
        metadata = os.stat(executable)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o111 == 0:
            raise ValueError("transport executable must be an executable regular file")
        self.config = config.model_copy(update={"executable": str(executable)})
        self.local_result_root = Path(local_result_root).expanduser().absolute()
        self.local_result_root.mkdir(parents=True, exist_ok=True, mode=0o770)

    @staticmethod
    def supports_preparation_profile(value: str) -> bool:
        return value == "tcad.reviewed-deck-package.v2"

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        value = self._call("capabilities", {})
        snapshots = tuple(
            SolverCapabilitySnapshot.model_validate_json(
                _canonical(item), strict=True
            )
            for item in value.get("capabilities", ())
        )
        return tuple(_adapter_capability(item) for item in snapshots)

    def validate_preparation_payload(
        self, raw: bytes, *, preparation_profile: str
    ) -> None:
        if preparation_profile != "tcad.reviewed-deck-package.v2":
            raise ValueError("command adapter requires tcad.reviewed-deck-package.v2")
        try:
            reviewed = validate_reviewed_deck_json(raw)
        except PackagerError as error:
            raise ValueError("TCAD reviewed package is invalid") from error
        self._require_active_capability(reviewed.capability)

    @classmethod
    def from_file(
        cls,
        path: Path | str,
        *,
        local_result_root: Path | str,
    ) -> CommandTCADExecutorAdapter:
        source = Path(path).expanduser().absolute()
        metadata = os.lstat(source)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("transport configuration must be a regular file")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ValueError("transport configuration must not be group/world writable")
        config = CommandAdapterConfig.model_validate_json(
            source.read_bytes(), strict=True
        )
        return cls(config, local_result_root=local_result_root)

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        if preparation_profile != "tcad.reviewed-deck-package.v2":
            raise ValueError("command adapter requires tcad.reviewed-deck-package.v2")
        raw = Path(payload.local_path).read_bytes()
        self.validate_preparation_payload(raw, preparation_profile=preparation_profile)
        packaged = package_reviewed_deck_json(
            raw,
            output_root=exchange_directory / "prepared",
        )
        value = self._call(
            "prepare",
            {
                "job_spec": _without_schema(packaged.job_spec_file),
                "archive": _without_schema(packaged.archive),
                "execution_exchange": str(exchange_directory),
                "local_result_root": str(self.local_result_root),
            },
        )
        return LocalFileDescriptor.model_validate(value["submission"], strict=True)

    def prepare_development_debug(
        self,
        *,
        job_spec_file: LocalFileDescriptor,
        archive: LocalFileDescriptor,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        job_raw = _read_bound_descriptor(
            job_spec_file, exchange_directory=exchange_directory
        )
        _read_bound_descriptor(archive, exchange_directory=exchange_directory)
        job = TCADJobSpec.model_validate_json(job_raw, strict=True)
        expected_archive = FileDescriptor.model_validate(
            archive.model_dump(mode="python", exclude={"schema_version"}),
            strict=True,
        )
        if (
            job.execution_purpose != "development_debug"
            or job.input_archive != expected_archive
            or job.solver_kind not in {"sprocess", "sdevice"}
        ):
            raise ValueError("development debug job binding is invalid")
        snapshots = tuple(
            SolverCapabilitySnapshot.model_validate_json(item.content, strict=True)
            for item in self.capabilities()
        )
        if not any(
            item.profile_id == job.tool_profile
            and item.solver_kind == job.solver_kind
            and item.capability_sha256 == job.capability_sha256
            for item in snapshots
        ):
            raise ValueError("development debug capability is not active")
        value = self._call(
            "prepare",
            {
                "job_spec": _without_schema(job_spec_file),
                "archive": _without_schema(archive),
                "execution_exchange": str(exchange_directory),
                "local_result_root": str(self.local_result_root),
            },
        )
        return LocalFileDescriptor.model_validate(value["submission"], strict=True)

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]:
        value = self._call("submit", {"submission": _without_schema(submission)})
        return str(value["run_id"]), str(value["state"])

    def lookup_submission(
        self, submission: LocalFileDescriptor
    ) -> tuple[str, str] | None:
        value = self._call(
            "lookup_submission", {"submission": _without_schema(submission)}
        )
        if value.get("found") is False:
            return None
        if value.get("found") is not True:
            raise RuntimeError("TCAD transport lookup returned no authority")
        return str(value["run_id"]), str(value["state"])

    def status(self, external_run_id: str) -> str:
        return str(self.status_details(external_run_id)["state"])

    def status_details(self, external_run_id: str) -> dict[str, Any]:
        return self._call("status", {"run_id": external_run_id})

    def cancel(self, external_run_id: str) -> str:
        value = self._call("cancel", {"run_id": external_run_id})
        return str(value["state"])

    def inspect_outputs(self, external_run_id: str, relative_path: str | None = None, max_bytes: int = 32*1024*1024, *, deadline_monotonic=None) -> dict[str, Any]:
        payload = {"run_id": external_run_id, "relative_path": relative_path, "max_bytes": max_bytes}
        if deadline_monotonic is not None:
            payload["deadline_monotonic"] = deadline_monotonic
        value = self._call("inspect_outputs", payload)
        if value.get("status") == "available" and "file" in value:
            descriptor = LocalFileDescriptor.model_validate(value["file"], strict=True)
            path = Path(descriptor.local_path)
            if not _within(path.resolve(), self.local_result_root.resolve()) or path.is_symlink() or descriptor.size_bytes > max_bytes:
                raise RuntimeError("inspection output is outside its bounds")
        return value

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]:
        value = self._call(
            "collect",
            {
                "run_id": external_run_id,
                "local_result_root": str(self.local_result_root),
            },
        )
        return self._collected_outputs(value)

    def collect_with_budget(self, external_run_id: str, *, context: CollectionContext) -> tuple[LocalFileDescriptor, ...]:
        context.remaining_seconds()
        value = self._call("collect", {"run_id": external_run_id,
            "local_result_root": str(self.local_result_root), "collection": context.wire(),
            "progress_path": context.progress_path}, context=context)
        return self._collected_outputs(value, context=context)

    def _collected_outputs(self, value, *, context=None):
        outputs = tuple(
            LocalFileDescriptor.model_validate(item, strict=True)
            for item in value["outputs"]
        )
        for item in outputs:
            if context is not None:
                context.remaining_seconds()
            path = Path(item.local_path).expanduser().absolute()
            if not _within(path, self.local_result_root):
                raise RuntimeError("transport output is outside its result root")
            metadata = os.lstat(path)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError("transport output is not a regular file")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    if context is not None:
                        context.remaining_seconds()
                    digest.update(chunk)
            if metadata.st_size != item.size_bytes or digest.hexdigest() != item.sha256:
                raise RuntimeError("transport output differs from its descriptor")
        return outputs

    def _call(self, operation: str, payload: dict[str, Any], *, context=None) -> dict[str, Any]:
        if operation == "status":
            payload = {**payload, "deadline_monotonic": time.monotonic() + self.config.query_timeout_seconds}
        deadline = payload.get("deadline_monotonic")
        timeout = context.remaining_seconds() if context is not None else max(.001, deadline - time.monotonic()) if deadline is not None else self.config.operation_timeout_seconds
        if deadline is not None and deadline <= time.monotonic():
            raise TimeoutError("TCAD transport request deadline exhausted before start")
        request = _canonical(
            {
                "schema_version": 1,
                "operation": operation,
                "payload": payload,
            }
        )
        environment = {
            "HOME": str(self.local_result_root),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
            **self.config.environment,
        }
        try:
            completed = run_bounded([self.config.executable, *self.config.arguments],
                input=request, env=environment, timeout=timeout, context=context)
        except subprocess.TimeoutExpired as error:
            log = preserve_log(self.local_result_root, "stderr", error.stderr or b"")
            preserve_log(self.local_result_root, "stdout", error.stdout or b"")
            raise RuntimeError(f"TCAD transport operation exceeded its short bound; stderr log: {log}") from error
        stderr_log = preserve_log(self.local_result_root, "stderr", completed.stderr) if completed.stderr else None
        if completed.returncode != 0:
            preserve_log(self.local_result_root, "stdout", completed.stdout)
            error = subprocess.CalledProcessError(completed.returncode, "TCAD transport",
                output=completed.stdout, stderr=completed.stderr)
            raise RuntimeError(f"TCAD transport operation failed; stderr log: {stderr_log}") from error
        if len(completed.stdout) > 8 * 1024 * 1024:
            raise RuntimeError("TCAD transport response exceeds its byte limit")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            log = preserve_log(self.local_result_root, "stdout", completed.stdout)
            raise RuntimeError(f"TCAD transport returned invalid JSON; stdout log: {log}") from error
        if (not isinstance(response, dict) or response.get("schema_version") != 1
                or response.get("operation") != operation or response.get("ok") is not True
                or not isinstance(response.get("payload"), dict)):
            preserve_log(self.local_result_root, "stdout", completed.stdout)
        if not isinstance(response, dict) or response.get("schema_version") != 1:
            raise RuntimeError("TCAD transport response has an invalid envelope")
        if response.get("operation") != operation:
            raise RuntimeError("TCAD transport response operation differs")
        if response.get("ok") is not True or not isinstance(response.get("payload"), dict):
            error = RuntimeError(str(response.get("error", "TCAD transport rejected operation")))
            if isinstance(response.get("engineering"), dict):
                error.engineering = response["engineering"]
            raise error
        return response["payload"]

    def _require_active_capability(
        self, expected: SolverCapabilitySnapshot
    ) -> None:
        snapshots = tuple(
            SolverCapabilitySnapshot.model_validate_json(item.content, strict=True)
            for item in self.capabilities()
        )
        if expected not in snapshots:
            raise ValueError("reviewed package capability is not active on this adapter")


def _without_schema(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude={"schema_version"})
    raise TypeError("descriptor is not a schema model")


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_bound_descriptor(
    descriptor: LocalFileDescriptor, *, exchange_directory: Path
) -> bytes:
    path = Path(descriptor.local_path).expanduser().absolute()
    if not _within(path, exchange_directory.expanduser().absolute()):
        raise ValueError("development debug file is outside its exchange")
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("development debug file is not regular")
    raw = path.read_bytes()
    if (
        len(raw) != descriptor.size_bytes
        or hashlib.sha256(raw).hexdigest() != descriptor.sha256
    ):
        raise ValueError("development debug file differs from its descriptor")
    return raw


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _adapter_capability(value: SolverCapabilitySnapshot) -> AdapterCapability:
    return AdapterCapability(
        key=value.profile_id,
        kind="solver_capability",
        schema_id="tcad.solver-capability.v2",
        payload_schema_version=2,
        media_type="application/json",
        content=_canonical(value.model_dump(mode="json")),
        public_summary={
            "profile": value.profile_id,
            "solver_kind": value.solver_kind,
            "launch_name": value.launch_name,
            "public_arguments": list(value.public_arguments),
            "public_release_label": value.public_release_label,
            "private_fixed_argument_count": value.private_fixed_argument_count,
        },
    )


__all__ = ["CommandAdapterConfig", "CommandTCADExecutorAdapter"]
