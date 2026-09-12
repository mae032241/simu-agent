"""Installed role-resource provider for the TCAD domain pack."""

from __future__ import annotations

from pathlib import Path

from scidiscovery.operation_declaration import RESEARCH_WORK_CONTEXT


def role_prompt(role: str) -> str:
    return RESEARCH_WORK_CONTEXT + (role_directory() / f"tcad_deck_{role}.md").read_text(encoding="utf-8")


def role_directory() -> Path:
    directory = Path(__file__).with_name("roles")
    if not directory.is_dir():
        raise FileNotFoundError("installed TCAD role resources are unavailable")
    return directory


__all__ = ["role_directory", "role_prompt"]
