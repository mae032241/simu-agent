"""Original goals are readable context, not repeated output registration."""
import json
from pathlib import Path

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from tests.operations.m3_transform_equivalence_runner import _engineering_intent
from tests.operations.test_general_transform_operations import _root, _register, _catalog
from tests.operations.test_hypothesis_objective_boundary import _foundation


def test_engineering_plan_review_reads_original_goal_without_equating_stage_goal(tmp_path):
    runtime, instance, root = _root(tmp_path)
    plan, _ = materialize_experiment_plan({'experiment_design_intent': _engineering_intent()})
    objective = canonical_json(json.loads(_foundation())['objective_contract'])
    assert json.loads(plan)['objective_key'] is None
    assert json.loads(plan)['objective'] != json.loads(objective)['statement']
    for name, raw, kind, schema in (
        ('plan', plan, 'experiment_portfolio', 'scidiscovery.experiment-portfolio.v1'),
        ('goal', objective, 'research_objective', 'scidiscovery.research-objective.v1'),
    ):
        _register(runtime, instance, name=name, raw=raw, kind=kind, schema=schema)
    request = dict(name='review', operation_id='science.object.review.v1',
        instruction='Review this bounded engineering prerequisite against the original research goal.', inputs=[
        dict(port='experiment_plan', artifact_names=['plan']),
        dict(port='research_objective', artifact_names=['goal']),
    ])
    checked = root.call_tool('operation_preflight', request)
    assert checked['admissible'], checked
    root.call_tool('operation_invoke', checked.get('normalized_request', request))
    compiled = _catalog().operation(request['operation_id'])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    binding = next(i for i in assignment['inputs'] if i['port'] == 'research_objective')
    assert (Path(opened['workspace_path']) / binding['relative_path']).read_bytes() == objective
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(
        schema_version=1, payload=dict(review_target='experiment_portfolio',
            verdict='revise', summary='Synthetic review: assess stage relevance separately from goal identity.'))))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    # Missing references and wrong schema remain admission failures.
    for name in ('absent', 'plan'):
        invalid = dict(request, name='invalid', inputs=[request['inputs'][0],
            dict(port='research_objective', artifact_names=[name])])
        assert not root.call_tool('operation_preflight', invalid)['admissible']
