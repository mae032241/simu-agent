"""Sealed producer -> analysis navigation -> exact controlled originals."""
import json

import pytest
from pathlib import Path
import shlex
import subprocess
import sys

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.input_reader import read
from tests.artifact_agent.test_input_reader import body
from tests.operations.test_native_experiment import installed, _start_native, _publish
from tests.operations.worker_fixtures import attached_worker
from tests.operations.test_worker_startup_templates import analysis_inputs


def test_published_failure_materials_remain_discoverable_and_readable_from_groups(tmp_path, installed):
    f = _start_native(tmp_path, scientific_material=True, scientific_file=True)
    originals = {}
    references = []
    for index in range(8):
        raw = canonical_json(dict(attempt=index, outcome='fail' if index < 4 else 'inconclusive',
            limitation='Retain this failed or incomplete attempt.', values=[index] * 1200))
        alias = _publish(f, f'attempt-{index}.json', raw, ['objective_source'])
        references.append(alias)
        originals[alias] = raw
    stage = f.worker.call_tool('worker_experiment_stage', dict(stage='validity',
        conclusion='All failed and incomplete attempts are retained.', materials=references))['reference']
    (f.workspace/'output/result.json').write_bytes(canonical_json(dict(payload=dict(
        summary='The bounded question remains unresolved.', outcome='inconclusive',
        remaining_question='Independent interpretation is needed.', adopted_stages=[stage]))))
    assert f.worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    subject = f.root.call_tool('run_status', dict(name='compute'))['output_artifact_name']
    f.root.call_tool('operation_invoke', dict(name='analysis', operation_id='science.result.analyze.v1',
        inputs=[dict(port='subject', artifact_names=[subject])], instruction='Independently assess every failed attempt.'))
    analyst = attached_worker(f.runtime, f.root, 'analysis')
    opened = analyst.call_tool('worker_open_assignment', {})
    workspace = Path(opened['workspace_path'])
    frozen = Path(opened['assignment_path']).read_bytes()
    assignment = json.loads(frozen)
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    groups = start['input_groups']
    assert len(start['inputs']) < len(assignment['inputs'])
    templates = start.get('input_templates', [])
    core = [{**(templates[item['template']] if 'template' in item else {}),
        **{key: value for key, value in item.items() if key != 'template'}} for item in start['inputs']]
    restored = []
    for entry in core:
        full = next(item for item in assignment['inputs'] if item['source_name'] == entry['source_name'])
        assert all(full[key] == value for key, value in entry.items() if key not in ('scientific_overview_available', 'text'))
        if 'text' in entry:  # A tiny input's complete exact original.
            assert entry['text'].encode() == f.runtime.artifacts.read(next(item.artifact_ref for item in
                f.runtime.runs.status(analyst._run_id).inputs if item.source_name == entry['source_name']))
        if entry.get('scientific_overview_available'):
            assert 'scientific_view' in full and 'scientific_view' not in entry
        restored.append(full)  # Existing same_source_as may omit repeated readable metadata.
    # Every returned exact pointer is an existing reader selection, not an
    # invented INDEX, port name or template-relative number.
    for group in groups:
        if 'members' in group:
            # Every member once by exact source_name, in pointer order; shared fields once.
            shared = {key: value for key, value in group.items() if key not in ('pointers', 'members')}
            assert len(group['members']) == len(group['pointers'])
            for pointer, member in zip(group['pointers'], group['members']):
                full = assignment['inputs'][int(pointer.rsplit('/', 1)[1])]
                assert member['source_name'] == full['source_name']
                assert all(full[key] == value for key, value in {**shared, **member}.items()
                    if key not in ('text', 'same_source_as', 'scientific_overview_available'))
        else:
            assert group['count'] == len(group['pointers'])
            command = shlex.split(group['read'])
            reply = subprocess.run([sys.executable, *command[1:]], cwd=workspace,
                text=True, capture_output=True, timeout=10, check=True)
            assert json.loads(body(reply.stdout)) == json.loads(body(read(workspace,
                'assignment.json', pointers=[group['pointers'][0]])))
        for pointer in group['pointers']:
            entry = json.loads(body(read(workspace, 'assignment.json', pointers=[pointer], budget=8192)))
            assert entry == assignment['inputs'][int(pointer.rsplit('/', 1)[1])]
            assert 'port' not in entry and 'artifact_ref' not in entry
            restored.append(entry)
            if entry.get('materialization') == 'controlled_tool_stream_only':
                materialized = analyst.call_tool('worker_materialize_input', dict(source_name=entry['source_name']))
                raw = (workspace/materialized['relative_path']).read_bytes()
                assert raw == f.runtime.artifacts.read(next(item.artifact_ref for item in
                    f.runtime.runs.status(analyst._run_id).inputs if item.source_name == entry['source_name']))
                if raw in originals.values():
                    assert json.loads(body(read(workspace, materialized['relative_path'], file=True,
                        pointers=['/outcome']))) in {'fail', 'inconclusive'}
    assert {item['source_name']: item for item in restored} == {
        item['source_name']: item for item in assignment['inputs']}
    bound = f.runtime.runs.status(analyst._run_id)
    published = f.runtime.runs.tool_evidence(f.run_id)
    file_refs = {item.artifact_ref.artifact_id for item in bound.inputs if item.port_name == 'experiment_files'}
    assert {item['artifact_ref']['artifact_id'] for item in published if item['alias'] in originals} <= file_refs
    assert Path(opened['assignment_path']).read_bytes() == frozen
    assert len(canonical_json(start)) < len(canonical_json({**start, 'inputs':assignment['inputs']}))
    # The actual copied reader defaults to sealed science, rather than expanding
    # the complete evidence-bearing experiment. Aliases keep original reads exact.
    experiment = next(item for item in assignment['inputs'] if item.get('scientific_view')
        and any(pointer == '/outcome' for pointer in item['scientific_view']['pointers']))
    response = subprocess.run([sys.executable, 'tools/read_input.py', experiment['source_name']],
        cwd=workspace, text=True, capture_output=True, timeout=10, check=True)
    overview = json.loads(body(response.stdout))
    values = {item['pointer']: item['value'] for item in overview['items'] if item['status'] == 'selected'}
    assert values['/outcome'] == 'inconclusive'
    assert values['/remaining_question'] == 'Independent interpretation is needed.'
    from scidiscovery.artifact_agent.service.input_reader import select
    assert select(overview, overview['sealed_handoff']['summary_ref']['pointer']) == 'The bounded question remains unresolved.'
    assert overview['original_read'] == 'not_confirmed'
    assert '/adopted_stages' not in values
    complete = read(workspace, experiment['source_name'], full=True, budget=8192)
    assert json.loads(body(complete))['adopted_stages'] == [stage]
    assert json.loads(body(read(workspace, experiment['source_name'], pointers=['/adopted_stages']))) == [stage]
    producer=f.runtime.runs.status(f.run_id)
    assert experiment['scientific_view']['pointers'] == ['/'+field for field in producer.decision_fields]
    root_default=f.root.call_tool('run_status', dict(name='compute'))
    assert root_default['output_delivery']=='compact'
    assert {item['pointer']:item['value'] for item in root_default['selected_output']['items']
        if item['status']=='selected'}['/outcome']=='inconclusive'
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    with pytest.raises(RootToolError):
        f.root.call_tool('run_status', dict(name='compute', output_paths=['/adopted_stages']))
    explicit=f.root.facade.run_status(name='compute', output_paths=['/adopted_stages'])
    assert explicit['output_delivery']=='selected' and explicit['selected_output']['items'][0]['value']==[stage]
    full=f.root.facade.run_status(name='compute', intent='full')
    assert full['sealed_output']['payload']['adopted_stages']==[stage]


