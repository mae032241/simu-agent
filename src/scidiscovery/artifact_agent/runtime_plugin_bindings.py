"""Startup binding and read-only health checks for compiled runtime plugins."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

from scidiscovery.operations.runtime_plugins import (
    RuntimePluginContext,
    RuntimePluginContribution,
)


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_LOCAL_BINDING = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class RuntimePluginBindingSummary:
    plugin_id: str
    configuration_schema_digest: str
    raw_config_sha256: str

    def __post_init__(self) -> None:
        if _PLUGIN_ID.fullmatch(self.plugin_id) is None or any(
            _DIGEST.fullmatch(value) is None
            for value in (
                self.configuration_schema_digest,
                self.raw_config_sha256,
            )
        ):
            raise ValueError("runtime plugin binding summary is invalid")


@dataclass(frozen=True, slots=True)
class LoadedRuntimePlugins:
    execution_adapters: Mapping[str, Any]
    tool_services: Mapping[str, Any]
    reconcilers: tuple[Any, ...]
    bindings: tuple[RuntimePluginBindingSummary, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "execution_adapters",
            MappingProxyType(dict(self.execution_adapters)),
        )
        object.__setattr__(
            self,
            "tool_services",
            MappingProxyType(dict(self.tool_services)),
        )


def parse_plugin_config_assignments(values: tuple[str, ...]) -> Mapping[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        plugin_id, separator, raw_path = value.partition("=")
        if (
            not separator
            or _PLUGIN_ID.fullmatch(plugin_id) is None
            or not raw_path
            or plugin_id in result
        ):
            raise ValueError("plugin config must be one unique plugin_id=path assignment")
        result[plugin_id] = Path(raw_path).expanduser().absolute()
    return MappingProxyType(result)


def load_runtime_plugin_contributions(
    catalog: Any,
    assignments: Mapping[str, Path],
    *,
    mode: Literal["control", "local_worker"],
    state_root: Path,
) -> LoadedRuntimePlugins:
    installed = set(catalog.runtime_plugin_ids())
    supplied = set(assignments)
    expected = supplied if mode == "local_worker" else installed
    unknown = supplied - installed
    if unknown:
        raise ValueError(
            "runtime plugin config does not match an installed plugin: "
            + ", ".join(sorted(unknown))
        )
    if supplied != expected:
        missing = sorted(expected - supplied)
        if missing:
            raise ValueError(
                "runtime plugin config is missing for: " + ", ".join(missing)
            )
        raise ValueError("runtime plugin config set is invalid")
    adapters: dict[str, Any] = {}
    services: dict[str, Any] = {}
    reconcilers: list[Any] = []
    summaries: list[RuntimePluginBindingSummary] = []
    for plugin_id in sorted(assignments):
        factory = catalog.runtime_factory(plugin_id)
        config_path = assignments[plugin_id]
        raw = _read_config(config_path)
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("plugin config is not valid JSON") from error
        if not isinstance(decoded, dict):
            raise ValueError("plugin config must be a JSON object")
        contribution = factory.build(
            RuntimePluginContext(
                plugin_id=plugin_id,
                mode=mode,
                config_path=config_path,
                config_bytes=raw,
                state_root=state_root,
            )
        )
        if not isinstance(contribution, RuntimePluginContribution):
            raise ValueError("runtime plugin factory returned the wrong type")
        local_names = (
            *contribution.execution_adapters,
            *contribution.tool_services,
        )
        if any(_LOCAL_BINDING.fullmatch(key) is None for key in local_names):
            raise ValueError("runtime plugin bindings must use local names")
        adapters.update(
            {
                f"{plugin_id}:{key}": value
                for key, value in contribution.execution_adapters.items()
            }
        )
        services.update(
            {
                f"{plugin_id}:{key}": value
                for key, value in contribution.tool_services.items()
            }
        )
        reconcilers.extend(contribution.reconcilers)
        summaries.append(
            RuntimePluginBindingSummary(
                plugin_id,
                catalog.runtime_configuration_digest(plugin_id),
                hashlib.sha256(raw).hexdigest(),
            )
        )
    if len(reconcilers) != len({id(item) for item in reconcilers}):
        raise ValueError("runtime plugins repeat a reconciler")
    return LoadedRuntimePlugins(
        adapters,
        services,
        tuple(reconcilers),
        tuple(summaries),
    )


def runtime_process_summary(
    catalog: Any,
    contribution: LoadedRuntimePlugins,
    *,
    mode: Literal["control", "local_worker"],
) -> bytes:
    from .service.execution_collection import COLLECTION_SECONDS, QUERY_SECONDS, FILE_SECONDS, IDLE_SECONDS
    return (
        json.dumps(
            {
                "schema_version": 1,
                "mode": mode,
                "catalog_digest": catalog.digest(),
                "io_budget_defaults": {"query_seconds": QUERY_SECONDS, "collection_seconds": COLLECTION_SECONDS,
                    "file_seconds": FILE_SECONDS, "idle_seconds": IDLE_SECONDS,
                    "author_debug": "remaining Run budget", "analysis_inspection": "remaining Run/IO budget"},
                "plugins": [
                    {
                        "plugin_id": item.plugin_id,
                        "configuration_schema_digest": item.configuration_schema_digest,
                        "raw_config_sha256": item.raw_config_sha256,
                    }
                    for item in contribution.bindings
                ],
            },
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_runtime_process_summary(path: Path, content: bytes) -> None:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise ValueError("runtime summary path must be an absolute file path")
    try:
        parent_metadata = os.lstat(path.parent)
    except FileNotFoundError as error:
        raise ValueError("runtime summary directory does not exist") from error
    if stat.S_ISLNK(parent_metadata.st_mode) or not stat.S_ISDIR(
        parent_metadata.st_mode
    ):
        raise ValueError("runtime summary directory must be a non-symlink directory")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o640,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o640, follow_symlinks=False)
        os.replace(temporary, path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_config(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as error:
        raise ValueError("plugin config does not exist") from error
    except OSError as error:
        raise ValueError("plugin config must be a regular non-symlink file") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("plugin config must be a regular non-symlink file")
        if metadata.st_size > 1024 * 1024:
            raise ValueError("plugin config exceeds one MiB")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("plugin config exceeds one MiB")
        return raw
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def read_runtime_summary(
    path: Path,
    *,
    expected_mode: Literal["control", "worker"],
) -> dict[str, Any]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError as error:
        raise ValueError(f"{expected_mode} runtime summary is missing") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o640
        or metadata.st_size > 1024 * 1024
    ):
        raise ValueError(f"{expected_mode} runtime summary metadata is invalid")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{expected_mode} runtime summary is invalid JSON") from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "mode",
        "catalog_digest",
        "plugins",
    }:
        raise ValueError(f"{expected_mode} runtime summary shape is invalid")
    if (
        value["schema_version"] != 1
        or value["mode"] != expected_mode
        or not isinstance(value["catalog_digest"], str)
        or _DIGEST.fullmatch(value["catalog_digest"]) is None
        or not isinstance(value["plugins"], list)
    ):
        raise ValueError(f"{expected_mode} runtime summary identity is invalid")
    plugin_ids: list[str] = []
    for item in value["plugins"]:
        if not isinstance(item, dict) or set(item) != {
            "plugin_id",
            "configuration_schema_digest",
            "raw_config_sha256",
        }:
            raise ValueError(f"{expected_mode} runtime plugin summary is invalid")
        plugin_id = item["plugin_id"]
        if (
            not isinstance(plugin_id, str)
            or _PLUGIN_ID.fullmatch(plugin_id) is None
            or any(
                not isinstance(item[name], str)
                or _DIGEST.fullmatch(item[name]) is None
                for name in (
                    "configuration_schema_digest",
                    "raw_config_sha256",
                )
            )
        ):
            raise ValueError(f"{expected_mode} runtime plugin identity is invalid")
        plugin_ids.append(plugin_id)
    if plugin_ids != sorted(plugin_ids) or len(plugin_ids) != len(set(plugin_ids)):
        raise ValueError(f"{expected_mode} runtime plugin order is invalid")
    return value


def verify_runtime_summaries(
    control_path: Path,
    worker_path: Path,
    *,
    expected_catalog_digest: str | None = None,
) -> tuple[str, tuple[str, ...]]:
    control = read_runtime_summary(control_path, expected_mode="control")
    worker = read_runtime_summary(worker_path, expected_mode="worker")
    if control["catalog_digest"] != worker["catalog_digest"]:
        raise ValueError("control and worker runtime catalogs differ")
    if (
        expected_catalog_digest is not None
        and control["catalog_digest"] != expected_catalog_digest
    ):
        raise ValueError("runtime summaries do not match the installed catalog")
    control_plugins = {
        item["plugin_id"]: (
            item["configuration_schema_digest"],
            item["raw_config_sha256"],
        )
        for item in control["plugins"]
    }
    worker_plugins = {
        item["plugin_id"]: (
            item["configuration_schema_digest"],
            item["raw_config_sha256"],
        )
        for item in worker["plugins"]
    }
    if control_plugins != worker_plugins:
        raise ValueError("control and worker runtime plugin bindings differ")
    return control["catalog_digest"], tuple(sorted(control_plugins))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scidiscovery-runtime-health")
    parser.add_argument("--control-summary", type=Path, required=True)
    parser.add_argument("--worker-summary", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from scidiscovery.operations.catalog import compile_installed_catalog

        digest, plugins = verify_runtime_summaries(
            args.control_summary,
            args.worker_summary,
            expected_catalog_digest=compile_installed_catalog().digest(),
        )
    except ValueError as error:
        parser.error(str(error))
    print(
        "runtime plugin health: pass "
        f"(catalog={digest}, plugins={','.join(plugins) or 'none'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LoadedRuntimePlugins",
    "RuntimePluginBindingSummary",
    "load_runtime_plugin_contributions",
    "main",
    "parse_plugin_config_assignments",
    "read_runtime_summary",
    "runtime_process_summary",
    "verify_runtime_summaries",
    "write_runtime_process_summary",
]
