"""Generated owner/helper entries assign bulk scope before parallel reading."""
import json
from pathlib import Path

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.role_result import split_reference, with_reference
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.worker_start import write_worker_start
from scidiscovery.general_science_result_analysis import CORE_PROMPT, PROMPT
from tests.operations.test_r4_internal_helpers import _gateway, _result


def test_generated_analysis_entry_divides_bulk_before_reading_and_keeps_full_contract(tmp_path):
    assignment = dict(instruction='Assess the exact original criterion.', role_instructions=PROMPT,
        tools=['worker_helper'], inputs=[dict(source_name='ledger', relative_path='inputs/ledger.json',
            size_bytes=24000, media_type='application/json', exposure='on_demand', usage='evidence_inventory')])
    frozen = canonical_json(assignment)
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_bulkdivision',
        inputs=(), assignment=frozen, result_schema=b'{}')
    start = json.loads(write_worker_start(workspace, assignment).read_bytes())
    core = start['role_instructions']
    policy = start['reading']['material_division']['instruction']
    assert core == CORE_PROMPT
    assert 'Before bulk' in core and 'Before bulk' not in assignment['instruction']
    assert 'before bulk originals' in policy and 'distinct read/check scopes' in policy
    assert 'do nonoverlapping work' in core and 'do nonoverlapping work' in policy
    assert 'Analyze bound experiment_results' in core
    assert 'bounded author claims' in core and 'author_reported stays unverified' in core
    assert 'Read goal/constraints yourself' in core and "independently of W's helper" in core
    assert 'required independent numerical checks remain yours' in core.replace('\n', ' ')
    assert 'dispute/gap or required independent check' in core
    assert 'avoid routine full JSON/ledger' in core
    assert 'never full ledgers/JSON' not in core
    assert 'explicit independent-check requirement' in policy
    assert 'not personal reading or formal qualification' in policy
    assert 'helpers are unavailable/unaffordable' in policy
    assert 'bounded original selections needed or report the unresolved gap' in policy
    assert 'not a tool admission gate' in policy
    assert 'inspected scope' not in policy  # Detailed helper report rules stay with the helper.
    assert workspace.assignment_path.read_bytes() == frozen
    core_again, sections = split_reference(PROMPT)
    guides = json.loads((workspace.root/'worker-guides.json').read_bytes())['guides']['role_reference']
    assert guides == sections
    assert with_reference(core_again, {key: guides[key] for key in sections}) == PROMPT
    assert 'Full inspection may be necessary for a claim' in guides['a_reading']
    assert 'do not omit failures or negative evidence' in guides['a_reading']
    assert start['inputs'][0]['source_name'] == 'ledger'
    assert start['inputs'][0]['relative_path'] == 'inputs/ledger.json'
    # Frozen HEAD 222be70 encoded string sizes: A core 4150B + division policy 848B.
    # Check the actual generated fields, not only the module constants.
    assert len(canonical_json(core)) <= 4150
    assert len(canonical_json(policy)) <= 848
    assert len(canonical_json(core)) + len(canonical_json(policy)) <= 4998


def test_generated_helper_scans_bulk_locally_without_owner_or_permission_changes(tmp_path, monkeypatch):
    runtime, _, run_id, call, owner = _gateway(tmp_path, monkeypatch)
    parent_path = Path(owner['assignment_path'])
    parent_before = parent_path.read_bytes()
    parent = json.loads(parent_before)
    source = parent['inputs'][0]
    prepared = _result(call('worker_helper', dict(name='bulk-check',
        task='Check complete ledger rows for failed or inconsistent observations; owner checks the original criterion.',
        materials=[source['source_name']])))
    assert prepared['dispatch']['context'] == 'fresh'
    opened = _result(call('worker_open_assignment', thread='helper', parent='owner'))
    helper = json.loads(Path(opened['assignment_path']).read_bytes())
    rules = helper['role_instructions']
    assert 'assigned read/check scope' in rules and 'flag necessary overlap' in rules
    assert 'Scan bulk JSON/logs locally' in rules
    assert 'print counts, selected fields and anomaly locators' in rules
    assert 'not pretty-full JSON/ledgers or embedded stdout' in rules
    assert 'Read needed ranges' in rules
    assert 'failed/inconclusive' in rules and 'negative evidence' in rules
    assert 'supporting and contrary evidence' in rules and 'counterevidence' in rules
    assert 'inspected scope, omissions/unread ranges and uncertainties' in rules
    assert 'Distinguish checked from inferred' in rules
    assert 'no formal independent review, qualification or permission' in rules
    assert 'no edits' in rules
    assert parent_path.read_bytes() == parent_before
    assert helper['inputs'][0]['source_name'] == source['source_name']
    assert helper['inputs'][0]['relative_path'] == source['relative_path']
    for key in ('usage', 'historical', 'reference_availability', 'source_checks'):
        if key in source:
            assert helper['inputs'][0][key] == source[key]
    assert (Path(owner['workspace_path'])/source['relative_path']).read_bytes()
    assert 'worker_submit_result' not in helper['tools'] and 'worker_helper' not in helper['tools']
    assert 'error' in call('worker_submit_result', thread='helper')
    assert _result(call('worker_heartbeat'))['state'] == 'running'
    assert runtime.runs.status(run_id).state == 'running'
    # Actual frozen helper role rules were 2320B as a JSON string, including navigation.
    assert len(canonical_json(rules)) <= 2320
