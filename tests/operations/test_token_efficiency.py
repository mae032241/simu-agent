"""Real reader, MCP projection and admission boundaries; no native model calls."""
import json

import pytest

from scripts.native_usage_audit import audit


def test_native_audit_deduplicates_requests_and_outputs_without_exporting_bodies(tmp_path):
    payload = dict(thread_id='r', response_id='response', turn_id='turn',
        usage=dict(input_tokens=100, cached_input_tokens=80, output_tokens=5))
    events = [dict(type='session_meta', payload={'id':'r'}),
        dict(type='token_usage_record', payload=payload), dict(type='token_usage_record', payload=payload),
        dict(type='event_msg', payload=dict(type='token_count', info={'total_token_usage':payload['usage']})),
        dict(type='response_item', payload=dict(type='custom_tool_call', call_id='c', name='exec', input='private input')),
        dict(type='response_item', payload=dict(type='custom_tool_call_output', call_id='c',
            output=[{'type':'input_text', 'text':'私密'}]))]
    events.append(events[-1])
    path = tmp_path/'native.jsonl'
    path.write_text('\n'.join(json.dumps(event) for event in events))
    report = audit([dict(path=path, thread_id='r', role='root')])
    thread = report['threads'][0]
    assert thread['requests'] == 1 and thread['tokens'] == payload['usage']
    assert report['tool_result_bytes'] == len('私密'.encode())
    assert thread['text_bytes_by_outer_tool']['code_mode'] == report['tool_result_bytes']
    assert '私密' not in json.dumps(report, ensure_ascii=False)
    assert 'private input' not in json.dumps(report)
    with pytest.raises(ValueError, match='identity_mismatch'):
        audit([dict(path=path, thread_id='other', role='root')])
    with pytest.raises(ValueError, match='duplicate_native_thread'):
        audit([dict(path=path, thread_id='r', role='root')]*2)
    events.append(dict(type='token_usage_record', payload={**payload, 'usage':{**payload['usage'], 'input_tokens':101}}))
    path.write_text('\n'.join(json.dumps(event) for event in events))
    with pytest.raises(ValueError, match='response_conflict'):
        audit([dict(path=path, thread_id='r', role='root')])
