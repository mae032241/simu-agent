from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import venv
from dataclasses import dataclass
from importlib.metadata import distribution
from pathlib import Path
from typing import Callable

import pytest


@dataclass(frozen=True)
class InstalledEnvironment:
    python: Path
    workdir: Path


def _copy_runtime_distribution(name: str, destination: Path) -> None:
    """Copy one installed runtime dependency without exposing system site packages."""

    package = distribution(name)
    root = destination.resolve()
    for relative in package.files or ():
        source = Path(package.locate_file(relative))
        target = (destination / relative).resolve()
        if not target.is_relative_to(root) or not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


@pytest.fixture(scope="session")
def installed_environments(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, InstalledEnvironment]:
    """Build wheels once and expose source-independent core/full runtimes."""

    repository = Path(__file__).resolve().parents[2]
    root = tmp_path_factory.mktemp("r0-installed")
    release_source = root / "source-release"
    subprocess.run(
        [
            sys.executable,
            str(repository / "scripts/build_git_release.py"),
            "--source",
            str(repository),
            "--output",
            str(release_source),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    fixture_plugins = root / "fixture-plugins"
    shutil.copytree(
        repository / "tests/fixtures/plugins",
        fixture_plugins,
        ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__", "*.pyc"),
    )
    for source in (
        release_source,
        release_source / "plugins/tcad_artifact",
        release_source / "plugins/curve_score",
        release_source / "plugins/curve_figure_evidence",
        release_source / "plugins/ingaas_fig4",
        fixture_plugins / "table_observation_plugin",
        fixture_plugins / "blind_csv_operation_plugin",
        fixture_plugins / "architecture_operation_plugin",
        fixture_plugins / "m7_effect_operation_plugin",
        fixture_plugins / "broken_operation_plugin",
        fixture_plugins / "invalid_unicode_operation_plugin",
        fixture_plugins / "producer_family_operation_plugin",
    ):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheelhouse),
                str(source),
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )

    wheels = {path.name: path for path in wheelhouse.glob("*.whl")}
    core = next(
        path for name, path in wheels.items() if name.startswith("scidiscovery-0")
    )
    tcad = next(path for name, path in wheels.items() if name.startswith("tcad_artifact-"))
    curve = next(
        path for name, path in wheels.items() if name.startswith("scidiscovery_curve_score-")
    )
    figure = next(
        path
        for name, path in wheels.items()
        if name.startswith("scidiscovery_curve_figure_evidence-")
    )
    ingaas = next(
        path for name, path in wheels.items() if name.startswith("scidiscovery_ingaas_fig4-")
    )
    table = next(
        path for name, path in wheels.items()
        if name.startswith("scidiscovery_table_observation-")
    )
    blind_csv = next(
        path for name, path in wheels.items()
        if name.startswith("scidiscovery_blind_csv_test_plugin-")
    )
    broken = next(
        path for name, path in wheels.items()
        if name.startswith("scidiscovery_broken_operation_test_plugin-")
    )
    invalid_unicode = next(
        path for name, path in wheels.items()
        if name.startswith("scidiscovery_invalid_unicode_operation_test_plugin-")
    )
    architecture = next(
        path for name, path in wheels.items()
        if name.startswith("scidiscovery_architecture_operation_test_plugin-")
    )
    m7_effect = next(
        path
        for name, path in wheels.items()
        if name.startswith("scidiscovery_m7_effect_test_plugin-")
    )
    producer_family = next(
        path for name, path in wheels.items()
        if name.startswith("scidiscovery_producer_family_test_plugin-")
    )

    environments: dict[str, InstalledEnvironment] = {}
    for name, selected in {
        "core": (core,),
        "curve": (core, curve),
        "figure": (core, curve, figure),
        "table": (core, table),
        "blind_csv": (core, blind_csv),
        "architecture": (core, architecture),
        "m7_effect": (core, m7_effect),
        "full": (core, tcad, curve),
        "ingaas": (core, tcad, curve, ingaas),
        "producer_family": (core, producer_family),
        "broken": (core, broken),
        "invalid_unicode": (core, invalid_unicode),
    }.items():
        environment_root = root / name
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment_root)
        python = environment_root / "bin/python"
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                *map(str, selected),
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        workdir = root / f"{name}-workdir"
        workdir.mkdir()
        environments[name] = InstalledEnvironment(python=python, workdir=workdir)

    # H3-A proof environment: retain only the exact current runtime packages,
    # without inheriting PyYAML or any other base-environment site package.
    environment_root = root / "core_no_yaml"
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment_root)
    python = environment_root / "bin/python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(core)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    site_packages = (
        environment_root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    for package_name in (
        "annotated-types",
        "Pillow",
        "attrs",
        "jsonschema",
        "jsonschema-specifications",
        "pydantic",
        "pydantic_core",
        "referencing",
        "rpds-py",
        "typing-extensions",
        "typing-inspection",
    ):
        _copy_runtime_distribution(package_name, site_packages)
    workdir = root / "core_no_yaml-workdir"
    workdir.mkdir()
    environments["core_no_yaml"] = InstalledEnvironment(
        python=python, workdir=workdir
    )

    environment_root = root / "tcad_resolved"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment_root)
    python = environment_root / "bin/python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(core)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    site_packages = (
        environment_root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    for package_name in (
        "attrs",
        "jsonschema",
        "jsonschema-specifications",
        "referencing",
        "rpds-py",
    ):
        _copy_runtime_distribution(package_name, site_packages)
    subprocess.run(
        [
            str(python), "-m", "pip", "install", "--no-index",
            "--find-links", str(wheelhouse), str(tcad),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    workdir = root / "tcad_resolved-workdir"
    workdir.mkdir()
    environments["tcad_resolved"] = InstalledEnvironment(
        python=python, workdir=workdir
    )
    return environments


@pytest.fixture
def installed_probe(
    installed_environments: dict[str, InstalledEnvironment],
) -> Callable[[str, str], str]:
    def run(environment_name: str, source: str) -> str:
        environment = installed_environments[environment_name]
        clean_environment = dict(os.environ)
        clean_environment.pop("PYTHONPATH", None)
        clean_environment.pop("SCIDISCOVERY_ROLE_DIR", None)
        clean_environment["PYTHONNOUSERSITE"] = "1"
        prefix = """
from pathlib import Path as _R0Path
import scidiscovery as _r0_scidiscovery
import sys as _r0_sys
assert _R0Path(_r0_scidiscovery.__file__).resolve().is_relative_to(
    _R0Path(_r0_sys.prefix).resolve()
), _r0_scidiscovery.__file__
"""
        completed = subprocess.run(
            [str(environment.python), "-c", textwrap.dedent(prefix + source)],
            cwd=environment.workdir,
            env=clean_environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, (
            f"installed probe failed ({environment_name})\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
        return completed.stdout

    return run
