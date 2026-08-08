from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
import tcad_artifact.remote_runner_py36 as remote_runner

from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    ProjectExpectedOutput,
    ProjectResourceLimits,
    package_deck_project,
)
from tcad_artifact.ssh_transport import (
    SSHRemoteClient,
    SSHTCADTransport,
    SSHTCADTransportConfig,
)


class FakeRemote:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.results: dict[str, bytes] = {
            "/remote/runs/run_0123456789abcdef0123456789abcdef/profile.plx": b"profile\n",
            "/remote/runs/run_0123456789abcdef0123456789abcdef/worker.log": b"done\n",
            "/remote/runs/run_0123456789abcdef0123456789abcdef/output_manifest.json": b'{"exit_code":0,"terminal_state":"succeeded"}',
        }

    def put(self, relative_path: str, raw: bytes) -> None:
        previous = self.uploads.setdefault(relative_path, raw)
        assert previous == raw

    def rpc(self, request: dict[str, object]) -> dict[str, object]:
        name = request["params"]["name"]  # type: ignore[index]
        request_id = request["id"]
        if name == "tcad_submit":
            result = {
                "run_id": "run_0123456789abcdef0123456789abcdef",
                "state": "accepted",
            }
        elif name == "tcad_status":
            result = {"state": "succeeded"}
        elif name == "tcad_cancel":
            result = {"state": "cancelling"}
        else:
            paths = tuple(self.results)
            result = {
                "outputs": [
                    _remote_descriptor("profile", paths[0], "text/plain"),
                    _remote_descriptor(
                        "tcad_log", paths[1], "text/plain; charset=utf-8"
                    ),
                    _remote_descriptor(
                        "tcad_manifest", paths[2], "application/json"
                    ),
                ]
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"structuredContent": result},
        }

    def get(self, local_path: str) -> bytes:
        return self.results[local_path]


