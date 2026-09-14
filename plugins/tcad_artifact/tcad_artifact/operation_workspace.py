"""TCAD task-private workspace components for registered Agent operations."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError, _validation_details
from scidiscovery.artifact_agent.schema.role_result import (
    RoleHandoff,
    RoleResultEnvelope,
    parse_role_result,
)
from scidiscovery.operations.spec import CallableComponent
from scidiscovery.operation_contract import contract_diagnostic, DeclaredDiagnostic, SemanticRuleViolation
from scidiscovery.operations.workspace import (
    WorkspaceFileRequest,
    WorkspaceFileRule,
    WorkspaceFinalizationRequest,
    WorkspaceMaterializationRequest,
    WorkspaceMaterializationResult,
    WorkspaceProtocolError,
    WorkspaceSnapshotFile,
)

from .project_materializer import (
    ProjectMaterializationError,
    declarations_template_json,
    materialization_contract_json,
    materialize_deck_project,
    report_json,
)
from .project_packager import (
    DeckProjectDraft,
    DeckFile,
    ImplementationGap,
    parse_author_result,
    validate_implementation_gap,
    ProjectInitializationAttestation,
    ProjectPreflightAttestation,
    project_debug_sha256,
)


_AUTHOR_PREFIX = "tcad.deck.author."
_REVISION_OPERATIONS = frozenset(
    {
        "tcad.deck.author.revise.v1",
        "tcad.deck.author.runtime-failure.v1",
    }
)
_MAX_SOURCE_FILE_BYTES = 8 * 1024 * 1024
_MAX_SOURCE_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_SOURCE_FILES = 4096


def _deck_root(root: Path) -> Path:
    deck = root / "deck"
    try:
        details = os.lstat(deck)
    except OSError as error:
        raise WorkspaceProtocolError("deck must be an existing task-local directory") from error
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise WorkspaceProtocolError("deck must be a real task-local directory, not a symbolic link")
    return deck


def _protocol_error(message: str, error: Exception | None = None, *, path: str = "$.deck") -> WorkspaceProtocolError:
    details: tuple[dict[str, str], ...] = getattr(error, "details", ())
    if isinstance(error, (ValidationError, SemanticRuleViolation)):
        schema = {"allOf": [DeckProjectDraft.model_json_schema(), ImplementationGap.model_json_schema()]}
        details = tuple(DeclaredDiagnostic({**item, "path": path + item["path"][1:]})
            for item in _validation_details(error, schema=schema, phase="output_payload"))
    return WorkspaceProtocolError(message, details=details)


def _read(path: Path, *, max_bytes: int) -> bytes:
    try:
        details = os.lstat(path)
    except OSError as error:
        raise WorkspaceProtocolError(f"workspace file is missing: {path.name}") from error
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise WorkspaceProtocolError("workspace item must be a regular non-symlink file")
    if details.st_size > max_bytes:
        raise WorkspaceProtocolError("workspace file exceeds its byte limit", details=(
            contract_diagnostic("output_invalid", phase="output_payload", affected_action="submit",
                path="$.deck.files", repairable=True,
                message=f"Workspace file exceeds its byte limit ({max_bytes} bytes)."),))
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise WorkspaceProtocolError("workspace file exceeds its byte limit", details=(
            contract_diagnostic("output_invalid", phase="output_payload", affected_action="submit",
                path="$.deck.files", repairable=True,
                message=f"Workspace file exceeds its byte limit ({max_bytes} bytes)."),))
    return raw


def _write(path: Path, content: bytes, *, editable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise WorkspaceProtocolError("workspace destination must be a regular file")
        if path.read_bytes() != content:
            raise WorkspaceProtocolError("workspace destination differs from immutable source")
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=".workspace.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600 if editable else 0o400)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _input(request: WorkspaceMaterializationRequest | WorkspaceFinalizationRequest, name: str) -> bytes:
    try:
        path = request.input_paths[name]
        return _read(path, max_bytes=64 * 1024 * 1024)
    except (KeyError, WorkspaceProtocolError) as error:
        raise RunCheckerError("TCAD bound input is unavailable in the workspace", category="integrity_failure") from error


def _source_files(root: Path, *, max_bytes: int = _MAX_SOURCE_TOTAL_BYTES, max_files: int = _MAX_SOURCE_FILES) -> list[dict[str, str]]:
    try:
        root_details = os.lstat(root)
    except OSError as error:
        raise WorkspaceProtocolError("deck/files directory does not exist") from error
    if stat.S_ISLNK(root_details.st_mode) or not stat.S_ISDIR(root_details.st_mode):
        raise WorkspaceProtocolError("deck/files must be a real directory")
    values: list[dict[str, str]] = []
    total = 0
    for current, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        current_path = Path(current)
        for directory in directories:
            details = os.lstat(current_path / directory)
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
                raise WorkspaceProtocolError("deck/files cannot contain symlinks")
        for name in sorted(files):
            path = current_path / name
            raw = _read(path, max_bytes=_MAX_SOURCE_FILE_BYTES)
            total += len(raw)
            if total > max_bytes or len(values) >= max_files:
                raise WorkspaceProtocolError("deck source tree exceeds its bound")
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise WorkspaceProtocolError("deck source file is not UTF-8") from error
            values.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "content": content,
                }
            )
    values.sort(key=lambda item: item["relative_path"])
    return values


def _restore_retry(request: WorkspaceMaterializationRequest) -> tuple[DeckProjectDraft | ImplementationGap, dict[str, Any]] | None:
    for root in reversed(request.provisional_roots):
        result = root / "result.json"
        if result.is_file() and not result.is_symlink():
            try:
                envelope = parse_role_result(json.loads(result.read_text("utf-8")))
                return (
                    parse_author_result(canonical_json(envelope.payload)),
                    envelope.handoff.model_dump(mode="json"),
                )
            except (OSError, UnicodeError, json.JSONDecodeError, ValidationError):
                pass
        deck = root / "deck"
        try:
            metadata = json.loads(_read(deck / "project.json", max_bytes=8 * 1024 * 1024))
            handoff = RoleHandoff.model_validate_json(
                _read(deck / "handoff.json", max_bytes=64 * 1024), strict=True
            )
            project = DeckProjectDraft.model_validate_json(
                canonical_json(
                    {**metadata, "files": _source_files(deck / "files")}
                ),
                strict=True,
            )
            return project, handoff.model_dump(mode="json")
        except (WorkspaceProtocolError, ValidationError, json.JSONDecodeError, TypeError):
            continue
    return None


def _author_metadata(metadata: dict[str, Any], *, deterministic: bool) -> dict[str, Any]:
    metadata = dict(metadata)
    for field in ("materialization_report", "preflight_attestation", "initialization_attestation"):
        metadata.pop(field, None)
    if deterministic:
        for field in (
            "schema_version", "tool_profile", "solver_kind", "capability_sha256",
            "expected_outputs", "parameter_bindings", "case_parameter_bindings",
            "runtime_assertions", "realization_manifest",
        ):
            metadata.pop(field, None)
    return metadata


def _restore_retry_tree(
    request: WorkspaceMaterializationRequest, deck: Path, *, deterministic: bool
) -> bool:
    """Restore the latest bounded raw candidate, including a not-yet-valid deck."""

    for root in reversed(request.provisional_roots):
        source = root / "deck"
        if not source.is_dir():
            continue
        _deck_root(root)
        for name in ("gap.json", "handoff.json"):
            if (source / name).exists():
                _write(deck / name, _read(source / name, max_bytes=64 * 1024), editable=True)
        _restore_attempt(deck, _attempt_files(source), author=True, deterministic=deterministic)
        return True
    return False


def _attempt_files(deck: Path) -> tuple[DeckFile, ...]:
    """Capture bounded source and diagnostics, without granting execution readiness."""
    values = []
    for name in ("project.json", "declarations.json", "attempts.md"):
        if (deck / name).exists():
            values.append(DeckFile(
                relative_path=name,
                content=_read(deck / name, max_bytes=8 * 1024 * 1024).decode("utf-8"),
            ))
    for directory in ("files", "reports"):
        root = deck / directory
        if root.exists():
            for item in _source_files(root, max_bytes=16 * 1024 * 1024, max_files=128):
                values.append(DeckFile(relative_path=f"{directory}/{item['relative_path']}", content=item["content"]))
    if len(values) > 128 or sum(len(item.content.encode("utf-8")) for item in values) > 16 * 1024 * 1024:
        raise WorkspaceProtocolError("attempt record exceeds its file or byte limit")
    return tuple(values)


def _restore_attempt(deck: Path, files: tuple[DeckFile, ...], *, author: bool, deterministic: bool) -> None:
    for item in files:
        path = item.relative_path
        content = item.content.encode("utf-8")
        if author and path == "project.json":
            try:
                metadata = json.loads(content)
            except (ValueError, UnicodeError):
                metadata = None
            if isinstance(metadata, dict):
                content = _pretty(_author_metadata(metadata, deterministic=deterministic))
            else:
                # An unfinished metadata edit must remain diagnosable, not
                # prevent creation of the repair workspace.
                path = f"reports/history/{canonical_sha256(item.content)}_project.json"

        if author and path.startswith("reports/") and not path.startswith("reports/history/"):
            # Historical diagnostics remain readable; fresh completion proofs must
            # be generated at the current reports/preflight|initialization paths.
            path = f"reports/history/{canonical_sha256(item.content)}_{Path(path).name}"
        _write(deck / path, content, editable=author and not path.startswith("reports/") and (path != "project.json" or not deterministic))


def _capability_snapshot(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunCheckerError("admitted execution_capability is invalid JSON", category="admission_defect") from error
    if not isinstance(value, dict):
        raise RunCheckerError("admitted execution_capability must be a JSON object", category="admission_defect")
    return value


def _make_tree_read_only(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in files:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                raise WorkspaceProtocolError("review workspace cannot contain symlinks")
            path.chmod(0o400)
        for name in directories:
            path = current_path / name
            if path.is_symlink() or not path.is_dir():
                raise WorkspaceProtocolError("review workspace directory is invalid")
            path.chmod(0o500)
    root.chmod(0o500)


def _review_template(project: DeckProjectDraft | ImplementationGap) -> bytes:
    """Build a structural, fail-closed review template without making a verdict."""

    requirements = [
        {
            "requirement_key": item.requirement_key,
            "status": "unknown",
            "rationale": "由独立审查者填写该要求的代码与物理核查结论。",
        }
        for item in (() if isinstance(project, ImplementationGap) else project.realization_manifest)
    ]
    return _pretty(
        {
            "schema_version": 1,
            "handoff": {
                "assumptions": [],
                "missing_inputs": [],
                "next_actions": [],
            },
            "payload": {
                "verdict": "blocked",
                "capability_sha256": None if isinstance(project, ImplementationGap) else project.capability_sha256,
                "summary": "结构模板；尚未形成科学审查结论。",
                "rationale": "逐项检查任务内项目、实验计划和能力声明后填写。",
                "physical_fidelity": "unknown",
                "implementation_fidelity": "unknown",
                "syntax_fidelity": "unknown",
                "numerical_protocol_fidelity": "unknown",
                "requirement_reviews": requirements,
                "findings": [],
                "undeclared_defaults": [],
                "unsupported_constructs": [],
                "missing_inputs": [],
                "execution_ready": False,
                "next_actions": [],
            },
        }
    )


def materialize_workspace(
    request: WorkspaceMaterializationRequest,
) -> WorkspaceMaterializationResult:
    author = request.operation_id.startswith(_AUTHOR_PREFIX)
    revision = author and request.operation_id in _REVISION_OPERATIONS
    deck = request.workspace / "deck"
    files_root = deck / "files"
    contract = deck / "contract"
    reports = deck / "reports"
    deck.mkdir(parents=True, exist_ok=True, mode=0o700)
    files_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    capability_raw = _input(request, "execution_capability")
    plan_raw = request.input_paths.get("experiment_plan")
    capability = _capability_snapshot(capability_raw)
    deterministic = (
        author
        and plan_raw is not None
        and capability.get("solver_kind") == "sprocess"
    )
    mode = "review"
    base: DeckProjectDraft | None = None
    handoff: dict[str, Any] | None = None
    if author:
        raw_retry = _restore_retry_tree(request, deck, deterministic=deterministic)
        restored = None if raw_retry else _restore_retry(request)
        if raw_retry:
            mode = "retry"
        elif restored is not None:
            mode = "retry"
            base, handoff = restored
            if isinstance(base, ImplementationGap):
                _restore_attempt(deck, base.attempt_files, author=True, deterministic=deterministic)
                _write(deck / "gap.json", _pretty(base.model_dump(mode="json", exclude={"attempt_files"})), editable=True)
                base = None
        elif revision:
            mode = "revise"
            try:
                base = parse_author_result(_input(request, "prior_project"))
            except ValidationError as error:
                raise _protocol_error("prior_project is invalid", error) from error
        else:
            mode = "create"
    else:
        try:
            base = parse_author_result(_input(request, "project"))
        except ValidationError as error:
            raise _protocol_error("review project is invalid", error) from error

    if author and isinstance(base, ImplementationGap):
        _restore_attempt(deck, base.attempt_files, author=True, deterministic=deterministic)
        _write(deck / "gap.json", _pretty(base.model_dump(mode="json", exclude={"attempt_files"})), editable=True)
        base = None

    if not author and isinstance(base, ImplementationGap):
        _restore_attempt(deck, base.attempt_files, author=False, deterministic=False)
        _write(deck / "gap.json", _pretty(base.model_dump(mode="json")), editable=False)
        _write(deck / "review-template.json", _review_template(base), editable=False)
        _make_tree_read_only(deck)
        return WorkspaceMaterializationResult(
            manifest_name="domain_workspace",
            manifest={"protocol": "scidiscovery.tcad-deck-workspace.v2", "mode": "review_gap",
                      "access": "read_only", "root_relative_path": "deck",
                      "gap_relative_path": "deck/gap.json", "review_template_relative_path": "deck/review-template.json"},
            paths={"deck_workspace_path": str(deck), "deck_gap_path": str(deck / "gap.json"),
                   "deck_review_template_path": str(deck / "review-template.json"), "deck_access": "read_only", "deck_mode": "review_gap"},
            read_paths=("deck",),
        )

    metadata_path = deck / "project.json"
    declarations_path = deck / "declarations.json"
    if not metadata_path.exists():
        if base is None:
            metadata: dict[str, Any] = (
                {}
                if deterministic
                else {
                    "schema_version": 1,
                    "tool_profile": capability.get("profile_id"),
                    "solver_kind": capability.get("solver_kind"),
                    "capability_sha256": capability.get("capability_sha256"),
                    "input_slots": [],
                    "entrypoint": None,
                    "arguments": [],
                    "expected_outputs": [],
                    "parameter_bindings": [],
                    "case_parameter_bindings": [],
                    "runtime_assertions": [],
                    "realization_manifest": [],
                    "resource_limits": None,
                }
            )
        else:
            metadata = base.model_dump(mode="json")
            metadata.pop("files", None)
            if author:
                # Retry/revision inherits authored content, never old control proofs.
                metadata = _author_metadata(metadata, deterministic=deterministic)
            for item in base.files:
                _write(
                    files_root / item.relative_path,
                    item.content.encode("utf-8"),
                    editable=author,
                )
        _write(metadata_path, _pretty(metadata), editable=author and not deterministic)

    if deterministic:
        assert plan_raw is not None
        plan = _read(plan_raw, max_bytes=16 * 1024 * 1024)
        contract.mkdir(parents=True, exist_ok=True, mode=0o700)
        reports.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not declarations_path.exists():
            _write(
                declarations_path,
                declarations_template_json(plan, base_project=base),
                editable=True,
            )
        _write(contract / "capability.json", capability_raw, editable=False)
        _write(contract / "experiment-controls.json", plan, editable=False)
        _write(
            contract / "materialization-spec.json",
            materialization_contract_json(plan),
            editable=False,
        )

    handoff_path = deck / "handoff.json"
    if author and not handoff_path.exists():
        _write(
            handoff_path,
            _pretty(
                handoff
                or {
                    "assumptions": [],
                    "missing_inputs": [],
                    "next_actions": [],
                }
            ),
            editable=True,
        )
    if not author:
        assert base is not None
        _write(deck / "review-template.json", _review_template(base), editable=False)
    readme = deck / "README.md"
    if not readme.exists():
        text = (
            "# TCAD deck workspace\n\nEdit only the declared task-private deck files "
            "through the access mode declared in domain-workspace.json. The control "
            "plane builds the canonical result.\n"
            if author
            else "# TCAD deck review workspace\n\nInspect this read-only expanded project and write only the formal review result.\n"
        )
        _write(readme, text.encode(), editable=False)
    if not author:
        _make_tree_read_only(deck)

    manifest: dict[str, Any] = {
        "protocol": "scidiscovery.tcad-deck-workspace.v2",
        "mode": mode,
        "access": (
            ("native_edit" if request.edit_protocol == "native" else "mcp_edit")
            if author
            else "read_only"
        ),
        "native_filesystem_access": (
            "declared_editable_paths"
            if author and request.edit_protocol == "native"
            else "read_only"
        ),
        "root_relative_path": "deck",
        "files_relative_path": "deck/files",
        "project_metadata_relative_path": "deck/project.json",
        "canonical_output_relative_path": "output/result.json",
        "control_builds_canonical_project": author,
    }
    if not author:
        manifest["review_template_relative_path"] = "deck/review-template.json"
    if deterministic:
        manifest.update(
            {
                "declarations_relative_path": "deck/declarations.json",
                "control_materializes_plan_bindings": True,
                "control_interprets_solver_source": False,
                "project_metadata_access": "control_read_only",
            }
        )
    if author:
        manifest["handoff_relative_path"] = "deck/handoff.json"
        manifest["gap_relative_path"] = "deck/gap.json"
        manifest["attempt_notes_relative_path"] = "deck/attempts.md"
        manifest["historical_reports_are_completion_proofs"] = False
        manifest["gap_schema_pointer"] = "/properties/payload"
    paths: dict[str, Any] = {
        "deck_workspace_path": str(deck),
        "deck_files_path": str(files_root),
        "deck_project_path": str(metadata_path),
        "deck_project_access": "control_read_only" if deterministic else manifest["access"],
        "deck_access": manifest["access"],
        "deck_mode": mode,
    }
    if author:
        paths["deck_handoff_path"] = str(handoff_path)
        paths["deck_gap_path"] = str(deck / "gap.json")
        paths["deck_preflight_attestation_path"] = str(reports / "preflight.json")
        paths["deck_initialization_attestation_path"] = str(reports / "initialization.json")
        if deterministic:
            paths.update(
                {
                    "deck_declarations_path": str(declarations_path),
                    "deck_contract_path": str(contract),
                    "deck_materialization_spec_path": str(contract / "materialization-spec.json"),
                    "deck_materialization_report_path": str(reports / "materialization.json"),
                }
            )
    else:
        paths["deck_review_template_path"] = str(deck / "review-template.json")
    return WorkspaceMaterializationResult(
        manifest_name="domain_workspace",
        manifest=manifest,
        paths=paths,
        read_paths=("deck",),
        patch_contract=({
            "target": "deck/handoff.json",
            "generated_fields": {"/verdict": "blocked when deck/gap.json exists",
                "/summary": "short reference to deck/gap.json /summary"},
            "draft_may_omit": ["/verdict", "/summary"],
            "instruction": "Only when deck/gap.json exists, the handoff file or these fields may be "
                "omitted. The finalizer fills them from the formal gap; explicit notes remain. "
                "A complete project still requires its authored handoff. Invalid existing JSON/types "
                "are errors, not omissions.",
        } if author else {
            "target": "output/result.json",
            "generated_fields": {"/handoff/verdict": "/payload/verdict",
                "/handoff/summary": "short reference to /payload/summary",
                "/payload/capability_sha256": "exact subject capability"},
            "draft_may_omit": ["/handoff", "/payload/capability_sha256"],
            "instruction": "Write the formal review summary once. The finalizer fills omitted "
                "handoff summary/verdict and subject capability before validating the sealed Schema; "
                "existing explicit handoff notes remain.",
        }),
    )


def workspace_file_policy(request: WorkspaceFileRequest) -> WorkspaceFileRule | None:
    if not request.operation_id.startswith(_AUTHOR_PREFIX):
        return None
    relative = request.relative_path
    if relative == Path("deck/project.json"):
        if (request.workspace / "deck/declarations.json").exists():
            raise WorkspaceProtocolError("deck/project.json is control-generated and read-only")
        return WorkspaceFileRule(8 * 1024 * 1024)
    if relative == Path("deck/declarations.json"):
        if not (request.workspace / relative).exists():
            raise WorkspaceProtocolError("deck/declarations.json is not declared")
        return WorkspaceFileRule(8 * 1024 * 1024)
    if relative == Path("deck/attempts.md"):
        return WorkspaceFileRule(64 * 1024)
    if relative == Path("deck/gap.json"):
        return WorkspaceFileRule(64 * 1024, removable=True)
    if relative == Path("deck/handoff.json"):
        return WorkspaceFileRule(64 * 1024)
    if len(relative.parts) >= 3 and relative.parts[:2] == ("deck", "files"):
        return WorkspaceFileRule(8 * 1024 * 1024, removable=True)
    if relative == Path("output/result.json"):
        raise WorkspaceProtocolError("the TCAD workspace finalizer owns output/result.json")
    return None


def finalize_review_workspace(request: WorkspaceFinalizationRequest) -> bytes:
    from scidiscovery.artifact_agent.service.result_materialization import finalize_result, materialize_summary_handoff
    def project(value):
        payload = value["payload"]
        project_name = next((name for name in ("project", "revised_project") if name in request.input_paths), None)
        if project_name is not None:
            source = json.loads(_input(request, project_name))
            if source.get("result_kind") == "implementation_gap":
                source = json.loads(_input(request, "execution_capability"))
            if source.get("capability_sha256") is not None:
                payload["capability_sha256"] = source["capability_sha256"]
        verdict = payload.get("verdict")
        valid_verdict = verdict if isinstance(verdict, str) and verdict in {"pass", "revise", "blocked"} else None
        materialize_summary_handoff(value, valid_verdict)
    return finalize_result(request, project)


REVIEW_FINALIZER_COMPONENT = CallableComponent("workspace_finalizer", finalize_review_workspace)


def finalize_workspace(request: WorkspaceFinalizationRequest) -> bytes:
    if not request.operation_id.startswith(_AUTHOR_PREFIX):
        raise WorkspaceProtocolError("this operation has no TCAD author finalizer")
    deck = _deck_root(request.workspace)
    if (deck / "gap.json").exists():
        try:
            gap = ImplementationGap.model_validate_json(_read(deck / "gap.json", max_bytes=64 * 1024), strict=True)
        except (ValidationError, ValueError) as error:
            raise _protocol_error("TCAD implementation gap is invalid", error, path="$.deck.gap") from error
        try:
            from scidiscovery.artifact_agent.service.result_materialization import materialize_summary_handoff
            handoff_path = deck / "handoff.json"
            handoff_value = (json.loads(_read(handoff_path, max_bytes=64 * 1024))
                if handoff_path.exists() or handoff_path.is_symlink() else {})
            value = {"payload": {"summary": gap.summary}, "handoff": handoff_value}
            materialize_summary_handoff(value, "blocked")
            handoff = RoleHandoff.model_validate_json(canonical_json(value["handoff"]), strict=True)
        except (ValidationError, ValueError) as error:
            raise _protocol_error("TCAD handoff is invalid", error, path="$.deck.handoff") from error
        try:
            inputs = {"experiment_plan": _input(request, "experiment_plan")}
            # The finalizer owns captured files; never trust an authored snapshot.
            gap = gap.model_copy(update={"attempt_files": _attempt_files(deck)})
            validate_implementation_gap(gap, inputs, handoff.model_dump(mode="json"))
        except (ValidationError, ValueError) as error:
            raise _protocol_error("TCAD implementation gap is invalid", error, path="$.deck.gap") from error
        raw = RoleResultEnvelope[Any](schema_version=1, handoff=handoff, payload=gap).canonical_json()
        if len(raw) > request.output_limit_bytes:
            raise WorkspaceProtocolError("implementation gap exceeds output limit")
        return raw
    try:
        metadata = json.loads(_read(deck / "project.json", max_bytes=8 * 1024 * 1024))
        handoff = RoleHandoff.model_validate_json(
            _read(deck / "handoff.json", max_bytes=64 * 1024), strict=True
        )
    except (ValidationError, json.JSONDecodeError) as error:
        raise _protocol_error("TCAD deck workspace is invalid", error) from error
    if not isinstance(metadata, dict) or "files" in metadata:
        raise WorkspaceProtocolError("deck/project.json must not embed source files")
    for field in ("preflight_attestation", "initialization_attestation"):
        if metadata.pop(field, None) is not None:
            raise WorkspaceProtocolError(f"{field} is control-owned and cannot be authored")
    files = _source_files(deck / "files")
    deterministic = (deck / "declarations.json").is_file()
    declarations_sha = None
    if deterministic:
        try:
            declarations = json.loads(
                _read(deck / "declarations.json", max_bytes=8 * 1024 * 1024)
            )
            declarations_sha = canonical_sha256(declarations)
            project = materialize_deck_project(
                metadata=metadata,
                declarations=declarations,
                files=files,
                experiment_plan=_input(request, "experiment_plan"),
                execution_capability=_input(request, "execution_capability"),
            )
        except ProjectMaterializationError as error:
            report_path = deck / "reports/materialization.json"
            _write(report_path, report_json(error.report), editable=False)
            raise WorkspaceProtocolError(
                "TCAD deck deterministic materialization failed",
                details=error.details,
            ) from error
        assert project.materialization_report is not None
        report_path = deck / "reports/materialization.json"
        if report_path.exists():
            report_path.chmod(0o600)
            report_path.unlink()
        _write(report_path, report_json(project.materialization_report), editable=False)
    else:
        try:
            project = DeckProjectDraft.model_validate_json(
                canonical_json({**metadata, "files": files}), strict=True
            )
        except (ValidationError, json.JSONDecodeError) as error:
            raise _protocol_error("TCAD deck workspace is invalid", error) from error
    for mode, model in (
        ("preflight", ProjectPreflightAttestation),
        ("initialization", ProjectInitializationAttestation),
    ):
        required = mode == "preflight" or (
            request.operation_id == "tcad.deck.author.initial.v1"
            or project.development_initialization_entrypoint is not None
        )
        report_path = deck / f"reports/{mode}.json"
        report = None
        problem = "missing"
        if report_path.is_file():
            try:
                report = model.model_validate_json(_read(report_path, max_bytes=16 * 1024), strict=True)
                problem = "failed" if not report.qualified else "stale"
                if (
                    report.qualified
                    and report.project_sha256 == project_debug_sha256(project)
                    and report.declarations_sha256 == declarations_sha
                ):
                    # Validate both source and project bindings before exposing the report.
                    project = DeckProjectDraft.model_validate_json(canonical_json({
                        **project.model_dump(mode="json"),
                        f"{mode}_attestation": report.model_dump(mode="json"),
                    }), strict=True)
                    continue
            except (ValidationError, json.JSONDecodeError):
                problem = "invalid"
        if request.final_submission and required:
            raise WorkspaceProtocolError(
                f"TCAD final submission requires a current qualified {mode}",
                details=({
                    "path": f"$.deck.reports.{mode}",
                    "message": f"{mode} is {problem}; run {mode} against the current source and declarations before resubmitting",
                    "type": f"tcad_{mode}_{problem}",
                },),
            )
    if request.operation_id in _REVISION_OPERATIONS:
        # Admission owns the prior result's shape. A gap has no executable
        # capability to inherit; bind its restored project to this Run's input.
        base = json.loads(_input(request, "prior_project"))
        capability_source = "prior_project"
        if base.get("result_kind") == "implementation_gap":
            capability = _capability_snapshot(_input(request, "execution_capability"))
            base = {
                "tool_profile": capability["profile_id"],
                "solver_kind": capability["solver_kind"],
                "capability_sha256": capability["capability_sha256"],
            }
            capability_source = "execution_capability"
        changed = tuple(
            name
            for name in ("tool_profile", "solver_kind", "capability_sha256")
            if base.get(name) != getattr(project, name)
        )
        if changed:
            raise WorkspaceProtocolError(
                "revised deck changed its frozen execution capability",
                details=tuple(
                    {
                        "path": f"$.deck.project.{name}",
                        "message": f"field must equal {capability_source}",
                        "type": "frozen_field_changed",
                    }
                    for name in changed
                ),
            )
    raw = RoleResultEnvelope[Any](
        schema_version=1, handoff=handoff, payload=project
    ).canonical_json()
    if len(raw) > request.output_limit_bytes:
        raise WorkspaceProtocolError("control-built deck result exceeds its byte limit")
    return raw


def snapshot_workspace(root: Path) -> tuple[WorkspaceSnapshotFile, ...]:
    deck = _deck_root(root)
    values: list[WorkspaceSnapshotFile] = []
    for name in ("gap.json", "handoff.json"):
        if (deck / name).exists():
            values.append(WorkspaceSnapshotFile(relative_path=f"deck/{name}", media_type="application/json", content=_read(deck / name, max_bytes=64 * 1024)))
    for item in _attempt_files(deck):
        values.append(WorkspaceSnapshotFile(relative_path=f"deck/{item.relative_path}", media_type="text/plain", content=item.content.encode("utf-8")))
    return tuple(values)


MATERIALIZER_COMPONENT = CallableComponent(
    "workspace_materializer", materialize_workspace
)
FILE_POLICY_COMPONENT = CallableComponent(
    "workspace_file_policy", workspace_file_policy
)
FINALIZER_COMPONENT = CallableComponent("workspace_finalizer", finalize_workspace)
SNAPSHOTTER_COMPONENT = CallableComponent(
    "workspace_snapshotter", snapshot_workspace
)


__all__ = [
    "FILE_POLICY_COMPONENT",
    "FINALIZER_COMPONENT",
    "MATERIALIZER_COMPONENT",
    "SNAPSHOTTER_COMPONENT",
]
