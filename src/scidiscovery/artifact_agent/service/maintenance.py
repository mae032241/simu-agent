"""Cross-process lock separating normal control writes from maintenance."""

from __future__ import annotations

import fcntl
import os
import shutil
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class MaintenanceBusy(RuntimeError):
    pass


class PrivatePathError(RuntimeError):
    pass


class StateMaintenanceLock:
    def __init__(self, path: Path | str, *, shared_group: bool = False) -> None:
        self.path = Path(path).expanduser().absolute()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.mode = 0o660 if shared_group else 0o600

    @contextmanager
    def shared(self) -> Iterator[None]:
        with self._acquire(fcntl.LOCK_SH):
            yield

    @contextmanager
    def exclusive(self, *, blocking: bool = True) -> Iterator[None]:
        operation = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        with self._acquire(operation):
            yield

    @contextmanager
    def _acquire(self, operation: int) -> Iterator[None]:
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, self.mode)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError("maintenance lock is not a regular file")
            os.fchmod(descriptor, self.mode)
            try:
                fcntl.flock(descriptor, operation)
            except BlockingIOError as error:
                raise MaintenanceBusy("control state is busy") from error
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)


def validate_private_directory(root: Path | str, name: str) -> Path | None:
    """Validate one real, direct-child directory without following links."""

    root_path, path = _private_child(root, name)
    root_metadata = _lstat_optional(root_path)
    if root_metadata is None:
        return None
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise PrivatePathError("private directory root is not a real directory")
    metadata = _lstat_optional(path)
    if metadata is None:
        return None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise PrivatePathError("private directory target is not a real directory")

    def fail(error: OSError) -> None:
        raise error

    for current, directories, files in os.walk(
        path, topdown=True, followlinks=False, onerror=fail
    ):
        current_path = Path(current)
        current_metadata = os.lstat(current_path)
        if stat.S_ISLNK(current_metadata.st_mode) or not stat.S_ISDIR(
            current_metadata.st_mode
        ):
            raise PrivatePathError("private directory tree changed during validation")
        for entry_name in directories:
            entry = current_path / entry_name
            entry_metadata = os.lstat(entry)
            if stat.S_ISLNK(entry_metadata.st_mode) or not stat.S_ISDIR(
                entry_metadata.st_mode
            ):
                raise PrivatePathError("private directory tree contains an unsafe entry")
        for entry_name in files:
            entry = current_path / entry_name
            entry_metadata = os.lstat(entry)
            if stat.S_ISLNK(entry_metadata.st_mode) or not stat.S_ISREG(
                entry_metadata.st_mode
            ):
                raise PrivatePathError("private directory tree contains an unsafe entry")
    return path


def remove_private_directory(root: Path | str, name: str) -> bool:
    """Remove one validated private tree, including control-sealed read-only trees."""

    path = validate_private_directory(root, name)
    if path is None:
        return False
    directories = [path]
    for current, child_names, _ in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        directories.extend(current_path / child_name for child_name in child_names)
    for directory in directories:
        metadata = os.lstat(directory)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise PrivatePathError("private directory tree changed before removal")
        os.chmod(
            directory,
            stat.S_IMODE(metadata.st_mode)
            | stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR,
        )
    shutil.rmtree(path)
    return True


def validate_private_file(root: Path | str, name: str) -> Path | None:
    """Validate one real, direct-child regular file without following links."""

    root_path, path = _private_child(root, name)
    root_metadata = _lstat_optional(root_path)
    if root_metadata is None:
        return None
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise PrivatePathError("private file root is not a real directory")
    metadata = _lstat_optional(path)
    if metadata is None:
        return None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PrivatePathError("private file target is not a regular file")
    return path


def remove_private_file(root: Path | str, name: str) -> bool:
    path = validate_private_file(root, name)
    if path is None:
        return False
    path.unlink()
    return True


def _private_child(root: Path | str, name: str) -> tuple[Path, Path]:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or Path(name).is_absolute()
        or Path(name).parts != (name,)
    ):
        raise PrivatePathError("private path name must identify one direct child")
    root_path = Path(root).expanduser().absolute()
    path = root_path / name
    if path.parent != root_path:
        raise PrivatePathError("private path escapes its root")
    return root_path, path


def _lstat_optional(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


__all__ = [
    "MaintenanceBusy",
    "PrivatePathError",
    "StateMaintenanceLock",
    "remove_private_directory",
    "remove_private_file",
    "validate_private_directory",
    "validate_private_file",
]
