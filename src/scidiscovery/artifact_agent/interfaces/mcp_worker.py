"""Scientific worker MCP with no identity or state-writing fields."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import resource
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..service.tasks import TaskInputError, TaskService
from ..web_fetch import fetch_web_evidence


class WorkerToolError(RuntimeError):
    pass


class WorkerToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadInput(WorkerToolInput):
    name: str = Field(min_length=1, max_length=256)
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=65536, ge=1, le=262144)


class NamedInput(WorkerToolInput):
    name: str = Field(min_length=1, max_length=256)


class PdfInput(NamedInput):
    first_page: int = Field(default=1, ge=1, le=100000)
    last_page: int | None = Field(default=None, ge=1, le=100000)
    max_chars: int = Field(default=131072, ge=1, le=524288)


class TableInput(NamedInput):
    start_row: int = Field(default=0, ge=0)
    max_rows: int = Field(default=200, ge=1, le=2000)
    delimiter: str | None = Field(default=None, min_length=1, max_length=1)


class ProfileInput(NamedInput):
    delimiter: str | None = Field(default=None, min_length=1, max_length=1)


class ValidateOutputInput(WorkerToolInput):
    content: Any


class AnalysisInput(WorkerToolInput):
    code: str = Field(min_length=1, max_length=65536)
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class WebEvidenceInput(WorkerToolInput):
    url: str = Field(min_length=1, max_length=4096)
    max_chars: int = Field(default=131072, ge=1, le=262144)


class FinalizeInput(WorkerToolInput):
    content: Any


@dataclass(frozen=True)
class WorkerTool:
    name: str
    description: str
    input_model: type[WorkerToolInput]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }


WORKER_TOOLS = (
    WorkerTool("worker_claim_task", "Open the assignment bound to this worker process.", WorkerToolInput),
    WorkerTool("worker_get_assignment", "Read the complete task-local assignment, output JSON Schema, and capabilities.", WorkerToolInput),
    WorkerTool("worker_materialize_assignment", "Materialize the complete assignment as identity-free local files with one fixed output path.", WorkerToolInput),
    WorkerTool("worker_list_inputs", "List task-local scientific source names.", WorkerToolInput),
    WorkerTool("worker_read_input", "Read a bounded UTF-8 slice of one text input.", ReadInput),
    WorkerTool("worker_stage_input", "Stage one immutable task input at a read-only local path.", NamedInput),
    WorkerTool("worker_extract_pdf_text", "Extract a bounded page range from one task PDF.", PdfInput),
    WorkerTool("worker_read_table", "Read bounded rows from a CSV, TSV, or JSON table input.", TableInput),
    WorkerTool("worker_profile_input", "Return a deterministic bounded structural profile without copying full input content.", ProfileInput),
    WorkerTool("worker_run_analysis", "Run bounded Python against staged task inputs in an isolated, offline, read-only-input sandbox.", AnalysisInput),
    WorkerTool("worker_fetch_web_evidence", "Fetch and freeze one public HTTPS source as task evidence.", WebEvidenceInput),
    WorkerTool("worker_validate_output", "Validate draft content against the exact assignment contract without completing the task.", ValidateOutputInput),
    WorkerTool("worker_validate_output_file", "Validate output/result.json from the materialized task workspace.", WorkerToolInput),
    WorkerTool("worker_heartbeat", "Renew the active task lease within its absolute runtime budget.", WorkerToolInput),
    WorkerTool("worker_finalize", "Submit one role result envelope for validation and completion.", FinalizeInput),
    WorkerTool("worker_finalize_file", "Submit output/result.json as one role result envelope.", WorkerToolInput),
)


class WorkerMCPRouter:
    def __init__(
        self,
        tasks: TaskService,
        *,
        worker_id: str,
        proxy_id: str | None = None,
    ) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        self.tasks = tasks
        self.worker_id = worker_id
        self.proxy_id = proxy_id or f"pxy_{uuid.uuid4().hex}"
        self._session_token: str | None = None
        self._completed = False
        self._tools = {tool.name: tool for tool in WORKER_TOOLS}

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in WORKER_TOOLS]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise WorkerToolError(f"unknown worker tool: {name}") from error
        try:
            parsed = tool.input_model.model_validate(arguments or {}, strict=False)
        except ValidationError as error:
            raise WorkerToolError(f"invalid arguments for {name}: {error}") from error
        if name == "worker_claim_task":
            if self._session_token is not None or self._completed:
                raise WorkerToolError("this worker process already owns an assignment")
            self._session_token = self.tasks.claim_next(
                worker_id=self.worker_id,
                proxy_id=self.proxy_id,
            )
            return {"state": "claimed"}
        if self._completed:
            raise WorkerToolError("this worker assignment is already completed")
        if self._session_token is None:
            raise WorkerToolError("worker_claim_task must be called first")
        session_token = self._session_token
        if name == "worker_get_assignment":
            assignment = self.tasks.assignment(
                session_token, worker_id=self.worker_id
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="assignment_read",
            )
            return assignment.model_dump(mode="json")
        if name == "worker_materialize_assignment":
            workspace = self.tasks.materialize_assignment(
                session_token, worker_id=self.worker_id
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="assignment_materialized",
            )
            return workspace
        if name == "worker_list_inputs":
            assignment = self.tasks.assignment(
                session_token, worker_id=self.worker_id
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="inputs_listed",
            )
            return {
                "inputs": [item.model_dump(mode="json") for item in assignment.inputs]
            }
        if name == "worker_read_input":
            input_name, media_type, content = self.tasks.read_input(
                session_token, worker_id=self.worker_id, name=parsed.name
            )
            base_type = media_type.split(";", 1)[0].strip().lower()
            if base_type.startswith("text/") or base_type in {
                "application/json",
                "application/xml",
            }:
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise WorkerToolError("text input is not valid UTF-8") from error
                end = min(len(text), parsed.offset + parsed.max_chars)
                if parsed.offset > len(text):
                    raise WorkerToolError("text input offset exceeds content length")
                self.tasks.record_activity(
                    session_token,
                    worker_id=self.worker_id,
                    activity="input_read",
                )
                return {
                    "name": input_name,
                    "media_type": media_type,
                    "content": text[parsed.offset:end],
                    "start": parsed.offset,
                    "end": end,
                    "truncated": end < len(text),
                }
            raise WorkerToolError(
                "binary input requires worker_stage_input or a format-specific reader"
            )
        if name == "worker_stage_input":
            local_path, staged_type, size = self.tasks.stage_input(
                session_token, worker_id=self.worker_id, name=parsed.name
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="input_staged",
            )
            return {
                "name": parsed.name,
                "media_type": staged_type,
                "size_bytes": size,
                "local_path": local_path,
                "access": "read_only",
            }
        if name == "worker_extract_pdf_text":
            local_path, media_type, _ = self.tasks.stage_input(
                session_token, worker_id=self.worker_id, name=parsed.name
            )
            if media_type.split(";", 1)[0].strip().lower() != "application/pdf":
                raise WorkerToolError("worker_extract_pdf_text requires application/pdf")
            if parsed.last_page is not None and parsed.last_page < parsed.first_page:
                raise WorkerToolError("last_page must not precede first_page")
            command = ["pdftotext", "-layout", "-f", str(parsed.first_page)]
            if parsed.last_page is not None:
                command.extend(("-l", str(parsed.last_page)))
            command.extend((local_path, "-"))
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    timeout=30,
                )
            except FileNotFoundError as error:
                raise WorkerToolError("pdftotext is not installed") from error
            except subprocess.TimeoutExpired as error:
                raise WorkerToolError("PDF text extraction timed out") from error
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace")[-2048:]
                raise WorkerToolError(f"PDF text extraction failed: {detail}")
            text = completed.stdout.decode("utf-8", errors="replace")
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="pdf_extracted",
            )
            return {
                "name": parsed.name,
                "media_type": "text/plain; charset=utf-8",
                "content": text[: parsed.max_chars],
                "first_page": parsed.first_page,
                "last_page": parsed.last_page,
                "truncated": len(text) > parsed.max_chars,
            }
        if name == "worker_read_table":
            _, media_type, content = self.tasks.read_input(
                session_token, worker_id=self.worker_id, name=parsed.name
            )
            columns, rows = _read_table(content, media_type, parsed.delimiter)
            end = min(len(rows), parsed.start_row + parsed.max_rows)
            if parsed.start_row > len(rows):
                raise WorkerToolError("table start_row exceeds row count")
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="table_read",
            )
            return {
                "name": parsed.name,
                "columns": columns,
                "rows": rows[parsed.start_row:end],
                "start_row": parsed.start_row,
                "next_row": end if end < len(rows) else None,
                "total_rows": len(rows),
            }
        if name == "worker_profile_input":
            _, media_type, content = self.tasks.read_input(
                session_token, worker_id=self.worker_id, name=parsed.name
            )
            profile = _profile_input(content, media_type, parsed.delimiter)
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="input_profiled",
            )
            return {"name": parsed.name, "media_type": media_type, **profile}
        if name == "worker_run_analysis":
            directory = self.tasks.analysis_directory(
                session_token, worker_id=self.worker_id
            )
            result = _run_analysis(
                directory=directory,
                code=parsed.code,
                timeout_seconds=parsed.timeout_seconds,
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="deterministic_analysis_completed",
            )
            return result
        if name == "worker_fetch_web_evidence":
            fetched = fetch_web_evidence(parsed.url, max_chars=parsed.max_chars)
            registered = self.tasks.register_web_evidence(
                session_token,
                worker_id=self.worker_id,
                original_url=fetched.original_url,
                final_url=fetched.final_url,
                accessed_at=fetched.accessed_at,
                http_status=fetched.http_status,
                media_type=fetched.media_type,
                body=fetched.body,
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="web_evidence_frozen",
            )
            return {
                "source_key": registered.source_key,
                "original_url": registered.original_url,
                "final_url": registered.final_url,
                "accessed_at": registered.accessed_at,
                "http_status": fetched.http_status,
                "media_type": registered.media_type,
                "content": fetched.text,
                "truncated": fetched.text_truncated,
            }
        if name == "worker_validate_output":
            valid, size, errors = self.tasks.validate_output(
                session_token,
                worker_id=self.worker_id,
                content=parsed.content,
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="output_validated" if valid else "output_rejected",
            )
            return {
                "valid": valid,
                "size_bytes": size,
                "errors": list(errors),
            }
        if name == "worker_validate_output_file":
            try:
                valid, size, errors = self.tasks.validate_output_file(
                    session_token,
                    worker_id=self.worker_id,
                )
            except TaskInputError as error:
                if not error.details:
                    raise WorkerToolError(str(error)) from error
                valid, size, errors = False, None, error.details
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="output_validated" if valid else "output_rejected",
            )
            return {
                "valid": valid,
                "size_bytes": size,
                "errors": list(errors),
            }
        if name == "worker_heartbeat":
            lease, absolute = self.tasks.heartbeat(
                session_token, worker_id=self.worker_id
            )
            return {
                "state": "claimed",
                "lease_deadline_at": lease,
                "absolute_deadline_at": absolute,
            }
        if name == "worker_finalize":
            try:
                self.tasks.finalize(
                    session_token,
                    worker_id=self.worker_id,
                    content=parsed.content,
                )
            except TaskInputError as error:
                details = error.details or (
                    {
                        "path": "$",
                        "message": str(error),
                        "type": "value_error",
                    },
                )
                self.tasks.record_activity(
                    session_token,
                    worker_id=self.worker_id,
                    activity="output_rejected",
                )
                return {"state": "rejected", "errors": list(details)}
            self._completed = True
            self._session_token = None
            return {"state": "completed"}
        if name == "worker_finalize_file":
            try:
                self.tasks.finalize_file(
                    session_token,
                    worker_id=self.worker_id,
                )
            except TaskInputError as error:
                details = error.details or (
                    {
                        "path": "$",
                        "message": str(error),
                        "type": "value_error",
                    },
                )
                self.tasks.record_activity(
                    session_token,
                    worker_id=self.worker_id,
                    activity="output_rejected",
                )
                return {"state": "rejected", "errors": list(details)}
            self._completed = True
            self._session_token = None
            return {"state": "completed"}
        raise AssertionError(f"unhandled worker tool: {name}")


def _read_table(
    content: bytes, media_type: str, delimiter: str | None
) -> tuple[list[str], list[list[Any]]]:
    base_type = media_type.split(";", 1)[0].strip().lower()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise WorkerToolError("table input is not valid UTF-8") from error
    if base_type == "application/json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise WorkerToolError("JSON table input is invalid") from error
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise WorkerToolError("JSON table must be an array of objects")
        columns = list(dict.fromkeys(key for item in value for key in item))
        return columns, [[item.get(key) for key in columns] for item in value]
    if base_type not in {"text/csv", "text/tab-separated-values", "text/plain"}:
        raise WorkerToolError("table reader supports CSV, TSV, and JSON only")
    chosen = delimiter or ("\t" if base_type == "text/tab-separated-values" else ",")
    reader = csv.reader(io.StringIO(text), delimiter=chosen)
    all_rows = list(reader)
    if not all_rows:
        return [], []
    return all_rows[0], all_rows[1:]


def _profile_input(
    content: bytes, media_type: str, delimiter: str | None
) -> dict[str, Any]:
    base_type = media_type.split(";", 1)[0].strip().lower()
    if base_type in {
        "text/csv",
        "text/tab-separated-values",
        "application/json",
    }:
        try:
            columns, rows = _read_table(content, media_type, delimiter)
        except WorkerToolError:
            if base_type != "application/json":
                raise
        else:
            summaries = []
            for index, column in enumerate(columns[:256]):
                values = [row[index] if index < len(row) else None for row in rows]
                missing = sum(value is None or str(value).strip() == "" for value in values)
                numeric = []
                non_finite = 0
                for value in values:
                    if value is None or str(value).strip() == "":
                        continue
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(number):
                        numeric.append(number)
                    else:
                        non_finite += 1
                summary: dict[str, Any] = {
                    "name": str(column),
                    "missing_count": missing,
                    "numeric_count": len(numeric),
                    "non_finite_count": non_finite,
                }
                if numeric:
                    summary.update({"minimum": min(numeric), "maximum": max(numeric)})
                summaries.append(summary)
            return {
                "profile_type": "table",
                "size_bytes": len(content),
                "row_count": len(rows),
                "column_count": len(columns),
                "columns": summaries,
                "columns_truncated": len(columns) > 256,
            }
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"profile_type": "binary", "size_bytes": len(content)}
    if base_type == "application/json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise WorkerToolError("JSON input is invalid") from error
        if isinstance(value, dict):
            keys = list(value)[:256]
            return {
                "profile_type": "json_object",
                "size_bytes": len(content),
                "key_count": len(value),
                "keys": keys,
                "keys_truncated": len(value) > len(keys),
            }
        if isinstance(value, list):
            return {
                "profile_type": "json_array",
                "size_bytes": len(content),
                "item_count": len(value),
            }
    return {
        "profile_type": "text",
        "size_bytes": len(content),
        "character_count": len(text),
        "line_count": len(text.splitlines()),
    }


def _run_analysis(
    *, directory: Any, code: str, timeout_seconds: int
) -> dict[str, Any]:
    python = sys.executable
    command = [
        "bwrap",
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--new-session",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/lib",
        "/lib",
    ]
    if os.environ.get("SCIDISCOVERY_ANALYSIS_NETWORK_ISOLATED") != "1":
        command.insert(6, "--unshare-net")
    if os.path.isdir("/lib64"):
        command.extend(("--ro-bind", "/lib64", "/lib64"))
    prefix = os.path.abspath(sys.prefix)
    if not prefix.startswith("/usr"):
        command.extend(("--ro-bind", prefix, prefix))
    command.extend(
        (
            "--ro-bind",
            str(directory),
            "/inputs",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--chdir",
            "/tmp",
            "--setenv",
            "HOME",
            "/tmp",
            python,
            "-I",
            "-c",
            code,
        )
    )
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout_seconds,
                check=False,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                preexec_fn=lambda: _set_analysis_limits(timeout_seconds),
            )
            stdout.seek(0)
            stderr.seek(0)
            output = stdout.read(1024 * 1024 + 1)
            errors = stderr.read(256 * 1024 + 1)
    except FileNotFoundError as error:
        raise WorkerToolError("bubblewrap is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise WorkerToolError("analysis sandbox timed out") from error
    if len(output) > 1024 * 1024 or len(errors) > 256 * 1024:
        raise WorkerToolError("analysis output exceeded its byte limit")
    return {
        "exit_code": completed.returncode,
        "stdout": output.decode("utf-8", errors="replace"),
        "stderr": errors.decode("utf-8", errors="replace"),
        "input_directory": "/inputs",
    }


def _set_analysis_limits(timeout_seconds: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds + 1))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


__all__ = ["WORKER_TOOLS", "WorkerMCPRouter", "WorkerTool", "WorkerToolError"]