class ProcessRemote:
    def __init__(self, runner: Path, config: Path) -> None:
        self.runner = runner
        self.config = config

    def put(self, relative_path: str, raw: bytes) -> None:
        self._call(
            "put",
            {
                "relative_path": relative_path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            },
            raw,
        )

    def rpc(self, request: dict[str, object]) -> dict[str, object]:
        payload, trailing = self._call("rpc", {"request": request}, b"")
        assert trailing == b""
        return payload["response"]

    def get(self, local_path: str) -> bytes:
        payload, raw = self._call("get", {"local_path": local_path}, b"")
        assert payload["sha256"] == hashlib.sha256(raw).hexdigest()
        return raw

    def _call(
        self, operation: str, payload: dict[str, object], body: bytes
    ) -> tuple[dict[str, object], bytes]:
        request = json.dumps(
            {"schema_version": 1, "operation": operation, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n" + body
        completed = subprocess.run(
            [sys.executable, str(self.runner), "--config", str(self.config)],
            input=request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        header, trailing = completed.stdout.split(b"\n", 1)
        response = json.loads(header)
        assert response["ok"] is True
        assert response["operation"] == operation
        return response["payload"], trailing


def _remote_descriptor(name: str, path: str, media_type: str) -> dict[str, object]:
    raw = FakeRemote().results[path]
    return {
        "name": name,
        "local_path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "media_type": media_type,
    }


def _draft() -> DeckProjectDraft:
    return DeckProjectDraft(
        tool_profile="sentaurus-sprocess-r2020.09",
        files=(DeckFile(relative_path="fig4.cmd", content="line x location=0.0\n"),),
        entrypoint="fig4.cmd",
        expected_outputs=(
            ProjectExpectedOutput(
                name="profile",
                relative_path="profile.plx",
                media_type="text/plain",
                required=True,
                max_bytes=1024,
            ),
        ),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=30,
            cpu_time_seconds=30,
            max_memory_bytes=1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=4,
        ),
    )


def test_ssh_transport_prepares_submits_and_collects_without_waiting(
    tmp_path: Path,
) -> None:
    packaged = package_deck_project(_draft(), output_root=tmp_path / "packages")
    remote = FakeRemote()
    transport = SSHTCADTransport(
        remote,
        local_result_root=tmp_path / "results",
        remote_exchange_root="/remote/exchange",
    )
    prepared = transport.handle(
        "prepare",
        {
            "job_spec": packaged.job_spec_file.model_dump(mode="json"),
            "archive": packaged.archive.model_dump(mode="json"),
        },
    )
    assert set(remote.uploads) == {
        next(path for path in remote.uploads if path.endswith("/project.tar")),
        next(path for path in remote.uploads if path.endswith("/job.json")),
    }
    assert transport.handle("submit", prepared) == {
        "run_id": "run_0123456789abcdef0123456789abcdef",
        "state": "accepted",
    }
    assert transport.handle(
        "status", {"run_id": "run_0123456789abcdef0123456789abcdef"}
    ) == {"state": "succeeded"}
    assert transport.handle(
        "cancel", {"run_id": "run_0123456789abcdef0123456789abcdef"}
    ) == {"state": "cancelling"}
    collected = transport.handle(
        "collect", {"run_id": "run_0123456789abcdef0123456789abcdef"}
    )
    assert [item["name"] for item in collected["outputs"]] == [
        "profile",
        "tcad_log",
        "tcad_manifest",
    ]
    assert all(Path(item["local_path"]).is_file() for item in collected["outputs"])


def test_vm_destination_resolver_replaces_stale_host_and_preserves_user(
    tmp_path: Path,
) -> None:
    resolver = tmp_path / "resolve-ip"
    resolver.write_text("#!/bin/sh\nprintf '192.0.2.34\\n'\n", encoding="utf-8")
    resolver.chmod(0o750)
    config = SSHTCADTransportConfig(
        ssh_executable="/bin/true",
        destination="tcad@192.0.2.10",
        destination_resolver=(str(resolver),),
        remote_helper="/home/tcad/runner",
        remote_config="/home/tcad/runner.json",
        remote_exchange_root="/home/tcad/exchange",
    )

    assert SSHRemoteClient(config)._destination() == "tcad@192.0.2.34"


def test_vm_destination_resolver_rejects_non_ip_output(tmp_path: Path) -> None:
    resolver = tmp_path / "resolve-ip"
    resolver.write_text("#!/bin/sh\nprintf 'not-an-ip\\n'\n", encoding="utf-8")
    resolver.chmod(0o750)
    config = SSHTCADTransportConfig(
        ssh_executable="/bin/true",
        destination="tcad@192.0.2.10",
        destination_resolver=(str(resolver),),
        remote_helper="/home/tcad/runner",
        remote_config="/home/tcad/runner.json",
        remote_exchange_root="/home/tcad/exchange",
    )

    with pytest.raises(RuntimeError, match="invalid address"):
        SSHRemoteClient(config)._destination()


def test_vm_destination_resolver_reports_bounded_stderr(tmp_path: Path) -> None:
    resolver = tmp_path / "resolve-ip"
    resolver.write_text(
        "#!/bin/sh\nprintf 'interop denied\\n' >&2\nexit 7\n", encoding="utf-8"
    )
    resolver.chmod(0o750)
    config = SSHTCADTransportConfig(
        ssh_executable="/bin/true",
        destination="tcad@192.0.2.10",
        destination_resolver=(str(resolver),),
        remote_helper="/home/tcad/runner",
        remote_config="/home/tcad/runner.json",
        remote_exchange_root="/home/tcad/exchange",
    )

    with pytest.raises(
        RuntimeError, match="exit code 7: interop denied"
    ):
        SSHRemoteClient(config)._destination()


def test_remote_runner_preserves_tool_symlink_launch_name(tmp_path: Path) -> None:
    target = tmp_path / "GENERIC"
    target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    target.chmod(0o750)
    alias = tmp_path / "sprocess"
    alias.symlink_to(target.name)
    config = tmp_path / "runner.json"
    config.write_text(
        json.dumps(
            {
                "exchange_root": str(tmp_path / "exchange"),
                "state_root": str(tmp_path / "state"),
                "result_root": str(tmp_path / "state/runs"),
                "tools": [
                    {
                        "profile_id": "identity-sensitive-tool",
                        "executable": str(alias),
                        "arguments": [],
                        "environment": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    loaded = remote_runner._load_config(str(config))
    assert loaded["tools"][0]["executable"] == str(alias.absolute())


def test_remote_runner_uses_portable_c_locale() -> None:
    environment = remote_runner._runtime_environment("/tmp/run")
    assert environment["LANG"] == "C"
    assert environment["LC_ALL"] == "C"


def test_dependency_free_remote_runner_completes_full_transport_lifecycle(
    tmp_path: Path,
) -> None:
    exchange = tmp_path / "remote-exchange"
    state = tmp_path / "remote-state"
    exchange.mkdir()
    state.mkdir()
    config = tmp_path / "runner.json"
    config.write_text(
        json.dumps(
            {
                "exchange_root": str(exchange),
                "state_root": str(state),
                "result_root": str(state / "runs"),
                "max_concurrent_runs": 1,
                "max_transfer_bytes": 8 * 1024 * 1024,
                "tools": [
                    {
                        "profile_id": "shell-smoke",
                        "executable": "/bin/sh",
                        "arguments": [],
                        "environment": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    draft = DeckProjectDraft(
        tool_profile="shell-smoke",
        files=(
            DeckFile(
                relative_path="run.sh",
                content="printf 'profile\\n' > profile.plx\n",
            ),
        ),
        entrypoint="run.sh",
        expected_outputs=(
            ProjectExpectedOutput(
                name="profile",
                relative_path="profile.plx",
                media_type="text/plain",
                required=True,
                max_bytes=1024,
            ),
        ),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=10,
            cpu_time_seconds=10,
            max_memory_bytes=128 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=4,
        ),
    )
    packaged = package_deck_project(draft, output_root=tmp_path / "direct-package")
    runner = (
        Path(__file__).resolve().parents[2]
        / "plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"
    )
    transport = SSHTCADTransport(
        ProcessRemote(runner, config),
        local_result_root=tmp_path / "local-results",
        remote_exchange_root=exchange,
    )
    prepared = transport.handle(
        "prepare",
        {
            "job_spec": packaged.job_spec_file.model_dump(mode="json"),
            "archive": packaged.archive.model_dump(mode="json"),
        },
    )
    submitted = transport.handle("submit", prepared)
    deadline = time.monotonic() + 5
    while True:
        status = transport.handle("status", {"run_id": submitted["run_id"]})
        if status["state"] == "succeeded":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    collected = transport.handle("collect", {"run_id": submitted["run_id"]})
    profile = next(item for item in collected["outputs"] if item["name"] == "profile")
    assert Path(profile["local_path"]).read_text(encoding="utf-8") == "profile\n"
    remote_profile = state / "runs" / submitted["run_id"] / "work/profile.plx"
    assert remote_profile.stat().st_mode & 0o222 == 0
    remote_profile.chmod(0o640)
    remote_profile.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="completed output differs from its manifest"):
        transport.handle("collect", {"run_id": submitted["run_id"]})


def test_dependency_free_remote_runner_rejects_tampered_upload(
    tmp_path: Path,
) -> None:
    config, runner = _runner_fixture(tmp_path)
    request = json.dumps(
        {
            "schema_version": 1,
            "operation": "put",
            "payload": {
                "relative_path": "case/input.dat",
                "sha256": hashlib.sha256(b"expected").hexdigest(),
                "size_bytes": len(b"tampered"),
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode() + b"\n" + b"tampered"
    completed = subprocess.run(
        [sys.executable, str(runner), "--config", str(config)],
        input=request,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode != 0
    assert b"uploaded bytes differ from descriptor" in completed.stderr


def test_dependency_free_remote_runner_cancels_with_terminal_markers(
    tmp_path: Path,
) -> None:
    exchange = tmp_path / "remote-exchange"
    state = tmp_path / "remote-state"
    exchange.mkdir()
    state.mkdir()
    config = tmp_path / "runner.json"
    config.write_text(
        json.dumps(
            {
                "exchange_root": str(exchange),
                "state_root": str(state),
                "result_root": str(state / "runs"),
                "max_concurrent_runs": 1,
                "max_transfer_bytes": 8 * 1024 * 1024,
                "tools": [
                    {
                        "profile_id": "shell-smoke",
                        "executable": "/bin/sh",
                        "arguments": [],
                        "environment": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    draft = DeckProjectDraft(
        tool_profile="shell-smoke",
        files=(DeckFile(relative_path="run.sh", content="sleep 30\n"),),
        entrypoint="run.sh",
        expected_outputs=(
            ProjectExpectedOutput(
                name="profile",
                relative_path="profile.plx",
                media_type="text/plain",
                required=False,
                max_bytes=1024,
            ),
        ),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=60,
            cpu_time_seconds=60,
            max_memory_bytes=128 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=4,
        ),
    )
    packaged = package_deck_project(draft, output_root=tmp_path / "cancel-package")
    runner = (
        Path(__file__).resolve().parents[2]
        / "plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"
    )
    transport = SSHTCADTransport(
        ProcessRemote(runner, config),
        local_result_root=tmp_path / "local-results",
        remote_exchange_root=exchange,
    )
    prepared = transport.handle(
        "prepare",
        {
            "job_spec": packaged.job_spec_file.model_dump(mode="json"),
            "archive": packaged.archive.model_dump(mode="json"),
        },
    )
    submitted = transport.handle("submit", prepared)
    cancelling = transport.handle("cancel", {"run_id": submitted["run_id"]})
    assert cancelling["state"] in {"cancelling", "cancelled"}
    deadline = time.monotonic() + 8
    while True:
        status = transport.handle("status", {"run_id": submitted["run_id"]})
        if status["state"] == "cancelled":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    run_dir = state / "runs" / submitted["run_id"]
    assert (run_dir / "cancel_requested").is_file()
    assert (run_dir / "done").is_file()
    assert (run_dir / "status").read_text(encoding="ascii").strip() == "130"
    collected = transport.handle("collect", {"run_id": submitted["run_id"]})
    assert [item["name"] for item in collected["outputs"]] == [
        "tcad_log",
        "tcad_manifest",
    ]
    manifest = next(
        item for item in collected["outputs"] if item["name"] == "tcad_manifest"
    )
    value = json.loads(Path(manifest["local_path"]).read_text(encoding="utf-8"))
    assert value["terminal_state"] == "cancelled"
    assert value["exit_code"] == 130


def test_dependency_free_remote_runner_rejects_result_path_escape(
    tmp_path: Path,
) -> None:
    config, runner = _runner_fixture(tmp_path)
    outside = tmp_path / "outside.dat"
    outside.write_bytes(b"not a result")
    request = json.dumps(
        {
            "schema_version": 1,
            "operation": "get",
            "payload": {"local_path": str(outside)},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode() + b"\n"
    completed = subprocess.run(
        [sys.executable, str(runner), "--config", str(config)],
        input=request,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode != 0
    assert b"outside configured root" in completed.stderr


def test_dependency_free_remote_runner_rejects_non_hex_run_identity(
    tmp_path: Path,
) -> None:
    config, runner = _runner_fixture(tmp_path)
    transport = SSHTCADTransport(
        ProcessRemote(runner, config),
        local_result_root=tmp_path / "local-results",
        remote_exchange_root=tmp_path / "remote-exchange",
    )
    with pytest.raises(RuntimeError, match="invalid run identity"):
        transport.handle("status", {"run_id": "run_../../escape0000000000000000000"})


def _runner_fixture(tmp_path: Path) -> tuple[Path, Path]:
    exchange = tmp_path / "remote-exchange"
    state = tmp_path / "remote-state"
    exchange.mkdir()
    state.mkdir()
    config = tmp_path / "runner.json"
    config.write_text(
        json.dumps(
            {
                "exchange_root": str(exchange),
                "state_root": str(state),
                "result_root": str(state / "runs"),
                "max_concurrent_runs": 1,
                "max_transfer_bytes": 1024,
                "tools": [
                    {
                        "profile_id": "shell-smoke",
                        "executable": "/bin/sh",
                        "arguments": [],
                        "environment": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    runner = (
        Path(__file__).resolve().parents[2]
        / "plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"
    )
    return config, runner
