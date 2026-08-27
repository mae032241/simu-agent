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
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..schema.common import canonical_json
from ..schema.curve_analysis import analyze_curve_error
from ..schema.curve_score import CurveBundle, CurveConsistencyReport
from ..schema.experiment import ExperimentPortfolio
from ..schema.task import TaskOutputBundle, TaskOutputBundleItem
from ..service.tasks import TaskInputError, TaskService
from ..service.tcad_debug import TCADDebugError, TCADDebugService
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


class CurveAnalyzeInput(WorkerToolInput):
    comparison_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    )


class WebEvidenceInput(WorkerToolInput):
    url: str = Field(min_length=1, max_length=4096)
    max_chars: int = Field(default=131072, ge=1, le=262144)


class FinalizeInput(WorkerToolInput):
    content: Any


class ResultUploadChunk(WorkerToolInput):
    content: str = Field(max_length=65536)


class WorkerFilePathInput(WorkerToolInput):
    relative_path: str = Field(min_length=1, max_length=1024)


class WorkerFileWriteBeginInput(WorkerFilePathInput):
    expected_bytes: int | None = Field(default=None, ge=0, le=64 * 1024 * 1024)
    operation: Literal["create", "patch"] = "create"


class WorkerFileWriteChunkInput(WorkerToolInput):
    content: str = Field(max_length=90000)
    encoding: Literal["utf8", "base64"] = "utf8"


class WorkerFilePatchInput(WorkerFilePathInput):
    patch: str = Field(min_length=1, max_length=65536)


class WorkerJsonPatchOperation(WorkerToolInput):
    op: Literal["test", "add", "replace", "remove"]
    path: str = Field(min_length=1, max_length=1024)
    value: Any | None = None

    @model_validator(mode="after")
    def _value_matches_operation(self) -> WorkerJsonPatchOperation:
        has_value = "value" in self.model_fields_set
        if self.op == "remove" and has_value:
            raise ValueError("remove operation must not declare value")
        if self.op != "remove" and not has_value:
            raise ValueError("test, add, and replace operations require value")
        return self


class WorkerFileJsonPatchInput(WorkerFilePathInput):
    operations: tuple[WorkerJsonPatchOperation, ...] = Field(
        min_length=1, max_length=128
    )
    expected_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def _patch_has_compare_and_swap_guard(self) -> WorkerFileJsonPatchInput:
        if self.expected_digest is None and not any(
            item.op == "test" for item in self.operations
        ):
            raise ValueError(
                "JSON patch requires expected_digest or at least one test operation"
            )
        return self


class WorkerFileMoveInput(WorkerToolInput):
    source_relative_path: str = Field(min_length=1, max_length=1024)
    destination_relative_path: str = Field(min_length=1, max_length=1024)


