"""Load the compact scheduler prompt and its separately installed reading guides."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import re


def load_scheduler_prompt() -> str:
    path = _scheduler_prompt_path()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"scheduler prompt is empty: {path}")
    return text.strip() + "\n"


def load_scheduler_guides() -> dict[str, str]:
    directory = _scheduler_prompt_path().parent / "scheduler"
    # The prompt's reading index is the sole file list; missing wheel data must
    # fail installation instead of leaving dangling instructions in AGENTS.md.
    return {
        name: (directory / name).read_text(encoding="utf-8")
        for name in re.findall(r"^- .*: ([\w-]+\.md)\.", load_scheduler_prompt(), re.MULTILINE)
    }


def _scheduler_prompt_path() -> Path:
    source = Path(__file__).resolve().parents[3] / "roles" / "scheduler.md"
    if source.is_file():
        return source
    for ancestor in Path(__file__).resolve().parents:
        installed = ancestor / "share" / "scidiscovery" / "roles" / "scheduler.md"
        if installed.is_file():
            return installed
    try:
        package = distribution("scidiscovery")
    except PackageNotFoundError as error:
        raise FileNotFoundError("installed scheduler prompt is unavailable") from error
    for entry in package.files or ():
        candidate = package.locate_file(entry)
        if candidate.name == "scheduler.md" and candidate.parent.name == "roles":
            return candidate
    raise FileNotFoundError("installed scheduler prompt is unavailable")


__all__ = ["load_scheduler_prompt", "load_scheduler_guides"]
