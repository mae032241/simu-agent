from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution, entry_points
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from scidiscovery.artifact_agent.schema.role_result import role_result_json_schema


CORE_ROLE_NAMES = (
    "evidence_extractor",
    "ideator",
    "critic",
    "evidence_auditor",
    "experiment_designer",
    "diagnostician",
)

DOMAIN_ROLE_PATHS = {}
_SOURCE_PLUGIN_NAMES: set[str] = set()
_source_plugin_root = Path(__file__).resolve().parents[3] / "plugins"
if _source_plugin_root.is_dir():
    for _plugin_directory in sorted(_source_plugin_root.iterdir()):
        if not _plugin_directory.is_dir():
            continue
        _role_directories = (
            _plugin_directory / "roles",
            _plugin_directory / _plugin_directory.name.replace("-", "_") / "roles",
        )
        _found = False
        for _role_directory in _role_directories:
            for _path in sorted(_role_directory.glob("*.md")):
                DOMAIN_ROLE_PATHS[_path.stem] = _path
                _found = True
        if _found:
            _SOURCE_PLUGIN_NAMES.add(_plugin_directory.name.replace("-", "_"))
for _entry_point in sorted(
    entry_points(group="scidiscovery.agent_role_packs"),
    key=lambda item: (item.name, item.value),
):
    if _entry_point.name.replace("-", "_") in _SOURCE_PLUGIN_NAMES:
        continue
    _directory = Path(_entry_point.load()()).expanduser().absolute()
    if not _directory.is_dir():
        raise FileNotFoundError(
            f"agent role pack directory does not exist: {_entry_point.name}"
        )
    for _path in sorted(_directory.glob("*.md")):
        DOMAIN_ROLE_PATHS.setdefault(_path.stem, _path)

DOMAIN_ROLE_NAMES = tuple(DOMAIN_ROLE_PATHS)

ROLE_NAMES = CORE_ROLE_NAMES + DOMAIN_ROLE_NAMES


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    description: str
    output: str
    output_format: str
    output_schema: str
    output_validator: str | None
    output_model: str | None
    context_policies: str | None
    prompt: str


def load_roles() -> tuple[RoleDefinition, ...]:
    directory = _role_directory()
    common = (directory / "common.md").read_text(encoding="utf-8").strip()
    roles: list[RoleDefinition] = []
    for name in ROLE_NAMES:
        metadata, body = _read_role(_role_path(directory, name))
        if metadata.get("name") != name:
            raise ValueError(f"role name mismatch in {name}.md")
        output = _required(metadata, "output", name)
        roles.append(
            RoleDefinition(
                name=name,
                description=_required(metadata, "description", name),
                output=output,
                output_format=metadata.get("format", "json"),
                output_schema=metadata.get(
                    "schema",
                    f"scidiscovery.role-output.{output.replace('_', '-')}.v1",
                ),
                output_validator=metadata.get("validator"),
                output_model=metadata.get("output_model"),
                context_policies=metadata.get("context_policies"),
                prompt=f"{body.strip()}\n\n{common}\n",
            )
        )
    return tuple(roles)


def role_output_json_schema(role: RoleDefinition) -> dict[str, Any]:
    """Return the exact worker-visible JSON Schema for one role output."""

    if role.output_format != "json":
        return {}
    if role.output_model is None:
        raise ValueError(f"role {role.name} has no typed payload model")
    module_name, separator, attribute = role.output_model.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"role {role.name} has an invalid output_model")
    try:
        model = getattr(import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise ValueError(f"role {role.name} output_model is unavailable") from error
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise ValueError(f"role {role.name} output_model is not a Pydantic model")
    return role_result_json_schema(model)


def load_scheduler_prompt() -> str:
    _, body = _read_role(_role_directory() / "scheduler.md")
    return body.strip() + "\n"


def render_worker_prompt(
    role: RoleDefinition,
    *,
    python_executable: Path | str,
) -> str:
    del python_executable
    return role.prompt.rstrip() + "\n"


def _required(metadata: dict[str, str], key: str, role: str) -> str:
    value = metadata.get(key, "").strip()
    if not value:
        raise ValueError(f"role {role} has no {key}")
    return value


def _read_role(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"role file has no frontmatter: {path}")
    frontmatter, separator, body = text[4:].partition("\n---\n")
    if not separator:
        raise ValueError(f"role frontmatter is unterminated: {path}")
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        key, marker, value = line.partition(":")
        if not marker or not key.strip() or not value.strip():
            raise ValueError(f"invalid role frontmatter line: {line}")
        metadata[key.strip()] = value.strip()
    return metadata, body


def _role_directory() -> Path:
    override = os.environ.get("SCIDISCOVERY_ROLE_DIR")
    if override:
        directory = Path(override).expanduser()
        if directory.is_dir():
            return directory
        raise FileNotFoundError(f"role directory does not exist: {directory}")

    source_directory = Path(__file__).resolve().parents[3] / "roles"
    if source_directory.is_dir():
        return source_directory

    for ancestor in Path(__file__).resolve().parents:
        installed_directory = ancestor / "share" / "scidiscovery" / "roles"
        if installed_directory.is_dir():
            return installed_directory

    try:
        package = distribution("scidiscovery")
    except PackageNotFoundError as error:
        raise FileNotFoundError("installed role prompts are unavailable") from error
    for entry in package.files or ():
        candidate = package.locate_file(entry)
        if candidate.name == "common.md" and candidate.parent.name == "roles":
            return candidate.parent
    raise FileNotFoundError("installed role prompts are unavailable")


def _role_path(core_directory: Path, name: str) -> Path:
    core_path = core_directory / f"{name}.md"
    if core_path.is_file():
        return core_path
    candidate = DOMAIN_ROLE_PATHS.get(name)
    if candidate is not None and candidate.is_file():
        return candidate
    raise FileNotFoundError(f"role definition is unavailable: {name}")
