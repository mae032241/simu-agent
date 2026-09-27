"""Bounded production-entry checks for self-contained Root contracts."""
import json


def test_root_contracts_compile_and_prompt_is_self_contained():
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from curve_score.plugin import PLUGIN as curve
    from tcad_artifact.plugin import PLUGIN as tcad
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import OperationSpec, scheduler_operation_view
    from scidiscovery.artifact_agent.interfaces.mcp_response_views import operation_invoke_contract
    from scidiscovery.platforms.scheduler_prompt import load_scheduler_prompt, load_scheduler_guides
    assert "agent_context" not in OperationSpec.model_fields
    catalog = compile_catalog((CORE_PLUGIN, science, curve, tcad))
    qualification = catalog.operation('science.evidence.qualify.v1')
    projected = scheduler_operation_view(qualification.spec).model_dump(mode='json', by_alias=True)
    contract = operation_invoke_contract(projected, revision_policy=None)
    assert [port['name'] for port in contract['inputs']] == ['scientific_foundation']
    assert 'defaults' not in contract
    assert 'Major-node policy' in contract['applies_when']
    critic = catalog.operation('science.hypothesis.criticize.v1')
    assert 'scientific_foundation' not in [p.name for p in scheduler_operation_view(critic.spec).inputs]
    assert all('min_items' in port and 'max_items' in port for port in contract['inputs'])
    assert critic.spec.independent_review_ports == ('hypothesis_portfolio',)
    assert not scheduler_operation_view(critic.spec).requires_independent_review
    import pytest
    from scidiscovery.operations.catalog import CatalogCompileError
    from scidiscovery.operations.spec import InputDerivationSpec
    target = next(op for op in science.operations if op.operation_id == 'science.experiment.v1')
    for change, expected in (({'agent_visible':False}, 'hidden_input_requires_control_derivation'),
                             ({'derivation':InputDerivationSpec(anchor_port='research_objective')}, 'input_derivation_invalid')):
        invalid = target.model_copy(update={'inputs':tuple(port.model_copy(update=change)
            if port.name == 'research_objective' else port for port in target.inputs)})
        plugin = science.model_copy(update={'operations':tuple(invalid if op.operation_id == target.operation_id else op for op in science.operations)})
        with pytest.raises(CatalogCompileError) as rejected:
            compile_catalog((CORE_PLUGIN, plugin, curve, tcad))
        assert rejected.value.reason_code == expected
    assert 'Read the applicable guide BEFORE' not in load_scheduler_prompt()
    assert 'normal work requires no guide files' in load_scheduler_prompt()
    assert 'dispatch.md' in load_scheduler_guides()


def test_root_default_decision_and_exact_origin_binding(tmp_path, monkeypatch):
    import pytest
    from tests.operations.test_r4_experiment_task import _real_experiment
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from curve_score.plugin import PLUGIN as curve
    from tcad_artifact.plugin import PLUGIN as tcad
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import InputDerivationSpec
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    runtime, root, original, _, instance = _real_experiment(tmp_path, monkeypatch)
    response = root.call_tool('run_status', {'name':'observe'})
    assert response['state'] == 'completed'
    selected = {item['pointer']:item for item in response['selected_output']['items']}
    assert selected['/summary']['value'] == 'Observed fixture.'
    assert selected['/limitations']['status'] == 'missing'  # No invented limitations.
    assert root.call_tool('run_status', {'name': 'observe', "intent": 'status'})['state'] == 'completed'
    assert 'selected_output' not in root.call_tool('run_status', {'name': 'observe', "intent": 'status'})
    requested = root.call_tool('run_status', {'name':'observe', 'output_fields':['outcome']})
    assert requested['selected_output']['items'][0]['value'] == 'completed'
    operations = []
    for operation in science.operations:
        if operation.operation_id == 'science.experiment.v1':
            operation = operation.model_copy(update={'inputs':tuple(
                port.model_copy(update={'derivation':InputDerivationSpec(anchor_port='prior_experiment', producer_input_path=('research_objective',))})
                if port.name == 'research_objective' else port for port in operation.inputs)})
        operations.append(operation)
    catalog = compile_catalog((CORE_PLUGIN, science.model_copy(update={'operations':tuple(operations)}), curve, tcad))
    root.facade._operation_catalog = catalog
    runtime.runs.operation_catalog = catalog
    request = {'name':'follow', 'operation_id':'science.experiment.v1',
        'inputs':[{'port':'prior_experiment','artifact_names':['observe.output']}],
        'instruction':'Reconsider the exact observation.'}
    created = root.call_tool('operation_invoke', request)
    assert created['result']['state'] == 'queued'
    assert created['result']['dispatch']['attachment']['name'] == 'follow'
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='follow')
    bound = runtime.runs.status(run_id)
    original_run = runtime.runs.status(runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='observe'))
    assert next(i.artifact_ref for i in bound.inputs if i.port_name=='research_objective') == next(i.artifact_ref for i in original_run.inputs if i.port_name=='research_objective')
    assert root.call_tool('operation_invoke', request)['result']['name'] == 'follow'
    with pytest.raises(RootToolError) as missing:
        root.call_tool('operation_invoke', {**request, 'name':'missing', 'inputs':[]})
    assert 'input_origin_missing' in str(missing.value)
    with pytest.raises(RootToolError) as manual:
        root.call_tool('operation_invoke', {**request, 'name':'manual', 'inputs':request['inputs']+[{'port':'research_objective','artifact_names':['objective']}]})
    assert 'input_port_unknown' in str(manual.value)


