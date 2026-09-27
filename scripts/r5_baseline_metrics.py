#!/usr/bin/env python3
"""Emit deterministic R5 structural metrics without importing SciDiscovery.

The snapshot separates production consumers from tests and historical prose.
It also aggregates each R0 responsibility over a versioned successor set, so
moving code to a new file cannot masquerade as simplification.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path


BASELINE_COMMIT = "404aeb14c6ebc4b08bac599db91eaee54c103f48"
R0_CORE_PATHS = (
    "src/scidiscovery/scheduler_topology.py",
    "src/scidiscovery/platforms/roles.py",
    "src/scidiscovery/artifact_agent/runtime.py",
    "src/scidiscovery/artifact_agent/interfaces/mcp_root.py",
    "src/scidiscovery/artifact_agent/service/tasks.py",
    "src/scidiscovery/artifact_agent/approval_ui/render.py",
)

# R5 stages must add every split successor here instead of replacing its owner.
RESPONSIBILITY_SUCCESSORS = {
    path: (path,) for path in R0_CORE_PATHS
} | {
    "src/scidiscovery/artifact_agent/interfaces/mcp_worker.py": (
        "src/scidiscovery/artifact_agent/interfaces/mcp_worker.py",
    ),
    "src/scidiscovery/general_science_plugin.py": (
        "src/scidiscovery/general_science_plugin.py",
    ),
    "src/scidiscovery/general_transform_operations.py": (
        "src/scidiscovery/general_transform_operations.py",
    ),
    "src/scidiscovery/operations/catalog.py": (
        "src/scidiscovery/operations/catalog.py",
    ),
}

# Deletion/migration witnesses, not a second runtime registry.
CONSUMER_PATTERNS = {
    "legacy_role_entry_point": r"scidiscovery\.agent_role_packs",
    "legacy_transform_entry_point": r"scidiscovery\.transform_adapters",
    "broken_operation_entry_point": r"scidiscovery\.operation_specs",
    "load_roles": r"\bload_roles\b",
    "load_transform_adapters": r"\bload_transform_adapters\b",
    "task_schedule": r"\btask_schedule\b",
    "artifact_transform": r"\bartifact_transform\b",
    "approval_request_create": r"\bapproval_request_create\b",
    "execution_request_create": r"\bexecution_request_create\b",
    "device_parameter_schema": (
        r"artifact_agent\.schema\.device_parameters|"
        r"(?:from|import)\s+[^\n]*device_parameters"
    ),
    "device_parameter_bundle_validator": (
        r"_validate_device_parameter_evidence_bundle|"
        r"_same_device_parameter_checklist"
    ),
    "parameter_operation_ids": (
        r"science\.(?:parameter\.(?:coverage|uncertainty)|"
        r"parameters\.qualify\.(?:pass|exception))\.v1"
    ),
    "producer_family_hardcoding": (
        r"_producer_output_family|_typed_intake_revision_family|"
        r"legacy\.device-parameter-evidence|extraction_primary|"
        r"revised_object|revision_diff"
    ),
    "scientific_readiness": r"\bscientific_readiness\b",
    "role_runtime_profile": (
        r"\bRoleRuntimeProfile\b|\b_ROLE_PROFILES\b|"
        r"\brole_runtime_profile\b"
    ),
    "core_context_policy": r"\bcore_context_policies\b",
}
DOMAIN_PATTERN = re.compile(
    r"\b(tcad|device_parameters?|curve_score|ingaas|fig4)\b", re.IGNORECASE
)
TEXT_SUFFIXES = {
    "", ".css", ".html", ".ini", ".js", ".json", ".md", ".py",
    ".service", ".sh", ".toml", ".txt", ".yaml", ".yml",
}
CATEGORIES = (
    "production",
    "dynamic-entry",
    "test",
    "current-doc",
    "historical-doc",
)


def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _git_lines(repository: Path, relative: str) -> int:
    output = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:{relative}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return len(output.splitlines())


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    )


def _top_level_definitions(path: Path) -> list[str]:
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        f"{type(node).__name__}:{node.name}"
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _text_files(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(
            path for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() in TEXT_SUFFIXES
        )
    )


def _scan_groups(repository: Path) -> dict[str, tuple[Path, ...]]:
    production = _python_files(repository / "src") + _python_files(
        repository / "plugins"
    )
    dynamic = (
        _text_files(repository / "deploy")
        + _text_files(repository / "roles")
        + tuple(sorted(repository.glob("*pyproject.toml")))
        + tuple(sorted((repository / "plugins").glob("*/pyproject.toml")))
    )
    current_docs = tuple(
        path
        for path in (
            repository / "AGENTS.md",
            *sorted(repository.glob("README*.md")),
            *_text_files(repository / "docs"),
        )
        if path.is_file() and "plans" not in path.relative_to(repository).parts
    )
    return {
        "production": production,
        "dynamic-entry": dynamic,
        # Test API consumers are executable Python, not frozen JSON data files.
        "test": _python_files(repository / "tests"),
        "current-doc": current_docs,
        "historical-doc": _text_files(repository / "docs/plans"),
    }


def _digest_lines(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def collect(repository: Path) -> dict[str, object]:
    repository = repository.resolve()
    operations = _python_files(repository / "src/scidiscovery/operations")
    production = _python_files(repository / "src") + _python_files(
        repository / "plugins"
    )
    consumer_files = {
        name: {category: [] for category in CATEGORIES}
        for name in CONSUMER_PATTERNS
    }
    consumer_occurrence_counts = {
        name: {category: 0 for category in CATEGORIES}
        for name in CONSUMER_PATTERNS
    }
    domain_hits: list[str] = []
    for category, paths in _scan_groups(repository).items():
        for path in paths:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = path.relative_to(repository).as_posix()
            matched_patterns: set[str] = set()
            for line_number, line in enumerate(content.splitlines(), 1):
                for name, pattern in CONSUMER_PATTERNS.items():
                    if re.search(pattern, line):
                        consumer_occurrence_counts[name][category] += 1
                        matched_patterns.add(name)
                if category == "production" and relative.startswith(
                    "src/scidiscovery/"
                ) and DOMAIN_PATTERN.search(line):
                    domain_hits.append(f"{relative}:{line_number}")
            for name in matched_patterns:
                consumer_files[name][category].append(relative)

    current_core = {
        relative: _lines(repository / relative)
        if (repository / relative).exists() else 0
        for relative in R0_CORE_PATHS
    }
    baseline_core = {
        relative: _git_lines(repository, relative) for relative in R0_CORE_PATHS
    }
    responsibilities: dict[str, object] = {}
    for owner, successors in RESPONSIBILITY_SUCCESSORS.items():
        line_counts = {
            relative: _lines(repository / relative)
            if (repository / relative).exists() else 0
            for relative in successors
        }
        responsibilities[owner] = {
            "successor_paths": list(successors),
            "lines_by_path": line_counts,
            "total_lines": sum(line_counts.values()),
            "top_level_definitions_by_path": {
                relative: _top_level_definitions(repository / relative)
                for relative in successors
            },
        }
    return {
        "schema_version": 2,
        "baseline_commit": BASELINE_COMMIT,
        "r0_core": {
            "paths": list(R0_CORE_PATHS),
            "baseline_lines": baseline_core,
            "baseline_total": sum(baseline_core.values()),
            "r5_0_lines": current_core,
            "r5_0_total": sum(current_core.values()),
        },
        "operations_package": {
            "files": len(operations),
            "lines": sum(_lines(path) for path in operations),
        },
        "production_python": {
            "files": len(production),
            "lines": sum(_lines(path) for path in production),
        },
        "deployment": {
            "install_sh_lines": _lines(repository / "deploy/install.sh")
        },
        "responsibilities": responsibilities,
        "consumer_files": consumer_files,
        "consumer_occurrence_counts": consumer_occurrence_counts,
        "generic_core_domain_tokens": {
            "count": len(domain_hits),
            "locations_sha256": _digest_lines(domain_hits),
        },
    }


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    print(json.dumps(collect(repository), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
