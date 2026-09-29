"""Goals and exact source lineage survive the public task/control/UI chain."""
import json

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_views import build_presentation
from tests.operations.test_instance_presentations import view
from tests.operations.test_hypothesis_objective_boundary import _foundation
from tests.operations.test_frozen_input_execution import _system


def test_intake_audit_derives_originals_and_goal_runs_follow_exact_sources(tmp_path, monkeypatch):
    runtime, instance, root, request = _system(tmp_path, monkeypatch)
    original = runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='artifact', name='source')).ref
    related, omitted = runtime.runs.goal_related_runs(instance_id=instance.instance_id, artifact_ref=original)
    assert not omitted
    names = {runtime.scheduler_bindings.find_name(instance=instance.instance_id, namespace='run', object_id=run.run_id) for run in related}
    assert names == {'author','auditor'}
    audit = runtime.runs.status(root.facade._binding('run','auditor').object_id)
    assert next(item.artifact_ref for item in audit.inputs if item.port_name == 'source_material') == original
    other = runtime.scheduler_bindings.create_instance(name='other',title='Other',objective='Different goal')
    assert runtime.runs.goal_related_runs(instance_id=other.instance_id, artifact_ref=original)[0] == ()
    _, truncated = runtime.runs.goal_related_runs(instance_id=instance.instance_id, artifact_ref=original, source_limit=1)
    assert truncated
    # A task using old evidence but an explicit different goal must not be
    # classified as progress on the old goal.
    objective = runtime.artifacts.register(canonical_json(json.loads(_foundation())['objective_contract']),
        ArtifactRegistration(kind='scientific',schema_id='scidiscovery.research-objective.v1',payload_schema_version=1,
            media_type='application/json',creator=runtime.actor),idempotency_key='different-objective')
    runtime.scheduler_bindings.bind(instance=instance.instance_id,namespace='artifact',name='different-goal',object_id=objective.artifact_id)
    root.call_tool('operation_invoke', {'name':'different-task','operation_id':'science.experiment.v1',
        'instruction':'Diagnose a separate scientific objective.', 'inputs':[
            {'port':'subject','artifact_names':['different-goal']},
            {'port':'scientific_materials','artifact_names':['author.output']}]})
    scoped, _ = runtime.runs.goal_related_runs(instance_id=instance.instance_id,artifact_ref=original)
    assert 'different-task' not in {runtime.scheduler_bindings.find_name(instance=instance.instance_id,
        namespace='run',object_id=item.run_id) for item in scoped}
    fresh = runtime.artifacts.register(b'Unrelated goal', ArtifactRegistration(kind='source',schema_id='opaque',
        payload_schema_version=1,media_type='text/plain',creator=runtime.actor), idempotency_key='unrelated')
    assert runtime.runs.goal_related_runs(instance_id=instance.instance_id, artifact_ref=fresh.ref)[0] == ()
    raw = runtime.artifacts.read(runtime.artifacts.get_by_id(root.facade._binding('artifact','author.output').object_id).ref)
    orphan = runtime.artifacts.register(raw, ArtifactRegistration(kind='scientific',schema_id='scidiscovery.scientific-intake.v1',
        payload_schema_version=1,media_type='application/json',creator=runtime.actor), idempotency_key='orphan')
    runtime.scheduler_bindings.bind(instance=instance.instance_id,namespace='artifact',name='orphan',object_id=orphan.artifact_id)
    preflight = root.call_tool('operation_preflight', {'name':'orphan-audit','operation_id':'science.evidence.audit.intake.v1',
        'instruction':'Audit the exact source.', 'inputs':[{'port':'scientific_intake','artifact_names':['orphan']}]})
    assert not preflight['admissible']


def test_embedded_goal_and_completion_conditions_have_ui_citations():
    foundation = json.loads(_foundation())
    marker = 'EXACT_COMPLETION_CONDITION'
    foundation['objective_contract']['closure_requirements'][0]['description'] = marker
    for schema, payload in [('scidiscovery.scientific-foundation.v1',foundation),
                            ('scidiscovery.scientific-intake.v1',{'scientific_foundation':foundation})]:
        projected = build_presentation([view('frozen',schema,payload)])
        assert marker in json.dumps(projected)
        assert 'objective_contract' in json.dumps(projected)


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
