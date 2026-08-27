"""Build and verify the exact Python runtime used by installed services."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence


TRACKED_DISTRIBUTIONS = ("pydantic", "PyYAML", "setuptools")


def current_runtime_identity() -> dict[str, object]:
    distributions: dict[str, str] = {}
    for name in TRACKED_DISTRIBUTIONS:
        try:
            distributions[name] = version(name)
        except PackageNotFoundError as error:
            raise RuntimeError(f"required runtime distribution is missing: {name}") from error
    return {
        "schema_version": 1,
        "python_executable": str(Path(sys.executable).resolve(strict=True)),
        "python_version": platform.python_version(),
        "distributions": distributions,
    }


def write_runtime_identity(path: Path | str) -> None:
    target = Path(path).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical(current_runtime_identity())
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    temporary.write_bytes(raw)
    os.replace(temporary, target)


def verify_runtime_identity(path: Path | str) -> None:
    target = Path(path).expanduser().absolute()
    value = json.loads(target.read_bytes())
    expected_fields = {
        "schema_version",
        "python_executable",
        "python_version",
        "distributions",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise RuntimeError("runtime identity manifest has unexpected fields")
    if value.get("schema_version") != 1 or _canonical(value) != target.read_bytes():
        raise RuntimeError("runtime identity manifest is invalid or non-canonical")
    current = current_runtime_identity()
    if value != current:
        raise RuntimeError(
            "Python runtime identity drifted; rebuild and reinstall the release site"
        )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("write", "verify"))
    parser.add_argument("--manifest", required=True)
    arguments = parser.parse_args(argv)
    if arguments.operation == "write":
        write_runtime_identity(arguments.manifest)
    else:
        verify_runtime_identity(arguments.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TRACKED_DISTRIBUTIONS",
    "current_runtime_identity",
    "main",
    "verify_runtime_identity",
    "write_runtime_identity",
]
