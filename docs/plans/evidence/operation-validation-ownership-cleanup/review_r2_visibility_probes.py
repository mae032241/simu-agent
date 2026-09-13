import json

def test_pre_dispatch_failure_is_visible_through_root(tmp_path, monkeypatch):
    from tests.operations.test_l4_local_tcad import _system
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
    _, runtime, root, _ = _system(tmp_path)
    run_ids = []
    reason = 'admitted execution_capability is invalid JSON'
    def fail(compiled, run_id, workspace):
        run_ids.append(run_id)
        raise RunCheckerError(reason, category='admission_defect')
    monkeypatch.setattr(runtime.runs, '_materialize_workspace', fail)
    wire = MCPRouter(root, name='review-visibility')
    request = {'name': 'preparation_fault', 'operation_id': 'tcad.deck.author.initial.v1',
        'inputs': [{'port': 'execution_capability', 'artifact_names': ['execution_capability']},
                   {'port': 'experiment_plan', 'artifact_names': ['experiment_plan']}],
        'instruction': 'Implement the bound fixture plan.'}
    reply = wire.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': 'operation_invoke', 'arguments': request}})
    assert len(run_ids) == 1
    internal = runtime.runs.status(run_ids[0])
    assert internal.state == 'failed' and reason in internal.reason
    listed = root.call_tool('run_list', {})
    lookup = wire.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {'name': 'run_status', 'arguments': {'name': 'preparation_fault'}}})
    print(json.dumps({'invoke': reply, 'listed': listed, 'lookup': lookup,
        'internal_reason': internal.reason}, ensure_ascii=False))
    assert reason in json.dumps({'invoke': reply, 'listed': listed, 'lookup': lookup})
