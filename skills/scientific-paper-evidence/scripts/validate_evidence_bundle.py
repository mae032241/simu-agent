#!/usr/bin/env python3
"""Validate a scientific-paper-evidence package without trusting prose counts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType


def _load_core() -> ModuleType:
    candidates = [Path("/tools/figure_evidence_validation.py")]
    script = Path(__file__).resolve()
    if len(script.parents) > 3:
        candidates.append(
            script.parents[3]
            / "src/scidiscovery/artifact_agent/figure_evidence_validation.py"
        )
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            continue
        spec = importlib.util.spec_from_file_location(
            "scidiscovery_figure_evidence_validation", path
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise RuntimeError("figure evidence validation core is unavailable")


def _write_new(path: Path, content: bytes) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise RuntimeError(f"refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate CSV rows, calibration, counts, ownership, and provenance."
    )
    parser.add_argument("package", type=Path, help="evidence package directory")
    parser.add_argument(
        "--report",
        type=Path,
        help="optional new path for the canonical validation report",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        core = _load_core()
        manifest_item, manifest_content, siblings = core.load_evidence_package(
            args.package
        )
        report = core.build_figure_evidence_validation_report(
            manifest_data_item=manifest_item,
            manifest_content=manifest_content,
            sibling_files=siblings,
        )
        content = core.canonical_json(report)
        if args.report is not None:
            _write_new(args.report, content)
    except (OSError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {"error": str(error), "integrity_status": "invalid"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(content.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