def test_control_receipt_recovery_uses_records_not_public_workspace(tmp_path, monkeypatch):
    from pathlib import Path
    from tests.operations.test_r4_experiment_task import _real_experiment
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch)
    root.call_tool('artifact_ingest_text', {'name':'paper', 'text':'A bounded original observation.'})
    request = {'name':'extract', 'operation_id':'science.evidence.extract.v1', 'max_attempts':2,
        'instruction':'Read the supplied observation.', 'inputs':[{'port':'source_material','artifact_names':['paper']}]}
    root.call_tool('operation_invoke', request)
    compiled = catalog.operation(request['operation_id'])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    run_id = worker._run_id
    tool = next(t for t in compiled.worker_tools if t.name == 'worker_capture_source')
    # Exercise receipt persistence only; this does not execute a capture/network request.
    attempt = runtime.runs.begin_tool_attempt(run_id, tool, {'request':'fixture'})
    runtime.runs.finish_tool_attempt(run_id, attempt, sources={}, result_status='computed', response={'value':1})
    runtime.runs._prepare_evidence_snapshot(run_id)
    index = Path(opened['workspace_path']) / 'output/tool-evidence.json'
    assert set(json.loads(index.read_bytes())) == {'materials'}
    assert b'operation_digest' not in index.read_bytes()
    value = runtime.runs.status(run_id)
    runtime.runs.record_failure(run_id, reason='Fixture interruption.', expected_state='running', expected_last_activity_at=value.last_activity_at)
    root.call_tool('operation_invoke', {**request, 'name':'continued', 'draft_from':'extract'})
    next_worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    next_worker.call_tool('worker_open_assignment', {})
    proof = runtime.runs.recovery_tool_proof(runtime.runs.status(next_worker._run_id))
    assert proof.attempts[0].attempt_key == attempt['attempt_key']
    assert proof.attempts[0].state == 'completed'
    assert proof.operation_digest == compiled.digest
    assert runtime.runs.tool_attempts(next_worker._run_id) == []


