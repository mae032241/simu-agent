"""Offline usage audit of explicitly supplied native threads; no session search.

Keeps counters only, never prompts, tool bodies, credentials or scientific text.
This complements control notifications; it does not replace budget accounting.
"""
import argparse
import json
from pathlib import Path


def output_text(value):
    if isinstance(value, str):
        return value, False
    if isinstance(value, list):
        blocks = [item for item in value if isinstance(item, dict)]
        return '\n'.join(item['text'] for item in blocks if isinstance(item.get('text'), str)), any(
            not isinstance(item.get('text'), str) for item in blocks) or len(blocks) != len(value)
    return '', True


def audit_thread(path, thread_id, role):
    requests, results, calls = {}, {}, {}
    identity_seen = False
    nontext = 0
    categories = dict(mcp=0, shell=0, code_mode=0, other=0)
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            value = event.get('payload', {})
            if event.get('type') == 'session_meta':
                if value.get('id') != thread_id:
                    raise ValueError('native_session_identity_mismatch')
                identity_seen = True
            if event.get('type') == 'token_usage_record':
                if value.get('thread_id') != thread_id:
                    raise ValueError('native_usage_identity_mismatch')
                identity = value.get('response_id')
                if not identity:
                    raise ValueError('native_usage_response_id_missing')
                usage = {key:value['usage'][key] for key in
                    ('input_tokens', 'cached_input_tokens', 'output_tokens')}
                if any(type(n) is not int or n < 0 for n in usage.values()) or usage['cached_input_tokens'] > usage['input_tokens']:
                    raise ValueError('native_usage_invalid')
                if identity in requests and requests[identity]['usage'] != usage:
                    raise ValueError('native_usage_response_conflict')
                requests[identity] = dict(time=event.get('timestamp'), turn_id=value.get('turn_id'), usage=usage)
            if event.get('type') != 'response_item':
                continue
            kind, identity = value.get('type'), value.get('call_id')
            if kind in {'function_call', 'custom_tool_call'} and identity:
                calls[identity] = value.get('name', '')
            if kind not in {'function_call_output', 'custom_tool_call_output'} or not identity:
                continue
            text, other = output_text(value.get('output'))
            observation = (len(text.encode('utf-8')), other)
            if identity in results and results[identity] != observation:
                raise ValueError('native_tool_result_conflict')
            results[identity] = observation
    if not identity_seen:
        raise ValueError('native_session_identity_missing')
    for identity, (size, other) in results.items():
        name = calls.get(identity, '')
        category = ('mcp' if name.startswith('mcp__') else 'shell' if name in {'exec_command', 'write_stdin'}
                    else 'code_mode' if name in {'exec', 'functions.exec'} else 'other')
        categories[category] += size
        nontext += int(other)
    totals = {key:sum(row['usage'][key] for row in requests.values()) for key in
        ('input_tokens', 'cached_input_tokens', 'output_tokens')}
    return dict(thread_id=thread_id, role=role, requests=len(requests), request_usage=list(requests.values()),
        tokens=totals if requests else None,
        tool_results=len(results), tool_result_text_bytes=sum(size for size, _ in results.values()),
        text_bytes_by_outer_tool=categories, nontext_results=nontext,
        unmatched_results=len(set(results)-set(calls)), calls_without_result=len(set(calls)-set(results)))


def audit(sources):
    if len({source['thread_id'] for source in sources}) != len(sources):
        raise ValueError('duplicate_native_thread')
    threads = [audit_thread(**source) for source in sources]
    return dict(source='explicit_native_logs', threads=threads,
        tool_result_bytes=sum(row['tool_result_text_bytes'] for row in threads),
        coverage='partial' if any(row['nontext_results'] or row['unmatched_results'] or
            row['calls_without_result'] for row in threads) else 'observed_for_supplied_logs',
        limitations=['Offline supplied-log evidence, not a live budget meter or proof of all participant coverage.',
            'Tool text includes wrappers. Code-mode may contain MCP and shell output; its nested bytes are unclassified.',
            'Bytes are not tokens. Cached input is included once. No monetary cost estimate.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--thread', action='append', required=True, help='ROLE:EXACT_THREAD_ID=PATH; repeat for each known participant')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sources = []
    for item in args.thread:
        identity, path = item.split('=', 1)
        role, thread_id = identity.split(':', 1)
        if role not in {'root', 'worker', 'helper', 'setup_root', 'unattributed'}:
            parser.error('invalid participant role')
        sources.append(dict(path=path, thread_id=thread_id, role=role))
    result = audit(sources)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(dict(output=str(args.output), threads=len(result['threads']), coverage=result['coverage'])))


if __name__ == '__main__':
    main()
