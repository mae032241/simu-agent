"""Small server-side file editor for the optional hardened Run backend."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...operations.workspace import WorkspaceFileRequest, operation_workspace_hooks
from ..schema.common import canonical_json
from .local_workspace import (
    OpenWorkspace,
    WorkspaceError,
    move_control_workspace_file,
    read_control_workspace_file,
    remove_control_workspace_file,
    write_control_workspace_file,
)


_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")
_UNIFIED_HUNK = re.compile(
    r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@(?:.*)$"
)


@dataclass(slots=True)
class _Upload:
    path: Path
    expected_bytes: int | None
    operation: str
    content: bytearray


class HardenedFileEditor:
    """Edit only paths admitted by the compiled Operation workspace contract."""

    def __init__(self, compiled: Any, workspace: OpenWorkspace) -> None:
        self.compiled = compiled
        self.workspace = workspace
        self._upload: _Upload | None = None

    def begin(
        self, relative_path: str, expected_bytes: int | None, operation: str
    ) -> dict[str, Any]:
        if self._upload is not None:
            raise WorkspaceError("a file upload is already active")
        path, limit, _ = self._admit(relative_path)
        if expected_bytes is not None and expected_bytes > limit:
            raise WorkspaceError("declared upload exceeds the file limit")
        exists = (self.workspace.root / path).exists()
        if operation == "create" and exists:
            raise WorkspaceError("create cannot replace an existing file")
        if operation == "patch" and not exists:
            raise WorkspaceError("patch requires an existing file")
        self._upload = _Upload(path, expected_bytes, operation, bytearray())
        return {"state": "started", "relative_path": path.as_posix()}

    def chunk(self, content: str, encoding: str) -> dict[str, Any]:
        upload = self._require_upload()
        try:
            raw = content.encode("utf-8") if encoding == "utf8" else base64.b64decode(
                content, validate=True
            )
        except (UnicodeEncodeError, binascii.Error) as error:
            raise WorkspaceError("file chunk encoding is invalid") from error
        _, limit, _ = self._admit(upload.path.as_posix())
        if len(upload.content) + len(raw) > limit:
            raise WorkspaceError("file upload exceeds the file limit")
        upload.content.extend(raw)
        return {"state": "receiving", "received_bytes": len(upload.content)}

    def commit(self) -> dict[str, Any]:
        upload = self._require_upload()
        content = bytes(upload.content)
        if upload.expected_bytes is not None and len(content) != upload.expected_bytes:
            raise WorkspaceError("file upload byte count differs")
        if upload.operation == "patch":
            raise WorkspaceError(
                "chunked patch is not enabled; use the declared JSON patch tool"
            )
        write_control_workspace_file(
            self.workspace.root,
            upload.path,
            content,
            replace=False,
            mode=0o600,
            create_parents=True,
        )
        self._upload = None
        return {
            "state": "committed",
            "relative_path": upload.path.as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def json_patch(
        self,
        relative_path: str,
        operations: tuple[Any, ...],
        expected_digest: str | None,
    ) -> dict[str, Any]:
        path, limit, _ = self._admit(relative_path)
        raw = read_control_workspace_file(self.workspace.root, path, max_bytes=limit)
        digest = hashlib.sha256(raw).hexdigest()
        if expected_digest is not None and digest != expected_digest:
            raise WorkspaceError("JSON patch digest does not match")
        try:
            value = json.loads(raw)
            result = _apply_json_patch(
                value, tuple(item.model_dump(exclude_unset=True) for item in operations)
            )
            content = json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8") + b"\n"
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise WorkspaceError("JSON patch is invalid") from error
        if len(content) > limit:
            raise WorkspaceError("patched JSON exceeds the file limit")
        write_control_workspace_file(
            self.workspace.root, path, content, replace=True, mode=0o600
        )
        return {
            "state": "patched",
            "relative_path": path.as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def text_patch(self, relative_path: str, patch: str) -> dict[str, Any]:
        path, limit, _ = self._admit(relative_path)
        raw = read_control_workspace_file(self.workspace.root, path, max_bytes=limit)
        try:
            original = raw.decode("utf-8")
            revised = _apply_text_patch(original, patch, path.as_posix()).encode(
                "utf-8"
            )
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkspaceError("text patch is invalid or stale") from error
        if len(revised) > limit:
            raise WorkspaceError("patched text exceeds the file limit")
        write_control_workspace_file(
            self.workspace.root, path, revised, replace=True, mode=0o600
        )
        return {
            "state": "patched",
            "relative_path": path.as_posix(),
            "sha256": hashlib.sha256(revised).hexdigest(),
        }

    def delete(self, relative_path: str) -> dict[str, Any]:
        path, _, removable = self._admit(relative_path)
        if not removable:
            raise WorkspaceError("workspace contract forbids removing this file")
        remove_control_workspace_file(self.workspace.root, path)
        return {"state": "deleted", "relative_path": path.as_posix()}

    def move(self, source: str, destination: str) -> dict[str, Any]:
        source_path, _, removable = self._admit(source)
        destination_path, _, _ = self._admit(destination)
        if not removable:
            raise WorkspaceError("workspace contract forbids moving this file")
        move_control_workspace_file(
            self.workspace.root, source_path, destination_path
        )
        return {
            "state": "moved",
            "source_relative_path": source_path.as_posix(),
            "destination_relative_path": destination_path.as_posix(),
        }

    def _require_upload(self) -> _Upload:
        if self._upload is None:
            raise WorkspaceError("file upload has not been started")
        return self._upload

    def _admit(self, value: str) -> tuple[Path, int, bool]:
        path = Path(value)
        if (
            path.is_absolute()
            or not path.parts
            or len(path.parts) > 16
            or "\\" in value
            or any(_PART.fullmatch(part) is None for part in path.parts)
        ):
            raise WorkspaceError("worker file path is unsafe")
        policy = operation_workspace_hooks(self.compiled).get(
            "workspace_file_policy"
        )
        if policy is not None:
            rule = policy(
                WorkspaceFileRequest(
                    operation_id=self.compiled.spec.operation_id,
                    workspace=self.workspace.root,
                    relative_path=path,
                )
            )
            if rule is not None:
                return path, rule.max_bytes, rule.removable
        assert self.compiled.spec.limits is not None
        if path == Path("output/result.json"):
            return path, self.compiled.spec.limits.max_output_bytes, False
        if len(path.parts) >= 3 and path.parts[:2] == ("output", "collections"):
            return path, self.compiled.spec.limits.max_output_bytes, True
        raise WorkspaceError("worker file path is not declared by this Operation")


def _apply_json_patch(value: Any, operations: tuple[dict[str, Any], ...]) -> Any:
    result = json.loads(canonical_json(value))
    for operation in operations:
        op = operation["op"]
        tokens = _pointer_tokens(operation["path"])
        parent = result
        for token in tokens[:-1]:
            parent = _pointer_get(parent, token)
        leaf = tokens[-1]
        if op == "test":
            if canonical_json(_pointer_get(parent, leaf)) != canonical_json(
                operation["value"]
            ):
                raise ValueError("JSON patch test did not match")
        elif isinstance(parent, dict):
            if op in {"replace", "remove"} and leaf not in parent:
                raise ValueError("JSON patch path does not exist")
            if op == "remove":
                del parent[leaf]
            else:
                parent[leaf] = operation["value"]
        elif isinstance(parent, list):
            index = len(parent) if op == "add" and leaf == "-" else int(leaf)
            if op == "add":
                parent.insert(index, operation["value"])
            elif op == "replace":
                parent[index] = operation["value"]
            else:
                del parent[index]
        else:
            raise ValueError("JSON patch parent is scalar")
    return result


def _apply_text_patch(original: str, patch: str, relative_path: str) -> str:
    """Apply one exact-context Codex or unified patch without fuzzy guessing."""

    if not patch or len(patch.encode("utf-8")) > 16 * 1024 * 1024:
        raise ValueError("text patch exceeds its byte limit")
    lines = patch.splitlines(keepends=True)
    if patch.startswith("*** Begin Patch"):
        if (
            len(lines) < 5
            or lines[0].rstrip("\r\n") != "*** Begin Patch"
            or lines[-1].rstrip("\r\n") != "*** End Patch"
            or lines[1].rstrip("\r\n") != f"*** Update File: {relative_path}"
        ):
            raise ValueError("Codex patch envelope or target is invalid")
        body = lines[2:-1]
        header = lambda value: value.startswith("@@")
    else:
        body = [line for line in lines if not line.startswith(("--- ", "+++ "))]
        header = lambda value: _UNIFIED_HUNK.match(value.rstrip("\r\n")) is not None
    hunks: list[list[str]] = []
    cursor = 0
    while cursor < len(body):
        if not header(body[cursor]):
            raise ValueError("text patch requires hunk headers")
        cursor += 1
        changes: list[str] = []
        while cursor < len(body) and not header(body[cursor]):
            line = body[cursor]
            if not line or line[0] not in {" ", "+", "-"}:
                raise ValueError("text patch change line is invalid")
            changes.append(line)
            cursor += 1
        if not changes or not any(line[0] in {" ", "-"} for line in changes):
            raise ValueError("text patch hunk has no exact old context")
        hunks.append(changes)
    if not hunks:
        raise ValueError("text patch contains no hunks")
    source = original.splitlines(keepends=True)
    output: list[str] = []
    source_cursor = 0
    for changes in hunks:
        old = [line[1:] for line in changes if line[0] in {" ", "-"}]
        candidates = [
            index
            for index in range(source_cursor, len(source) - len(old) + 1)
            if source[index : index + len(old)] == old
        ]
        if len(candidates) != 1:
            raise ValueError("text patch context is missing or ambiguous")
        start = candidates[0]
        output.extend(source[source_cursor:start])
        source_cursor = start
        for change in changes:
            payload = change[1:]
            if change[0] in {" ", "-"}:
                if source_cursor >= len(source) or source[source_cursor] != payload:
                    raise ValueError("text patch context changed")
                source_cursor += 1
            if change[0] in {" ", "+"}:
                output.append(payload)
    output.extend(source[source_cursor:])
    return "".join(output)


def _pointer_tokens(path: str) -> tuple[str, ...]:
    if not path.startswith("/") or path == "/":
        raise ValueError("JSON patch path must be non-root")
    values = []
    for raw in path[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if "~" in raw.replace("~0", "").replace("~1", ""):
            raise ValueError("JSON patch escape is invalid")
        values.append(token)
    return tuple(values)


def _pointer_get(parent: Any, token: str) -> Any:
    if isinstance(parent, dict):
        return parent[token]
    if isinstance(parent, list):
        return parent[int(token)]
    raise ValueError("JSON patch parent is scalar")


__all__ = ["HardenedFileEditor"]
