"""Thin trusted-local orchestration of the existing bounded TCAD debug adapter."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict
from pathlib import Path

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json
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
from .project_packager import DeckProjectDraft


_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MODES = frozenset({"preflight", "smoke", "initialization"})
_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
_STATES = frozenset({"accepted", "running", "cancelling", *_TERMINAL})


class LocalTCADDebugService:
    """Keep only process-local diagnostic bindings; Run owns scientific state."""

    def __init__(self, *, adapter: TCADDevelopmentDebugAdapter, exchange_root: Path | str) -> None:
        self.adapter = adapter
        self.exchange_root = Path(exchange_root).expanduser().absolute()
        self.exchange_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.exchange_root.is_symlink() or not self.exchange_root.is_dir():
            raise ValueError("local TCAD debug exchange must be a real directory")

    def run(
        self, context: OperationToolContext, *, run_name: str, mode: str
    ) -> dict[str, object]:
        if _RUN_NAME.fullmatch(run_name) is None or mode not in _MODES:
            raise TCADDebugError("TCAD development debug request is invalid")
        runs = context.state.setdefault("runs", {})
        if not isinstance(runs, dict):
            raise TCADDebugError("local TCAD debug state is invalid")
        record = runs.get(run_name)
        if record is None:
            if len(runs) >= 6:
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
                state = _state(self.adapter.status(str(record["external_run_id"])))
            except Exception as error:
                raise TCADDebugError("TCAD debug status is unavailable") from error
            record["state"] = state
            context.record_activity("tcad_debug_polled")
        if state not in _TERMINAL:
            return _pending(run_name, mode, state)
        try:
            collected = self.adapter.collect(str(record["external_run_id"]))
            response = self._finish(context, run_name, mode, record, collected)
        except Exception as error:
            raise TCADDebugError("TCAD debug collection is unavailable") from error
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
        remaining = min(context.remaining_seconds, 360 - used)
        if remaining < 1:
            raise TCADDebugError("TCAD development debug budget is exhausted")
        project, source_sha, sources = _candidate(context)
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
        except Exception as error:
            raise TCADDebugError(
                "staged TCAD project is not eligible for development debug"
            ) from error
        if not isinstance(external_run_id, str) or not external_run_id:
            raise TCADDebugError("TCAD debug returned an invalid private binding")
        context.state["reserved_wall_seconds"] = used + prepared.wall_time_seconds
        context.record_activity("tcad_debug_submitted")
        return {
            "mode": mode,
            "external_run_id": external_run_id,
            "state": _state(state),
            "source_tree_sha256": source_sha,
        }

    def _finish(self, context, run_name, mode, record, collected) -> dict[str, object]:
        root = context.workspace / ".operation-tools/tcad" / run_name
        for directory in (root.parents[1], root.parent, root):
            directory.mkdir(exist_ok=True, mode=0o700)
            if directory.is_symlink() or not directory.is_dir():
                raise TCADDebugError("TCAD debug private directory is unsafe")
        outputs = []
        for item in collected.files:
            _write_private(root / item.name, item.content)
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
            "exit_code": collected.exit_code,
            "outputs": outputs,
        }
        if collected.source_diagnostic is not None:
            response["source_diagnostic"] = asdict(collected.source_diagnostic)
        if len(canonical_json(response)) > 32 * 1024:
            raise TCADDebugError("TCAD debug diagnostic response exceeds its bound")
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
