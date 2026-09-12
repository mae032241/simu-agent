"""WSL-to-VM transport for the command TCAD execution adapter."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor

from .transport_logs import preserve_log

from .execution_control import FileDescriptor, SolverCapabilitySnapshot, TCADJobSpec


class SSHTCADTransportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ssh_executable: str = Field(min_length=1, max_length=4096)
    identity_file: str | None = Field(default=None, min_length=1, max_length=4096)
    destination: str = Field(min_length=3, max_length=512)
    destination_resolver: tuple[str, ...] = Field(default=(), max_length=32)
    port: int = Field(default=22, ge=1, le=65535)
    host_key_alias: str | None = Field(default=None, min_length=1, max_length=512)
    known_hosts_file: str | None = Field(default=None, min_length=1, max_length=4096)
    remote_helper: str = Field(min_length=1, max_length=4096)
    remote_config: str = Field(min_length=1, max_length=4096)
    remote_exchange_root: str = Field(min_length=1, max_length=4096)
    connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    operation_timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_transfer_bytes: int = Field(default=512 * 1024 * 1024, ge=1, le=2**40)

    @field_validator(
        "ssh_executable", "remote_helper", "remote_config", "remote_exchange_root"
    )
    @classmethod
    def _safe_absolute(cls, value: str) -> str:
        if not Path(value).is_absolute() or not re.fullmatch(r"[A-Za-z0-9_./ ()-]+", value):
            raise ValueError("transport command paths must be safe absolute paths")
        return value


class RemoteClient(Protocol):
    def put(self, relative_path: str, raw: bytes) -> None: ...
    def rpc(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, local_path: str) -> bytes: ...
    def get_to(self, local_path: str, destination: Path, max_bytes: int) -> None: ...


class SSHRemoteClient:
    def __init__(self, config: SSHTCADTransportConfig, *, diagnostic_root: Path | None = None) -> None:
        executable = Path(config.ssh_executable)
        if not executable.is_file():
            raise ValueError("SSH executable does not exist")
        if config.destination_resolver and not Path(
            config.destination_resolver[0]
        ).is_file():
            raise ValueError("destination resolver executable does not exist")
        self.config = config
        self.diagnostic_root = diagnostic_root

    def _run(self, *args, **kwargs):
        try:
            return subprocess.run(*args, **kwargs)
        except subprocess.TimeoutExpired as error:
            if self.diagnostic_root is not None:
                preserve_log(self.diagnostic_root, "ssh-stderr", error.stderr or b"")
                preserve_log(self.diagnostic_root, "ssh-stdout", error.stdout or b"")
            raise

    def put(self, relative_path: str, raw: bytes) -> None:
        response, trailing = self._call(
            "put",
            {
                "relative_path": relative_path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            },
            raw,
        )
        if trailing:
            raise RuntimeError("VM upload returned unexpected bytes")
        _require_ok(response, "put")

    def rpc(self, request: dict[str, Any]) -> dict[str, Any]:
        response, trailing = self._call("rpc", {"request": request}, b"")
        if trailing:
            raise RuntimeError("VM RPC returned unexpected bytes")
        payload = _require_ok(response, "rpc")
        value = payload.get("response")
        if not isinstance(value, dict):
            raise RuntimeError("VM RPC response is not an object")
        return value

    def get(self, local_path: str) -> bytes:
        response, raw = self._call("get", {"local_path": local_path}, b"")
        payload = _require_ok(response, "get")
        if (
            payload.get("size_bytes") != len(raw)
            or payload.get("sha256") != hashlib.sha256(raw).hexdigest()
        ):
            raise RuntimeError("VM download differs from response descriptor")
        return raw

    def get_to(self, local_path: str, destination: Path, max_bytes: int) -> None:
        response, _ = self._call("get", {"local_path": local_path, "max_bytes": max_bytes}, b"",
                                 download_to=destination, download_limit=max_bytes)
        payload = _require_ok(response, "get")
        digest = hashlib.sha256()
        size = 0
        with destination.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        if payload.get("size_bytes") != size or payload.get("sha256") != digest.hexdigest():
            raise RuntimeError("VM download differs from response descriptor")

    def _call(
        self,
        operation: str,
        payload: dict[str, Any],
        body: bytes,
        *, download_to: Path | None = None, download_limit: int = 0,
    ) -> tuple[dict[str, Any], bytes]:
        request = _canonical(
            {"schema_version": 1, "operation": operation, "payload": payload}
        ) + b"\n" + body
        command = [
            self.config.ssh_executable,
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.config.connect_timeout_seconds}",
            "-o",
            "StrictHostKeyChecking=yes",
            "-p",
            str(self.config.port),
        ]
        if self.config.identity_file is not None:
            command.extend(("-i", self.config.identity_file))
        if self.config.host_key_alias is not None:
            command.extend(("-o", f"HostKeyAlias={self.config.host_key_alias}"))
        if self.config.known_hosts_file is not None:
            command.extend(
                ("-o", f"UserKnownHostsFile={self.config.known_hosts_file}")
            )
        command.extend(
            (
                self._destination(),
                f"{self.config.remote_helper} --config {self.config.remote_config}",
            )
        )
        download_stream = tempfile.TemporaryFile() if download_to is not None else None
        try:
            completed = self._run(
                command,
                input=request,
                stdout=download_stream if download_stream is not None else subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=_transport_environment(self.config.ssh_executable),
                timeout=self.config.operation_timeout_seconds,
                check=False,
            )
            if download_stream is not None:
                download_stream.seek(0)
                header = download_stream.readline(1024 * 1024 + 1)
                if not header.endswith(b"\n") or len(header) > 1024 * 1024:
                    raise RuntimeError("VM download returned no bounded header")
                response = json.loads(header)
                size = 0
                with download_to.open("wb") as stream:
                    for chunk in iter(lambda: download_stream.read(1024 * 1024), b""):
                        size += len(chunk)
                        if size > download_limit:
                            raise RuntimeError("VM download exceeds inspection bound")
                        stream.write(chunk)
                completed = subprocess.CompletedProcess(completed.args, completed.returncode,
                                                         stdout=header, stderr=completed.stderr)
        finally:
            if download_stream is not None:
                download_stream.close()
        if completed.stderr and self.diagnostic_root is not None:
            preserve_log(self.diagnostic_root, "ssh-stderr", completed.stderr)
        if completed.returncode != 0:
            if self.diagnostic_root is not None:
                preserve_log(self.diagnostic_root, "ssh-stdout", completed.stdout)
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"VM transport command failed{suffix}")
        header, separator, trailing = completed.stdout.partition(b"\n")
        if not separator or len(header) > 1024 * 1024:
            raise RuntimeError("VM transport returned no bounded header")
        response = json.loads(header)
        if not isinstance(response, dict):
            raise RuntimeError("VM transport response is not an object")
        return response, trailing

    def _destination(self) -> str:
        if not self.config.destination_resolver:
            return self.config.destination
        completed = self._run(
            list(self.config.destination_resolver),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_transport_environment(self.config.destination_resolver[0]),
            timeout=self.config.operation_timeout_seconds,
            check=False,
        )
        if completed.stderr and self.diagnostic_root is not None:
            preserve_log(self.diagnostic_root, "ssh-stderr", completed.stderr)
        if completed.returncode != 0:
            if self.diagnostic_root is not None:
                preserve_log(self.diagnostic_root, "ssh-stdout", completed.stdout)
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(
                f"VM destination resolver failed with exit code "
                f"{completed.returncode}{suffix}"
            )
        try:
            lines = completed.stdout.decode("utf-8", errors="strict").splitlines()
        except UnicodeDecodeError as error:
            raise RuntimeError("VM destination resolver returned invalid text") from error
        if len(lines) != 1 or lines[0].strip() != lines[0]:
            raise RuntimeError("VM destination resolver returned an invalid address")
        try:
            address = str(ipaddress.ip_address(lines[0]))
        except ValueError as error:
            raise RuntimeError("VM destination resolver returned an invalid address") from error
        user, separator, _ = self.config.destination.rpartition("@")
        return f"{user}@{address}" if separator else address


class SSHTCADTransport:
    def __init__(
        self,
        remote: RemoteClient,
        *,
        local_result_root: Path | str,
        remote_exchange_root: Path | str = "/var/lib/scidiscovery/execution-exchange",
    ) -> None:
        self.remote = remote
        self.local_result_root = Path(local_result_root).expanduser().absolute()
        self.local_result_root.mkdir(parents=True, exist_ok=True, mode=0o770)
        self.remote_exchange_root = Path(remote_exchange_root)
        if not self.remote_exchange_root.is_absolute():
            raise ValueError("remote exchange root must be absolute")

    def handle(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "capabilities":
            if payload:
                raise ValueError("capability discovery accepts no payload")
            value = self._rpc("tcad_capabilities", {})
            snapshots = tuple(
                SolverCapabilitySnapshot.model_validate_json(
                    _canonical(item), strict=True
                )
                for item in value.get("capabilities", ())
            )
            if not snapshots:
                raise RuntimeError("remote TCAD runner returned no capabilities")
            profiles = tuple(item.profile_id for item in snapshots)
            if len(profiles) != len(set(profiles)):
                raise RuntimeError("remote TCAD capability profiles are not unique")
            return {
                "capabilities": [item.model_dump(mode="json") for item in snapshots]
            }
        if operation == "prepare":
            return self._prepare(payload)
        if operation == "lookup_submission":
            marker = self._read_marker(payload["submission"])
            value = self._rpc(
                "tcad_lookup_submission",
                {
                    "submission_sha256": marker["remote_submission"]["sha256"]
                },
            )
            if value.get("found") is False:
                return {"found": False}
            return {
                "found": True,
                "run_id": value["run_id"],
                "state": value["state"],
            }
        if operation == "submit":
            marker = self._read_marker(payload["submission"])
            value = self._rpc("tcad_submit", {"submission": marker["remote_submission"]})
            return {"run_id": value["run_id"], "state": value["state"]}
        if operation == "status":
            value = self._rpc("tcad_status", {"run_id": payload["run_id"]})
            return {"state": value["state"]}
        if operation == "cancel":
            value = self._rpc("tcad_cancel", {"run_id": payload["run_id"]})
            return {"state": value["state"]}
        if operation == "inspect_outputs":
            return self._inspect_outputs(str(payload["run_id"]), payload.get("relative_path"), payload.get("max_bytes", 32*1024*1024))
        if operation == "collect":
            return self._collect(str(payload["run_id"]))
        raise ValueError("unsupported TCAD transport operation")

    def _prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_descriptor = FileDescriptor.model_validate(payload["job_spec"], strict=True)
        archive_descriptor = FileDescriptor.model_validate(payload["archive"], strict=True)
        job_raw = _read_descriptor(job_descriptor)
        archive_raw = _read_descriptor(archive_descriptor)
        job = TCADJobSpec.model_validate_json(job_raw, strict=True)
        if job.input_archive != archive_descriptor:
            raise ValueError("job archive binding differs from prepare archive")
        digest = hashlib.sha256(job_raw).hexdigest()
        prefix = f"transport/{digest}"
        remote_archive_path = str(self.remote_exchange_root / prefix / "project.tar")
        self.remote.put(f"{prefix}/project.tar", archive_raw)
        remote_archive = job.input_archive.model_copy(
            update={"local_path": remote_archive_path}
        )
        remote_job = job.model_copy(update={"input_archive": remote_archive})
        remote_job_raw = _canonical(remote_job.model_dump(mode="python"))
        self.remote.put(f"{prefix}/job.json", remote_job_raw)
        remote_submission = FileDescriptor(
            name="execution_payload",
            local_path=str(self.remote_exchange_root / prefix / "job.json"),
            sha256=hashlib.sha256(remote_job_raw).hexdigest(),
            size_bytes=len(remote_job_raw),
            media_type="application/json",
        )
        marker_raw = _canonical(
            {
                "schema_version": 1,
                "remote_submission": remote_submission.model_dump(mode="json"),
            }
        )
        marker_path = self.local_result_root / "submissions" / f"{digest}.json"
        _write_immutable(marker_path, marker_raw)
        return {
            "submission": _local_descriptor(
                "execution_payload", marker_path, "application/json"
            ).model_dump(mode="json")
        }

    def _read_marker(self, value: dict[str, Any]) -> dict[str, Any]:
        descriptor = LocalFileDescriptor.model_validate(value, strict=True)
        path = Path(descriptor.local_path).absolute()
        if not _within(path, self.local_result_root):
            raise ValueError("transport submission marker is outside result root")
        raw = _read_local_descriptor(descriptor)
        marker = json.loads(raw)
        if marker.get("schema_version") != 1:
            raise ValueError("transport submission marker is invalid")
        FileDescriptor.model_validate(marker.get("remote_submission"), strict=True)
        return marker

    def _inspect_outputs(self, run_id: str, relative_path: str | None, max_bytes: int) -> dict[str, Any]:
        if not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
            raise ValueError("invalid TCAD run identity")
        value = self._rpc("tcad_inspect_outputs", {"run_id": run_id, "relative_path": relative_path, "max_bytes": max_bytes})
        if value.get("status") != "available" or "file" not in value:
            return value
        descriptor = FileDescriptor.model_validate(value["file"], strict=True)
        if descriptor.size_bytes > min(max_bytes, 32 * 1024 * 1024):
            raise ValueError("inspection file exceeds limit")
        path = self.local_result_root / "inspection" / run_id / descriptor.sha256
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as directory:
            temporary = Path(directory) / "download"
            self.remote.get_to(descriptor.local_path, temporary, min(max_bytes, 32 * 1024 * 1024))
            observed = _local_descriptor("candidate", temporary, descriptor.media_type)
            if observed.size_bytes != descriptor.size_bytes or observed.sha256 != descriptor.sha256:
                return {"status": "changed_since_inspection", "reason": "download_changed"}
            os.chmod(temporary, 0o400)
            if path.exists():
                existing = _local_descriptor("candidate", path, descriptor.media_type)
                if existing.sha256 != descriptor.sha256:
                    raise RuntimeError("immutable inspection copy changed")
            else:
                os.link(temporary, path)
        return {**value, "file": _local_descriptor("candidate", path, descriptor.media_type).model_dump(mode="json")}

    def _collect(self, run_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
            raise ValueError("invalid TCAD run identity")
        value = self._rpc("tcad_collect", {"run_id": run_id})
        output_directory = self.local_result_root / "runs" / run_id
        outputs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in value["outputs"]:
            remote_descriptor = FileDescriptor.model_validate(item, strict=True)
            if remote_descriptor.name in seen:
                raise RuntimeError("remote result names are not unique")
            seen.add(remote_descriptor.name)
            raw = self.remote.get(remote_descriptor.local_path)
            if (
                len(raw) != remote_descriptor.size_bytes
                or hashlib.sha256(raw).hexdigest() != remote_descriptor.sha256
            ):
                raise RuntimeError("downloaded result differs from remote descriptor")
            name = re.sub(r"[^A-Za-z0-9_.-]+", "_", remote_descriptor.name)
            path = output_directory / name
            _write_immutable(path, raw)
            outputs.append(
                _local_descriptor(
                    remote_descriptor.name,
                    path,
                    remote_descriptor.media_type,
                ).model_dump(mode="json")
            )
        return {"outputs": outputs}

    def _rpc(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        response = self.remote.rpc(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            }
        )
        if response.get("id") != request_id:
            raise RuntimeError("remote TCAD response identity differs")
        if "error" in response:
            raise RuntimeError(str(response["error"].get("message", "remote TCAD call failed")))
        try:
            value = response["result"]["structuredContent"]
        except (KeyError, TypeError) as error:
            raise RuntimeError("remote TCAD response has no structured result") from error
        if not isinstance(value, dict):
            raise RuntimeError("remote TCAD result is not an object")
        return value


def _read_descriptor(descriptor: FileDescriptor) -> bytes:
    path = Path(descriptor.local_path).absolute()
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("transport input is not a regular file")
    raw = path.read_bytes()
    if len(raw) != descriptor.size_bytes or hashlib.sha256(raw).hexdigest() != descriptor.sha256:
        raise ValueError("transport input differs from descriptor")
    return raw


def _read_local_descriptor(descriptor: LocalFileDescriptor) -> bytes:
    path = Path(descriptor.local_path).absolute()
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("local descriptor is not a regular file")
    raw = path.read_bytes()
    if len(raw) != descriptor.size_bytes or hashlib.sha256(raw).hexdigest() != descriptor.sha256:
        raise ValueError("local file differs from descriptor")
    return raw


def _write_immutable(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o770)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError("existing local transport file differs")
        return
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, 0o440)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _local_descriptor(name: str, path: Path, media_type: str) -> LocalFileDescriptor:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return LocalFileDescriptor(
        name=name,
        local_path=str(path),
        sha256=digest.hexdigest(),
        size_bytes=size,
        media_type=media_type,
    )


def _require_ok(response: dict[str, Any], operation: str) -> dict[str, Any]:
    if response.get("schema_version") != 1 or response.get("operation") != operation:
        raise RuntimeError("VM transport response envelope differs")
    if response.get("ok") is not True or not isinstance(response.get("payload"), dict):
        raise RuntimeError("VM transport rejected operation")
    return response["payload"]


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _transport_environment(executable: str) -> dict[str, str]:
    environment = dict(os.environ)
    if executable.lower().endswith(".exe") and not environment.get("WSL_INTEROP"):
        candidates: list[tuple[int, Path]] = []
        for path in Path("/run/WSL").glob("*_interop"):
            try:
                metadata = os.stat(path)
            except FileNotFoundError:
                continue
            if stat.S_ISSOCK(metadata.st_mode):
                candidates.append((metadata.st_mtime_ns, path))
        if not candidates:
            raise RuntimeError("no active WSL interop socket is available for ssh.exe")
        environment["WSL_INTEROP"] = str(max(candidates)[1])
    return environment


def _read_config(path: Path) -> SSHTCADTransportConfig:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("SSH transport configuration must be a regular file")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise ValueError("SSH transport configuration must not be group/world writable")
    return SSHTCADTransportConfig.model_validate_json(path.read_bytes(), strict=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-tcad-transport")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    operation = "unknown"
    try:
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        if not raw or len(raw) > 1024 * 1024:
            raise ValueError("transport request is missing or too large")
        request = json.loads(raw)
        if request.get("schema_version") != 1 or not isinstance(request.get("payload"), dict):
            raise ValueError("transport request envelope is invalid")
        operation = str(request.get("operation"))
        config = _read_config(args.config)
        transport = SSHTCADTransport(
            SSHRemoteClient(config, diagnostic_root=Path(os.environ.get(
                "SCIDISCOVERY_TCAD_RESULT_ROOT", "/var/lib/scidiscovery/transport-results"
            ))),
            local_result_root=os.environ.get(
                "SCIDISCOVERY_TCAD_RESULT_ROOT", "/var/lib/scidiscovery/transport-results"
            ),
            remote_exchange_root=config.remote_exchange_root,
        )
        payload = transport.handle(operation, request["payload"])
        response = {"schema_version": 1, "operation": operation, "ok": True, "payload": payload}
    except Exception as error:
        response = {
            "schema_version": 1,
            "operation": operation,
            "ok": False,
            "error": str(error),
            "payload": {},
        }
    sys.stdout.buffer.write(_canonical(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RemoteClient",
    "SSHRemoteClient",
    "SSHTCADTransport",
    "SSHTCADTransportConfig",
    "main",
]
