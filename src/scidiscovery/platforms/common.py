from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class PlatformConflictError(RuntimeError):
    """Raised when generation would overwrite user-owned content."""


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
    os.replace(temporary, path)


def commit_text_files(
    *,
    platform: str,
    project_root: Path,
    desired: Mapping[Path, str],
    exclusive: frozenset[Path],
    exclusive_markers: Mapping[Path, str] | None = None,
    dry_run: bool,
) -> GenerationReport:
    markers = exclusive_markers or {}
    changed: list[Path] = []
    unchanged: list[Path] = []
    for path, content in desired.items():
        if path.exists():
            current = path.read_text(encoding="utf-8")
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

    if not dry_run:
        for path in changed:
            atomic_write(path, desired[path])

    return GenerationReport(
        platform=platform,
        project_root=project_root,
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        dry_run=dry_run,
    )


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
        _, suffix = remainder.split(end, 1)
        result = prefix.rstrip()
        if result:
            result += "\n\n"
        result += block
        if suffix.strip():
            result += "\n\n" + suffix.lstrip()
        return result.rstrip() + "\n"
    if current.strip():
        return current.rstrip() + "\n\n" + block + "\n"
    return block + "\n"
