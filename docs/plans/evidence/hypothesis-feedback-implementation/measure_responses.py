"""Isolated fixture response measurements; no production tools or external solver."""
import json
from pathlib import Path
import tempfile
import sys, tomllib
repository = Path(__file__).resolve().parents[4]
configuration = tomllib.loads((repository/'pyproject.toml').read_text())
sys.path[:0] = [str(repository)] + [str(repository/path) for path in configuration['tool']['pytest']['ini_options']['pythonpath']]
from pytest import MonkeyPatch
from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, raw_request, analysis_report, write_analysis


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def measure(old, new):
    return dict(full_json_bytes=size(old), summary_json_bytes=size(new),
                reduction_percent=round(100*(1-size(new)/size(old)), 2))


with tempfile.TemporaryDirectory(prefix='scid-response-measure-') as directory, MonkeyPatch.context() as patch:
    base = Path(directory)
    (base/"execution").mkdir()
    (base/"analysis").mkdir()
    runtime, _, adapter, _, root, _ = _setup(base/'execution')
    _create_effect(root, name='fixture')
    _decide_execution_approval(runtime, root, name='fixture')
    root.call_tool('execution_start', {'name':'fixture'})
    # Same two log-tail entries as a runner exporting stdout and solver_log.
    patch.setattr(adapter, 'status_details', lambda _: {'state':'running','progress':dict(elapsed_seconds=19,
        log_tails=[dict(name=name, text='solver iteration\n'*128) for name in ('stdout','solver_log')])}, raising=False)
    short = root.call_tool('execution_sync', {'name':'fixture'})
    full = root.call_tool('execution_status', {'name':'fixture', 'view':'detail'})
    assert short['state'] == full['state'] and short['progress']['elapsed_seconds'] == full['progress']['elapsed_seconds']
    measurements = {'execution_status_sync':measure(full, short)}
    measurements['execution_poll_decision'] = dict(old_calls=1, new_calls=1, decision_fields=['state','elapsed_seconds','collection/observation errors'])
    catalog, runtime, root, request, *_ = system = analysis_system(base/'analysis')
    complete_catalog = root.facade.operation_catalog(scope='public')
    first_page = root.call_tool('operation_catalog', {'scope':'public'})
    measurements['operation_catalog_first_page'] = measure(complete_catalog, first_page)
    pages = [first_page]
    while pages[-1]['next_before'] is not None:
        pages.append(root.call_tool('operation_catalog', {'scope':'public', 'before':pages[-1]['next_before']}))
    selected_contract = root.call_tool('operation_catalog', dict(operation_id='science.hypothesis.propose.v1', view='detail'))
    measurements['catalog_decision'] = dict(old_calls=1, new_calls=len(pages)+1,
        old_json_bytes=size(complete_catalog), new_json_bytes=sum(map(size,pages))+size(selected_contract),
        covered_operations=sum(len(p['operations']) for p in pages),
        note='All public summaries plus the full selected proposal contract. First-page reduction alone is not equivalent coverage.')
    worker, opened = open_analysis(system)
    record = worker.call_tool('worker_tcad_curve_score', dict(record_key='fixture',request=raw_request()))
    original = json.loads(Path(record['calculation_path']).read_bytes())
    assert original['status'] == record['status']
    measurements['curve_score'] = measure({**original, 'calculation_ref':record['calculation_ref']}, record)
    report = analysis_report()
    write_analysis(opened, report)
    sealed = worker.call_tool('worker_submit_result', {})
    assert sealed['state'] == 'completed', sealed
    full = root.call_tool('run_status', {'name':'analysis', 'view':'detail'})
    short = root.call_tool('run_status', {'name':'analysis'})
    measurements['completed_run_status'] = measure(full, short)
    selected = root.call_tool('run_status', {'name':'analysis', 'output_paths':['/overall_verdict','/summary','/limitations','/next_action']})
    measurements['analysis_decision'] = dict(old_calls=1,new_calls=1,old_json_bytes=size(full),new_json_bytes=size(selected),
        fields=['overall_verdict','summary','limitations','next_action','scheduler_signal'],
        note='Known report schema; one explicit selection call, no default full output required.')
    measurements['method'] = 'UTF-8 serialized JSON bytes of identical isolated engineering fixtures; not token telemetry or production latency.'
    Path(__file__).with_name('response-measurements.json').write_text(json.dumps(measurements,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(measurements,ensure_ascii=False))
