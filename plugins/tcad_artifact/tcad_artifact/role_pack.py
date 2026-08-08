"""Installed role-resource provider for the TCAD domain pack."""

from __future__ import annotations

from pathlib import Path


def role_directory() -> Path:
    directory = Path(__file__).with_name("roles")
    if not directory.is_dir():
        raise FileNotFoundError("installed TCAD role resources are unavailable")
    return directory


__all__ = ["role_directory"]
