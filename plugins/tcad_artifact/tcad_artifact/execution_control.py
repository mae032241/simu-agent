"""Execution-only TCAD dispatcher and MCP surface."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tarfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


def _validate_relative_path(value: str) -> str:
    if value.startswith("/") or "\\" in value or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise ValueError("unsafe relative path")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class FileDescriptor(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    local_path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=2**50)
    media_type: str = Field(min_length=3, max_length=255)


class ResourceLimits(StrictModel):
    wall_time_seconds: int = Field(ge=1, le=604800)
    cpu_time_seconds: int = Field(ge=1, le=604800)
    max_memory_bytes: int = Field(ge=1, le=2**50)
    max_output_bytes: int = Field(ge=1, le=2**50)
    max_processes: int = Field(ge=1, le=4096)


class ArchiveEntry(StrictModel):
    relative_path: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=2**50)

    _safe_path = field_validator("relative_path")(_validate_relative_path)


class ExpectedOutput(StrictModel):
    name: str = Field(min_length=1, max_length=256)
    relative_path: str = Field(min_length=1, max_length=1024)
    media_type: str = Field(min_length=3, max_length=255)
    required: bool = True
    max_bytes: int = Field(ge=1, le=2**50)

    _safe_path = field_validator("relative_path")(_validate_relative_path)


class TCADJobSpec(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    tool_profile: str = Field(min_length=1, max_length=256)
    input_archive: FileDescriptor
    archive_entries: tuple[ArchiveEntry, ...] = Field(min_length=1, max_length=4096)
    arguments: tuple[str, ...] = Field(default=(), max_length=256)
    expected_outputs: tuple[ExpectedOutput, ...] = Field(max_length=4096)
    limits: ResourceLimits

    @model_validator(mode="after")
    def _unique_paths(self) -> TCADJobSpec:
        inputs = tuple(item.relative_path for item in self.archive_entries)
        outputs = tuple(item.relative_path for item in self.expected_outputs)
        names = tuple(item.name for item in self.expected_outputs)
        if len(inputs) != len(set(inputs)):
            raise ValueError("archive entry paths must be unique")
        if len(outputs) != len(set(outputs)) or len(names) != len(set(names)):
            raise ValueError("expected output paths and names must be unique")
        if any("\x00" in value or len(value) > 4096 for value in self.arguments):
            raise ValueError("job argument is invalid")
        return self


class ToolProfile(StrictModel):
    profile_id: str = Field(min_length=1, max_length=256)
    executable: str = Field(min_length=1, max_length=4096)
    arguments: tuple[str, ...] = Field(default=(), max_length=256)
    environment: dict[str, str] = Field(default_factory=dict)

    @field_validator("executable")
    @classmethod
    def _absolute_executable(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("tool executable must be absolute")
        return value


class TCADExecutionPolicy(StrictModel):
    allowed_input_roots: tuple[str, ...] = Field(min_length=1, max_length=32)
    tools: tuple[ToolProfile, ...] = Field(min_length=1, max_length=128)
    max_concurrent_runs: int = Field(default=1, ge=1, le=128)
    preparation_timeout_seconds: int = Field(default=30, ge=1, le=300)

    @model_validator(mode="after")
    def _valid_policy(self) -> TCADExecutionPolicy:
        roots = tuple(str(Path(value).expanduser().absolute()) for value in self.allowed_input_roots)
        profiles = tuple(tool.profile_id for tool in self.tools)
        if len(roots) != len(set(roots)) or len(profiles) != len(set(profiles)):
            raise ValueError("policy roots and tool profiles must be unique")
        object.__setattr__(self, "allowed_input_roots", roots)
        return self

    def tool(self, profile_id: str) -> ToolProfile:
        for profile in self.tools:
            if profile.profile_id == profile_id:
                return profile
        raise ExecutionToolError("TCAD tool profile is not allowed")


class ExecutionToolError(RuntimeError):
    pass


class ExecutionToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubmitInput(ExecutionToolInput):
    submission: FileDescriptor


class RunIdInput(ExecutionToolInput):
    run_id: str = Field(min_length=1, max_length=256)


@dataclass(frozen=True)
class ExecutionTool:
    name: str
    description: str
    input_model: type[ExecutionToolInput]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }


EXECUTION_TOOLS = (
    ExecutionTool("tcad_submit", "Submit one prepared TCAD job and return immediately.", SubmitInput),
    ExecutionTool("tcad_status", "Read one short durable TCAD job status.", RunIdInput),
    ExecutionTool("tcad_cancel", "Request cancellation of one TCAD job.", RunIdInput),
    ExecutionTool("tcad_collect", "Return local descriptors for terminal TCAD outputs.", RunIdInput),
)


class TCADExecutionFacade:
    """Own only TCAD runtime state; scientific identity remains outside."""

    def __init__(
        self,
        *,
        policy: TCADExecutionPolicy,
        state_root: Path | str,
    ) -> None:
        self.policy = policy
        self.state_root = Path(state_root).expanduser().absolute()
        self.runs_root = self.state_root / "runs"
        self.database_path = self.state_root / "submissions.sqlite3"
        self.runs_root.mkdir(parents=True, exist_ok=True, mode=0o770)
        self._initialize()

    def tcad_submit(self, *, submission: FileDescriptor) -> dict[str, Any]:
        raw = self._read_input(submission)
        try:
            job = TCADJobSpec.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise ExecutionToolError("TCAD job specification is invalid") from error
        job_raw = _canonical(job.model_dump(mode="python"))
        if raw not in {job_raw, job_raw + b"\n"}:
            raise ExecutionToolError("TCAD job specification must use canonical JSON")
        archive = self._read_input(job.input_archive)
        digest = hashlib.sha256(job_raw).hexdigest()
        self._reconcile_active()
        submitted_at = _timestamp()
        run_id = f"run_{uuid.uuid4().hex}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT run_id FROM submissions WHERE job_sha256 = ?", (digest,)
            ).fetchone()
            if previous is not None:
                connection.execute("ROLLBACK")
                return self.tcad_status(run_id=previous["run_id"])
            active = connection.execute(
                """
                SELECT COUNT(*) AS count FROM submissions
                WHERE lifecycle_state IN ('preparing', 'running', 'cancel_requested')
                """
            ).fetchone()["count"]
            if active >= self.policy.max_concurrent_runs:
                connection.execute("ROLLBACK")
                raise ExecutionToolError("TCAD concurrent run limit is reached")
            connection.execute(
                """
                INSERT INTO submissions (
                    job_sha256, run_id, submitted_at, lifecycle_state
                ) VALUES (?, ?, ?, 'preparing')
                """,
                (digest, run_id, submitted_at),
            )
            connection.execute("COMMIT")

        tool = self.policy.tool(job.tool_profile)
        executable = _verified_executable(tool.executable)
        run_dir = self.runs_root / run_id
        process: subprocess.Popen[bytes] | None = None
        try:
            run_dir.mkdir(mode=0o770)
            work_dir = run_dir / "work"
            _extract_archive(archive, job.archive_entries, work_dir)
            runtime = {
                "arguments": [*tool.arguments, *job.arguments],
                "environment": dict(tool.environment),
                "executable": str(executable),
                "expected_outputs": [
                    item.model_dump(mode="python") for item in job.expected_outputs
                ],
                "limits": job.limits.model_dump(mode="python"),
            }
            _write_new(run_dir / "job.json", _canonical(runtime), mode=0o440)
            _write_new(run_dir / "submitted_at", (submitted_at + "\n").encode("ascii"), mode=0o440)
            with self._connect() as connection:
                lifecycle_state = connection.execute(
                    "SELECT lifecycle_state FROM submissions WHERE run_id = ?",
                    (run_id,),
                ).fetchone()["lifecycle_state"]
            if lifecycle_state == "cancel_requested":
                _write_abandoned_terminal(
                    run_dir,
                    terminal_state="cancelled",
                    exit_code=130,
                    error="cancelled_before_launch",
                )
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE submissions SET lifecycle_state = 'terminal' WHERE run_id = ?",
                        (run_id,),
                    )
                return self.tcad_status(run_id=run_id)
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("worker.py")), str(run_dir)],
                cwd=run_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            _write_new(run_dir / "launcher_pid", f"{process.pid}\n".encode("ascii"), mode=0o440)
            identity = _process_identity(process.pid)
            if identity is None:
                raise ExecutionToolError("TCAD worker identity is unavailable after launch")
            _write_new(
                run_dir / "launcher_identity",
                (identity + "\n").encode("ascii"),
                mode=0o440,
            )
            with self._connect() as connection:
                updated = connection.execute(
                    """
                    UPDATE submissions SET lifecycle_state = 'running'
                    WHERE run_id = ? AND lifecycle_state = 'preparing'
                    """,
                    (run_id,),
                )
                lifecycle_state = connection.execute(
                    "SELECT lifecycle_state FROM submissions WHERE run_id = ?",
                    (run_id,),
                ).fetchone()["lifecycle_state"]
            if updated.rowcount == 0 and lifecycle_state == "cancel_requested":
                (run_dir / "cancel_requested").touch(exist_ok=True)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        except Exception:
            if process is not None:
                _terminate_process_group(process.pid)
            with self._connect() as connection:
                connection.execute("DELETE FROM submissions WHERE run_id = ?", (run_id,))
            shutil.rmtree(run_dir, ignore_errors=True)
            raise
        return {"run_id": run_id, "state": "accepted", "accepted_at": submitted_at}

    def tcad_status(self, *, run_id: str) -> dict[str, Any]:
        row = self._submission_row(run_id)
        run_dir = self.runs_root / run_id
        submitted = row["submitted_at"]
        if (run_dir / "done").is_file():
            manifest = _read_json(run_dir / "output_manifest.json")
            with self._connect() as connection:
                connection.execute(
                    "UPDATE submissions SET lifecycle_state = 'terminal' WHERE run_id = ?",
                    (run_id,),
                )
            return {
                "run_id": run_id,
                "state": manifest["terminal_state"],
                "accepted_at": submitted,
                "exit_code": manifest["exit_code"],
                "done": True,
            }
        if row["lifecycle_state"] == "cancel_requested":
            identity_exists = (run_dir / "launcher_identity").is_file()
            if identity_exists and _recorded_process_is_alive(run_dir):
                (run_dir / "cancel_requested").touch(exist_ok=True)
                try:
                    launcher_pid = int(
                        (run_dir / "launcher_pid").read_text(encoding="ascii").strip()
                    )
                    os.killpg(launcher_pid, signal.SIGTERM)
                except (FileNotFoundError, ProcessLookupError, ValueError):
                    pass
                return {
                    "run_id": run_id,
                    "state": "cancelling",
                    "accepted_at": submitted,
                    "exit_code": None,
                    "done": False,
                }
            if identity_exists or (
                _elapsed_seconds(submitted) >= self.policy.preparation_timeout_seconds
            ):
                run_dir.mkdir(mode=0o770, exist_ok=True)
                _write_abandoned_terminal(
                    run_dir,
                    terminal_state="cancelled",
                    exit_code=130,
                    error="cancelled",
                )
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE submissions SET lifecycle_state = 'terminal' WHERE run_id = ?",
                        (run_id,),
                    )
                return {
                    "run_id": run_id,
                    "state": "cancelled",
                    "accepted_at": submitted,
                    "exit_code": 130,
                    "done": True,
                }
            return {
                "run_id": run_id,
                "state": "cancelling",
                "accepted_at": submitted,
                "exit_code": None,
                "done": False,
            }
        if row["lifecycle_state"] == "preparing":
            if (run_dir / "launcher_identity").is_file() and _recorded_process_is_alive(
                run_dir
            ):
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE submissions SET lifecycle_state = 'running' WHERE run_id = ?",
                        (run_id,),
                    )
            elif _elapsed_seconds(submitted) >= self.policy.preparation_timeout_seconds:
                run_dir.mkdir(mode=0o770, exist_ok=True)
                _write_abandoned_terminal(
                    run_dir,
                    terminal_state="failed",
                    exit_code=96,
                    error="preparation_lost",
                )
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE submissions SET lifecycle_state = 'terminal' WHERE run_id = ?",
                        (run_id,),
                    )
                return {
                    "run_id": run_id,
                    "state": "failed",
                    "accepted_at": submitted,
                    "exit_code": 96,
                    "done": True,
                }
            else:
                return {
                    "run_id": run_id,
                    "state": "accepted",
                    "accepted_at": submitted,
                    "exit_code": None,
                    "done": False,
                }
        if not _recorded_process_is_alive(run_dir):
            _write_worker_lost_terminal(run_dir)
            with self._connect() as connection:
                connection.execute(
                    "UPDATE submissions SET lifecycle_state = 'terminal' WHERE run_id = ?",
                    (run_id,),
                )
            manifest = _read_json(run_dir / "output_manifest.json")
            return {
                "run_id": run_id,
                "state": manifest["terminal_state"],
                "accepted_at": submitted,
                "exit_code": manifest["exit_code"],
                "done": True,
            }
        return {
            "run_id": run_id,
            "state": "running" if (run_dir / "running").is_file() else "accepted",
            "accepted_at": submitted,
            "exit_code": None,
            "done": False,
        }

    def tcad_cancel(self, *, run_id: str) -> dict[str, Any]:
        status = self.tcad_status(run_id=run_id)
        if status["done"]:
            return status
        run_dir = self._run_dir(run_id)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM submissions WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise ExecutionToolError("TCAD run does not exist")
            if row["lifecycle_state"] in {"preparing", "running"}:
                connection.execute(
                    "UPDATE submissions SET lifecycle_state = 'cancel_requested' WHERE run_id = ?",
                    (run_id,),
                )
            connection.execute("COMMIT")
        if run_dir.is_dir():
            (run_dir / "cancel_requested").touch(exist_ok=True)
        for name in ("pid", "launcher_pid"):
            try:
                pid = int((run_dir / name).read_text(encoding="ascii").strip())
                os.killpg(pid, signal.SIGTERM)
                break
            except (FileNotFoundError, ProcessLookupError, ValueError):
                continue
        return {**status, "state": "cancelling"}

    def tcad_collect(self, *, run_id: str) -> dict[str, Any]:
        status = self.tcad_status(run_id=run_id)
        if not status["done"]:
            raise ExecutionToolError("TCAD job is not terminal")
        run_dir = self._run_dir(run_id)
        manifest = _read_json(run_dir / "output_manifest.json")
        outputs = [
            _descriptor(
                name=item["name"],
                path=run_dir / "work" / item["relative_path"],
                media_type=item["media_type"],
            )
            for item in manifest["outputs"]
        ]
        outputs.append(
            _descriptor(
                name="tcad_log",
                path=run_dir / "worker.log",
                media_type="text/plain; charset=utf-8",
            )
        )
        outputs.append(
            _descriptor(
                name="tcad_manifest",
                path=run_dir / "output_manifest.json",
                media_type="application/json",
            )
        )
        return {"run_id": run_id, "outputs": outputs}

    def _read_input(self, descriptor: FileDescriptor) -> bytes:
        path = Path(descriptor.local_path).expanduser().absolute()
        if not any(_within(path, Path(root)) for root in self.policy.allowed_input_roots):
            raise ExecutionToolError("TCAD input is outside allowed roots")
        return _read_descriptor(descriptor)

    def _run_dir(self, run_id: str) -> Path:
        self._submission_row(run_id)
        return self.runs_root / run_id

    def _submission_row(self, run_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM submissions WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise ExecutionToolError("TCAD run does not exist")
        return row

    def _reconcile_active(self) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id FROM submissions
                WHERE lifecycle_state IN ('preparing', 'running', 'cancel_requested')
                """
            ).fetchall()
        for row in rows:
            self.tcad_status(run_id=row["run_id"])

    def _initialize(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o770)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                    job_sha256 TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    submitted_at TEXT NOT NULL,
                    lifecycle_state TEXT NOT NULL DEFAULT 'running'
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(submissions)").fetchall()
            }
            if "lifecycle_state" not in columns:
                connection.execute(
                    """
                    ALTER TABLE submissions
                    ADD COLUMN lifecycle_state TEXT NOT NULL DEFAULT 'running'
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection


class TCADExecutionRouter:
    def __init__(self, facade: TCADExecutionFacade) -> None:
        self.facade = facade
        self._tools = {tool.name: tool for tool in EXECUTION_TOOLS}

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in EXECUTION_TOOLS]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise ExecutionToolError(f"unknown TCAD tool: {name}") from error
        try:
            parsed = tool.input_model.model_validate(arguments or {}, strict=False)
        except ValidationError as error:
            raise ExecutionToolError(f"invalid arguments for {name}: {error}") from error
        values = {field: getattr(parsed, field) for field in type(parsed).model_fields}
        return getattr(self.facade, name)(**values)


def _extract_archive(raw: bytes, entries: tuple[ArchiveEntry, ...], destination: Path) -> None:
    expected = {item.relative_path: item for item in entries}
    destination.mkdir(mode=0o750)
    seen: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive.getmembers():
                name = _validate_relative_path(member.name)
                if name in seen or name not in expected or not member.isfile():
                    raise ExecutionToolError("TCAD archive contains an undeclared member")
                item = expected[name]
                source = archive.extractfile(member)
                content = source.read(item.size_bytes + 1) if source is not None else b""
                if len(content) != item.size_bytes or hashlib.sha256(content).hexdigest() != item.sha256:
                    raise ExecutionToolError("TCAD archive member differs from its manifest")
                target = destination.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_new(target, content, mode=0o440)
                seen.add(name)
    except (tarfile.TarError, OSError) as error:
        raise ExecutionToolError("TCAD archive extraction failed") from error
    if seen != set(expected):
        raise ExecutionToolError("TCAD archive is missing declared members")


def _read_descriptor(descriptor: FileDescriptor) -> bytes:
    path = Path(descriptor.local_path).absolute()
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ExecutionToolError("TCAD input must be a regular non-symlink file")
    content = path.read_bytes()
    if len(content) != descriptor.size_bytes or hashlib.sha256(content).hexdigest() != descriptor.sha256:
        raise ExecutionToolError("TCAD input differs from its descriptor")
    return content


def _descriptor(*, name: str, path: Path, media_type: str) -> dict[str, Any]:
    content = path.read_bytes()
    return FileDescriptor(
        name=name,
        local_path=str(path),
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type=media_type,
    ).model_dump(mode="json")


def _verified_executable(value: str) -> Path:
    # Verify the symlink target but retain the configured invocation path.
    # Multi-call launchers such as Synopsys GENERIC dispatch from argv[0].
    path = Path(value).expanduser().absolute()
    metadata = os.stat(path)
    if not stat.S_ISREG(metadata.st_mode):
        raise ExecutionToolError("TCAD executable must resolve to a regular file")
    if metadata.st_mode & 0o111 == 0:
        raise ExecutionToolError("TCAD executable is not executable")
    return path


def _process_identity(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        fields = raw.rpartition(") ")[2].split()
        if fields[0] == "Z":
            return None
        start_ticks = fields[19]
    except (FileNotFoundError, IndexError, OSError, UnicodeError):
        return None
    return f"{pid}:{start_ticks}"


def _recorded_process_is_alive(run_dir: Path) -> bool:
    try:
        pid = int((run_dir / "launcher_pid").read_text(encoding="ascii").strip())
        expected = (run_dir / "launcher_identity").read_text(encoding="ascii").strip()
    except (FileNotFoundError, ValueError, OSError):
        return False
    return _process_identity(pid) == expected


def _terminate_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _write_worker_lost_terminal(run_dir: Path) -> None:
    try:
        solver_pid = int((run_dir / "solver_pid").read_text(encoding="ascii").strip())
        _terminate_process_group(solver_pid)
    except (FileNotFoundError, ValueError, OSError):
        pass
    cancelled = (run_dir / "cancel_requested").is_file()
    _write_abandoned_terminal(
        run_dir,
        terminal_state="cancelled" if cancelled else "failed",
        exit_code=130 if cancelled else 98,
        error="cancelled" if cancelled else "worker_lost",
    )


def _write_abandoned_terminal(
    run_dir: Path,
    *,
    terminal_state: str,
    exit_code: int,
    error: str,
) -> None:
    log = run_dir / "worker.log"
    if not log.exists():
        _write_new(log, (error + "\n").encode("ascii"), mode=0o440)
    manifest = {
        "completed_at": _timestamp(),
        "error": error,
        "exit_code": exit_code,
        "outputs": [],
        "started_at": None,
        "terminal_state": terminal_state,
    }
    _write_new(
        run_dir / "output_manifest.json",
        _canonical(manifest),
        mode=0o440,
    )
    _write_new(run_dir / "status", f"{exit_code}\n".encode("ascii"), mode=0o440)
    (run_dir / "running").unlink(missing_ok=True)
    (run_dir / "done").touch(exist_ok=False)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.expanduser().absolute())
    except ValueError:
        return False
    return True


def _write_new(path: Path, content: bytes, *, mode: int) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, mode)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExecutionToolError("TCAD runtime state is invalid")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _elapsed_seconds(timestamp: str) -> float:
    recorded = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - recorded).total_seconds()


__all__ = [
    "ArchiveEntry",
    "EXECUTION_TOOLS",
    "ExecutionToolError",
    "ExpectedOutput",
    "FileDescriptor",
    "ResourceLimits",
    "TCADExecutionFacade",
    "TCADExecutionPolicy",
    "TCADExecutionRouter",
    "TCADJobSpec",
    "ToolProfile",
]