def test_contract_groups_exclude_hidden_inputs_and_keep_exact_permissions(analysis_inputs):
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.run_assignment import assignment_json
    from scidiscovery.artifact_agent.service.run_records import RunInputBinding
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    _, bound, _ = analysis_inputs
    spec = bound.compiled.spec.model_copy(update={'inputs': tuple(
        port.model_copy(update={'agent_visible': False}) if port.name == 'experiment_files' else port
        for port in bound.compiled.spec.inputs)})
    bound = replace(bound, compiled=replace(bound.compiled, spec=spec))
    bindings = tuple(RunInputBinding(item.port_name, item.source_name, item.artifact_name, item.artifact.ref,
        item.artifact.media_type, item.exposure, item.usage, False) for item in bound.inputs)
    assignment = json.loads(assignment_json(bound, bindings, tool_names=()))
    assert not any(item['source_name'].startswith('asset_') for item in assignment['inputs'])
    assert sum(len(group['pointers']) for group in assignment['input_groups']) == 6
    assert all(int(pointer.rsplit('/', 1)[1]) < len(assignment['inputs'])
        for group in assignment['input_groups'] for pointer in group['pointers'])
    original = canonical_json(assignment)
    startup_document(assignment)
    assert canonical_json(assignment) == original
    # The group stores positions, never shared permission defaults. Different
    # usage, historical and availability values remain in their exact originals.
    assignment['inputs'][-1].update(usage='prior_signal', historical=True, reference_availability='unresolved')
    assert startup_document(assignment).get('input_groups', assignment['input_groups'])[-1]['pointers'][-1] == '/inputs/9'
    assert assignment['inputs'][-1]['usage'] == 'prior_signal'
    assert assignment['inputs'][-1]['historical'] is True


