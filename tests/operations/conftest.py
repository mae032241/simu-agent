from __future__ import annotations

import os
import shutil
import textwrap
from pathlib import Path
from typing import Callable, Iterator

import pytest

from scripts.installed_candidates import InstalledEnvironment, create_environments, _run_logged


@pytest.fixture(scope="session")
def installed_environments(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, InstalledEnvironment]]:
    root = tmp_path_factory.mktemp("installed")
    try:
        yield create_environments(Path(__file__).resolve().parents[2], root)
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
