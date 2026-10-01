"""Solver-relative names survive collection; malformed maps cannot rename originals."""
import json

import pytest

from tests.operations.test_r4_experiment_task import _real_experiment


@pytest.mark.parametrize('damage', ['absolute_path', 'digest', 'duplicate'])
def test_task_status_withholds_inconsistent_inventory_without_resubmitting(tmp_path, monkeypatch, damage):
    def check(runtime, root, worker, instance, workspace, catalog, collected):
        assert {item['file_name'] for item in collected['outputs']} == {
            'case-A/final.tdr', 'case-A/profile_480s.txt'}
        execution = next(b.object_id for b in runtime.scheduler_bindings.list(
            instance=instance.instance_id, namespace='execution')
            if runtime.executions.status(b.object_id).state == 'collected')
        inventory = next(o for o in runtime.executions.outputs(execution) if o.logical_name == 'tcad_manifest')
        original_read = runtime.artifacts.read
        ref = runtime.artifacts.get_by_id(inventory.artifact_id).ref
        document = json.loads(original_read(ref))
        if damage == 'absolute_path':
            document['outputs'][0]['relative_path'] = '/private/remote/work/output.txt'
        elif damage == 'digest':
            document['outputs'][0]['sha256'] = 'f' * 64
        else:
            document['outputs'].append(document['outputs'][0])
        with monkeypatch.context() as patch:
            patch.setattr(runtime.artifacts, 'read', lambda target:
                json.dumps(document).encode() if target == ref else original_read(target))
            status = worker.call_tool('worker_experiment_execute', {'action': 'status'})
            assert status['state'] == 'collected'
            assert not any('file_name' in item for item in status['outputs'])
            assert 'original filenames are withheld' in status['output_inventory_note']
            assert '/private/remote' not in json.dumps(status)
        assert runtime.executions.status(execution).state == 'collected'
        assert worker.call_tool('worker_experiment_execute', {'action': 'status'})['state'] == 'collected'
        return []
    _real_experiment(tmp_path, monkeypatch, before_submit=check)
