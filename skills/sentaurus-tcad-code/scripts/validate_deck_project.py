#!/usr/bin/env python3
"""Static direct-solver contract checks for a textual DeckProject JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import PurePosixPath
from typing import Any


WORKBENCH_TOKEN = re.compile(r"@[A-Za-z_][A-Za-z0-9_.:-]*@")
SHELL_MARKERS = (
    "#!/bin/sh",
    "#!/usr/bin/env sh",
    "#!/bin/bash",
    "#!/usr/bin/env bash",
    "set -e",
    "set -u",
    "nohup ",
)


def _safe_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def validate(project: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(level: str, code: str, message: str) -> None:
        findings.append({"level": level, "code": code, "message": message})

    if not isinstance(project, dict):
        return [{"level": "error", "code": "project.type", "message": "project must be a JSON object"}]

    profile = project.get("tool_profile")
    kind = project.get("solver_kind")
    entrypoint = project.get("entrypoint")
    files = project.get("files")
    arguments = project.get("arguments", [])
    outputs = project.get("expected_outputs", [])
    runtime_assertions = project.get("runtime_assertions", [])
    realization_manifest = project.get("realization_manifest", [])

    if not isinstance(profile, str) or not profile:
        add("error", "profile.missing", "tool_profile must be a nonempty string")
    if kind not in {"sprocess", "sdevice", "shell_runner", "deterministic_tool"}:
        add("error", "solver_kind.invalid", "solver_kind must be an explicit supported capability")

    if not _safe_path(entrypoint):
        add("error", "entrypoint.path", "entrypoint must be a safe project-relative path")

    file_map: dict[str, str] = {}
    if not isinstance(files, list):
        add("error", "files.type", "files must be an array")
    else:
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                add("error", "files.item", f"files[{index}] must be an object")
                continue
            path = item.get("relative_path")
            content = item.get("content")
            if not _safe_path(path):
                add("error", "files.path", f"files[{index}] has an unsafe relative_path")
                continue
            if not isinstance(content, str):
                add("error", "files.content", f"{path} content must be UTF-8 text")
                continue
            if path in file_map:
                add("error", "files.duplicate", f"duplicate file path: {path}")
            file_map[path] = content

    entry_content = file_map.get(entrypoint) if isinstance(entrypoint, str) else None
    if isinstance(entrypoint, str) and entry_content is None:
        add("error", "entrypoint.missing", "entrypoint is absent from files")

    if kind in {"sprocess", "sdevice"} and isinstance(entrypoint, str):
        if PurePosixPath(entrypoint).suffix.lower() != ".cmd":
            add("error", "entrypoint.kind", f"direct {kind} entrypoint must be a .cmd solver deck")
        if entry_content is not None and any(marker in entry_content for marker in SHELL_MARKERS):
            add("error", "entrypoint.shell", f"direct {kind} entrypoint contains shell-runner syntax")
        if isinstance(arguments, list) and any(str(value) in {"submit", "worker", "status"} for value in arguments):
            add("error", "arguments.scheduler", f"direct {kind} arguments contain job-scheduler commands")
        if runtime_assertions:
            add(
                "error",
                "runtime_assertions.post_execution",
                f"direct {kind} deck must leave runtime_assertions empty",
            )
        if isinstance(realization_manifest, list):
            for index, item in enumerate(realization_manifest):
                if isinstance(item, dict) and item.get("implementation_status") == "unsupported":
                    add(
                        "error",
                        "manifest.unsupported",
                        f"realization_manifest[{index}] is not an implemented deck requirement",
                    )

    if not isinstance(arguments, list) or not all(isinstance(value, str) for value in arguments):
        add("error", "arguments.type", "arguments must be an array of strings")

    for relative_path, content in file_map.items():
        tokens = sorted(set(WORKBENCH_TOKEN.findall(content)))
        if tokens:
            add(
                "error",
                "files.workbench_tokens",
                f"{relative_path} contains unresolved standalone tokens: "
                + ", ".join(tokens),
            )

    if entry_content is not None:
        if kind == "sprocess" and re.search(r"(^|[;\n])\s*(?:exec\s+)?sprocess\b", entry_content, re.I):
            add("error", "entrypoint.nested_solver", "SProcess entrypoint launches another sprocess process")
        if kind == "sdevice" and re.search(r"(^|[;\n])\s*(?:exec\s+)?sdevice\b", entry_content, re.I):
            add("error", "entrypoint.nested_solver", "SDevice entrypoint launches another sdevice process")

    input_paths = set(file_map)
    output_names: set[str] = set()
    output_paths: set[str] = set()
    if not isinstance(outputs, list):
        add("error", "outputs.type", "expected_outputs must be an array")
    else:
        native_suffixes = {".tdr", ".plx", ".plt", ".log"}
        for index, item in enumerate(outputs):
            if not isinstance(item, dict):
                add("error", "outputs.item", f"expected_outputs[{index}] must be an object")
                continue
            name = item.get("name")
            path = item.get("relative_path")
            if not isinstance(name, str) or not name:
                add("error", "outputs.name", f"expected_outputs[{index}] has no valid name")
            elif name in output_names:
                add("error", "outputs.duplicate_name", f"duplicate output name: {name}")
            else:
                output_names.add(name)
            if not _safe_path(path):
                add("error", "outputs.path", f"expected_outputs[{index}] has an unsafe relative_path")
            elif path in output_paths:
                add("error", "outputs.duplicate_path", f"duplicate output path: {path}")
            else:
                output_paths.add(path)
            if path in input_paths:
                add("error", "outputs.overwrite_input", f"output overwrites project input: {path}")
            if (
                kind in {"sprocess", "sdevice"}
                and isinstance(path, str)
                and PurePosixPath(path).suffix.lower() not in native_suffixes
            ):
                add(
                    "error",
                    "outputs.post_execution",
                    f"direct {kind} output is not raw solver-native TDR/PLX/PLT/log: {path}",
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="DeckProject JSON path, or - for stdin")
    args = parser.parse_args()
    try:
        if args.project == "-":
            raw = sys.stdin.read()
        else:
            with open(args.project, encoding="utf-8") as source:
                raw = source.read()
        project = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(json.dumps({"valid": False, "findings": [{"level": "error", "code": "input.read", "message": str(error)}]}, ensure_ascii=False))
        return 2
    findings = validate(project)
    valid = not any(item["level"] == "error" for item in findings)
    print(json.dumps({"valid": valid, "findings": findings}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
