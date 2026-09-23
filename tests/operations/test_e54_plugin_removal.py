"""P1 package ownership and case-plugin removal regression boundaries."""

from pathlib import Path
import json

import pytest

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN


def test_figure_implementations_belong_to_the_figure_package():
    shared = {
        "nonempty_validator": "curve_score.science_operations:_NONEMPTY_COMPONENT",
        "figure_request_workspace": "scidiscovery.general_science_components:WORKSPACE",
    }
    for component in FIGURE_PLUGIN.components:
        if component.component_id in shared:
            assert component.implementation == shared[component.component_id]
            continue
        assert component.implementation.startswith("curve_figure_evidence."), component


def test_case_plugin_and_release_wrapper_are_absent():
    root = Path(__file__).resolve().parents[2]
    assert not (root / "plugins/ingaas_fig4").exists()
    assert not (root / "deploy/apply_ingaas_fig4_profile.sh").exists()
    for path in (root / "pyproject.toml", root / "scripts/build_git_release.py"):
        assert "plugins/ingaas_fig4" not in path.read_text()


def test_historical_replay_fixture_uses_generic_curve_contracts(monkeypatch):
    from curve_score.plugin import PLUGIN as CURVE_PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    from tests.operations.test_m2_curve_analysis_boundary import _inputs

    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "tests/fixtures/plugins/r5_e2e_tcad_plugin"))
    from r5_e2e_tcad_plugin.plugin import PLUGIN
    from r5_e2e_tcad_plugin.runtime import project_science_sources

    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, PLUGIN))
    source_view = catalog.operation("r5.fixture.fig4-science-source-view.v1")
    assert [port.schema_id for port in source_view.spec.inputs] == [
        "scidiscovery.curve-consistency-report.v1", "scidiscovery.curve-bundle.v1",
    ]
    inputs = _inputs()
    result = project_science_sources({key: (inputs[key],) for key in ("metric_report", "curve_bundle")})
    assert result == {"metric_source": (inputs["metric_report"],), "curve_source": (inputs["curve_bundle"],)}
    with pytest.raises(ValueError):
        project_science_sources({"metric_report": (b'{"schema_version":1}',), "curve_bundle": (b"material,x,y\na,1,2\n",)})
    manifest = json.loads((root / "tests/fixtures/r5_e2e_tcad/manifest.json").read_text())
    assert manifest["status"] == "historical_only_not_current_qualification"
    assert "operation_contract" not in manifest
