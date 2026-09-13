"""Read-only engineering replay; emits field diagnostics, never scientific prose.

Uses only tool-call/write events, ignores all reasoning and conversation records.
No logged shell/JS/Python is executed. Patches are applied to strings in memory.
The live database is opened in read-only mode; production records are not changed.
"""
import collections
import hashlib
import json
import re
import resource
import sqlite3
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (45, 45))

from pydantic import ValidationError
from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
from scidiscovery.operation_contract import validation_diagnostics

HERE = Path(__file__).resolve().parent
SESSION = next(Path('/home/da/.codex/sessions/2026/09/13').glob(
    'rollout-2026-09-13T00-15-10-*.jsonl'))
RUN = 'fig4_iterative_alignment_plan_review_1'
BOUND_ALIASES = None
if len(sys.argv) > 1:
    from scidiscovery.operation_contract import validate_evidence_source_aliases
    with sqlite3.connect('file:/var/lib/scidiscovery-m7/database/runs.sqlite3?mode=ro', uri=True) as db:
        binding = db.execute('SELECT inputs_json FROM runs WHERE output_binding_name=? AND created_at=?',
            (RUN + '.output', '2026-09-12T16:15:02.093204Z')).fetchall()
    assert len(binding) == 1
    BOUND_ALIASES = {item['source_name'] for item in json.loads(binding[0][0])}

files = {}
patch_audit = []
submissions = []
failed_patch_calls = set()
patch_calls = set()
with SESSION.open() as stream:
    for line in stream:
        event = json.loads(line)
        data = event.get('payload', {})
        if event.get('type') != 'response_item':
            continue
        if data.get('type') in {'function_call', 'custom_tool_call'} and 'tools.apply_patch' in data.get('input', data.get('arguments', '')):
            patch_calls.add(data.get('call_id'))
        if data.get('type') in {'function_call_output', 'custom_tool_call_output'} and data.get('call_id') in patch_calls:
            output = json.dumps(data.get('output', {}))
            if 'Error' in output or 'error' in output:
                failed_patch_calls.add(data['call_id'])


def apply_patch_text(patch):
    lines = patch.splitlines()
    assert lines[0] == '*** Begin Patch' and lines[-1] == '*** End Patch'
    i = 1
    while i < len(lines) - 1:
        header = lines[i]
        i += 1
        if header.startswith('*** Delete File: '):
            files.pop(header.removeprefix('*** Delete File: '))
            continue
        if header.startswith('*** Add File: '):
            name = header.removeprefix('*** Add File: ')
            body = []
            while i < len(lines) and not lines[i].startswith('*** '):
                assert lines[i].startswith('+')
                body.append(lines[i][1:])
                i += 1
            assert name not in files
            files[name] = '\n'.join(body) + '\n'
            continue
        assert header.startswith('*** Update File: ')
        name = header.removeprefix('*** Update File: ')
        assert name in files
        content = files[name].splitlines()
        cursor = 0
        while i < len(lines) and not lines[i].startswith('*** '):
            assert lines[i].startswith('@@')
            i += 1
            old, new = [], []
            while i < len(lines) and not lines[i].startswith(('@@', '*** ')):
                line = lines[i]
                if line == '':
                    line = ' '
                assert line[0] in ' +-'
                if line[0] in ' -':
                    old.append(line[1:])
                if line[0] in ' +':
                    new.append(line[1:])
                i += 1
            matches = [j for j in range(cursor, len(content) - len(old) + 1)
                       if content[j:j + len(old)] == old]
            if not matches:
                matches = [j for j in range(cursor, len(content) - len(old) + 1)
                           if [v.strip() for v in content[j:j + len(old)]] == [v.strip() for v in old]]
            assert len(matches) == 1, f'patch context not unique: {len(matches)} matches, {len(old)} lines'
            j = matches[0]
            content[j:j + len(old)] = new
            cursor = j + len(new)
        files[name] = '\n'.join(content) + '\n'


