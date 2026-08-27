"""SciDiscovery execution adapter for the internal TCAD control socket."""

from __future__ import annotations

import hashlib
import json
import socket
import uuid
from pathlib import Path
from typing import Any

from scidiscovery.artifact_agent.execution_bridge import AdapterCapability
from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor

from .execution_control import FileDescriptor, SolverCapabilitySnapshot, TCADJobSpec
from .project_packager import (
    PackagerError,
    package_reviewed_deck_json,
    validate_reviewed_deck_json,
)


class TCADExecutorAdapter:
    def __init__(self, socket_path: Path | str, *, timeout: float = 10.0) -> None:
        if timeout <= 0:
            raise ValueError("adapter timeout must be positive")
        self.socket_path = Path(socket_path).expanduser().absolute()
        self.timeout = timeout

    @staticmethod
    def supports_preparation_profile(value: str) -> bool:
        return value == "tcad.reviewed-deck-package.v2"

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        value = self._call("tcad_capabilities", {})
        snapshots = tuple(
            SolverCapabilitySnapshot.model_validate_json(
                json.dumps(
                    item,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                strict=True,
            )
            for item in value.get("capabilities", ())
        )
        return tuple(_adapter_capability(item) for item in snapshots)

    def validate_preparation_payload(
        self, raw: bytes, *, preparation_profile: str
    ) -> None:
        if preparation_profile != "tcad.reviewed-deck-package.v2":
            raise ValueError("TCAD execution requires tcad.reviewed-deck-package.v2")
        try:
            reviewed = validate_reviewed_deck_json(raw)
        except PackagerError as error:
            raise ValueError("TCAD reviewed package is invalid") from error
        self._require_active_capability(reviewed.capability)

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        payload_path = Path(payload.local_path).absolute()
        if payload_path.parent != exchange_directory.absolute():
            raise ValueError("execution payload is outside its exchange directory")
        if preparation_profile != "tcad.reviewed-deck-package.v2":
            raise ValueError(
                "TCAD execution requires tcad.reviewed-deck-package.v2"
            )
        raw = payload_path.read_bytes()
        self.validate_preparation_payload(raw, preparation_profile=preparation_profile)
        packaged = package_reviewed_deck_json(
            raw,
            output_root=exchange_directory / "prepared",
        )
        return LocalFileDescriptor.model_validate(
            packaged.job_spec_file.model_dump(mode="python"), strict=True
        )

    def prepare_development_debug(
        self,
        *,
        job_spec_file: LocalFileDescriptor,
        archive: LocalFileDescriptor,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        raw = _read_bound_descriptor(
            job_spec_file, exchange_directory=exchange_directory
        )
        _read_bound_descriptor(archive, exchange_directory=exchange_directory)
        job = TCADJobSpec.model_validate_json(raw, strict=True)
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
        return job_spec_file

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]:
        value = self._call(
            "tcad_submit",
            {
                "submission": submission.model_dump(
                    mode="json", exclude={"schema_version"}
                )
            },
        )
        return str(value["run_id"]), str(value["state"])

    def status(self, external_run_id: str) -> str:
        return str(self._call("tcad_status", {"run_id": external_run_id})["state"])

    def cancel(self, external_run_id: str) -> str:
        return str(self._call("tcad_cancel", {"run_id": external_run_id})["state"])

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]:
        value = self._call("tcad_collect", {"run_id": external_run_id})
        return tuple(
            LocalFileDescriptor.model_validate(item, strict=True)
            for item in value["outputs"]
        )

    def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(self.timeout)
            client.connect(str(self.socket_path))
            client.sendall(request + b"\n")
            with client.makefile("rb") as stream:
                raw = stream.readline(16 * 1024 * 1024 + 1)
        if not raw or len(raw) > 16 * 1024 * 1024:
            raise RuntimeError("TCAD control returned no bounded response")
        response = json.loads(raw)
        if response.get("id") != request_id:
            raise RuntimeError("TCAD control response identity differs")
        if "error" in response:
            raise RuntimeError(str(response["error"].get("message", "TCAD call failed")))
        try:
            value = response["result"]["structuredContent"]
        except (KeyError, TypeError) as error:
            raise RuntimeError("TCAD control response has no structured result") from error
        if not isinstance(value, dict):
            raise RuntimeError("TCAD control result is not an object")
        return value

    def _require_active_capability(
        self, expected: SolverCapabilitySnapshot
    ) -> None:
        snapshots = tuple(
            SolverCapabilitySnapshot.model_validate_json(item.content, strict=True)
            for item in self.capabilities()
        )
        if expected not in snapshots:
            raise ValueError("reviewed package capability is not active on this adapter")


def _adapter_capability(value: SolverCapabilitySnapshot) -> AdapterCapability:
    content = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return AdapterCapability(
        key=value.profile_id,
        kind="solver_capability",
        schema_id="tcad.solver-capability.v2",
        payload_schema_version=2,
        media_type="application/json",
        content=content,
        public_summary={
            "profile": value.profile_id,
            "solver_kind": value.solver_kind,
            "launch_name": value.launch_name,
            "public_arguments": list(value.public_arguments),
            "public_release_label": value.public_release_label,
            "private_fixed_argument_count": value.private_fixed_argument_count,
        },
    )


def _read_bound_descriptor(
    descriptor: LocalFileDescriptor, *, exchange_directory: Path
) -> bytes:
    path = Path(descriptor.local_path).expanduser().absolute()
    try:
        path.relative_to(exchange_directory.expanduser().absolute())
    except ValueError as error:
        raise ValueError("development debug file is outside its exchange") from error
    metadata = path.lstat()
    if path.is_symlink() or not path.is_file():
        raise ValueError("development debug file is not regular")
    raw = path.read_bytes()
    if (
        metadata.st_size != descriptor.size_bytes
        or len(raw) != descriptor.size_bytes
        or hashlib.sha256(raw).hexdigest() != descriptor.sha256
    ):
        raise ValueError("development debug file differs from its descriptor")
    return raw


__all__ = ["TCADExecutorAdapter"]