class TCADDebugRunInput(WorkerToolInput):
    run_name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$",
    )
    mode: Literal["preflight", "smoke", "initialization"]


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
    WorkerTool("worker_materialize_assignment", "Materialize the assignment and return exact local paths for native read-only inspection.", WorkerToolInput),
    WorkerTool("worker_extract_pdf_text", "Extract a bounded PDF page range to an exact local read-only text path.", PdfInput),
    WorkerTool("worker_run_analysis", "Run bounded Python against staged task inputs with optional bounded collection output access in an isolated offline sandbox.", AnalysisInput),
    WorkerTool("worker_curve_analyze", "Deterministically localize failed residual comparisons from the exact plan, metric report, and curve bundle; write bounded PNG plots and return their current local paths.", CurveAnalyzeInput),
    WorkerTool("worker_fetch_web_evidence", "Fetch and freeze one public HTTPS source as task evidence.", WebEvidenceInput),
    WorkerTool("worker_file_write_begin", "Begin a bounded new-file creation or chunked Codex patch. Omit expected_bytes for server-counted UTF-8; do not use TextEncoder. Existing files cannot be replaced wholesale.", WorkerFileWriteBeginInput),
    WorkerTool("worker_file_write_chunk", "Append one bounded UTF-8 or base64 chunk. Pass source as ordinary quoted strings or arrays of lines, never a JavaScript template literal containing Tcl ${...}.", WorkerFileWriteChunkInput),
    WorkerTool("worker_file_write_commit", "Atomically publish the complete active create-or-patch operation.", WorkerToolInput),
    WorkerTool("worker_file_apply_patch", "Apply one native Codex `*** Begin Patch`/`*** Update File` patch without hunk line counts, or one legacy standard unified diff, to an existing task-relative text file; reject stale or ambiguous context atomically, then require a fresh read before another patch.", WorkerFilePatchInput),
    WorkerTool("worker_file_json_patch", "Atomically apply bounded JSON Pointer test/add/replace/remove operations to one existing task-relative JSON file. Guard the update with the current content digest or a test operation; no textual context matching is used.", WorkerFileJsonPatchInput),
    WorkerTool("worker_file_delete", "Delete one optional task-relative deck or collection file.", WorkerFilePathInput),
    WorkerTool("worker_file_move", "Move one optional task-relative deck or collection file without rewriting its content.", WorkerFileMoveInput),
    WorkerTool("worker_checkpoint_output", "Freeze the current bounded output workspace as task-private provisional retry context.", WorkerToolInput),
    WorkerTool("worker_validate_output_file", "Validate output/result.json and any configured output/bundle.json collection files.", WorkerToolInput),
    WorkerTool("worker_heartbeat", "Renew the active task lease within its absolute runtime budget.", WorkerToolInput),
    WorkerTool(
        "worker_tcad_debug_run",
        "Submit or poll one named control-selected preflight, smoke, or SProcess "
        "initialization run for this TCAD author attempt. Initialization uses a "
        "control-derived one-step baseline copy, never the full study. Collected "
        "failures include one bounded structured source_diagnostic when the solver "
        "log provides a locator; full-study development execution is unavailable.",
        TCADDebugRunInput,
    ),
    WorkerTool("worker_finalize_file", "Finalize only the immutable bytes sealed by successful file validation.", WorkerToolInput),
)


_LEGACY_WORKER_TOOLS = (
    WorkerTool("worker_get_assignment", "Compatibility-only inline assignment read.", WorkerToolInput),
    WorkerTool("worker_list_inputs", "Compatibility-only input listing.", WorkerToolInput),
    WorkerTool("worker_read_input", "Compatibility-only bounded text input read.", ReadInput),
    WorkerTool("worker_stage_input", "Compatibility-only immutable input staging.", NamedInput),
    WorkerTool("worker_read_table", "Compatibility-only bounded table read.", TableInput),
    WorkerTool("worker_profile_input", "Compatibility-only input profile read.", ProfileInput),
    WorkerTool("worker_begin_result_upload", "Compatibility-only bounded primary-result upload start.", WorkerToolInput),
    WorkerTool("worker_append_result_upload", "Compatibility-only bounded primary-result upload chunk.", ResultUploadChunk),
    WorkerTool("worker_commit_result_upload", "Compatibility-only primary-result upload commit.", WorkerToolInput),
    WorkerTool("worker_validate_output", "Compatibility-only inline draft validation.", ValidateOutputInput),
    WorkerTool("worker_write_result", "Compatibility-only inline primary-result write.", FinalizeInput),
    WorkerTool("worker_finalize", "Compatibility-only inline finalization.", FinalizeInput),
)


