"""Controlled feedback handoff; fixture outputs test transport, not LLM judgement."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _catalog, _feedback_record,
)
from tests.operations.test_general_transform_operations import _intake, _register, _root
from tests.operations.test_hypothesis_review_routing import _critic


def start(runtime, root, request):
    checked = root.call_tool('operation_preflight', request)
    assert checked['admissible'], checked
    queued = root.call_tool('operation_invoke', checked['normalized_request'])['result']
    assert queued['state'] == 'queued' and queued['agent_type'] and queued['execution_profile']
    assert 'bound_inputs' not in queued
    operation = runtime.runs.operation_catalog.operation(request['operation_id'])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=request['operation_id'], operation_digest=operation.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    return worker, opened


def seal(worker, opened, payload, verdict='pass'):
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({
        'schema_version': 1, 'payload': payload,
        'handoff': {'verdict': verdict, 'summary': 'Synthetic engineering fixture; no scientific inference.'}}))
    return worker.call_tool('worker_submit_result', {})


def request(name, operation, ports):
    return dict(name=name, operation_id=operation,
        inputs=[dict(port=k, artifact_names=v if isinstance(v, list) else [v]) for k,v in ports.items()],
        instruction='Use the exact bound records and their stated limits.')


@pytest.mark.parametrize('feedback', [False, True])
def test_feedback_proposal_critic_revision_and_design_seal_exact_cohort(tmp_path, monkeypatch, experiment_case, feedback):
    runtime, instance, root = _root(tmp_path, catalog=_catalog())
    intent, prior_sources = deepcopy(experiment_case)
    intent['objective_key'] = 'objective_expected'
    foundation_payload = _intake().scientific_foundation.model_dump(mode='json')
    foundation_payload['objective_contract'] = json.loads(prior_sources['research_objective'])
    foundation_payload['objective'] = foundation_payload['objective_contract']['statement']
    foundation = _register(runtime, instance, name='scientific_foundation', raw=canonical_json(foundation_payload),
        kind='scientific_foundation', schema='scidiscovery.scientific-foundation.v1')
    for port, schema in (('research_objective', 'scidiscovery.research-objective.v1'),
                         ('hypothesis_portfolio', 'scidiscovery.hypothesis-proposal.v2')):
        _register(runtime, instance, name=port, raw=prior_sources[port], kind=port, schema=schema, parents=(foundation.ref,))
    monkeypatch.setattr(runtime.approvals, 'are_subjects_approved_by_provider', lambda *a, **k: True)
    # Only the existing foundation human decision is stubbed. Every new scientific
    # proposal, review and design below is submitted through the real Worker.
    foundation_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='artifact', name='scientific_foundation')
    foundation = runtime.artifacts.get_by_id(foundation_id)
    source = json.loads(runtime.artifacts.read(foundation.ref))['evidence'][0]['source_key']
    _register(runtime, instance, name='problem_frame', raw=canonical_json(_intake().problem_frame.model_dump(mode="json")),
        kind='problem_frame', schema='scidiscovery.problem-frame.v1', parents=(foundation.ref,))
    extra = {}
    if feedback:
        for name in ('failed_result', 'limited_analysis', 'history'):
            _feedback_record(runtime, instance, name, state='nonclaiming',
                raw=canonical_json({'summary':'Synthetic failed/limited observation; no physical refutation.', 'overall_verdict':'invalid_study'}))
        extra = {'experiment_results':'failed_result', 'result_analysis':'limited_analysis', 'current_progress':'history'}
    proposal = json.loads(experiment_case[1]['hypothesis_portfolio'])
    # New proposal may replace keys. Revision below must preserve this new set.
    proposal['hypotheses'][0]['hypothesis_key'] = 'hypothesis_new'
    proposal['evidence'] = [dict(source_key=k, source_type='frozen_input', locator='Exact supplied record')
                            for k in (source, 'scientific_foundation', *extra)]
    inputs = dict(problem_frame='problem_frame', scientific_foundation='scientific_foundation', **extra)
    if feedback:
        inputs['previous_hypotheses'] = 'hypothesis_portfolio'
    worker, opened = start(runtime, root, request('proposal', 'science.hypothesis.propose.v1', inputs))
    workspace = runtime.runs.backend.open(worker._run_id)
    for port, name in extra.items():
        item = next(i for i in runtime.runs.status(worker._run_id).inputs if i.port_name == port)
        assert item.artifact_name == name and item.exposure == 'on_demand' and item.usage == 'evidence_inventory'
        assert workspace.input_paths[port].read_bytes() == runtime.artifacts.read(item.artifact_ref)
    bad = deepcopy(proposal); bad['evidence'][0]['source_key'] = 'unbound_source'
    rejected = seal(worker, opened, bad)
    assert rejected['state'] == 'rejected', rejected
    assert any('source' in str(d) and d.get('path') for d in rejected['diagnostics'])
    assert seal(worker, opened, proposal)['state'] == 'completed'

    review = _critic(disposition='revise_hypothesis').model_dump(mode='json')
    review['reviews'][0]['hypothesis_key'] = 'hypothesis_new'
    review['evidence'] = deepcopy(proposal['evidence'])
    critic_inputs = dict(hypothesis_portfolio='proposal.output', scientific_foundation='scientific_foundation', **extra)
    if feedback:
        critic_inputs['previous_hypotheses'] = 'hypothesis_portfolio'
    worker, opened = start(runtime, root, request('critic', 'science.hypothesis.criticize.v1', critic_inputs))
    assert seal(worker, opened, review, 'revise')['state'] == 'completed'
    revision_inputs = dict(prior_draft='proposal.output', change_request='critic.output', scientific_foundation='scientific_foundation', **extra)
    worker, opened = start(runtime, root, request('revision', 'science.hypothesis.revise.v1', revision_inputs))
    bad = deepcopy(proposal); bad['hypotheses'][0]['hypothesis_key'] = 'different'
    rejected = seal(worker, opened, bad)
    assert rejected['state'] == 'rejected', rejected
    assert 'cannot add, remove, or rename' in str(rejected)
    proposal['hypotheses'][0]['scope'] = 'Only the supplied fixture system and its bounded intervention.'
    revised = seal(worker, opened, proposal)
    assert revised['state'] == 'completed', revised
    review['disposition'] = 'ready_for_experiment'
    review['reviews'][0].update(physical_plausibility='pass', falsifiability='pass', finite_discriminability='pass')
    critic_inputs['hypothesis_portfolio'] = 'revision.output'
    worker, opened = start(runtime, root, request('final_critic', 'science.hypothesis.criticize.v1', critic_inputs))
    assert seal(worker, opened, review)['state'] == 'completed'

    design_inputs = dict(scientific_foundation='scientific_foundation', research_objective='research_objective',
        hypothesis_portfolio='revision.output', critic_review='final_critic.output', **extra)
    # A passing critic for the OLD proposal cannot qualify the revised portfolio.
    worker, opened = start(runtime, root, request('old_ready_critic', 'science.hypothesis.criticize.v1',
        {**critic_inputs, 'hypothesis_portfolio':'proposal.output'}))
    assert seal(worker, opened, review)['state'] == 'completed'
    wrong = request('wrong_design', 'science.experiment.design.v1', {**design_inputs, 'critic_review':'old_ready_critic.output'})
    rejected = root.call_tool('operation_preflight', wrong)
    assert not rejected['admissible'], rejected
    assert rejected['reason_code'] != 'input_critic_disposition_invalid', rejected
    worker, opened = start(runtime, root, request('design', 'science.experiment.design.v1', design_inputs))
    intent = json.loads(json.dumps(intent).replace('hypothesis_a', 'hypothesis_new'))
    submitted = seal(worker, opened, intent)
    assert submitted['state'] == 'completed', submitted
    # Explicit reads preserve exact bindings and scientific payloads after summary defaults.
    short = root.call_tool('run_status', {'name':'design'})
    assert 'sealed_output' not in short and 'bound_inputs' not in short
    full = root.call_tool('run_status', {'name':'design', 'view':'detail'})
    assert full['sealed_output']['payload']['selected_hypothesis_keys'] == ['hypothesis_new']
    assert {p['port']:p['artifact_names'] for p in full['bound_inputs']}['hypothesis_portfolio'] == ['revision.output']
    materialize = request('materialized', 'science.experiment.materialize.v1', dict(
        experiment_design_intent='design.output', scientific_foundation='scientific_foundation',
        research_objective='research_objective', hypothesis_portfolio='revision.output', critic_review='final_critic.output'))
    materialize.pop('instruction')
    checked = root.call_tool('operation_preflight', materialize)
    assert checked['admissible'], checked
    result = root.call_tool('operation_invoke', materialize)
    assert result['executor_kind'] == 'transform', result
