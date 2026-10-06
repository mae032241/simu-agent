from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class PlatformConflictError(RuntimeError):
    """Raised when generation would overwrite user-owned content."""


class PlatformRollbackError(RuntimeError):
    """Keep the installation failure and every failed recovery visible."""

    def __init__(self, original_error: BaseException,
                 rollback_errors: tuple[tuple[Path, str, BaseException], ...]):
        self.original_error = original_error
        self.rollback_errors = rollback_errors
        failures = "; ".join(
            f"{operation} {path}: {type(error).__name__}: {error}"
            for path, operation, error in rollback_errors
        )
        super().__init__(
            f"platform installation failed: {type(original_error).__name__}: "
            f"{original_error}; rollback incomplete: {failures}"
        )


@dataclass(frozen=True)
class GenerationReport:
    platform: str
    project_root: Path
    changed: tuple[Path, ...]
    unchanged: tuple[Path, ...]
    dry_run: bool


def absolute_project_root(project_root: Path | str) -> Path:
    return Path(project_root).expanduser().resolve()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.scidiscovery.tmp")
    temporary.write_text(content, encoding="utf-8")
    if path.exists():
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
    os.replace(temporary, path)


def commit_text_files(
    *,
    platform: str,
    project_root: Path,
    desired: Mapping[Path, str],
    exclusive: frozenset[Path],
    exclusive_markers: Mapping[Path, str] | None = None,
    obsolete: frozenset[Path] = frozenset(),
    obsolete_markers: Mapping[Path, str] | None = None,
    dry_run: bool,
) -> GenerationReport:
    markers = exclusive_markers or {}
    removal_markers = obsolete_markers or {}
    changed: list[Path] = []
    unchanged: list[Path] = []
    if set(desired).intersection(obsolete):
        raise ValueError("desired and obsolete platform files must be disjoint")
    for path, content in desired.items():
        if path.is_symlink():
            raise PlatformConflictError(f"refusing to replace symlink: {path}")
        if path.exists():
            with path.open(encoding="utf-8", newline="") as stream:
                current = stream.read()
            if current == content:
                unchanged.append(path)
                continue
            if path in exclusive:
                marker = markers.get(path)
                if not marker or marker not in current:
                    raise PlatformConflictError(
                        f"refusing to replace user-owned file: {path}"
                    )
        changed.append(path)

    for path in sorted(obsolete):
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            raise PlatformConflictError(
                f"refusing to remove unsafe managed file: {path}"
            )
        marker = removal_markers.get(path)
        if not marker or marker not in path.read_text(encoding="utf-8"):
            raise PlatformConflictError(
                f"refusing to remove user-owned file: {path}"
            )
        changed.append(path)

    if not dry_run:
        previous = {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
                    if path.exists() else None for path in changed}
        written: list[Path] = []
        try:
            for path in changed:
                written.append(path)
                if path in desired:
                    atomic_write(path, desired[path])
                else:
                    path.unlink()
        except BaseException as original_error:
            rollback_errors: list[tuple[Path, str, BaseException]] = []
            for path in reversed(written):
                saved = previous[path]
                temporary = path.with_name(f".{path.name}.scidiscovery.tmp")
                try:
                    current = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) \
                        if path.exists() else None
                    if current != saved:
                        if saved is None:
                            path.unlink(missing_ok=True)
                        else:
                            temporary.write_bytes(saved[0])
                            temporary.chmod(saved[1])
                            os.replace(temporary, path)
                except BaseException as error:
                    rollback_errors.append((path, "restore", error))
                try:
                    if temporary.exists() or temporary.is_symlink():
                        temporary.unlink()
                except BaseException as error:
                    rollback_errors.append((temporary, "cleanup", error))
            if rollback_errors:
                raise PlatformRollbackError(original_error, tuple(rollback_errors)) from original_error
            raise

    return GenerationReport(
        platform=platform,
        project_root=project_root,
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        dry_run=dry_run,
    )


def obsolete_managed_files(
    directory: Path,
    *,
    desired: frozenset[Path],
    pattern: str,
    marker: str,
) -> tuple[frozenset[Path], dict[Path, str]]:
    """Find retired generated files without claiming user-owned siblings."""

    obsolete: set[Path] = set()
    markers: dict[Path, str] = {}
    if not directory.exists():
        return frozenset(), markers
    if directory.is_symlink() or not directory.is_dir():
        raise PlatformConflictError(
            f"managed agent path must be a real directory: {directory}"
        )
    for path in directory.glob(pattern):
        if path in desired:
            continue
        if path.is_symlink() or not path.is_file():
            raise PlatformConflictError(f"managed agent file is unsafe: {path}")
        if marker not in path.read_text(encoding="utf-8"):
            continue
        obsolete.add(path)
        markers[path] = marker
    return frozenset(obsolete), markers


def managed_block(
    current: str,
    *,
    begin: str,
    end: str,
    body: str,
) -> str:
    begin_count = current.count(begin)
    end_count = current.count(end)
    if begin_count != end_count or begin_count > 1:
        raise PlatformConflictError("managed block markers are malformed")
    block = f"{begin}\n{body.rstrip()}\n{end}"
    if begin_count == 1:
        prefix, remainder = current.split(begin, 1)
        if end not in remainder:
            raise PlatformConflictError("managed block markers are malformed")
        _, suffix = remainder.split(end, 1)
        return prefix + block + suffix
    if current:
        return current + ("\n" if current.endswith("\n") else "\n\n") + block + "\n"
    return block + "\n"