def inspect_payload(payload):
    sources = {v['source_key'] for v in payload.get('evidence', [])}
    keys = [v['hypothesis_key'] for v in payload.get('hypothesis_reviews', [])]
    missing = []
    for i, finding in enumerate(payload.get('findings', [])):
        for j, key in enumerate(finding.get('evidence_keys', [])):
            if key not in sources:
                missing.append({'path': f'$.payload.findings[{i}].evidence_keys[{j}]',
                                'reference_key': key})
    result = {'findings_count': len(payload.get('findings', [])),
              'evidence_count': len(payload.get('evidence', [])),
              'duplicate_hypothesis_keys': len(keys) != len(set(keys)),
              'target_is_experiment_portfolio': payload.get('review_target') == 'experiment_portfolio',
              'missing_references': missing}
    try:
        ScientificReview.model_validate_json(json.dumps(payload, ensure_ascii=False), strict=True)
        if BOUND_ALIASES is not None:
            validate_evidence_source_aliases(payload, BOUND_ALIASES)
            result['actual_bound_aliases_verified'] = True
        result['accepted'] = True
    except ValidationError as error:
        result['accepted'] = False
        result['raw_errors'] = error.errors(include_input=False, include_context=False, include_url=False)
        result['projected_errors'] = validation_diagnostics(error,
            schema=ScientificReview.model_json_schema(), phase='output_payload', action='submit')
    return result


with SESSION.open() as stream:
    for line in stream:
        event = json.loads(line)
        data = event.get('payload', {})
        if event.get('type') != 'response_item' or data.get('type') not in {'function_call', 'custom_tool_call'}:
            continue
        code = data.get('input', data.get('arguments', ''))
        when = event['timestamp']
        if 'tools.apply_patch' in code:
            if data.get('call_id') in failed_patch_calls:
                patch_audit.append({'timestamp': when, 'applied_in_memory': False, 'actual_patch_tool_failed': True})
                continue
            patches = []
            for token in re.findall(r'"(?:\\.|[^"\\])*"', code):
                try:
                    value = json.loads(token)
                except ValueError:
                    continue
                if value.startswith('*** Begin Patch'):
                    patches.append(value)
            assert len(patches) == 1
            try:
                apply_patch_text(patches[0])
            except AssertionError as error:
                raise AssertionError(f'{when}: {error}') from None
            patch_audit.append({'timestamp': when, 'applied_in_memory': True})
        if 'tools.exec_command' in code and when >= '2026-09-12T16:21:00':
            for token in re.finditer(r'(?:"cmd"|\bcmd)\s*:\s*("(?:\\.|[^"\\])*")', code):
                command = json.loads(token.group(1))
                # The recorded exec calls in this interval parse/print JSON, rg or sed.
                # Any write would invalidate this patch-only reconstruction.
                assert not re.search(r'write_text|write_bytes|json\.dump\(|open\([^\n]*[\'\"]w|sed -i|\s>\s', command), 'unreplayed write'
        if re.search(r'tools\.mcp__\w+__worker_submit_result\(', code):
            candidates = [v for k, v in files.items() if k.endswith('/output/result.json')]
            assert len(candidates) == 1
            envelope = json.loads(candidates[0])
            submissions.append({'timestamp': when, **inspect_payload(envelope['payload'])})

connection = sqlite3.connect('file:/var/lib/scidiscovery-m7/database/runs.sqlite3?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
rows = connection.execute('SELECT run_id, recovery_draft_json FROM runs WHERE output_binding_name=? AND operation_id=? AND created_at=?',
    (RUN + '.output', 'science.object.review.v1', '2026-09-12T16:15:02.093204Z')).fetchall()
assert len(rows) == 1
row = rows[0]
activities = [{'timestamp': r['recorded_at'], 'activity': r['activity'],
               'diagnostic': json.loads(r['diagnostic_json']) if r['diagnostic_json'] else None}
              for r in connection.execute('SELECT activity, recorded_at, diagnostic_json FROM run_activity WHERE run_id=? AND activity IN (?,?) ORDER BY rowid',
              (row['run_id'], 'output_rejected', 'framework_failure'))]
manifest = json.loads(row['recovery_draft_json'])
root = Path('/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/workspace/ingaas_inalas_photodetector/.scidiscovery-runs/recovery') / manifest['draft_digest']
saved = (root / 'result.json').read_bytes()
assert hashlib.sha256(saved).hexdigest() == manifest['files'][0]['sha256']
saved_payload = json.loads(saved)['payload']
report = {'run_name': RUN, 'method': 'Static in-memory patch reconstruction from tool-call events; reasoning/chat skipped; no logged command executed.',
          'patches': patch_audit, 'submissions': submissions, 'controlled_activities': activities,
          'recovery_integrity_verified': True, 'recovery_payload_diagnostic': inspect_payload(saved_payload)}
report['last_reconstructed_payload_matches_recovery'] = envelope['payload'] == saved_payload
(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'review-rejection-submission-replay.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'submissions': submissions, 'last_reconstructed_payload_matches_recovery': report['last_reconstructed_payload_matches_recovery'],
                  'recorded_rejections': sum(x['activity'] == 'output_rejected' for x in activities)}, ensure_ascii=False))
