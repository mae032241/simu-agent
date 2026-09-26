from __future__ import annotations

import os
import csv
import io
import itertools
import shutil
import subprocess
import sys
import textwrap
import venv
from dataclasses import dataclass
from importlib.metadata import distribution
from pathlib import Path
from typing import Callable, Iterator

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


def _supply_runtime_dependencies(site_packages: Path) -> None:
    for package_name in (
        "annotated-types", "Pillow", "attrs", "jsonschema",
        "jsonschema-specifications", "pydantic", "pydantic_core",
        "referencing", "rpds-py", "typing-extensions", "typing-inspection",
        "cryptography", "cffi", "pycparser",
    ):
        _copy_runtime_distribution(package_name, site_packages)
    if sys.version_info < (3, 11):
        _copy_runtime_distribution("tomli", site_packages)


_LOG_SEQUENCE = itertools.count(1)


def _run_logged(command, *, cwd: Path, timeout: int, env=None, read_stdout=False) -> str:
    """Fixture logs stay on disk and under the outer runner's sampled log budget."""
    log_root = Path(os.environ["SCID_TEST_LOG_DIR"])
    log_root.mkdir(parents=True, exist_ok=True)
    stem = str(next(_LOG_SEQUENCE))
    stdout_path, stderr_path = (log_root / f"{stem}.{channel}.log" for channel in ("stdout", "stderr"))
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                timeout=timeout, check=False)
    limit = int(os.environ["SCID_TEST_LOG_BYTES"])
    assert stdout_path.stat().st_size + stderr_path.stat().st_size <= limit, f"fixture log budget exceeded: {log_root}"
    def tail(path):
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 4096))
            return stream.read(4096).decode("utf-8", errors="replace")
    assert result.returncode == 0, (f"installed command failed ({result.returncode}); logs: {log_root}\n"
                                    f"stdout tail: {tail(stdout_path)}\nstderr tail: {tail(stderr_path)}")
    return stdout_path.read_text() if read_stdout else ""


def _link_runtime_file(source, target):
    # The immutable per-session dependency cache is not the user's installation.
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return target


@pytest.fixture(scope="session")
def installed_environments(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[dict[str, InstalledEnvironment]]:
    """Build wheels once; retain one isolated runtime, with shared dependency files."""

    repository = Path(__file__).resolve().parents[2]
    root = tmp_path_factory.mktemp("installed")
    dependency_cache = root / "runtime-dependencies"
    _supply_runtime_dependencies(dependency_cache)
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    fixture_plugins = repository / "tests/fixtures/plugins"
    sources = {
        "core": (repository, "scidiscovery-"),
        "tcad": (repository / "plugins/tcad_artifact", "tcad_artifact-"),
        "curve": (repository / "plugins/curve_score", "scidiscovery_curve_score-"),
        "figure": (repository / "plugins/curve_figure_evidence", "scidiscovery_curve_figure_evidence-"),
        "architecture": (fixture_plugins / "architecture_operation_plugin", "scidiscovery_architecture_operation_test_plugin-"),
        "blind_csv": (fixture_plugins / "blind_csv_operation_plugin", "scidiscovery_blind_csv_test_plugin-"),
        "m7_effect": (fixture_plugins / "m7_effect_operation_plugin", "scidiscovery_m7_effect_test_plugin-"),
        "broken": (fixture_plugins / "broken_operation_plugin", "scidiscovery_broken_operation_test_plugin-"),
        "invalid_unicode": (fixture_plugins / "invalid_unicode_operation_plugin", "scidiscovery_invalid_unicode_operation_test_plugin-"),
    }
    selections = {
        "core": ("core",),
        "curve": ("core", "curve"),
        "architecture": ("core", "architecture"),
        "blind_csv": ("core", "blind_csv"),
        "m7_effect": ("core", "m7_effect"),
        "all_domains": ("core", "tcad", "curve", "figure"),
        "broken": ("core", "broken"),
        "invalid_unicode": ("core", "invalid_unicode"),
        "tcad_resolved": ("core", "curve", "tcad"),
    }
    built = {}

    def wheel(name):
        if name not in built:
            source, prefix = sources[name]
            stage = root / "sources" / name
            ignored = shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__", "*.pyc")
            if name == "core":
                # Exactly the package/readme/data roots declared by pyproject.toml.
                # Release assembly and bundled manual scans have their own tests.
                stage.mkdir(parents=True)
                for relative in ("pyproject.toml", "README.md"):
                    shutil.copy2(source / relative, stage / relative)
                for relative in ("src", "roles", "deploy/systemd"):
                    shutil.copytree(source / relative, stage / relative, ignore=ignored)
            else:
                shutil.copytree(source, stage, ignore=ignored)
            _run_logged([
                sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-index", "--no-cache-dir",
                "--no-build-isolation", "--wheel-dir", str(wheelhouse), str(stage),
            ], cwd=root, timeout=180)
            built[name] = next(path for path in wheelhouse.glob("*.whl") if path.name.startswith(prefix))
        return built[name]

    def create_environment(name: str) -> InstalledEnvironment:
        if name not in selections:
            raise KeyError(name)
        selected = tuple(wheel(package) for package in selections[name])
        environment_root = root / name
        venv.EnvBuilder(with_pip=False, symlinks=True, system_site_packages=False).create(environment_root)
        site_packages = environment_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
        shutil.copytree(dependency_cache, site_packages, dirs_exist_ok=True, copy_function=_link_runtime_file)
        python = environment_root / "bin/python"
        if name == "tcad_resolved":
            selected = (wheel("core"),)
        _run_logged(
            [
                sys.executable, "-m", "pip", "--python", str(python),
                "install", "--no-cache-dir", "--no-compile",
                "--no-index",
                "--no-deps",
                *map(str, selected),
            ],
            cwd=root,
            timeout=180,
        )
        if name == "tcad_resolved":
            _run_logged(
                [
                    sys.executable, "-m", "pip", "--python", str(python),
                    "install", "--no-index", "--no-cache-dir", "--no-compile",
                    "--find-links", str(wheelhouse), str(wheel("tcad")),
                ],
                cwd=root,
                timeout=180,
            )
        workdir = root / f"{name}-workdir"
        workdir.mkdir()
        return InstalledEnvironment(python=python, workdir=workdir)

    class LazyEnvironments(dict[str, InstalledEnvironment]):
        def __missing__(self, name: str) -> InstalledEnvironment:
            for previous in self.values():
                shutil.rmtree(previous.python.parent.parent)
                shutil.rmtree(previous.workdir)
            self.clear()
            environment = create_environment(name)
            self[name] = environment
            return environment

    try:
        yield LazyEnvironments()
    finally:
        shutil.rmtree(root)


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
        return _run_logged(
            [str(environment.python), "-c", textwrap.dedent(prefix + source)],
            cwd=environment.workdir, env=clean_environment, timeout=120, read_stdout=True,
        )

    return run