class WorkerMCPRouter:
    def __init__(
        self,
        tasks: TaskService,
        *,
        worker_id: str,
        proxy_id: str | None = None,
        tcad_debug: TCADDebugService | None = None,
    ) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        self.tasks = tasks
        self.worker_id = worker_id
        self.proxy_id = proxy_id or f"pxy_{uuid.uuid4().hex}"
        self.tcad_debug = tcad_debug
        self._session_token: str | None = None
        self._completed = False
        self._curve_analysis_request: bytes | None = None
        self._curve_analysis_response: dict[str, Any] | None = None
        self._operation_lock = threading.RLock()
        self._tools = {
            tool.name: tool for tool in (*WORKER_TOOLS, *_LEGACY_WORKER_TOOLS)
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in WORKER_TOOLS]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        if name == "worker_heartbeat":
            return self._call_tool(name, arguments)
        with self._operation_lock:
            return self._call_tool(name, arguments)

    def _call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise WorkerToolError(f"unknown worker tool: {name}") from error
        try:
            parsed = tool.input_model.model_validate(arguments or {}, strict=False)
        except ValidationError as error:
            if (
                name in {"worker_run_analysis", "worker_curve_analyze"}
                and self._session_token is not None
                and not self._completed
            ):
                self.tasks.record_activity(
                    self._session_token,
                    worker_id=self.worker_id,
                    activity="deterministic_analysis_rejected",
                )
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
            try:
                extracted = self.tasks.extract_pdf_text(
                    session_token,
                    worker_id=self.worker_id,
                    name=parsed.name,
                    first_page=parsed.first_page,
                    last_page=parsed.last_page,
                    max_chars=parsed.max_chars,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="pdf_cache_hit" if extracted.cache_hit else "pdf_extracted",
            )
            return {
                "name": parsed.name,
                "media_type": "text/plain; charset=utf-8",
                "local_path": extracted.local_path,
                "size_bytes": extracted.size_bytes,
                "access": "read_only",
                "first_page": extracted.first_page,
                "last_page": extracted.last_page,
                "available_page_count": extracted.available_page_count,
                "truncated": extracted.truncated,
                "cache": "hit" if extracted.cache_hit else "created",
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
            output_directory = self.tasks.analysis_output_directory(
                session_token, worker_id=self.worker_id
            )
            result = _run_analysis(
                directory=directory,
                output_directory=output_directory,
                code=parsed.code,
                timeout_seconds=parsed.timeout_seconds,
            )
            try:
                self.tasks.validate_analysis_outputs(
                    session_token, worker_id=self.worker_id
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="deterministic_analysis_completed",
            )
            return result
        if name == "worker_curve_analyze":
            request = canonical_json(parsed.model_dump(mode="json"))
            if self._curve_analysis_request is not None:
                if request != self._curve_analysis_request:
                    raise WorkerToolError(
                        "curve analysis already ran with a different request"
                    )
                assert self._curve_analysis_response is not None
                return self._curve_analysis_response
            assignment = self.tasks.assignment(
                session_token, worker_id=self.worker_id
            )
            if assignment.role != "diagnostician":
                raise WorkerToolError(
                    "worker_curve_analyze is available only to diagnostician"
                )
            if not any(
                item.name == "curve_analysis_plots"
                for item in assignment.output.collections
            ):
                raise WorkerToolError(
                    "curve analysis requires output profile curve-error-analysis"
                )
            try:
                _, _, plan_raw = self.tasks.read_input(
                    session_token,
                    worker_id=self.worker_id,
                    name="experiment_plan",
                )
                _, _, metric_raw = self.tasks.read_input(
                    session_token,
                    worker_id=self.worker_id,
                    name="metric_report",
                )
                _, _, bundle_raw = self.tasks.read_input(
                    session_token,
                    worker_id=self.worker_id,
                    name="curve_bundle",
                )
                artifacts = analyze_curve_error(
                    ExperimentPortfolio.model_validate_json(plan_raw, strict=True),
                    CurveConsistencyReport.model_validate_json(
                        metric_raw, strict=True
                    ),
                    CurveBundle.model_validate_json(bundle_raw, strict=True),
                    comparison_key=parsed.comparison_key,
                )
                output_directory = self.tasks.analysis_output_directory(
                    session_token, worker_id=self.worker_id
                )
                if output_directory is None:
                    raise TaskInputError(
                        "curve analysis output collection is unavailable"
                    )
                local_paths = _write_curve_analysis_outputs(
                    output_directory, artifacts.plots
                )
                self.tasks.validate_analysis_outputs(
                    session_token, worker_id=self.worker_id
                )
            except (TaskInputError, ValidationError, ValueError) as error:
                self.tasks.record_activity(
                    session_token,
                    worker_id=self.worker_id,
                    activity="deterministic_analysis_rejected",
                )
                raise WorkerToolError(str(error)) from error
            response = {
                "analysis": artifacts.report.model_dump(mode="json"),
                "plots": [
                    {
                        "comparison_key": item.comparison_key,
                        "operator_key": item.operator_key,
                        "plot_item": item.plot_item,
                        "plot_relative_path": (
                            "output/collections/curve_analysis_plots/"
                            f"{item.plot_item}"
                        ),
                        "plot_local_path": local_paths[item.plot_item],
                    }
                    for item in artifacts.report.analyses
                ],
            }
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="deterministic_analysis_completed",
            )
            self._curve_analysis_request = request
            self._curve_analysis_response = response
            return response
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
                text=fetched.text,
                text_truncated=fetched.text_truncated,
            )
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="web_evidence_frozen",
            )
            materialized = self.tasks.materialize_web_evidence(
                session_token,
                worker_id=self.worker_id,
                original_url=registered.original_url,
                source_key=registered.source_key,
            )
            return {
                "source_key": registered.source_key,
                "original_url": registered.original_url,
                "final_url": registered.final_url,
                "accessed_at": registered.accessed_at,
                "http_status": fetched.http_status,
                "media_type": registered.media_type,
                "local_path": materialized.local_path,
                "size_bytes": materialized.size_bytes,
                "text_local_path": materialized.text_local_path,
                "text_size_bytes": materialized.text_size_bytes,
                "text_truncated": materialized.text_truncated,
                "access": "read_only",
            }
        if name == "worker_begin_result_upload":
            self.tasks.begin_result_upload(
                session_token, worker_id=self.worker_id
            )
            return {"state": "uploading", "max_chunk_bytes": 65536}
        if name == "worker_append_result_upload":
            size = self.tasks.append_result_upload(
                session_token,
                worker_id=self.worker_id,
                content=parsed.content,
            )
            return {"state": "uploading", "size_bytes": size}
        if name == "worker_commit_result_upload":
            size = self.tasks.commit_result_upload(
                session_token, worker_id=self.worker_id
            )
            return {
                "state": "committed",
                "size_bytes": size,
                "relative_path": "output/result.json",
            }
        if name == "worker_file_write_begin":
            try:
                max_bytes = self.tasks.begin_worker_file_write(
                    session_token,
                    worker_id=self.worker_id,
                    relative_path=parsed.relative_path,
                    expected_bytes=parsed.expected_bytes,
                    operation=parsed.operation,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {
                "state": "uploading",
                "relative_path": parsed.relative_path,
                "expected_bytes": parsed.expected_bytes,
                "operation": parsed.operation,
                "max_file_bytes": max_bytes,
                "max_chunk_bytes": 65536,
            }
        if name == "worker_file_write_chunk":
            try:
                size = self.tasks.append_worker_file_write(
                    session_token,
                    worker_id=self.worker_id,
                    content=parsed.content,
                    encoding=parsed.encoding,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {"state": "uploading", "size_bytes": size}
        if name == "worker_file_write_commit":
            try:
                relative_path, size = self.tasks.commit_worker_file_write(
                    session_token, worker_id=self.worker_id
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {
                "state": "committed",
                "relative_path": relative_path,
                "size_bytes": size,
            }
        if name == "worker_file_apply_patch":
            try:
                size = self.tasks.apply_worker_file_patch(
                    session_token,
                    worker_id=self.worker_id,
                    relative_path=parsed.relative_path,
                    patch=parsed.patch,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {
                "state": "patched",
                "relative_path": parsed.relative_path,
                "size_bytes": size,
            }
        if name == "worker_file_json_patch":
            try:
                size, digest = self.tasks.apply_worker_file_json_patch(
                    session_token,
                    worker_id=self.worker_id,
                    relative_path=parsed.relative_path,
                    operations=tuple(
                        item.model_dump(mode="python", exclude_unset=True)
                        for item in parsed.operations
                    ),
                    expected_digest=parsed.expected_digest,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {
                "state": "patched",
                "relative_path": parsed.relative_path,
                "size_bytes": size,
                "content_digest": digest,
            }
        if name == "worker_file_delete":
            try:
                self.tasks.delete_worker_file(
                    session_token,
                    worker_id=self.worker_id,
                    relative_path=parsed.relative_path,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {"state": "deleted", "relative_path": parsed.relative_path}
        if name == "worker_file_move":
            try:
                size = self.tasks.move_worker_file(
                    session_token,
                    worker_id=self.worker_id,
                    source_relative_path=parsed.source_relative_path,
                    destination_relative_path=parsed.destination_relative_path,
                )
            except TaskInputError as error:
                raise WorkerToolError(str(error)) from error
            return {
                "state": "moved",
                "source_relative_path": parsed.source_relative_path,
                "destination_relative_path": parsed.destination_relative_path,
                "size_bytes": size,
            }
        if name == "worker_checkpoint_output":
            snapshot_name = self.tasks.checkpoint_output(
                session_token, worker_id=self.worker_id
            )
            return {"state": "checkpointed", "name": snapshot_name}
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
        if name == "worker_write_result":
            try:
                size = self.tasks.write_result_file(
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
                return {"written": False, "size_bytes": None, "errors": list(details)}
            self.tasks.record_activity(
                session_token,
                worker_id=self.worker_id,
                activity="output_written",
            )
            return {
                "written": True,
                "size_bytes": size,
                "relative_path": "output/result.json",
                "errors": [],
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
        if name == "worker_tcad_debug_run":
            if self.tcad_debug is None:
                raise WorkerToolError("TCAD development debug is not configured")
            try:
                return self.tcad_debug.run(
                    session_token,
                    worker_id=self.worker_id,
                    run_name=parsed.run_name,
                    mode=parsed.mode,
                )
            except TCADDebugError as error:
                raise WorkerToolError(str(error)) from error
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
                return {"state": "rejected", "errors": list(details)}
            self._completed = True
            self._session_token = None
            return {"state": "completed"}
        raise AssertionError(f"unhandled worker tool: {name}")


def _write_curve_analysis_outputs(
    output_directory: Path,
    plots: tuple[tuple[str, bytes], ...],
) -> dict[str, str]:
    """Atomically write one idempotent, tool-owned curve plot collection."""

    collection = output_directory / "collections" / "curve_analysis_plots"
    if collection.exists() and (collection.is_symlink() or not collection.is_dir()):
        raise TaskInputError("curve analysis plot collection must be a real directory")
    collection.mkdir(parents=True, mode=0o700, exist_ok=True)
    expected = {name: content for name, content in plots}
    if len(expected) != len(plots):
        raise TaskInputError("curve analysis plot item names must be unique")
    if not 1 <= len(expected) <= 8:
        raise TaskInputError("curve analysis must produce between one and eight plots")
    for name, content in expected.items():
        if not name.endswith(".png") or len(name) > 256:
            raise TaskInputError("curve analysis produced an invalid plot item name")
        if len(content) > 1024 * 1024 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise TaskInputError("curve analysis produced an invalid bounded PNG")
    existing = {
        path.name: path
        for path in collection.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    if set(existing) - set(expected):
        raise TaskInputError("curve plot collection contains undeclared existing files")
    for name, content in expected.items():
        destination = collection / name
        if destination.exists():
            if destination.is_symlink() or destination.read_bytes() != content:
                raise TaskInputError("existing curve analysis plot differs")
            continue
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{name}.", dir=collection
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    bundle = TaskOutputBundle(
        items=tuple(
            TaskOutputBundleItem(
                collection="curve_analysis_plots",
                item=name,
                media_type="image/png",
                relative_path=f"collections/curve_analysis_plots/{name}",
            )
            for name in sorted(expected)
        )
    )
    bundle_content = canonical_json(bundle)
    bundle_path = output_directory / "bundle.json"
    if bundle_path.exists():
        if bundle_path.is_symlink() or bundle_path.read_bytes() != bundle_content:
            raise TaskInputError("existing curve analysis bundle differs")
    else:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".bundle.json.", dir=output_directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(bundle_content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, bundle_path)
        finally:
            temporary.unlink(missing_ok=True)
    return {name: str(collection / name) for name in sorted(expected)}


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
    *,
    directory: Any,
    output_directory: Any | None = None,
    code: str,
    timeout_seconds: int,
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
    if output_directory is not None:
        command.extend(("--bind", str(output_directory), "/outputs"))
        evidence_script = _scientific_paper_evidence_script()
        renderer_script = _scientific_paper_evidence_renderer_script()
        validator_script = _scientific_paper_evidence_validator_script()
        validator_core = (
            Path(__file__).resolve().parents[1] / "figure_evidence_validation.py"
        )
        if evidence_script is not None or renderer_script is not None or (
            validator_script is not None and validator_core.is_file()
        ):
            command.extend(("--dir", "/tools"))
        if evidence_script is not None:
            command.extend(
                (
                    "--ro-bind",
                    str(evidence_script),
                    "/tools/digitize_plot.py",
                )
            )
        if renderer_script is not None:
            command.extend(
                (
                    "--ro-bind",
                    str(renderer_script),
                    "/tools/render_curve_support.py",
                )
            )
        if validator_script is not None and validator_core.is_file():
            command.extend(
                (
                    "--ro-bind",
                    str(validator_script),
                    "/tools/validate_evidence_bundle.py",
                    "--ro-bind",
                    str(validator_core),
                    "/tools/figure_evidence_validation.py",
                )
            )
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
    result = {
        "exit_code": completed.returncode,
        "stdout": output.decode("utf-8", errors="replace"),
        "stderr": errors.decode("utf-8", errors="replace"),
        "input_directory": "/inputs",
    }
    if output_directory is not None:
        result["output_directory"] = "/outputs"
        tool_paths = {}
        if evidence_script is not None:
            tool_paths["scientific_paper_evidence"] = "/tools/digitize_plot.py"
        if renderer_script is not None:
            tool_paths["scientific_paper_evidence_support_renderer"] = (
                "/tools/render_curve_support.py"
            )
        if validator_script is not None and validator_core.is_file():
            tool_paths["scientific_paper_evidence_validator"] = (
                "/tools/validate_evidence_bundle.py"
            )
        if tool_paths:
            result["tool_paths"] = tool_paths
    return result


def _scientific_paper_evidence_script() -> Path | None:
    """Locate the installed deterministic plot digitizer for sandbox mounting."""

    configured = os.environ.get("SCIDISCOVERY_PAPER_EVIDENCE_SCRIPT")
    installed_root = Path(__file__).resolve().parents[3]
    candidates = (
        Path(configured) if configured else None,
        installed_root
        / "share/scidiscovery/skills/scientific-paper-evidence/scripts/digitize_plot.py",
        Path(sys.prefix)
        / "share/scidiscovery/skills/scientific-paper-evidence/scripts/digitize_plot.py",
        Path(__file__).resolve().parents[4]
        / "skills/scientific-paper-evidence/scripts/digitize_plot.py",
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file() and not candidate.is_symlink():
            return candidate.resolve()
    return None


def _scientific_paper_evidence_validator_script() -> Path | None:
    """Locate the installed evidence bundle validator for sandbox mounting."""

    configured = os.environ.get("SCIDISCOVERY_PAPER_EVIDENCE_VALIDATOR_SCRIPT")
    installed_root = Path(__file__).resolve().parents[3]
    candidates = (
        Path(configured) if configured else None,
        installed_root
        / "share/scidiscovery/skills/scientific-paper-evidence/scripts/validate_evidence_bundle.py",
        Path(sys.prefix)
        / "share/scidiscovery/skills/scientific-paper-evidence/scripts/validate_evidence_bundle.py",
        Path(__file__).resolve().parents[4]
        / "skills/scientific-paper-evidence/scripts/validate_evidence_bundle.py",
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file() and not candidate.is_symlink():
            return candidate.resolve()
    return None


def _scientific_paper_evidence_renderer_script() -> Path | None:
    """Locate the installed observed-support renderer for sandbox mounting."""

    configured = os.environ.get("SCIDISCOVERY_PAPER_EVIDENCE_RENDERER_SCRIPT")
    installed_root = Path(__file__).resolve().parents[3]
    candidates = (
        Path(configured) if configured else None,
        installed_root
        / "share/scidiscovery/skills/scientific-paper-evidence/scripts/render_curve_support.py",
        Path(sys.prefix)
        / "share/scidiscovery/skills/scientific-paper-evidence/scripts/render_curve_support.py",
        Path(__file__).resolve().parents[4]
        / "skills/scientific-paper-evidence/scripts/render_curve_support.py",
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file() and not candidate.is_symlink():
            return candidate.resolve()
    return None


def _set_analysis_limits(timeout_seconds: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds + 1))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


__all__ = ["WORKER_TOOLS", "WorkerMCPRouter", "WorkerTool", "WorkerToolError"]
