"""Small production-path continuations; no solver or scientific Agent is launched."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json


def test_legacy_draft_without_coverage_or_runtime_files_does_not_advertise_them(tmp_path):
    from curve_score.analysis_workspace import materialize
    from scidiscovery.operations.workspace import WorkspaceMaterializationRequest
    draft = tmp_path/'recovery-draft'; (draft/'scratch').mkdir(parents=True)
    (draft/'scratch/numbers.json').write_text('{"value":3}')
    (tmp_path/'assignment.json').write_text('{"inputs":[],"tools":[]}')
    result = materialize(WorkspaceMaterializationRequest(operation_id='fixture', workspace=tmp_path,
        input_paths={}, provisional_roots=(draft,), edit_protocol='native'))
    start = json.loads((tmp_path/'analysis-start.json').read_bytes())
    assert result.paths['recovery_manifest'] is start['recovery']['coverage_path'] is None
    assert start['recovery']['historical_runtime_path'] is None
    assert (tmp_path/'scratch/numbers.json').read_text() == '{"value":3}'


def _mapping_fixture():
    from tests.operations.test_prior_analysis_sources import bindings, replace_manifest
    from scidiscovery.operations.input_validation import ValidationSources
    basis = dict(kind='evidence', evidence_refs=[dict(input_alias='old_plan', locator='old_plan:/proposals/0')], rationale='Conditional fixture mapping.')
    previous = canonical_json({'source_references':[dict(source_key='r', input_alias='old_curve', output_name='A',
        experiment_key='e', case_key='one', case_mapping_basis=basis)]})
    contents, descriptors = bindings(previous=previous)
    proof = json.loads(contents['proof'])
    for alias, port, value in [
            ('plan', 'experiment_plan', {'proposals':[{'experiment_key':'e','cases':[{'case_key':'one'},{'case_key':'two'}]}]}),
            ('package', 'execution_package', {'project':{'expected_outputs':[{'name':'A','case_key':None}]}})]:
        raw = canonical_json(value)
        identity = descriptors['new_curve'].artifact_ref.model_copy(update={'artifact_id':'artifact_'+alias, 'sha256':hashlib.sha256(raw).hexdigest()})
        contents[alias] = raw
        descriptors[alias] = replace(descriptors['new_curve'], source_name=alias, port_name=port,
            artifact_ref=identity, sha256=identity.sha256, size_bytes=len(raw))
        proof['bindings']['old_'+alias] = {'artifact_ref':identity.model_dump(mode='json'), 'port_name':port}
    descriptors['proof'] = replace(descriptors['proof'], parent_refs=(*descriptors['proof'].parent_refs,
        descriptors['plan'].artifact_ref, descriptors['package'].artifact_ref))
    replace_manifest(contents, descriptors, proof)
    descriptors['new_curve'] = replace(descriptors['new_curve'], output_name='A')
    descriptors['old_curve'] = replace(descriptors['old_curve'], output_name='B')
    return ValidationSources(contents, descriptors)


@pytest.mark.parametrize('defect', ['none', 'cohort', 'raw_identity', 'ambiguous', 'basis_missing'])
def test_conditional_projection_never_guesses_or_changes_identity(defect):
    from tcad_artifact.analysis_bindings import source_bindings
    from scidiscovery.operations.input_validation import ValidationSources
    sources = _mapping_fixture(); contents = dict(sources); descriptors = dict(sources.binding_descriptors)
    if defect in {'cohort', 'raw_identity'}:
        alias = 'plan' if defect == 'cohort' else 'new_curve'
        descriptors[alias] = replace(descriptors[alias], artifact_ref=descriptors[alias].artifact_ref.model_copy(update={'artifact_id':'different_identity'}))
    elif defect in {'ambiguous', 'basis_missing'}:
        prior = json.loads(contents['previous'])
        if defect == 'ambiguous':
            prior['source_references'].append({**prior['source_references'][0], 'source_key':'other', 'case_key':'two'})
        else:
            prior['source_references'][0]['case_mapping_basis']['evidence_refs'][0]['input_alias'] = 'unbound_log'
        contents['previous'] = canonical_json(prior)
    current = ValidationSources(contents, descriptors)
    before = deepcopy(contents)
    view = source_bindings(current)
    assert contents == before
    assert 'case_key' not in view['sources']['old_curve']  # Same bytes/old spelling is a different Artifact.
    if defect == 'none':
        known = view['sources']['new_curve']
        assert known['case_key'] == 'one'
        assert known['case_mapping_basis']['evidence_refs'] == [dict(input_alias='plan', locator='plan:/proposals/0')]
    else:
        assert 'case_key' not in view['sources']['new_curve']


def test_start_excerpts_are_bounded_traceable_and_skip_hidden_inputs(tmp_path):
    from curve_score.analysis_workspace import _start_file, START_LIMIT
    from scidiscovery.operations.workspace import WorkspaceMaterializationRequest
    sources = _mapping_fixture()
    visible = tmp_path / 'inputs/plan.json'; visible.parent.mkdir()
    value = {'objective':'o' * 8192, 'proposals':[
        {'objectives':['later' * 1000], 'current_objectives':['current' * 1000], 'stop_conditions':['stop' * 1000]}
        for _ in range(16)]}
    visible.write_text(json.dumps(value))
    assignment = {'instruction':'Continue the selected task.', 'inputs':[dict(source_name='plan',
        port='experiment_plan', relative_path='inputs/plan.json', historical=True)], 'tools':[]}
    (tmp_path / 'assignment.json').write_text(json.dumps(assignment))
    descriptor = sources.binding_descriptors['plan']
    descriptors = {'plan':replace(descriptor, artifact_ref=descriptor.artifact_ref.model_copy(
        update={'schema_id':'scidiscovery.experiment-portfolio.v1'})),
        'hidden_secret':replace(descriptor, source_name='hidden_secret', port_name='hidden')}
    request = WorkspaceMaterializationRequest('fixture', tmp_path, {'plan':visible}, (), binding_descriptors=descriptors)
    _start_file(request, {'restored':[], 'copy_omissions':[]})
    raw = (tmp_path / 'analysis-start.json').read_bytes(); start = json.loads(raw)
    assert len(raw) <= START_LIMIT and start['omitted'] > 0
    assert b'hidden_secret' not in raw
    assert any(item['omitted'] for item in start['excerpts'])
    for item in start['excerpts']:
        original = value
        for key in item['pointer'].strip('/').split('/'):
            original = original[int(key)] if isinstance(original, list) else original[key]
        text = original if isinstance(original, str) else json.dumps(original, ensure_ascii=False)
        assert text.startswith(item['text'])


def test_explicit_new_scientific_basis_is_not_replaced_by_history():
    from tcad_artifact.analysis_bindings import source_bindings, materialize_references
    sources = _mapping_fixture()
    reference = dict(source_key='new_claim', input_alias='new_curve', output_name='A',
        experiment_key='e', case_key='two', case_mapping_basis=dict(kind='evidence',
            evidence_refs=[dict(input_alias='plan', locator='/proposals/0/cases/1')],
            rationale='A newly argued association, different from the prior conditional claim.'))
    payload = {'evidence':[dict(source_key='new_claim', locator='new_curve')], 'source_references':[reference]}
    before = deepcopy(payload)
    materialize_references(payload, source_bindings(sources), sources.binding_descriptors)
    assert payload == before
