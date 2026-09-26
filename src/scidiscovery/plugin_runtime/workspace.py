"""Bounded files under a control-supplied task root; no artifact/Run authority."""
from __future__ import annotations
import json
import mimetypes
import os
import re
import stat
import uuid
from pathlib import Path

__all__ = ["WorkspaceError", "WorkspaceOutputError", "read_control_workspace_file",
    "write_control_workspace_file", "remove_control_workspace_file", "move_control_workspace_file",
    "validate_publication_content", "media_type_for_path"]

_MACHINE_PATH = re.compile(
    rb"(?<![A-Za-z0-9_])(?:/(?:home|tmp|var|etc|Users)/[^\s\"']+|[A-Za-z]:\\(?:Users|Temp)\\[^\s\"']+)"
)
_SECRET = re.compile(
    rb"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_-]{20,}\b|(?:api[_-]?key|password|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,})",
    re.IGNORECASE,
)


class WorkspaceError(RuntimeError):
    pass

class WorkspaceOutputError(WorkspaceError):
    """Candidate file content/shape can be corrected by the worker."""

def write_control_workspace_file(
    workspace: Path,
    relative_path: Path,
    content: bytes,
    *,
    replace: bool,
    mode: int,
    create_parents: bool = False,
) -> Path:
    """Write through non-symlink directory handles below one workspace root."""

    if type(content) is not bytes:
        raise TypeError("workspace content must be bytes")
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise WorkspaceError("control workspace path is invalid")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    temporary = f".{relative_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(workspace, directory_flags)
        descriptors.append(descriptor)
        for part in relative_path.parts[:-1]:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create_parents:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                child = os.open(part, directory_flags, dir_fd=descriptor)
            descriptor = child
            descriptors.append(descriptor)
        parent = descriptors[-1]
        destination = relative_path.name
        try:
            metadata = os.stat(destination, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            metadata = None
        if metadata is not None and not stat.S_ISREG(metadata.st_mode):
            raise WorkspaceError("control workspace destination is invalid")
        if metadata is not None and not replace:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            existing = os.open(destination, flags, dir_fd=parent)
            try:
                if os.read(existing, max(1, len(content)) + 1) != content:
                    raise WorkspaceError("control workspace file changed")
            finally:
                os.close(existing)
            return workspace / relative_path
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        output = os.open(temporary, flags, mode, dir_fd=parent)
        try:
            with os.fdopen(output, "wb", closefd=False) as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.fchmod(output, mode)
        finally:
            os.close(output)
        os.replace(temporary, destination, src_dir_fd=parent, dst_dir_fd=parent)
        os.chmod(destination, mode, dir_fd=parent, follow_symlinks=False)
        return workspace / relative_path
    except OSError as error:
        raise WorkspaceError("control workspace path is not a real directory tree") from error
    finally:
        if descriptors:
            try:
                os.unlink(temporary, dir_fd=descriptors[-1])
            except FileNotFoundError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)

def read_control_workspace_file(
    workspace: Path, relative_path: Path, *, max_bytes: int
) -> bytes:
    """Read one regular file without following any path-component symlink."""

    descriptors, parent = _open_workspace_parent(workspace, relative_path)
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(relative_path.name, flags, dir_fd=parent)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > max_bytes:
                raise WorkspaceError("workspace file exceeds its byte limit")
            value = os.read(descriptor, max_bytes + 1)
        finally:
            os.close(descriptor)
        if len(value) > max_bytes:
            raise WorkspaceError("workspace file exceeds its byte limit")
        return value
    except OSError as error:
        raise WorkspaceError("workspace file is unavailable") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)

def remove_control_workspace_file(workspace: Path, relative_path: Path) -> None:
    """Remove one regular file through its verified parent directory handle."""

    descriptors, parent = _open_workspace_parent(workspace, relative_path)
    try:
        metadata = os.stat(relative_path.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            raise WorkspaceError("workspace file is not regular")
        os.unlink(relative_path.name, dir_fd=parent)
    except OSError as error:
        raise WorkspaceError("workspace file cannot be removed") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)

def move_control_workspace_file(
    workspace: Path, source: Path, destination: Path
) -> None:
    """Move one regular file between two verified workspace parents."""

    source_descriptors, source_parent = _open_workspace_parent(workspace, source)
    destination_descriptors: list[int] = []
    try:
        destination_descriptors, destination_parent = _open_workspace_parent(
            workspace, destination
        )
        source_metadata = os.stat(
            source.name, dir_fd=source_parent, follow_symlinks=False
        )
        if not stat.S_ISREG(source_metadata.st_mode):
            raise WorkspaceError("workspace source is not regular")
        try:
            os.stat(destination.name, dir_fd=destination_parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise WorkspaceError("workspace destination already exists")
        os.rename(
            source.name,
            destination.name,
            src_dir_fd=source_parent,
            dst_dir_fd=destination_parent,
        )
    except OSError as error:
        raise WorkspaceError("workspace file cannot be moved") from error
    finally:
        for descriptor in reversed(destination_descriptors):
            os.close(descriptor)
        for descriptor in reversed(source_descriptors):
            os.close(descriptor)

def _open_workspace_parent(
    workspace: Path, relative_path: Path
) -> tuple[list[int], int]:
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise WorkspaceError("workspace path is invalid")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    try:
        descriptor = os.open(workspace, flags)
        descriptors.append(descriptor)
        for part in relative_path.parts[:-1]:
            descriptor = os.open(part, flags, dir_fd=descriptor)
            descriptors.append(descriptor)
        return descriptors, descriptors[-1]
    except OSError as error:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise WorkspaceError("workspace path is not a real directory tree") from error

def validate_publication_content(
    relative_path: str, content: bytes, media_type: str
) -> None:
    if media_type == "application/octet-stream":
        raise WorkspaceOutputError(f"undeclared binary output is forbidden: {relative_path}")
    if _SECRET.search(content):
        raise WorkspaceOutputError(f"output contains an apparent secret: {relative_path}")
    if _MACHINE_PATH.search(content):
        raise WorkspaceOutputError(f"output contains a host-specific path: {relative_path}")
    if media_type.startswith("text/") or media_type in {
        "application/json",
        "application/xml",
        "application/javascript",
    }:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise WorkspaceOutputError(f"text output is not UTF-8: {relative_path}") from error

def media_type_for_path(relative_path: str) -> str:
    if relative_path == "result.json" or relative_path.endswith(".json"):
        return "application/json"
    if relative_path.endswith((".py", ".log")):
        return "text/plain"
    return mimetypes.guess_type(relative_path)[0] or "application/octet-stream"


def atomic_json(path: Path, value: dict, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("engineering record path must not be a symlink")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, *, max_bytes: int = 128 * 1024) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("engineering record is not a regular file")
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("engineering record exceeds its byte bound")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("engineering record must be an object")
    return value


__all__ += ["atomic_json", "read_json"]
