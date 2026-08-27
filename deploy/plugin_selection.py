#!/usr/bin/env python3
"""Validate and resolve the generic local plugin selection."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 deployment path
    import tomli as tomllib


PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass(frozen=True)
class Plugin:
    plugin_id: str
    distribution: str
    dependencies: tuple[str, ...]


def resolve_plugins(source_root: Path | str, specification: str) -> tuple[Plugin, ...]:
    root = Path(source_root).expanduser().resolve(strict=True)
    plugins_root = root / "plugins"
    available: dict[str, Plugin] = {}
    distributions: dict[str, str] = {}
    for directory in sorted(plugins_root.iterdir()):
        metadata_path = directory / "pyproject.toml"
        if (
            not directory.is_dir()
            or directory.is_symlink()
            or not metadata_path.is_file()
        ):
            continue
        plugin = _read_plugin(directory.name, metadata_path)
        normalized_distribution = _normalize_distribution(plugin.distribution)
        if normalized_distribution in distributions:
            raise ValueError(
                "duplicate local plugin distribution: " + plugin.distribution
            )
        distributions[normalized_distribution] = plugin.plugin_id
        available[plugin.plugin_id] = plugin

    requested = tuple(item.strip() for item in specification.split(","))
    if not requested or any(not item for item in requested):
        raise ValueError("SCID_PLUGINS must be a comma-separated non-empty plugin list")
    if len(set(requested)) != len(requested):
        raise ValueError("SCID_PLUGINS contains a duplicate plugin")
    for plugin_id in requested:
        if not PLUGIN_ID.fullmatch(plugin_id):
            raise ValueError(f"invalid plugin identifier: {plugin_id}")
        if plugin_id not in available:
            raise ValueError(f"unknown local plugin: {plugin_id}")

    selected = tuple(available[plugin_id] for plugin_id in requested)
    selected_ids = {item.plugin_id for item in selected}
    for plugin in selected:
        for dependency in plugin.dependencies:
            dependency_id = distributions.get(_normalize_distribution(dependency))
            if dependency_id is not None and dependency_id not in selected_ids:
                raise ValueError(
                    f"plugin {plugin.plugin_id} requires local plugin {dependency_id}"
                )
    return selected


def _read_plugin(plugin_id: str, path: Path) -> Plugin:
    if not PLUGIN_ID.fullmatch(plugin_id):
        raise ValueError(f"invalid local plugin directory name: {plugin_id}")
    value = tomllib.loads(path.read_text(encoding="utf-8"))
    project = value.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"plugin has no [project] metadata: {plugin_id}")
    distribution = project.get("name")
    dependencies = project.get("dependencies", [])
    if not isinstance(distribution, str) or not distribution.strip():
        raise ValueError(f"plugin has no distribution name: {plugin_id}")
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        raise ValueError(f"plugin dependencies are invalid: {plugin_id}")
    names = []
    for dependency in dependencies:
        match = REQUIREMENT_NAME.match(dependency)
        if match is None:
            raise ValueError(f"plugin dependency is invalid: {dependency}")
        names.append(match.group(1))
    return Plugin(plugin_id, distribution.strip(), tuple(names))


def _normalize_distribution(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--plugins", required=True)
    parser.add_argument("--field", choices=("id", "distribution"), default="id")
    arguments = parser.parse_args(argv)
    try:
        plugins = resolve_plugins(arguments.source_root, arguments.plugins)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        parser.error(str(error))
    for plugin in plugins:
        print(plugin.plugin_id if arguments.field == "id" else plugin.distribution)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
