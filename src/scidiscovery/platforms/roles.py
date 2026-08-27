from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution, entry_points
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from scidiscovery.artifact_agent.schema.device_parameters import (
    DeviceParameterRequirementSet,
    DeviceParameterSet,
    EvidenceSourceCatalog,
)
from scidiscovery.artifact_agent.schema.role_result import role_result_json_schema
from scidiscovery.artifact_agent.schema.task import TaskOutputCollectionSpec


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


SCIENTIFIC_PAPER_EVIDENCE_COLLECTIONS = (
    TaskOutputCollectionSpec(
        name="figure_manifest",
        kind="figure_evidence_manifest",
        schema_id="scidiscovery.figure-evidence-manifest.v1",
        validator=(
            "scidiscovery.artifact_agent.schema.figure_evidence:"
            "validate_figure_evidence_manifest"
        ),
        media_types=("application/json",),
        min_items=1,
        max_items=1,
        max_item_bytes=1024 * 1024,
        max_total_bytes=1024 * 1024,
    ),
    TaskOutputCollectionSpec(
        name="source_panels",
        kind="figure_source_panel",
        schema_id="opaque",
        media_types=("image/png", "image/jpeg", "image/webp"),
        min_items=1,
        max_items=16,
        max_item_bytes=16 * 1024 * 1024,
        max_total_bytes=64 * 1024 * 1024,
    ),
    TaskOutputCollectionSpec(
        name="audit_overlays",
        kind="figure_audit_overlay",
        schema_id="opaque",
        media_types=("image/png",),
        min_items=1,
        max_items=32,
        max_item_bytes=16 * 1024 * 1024,
        max_total_bytes=128 * 1024 * 1024,
    ),
    TaskOutputCollectionSpec(
        name="curve_tables",
        kind="digitized_curve_table",
        schema_id="opaque",
        media_types=("text/csv",),
        min_items=1,
        max_items=128,
        max_item_bytes=8 * 1024 * 1024,
        max_total_bytes=64 * 1024 * 1024,
    ),
)


DEVICE_PARAMETER_EVIDENCE_COLLECTIONS = (
    TaskOutputCollectionSpec(
        name="parameter_requirements",
        kind="device_parameter_requirements",
        schema_id="scidiscovery.device-parameter-requirements.v1",
        validator=(
            "scidiscovery.artifact_agent.schema.device_parameters:"
            "validate_device_parameter_requirement_set"
        ),
        json_schema=DeviceParameterRequirementSet.model_json_schema(
            mode="validation"
        ),
        media_types=("application/json",),
        min_items=1,
        max_items=1,
        max_item_bytes=2 * 1024 * 1024,
        max_total_bytes=2 * 1024 * 1024,
    ),
    TaskOutputCollectionSpec(
        name="device_parameters",
        kind="device_parameters",
        schema_id="scidiscovery.device-parameter-set.v1",
        validator=(
            "scidiscovery.artifact_agent.schema.device_parameters:"
            "validate_device_parameter_set"
        ),
        json_schema=DeviceParameterSet.model_json_schema(mode="validation"),
        media_types=("application/json",),
        min_items=1,
        max_items=1,
        max_item_bytes=2 * 1024 * 1024,
        max_total_bytes=2 * 1024 * 1024,
    ),
    TaskOutputCollectionSpec(
        name="source_catalog",
        kind="evidence_source_catalog",
        schema_id="scidiscovery.evidence-source-catalog.v1",
        validator=(
            "scidiscovery.artifact_agent.schema.device_parameters:"
            "validate_evidence_source_catalog"
        ),
        json_schema=EvidenceSourceCatalog.model_json_schema(mode="validation"),
        media_types=("application/json",),
        min_items=1,
        max_items=1,
        max_item_bytes=1024 * 1024,
        max_total_bytes=1024 * 1024,
    ),
)


CURVE_ERROR_ANALYSIS_COLLECTIONS = (
    TaskOutputCollectionSpec(
        name="curve_analysis_plots",
        kind="curve_error_plot",
        schema_id="scidiscovery.curve-error-plot.v1",
        bundle_validator=(
            "scidiscovery.artifact_agent.schema.curve_analysis:"
            "validate_curve_error_plot_collection"
        ),
        media_types=("image/png",),
        min_items=1,
        max_items=8,
        max_item_bytes=1024 * 1024,
        max_total_bytes=8 * 1024 * 1024,
    ),
)


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    description: str
    output: str
    output_format: str
    output_schema: str
    output_validator: str | None
    output_context_validator: str | None
    output_context_sources: tuple[str, ...]
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
                output_context_validator=metadata.get("context_validator"),
                output_context_sources=tuple(
                    item.strip()
                    for item in metadata.get("context_sources", "").split(",")
                    if item.strip()
                ),
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


def role_output_collection_profiles(
    role: RoleDefinition,
) -> dict[str, tuple[TaskOutputCollectionSpec, ...]]:
    """Return static, exact sibling-output profiles admitted by one role."""

    if role.name == "evidence_extractor":
        return {
            "scientific-paper-evidence": SCIENTIFIC_PAPER_EVIDENCE_COLLECTIONS,
            "device-parameter-evidence": DEVICE_PARAMETER_EVIDENCE_COLLECTIONS,
        }
    if role.name == "diagnostician":
        return {"curve-error-analysis": CURVE_ERROR_ANALYSIS_COLLECTIONS}
    return {}


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
