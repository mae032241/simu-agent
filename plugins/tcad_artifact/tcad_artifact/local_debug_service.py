"""Thin trusted-local orchestration of the existing bounded TCAD debug adapter."""

from __future__ import annotations

import hashlib
import fcntl
import json
import re
import uuid
import time
from dataclasses import asdict
from pathlib import Path

from scidiscovery.artifact_agent.operation_tool_context import OperationToolContext
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.role_result import parse_role_result
from scidiscovery.plugin_runtime.workspace import (
    WorkspaceError,
    write_control_workspace_file,
)
from scidiscovery.plugin_runtime.diagnostics import (
    RunCheckerError,
    RunOutputError,
)

from .debug_contract import (
    DEVELOPMENT_ARTIFACT_LIMIT_BYTES,
    TCADDebugError,
    TCADDebugSource,
    TCADDevelopmentDebugAdapter,
)
from .debug_adapter import _development_limits
from .execution_policy import DebugPolicy
from .project_packager import DeckProjectDraft, project_debug_sha256


_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MODES = frozenset({"preflight", "smoke", "initialization"})
_TERMINAL = frozenset({"succeeded", "failed", "cancelled", "collected"})
_STATES = frozenset({"accepted", "running", "cancelling", *_TERMINAL})
def debug_tool_description() -> str:
    return (
        "Submit or poll one TCAD development diagnostic under administrator-configured mode, "
        "attempt, wall-time, storage and delivery limits; never scientific evidence. "
        "Responses expose the frozen Run budget and each job reservation. Renaming a job "
        "does not reset the budget; repeating a name polls the same submission. "
        "For initialization select declared output_names. Read details_path for retained "
        "diagnostics and file identities; file bytes are not returned in this summary."
    )


def _debug_policy(context):
    return DebugPolicy.model_validate_json(json.dumps(context.state["debug_policy"]), strict=True)


