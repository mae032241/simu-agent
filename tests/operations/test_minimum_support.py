"""Fixed role decisions measured through real open, startup and copied readers.

Frozen before any candidate change (baseline HEAD 0620774):

* initial_h  -- propose the initial mechanism portfolio from the original task.
  Needs the verbatim task, the role contract and the boundary-declaration rules
  (H separates prohibitions/conditions with boundary_declarations).
* h_revision -- revise the previous portfolio against the frame and foundation.
  Needs the complete frame, foundation, previous portfolio and the boundary
  rules (derived boundaries are revised with boundary_declarations.revises).
* w_portfolio -- choose the next discriminating experiment within current H
  after A feedback.  Needs the complete H portfolio, original goal, A analysis
  and prior W report.
* a_results -- judge W's contribution and route the next action.  Needs the W
  report, H portfolio, goal, adopted stage receipt, every captured attempt file
  (including the uncited failure), the derived ledger records and the capture
  inventory coverage.

Each role reads its core plus the frozen sections required by its stated decision,
including boundary-declaration rules. Complete detailed contracts stay readable;
none/all sensitivity is measured separately.

Every required exact object is read once (dedup by exact private ArtifactRef on
both sides, the conservative denominator).  A read is skipped only when the
default view already delivered that object's decision content and the test
verifies it field by field against the original.  Navigation that a Worker
cannot avoid (grouped input metadata only addressable by pointer) is counted.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.artifact_agent.test_input_reader import body
from tests.operations.test_boundary_provenance import submit
from tests.operations.test_completed_science_compatibility import _qualified_foundation
from tests.operations.test_historical_compatibility_paths import _complete
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.test_l2_run_invariants import _system
from tests.operations.test_ledger_capture import config, row
from tests.operations.worker_fixtures import attached_worker


TASK = ('Improve performance under the target conditions. Preserve original observations. '
    'A validation proxy does not cover the changed target mechanism. Compare candidates '
    'and keep failed or inconclusive evidence. Explore justified directions within the authorized budget.')
KEYS = tuple(f'mechanism_{n}' for n in range(6))
CASES = ('initial_h', 'h_revision', 'w_portfolio', 'a_results')
# On-demand role_reference sections each decision reads beyond the core checklist.
# Frozen from the decision statements above (written in 78aedd3, before the
# compacted contract existed) by responsibility, conservatively: every
# responsibility the decision exercises, and always closeout/boundary/proxy
# sections when the decision touches them (the task text names a validation
# proxy that misses the target, so every case touches proxy and boundaries).
# SCID_M12_SECTIONS=none|all give the lower/upper sensitivity bounds; savings
# below the 'all' bound depend on on-demand reading.
_W_DECISION = ('boundary_declarations', 'w_boundaries', 'w_scope', 'w_inputs', 'w_iteration', 'w_revision_route',
    'w_predictions', 'w_reporting')
GUIDES = {
    'initial_h': ('work_context', 'boundary_declarations', 'h_understanding', 'h_portfolio', 'h_hypothesis_content',
        'h_target_coverage', 'h_boundaries', 'h_handoff'),
    'h_revision': ('work_context', 'boundary_declarations', 'h_revision', 'h_portfolio', 'h_hypothesis_content',
        'h_target_coverage', 'h_boundaries', 'h_handoff'),
    'w_portfolio': _W_DECISION,
    'a_results': ('boundary_declarations', 'a_boundaries', 'a_boundary_refs', 'a_analysis', 'a_reading', 'a_proxy',
        'a_direction', 'a_completion', 'a_closeout', 'budget_reading', 'a_report'),
}


def invoke(root, name, operation, inputs):
    return root.call_tool('operation_invoke', dict(name=name, operation_id=operation,
        inputs=[dict(port=key, artifact_names=[value]) for key, value in inputs.items()],
        instruction='Decide the next discriminating question from the exact supplied evidence.'))


def proposal():
    value = _proposal(hypothesis_keys=KEYS)
    value.pop('research_objective_key')
    value['contradiction'] = 'Proxy ranks candidate one first; target contribution remains unknown.'
    return value


def analysis_payload():
    return dict(summary='Proxy improvement leaves target contribution unknown.', overall_verdict='inconclusive',
        claim_allowed=False,
        hypothesis_assessments=[dict(hypothesis_key=key, outcome='not_tested', evidence_keys=['experiment_results'],
            rationale='No discriminating target observation is available.') for key in KEYS],
        evidence=[dict(source_key='experiment_results', source_type='runtime_output', title='Exact experiment', locator='/summary')],
        source_references=[dict(source_key='experiment_results', input_alias='experiment_results')],
        limitations=['The proxy misses changed target conditions.'],
        remaining_contradiction='The untested mechanisms may alter target ranking.',
        next_action='W: obtain a discriminating target observation within mechanism_0; otherwise H: revise the validation boundary.')








def support_observations():
    """Private fixture truth; control must retain its author-reported uncertainty."""
    return [
        dict(checks=dict(candidate='a', version='v1', outcome='inconclusive', average=.9, worst=.2,
            limitation='Proxy conditions only; target contribution unknown.'),
            appendix=dict(changed_condition='Target condition changed; keep the ranking unresolved.',
                unread_tail='Uninspected observation. ' * 1500)),
        dict(checks=dict(candidate='b', version='v1', outcome='inconclusive', average=.8, worst=.7,
            limitation='Proxy conditions only; target contribution unknown.')),
        dict(checks=dict(candidate='a', version='v2', outcome='failed', average=None, worst=None,
            limitation='Changed target condition failed; v1 does not validate this version.')),
    ]


def fixed_case(tmp_path, case, *, attempt_payloads=None):
    if case == 'h_revision':
        _, runtime, _, root, foundation = _qualified_foundation(tmp_path)
        prior = _complete(runtime, root, 'prior', 'science.hypothesis.propose.v1',
            {'problem_frame':'split', 'scientific_foundation':foundation},
            _proposal(hypothesis_keys=KEYS))
        invoke(root, 'selected', 'science.hypothesis.propose.v1',
            {'problem_frame':'split', 'scientific_foundation':foundation, 'previous_hypotheses':prior})
    else:
        _, runtime, _, _, root = _system(tmp_path)
        root.call_tool('artifact_ingest_text', dict(name='task', text=TASK))
        if case == 'initial_h':
            invoke(root, 'selected', 'science.hypothesis.propose.v1', {'subject':'task'})
        else:
            invoke(root, 'H', 'science.hypothesis.propose.v1', {'subject':'task'})
            submit(runtime, root, 'H', proposal())
            if case == 'a_results':
                from scidiscovery.agent_execution_settings import parse_settings
                host = tmp_path/'host'; host.mkdir()
                ledger = host/'results.jsonl'
                ledger.write_bytes(b''.join(canonical_json(row(n))+b'\n' for n in (1,2,3,1))
                    + b'{malformed\n' + canonical_json(row(4)))
                runtime.runs.agent_settings = parse_settings(config(ledger, name='W', operation='science.experiment.v1'))
            invoke(root, 'W', 'science.experiment.v1', {'subject':'H.output'})
            worker = attached_worker(runtime, root, 'W')
            opened = worker.call_tool('worker_open_assignment', {})
            workspace = Path(opened['workspace_path'])
            for n in range(3):
                payload = attempt_payloads[n] if attempt_payloads is not None else dict(
                    candidate=n, outcome='failed' if n == 2 else 'inconclusive',
                    proxy_score=2-n, target_support='unknown', limitation='Target conditions unobserved.')
                (workspace/'scratch/artifacts'/f'attempt-{n}.json').write_bytes(canonical_json(payload))
            stage = worker.call_tool('worker_experiment_stage', dict(stage='validity',
                conclusion='Proxy ranking is available, target contribution unknown.',
                materials=['file:scratch/artifacts/attempt-0.json','file:scratch/artifacts/attempt-1.json']))['reference']
            (workspace/'output/result.json').write_bytes(canonical_json(dict(payload=dict(
                summary='Proxy ranking does not resolve the target mechanism.', outcome='inconclusive',
                limitations=['Third failure retained but not cited.'],
                remaining_question='Which mechanism changes target ranking?', adopted_stages=[stage]))))
            assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
            if case == 'a_results':
                invoke(root, 'selected', 'science.result.analyze.v1', {'subject':'W.output'})
            else:
                invoke(root, 'A', 'science.result.analyze.v1', {'subject':'W.output'})
                submit(runtime, root, 'A', analysis_payload())
                invoke(root, 'selected', 'science.experiment.v1',
                    {'subject':'H.output','scientific_materials':'A.output','prior_experiment':'W.output'})
    worker = attached_worker(runtime, root, 'selected')
    opened = worker.call_tool('worker_open_assignment', {})
    return runtime, root, worker, opened


def copied_pages(workspace, source, *, pointers=(), file=False, full=False):
    """Capture every page and its actual wrapper, retaining exact selected text."""
    args = [sys.executable, '-I', 'tools/read_input.py', source, '--budget', '8192']
    for pointer in pointers:
        args += ['--pointer', pointer]
    if file: args.append('--file')
    if full: args.append('--full')
    replies, fragments = [], []
    while True:
        response = subprocess.run(args, cwd=workspace, capture_output=True, text=True, check=True, timeout=10).stdout
        replies.append(response)
        fragments.append(body(response))
        following = re.search(r'next_offset (\d+)', response)
        if following is None:
            break
        handle = re.search(r'--selection ([0-9a-f]{32})', response).group(1)
        args = [sys.executable, '-I', 'tools/read_input.py', '--selection', handle,
            '--offset', following.group(1), '--budget', '8192']
    return replies, ''.join(fragments)


def run_command(workspace, command):
    """Follow an advertised read command exactly, including continuation."""
    parts = command.split()
    assert parts[:2] == ['python', 'tools/read_input.py']
    source, rest = parts[2], parts[3:]
    pointers = [rest[i+1] for i, value in enumerate(rest) if value == '--pointer']
    return copied_pages(workspace, source, pointers=pointers, file='--file' in rest, full='--full' in rest)


def observed_overview(start, workspace=None):
    observed = start.get('observed_results', {})
    if workspace is not None and 'details_read' in observed:
        _, restored = run_command(workspace, observed['details_read'])
        observed = json.loads(restored)
    return {item['source_name']: item for item in observed.get('sources', ())}


def verify_overview(raw, overview):
    """The exact results detail retains every projected decision field of the original."""
    if overview['kind'] == 'capture_inventory':
        original = json.loads(raw)
        assert overview['coverage'] == original['coverage']
        assert overview['attempt_inventory'] == original['attempt_inventory']
        entries = {item['path']: item for item in overview['entries']}
        assert len(entries) == len(original['entries'])
        for item in original['entries']:
            shown = entries[item['path']]
            for key in ('reference', 'size_bytes', 'status', 'source_coverage', 'projection_coverage',
                        'physical_records', 'attempt_total', 'raw_retained', 'producer_trust'):
                if key in item:
                    assert shown[key] == item[key], key
            if 'duplicate_groups' in item:
                assert shown['duplicate_groups'] == item['duplicate_groups']
    else:
        records = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        common, columns = overview['common'], overview['value_columns']
        shown = overview['records']
        assert len(shown) == len(records)
        for original, item in zip(records, shown):
            item = dict(item)
            if isinstance(item.get('values'), list):
                item['values'] = dict(zip(columns, item['values']))
            assert {**common, **item} == original


def workset(runtime, worker, opened, case):
    """Return captured samples for the frozen decision, plus semantic checks."""
    workspace = Path(opened['workspace_path'])
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    samples = [dict(kind='open', content=canonical_json(opened).decode())]
    pages, restored = copied_pages(workspace, 'worker-start.json', file=True)
    assert json.loads(restored) == start
    samples += [dict(kind='startup', content=page) for page in pages]
    default_count = len(samples)
    bindings = {item.source_name: item for item in runtime.runs.status(worker._run_id).inputs}
    visible = {item['source_name']: item for item in start['inputs']}
    hidden = []
    for group in start.get('input_groups', ()):
        if 'members' in group:
            visible.update({item['source_name']: item for item in group['members']})
        else:
            hidden += group['pointers']
    if hidden:
        # Grouped metadata is addressable only by pointer from frozen assignment.json.
        pages, restored = copied_pages(workspace, 'assignment.json', pointers=hidden)
        samples += [dict(kind='navigation', content=page) for page in pages]
        assignment = json.loads(Path(opened['assignment_path']).read_bytes())
        for pointer in hidden:
            entry = assignment['inputs'][int(pointer.rsplit('/', 1)[1])]
            visible[entry['source_name']] = entry
    overview = observed_overview(start)
    required, seen, read_contracts = [], set(), set()
    for source, entry in visible.items():
        item = bindings[source]
        if item.artifact_ref in seen or item.exposure == 'handoff_only':
            continue
        seen.add(item.artifact_ref)
        raw = runtime.artifacts.read(item.artifact_ref)
        required.append(dict(source_name=source, sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)))
        if 'text' in entry:
            assert entry['text'].encode() == raw
            continue
        if source in overview:
            shown = overview[source]
            if 'details_read' in shown:
                pages, restored = run_command(workspace, shown['details_read'])
                samples += [dict(kind='overview_detail', source=source, content=page) for page in pages]
                shown = json.loads(restored)
            verify_overview(raw, shown)
            continue
        if item.exposure == 'file_reference':
            if 'worker_materialize_input' not in read_contracts:
                contract = subprocess.check_output([sys.executable, '-I', 'tools/read_tool_contract.py',
                    'worker_materialize_input', '--full'], cwd=workspace, text=True, timeout=10)
                assert json.loads(contract)['contract'] == json.loads(
                    Path(opened['assignment_path']).read_bytes())['tool_contracts']['worker_materialize_input']
                samples.append(dict(kind='tool_contract', source='worker_materialize_input', content=contract))
                read_contracts.add('worker_materialize_input')
            reply = worker.call_tool('worker_materialize_input', dict(source_name=source))
            samples.append(dict(kind='materialize', content=canonical_json(reply).decode()))
            pages, restored = copied_pages(workspace, reply['relative_path'], file=True)
        else:
            pages, restored = copied_pages(workspace, source, full=True)
        assert restored.strip() == raw.decode().strip()
        samples += [dict(kind='evidence', source=source, content=page) for page in pages]
    assert {value.artifact_ref for value in bindings.values() if value.exposure != 'handoff_only'} == seen
    guides = {item['name']: item for item in start.get('guides', ())}
    if 'role_reference' in guides:
        mode = os.environ.get('SCID_M12_SECTIONS', 'frozen')
        sections = {'none': (), 'all': tuple(guides['role_reference']['sections'])}.get(mode, GUIDES[case])
        context = json.loads((workspace/'worker-guides.json').read_bytes())
        if sections:
            # One reader call with repeated --pointer selects every needed section.
            prefix = guides['role_reference']['read'].replace(' --pointer /guides/role_reference/SECTION', '')
            command = prefix + ''.join(' --pointer /guides/role_reference/' + name for name in sections)
            pages, restored = run_command(workspace, command)
            samples += [dict(kind='guide', source=','.join(sections), content=page) for page in pages]
            for name in sections:
                assert json.dumps(context['guides']['role_reference'][name], ensure_ascii=False) in restored
    return start, samples, default_count, required


@pytest.mark.parametrize('case', CASES)
def test_fixed_decision_worksets(tmp_path, case):
    runtime, root, worker, opened = fixed_case(tmp_path, case)
    assignment_bytes = Path(opened['assignment_path']).read_bytes()
    start, samples, default_count, required = workset(runtime, worker, opened, case)
    assert Path(opened['assignment_path']).read_bytes() == assignment_bytes
    from scidiscovery.artifact_agent.schema.role_result import BOUNDARY_GUIDANCE
    assignment = json.loads(assignment_bytes)
    # The frozen contract is complete; startup core plus on-demand sections reconstruct it exactly.
    try:
        from scidiscovery.artifact_agent.schema.role_result import split_reference, with_reference
    except ImportError:  # Revisions before the compact contract (baseline measurement).
        split_reference = None
    context = json.loads((Path(opened['workspace_path'])/'worker-context.json').read_bytes())
    sections = context.get('guides', {}).get('role_reference')
    guide = next((item for item in start.get('guides', ()) if item['name'] == 'role_reference'), None)
    if guide:
        # Gate-only reconstruction, separate from the selected decision workset.
        _, restored = run_command(Path(opened['workspace_path']), guide['read'].removesuffix('/SECTION'))
        sections = json.loads(restored)
        assert guide['sections'] == {name: len(text.encode()) for name, text in sections.items()}
    if sections:
        assert split_reference(assignment['role_instructions']) == (start['role_instructions'], sections)
        original_sections = split_reference(assignment['role_instructions'])[1]
        ordered_sections = {name: sections[name] for name in original_sections}
        assert with_reference(start['role_instructions'], ordered_sections) == assignment['role_instructions']
        assert BOUNDARY_GUIDANCE.strip() == sections['boundary_declarations']
    else:
        assert start['role_instructions'] == assignment['role_instructions']
    assert BOUNDARY_GUIDANCE.strip() in assignment['role_instructions']
    target = os.environ.get('SCID_M12_EVIDENCE')
    if target:
        destination = Path(target)/case
        destination.mkdir(parents=True, exist_ok=False)
        for index, sample in enumerate(samples):
            (destination/f'{index:03}-{sample["kind"]}.txt').write_text(sample['content'])
        (destination/'assignment.json').write_bytes(assignment_bytes)
        (destination/'worker-start.json').write_bytes(Path(opened['start_here_path']).read_bytes())
        (destination/'worker-context.json').write_bytes((Path(opened['workspace_path'])/'worker-context.json').read_bytes())
        kinds = {}
        for sample in samples:
            kinds.setdefault(sample['kind'], [0, 0])
            kinds[sample['kind']][0] += 1
            kinds[sample['kind']][1] += len(sample['content'].encode())
        supplemental = {}
        frozen_baseline = os.environ.get('SCID_M1_BASELINE_EVIDENCE')
        if frozen_baseline and case == 'a_results':
            from scidiscovery.artifact_agent.service import tool_contract_reader
            replay = tmp_path/'baseline-contract-replay'; (replay/'tools').mkdir(parents=True)
            original_assignment = (Path(frozen_baseline)/case/'assignment.json').read_bytes()
            (replay/'assignment.json').write_bytes(original_assignment)
            (replay/'tools/read_tool_contract.py').write_bytes(Path(tool_contract_reader.__file__).read_bytes())
            packet = subprocess.check_output([sys.executable, '-I', 'tools/read_tool_contract.py',
                'worker_materialize_input', '--full'], cwd=replay, text=True, timeout=10)
            assert json.loads(packet)['contract'] == json.loads(original_assignment)['tool_contracts']['worker_materialize_input']
            (destination/'baseline-materialization-contract.txt').write_text(packet)
            supplemental['baseline_materialization_contract_bytes'] = len(packet.encode())
            supplemental['baseline_materialization_contract_reads'] = 1
        (destination/'measurement.json').write_bytes(canonical_json(dict(case=case, **supplemental,
            default_bytes=sum(len(s['content'].encode()) for s in samples[:default_count]),
            default_reads=default_count,
            workset_bytes=sum(len(s['content'].encode()) for s in samples),
            workset_reads=len(samples), by_kind=kinds, required=required)))


def _context(opened):
    workspace = Path(opened['workspace_path'])
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    members = {item['source_name']: {**{k: v for k, v in group.items() if k not in ('pointers', 'members')}, **item}
        for group in start.get('input_groups', ()) for item in group.get('members', ())}
    return workspace, start, {**{item['source_name']: item for item in start['inputs']}, **members}


def test_uncited_failed_attempt_is_visible_in_default_view(tmp_path):
    runtime, root, worker, opened = fixed_case(tmp_path, 'a_results')
    workspace, start, entries = _context(opened)
    default = next(item for item in observed_overview(start).values() if item['kind'] == 'capture_inventory')
    assert default['coverage'] == 'incomplete'
    assert default['entry_count'] and default['entry_states']['status']
    assert 'unverified' in start['observed_results']['instruction']
    overview = observed_overview(start, workspace)
    inventory = next(item for item in overview.values() if item['kind'] == 'capture_inventory')
    by_path = {item['path']: item for item in inventory['entries']}
    failed = by_path['scratch/artifacts/attempt-2.json']
    # Exact inventory detail exposes every captured entry, including uncited failure.
    assert failed['status'] == 'retained' and failed['stage_materials'] == []
    assert [by_path[f'scratch/artifacts/attempt-{n}.json']['stage_materials'] for n in (0, 1)] == [
        ['experiment_materials'], ['experiment_materials']]
    # Outcome and metric of the small attempt are the complete exact original.
    assert json.loads(entries[failed['source_name']]['text']) == dict(candidate=2, outcome='failed',
        proxy_score=0, target_support='unknown', limitation='Target conditions unobserved.')
    ledger = next(item for item in overview.values() if item['kind'] == 'ledger_view')
    rows = [dict(zip(ledger['value_columns'], row['values'])) if isinstance(row['values'], list) else row['values']
        for row in ledger['records']]
    assert any(row.get('ok') is False and row.get('val_score') == -3.0 for row in rows)
    assert [row['status'] for row in ledger['records']][-2:] == ['incomplete', 'pending_tail']
    assert inventory['coverage'] == 'incomplete' and 'unknown' in start['observed_results']['basis']
    assert by_path['ledger:covshift_results']['duplicate_groups'] == [{'locators': ['line:1', 'line:4'], 'status': 'ambiguous'}]
    # Neutral control facts only: no author verdicts, summaries or Root judgments.
    assert not {'summary', 'verdict', 'next_actions', 'root_judgment'} & set(json.dumps(start['observed_results']).split('"'))
    # Root's public status remains compact: no capture arrays or attempt contents.
    status = json.dumps(root.call_tool('run_status', {'name': 'selected'}))
    assert 'observed_results' not in status and 'proxy_score' not in status


def test_default_support_keeps_conflicting_versions_failures_and_unread_originals(tmp_path):
    originals = support_observations()
    runtime, _, worker, opened = fixed_case(tmp_path, 'a_results', attempt_payloads=originals)
    workspace, start, entries = _context(opened)
    inventory = next(item for item in observed_overview(start, workspace).values() if item['kind'] == 'capture_inventory')
    by_path = {item['path']:item for item in inventory['entries']}
    sources = [by_path[f'scratch/artifacts/attempt-{n}.json']['source_name'] for n in range(3)]
    bound = {item.source_name:item.artifact_ref for item in runtime.runs.status(worker._run_id).inputs}
    assert len({bound[name] for name in sources}) == 3
    assert all('same_source_as' not in entries[name] for name in sources)
    assert inventory['coverage'] == 'incomplete'
    assert by_path['ledger:covshift_results']['duplicate_groups'] == [{'locators':['line:1','line:4'], 'status':'ambiguous'}]
    assert by_path['scratch/artifacts/attempt-2.json']['stage_materials'] == []
    assert 'unverified' in start['observed_results']['basis'] and 'unknown' in start['observed_results']['basis']
    # The large original is navigation, while the new failure/limit remains a
    # distinct small original. Average and worst-case rankings must not merge.
    assert 'text' not in entries[sources[0]]
    values, readers = [], {}
    for name, original in zip(sources, originals):
        if entries[name].get('exposure') == 'file_reference':
            delivered = worker.call_tool('worker_materialize_input', dict(source_name=name))
            readers[name] = (delivered['relative_path'], True)
        else:
            readers[name] = (name, False)
        source, file = readers[name]
        _, selected = copied_pages(workspace, source, pointers=['/checks'], file=file)
        values.append(json.loads(selected))
        assert values[-1] == original['checks']
    assert values[0]['average'] > values[1]['average'] and values[0]['worst'] < values[1]['worst']
    assert values[2]['candidate'] == values[0]['candidate'] and values[2]['version'] != values[0]['version']
    assert values[2]['outcome'] == 'failed' and 'does not validate' in values[2]['limitation']
    assert json.loads(entries[sources[2]]['text']) == originals[2]
    # Exact reader continuation exposes the unread appendix without adding it
    # to the default context or pretending it was inspected.
    source, file = readers[sources[0]]
    replies, restored = copied_pages(workspace, source, pointers=['/appendix'], file=file)
    assert len(replies) > 1 and json.loads(restored) == originals[0]['appendix']
    assert originals[0]['appendix']['unread_tail'] not in Path(opened['start_here_path']).read_text()


def test_advertised_sources_are_bound_and_readable_and_unbound_entries_say_so(tmp_path):
    """F2: never advertise a locator this task cannot read."""
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.worker_start import open_support
    runtime, root, worker, opened = fixed_case(tmp_path, 'a_results')
    workspace, start, entries = _context(opened)
    bound = {item.source_name for item in runtime.runs.status(worker._run_id).inputs}
    named = [entry['source_name'] for source in observed_overview(start, workspace).values()
        for entry in [source, *source.get('entries', ())] if entry.get('source_name') is not None]
    assert named and set(named) <= bound
    for name in set(named):
        if entries[name].get('exposure') == 'file_reference':
            reply = worker.call_tool('worker_materialize_input', dict(source_name=name))
            assert (workspace/reply['relative_path']).is_file()
        else:
            copied_pages(workspace, name)
    # Remove one captured attempt from the binding set: its entry stays visible
    # as an observed result, but with no readable locator or citation claim.
    status = runtime.runs.status(worker._run_id)
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    removed = 'experiment_files_003'
    narrowed = replace(status, inputs=tuple(item for item in status.inputs if item.source_name != removed))
    support = open_support(runtime.runs, narrowed, dict(assignment, inputs=[item for item in assignment['inputs']
        if item['source_name'] != removed]))
    inventory = next(item for item in support['observed_results']['sources'] if item['kind'] == 'capture_inventory')
    entry = next(item for item in inventory['entries'] if item['path'] == 'scratch/artifacts/attempt-2.json')
    assert entry['source_name'] is None and entry['stage_materials'] == [] and entry['status'] == 'retained'
    assert removed not in support['inline_inputs']


def test_stage_citations_resolve_in_the_original_producer_namespace(tmp_path, monkeypatch):
    """F1: a colliding alias spelling in another namespace never becomes a citation."""
    from scidiscovery.artifact_agent.service import sealed_materials
    from scidiscovery.artifact_agent.service.worker_start import open_support
    runtime, root, worker, opened = fixed_case(tmp_path, 'a_results')
    status = runtime.runs.status(worker._run_id)
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    original = sealed_materials.resolve_material
    def other_namespace(runs, value, alias):
        record = original(runs, value, alias)
        if record and record['metadata'].get('kind') == 'experiment_stage':
            # Same alias spellings, different producer objects.
            unrelated = next(item.artifact_ref for item in value.inputs if item.source_name == 'objective_source')
            record = dict(record, source_refs={key: unrelated for key in record['source_refs']})
        return record
    monkeypatch.setattr(sealed_materials, 'resolve_material', other_namespace)
    inventory = next(item for item in open_support(runtime.runs, status, assignment)['observed_results']['sources']
        if item['kind'] == 'capture_inventory')
    assert all(entry.get('stage_materials') == [] for entry in inventory['entries'] if entry.get('source_name'))
    # Consumer aliases are never parsed as producer aliases.
    assert not any(name.startswith('attachment_') for name in
        (entry.get('source_name') or '' for entry in inventory['entries']))


@pytest.mark.parametrize('case', ['w_portfolio', 'a_results'])
def test_each_exact_object_is_delivered_once(tmp_path, case):
    """F3: aliases of one exact ArtifactRef share a single delivered copy."""
    runtime, root, worker, opened = fixed_case(tmp_path, case)
    workspace, start, entries = _context(opened)
    refs = {item.source_name: item.artifact_ref for item in runtime.runs.status(worker._run_id).inputs}
    carriers = {}
    for name, entry in entries.items():
        if 'same_source_as' in entry:
            assert refs[entry['same_source_as']] == refs[name]
            assert not {'text', 'size_bytes', 'relative_path'} & set(entry)
        else:
            carriers.setdefault(refs[name], []).append(name)
    assert all(len(names) == 1 for names in carriers.values())
    for source in observed_overview(start, workspace).values():
        for entry in source.get('entries', ()):
            if entry.get('source_name') in observed_overview(start):
                assert 'record_positions' not in entry  # The ledger view carries those records once.
    text = (Path(opened['start_here_path'])).read_text()
    for name, entry in entries.items():
        if 'text' in entry:
            assert text.count(json.dumps(entry['text'], ensure_ascii=False)) == 1










def test_formal_reviewer_open_has_no_coverage_or_delta_and_neutral_memory(tmp_path):
    runtime, root, _, _ = fixed_case(tmp_path, 'w_portfolio')
    invoke_review = root.call_tool('operation_invoke', dict(name='review', operation_id='science.object.review.v1',
        inputs=[dict(port='subject', artifact_names=['W.output']),
            dict(port='scientific_materials', artifact_names=['H.output'])],
        instruction='Assess the exact subject independently.'))
    assert invoke_review
    reviewer = attached_worker(runtime, root, 'review')
    opened = reviewer.call_tool('worker_open_assignment', {})
    start_text = Path(opened['start_here_path']).read_text()
    context_text = (Path(opened['workspace_path'])/'worker-context.json').read_text()
    for text in (start_text, context_text, json.dumps(opened)):
        assert 'mechanism_coverage' not in text and 'handoff_delta' not in text and 'a_history' not in text
    start = json.loads(start_text)
    memory = json.loads(context_text).get('attempt_memory', start.get('attempt_memory'))
    assert memory is not None
    assert not any(key in json.dumps(memory) for key in ('worker_verdict', 'root_judgment', 'scientific_fields'))
    # Inline originals are exactly the bound review inputs, never other tasks' conclusions.
    bound = {item.source_name for item in runtime.runs.status(reviewer._run_id).inputs}
    assert set(start.get('inline_inputs', {})) <= bound
    assert 'The untested mechanisms may alter target ranking.' not in start_text + context_text
    # A different caller cannot open the formal review (independence boundary).
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    value = runtime.runs.status(reviewer._run_id)
    impostor = LocalWorkerMCPRouter(runtime.runs, operation_id=value.operation_id,
        operation_digest=value.operation_digest, run_id=value.run_id, trusted_caller=('source-test-session', 'other'))
    with pytest.raises(Exception):
        impostor.call_tool('worker_open_assignment', {})


def _tagged(core):
    return {name.strip() for tags in re.findall(r'\[([a-z0-9_, ]+)\]', core) for name in tags.split(',')}


def reachable(role_instructions, clause):
    """Where a contract clause lives: 'core', or the core-tagged on-demand section."""
    from scidiscovery.artifact_agent.schema.role_result import split_reference
    core, sections = split_reference(role_instructions)
    flat = lambda text: ' '.join(text.split())
    if flat(clause) in flat(core):
        return 'core'
    names = [name for name, body in (sections or {}).items() if flat(clause) in flat(body)]
    assert names and set(names) <= _tagged(core), names
    return names


@pytest.mark.parametrize('operation', ['science.hypothesis.propose.v1', 'science.experiment.v1',
    'science.result.analyze.v1'])
def test_compact_core_names_every_reference_section_and_loses_no_contract_text(operation):
    from scidiscovery.artifact_agent.schema.role_result import split_reference, with_reference, BOUNDARY_GUIDANCE
    from scidiscovery.operations.tooling import operation_role_instructions
    from tests.operations.test_root_scheduler_ownership import structured_catalog
    full = operation_role_instructions(structured_catalog().operation(operation))
    core, sections = split_reference(full)
    assert sections and 2000 <= len(core.encode()) <= 4600
    # Every on-demand section is named by a checklist item: no responsibility is unreachable.
    assert set(sections) <= _tagged(core)
    assert split_reference(with_reference(core, sections)) == (core, sections)
    assert sections['boundary_declarations'] == BOUNDARY_GUIDANCE.strip()
    # Core keeps at most a few boundary sentences; the full boundary text is on demand once.
    assert BOUNDARY_GUIDANCE.strip()[:200] not in core


def test_removed_role_sentences_are_only_code_enforced_rules():
    """Old role text = reference sections + the listed removals (each enforced in code)."""
    from scidiscovery import general_science_resources as h, general_science_experiment_task as w
    from scidiscovery import general_science_result_analysis as a
    from scidiscovery.artifact_agent.schema.role_result import split_reference
    flat = lambda text: ' '.join(text.split())
    for module, full, removed in (
            (h, h.IDEATOR_PROMPT, ('never invent one or manufacture a qualified foundation', 'reviews are not inherited')),
            (w, w.PROMPT, ('never author hashes or internal bindings',)),
            (a, a.PROMPT, ('Do not invent experiment/plan/objective keys', 'do not author their duplicate handoff fields'))):
        core, sections = split_reference(full)
        joined = flat(' '.join(sections.values()))
        for sentence in removed:
            assert sentence not in joined and sentence not in flat(core)


@pytest.mark.parametrize('broken', ['receipt', 'support'])
def test_unverifiable_support_is_explicit_and_originals_stay_readable(tmp_path, monkeypatch, broken):
    from scidiscovery.artifact_agent.service import sealed_materials, worker_start
    from scidiscovery.operation_contract import DiagnosticError
    runtime, _, worker, opened = fixed_case(tmp_path, 'a_results')
    if broken == 'receipt':
        original = sealed_materials.resolve_material
        def unverifiable(runs, status, alias):
            record = original(runs, status, alias)
            if record and record['metadata'].get('kind') == 'capture_inventory':
                raise DiagnosticError('Private sentinel must not appear.')
            return record
        monkeypatch.setattr(sealed_materials, 'resolve_material', unverifiable)
    else:
        def unavailable(*args, **kwargs):
            raise OSError('Private sentinel must not appear.')
        monkeypatch.setattr(worker_start, 'open_support', unavailable)
    reopened = worker.call_tool('worker_open_assignment', {})
    assert reopened['state'] == 'opened'
    start = json.loads(Path(reopened['start_here_path']).read_bytes())
    assert 'Private sentinel' not in json.dumps(start)
    if broken == 'receipt':
        observed = start['observed_results']
        assert observed['omitted'] and 'unverified' in observed['basis']
        assert all(item['reason'] == 'material_receipt_unverifiable' for item in observed['omitted'])
        source = observed['omitted'][0]['source_name']
        binding = next(item for item in runtime.runs.status(worker._run_id).inputs if item.source_name == source)
        if binding.exposure == 'file_reference':
            materialized = worker.call_tool('worker_materialize_input', dict(source_name=source))
            _, restored = copied_pages(Path(opened['workspace_path']), materialized['relative_path'], file=True)
        else:
            _, restored = copied_pages(Path(opened['workspace_path']), source, full=True)
        assert json.loads(restored) == json.loads(runtime.artifacts.read(binding.artifact_ref))
    else:
        assert 'unknown' in start['support_status']['basis']
        assert all(start['support_status'][key] == 'unavailable:generation_error:OSError'
            for key in ('exact_duplicates', 'inline_inputs', 'observed_results'))
        copied_pages(Path(opened['workspace_path']), 'objective_source', full=True)


def test_omitted_inventory_never_becomes_a_duplicate_display_representative(monkeypatch):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service import sealed_materials, worker_start
    def ref(name):
        return ArtifactRef(artifact_id=name, sha256=hashlib.sha256(name.encode()).hexdigest(), kind='fixture',
            schema_id='opaque')
    first_ref, second_ref, leaf_ref = (ref(name) for name in ('first', 'second', 'leaf'))
    entry = dict(path='scratch/artifacts/result.json', status='retained', reference='attachment_001')
    small = dict(coverage='complete', attempt_inventory='declared_author_reported', entries=[entry])
    big = dict(small, source_declarations=['x' * 2000])
    payloads = {first_ref: canonical_json(big), second_ref: canonical_json(small), leaf_ref: b'{"outcome":"failed"}'}
    bindings = [SimpleNamespace(source_name=name, artifact_ref=original, media_type='application/json')
        for name, original in (('first_inventory', first_ref), ('second_inventory', second_ref), ('result', leaf_ref))]
    mapping = {'entries': [dict(path=entry['path'], artifact_ref=leaf_ref.model_dump(mode='json'))]}
    def resolve(runs, status, source):
        return {'metadata': {'kind': 'capture_inventory', 'capture_map': mapping}} if source.endswith('inventory') else None
    monkeypatch.setattr(sealed_materials, 'resolve_material', resolve)
    monkeypatch.setattr(worker_start, 'OBSERVED_TOTAL_BYTES', 1000)
    artifacts = SimpleNamespace(read=lambda original: payloads[original], catalog=lambda original:
        SimpleNamespace(size_bytes=len(payloads[original]), labels={'tool_producer_run': 'fixture'}))
    observed = worker_start._observed_results(SimpleNamespace(artifacts=artifacts), None, bindings,
        {item.artifact_ref: item.source_name for item in bindings}, {})
    assert observed['omitted'] == [dict(source_name='first_inventory', reason='overview_byte_limit')]
    (shown,) = observed['sources']
    assert shown['source_name'] == 'second_inventory'
    assert shown['entries'][0]['source_name'] == 'result'
    assert 'same_entry_as' not in shown['entries'][0]
    assert 'python tools/read_input.py SOURCE_NAME' in observed['omitted_read']


def test_source_m1_open_and_copied_input_and_reference_readers(source_catalog, tmp_path):
    source_catalog()
    import json, subprocess, sys, shlex
    from pathlib import Path
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter, WorkerToolError
    from scidiscovery.artifact_agent.schema.role_result import split_reference
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    from scidiscovery.operations.tooling import operation_role_instructions
    root = tmp_path; project = root/'project'; project.mkdir()
    runtime = open_runtime(project_root=project, state_root=root/'state', worker_backend='local')
    catalog = runtime.operation_catalog
    instance = runtime.scheduler_bindings.create_instance(name='m1', title='M1 source', objective='Read frozen originals.')
    router = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
        instance=instance.instance_id, operation_catalog=catalog))
    original = 'Preserve original restrictions; target support remains unknown.'
    router.call_tool('artifact_ingest_text', dict(name='task', text=original))
    router.call_tool('operation_invoke', dict(name='H', operation_id='science.hypothesis.propose.v1',
        inputs=[dict(port='subject', artifact_names=['task'])], instruction='Propose a bounded mechanism.'))
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='H')
    compiled = catalog.operation('science.hypothesis.propose.v1')
    identity = ('source-m1-session', 'source-m1-thread')
    runtime.runs.worker_connections.attach(run_id=run_id, platform_session=identity[0], thread_id=identity[1])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=run_id, trusted_caller=identity)
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['workspace_path']); frozen = Path(opened['assignment_path']).read_bytes()
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    assert 'budget' not in opened and 'narrative_instruction' not in opened
    assert start['budget']['deadline_at'] == opened['deadline_at']
    context = json.loads((workspace/'worker-context.json').read_bytes())
    role_guide = next(item for item in start['guides'] if item['name'] == 'role_reference')
    guide_command = shlex.split(role_guide['read'])
    assert guide_command[:2] == ['python', 'tools/read_input.py']
    assert guide_command[-1].endswith('/SECTION')
    guides = json.loads((workspace/guide_command[2]).read_bytes())['guides']
    assignment = json.loads(frozen)
    assert 'guides' not in context
    assert split_reference(assignment['role_instructions']) == (start['role_instructions'], guides['role_reference'])
    def read(*args):
        response = subprocess.check_output([sys.executable, '-I', 'tools/read_input.py', *args],
            cwd=workspace, text=True, timeout=10)
        return response.rsplit('\n[read_input: ', 1)[0]
    assert read('subject', '--full').strip() == original
    section = json.loads(read(*guide_command[2:-1], guide_command[-1].replace('/SECTION', '/h_understanding')))
    assert section == guides['role_reference']['h_understanding']
    outside = root/'outside.txt'; outside.write_text('not an assignment material')
    denied = subprocess.run([sys.executable, '-I', 'tools/read_input.py', str(outside), '--file'],
        cwd=workspace, capture_output=True, text=True, timeout=10)
    assert denied.returncode != 0 and 'source must be a file within this workspace' in denied.stdout
    assert 'not an assignment material' not in denied.stdout
    worker.call_tool('worker_open_assignment', {})
    assert Path(opened['assignment_path']).read_bytes() == frozen
    impostor = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=run_id, trusted_caller=('other', 'other'))
    try:
        impostor.call_tool('worker_open_assignment', {})
    except WorkerToolError:
        pass
    else:
        raise AssertionError('unattached caller opened an assignment')
    for operation in ('science.hypothesis.propose.v1', 'science.experiment.v1', 'science.result.analyze.v1'):
        role = operation_role_instructions(catalog.operation(operation))
        modern = startup_document(dict(role_instructions=role, inputs=[]), on_demand=True)
        frozen_view = startup_document(dict(role_instructions=role, inputs=[]), reader_navigation=3)
        assert frozen_view['role_instructions'] == role
        assert 'role' in frozen_view['reading']
        assert 'Safety (always)' in modern['role_instructions']
        assert 'mechanism_coverage' not in role and 'handoff_delta' not in role
        if operation == 'science.experiment.v1':
            assert 'Native local execution' in modern['role_instructions'] or 'native' in modern['role_instructions']
