"""Lossless display templates leave frozen bindings and original readers intact."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.run_assignment import assignment_json
from scidiscovery.artifact_agent.service import worker_start
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import BoundInput, BoundOperationCall, InvocationArtifact
from scidiscovery.operations.tooling import operation_worker_tool_names
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN


@pytest.fixture
def analysis_inputs():
    from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))
    compiled = catalog.operation('science.result.analyze.v1')
    ports = {port.name: port for port in compiled.spec.inputs}
    names = [(name, name) for name in ('subject', 'experiment_results', 'hypothesis_portfolio', 'objective_source')]
    names += [('experiment_materials', f'context_{index}') for index in range(4)]
    names += [('experiment_sources', f'original_{index}') for index in range(2)]
    names += [('experiment_files', f'asset_{index}') for index in range(22)]
    inputs, contents = [], {}
    media = ('text/plain', 'application/octet-stream', 'text/csv', 'application/json')
    for index, (port_name, alias) in enumerate(names):
        port = ports[port_name]
        raw = canonical_json(dict(index=index, scientific_value=f'精确材料 {index}'))
        schema = 'opaque'
        if port_name in {'subject', 'experiment_results'}:
            raw = canonical_json(dict(summary=f'精确报告 {index}', outcome='inconclusive', remaining_question='Pending fixture.'))
            schema = 'scidiscovery.experiment-report.v1'
        elif port_name == 'hypothesis_portfolio':
            raw = canonical_json(_proposal())
            schema = 'scidiscovery.hypothesis-proposal.v2'
        elif port_name == 'objective_source':
            raw = _foundation()
            schema = 'scidiscovery.scientific-foundation.v1'
        content_type = media[index % len(media)] if port.exposure == 'file_reference' else 'application/json'
        ref = ArtifactRef(artifact_id=alias, sha256=hashlib.sha256(raw).hexdigest(), kind='material', schema_id=schema)
        artifact = InvocationArtifact(alias, ref, schema, content_type, len(raw))
        inputs.append(BoundInput(port_name, alias, alias, artifact, port.exposure, port.usage))
        contents[alias] = raw
    return catalog, BoundOperationCall(compiled, 'analysis', tuple(inputs), 'Read only the exact selected originals.'), contents


def assignment(bound):
    from scidiscovery.artifact_agent.service.run_records import RunInputBinding
    bindings = tuple(RunInputBinding(item.port_name, item.source_name, item.artifact_name, item.artifact.ref,
        item.artifact.media_type, item.exposure, item.usage, False) for item in bound.inputs)
    return json.loads(assignment_json(bound, bindings, tool_names=operation_worker_tool_names(bound.compiled)))


def expand(start):
    templates = start.get('input_templates', [])
    return [{**(templates[item['template']] if 'template' in item else {}),
        **{key: value for key, value in item.items() if key != 'template'}} for item in start['inputs']]


def without_navigation_names(inputs):
    return [{key: value for key, value in item.items()
        if key != 'artifact_name' or item.get('artifact_name_usage') != 'navigation_only'} for item in inputs]


def test_32_compiled_inputs_expand_to_identical_display_and_shrink_net_bytes(analysis_inputs, monkeypatch):
    _, bound, _ = analysis_inputs
    original = assignment(bound)
    frozen = canonical_json(original)
    with monkeypatch.context() as baseline:
        baseline.setattr(worker_start, '_with_input_templates', lambda document: document)
        before = worker_start.startup_document(original)
    after = worker_start.startup_document(original)
    assert len(after['inputs']) == 32
    assert expand(after) == without_navigation_names(before['inputs'])
    assert before['inputs'] == original['inputs']
    assert any('reference_availability' in template for template in after['input_templates'])
    assert [item['source_name'] for item in after['inputs']] == [item['source_name'] for item in original['inputs']]
    assert canonical_json(original) == frozen
    assert 'input_templates[INDEX]' in after['reading']['inputs']
    assert 'do not imply a common source, port, permission or validation' in after['reading']['inputs']
    before_index = len(canonical_json(before['inputs']))
    after_index = len(canonical_json(dict(inputs=after['inputs'], input_templates=after['input_templates'])))
    before_full, after_full = len(canonical_json(before)), len(canonical_json(after))
    assert before_index - after_index > 4000
    assert before_full - after_full > 4000
    if directory := os.environ.get('SCID_TEST_LOG_DIR'):
        Path(directory).mkdir(exist_ok=True)
        Path(directory, 'node3-startup-metrics.json').write_text(json.dumps(dict(input_count=32,
            before_index_bytes=before_index, after_index_bytes=after_index,
            before_startup_bytes=before_full, after_startup_bytes=after_full,
            net_startup_saved_bytes=before_full-after_full)))


def test_templates_preserve_mixed_permission_history_and_unavailable_exceptions(analysis_inputs):
    _, bound, _ = analysis_inputs
    original = assignment(bound)
    # Exercise projected binding differences; this does not assert scientific admission.
    item = original['inputs'][-1]
    item.update(usage='prior_signal', exposure='on_demand', historical=True, reference_availability='unresolved',
        source_origin='user_via_scheduler', same_source_as='original_0')
    item.pop('materialization')
    item.pop('materialize_tool')
    original['inputs'][-2]['reference_availability'] = 'unavailable'
    original['inputs'][-3]['historical'] = 0  # Equality alone must not conflate bool and integer.
    before = deepcopy(original)
    start = worker_start.startup_document(original)
    assert expand(start) == without_navigation_names(original['inputs'])
    assert original == before
    rendered = start['inputs'][-1]
    for key in ('source_name', 'usage', 'exposure', 'historical', 'reference_availability', 'source_origin', 'same_source_as'):
        assert rendered[key] == item[key]
    assert start['inputs'][-2]['reference_availability'] == 'unavailable'
    assert type(start['inputs'][-3]['historical']) is int


def test_small_index_keeps_flat_display_when_template_explanation_costs_more():
    inputs = [dict(source_name=f'item_{index}', description='Short') for index in range(2)]
    start = worker_start.startup_document(dict(inputs=inputs))
    assert start['inputs'] == inputs and 'input_templates' not in start
    assert 'template INDEX' not in start['reading']['inputs']


def test_changed_startup_layout_requires_new_selection_and_pages_every_input(analysis_inputs, monkeypatch, tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    from tests.artifact_agent.test_input_reader import body, replay_arguments, next_arguments, finished
    _, bound, contents = analysis_inputs
    original = assignment(bound)
    (tmp_path/'assignment.json').write_bytes(canonical_json(original))
    with monkeypatch.context() as baseline:
        baseline.setattr(worker_start, '_with_input_templates', lambda document: document)
        old = worker_start.startup_document(original)
    path = tmp_path/'worker-start.json'
    path.write_bytes(canonical_json(old))
    first = read(tmp_path, 'worker-start.json', file=True, budget=1024)
    old_handle = replay_arguments(first)[1]
    path.write_bytes(canonical_json(worker_start.startup_document(original)))
    with pytest.raises(ValueError, match='changed'):
        read(tmp_path, selection_id=old_handle, offset=0, budget=1024)
    reply = read(tmp_path, 'worker-start.json', file=True, offset=0, budget=1024)
    assert replay_arguments(reply)[1] != old_handle
    parts, pages = [], 0
    while True:
        assert len(reply.encode()) <= 1024
        parts.append(body(reply)); pages += 1
        if finished(reply):
            break
        reply = read(tmp_path, selection_id=replay_arguments(reply)[1], offset=int(next_arguments(reply)[3]), budget=1024)
    restored = json.loads(''.join(parts))
    assert pages > 1 and expand(restored) == without_navigation_names(original['inputs'])
    assert (tmp_path/'assignment.json').read_bytes() == canonical_json(original)
    assert json.loads(body(read(tmp_path,'assignment.json',file=True,pointers=['/inputs/0/artifact_name']))) == original['inputs'][0]['artifact_name']
    source=original['inputs'][0]['source_name']
    (tmp_path/'inputs').mkdir()
    (tmp_path/original['inputs'][0]['relative_path']).write_bytes(contents[source])
    assert body(read(tmp_path,source)) == contents[source].decode()


def test_navigation_omission_preserves_other_names_and_typed_scalar_differences(analysis_inputs):
    _, bound, _ = analysis_inputs
    original = assignment(bound)
    original['inputs'][-1]['artifact_name_usage'] = 'claim'
    original['inputs'][-2]['reference_availability'] = False
    original['inputs'][-3]['reference_availability'] = 0
    before = deepcopy(original)
    start = worker_start.startup_document(original)
    restored = expand(start)
    assert restored == without_navigation_names(original['inputs'])
    assert restored[-1]['artifact_name'] == original['inputs'][-1]['artifact_name']
    assert restored[-2]['reference_availability'] is False
    assert type(restored[-3]['reference_availability']) is int
    assert original == before


def test_navigation_only_small_index_keeps_flat_display_when_guidance_costs_more():
    inputs = [dict(source_name='one',artifact_name='tiny',artifact_name_usage='navigation_only')]
    start = worker_start.startup_document(dict(inputs=inputs))
    assert start['inputs'] == inputs
