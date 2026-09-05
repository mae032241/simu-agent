"""Load the one static scheduler prompt without discovering scientific roles."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path


def load_scheduler_prompt() -> str:
    path = _scheduler_prompt_path()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"scheduler prompt is empty: {path}")
    return text.strip() + "\n"


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


__all__ = ["load_scheduler_prompt"]
