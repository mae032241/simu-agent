"""Extract actual platform role/model/effort metadata, excluding model-authored claims."""
import json
import os
import re
from pathlib import Path

base=Path(os.environ.get('SCID_SETTINGS_PROBE_ROOT', '/tmp/scid-execution-settings-p0'))
fixture=json.loads((base/'fixture.json').read_text())
observed=[]
for path in sorted((base/'cli-home/sessions').rglob('*.jsonl')):
    row={'session_file':path.name,'contexts':[],'tool_names':[]}
    for line in path.open():
        try: event=json.loads(line)
        except ValueError: continue
        payload=event.get('payload',{})
        if event.get('type')=='session_meta':
            row['session_id']=payload.get('id')
            row['agent_role']=payload.get('agent_role')
            source=payload.get('source',{})
            if isinstance(source,dict):row['source']=source
        elif event.get('type')=='turn_context':
            row['contexts'].append({k:payload.get(k) for k in ('model','effort')})
        elif event.get('type')=='response_item' and payload.get('type') in ('function_call', 'custom_tool_call'):
            row['tool_names'].append(payload.get('name'))
            row['tool_names'].extend(re.findall(r'tools\.([A-Za-z0-9_]+)\(', payload.get('input', '')))
    if row.get('agent_role')==fixture['agent_type']:
        row['tool_names']=sorted(set(row['tool_names']))
        observed.append(row)
out={'agent_type':fixture['agent_type'],'operation_digest':fixture['operation_digest'],
    'source':'Codex session_meta and turn_context records; not Agent self-report',
    'observed_children':observed}
Path(__file__).with_name(os.environ.get('SCID_SETTINGS_OBSERVATIONS_NAME','P0_PLATFORM_OBSERVATIONS.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
