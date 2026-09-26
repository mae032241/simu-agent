from __future__ import annotations

from importlib.metadata import EntryPoint, EntryPoints
import fcntl
import os
from pathlib import Path

import pytest

from scidiscovery.operations import catalog as catalog_module


_SOURCE_FULL_PLUGINS = EntryPoints(
    (
        EntryPoint(
            name="builtin",
            value="scidiscovery.builtin_plugin:CORE_PLUGIN",
            group="scidiscovery.plugins",
        ),
        EntryPoint(
            name="general_science",
            value="scidiscovery.general_science_plugin:PLUGIN",
            group="scidiscovery.plugins",
        ),
        EntryPoint(
            name="tcad_artifact",
            value="tcad_artifact.plugin:PLUGIN",
            group="scidiscovery.plugins",
        ),
        EntryPoint(
            name="curve_score",
            value="curve_score.plugin:PLUGIN",
            group="scidiscovery.plugins",
        ),
    )
)


@pytest.fixture(autouse=True)
def _source_checkout_plugin_metadata(monkeypatch: pytest.MonkeyPatch):
    """Model the default full install without writing egg-info into the checkout."""

    monkeypatch.setattr(catalog_module, "entry_points", lambda: _SOURCE_FULL_PLUGINS)
    catalog_module.compile_installed_catalog.cache_clear()
    yield
    catalog_module.compile_installed_catalog.cache_clear()


_LANES = {"installed": "installed", "process_e2e": "process", "stress": "stress", "live_platform": "live"}


def pytest_addoption(parser):
    parser.addoption("--test-lane", choices=("source", "installed", "process", "stress", "live"),
                     default="source", help="Explicit test layer; default source never runs marked heavy tests")


def pytest_configure(config):
    if (config.getoption("numprocesses", default=0) not in (None, 0, "0")
            or "PYTEST_XDIST_WORKER" in os.environ):
        raise pytest.UsageError("xdist is disabled: use scripts/run_tests.py serially")
    lock_path = Path("/tmp") / f"scid-tests-{os.getuid()}.lock"
    inherited = os.environ.get("SCID_TEST_LOCK_FD")
    if inherited is not None:
        try:
            fd = int(inherited)
            inherited_stat, expected_stat = os.fstat(fd), lock_path.stat()
            if (inherited_stat.st_ino, inherited_stat.st_dev) != (expected_stat.st_ino, expected_stat.st_dev):
                raise ValueError("wrong lock file")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ValueError) as exc:
            raise pytest.UsageError("invalid inherited serial test lock") from exc
    else:
        lock = lock_path.open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock.close()
            raise pytest.UsageError("another pytest/runner owns this repository's serial lock") from exc
        config._scid_test_lock = lock


def pytest_unconfigure(config):
    lock = getattr(config, "_scid_test_lock", None)
    if lock is not None:
        lock.close()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    selected, deselected = [], []
    lane = config.getoption("test_lane")
    for item in items:
        if {"installed_probe", "installed_environments"}.intersection(item.fixturenames):
            item.add_marker(pytest.mark.installed)
        # A stress/live test can also use installation; choose the strongest opt-in.
        marked = {marker.name for marker in item.iter_markers()}
        actual = next((_LANES[name] for name in ("live_platform", "stress", "installed", "process_e2e")
                       if name in marked), "source")
        (selected if actual == lane else deselected).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if item.config.getoption("test_lane") != "source" and os.environ.get("SCID_TEST_GUARD") != "1":
        raise pytest.UsageError("heavy test lanes require scripts/run_tests.py resource supervision")
