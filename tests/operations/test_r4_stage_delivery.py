"""Read real sealed experiment deliveries through Root, workbench and API routes."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from tests.operations.test_r4_experiment_task import _real_experiment
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.workbench_render import render_node
from scidiscovery.artifact_agent.service.stage_deliveries import read_stage_deliveries


def _model(runtime, catalog):
    return InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=catalog)


def _snapshot(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob('*') if path.is_file()}


def _pages(root):
    items, offset = [], 0
    while True:
        page = root.call_tool('run_status', {'name': 'observe', 'stage_offset': offset, 'stage_limit': 2})['sealed_stages']
        assert len(json.dumps(page, ensure_ascii=False).encode()) < 40 * 1024
        items.extend(page['items'])
        if page['next_offset'] is None:
            assert len(items) == page['total']
            return items
        assert page['next_offset'] > offset
        offset = page['next_offset']


def test_running_and_final_deliveries_share_readonly_scientific_projection(tmp_path, monkeypatch):
    adopted = []
    def during(runtime, root, worker, instance, workspace, catalog, collected):
        stage = {'stage': 'execution', 'conclusion': 'Author interpretation <script>unsafe</script>',
            'remaining_question': 'Need independent physical validation.', 'materials': [collected['reference']]}
        first = worker.call_tool('worker_experiment_stage', stage)
        assert worker.call_tool('worker_experiment_stage', stage) == first
        second = worker.call_tool('worker_experiment_stage', {**stage, 'conclusion': 'Revised interpretation.'})
        adopted.append(second['reference'])
        (workspace / 'scratch/unsealed.json').write_text('{"conclusion":"DRAFT_MUST_NOT_APPEAR"}')
        (workspace / 'output/result.json').write_text('{"payload":{"summary":"DRAFT_MUST_NOT_APPEAR"}}')
        model = _model(runtime, catalog)
        ui = ApprovalUI(runtime.approvals, bindings=runtime.scheduler_bindings, read_model=model,
            instance_management_secret=b'b' * 32)
        cookie = access_cookie(instance.instance_id, ui.browser_access.issue(instance.instance_id))
        handler = SimpleNamespace(headers={'Cookie': cookie})
        responses = []
        monkeypatch.setattr(ui, '_json_response', lambda handler, status, value: responses.append((status, value)))
        html_responses = []
        monkeypatch.setattr(ui, '_respond', lambda handler, status, body, *args, **kwargs: html_responses.append((status, body)))
        before = _snapshot(tmp_path / 'state')
        with monkeypatch.context() as patch:
            patch.setattr(runtime.artifacts, 'read', lambda *args: pytest.fail('Default status read a payload'))
            short = root.call_tool('run_status', {'name': 'observe'})
        assert short['state'] == 'running' and 'sealed_stages' not in short
        rows = _pages(root)
        assert len({item['reference'] for item in rows}) == len(rows)
        executions = [item for item in rows if item['stage'] == 'execution']
        assert {item['delivery_kind'] for item in executions} == {'executor_observation', 'author_conclusion'}
        authored = [item for item in executions if item['delivery_kind'] == 'author_conclusion']
        assert [item['version'] for item in authored] == [1, 2]
        assert all(item['adopted'] is None for item in rows)
        assert all('conclusion' not in item for item in rows if item['delivery_kind'] == 'executor_observation')
        view = model.node(instance.instance_id, 'run:observe', stage_offset=len(rows) - 2)
        page = view['sealed_stages']
        assert page['run_state'] == 'running' and page['final_selection'] == 'pending'
        assert page['qualification'] == 'not_evaluated' and 'sealed_output' not in view
        assert page == root.call_tool('run_status', {'name': 'observe', 'stage_offset': len(rows) - 2})['sealed_stages']
        html = render_node(view, instance_id=instance.instance_id).decode()
        assert '作者科学结论' in html and 'Need independent physical validation.' in html
        assert '<script>unsafe</script>' not in html and '&lt;script&gt;' in html
        ui._handle_instance_api(handler, ['api', 'instances', instance.instance_id, 'nodes', 'run:observe'],
            {'stage_offset': [str(len(rows) - 2)]})
        assert responses[-1][0] == 200 and responses[-1][1]['sealed_stages'] == page
        ui._handle_workbench(handler, ['instance', instance.instance_id, 'nodes', 'run:observe'],
            {'stage_offset': [str(len(rows) - 2)]})
        assert html_responses[-1][0] == 200 and b'sealed-stages' in html_responses[-1][1]
        ui._handle_workbench(handler, ['instance', instance.instance_id], {})
        assert html_responses[-1][0] == 200 and b'sealed-stages' in html_responses[-1][1]
        visible = json.dumps([rows, page, responses[-1][1]['sealed_stages']])
        for private in ('artifact_ref', 'source_ref', 'operation_digest', 'budget_owner', 'private_outputs', 'tcad_manifest', 'DRAFT_MUST_NOT_APPEAR', str(workspace)):
            assert private not in visible
        debug = next(item for item in rows if item['delivery_kind'] == 'executor_observation' and item['stage'] == 'debug')
        detail = root.call_tool('run_status', {'name': 'observe', 'stage_reference': debug['reference']})['sealed_stages']['material']
        assert 'scratch/debug' not in detail['text'] and 'log' not in json.loads(detail['text'])
        ui._handle_instance_api(SimpleNamespace(headers={}),
            ['api', 'instances', instance.instance_id, 'nodes', 'run:observe'], {})
        assert responses[-1][0] == 403
        for arguments in ({'stage_limit': ['0']}, {'stage_offset': ['-1']}, {'stage_reference': ['tool_recovery_manifest']}):
            ui._handle_instance_api(handler, ['api', 'instances', instance.instance_id, 'nodes', 'run:observe'], arguments)
            assert responses[-1][0] == 400
        value = runtime.runs.status(worker._run_id)
        with pytest.raises(PermissionError):
            read_stage_deliveries(runtime.runs, value, instance_id='another-instance', stage_offset=0)
        assert _snapshot(tmp_path / 'state') == before
        return adopted
    runtime, root, catalog, _, instance = _real_experiment(tmp_path, monkeypatch, before_submit=during)
    rows = _pages(root)
    authored = [item for item in rows if item['stage'] == 'execution' and item['delivery_kind'] == 'author_conclusion']
    assert [item['adopted'] for item in authored] == [False, True]
    final = root.call_tool('run_status', {'name': 'observe', 'stage_offset': 0})['sealed_stages']
    assert final['final_selection'] == 'sealed' and adopted[0] in final['adopted_references']
    html = render_node(_model(runtime, catalog).node(instance.instance_id, 'run:observe', stage_offset=len(rows)-2), instance_id=instance.instance_id).decode()
    assert '未被最终报告采用' in html and '最终采用' in html
    with monkeypatch.context() as patch:
        patch.setattr(runtime.artifacts, 'read', lambda *args: pytest.fail('Default status read a payload'))
        assert 'sealed_stages' not in root.call_tool('run_status', {'name': 'observe', "intent": 'status'})
    assert root.call_tool('run_status', {'name': 'observe', 'stage_offset': 0, "intent": 'navigation'})['sealed_stages'] == final


def test_large_material_pagination_and_instance_boundaries(tmp_path, monkeypatch):
    def during(runtime, root, worker, instance, workspace, catalog, collected):
        conclusion = '測' * 16384
        sealed = worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': conclusion})
        rows = _pages(root)
        assert 'conclusion' in rows[-1]['omitted_fields']
        text, offset = '', 0
        while True:
            material = root.call_tool('run_status', {'name': 'observe', 'stage_reference': sealed['reference'],
                'stage_text_offset': offset})['sealed_stages']['material']
            assert len(material['text']) <= 8192
            text += material['text']
            if material['next_text_offset'] is None:
                break
            assert material['next_text_offset'] > offset
            offset = material['next_text_offset']
        assert json.loads(text)['conclusion'] == conclusion
        second = runtime.scheduler_bindings.create_instance(name='other', title='Other', objective='Other')
        # Even a corrupt/misbound semantic name does not grant another instance's receipts.
        runtime.scheduler_bindings.bind(instance=second.instance_id, namespace='run', name='misbound', object_id=worker._run_id)
        from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
        other = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
            approvals=runtime.approvals, executions=runtime.executions,
            bindings=runtime.scheduler_bindings, instance=second.instance_id, operation_catalog=catalog))
        with pytest.raises((PermissionError, ValueError)):
            other.call_tool('run_status', {'name': 'misbound', 'stage_offset': 0})
        model = _model(runtime, catalog)
        with pytest.raises(PermissionError):
            model.node(second.instance_id, 'run:misbound')
        assert model.stage_deliveries(instance.instance_id, 'run:observe', stage_reference=sealed['reference'])['material']['reference'] == sealed['reference']
        return []
    _real_experiment(tmp_path, monkeypatch, before_submit=during)


def test_initialization_missing_outputs_are_visible_or_explicitly_omitted(tmp_path, monkeypatch):
    def during(runtime, root, worker, instance, workspace, catalog, collected):
        from tcad_artifact.local_debug_service import LocalTCADDebugService
        implementation = next(item['alias'] for item in runtime.runs.tool_evidence(worker._run_id)
            if item['metadata']['kind'] == 'experiment_implementation')
        model = _model(runtime, catalog)
        for index, missing in enumerate((['required-grid.tdr'], ['long-' + 'x' * 600, *[f'output-{n}.tdr' for n in range(9)]])):
            # Substitute diagnostic execution facts, then use the registered
            # Worker tool's real immutable seal and the production read chain.
            with monkeypatch.context() as patch:
                patch.setattr(LocalTCADDebugService, 'run', lambda *args, **kwargs: {
                    'state': 'collected', 'mode': 'initialization', 'exit_code': 0,
                    'summary': 'Solver exited; required files are absent.', 'missing_outputs': missing})
                receipt = worker.call_tool('worker_experiment_debug', {'implementation': implementation,
                    'name': f'missing-{index}', 'mode': 'initialization'})
            rows = _pages(root)
            preview = next(item for item in rows if item['reference'] == receipt['reference'])
            assert preview['missing_outputs'] == [value[:512] for value in missing[:8]]
            assert ('missing_outputs' in preview['omitted_fields']) == (index == 1)
            node = model.node(instance.instance_id, 'run:observe', stage_offset=len(rows)-1)
            assert node['sealed_stages']['items'][0] == preview
            html = render_node(node, instance_id=instance.instance_id).decode()
            assert preview['missing_outputs'][0] in html
            assert ('预览有省略，请按引用读取分段原文。' in html) == (index == 1)
            material = root.call_tool('run_status', {'name': 'observe',
                'stage_reference': receipt['reference']})['sealed_stages']['material']
            assert material['next_text_offset'] is None
            assert json.loads(material['text'])['missing_outputs'] == missing
        return []
    _real_experiment(tmp_path, monkeypatch, before_submit=during)
