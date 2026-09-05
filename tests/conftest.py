from __future__ import annotations

from importlib.metadata import EntryPoint, EntryPoints

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
