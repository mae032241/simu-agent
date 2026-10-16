"""The only pytest fixtures allowed to construct an installed candidate."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.installed_candidates import create_environment, _run_logged


@pytest.fixture(scope="session")
def installed_environment(pytestconfig, tmp_path_factory):
    if pytestconfig.getoption("test_lane") != "installed":
        raise pytest.UsageError("installation checks require --test-lane=installed")
    root = tmp_path_factory.mktemp("installation")
    return create_environment(Path(__file__).resolve().parents[2], root,
                              cohort=pytestconfig.getoption("installation_cohort"))


@pytest.fixture
def installed_probe(installed_environment):
    """Run a packaging assertion in the session's sole installed interpreter."""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("SCIDISCOVERY_ROLE_DIR", None)
    environment["PYTHONNOUSERSITE"] = "1"

    def run(source):
        return _run_logged([str(installed_environment.python), "-I", "-c", source],
                           cwd=installed_environment.workdir, env=environment,
                           timeout=60, read_stdout=True)

    return run