def debug_response(context: OperationToolContext, run_name: str, response: dict) -> dict:
    runs = context.state.get("runs", {})
    used = context.state.get("reserved_wall_seconds", 0)
    remaining = max(0, _debug_policy(context).total_wall_seconds - used)
    result = {**response, "budget": {
        "total_wall_seconds": _debug_policy(context).total_wall_seconds,
        "reserved_wall_seconds": used,
        "remaining_wall_seconds": remaining,
        "max_runs": _debug_policy(context).max_runs,
        "created_runs": len(context.state.get("reservations", runs)),
        "remaining_runs": max(0, _debug_policy(context).max_runs - len(context.state.get("reservations", runs))),
        "run_remaining_seconds": context.remaining_seconds,
        "effective_wall_seconds": max(0, min(remaining, context.remaining_seconds)),
    }}
    record = runs.get(run_name)
    if record is not None:
        result["reserved_wall_seconds_for_run"] = record["reserved_wall_seconds"]
        result["delivery_budget"] = record.get("delivery_budget")
    if len(canonical_json(result)) > _debug_policy(context).max_response_bytes:
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
        "source_diagnostic", "log_relative_path", "delivery_budget", "budget", "reserved_wall_seconds_for_run", "missing_outputs") if key in full}
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
        self, context: OperationToolContext, *, run_name: str, mode: str, output_names: list[str] | None = None
    ) -> dict[str, object]:
        subject = None
        for alias in ("research_objective", "scientific_skeleton", "experiment_plan"):
            try:
                subject = context.input_ref(alias)
                break
            except (KeyError, ValueError):
                continue
        if subject is None:
            raise TCADDebugError("debug budget requires an immutable scientific subject binding")
        key = canonical_sha256({"subject": subject})
        root = self.exchange_root / "budgets"
        root.mkdir(exist_ok=True, mode=0o700)
        path = root / (key + ".json")
        from scidiscovery.plugin_runtime.workspace import atomic_json
        with (root / (key + ".lock")).open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if path.exists():
                context.state.update(json.loads(path.read_bytes()))
            context.state["budget_ledger_path"] = str(path)
            try:
                return self._run_locked(context, run_name=run_name, mode=mode, output_names=output_names)
            finally:
                self._save_budget(context)

    def experiment_activity(self, run_ids, inputs, *, cancel=False, name=None):
        """Observe/cancel persisted jobs without resetting the original allowance."""
        from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
        from scidiscovery.plugin_runtime.workspace import atomic_json
        subject = next((item.artifact_ref for item in inputs if item.port_name == "research_objective"), None)
        if subject is None:
            return False
        key = canonical_sha256({"subject": subject})
        root = self.exchange_root / "budgets"
        path = root / (key + ".json")
        if not path.exists():
            return False
        active = False
        with (root / (key + ".lock")).open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            ledger = json.loads(path.read_bytes())
            records = ledger.setdefault("runs", {})
            for alias, reservation in ledger.get("reservations", {}).items():
                record = records.get(alias, reservation["record"])
                if record.get("run_id") not in run_ids or (name is not None and alias != name):
                    continue
                if record.get("state") in _TERMINAL:
                    continue
                external = record.get("external_run_id")
                if external is None:
                    found = self.adapter.lookup_submission(LocalFileDescriptor.model_validate_json(json.dumps(reservation["submission"]), strict=True))
                    if found is None:
                        # No accepted job; its reservation remains spent.
                        continue
                    external, state = found
                    record = {**record, "external_run_id": external, "state": _state(state)}
                if cancel and record["state"] not in _TERMINAL:
                    record["state"] = _state(self.adapter.cancel(external))
                active = active or record["state"] not in _TERMINAL
                if cancel:
                    records[alias] = record
            if cancel:
                atomic_json(path, ledger)
        return active

    @staticmethod
    def _save_budget(context):
        from scidiscovery.plugin_runtime.workspace import atomic_json
        atomic_json(Path(context.state["budget_ledger_path"]), {key: context.state[key] for key in
            ("debug_policy", "reserved_wall_seconds", "runs", "reservations") if key in context.state})

    def _run_locked(self, context, *, run_name, mode, output_names):
        context.state.setdefault("debug_policy", self.adapter.policy.model_dump(mode="json"))
        call_started = time.monotonic()
        if _RUN_NAME.fullmatch(run_name) is None or mode not in _MODES:
            raise TCADDebugError("TCAD development debug request is invalid")
        if output_names and mode != "initialization":
            raise TCADDebugError("output_names is only available for initialization")
        selected = tuple(sorted(set(output_names or ())))
        runs = context.state.setdefault("runs", {})
        if not isinstance(runs, dict):
            raise TCADDebugError("local TCAD debug state is invalid")
        record = runs.get(run_name)
        reservations = context.state.setdefault("reservations", {})
        if record is None and run_name in reservations:
            from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
            pending = reservations[run_name]
            found = self.adapter.lookup_submission(LocalFileDescriptor.model_validate_json(
                json.dumps(pending["submission"]), strict=True))
            if found is None:
                raise TCADDebugError("reserved debug submission was not accepted; allowance remains consumed")
            record = {**pending["record"], "external_run_id": found[0], "state": _state(found[1])}
            runs[run_name] = record
        if record is None:
            if len(reservations) >= _debug_policy(context).max_runs:
                raise TCADDebugError("TCAD development debug run limit is exhausted")
            record = self._start(context, run_name, mode, selected)
            runs[run_name] = record
        if not isinstance(record, dict) or record.get("mode") != mode:
            raise TCADDebugError("TCAD debug run_name is bound to another mode")
        if output_names is not None and tuple(record.get("output_names", ())) != selected:
            raise TCADDebugError("debug run_name is bound to another output selection; poll without output_names")
        if isinstance(record.get("response"), dict) or (self._receipt_directory(context, run_name, record["run_id"]) / "receipt.json").is_file():
            return self._restore_receipt(context, run_name, record)
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
            from scidiscovery.plugin_runtime.collection import CollectionContext
            remaining = context.remaining_seconds - (time.monotonic() - call_started)
            budget = CollectionContext.for_seconds(remaining)
            budget.remaining_seconds()
            collect = getattr(self.adapter, "collect_with_budget", None)
            if self.runtime_context is not None:
                from .debug_collection import collect as collect_in_process
                collected = collect_in_process(self.runtime_context, str(record["external_run_id"]), context=budget, limits=record["collection_limits"])
            elif callable(collect):
                collected = collect(str(record["external_run_id"]), context=budget, limits=record["collection_limits"])
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
        self, context: OperationToolContext, run_name: str, mode: str, output_names: tuple[str, ...]
    ) -> dict[str, object]:
        used = context.state.get("reserved_wall_seconds", 0)
        if type(used) is not int or used < 0:
            raise TCADDebugError("local TCAD debug budget is invalid")
        remaining = min(context.remaining_seconds, _debug_policy(context).total_wall_seconds - used)
        if remaining < 1:
            raise TCADDebugError("TCAD development debug budget is exhausted")
        project, source_sha, sources = _candidate(context)
        delivery = _delivery_budget(context, project, mode, output_names)
        capability = (context.state["experiment_capability"] if "experiment_capability" in context.state
            else context.read_input("execution_capability"))
        draft = DeckProjectDraft.model_validate_json(project, strict=True)
        entrypoint = draft.development_initialization_entrypoint if mode == "initialization" else draft.entrypoint
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
                capability=capability,
                sources=sources,
                exchange_directory=exchange,
                mode=mode,
                output_budget_bytes=delivery["effective_collection_bytes"],
                **({"output_names": output_names} if output_names else {}),
            )
            prepared = self.adapter.clamp_wall_time(prepared, wall_time_seconds=remaining)
            submission = self.adapter.prepare_submission(prepared)
            pending_record = {
                "mode": mode,
                "delivery_budget": delivery,
                "collection_limits": {"max_output_bytes": delivery["effective_collection_bytes"],
                    **{key: getattr(_debug_policy(context), key) for key in
                       ("max_output_file_bytes", "max_output_files", "max_log_bytes", "max_manifest_bytes", "max_response_log_chars")}},
                "run_id": context.run_id,
                "operation_id": context.operation_id,
                "backend_release": json.loads(capability).get("public_release_label"),
                "entrypoint": entrypoint,
                "arguments": prepared.arguments,
                "output_names": output_names,
                "collect_generated_outputs": DeckProjectDraft.model_validate_json(project).collect_generated_outputs,
                "reserved_wall_seconds": prepared.wall_time_seconds,
                "external_run_id": None,
                "state": "accepted",
                "source_tree_sha256": source_sha,
                "project_sha256": project_debug_sha256(
                    DeckProjectDraft.model_validate_json(project, strict=True)
                ),
                **({"implementation_ref": context.state["experiment_implementation_ref"]}
                    if "experiment_implementation_ref" in context.state else {}),
                "declarations_sha256": declarations_sha,
            }
            context.state["reserved_wall_seconds"] = used + prepared.wall_time_seconds
            context.state.setdefault("reservations", {})[run_name] = {
                "submission": submission.model_dump(mode="json"), "record": pending_record}
            self._save_budget(context)
            external_run_id, state = self.adapter.submit(submission)
        except TCADDebugError:
            raise
        except ValueError as error:
            raise TCADDebugError(
                "staged TCAD project is not eligible for development debug: " + str(error)
            ) from error
        except Exception as error:
            raise RuntimeError("TCAD development debug startup failed") from error
        if not isinstance(external_run_id, str) or not external_run_id:
            raise TCADDebugError("TCAD debug returned an invalid private binding")
        context.state["reserved_wall_seconds"] = used + prepared.wall_time_seconds
        context.record_activity("tcad_debug_submitted")
        return {**pending_record, "external_run_id": external_run_id, "state": _state(state)}

    def _finish(self, context, run_name, mode, record, collected, *, budget=None) -> dict[str, object]:
        root = context.workspace / ".operation-tools/tcad" / run_name
        for directory in (root.parents[1], root.parent, root):
            directory.mkdir(exist_ok=True, mode=0o700)
            if directory.is_symlink() or not directory.is_dir():
                raise TCADDebugError("TCAD debug private directory is unsafe")
        outputs = []
        retained = []
        for item in collected.files:
            if budget: budget.remaining_seconds()
            if mode != "initialization" or item.name == "debug.log.txt":
                _write_private(root / item.name, item.content)
            if item.name == "debug.log.txt":
                write_control_workspace_file(
                    context.workspace,
                    Path(f"deck/reports/log-{run_name}.txt"),
                    item.content, replace=False, mode=0o400, create_parents=True,
                )
                retained.append(_file_identity(f"reports/log-{run_name}.txt", item.content, item.media_type))
            if item.name != "debug.log.txt":
                entry = {"name": item.name, "media_type": item.media_type, "size_bytes": len(item.content)}
                if item.relative_path is not None:
                    entry["source_path"] = item.relative_path
                if mode == "initialization":
                    relative = Path("deck/reports") / run_name / item.name
                    try:
                        write_control_workspace_file(context.workspace, relative, item.content,
                            replace=False, mode=0o400, create_parents=True)
                    except WorkspaceError as error:
                        raise TCADDebugError(f"initialization output path is unsafe: {relative}") from error
                    entry["relative_path"] = relative.as_posix()
                entry["sha256"] = hashlib.sha256(item.content).hexdigest()
                outputs.append(entry)
                if mode == "initialization" and (
                    item.name in record.get("output_names", ())
                    or (record.get("collect_generated_outputs") and item.name.startswith("generated_"))
                ):
                    retained.append(_file_identity(relative.relative_to("deck").as_posix(), item.content, item.media_type))
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
        present = {item["name"] for item in outputs if item["size_bytes"] > 0}
        missing = sorted(set(record.get("output_names", ())) - present)
        if missing:
            response["missing_outputs"] = missing
            if collected.diagnostic_layer in {"complete", "output_contract"}:
                response.update(diagnostic_layer="collection",
                    summary="Initialization diagnostic outputs missing or empty: " + ", ".join(missing))
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
            "source_tree_sha256", "project_sha256", "declarations_sha256",
            "run_id", "operation_id", "backend_release", "entrypoint", "arguments", "output_names", "delivery_budget", "collection_limits"
        )})
        diagnostic["run_name"] = run_name
        if "implementation_ref" in record:
            diagnostic["implementation_ref"] = record["implementation_ref"]
        diagnostic_bytes = canonical_json(diagnostic)
        retained.append(_file_identity(f"reports/diagnostic-{run_name}.json", diagnostic_bytes, "application/json"))
        try:
            write_control_workspace_file(
                context.workspace,
                Path(f"deck/reports/diagnostic-{run_name}.json"),
                diagnostic_bytes, replace=False, mode=0o400, create_parents=True,
            )
        except WorkspaceError as error:
            raise TCADDebugError("TCAD diagnostic record path is unsafe") from error
        if mode in {"preflight", "initialization"}:
            profile = (
                "tcad.project-preflight.v1"
                if mode == "preflight"
                else "tcad.project-initialization.v1"
            )
            report_bytes = canonical_json(
                        {
                            "schema_version": 1,
                            "profile": profile,
                            "source_tree_sha256": record["source_tree_sha256"],
                            "project_sha256": record["project_sha256"],
                            "declarations_sha256": record["declarations_sha256"],
                            "mode": mode,
                            "terminal_state": collected.terminal_state,
                            "exit_code": collected.exit_code,
                            "diagnostic_layer": response["diagnostic_layer"],
                            "qualified": (
                                collected.terminal_state == "succeeded"
                                and collected.exit_code == 0
                                and response["diagnostic_layer"] == "complete"
                                and not missing
                            ),
                            "summary": response["summary"],
                        }
                    )
            try:
                write_control_workspace_file(
                    context.workspace,
                    Path(f"deck/reports/{mode}.json"),
                    report_bytes,
                    replace=True,
                    mode=0o400,
                    create_parents=True,
                )
            except WorkspaceError as error:
                raise TCADDebugError("TCAD debug report path is unsafe") from error
            retained.append(_file_identity(f"reports/{mode}.json", report_bytes, "application/json"))
            proof = {**diagnostic, "files": retained, "collection_complete": (
                collected.terminal_state == "succeeded" and collected.exit_code == 0
                and response["diagnostic_layer"] == "complete" and not missing)}
            context.state.setdefault("finalization_records", {})[mode] = canonical_json(proof)
        else:
            proof = {**diagnostic, "files": retained, "collection_complete": False}
        self._save_receipt(context, run_name, record, proof, response)
        return response

    @staticmethod
    def _receipt_directory(context, run_name, source_run_id):
        key = canonical_sha256({"run_id": source_run_id, "run_name": run_name})
        return Path(context.state["budget_ledger_path"]).parent / "receipts" / key

    def _save_receipt(self, context, run_name, record, proof, response):
        """Persist control-produced collection identities separately from budgets."""
        root = self._receipt_directory(context, run_name, record["run_id"])
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for item in proof["files"]:
            raw = (context.workspace / "deck" / item["relative_path"]).read_bytes()
            if len(raw) != item["size_bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise TCADDebugError("diagnostic changed before control receipt retention")
            _write_private(root / item["sha256"], raw)
        _write_private(root / "receipt.json", canonical_json({"proof": proof, "response": response,
            "submission": context.state["reservations"][run_name]["submission"]}))

    def _restore_receipt(self, context, run_name, record, *, validate=True):
        source_run = record["run_id"]
        if not context.recovery_authorized(source_run):
            raise TCADDebugError("cached diagnostic belongs to another Run without a control recovery relationship")
        root = self._receipt_directory(context, run_name, source_run)
        receipt = json.loads((root / "receipt.json").read_bytes())
        if receipt["submission"] != context.state["reservations"][run_name]["submission"]:
            raise TCADDebugError("retained diagnostic submission identity changed")
        proof = receipt["proof"]
        if proof["run_id"] != source_run or proof["project_sha256"] != record["project_sha256"]:
            raise TCADDebugError("retained diagnostic proof identity changed")
        experiment = "experiment_project" in context.state
        if experiment:
            current = DeckProjectDraft.model_validate_json(context.state["experiment_project"], strict=True)
            if (record.get("implementation_ref") != context.state.get("experiment_implementation_ref")
                    or proof.get("implementation_ref") != record.get("implementation_ref")
                    or project_debug_sha256(current) != record["project_sha256"]):
                raise TCADDebugError("Retained diagnostic does not belong to this sealed implementation.")
        for item in proof["files"]:
            relative = Path(item["relative_path"])
            if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "reports":
                raise TCADDebugError("retained diagnostic path is unsafe")
            raw = (root / item["sha256"]).read_bytes()
            if len(raw) != item["size_bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise TCADDebugError("retained diagnostic bytes changed")
            target = context.workspace / "deck" / relative
            if target.exists() and target.read_bytes() != raw:
                raise TCADDebugError("current diagnostic conflicts with the retained original")
            write_control_workspace_file(context.workspace, Path("deck") / relative, raw,
                replace=True, mode=0o400, create_parents=True)
        restored = {**proof, "run_id": context.run_id, "operation_id": context.operation_id,
            "recovered_from_run_id": source_run,
            "original_receipt_sha256": canonical_sha256(receipt)}
        records = context.state.setdefault("finalization_records", {})
        previous = dict(records)
        if record["mode"] in {"preflight", "initialization"}:
            records[record["mode"]] = canonical_json(restored)
        if validate and not experiment:
            try:
                # Restore all completed modes before the finalizer checks the
                # current candidate. Each control receipt is independently verified.
                for other_name, other in context.state.get("runs", {}).items():
                    if (other_name != run_name and (self._receipt_directory(context, other_name, other["run_id"]) / "receipt.json").is_file()
                            and other.get("project_sha256") == record["project_sha256"]
                            and context.recovery_authorized(other["run_id"])):
                        self._restore_receipt(context, other_name, other, validate=False)
                context.candidate_snapshot()
                envelope = json.loads((context.output_directory / "result.json").read_bytes())
                current = DeckProjectDraft.model_validate_json(canonical_json(envelope["payload"]), strict=True)
                if project_debug_sha256(current) != record["project_sha256"]:
                    raise TCADDebugError("recovered diagnostic differs from current project")
            except Exception:
                records.clear()
                records.update(previous)
                raise
        return dict(receipt["response"])


def _file_identity(path, raw, media_type):
    return {"relative_path": path, "media_type": media_type, "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def _delivery_budget(context, project, mode, output_names):
    """Budget encoding before reservation; a generous contract maximum is not a prediction."""
    from .project_packager import AttemptFile
    import base64
    envelope = ({"payload": json.loads(project)} if "experiment_project" in context.state
        else json.loads((context.output_directory / "result.json").read_bytes()))
    handoff = context.workspace / "deck/handoff.json"
    if handoff.is_file():
        envelope["handoff"] = json.loads(handoff.read_bytes())
    existing = {}
    for raw in context.state.get("finalization_records", {}).values():
        proof = json.loads(raw)
        if not proof.get("collection_complete") or proof["mode"] == mode or proof["project_sha256"] != project_debug_sha256(DeckProjectDraft.model_validate_json(project)):
            continue
        for item in proof["files"]:
            content = (context.workspace / "deck" / item["relative_path"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise TCADDebugError("existing selected development diagnostic was changed: " + item["relative_path"])
            try:
                text, encoding = content.decode("utf-8"), "utf8"
            except UnicodeDecodeError:
                text, encoding = base64.b64encode(content).decode("ascii"), "base64"
            existing[item["relative_path"]] = AttemptFile(relative_path=item["relative_path"], content=text, encoding=encoding).model_dump(mode="json")
    envelope["payload"]["development_diagnostics"] = list(existing.values())
    known = len(canonical_json(envelope))
    # Two reports and future attestation/envelope metadata. Binary snapshots use
    # base64; this twofold estimate is not a guarantee for arbitrary text, so the
    # final envelope check remains authoritative.
    reserve = 256 * 1024 + 1024 * len(output_names)
    remaining = DEVELOPMENT_ARTIFACT_LIMIT_BYTES - known - reserve
    if remaining <= 0:
        raise TCADDebugError(f"development delivery budget exhausted before startup: known_bytes={known}, report_reserve_bytes={reserve}, remaining_bytes={remaining}, outputs={list(output_names)}; shrink the diagnostic/source or selected output_names")
    effective = min(DeckProjectDraft.model_validate_json(project).resource_limits.max_output_bytes, _development_limits(mode, _debug_policy(context))[1], remaining // 2)
    return {"envelope_limit_bytes": DEVELOPMENT_ARTIFACT_LIMIT_BYTES, "known_encoded_bytes": known,
            "report_reserve_bytes": reserve, "remaining_encoded_bytes": remaining,
            "effective_collection_bytes": effective, "unknown_output_sizes": list(output_names),
            "final_delivery_guaranteed": False,
            "overflow_action": "retain collection error and diagnostic paths; shrink diagnostic or deliver implementation_gap; final envelope is checked again"}


def _candidate(
    context: OperationToolContext,
) -> tuple[bytes, str, tuple[TCADDebugSource, ...]]:
    try:
        if "experiment_project" in context.state:
            project = DeckProjectDraft.model_validate_json(context.state["experiment_project"], strict=True)
            sources = tuple(context.state["experiment_sources"])
        else:
            context.candidate_snapshot()
            envelope = parse_role_result(json.loads((context.output_directory / "result.json").read_bytes()))
            project = DeckProjectDraft.model_validate_json(canonical_json(envelope.payload), strict=True)
            sources = tuple(
            TCADDebugSource(
                source_name=slot.semantic_name,
                artifact_ref=context.input_ref(slot.semantic_name),
                media_type=context.input_media_type(slot.semantic_name),
                content=context.input_path(slot.semantic_name),
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
