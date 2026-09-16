"""Thin trusted-local orchestration of the existing bounded TCAD debug adapter."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import time
from dataclasses import asdict
from pathlib import Path

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.role_result import parse_role_result
from scidiscovery.artifact_agent.service.local_workspace import (
    WorkspaceError,
    write_control_workspace_file,
)
from scidiscovery.artifact_agent.service.run_outputs import (
    RunCheckerError,
    RunOutputError,
)

from .debug_contract import TCADDebugError, TCADDebugSource, TCADDevelopmentDebugAdapter
from .debug_adapter import _development_limits
from .project_packager import DeckProjectDraft, project_debug_sha256


_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MODES = frozenset({"preflight", "smoke", "initialization"})
_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
_STATES = frozenset({"accepted", "running", "cancelling", *_TERMINAL})
_MAX_RUNS = 6
_TOTAL_WALL_SECONDS = 360
_MAX_RESPONSE_BYTES = 32 * 1024


def debug_tool_description() -> str:
    modes = ", ".join(f"{mode} {_development_limits(mode)[0]}s" for mode in sorted(_MODES))
    return (
        "Submit or poll one bounded TCAD development diagnostic; never scientific evidence. "
        f"Budget: {_TOTAL_WALL_SECONDS}s reserved wall time and {_MAX_RUNS} created run names. "
        f"Mode caps: {modes}. Each submitted job reserves its capped wall limit once, "
        "further clamped by project limits, remaining debug budget and Run time; "
        "solver failure does not refund it. Repeat the same name/mode to poll without "
        "new reservation; use a new name after source corrections, which do not reset "
        "the budget. Responses report current budget and per-job reservation. "
        "On updated runners, summary progress includes observed job elapsed_seconds. "
        "Read details_path for redacted log_tails and manifest timing; "
        "log_relative_path locates the complete bounded log. These are observations, "
        "not an ETA or proof of physical initialization. Older runners may omit progress."
    )


def debug_response(context: OperationToolContext, run_name: str, response: dict) -> dict:
    runs = context.state.get("runs", {})
    used = context.state.get("reserved_wall_seconds", 0)
    remaining = max(0, _TOTAL_WALL_SECONDS - used)
    result = {**response, "budget": {
        "total_wall_seconds": _TOTAL_WALL_SECONDS,
        "reserved_wall_seconds": used,
        "remaining_wall_seconds": remaining,
        "max_runs": _MAX_RUNS,
        "created_runs": len(runs),
        "remaining_runs": max(0, _MAX_RUNS - len(runs)),
        "run_remaining_seconds": context.remaining_seconds,
        "effective_wall_seconds": max(0, min(remaining, context.remaining_seconds)),
    }}
    record = runs.get(run_name)
    if record is not None:
        result["reserved_wall_seconds_for_run"] = record["reserved_wall_seconds"]
    if len(canonical_json(result)) > _MAX_RESPONSE_BYTES:
        raise TCADDebugError("TCAD debug diagnostic response exceeds its bound")
    return result


def debug_summary(context, run_name, response):
    """Keep the complete engineering snapshot in this Run, not in every poll."""
    full = debug_response(context, run_name, response)
    path = write_control_workspace_file(context.workspace,
        Path(f"deck/reports/response-{run_name}.json"), canonical_json(full),
        replace=True, mode=0o400, create_parents=True)
    result = {key: full[key] for key in ("run_name", "mode", "state", "phase", "development_only",
        "scientific_claim_admissible", "diagnostic_layer", "summary", "exit_code", "diagnostics",
        "source_diagnostic", "log_relative_path", "budget", "reserved_wall_seconds_for_run") if key in full}
    if isinstance(full.get("progress"), dict):
        result["progress"] = {key: full["progress"][key] for key in
            ("elapsed_seconds", "observed_at", "started_at", "completed_at") if key in full["progress"]}
    result.update(details_path=str(path), output_count=len(full.get("outputs", [])))
    return result


class LocalTCADDebugService:
    """Keep only process-local diagnostic bindings; Run owns scientific state."""

    def __init__(self, *, adapter: TCADDevelopmentDebugAdapter, exchange_root: Path | str,
                 runtime_context=None) -> None:
        self.adapter = adapter
        self.runtime_context = runtime_context
        self.exchange_root = Path(exchange_root).expanduser().absolute()
        self.exchange_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.exchange_root.is_symlink() or not self.exchange_root.is_dir():
            raise ValueError("local TCAD debug exchange must be a real directory")

    def run(
        self, context: OperationToolContext, *, run_name: str, mode: str
    ) -> dict[str, object]:
        call_started = time.monotonic()
        if _RUN_NAME.fullmatch(run_name) is None or mode not in _MODES:
            raise TCADDebugError("TCAD development debug request is invalid")
        runs = context.state.setdefault("runs", {})
        if not isinstance(runs, dict):
            raise TCADDebugError("local TCAD debug state is invalid")
        record = runs.get(run_name)
        if record is None:
            if len(runs) >= _MAX_RUNS:
                raise TCADDebugError("TCAD development debug run limit is exhausted")
            record = self._start(context, run_name, mode)
            runs[run_name] = record
        if not isinstance(record, dict) or record.get("mode") != mode:
            raise TCADDebugError("TCAD debug run_name is bound to another mode")
        if isinstance(record.get("response"), dict):
            return dict(record["response"])
        state = _state(str(record["state"]))
        if state not in _TERMINAL:
            try:
                reader = getattr(self.adapter, "status_details", None)
                details = (reader(str(record["external_run_id"])) if callable(reader)
                           else {"state": self.adapter.status(str(record["external_run_id"]))})
                state = _state(str(details["state"]))
            except Exception as error:
                raise RuntimeError("TCAD debug status is unavailable") from error
            record["state"] = state
            context.record_activity("tcad_debug_polled")
        if state not in _TERMINAL:
            response = _pending(run_name, mode, state)
            if isinstance(details.get("progress"), dict):
                response["progress"] = details["progress"]
            return response
        try:
            from scidiscovery.artifact_agent.service.execution_collection import CollectionContext
            remaining = context.remaining_seconds - (time.monotonic() - call_started)
            budget = CollectionContext.for_seconds(remaining)
            budget.remaining_seconds()
            collect = getattr(self.adapter, "collect_with_budget", None)
            if self.runtime_context is not None:
                from .debug_collection import collect as collect_in_process
                collected = collect_in_process(self.runtime_context, str(record["external_run_id"]), context=budget)
            elif callable(collect):
                collected = collect(str(record["external_run_id"]), context=budget)
            else:
                raise RuntimeError("legacy debug collection requires its configured runtime factory")
            budget.remaining_seconds()
            response = self._finish(context, run_name, mode, record, collected, budget=budget)
        except TCADDebugError:
            raise
        except Exception as error:
            raise RuntimeError("TCAD debug collection is unavailable") from error
        record["state"] = "collected"
        record["response"] = response
        context.record_activity("tcad_debug_collected")
        return response

    def _start(
        self, context: OperationToolContext, run_name: str, mode: str
    ) -> dict[str, object]:
        used = context.state.get("reserved_wall_seconds", 0)
        if type(used) is not int or used < 0:
            raise TCADDebugError("local TCAD debug budget is invalid")
        remaining = min(context.remaining_seconds, _TOTAL_WALL_SECONDS - used)
        if remaining < 1:
            raise TCADDebugError("TCAD development debug budget is exhausted")
        project, source_sha, sources = _candidate(context)
        declarations_path = context.workspace / "deck/declarations.json"
        declarations_sha = (
            canonical_sha256(json.loads(declarations_path.read_bytes()))
            if declarations_path.is_file() else None
        )
        exchange = self.exchange_root / uuid.uuid4().hex / run_name
        exchange.mkdir(parents=True, mode=0o700)
        try:
            prepared = self.adapter.prepare(
                project=project,
                capability=context.read_input("execution_capability"),
                sources=sources,
                exchange_directory=exchange,
                mode=mode,
            )
            prepared = self.adapter.clamp_wall_time(prepared, wall_time_seconds=remaining)
            submission = self.adapter.prepare_submission(prepared)
            external_run_id, state = self.adapter.submit(submission)
        except ValueError as error:
            raise TCADDebugError(
                "staged TCAD project is not eligible for development debug"
            ) from error
        except Exception as error:
            raise RuntimeError("TCAD development debug startup failed") from error
        if not isinstance(external_run_id, str) or not external_run_id:
            raise TCADDebugError("TCAD debug returned an invalid private binding")
        context.state["reserved_wall_seconds"] = used + prepared.wall_time_seconds
        context.record_activity("tcad_debug_submitted")
        return {
            "mode": mode,
            "reserved_wall_seconds": prepared.wall_time_seconds,
            "external_run_id": external_run_id,
            "state": _state(state),
            "source_tree_sha256": source_sha,
            "project_sha256": project_debug_sha256(
                DeckProjectDraft.model_validate_json(project, strict=True)
            ),
            "declarations_sha256": declarations_sha,
        }

    def _finish(self, context, run_name, mode, record, collected, *, budget=None) -> dict[str, object]:
        root = context.workspace / ".operation-tools/tcad" / run_name
        for directory in (root.parents[1], root.parent, root):
            directory.mkdir(exist_ok=True, mode=0o700)
            if directory.is_symlink() or not directory.is_dir():
                raise TCADDebugError("TCAD debug private directory is unsafe")
        outputs = []
        for item in collected.files:
            if budget: budget.remaining_seconds()
            _write_private(root / item.name, item.content)
            if item.name == "debug.log.txt":
                write_control_workspace_file(
                    context.workspace,
                    Path(f"deck/reports/log-{run_name}.txt"),
                    item.content, replace=False, mode=0o400, create_parents=True,
                )
            if item.name != "debug.log.txt":
                outputs.append(
                    {"name": item.name, "media_type": item.media_type, "size_bytes": len(item.content)}
                )
        response: dict[str, object] = {
            "run_name": run_name,
            "mode": mode,
            "state": collected.terminal_state,
            "phase": "collected",
            "development_only": True,
            "scientific_claim_admissible": False,
            "diagnostic_layer": collected.diagnostic_layer,
            "summary": collected.summary,
            "log_excerpt": collected.log_excerpt,
            "log_relative_path": (
                f"deck/reports/log-{run_name}.txt"
                if any(item.name == "debug.log.txt" for item in collected.files) else None
            ),
            "log_excerpt_is_complete": any(
                item.name == "debug.log.txt" and item.content == collected.log_excerpt.encode("utf-8")
                for item in collected.files
            ),
            "exit_code": collected.exit_code,
            "outputs": outputs,
        }
        if collected.source_diagnostic is not None:
            response["source_diagnostic"] = asdict(collected.source_diagnostic)
        if collected.timing is not None:
            response["progress"] = collected.timing
        # Validate the complete public response before sealing a control proof.
        # Cache only the diagnostic; the handler refreshes budget on every call.
        debug_response(context, run_name, response)
        if budget: budget.remaining_seconds()
        # Preserve each attempt, including failed diagnostics, as a bounded
        # workspace record tied to the exact submitted source and declarations.
        diagnostic = {key: value for key, value in response.items() if key != "run_name"}
        diagnostic.update({key: record[key] for key in (
            "source_tree_sha256", "project_sha256", "declarations_sha256"
        )})
        try:
            write_control_workspace_file(
                context.workspace,
                Path(f"deck/reports/diagnostic-{run_name}.json"),
                canonical_json(diagnostic), replace=False, mode=0o400, create_parents=True,
            )
        except WorkspaceError as error:
            raise TCADDebugError("TCAD diagnostic record path is unsafe") from error
        if mode in {"preflight", "initialization"}:
            profile = (
                "tcad.project-preflight.v1"
                if mode == "preflight"
                else "tcad.project-initialization.v1"
            )
            try:
                write_control_workspace_file(
                    context.workspace,
                    Path(f"deck/reports/{mode}.json"),
                    canonical_json(
                        {
                            "schema_version": 1,
                            "profile": profile,
                            "source_tree_sha256": record["source_tree_sha256"],
                            "project_sha256": record["project_sha256"],
                            "declarations_sha256": record["declarations_sha256"],
                            "mode": mode,
                            "terminal_state": collected.terminal_state,
                            "exit_code": collected.exit_code,
                            "diagnostic_layer": collected.diagnostic_layer,
                            "qualified": (
                                collected.terminal_state == "succeeded"
                                and collected.exit_code == 0
                                and collected.diagnostic_layer == "complete"
                            ),
                            "summary": collected.summary,
                        }
                    ),
                    replace=True,
                    mode=0o400,
                    create_parents=True,
                )
            except WorkspaceError as error:
                raise TCADDebugError("TCAD debug report path is unsafe") from error
        return response


def _candidate(
    context: OperationToolContext,
) -> tuple[bytes, str, tuple[TCADDebugSource, ...]]:
    try:
        context.candidate_snapshot()
        envelope = parse_role_result(
            json.loads((context.output_directory / "result.json").read_bytes())
        )
        project = DeckProjectDraft.model_validate_json(
            canonical_json(envelope.payload), strict=True
        )
        sources = tuple(
            TCADDebugSource(
                source_name=slot.semantic_name,
                artifact_ref=context.input_ref(slot.semantic_name),
                media_type=context.input_media_type(slot.semantic_name),
                content=context.read_input(slot.semantic_name),
            )
            for slot in project.input_slots
        )
    except (RunCheckerError, RunOutputError, WorkspaceError):
        raise
    except Exception as error:
        raise TCADDebugError(
            "staged TCAD project did not pass complete output validation: "
            + str(error)[:2048]
        ) from error
    digest = hashlib.sha256()
    for item in sorted(project.files, key=lambda value: value.relative_path):
        digest.update(item.relative_path.encode() + b"\0" + item.content.encode() + b"\0")
    return canonical_json(project.model_dump(mode="json")), digest.hexdigest(), sources


def _state(value: str) -> str:
    if value not in _STATES:
        raise TCADDebugError("TCAD debug adapter state is invalid")
    return value


def _pending(run_name: str, mode: str, state: str) -> dict[str, object]:
    return {
        "run_name": run_name,
        "mode": mode,
        "state": state,
        "phase": "pending",
        "development_only": True,
        "scientific_claim_admissible": False,
    }


def _write_private(path: Path, content: bytes) -> None:
    if _RUN_NAME.fullmatch(path.name) is None:
        raise TCADDebugError("TCAD debug output name is unsafe")
    if path.is_symlink():
        raise TCADDebugError("TCAD debug result path is unsafe")
    if path.exists() and (not path.is_file() or path.read_bytes() != content):
        raise TCADDebugError("TCAD debug result changed for one run_name")
    if not path.exists():
        path.write_bytes(content)
        path.chmod(0o400)


__all__ = ["LocalTCADDebugService"]
