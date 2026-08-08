"""SciDiscovery execution adapter for the internal TCAD control socket."""

from __future__ import annotations

import json
import socket
import uuid
from pathlib import Path
from typing import Any

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor

from .project_packager import package_reviewed_deck_json


class TCADExecutorAdapter:
    def __init__(self, socket_path: Path | str, *, timeout: float = 10.0) -> None:
        if timeout <= 0:
            raise ValueError("adapter timeout must be positive")
        self.socket_path = Path(socket_path).expanduser().absolute()
        self.timeout = timeout

    @staticmethod
    def supports_preparation_profile(value: str) -> bool:
        return value in {"tcad.job-spec.v1", "tcad.reviewed-deck-package.v1"}

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
        if preparation_profile == "tcad.job-spec.v1":
            return payload
        if preparation_profile != "tcad.reviewed-deck-package.v1":
            raise ValueError("unsupported TCAD preparation profile")
        packaged = package_reviewed_deck_json(
            payload_path.read_bytes(),
            output_root=exchange_directory / "prepared",
        )
        return LocalFileDescriptor.model_validate(
            packaged.job_spec_file.model_dump(mode="python"), strict=True
        )

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


__all__ = ["TCADExecutorAdapter"]
