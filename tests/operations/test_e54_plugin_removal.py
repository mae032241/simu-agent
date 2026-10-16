"""P1 package ownership and case-plugin removal regression boundaries."""

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN


def test_figure_implementations_belong_to_the_figure_package():
    shared = {
        "figure_intake_validator": "scidiscovery.general_science_components:Components.intake_validator",
        "nonempty_validator": "curve_score.science_operations:_NONEMPTY_COMPONENT",
        "figure_request_workspace": "scidiscovery.general_science_components:WORKSPACE",
    }
    for component in FIGURE_PLUGIN.components:
        if component.component_id in shared:
            assert component.implementation == shared[component.component_id]
            continue
        assert component.implementation.startswith("curve_figure_evidence."), component
