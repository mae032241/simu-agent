"""Author forms, automatic plan identities, and real Worker sealing agree."""
import json
from pathlib import Path
import pytest
from scidiscovery.artifact_agent.schema.common import canonical_json


def test_multiple_plan_choices_are_explicit_and_wrong_identity_rejected():
    from tcad_artifact.analysis_bindings import analysis_draft_schema, complete_plan_identity
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
    from scidiscovery.artifact_agent.schema.role_result import RoleResultEnvelope
    schema = RoleResultEnvelope[LayeredDiagnosisReport].model_json_schema()
    # Use the same payload schema layout as the real assignment compiler.
    schema['properties']['payload'] = LayeredDiagnosisReport.model_json_schema()
    choices = [{'plan_key':'p1', 'experiment_key':'a'}, {'plan_key':'p2','experiment_key':'b'}]
    plan = {'validation_plans':choices}
    form = analysis_draft_schema(schema, 'scidiscovery.layered-diagnosis.v1', {'package':'execution_package'},
        {'package':canonical_json({'project':{'execution_plan':plan}})})['properties']['payload']
    assert set(('plan_key','experiment_key')) <= set(form['required'])
    assert [{key:item[key] for key in ('plan_key','experiment_key')}
            for item in form['x-scidiscovery-validation-plans']] == choices
    assert form['x-scidiscovery-validation-plans'][1]['pointer'] == '/project/execution_plan/validation_plans/1'
    with pytest.raises(WorkspaceProtocolError):
        complete_plan_identity({'plan_key':'wrong'}, {'validation_plans':choices[:1]})
