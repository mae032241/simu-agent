from __future__ import annotations

import os
import csv
import io
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
    record = package.read_text("RECORD")
    assert record is not None, f"offline dependency has no wheel RECORD: {name}"
    for row in csv.reader(io.StringIO(record)):
        relative = Path(row[0])
        if "__pycache__" in relative.parts or relative.suffix in {".pyc", ".pyo"}:
            continue
        source = Path(package.locate_file(relative))
        target = (destination / relative).resolve()
        if not target.is_relative_to(root) or not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _supply_runtime_dependencies(environment_root: Path) -> None:
    site_packages = environment_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    for package_name in (
        "annotated-types", "Pillow", "attrs", "jsonschema",
        "jsonschema-specifications", "pydantic", "pydantic_core",
        "referencing", "rpds-py", "typing-extensions", "typing-inspection",
        "cryptography", "cffi", "pycparser",
    ):
        _copy_runtime_distribution(package_name, site_packages)
    if sys.version_info < (3, 11):
        _copy_runtime_distribution("tomli", site_packages)


@pytest.fixture(scope="session")
def installed_environments(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, InstalledEnvironment]:
    """Build wheels once; install only the source-independent runtimes used."""

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
        fixture_plugins / "table_observation_plugin",
        fixture_plugins / "blind_csv_operation_plugin",
        fixture_plugins / "architecture_operation_plugin",
        fixture_plugins / "m7_effect_operation_plugin",
        fixture_plugins / "broken_operation_plugin",
        fixture_plugins / "invalid_unicode_operation_plugin",
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
    selections = {
        "core": (core,),
        "curve": (core, curve),
        "figure": (core, curve, figure),
        "table": (core, table),
        "blind_csv": (core, blind_csv),
        "architecture": (core, architecture),
        "m7_effect": (core, m7_effect),
        "full": (core, tcad, curve),
        "all_domains": (core, tcad, curve, figure),
        "broken": (core, broken),
        "invalid_unicode": (core, invalid_unicode),
    }

    def create_environment(name: str) -> InstalledEnvironment:
        if name not in selections and name != "tcad_resolved":
            raise KeyError(name)
        environment_root = root / name
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment_root)
        _supply_runtime_dependencies(environment_root)
        python = environment_root / "bin/python"
        selected = selections[name] if name != "tcad_resolved" else (core,)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                *map(str, selected),
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if name == "tcad_resolved":
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
        workdir = root / f"{name}-workdir"
        workdir.mkdir()
        return InstalledEnvironment(python=python, workdir=workdir)

    class LazyEnvironments(dict[str, InstalledEnvironment]):
        def __missing__(self, name: str) -> InstalledEnvironment:
            environment = create_environment(name)
            self[name] = environment
            return environment

    return LazyEnvironments()


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
assert 'include-system-site-packages = false' in (_R0Path(_r0_sys.prefix) / 'pyvenv.cfg').read_text()
import PIL as _r0_pil
assert _R0Path(_r0_pil.__file__).resolve().is_relative_to(_R0Path(_r0_sys.prefix).resolve())
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
