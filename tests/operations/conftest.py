"""Source discovery fixtures. Functional tests never build or install candidates."""
from __future__ import annotations

from importlib.metadata import EntryPoint, EntryPoints
from pathlib import Path

import pytest

from scidiscovery.operations import catalog as catalog_module


@pytest.fixture
def source_catalog(monkeypatch):
    """Expose only the requested source plugins through the real catalog loader."""
    repository = Path(__file__).resolve().parents[2]
    plugins = {
        "curve_score": ("plugins/curve_score", "curve_score.plugin:PLUGIN"),
        "tcad_artifact": ("plugins/tcad_artifact", "tcad_artifact.plugin:PLUGIN"),
        "curve_figure_evidence": ("plugins/curve_figure_evidence", "curve_figure_evidence.plugin:PLUGIN"),
        "blind_csv": ("tests/fixtures/plugins/blind_csv_operation_plugin", "blind_csv_plugin.plugin:PLUGIN"),
        "m7_effect_fixture": ("tests/fixtures/plugins/m7_effect_operation_plugin", "m7_effect_operation_plugin:PLUGIN"),
        "broken": ("tests/fixtures/plugins/broken_operation_plugin", "broken_operation_plugin.plugin:PLUGIN"),
        "invalid_unicode": ("tests/fixtures/plugins/invalid_unicode_operation_plugin", "invalid_unicode_operation_plugin.plugin:PLUGIN"),
    }

    def select(*names):
        entries = [
            EntryPoint(name="builtin", value="scidiscovery.builtin_plugin:CORE_PLUGIN", group="scidiscovery.plugins"),
            EntryPoint(name="general_science", value="scidiscovery.general_science_plugin:PLUGIN", group="scidiscovery.plugins"),
        ]
        for name in names:
            directory, value = plugins[name]
            monkeypatch.syspath_prepend(str(repository / directory))
            entries.append(EntryPoint(name=name, value=value, group="scidiscovery.plugins"))
        monkeypatch.setattr(catalog_module, "entry_points", lambda: EntryPoints(entries))
        catalog_module.compile_installed_catalog.cache_clear()

    yield select
    catalog_module.compile_installed_catalog.cache_clear()