def test_qualification_derives_exact_sources_and_rejects_old_audit(tmp_path, monkeypatch):
    from pathlib import Path
    import pytest
    from tests.operations.test_r4_experiment_task import _real_experiment
    from tests.operations.test_general_transform_operations import _intake
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from curve_score.plugin import PLUGIN as curve
    from tcad_artifact.plugin import PLUGIN as tcad
    from scidiscovery.operations.catalog import compile_catalog
    runtime, root, catalog, connections, instance = _real_experiment(tmp_path, monkeypatch)
    root.call_tool('artifact_ingest_text', {'name':'paper', 'text':'One frozen target observation.'})

    def complete(name, operation, inputs, payload):
        created = root.call_tool('operation_invoke', {'name':name, 'operation_id':operation,
            'inputs':[{'port':port, 'artifact_names':[source]} for port, source in inputs.items()],
            'instruction':'Use these exact frozen observations.'})
        assert created['result']['state'] == 'queued'
        run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name=name)
        connections.attach(run_id=run_id, platform_session='session', thread_id=name)
        compiled = catalog.operation(operation)
        from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
        services = bind_experiment_services(runtime.runs, compiled,
            dict(runtime.runs.experiment_executions.worker_services))
        worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation,
            operation_digest=compiled.digest, run_id=run_id, trusted_caller=('session',name),
            tool_services=services)
        opened = worker.call_tool('worker_open_assignment', {})
        Path(opened['output_directory'], 'result.json').write_text(json.dumps({
            'schema_version':1, 'payload':payload,
            'handoff':{'verdict':'pass', 'summary':'Exact frozen source fixture.'}}))
        assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
        return root.call_tool('run_status', {'name':name})['output_artifact_name']

    intake_payload = json.loads(_intake().model_dump_json().replace('"paper"', '"source_material"'))
    objective_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='artifact', name='objective')
    objective = json.loads(runtime.artifacts.read(runtime.artifacts.get_by_id(objective_id).ref))
    intake_payload['scientific_foundation']['objective_contract'] = objective
    intake_payload['scientific_foundation']['objective'] = objective['statement']
    intake_payload['problem_frame']['objective'] = objective['statement']
    intake = complete('qualified_author', 'science.evidence.extract.v1', {'source_material':'paper'}, intake_payload)
    status = root.call_tool('run_status', {'name':'qualified_author'})
    assert status['selected_output']['items'][0]['value'] == 'One target is frozen.'
    audit = complete('qualified_auditor', 'science.evidence.audit.intake.v1',
        {'scientific_intake':intake, 'source_material':'paper'},
        {'checks':[{'check_key':'source_traceability', 'subject':'Frozen source',
            'status':'pass', 'basis':'Exact fixture source.', 'evidence_keys':['source_material']}],
         'evidence':[{'source_key':'source_material', 'source_type':'frozen_input', 'locator':'line 1'}]})
    root.call_tool('operation_invoke', {'name':'split', 'operation_id':'science.intake.split.v1',
        'inputs':[{'port':'scientific_intake', 'artifact_names':[intake]},
                  {'port':'evidence_audit', 'artifact_names':[audit]}]})
    hypothesis = {'name':'unqualified_hypothesis', 'operation_id':'science.hypothesis.propose.v1',
        'instruction':'Propose a bounded hypothesis.', 'inputs':[
            {'port':'problem_frame', 'artifact_names':['split']},
            {'port':'scientific_foundation', 'artifact_names':['split.scientific_foundation']}]}
    refused = root.call_tool('operation_preflight', hypothesis)
    assert not refused['admissible']
    assert refused['reason_code'] == 'input_cohort_approval_missing', refused
    assert '$.inputs.scientific_foundation' in json.dumps(refused)
    assert 'qualified_foundation' not in json.dumps(refused)
    assert 'qualification' in json.dumps(refused)
    with pytest.raises(RootToolError) as admission:
        root.call_tool('operation_invoke', hypothesis)
    assert '$.inputs.scientific_foundation' in json.dumps(admission.value.details)
    assert 'qualified_foundation' not in json.dumps(admission.value.details)

    # Actual Run -> Transform -> original Run, with the transform on hop two.
    # The extra input is declared on the existing experiment to exercise the
    # common compiler/invoke mechanism without creating another public task.
    prior = complete('foundation_consumer', 'science.experiment.v1',
        {'research_objective':'objective', 'scientific_materials':'split.scientific_foundation'},
        {'summary':'The fixture requires another observation.', 'outcome':'blocked',
         'limitations':['No new execution was requested.'], 'remaining_question':'Which observation is needed?'})
    from scidiscovery.operations.spec import InputDerivationSpec
    original_input = next(port for port in catalog.operation('science.evidence.audit.intake.v1').spec.inputs
        if port.name == 'scientific_intake')
    def chain_catalog(last_edge):
        derived = original_input.model_copy(update={'name':'original_intake',
            'derivation':InputDerivationSpec(anchor_port='prior_experiment',
                producer_input_path=('scientific_materials', last_edge))})
        changed = science.model_copy(update={'operations':tuple(
            op.model_copy(update={'inputs':(*op.inputs, derived)})
            if op.operation_id == 'science.experiment.v1' else op for op in science.operations)})
        return compile_catalog((CORE_PLUGIN, changed, curve, tcad))
    runtime.runs.operation_catalog = root.facade._operation_catalog = chain_catalog('scientific_intake')
    chained = {'name':'multi_hop', 'operation_id':'science.experiment.v1',
        'instruction':'Use the exact original evidence.', 'inputs':[
            {'port':'research_objective', 'artifact_names':['objective']},
            {'port':'prior_experiment', 'artifact_names':[prior]}]}
    assert root.call_tool('operation_invoke', chained)['result']['state'] == 'queued'
    bound = runtime.runs.status(runtime.scheduler_bindings.resolve(instance=instance.instance_id,
        namespace='run', name='multi_hop'))
    expected = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='artifact', name=intake)
    assert next(item.artifact_ref.artifact_id for item in bound.inputs if item.port_name == 'original_intake') == expected
    runtime.runs.operation_catalog = root.facade._operation_catalog = chain_catalog('absent_original')
    missing = {**chained, 'name':'missing_original'}
    rejected = root.call_tool('operation_preflight', missing)
    assert not rejected['admissible'] and rejected['reason_code'] == 'input_origin_missing', rejected
    assert '$.inputs.prior_experiment' in json.dumps(rejected)
    assert 'original_intake' not in json.dumps(rejected)
    with pytest.raises(RootToolError):
        root.call_tool('operation_invoke', missing)
    runtime.runs.operation_catalog = root.facade._operation_catalog = catalog
    request = {'name':'qualification', 'operation_id':'science.evidence.qualify.v1',
        'inputs':[{'port':'scientific_foundation', 'artifact_names':['split.scientific_foundation']}]}
    assert root.call_tool('operation_preflight', request)['admissible']
    assert root.call_tool('operation_invoke', request)['executor_kind'] == 'approval'
    assert root.call_tool('operation_invoke', request)['executor_kind'] == 'approval'
    upgraded = science.model_copy(update={'operations':tuple(
        op.model_copy(update={'version':'auditor-upgrade'}) if op.operation_id == 'science.evidence.audit.intake.v1' else op
        for op in science.operations)})
    runtime.runs.operation_catalog = root.facade._operation_catalog = compile_catalog((CORE_PLUGIN, upgraded, curve, tcad))
    request = {**request, 'name':'old_audit_qualification'}
    before = runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='approval')
    refused = root.call_tool('operation_preflight', request)
    assert not refused['admissible'], refused
    with pytest.raises(RootToolError):
        root.call_tool('operation_invoke', request)
    assert runtime.scheduler_bindings.list(instance=instance.instance_id, namespace='approval') == before


