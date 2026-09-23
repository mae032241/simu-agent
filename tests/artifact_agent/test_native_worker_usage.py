import importlib.util
import json
from pathlib import Path


def test_native_usage_deduplicates_and_does_not_export_bodies(tmp_path):
    source = Path(__file__).resolve().parents[2]/'docs/plans/evidence/mcp-response-levels/probe_request_usage.py'
    spec=importlib.util.spec_from_file_location('native_probe',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=[{'type':'turn_context','payload':{'model':'gpt-5.6-sol','effort':'medium'}},
        {'type':'response_item','payload':{'type':'custom_tool_call','call_id':'a','name':'exec','input':'read inputs/x.json --pointer /goal --offset 0'}},
        {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'a','output':'SECRET SCIENTIFIC BODY'}},
        {'type':'response_item','payload':{'type':'reasoning','content':'PRIVATE REASONING'}},
        {'type':'compacted','payload':{'message':'PRIVATE COMPACTION'}}]
    usage={'type':'token_usage_record','payload':{'response_id':'one','usage':{'input_tokens':1000,'cached_input_tokens':0,'output_tokens':10}}}
    rows.extend([usage,usage,{'type':'event_msg','payload':{'type':'token_count','info':{'last_token_usage':{'input_tokens':1000}}}},
        {'type':'token_usage_record','payload':{'response_id':'two','usage':{'input_tokens':900,'cached_input_tokens':800,'output_tokens':10}}}])
    path=tmp_path/'trace.jsonl';path.write_text('\n'.join(json.dumps(r) for r in rows))
    report=module.native_trace_metrics(path)
    assert report['valid_usage'] and report['request_count'] == 2
    assert report['net_input_growth'] == -100 and report['peak_input_tokens'] == 1000
    assert report['requests'][1]['net_input_change_tokens'] == -100
    assert report['context_events'][0]['type'] == 'compacted'
    assert 'PRIVATE COMPACTION' not in json.dumps(report)
    assert report['tools'][0]['reader_pointers'] == ['/goal']
    assert 'SECRET SCIENTIFIC BODY' not in json.dumps(report) and 'PRIVATE REASONING' not in json.dumps(report)
    incomplete=json.loads(json.dumps(usage));del incomplete['payload']['usage']['cached_input_tokens']
    path.write_text('\n'.join(json.dumps(r) for r in [rows[0],incomplete]))
    assert not module.native_trace_metrics(path)['valid_usage']
    path.write_text(json.dumps({'type':'event_msg','payload':{'type':'token_count'}}))
    assert not module.native_trace_metrics(path)['valid_usage']
