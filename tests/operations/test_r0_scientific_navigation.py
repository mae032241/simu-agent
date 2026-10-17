"""Goals and exact source lineage survive the public task/control/UI chain."""
import json

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_hypothesis_objective_boundary import _foundation


def test_plugin_defaults_publish_goals_and_assessments():
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as G
    from tcad_artifact.plugin import PLUGIN as T
    from curve_score.plugin import PLUGIN as C
    from curve_figure_evidence.plugin import PLUGIN as F
    catalog = compile_catalog((CORE_PLUGIN,G,T,C,F))
    for key in ('science.evidence.extract.figure.v3','tcad.parameter.evidence.extract.v1'):
        fields = catalog.operation(key).spec.decision_fields
        assert any('closure_requirements' in field for field in fields)
    for key in ('science.result.diagnose.v1','tcad.result.analyze.v1'):
        fields = catalog.operation(key).spec.decision_fields
        assert {'objective_assessment','hypothesis_assessments'} <= set(fields)