def test_failed_run_safe_reason_and_diagnostic_pagination(tmp_path, monkeypatch):
    from tests.operations.test_r4_experiment_task import _real_experiment
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch)
    root.call_tool('artifact_ingest_text', {'name':'paper', 'text':'One observation.'})
    root.call_tool('operation_invoke', {'name':'bad_output', 'operation_id':'science.evidence.extract.v1',
        'instruction':'Read the supplied observation.', 'inputs':[{'port':'source_material', 'artifact_names':['paper']}]})
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='bad_output')
    secret = '/private/workspace/identity-secret'
    for _ in range(2):
        runtime.runs.record_error_observation(run_id, 'output_rejected', diagnostic={
            'category':'output_rejected', 'details':[{'path':'$.scientific_foundation.summary', 'type':'missing',
                'message':secret}], 'engineering':{'reference':secret, 'artifact_ref':run_id}})
    value = runtime.runs.status(run_id)
    runtime.runs.record_failure(run_id, reason=secret, category='output_rejected',
        expected_state=value.state, expected_last_activity_at=value.last_activity_at,
        engineering={'reference':secret})
    request = {'name':'bad_output', 'intent':'status', 'diagnostic_after':0, 'diagnostic_limit':1}
    first = root.call_tool('run_status', request)
    assert 'declared contract' in first['reason']
    events = first['diagnostic_events']
    assert len(events['events']) == 1 and events['next_after'] is not None
    detail = events['events'][0]['diagnostic']['details'][0]
    assert detail['path'] == '$.scientific_foundation.summary'
    assert detail['message'] == 'Required field is missing.'
    second = root.call_tool('run_status', {**request, 'diagnostic_after':events['next_after']})
    assert second['diagnostic_events']['events'][0]['event_id'] > events['events'][0]['event_id']
    last = root.call_tool('run_status', {**request, 'diagnostic_after':second['diagnostic_events']['next_after']})
    assert last['diagnostic_events']['next_after'] is None
    public = json.dumps([first,second,last,root.call_tool('run_status', {'name':'bad_output'})])
    assert secret not in public and run_id not in public and 'engineering' not in public
    # The maintenance truth is retained, not erased to make the public check pass.
    assert secret in json.dumps(runtime.runs.diagnostic_events(runtime.runs.status(run_id)))