def test_small_empty_or_unrecognized_frozen_reader_keeps_flat_inputs():
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    item = dict(source_name='one', artifact_name='original', description='One original.', usage='evidence_inventory')
    assignment = dict(inputs=[item], input_groups=[dict(description='Supporting sources.', pointers=['/inputs/0'])])
    assert startup_document(assignment)['inputs'] == [item]
    assert 'input_groups' not in startup_document(assignment)
    assert startup_document(dict(inputs=[], input_groups=[]))['inputs'] == []
    assert 'input_groups' not in startup_document(assignment, reader_navigation=0)


def test_derived_scientific_input_collection_is_not_labeled_secondary(analysis_inputs, tmp_path):
    from dataclasses import replace
    from scidiscovery.artifact_agent.service.run_assignment import assignment_json
    from scidiscovery.artifact_agent.service.run_records import RunInputBinding
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    _, bound, _ = analysis_inputs
    description = 'Required exact scientific observations for the analysis conclusion.'
    spec = bound.compiled.spec.model_copy(update={'inputs': tuple(
        port.model_copy(update={'usage': 'scientific_input', 'description': description})
        if port.name == 'experiment_files' else port for port in bound.compiled.spec.inputs)})
    inputs = tuple(replace(item, usage='scientific_input') if item.port_name == 'experiment_files'
        else item for item in bound.inputs)
    bound = replace(bound, compiled=replace(bound.compiled, spec=spec), inputs=inputs)
    bindings = tuple(RunInputBinding(item.port_name, item.source_name, item.artifact_name, item.artifact.ref,
        item.artifact.media_type, item.exposure, item.usage, False) for item in inputs)
    frozen = assignment_json(bound, bindings, tool_names=('worker_materialize_input',))
    (tmp_path/'assignment.json').write_bytes(frozen)
    start = startup_document(json.loads(frozen))
    group = next(group for group in start['input_groups'] if group['description'] == description)
    assert group['count'] == 22
    for pointer in group['pointers']:
        metadata = json.loads(body(read(tmp_path, 'assignment.json', pointers=[pointer])))
        assert metadata['usage'] == 'scientific_input'
        assert metadata['description'] == description
        assert metadata['materialize_tool'] == 'worker_materialize_input'
    guidance = start['reading']['inputs']
    assert 'supporting source' not in guidance and 'Core inputs' not in guidance
    assert 'may be primary evidence required for the conclusion' in guidance
    assert (tmp_path/'assignment.json').read_bytes() == frozen
