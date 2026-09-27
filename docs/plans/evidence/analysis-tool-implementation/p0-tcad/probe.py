import json
from pathlib import Path
import pytest
import test_l4_local_tcad as fixtures
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter


def test_no_contract_route_and_missing_analysis(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
    from tcad_artifact.execution_adapter import TCADExecutorAdapter
    original_system = fixtures._system
    def system(*args, **kwargs):
        catalog, runtime, root, capability = original_system(*args, **kwargs)
        adapter = TCADExecutorAdapter('/tmp/unused-fixture-socket')
        monkeypatch.setattr(adapter, '_call', lambda method, args: {'capabilities': [capability.public_snapshot().model_dump(mode='json')]})
        root.facade.execution_bridge = ExecutionBridge(runtime.executions, adapters={'tcad_artifact:tcad': adapter})
        return catalog, runtime, root, capability
    monkeypatch.setattr(fixtures, '_system', system)
    original = RootMCPRouter.call_tool
    observations = []
    def capture(self, name, arguments):
        result = original(self, name, arguments)
        if name == 'operation_invoke' and arguments['operation_id'] == 'tcad.reviewed-deck-package.v2':
            package = result['result']['outputs'][0]['artifact_name']
            probe = original(self, 'operation_preflight', {
                'name': 'no_contract_execution', 'operation_id': 'tcad.study.execute',
                'inputs': [{'port': 'reviewed_package', 'artifact_names': [package]}],
            })
            observations.append({'execute_preflight': probe})
            assert probe['admissible'] is True, probe
        return result
    monkeypatch.setattr(RootMCPRouter, 'call_tool', capture)
    fixtures.test_materialized_sprocess_author_review_package_preserves_case_anchors(tmp_path, monkeypatch)
    catalog = fixtures.compile_catalog((fixtures.CORE_PLUGIN, fixtures.SCIENCE_PLUGIN, fixtures.CURVE_PLUGIN, fixtures.TCAD_PLUGIN))
    old = catalog.operation('science.result.diagnose.v1').spec
    required = [p.name for p in old.inputs if p.min_items]
    assert 'metric_report' in required and 'curve_contract' in required
    with pytest.raises(Exception) as missing:
        catalog.operation('tcad.result.analyze.v1')
    observations.append({'old_analysis_required_ports': required, 'raw_plx_entry_missing': str(missing.value)})
    Path('/tmp/scid-tcad-analysis-p0.json').write_text(json.dumps(observations, indent=2))