def test_execution_surface_has_one_declaration_projection_and_no_default_call_bypass():
    from types import SimpleNamespace
    from unittest.mock import Mock
    import pytest
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolError, ROOT_TOOLS
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_unified_mcp import rpc, result
    handler = Mock(return_value={"name":"standalone", "state":"collected"})
    facade = SimpleNamespace(runs=SimpleNamespace(worker_connections=SimpleNamespace()),
        execution_status=handler, session_key=None, _instance_id=lambda:"fixture",
        engineering_diagnostics=SimpleNamespace(capture=Mock()),
        operation_catalog=lambda **_: {"scope":"all", "operations":[]})
    root = RootMCPRouter(facade)
    for surface in ("research", "execution"):
        assert {t["name"] for t in root.list_tools(surface=surface)} == {
            t.name for t in ROOT_TOOLS if t.surface == surface}
    assert "execution_status" not in {t["name"] for t in root.list_tools()}
    with pytest.raises(RootToolError):
        root.call_tool("execution_status", {"name":"standalone"})
    handler.assert_not_called()
    gateway = UnifiedMCPRouter(root)
    catalog = result(rpc(gateway, "scid_catalog", {"kind":"interfaces", "surface":"execution"}))
    assert {t["name"] for t in catalog["entries"]} == {t.name for t in ROOT_TOOLS if t.surface == "execution"}
    described = result(rpc(gateway, "scid_describe", {"name":"execution_status", "surface":"execution"}))
    assert described["name"] == "execution_status"
    assert "error" in rpc(gateway, "scid_describe", {"name":"execution_status"})
    assert "error" in rpc(gateway, "scid_call", {"name":"execution_status", "arguments":{"name":"standalone"}})
    response = result(rpc(gateway, "scid_call", {"name":"execution_status", "surface":"execution", "arguments":{"name":"standalone"}}))
    assert response["state"] == "collected"
    for method, args in (("scid_catalog", {"kind":"interfaces"}),
                         ("scid_describe", {"name":"execution_status"}),
                         ("scid_call", {"name":"execution_status", "arguments":{"name":"standalone"}})):
        reply = rpc(gateway, method, {**args, "surface":"execution"}, child="helper")
        assert "execution surface is available only to Root" in reply["error"]["message"]
    assert handler.call_count == 1


def test_execution_capability_cannot_select_internal_compiled_effect():
    from types import SimpleNamespace
    from unittest.mock import Mock
    import pytest
    from scidiscovery.artifact_agent.interfaces.mcp_root_execution_routes import RootExecutionRoutes
    from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import RootOperationRoutes
    from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError

    class Fixture(RootExecutionRoutes, RootOperationRoutes):
        pass

    facade = Fixture()
    facade._operation_catalog = SimpleNamespace(operation=lambda _: SimpleNamespace(
        spec=SimpleNamespace(catalog_scope="internal")))
    facade.execution_bridge = SimpleNamespace(capabilities=Mock())
    with pytest.raises(RootToolError, match="not available to Root"):
        facade.execution_capabilities(operation_id="internal.effect.v1")
    facade.execution_bridge.capabilities.assert_not_called()
