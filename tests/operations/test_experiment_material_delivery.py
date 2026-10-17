"""Real input binding and lazy file delivery, without solver or model processes."""
import hashlib
from dataclasses import replace

import pytest

from scidiscovery.agent_execution_settings import MaterialInputSettings
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal
from scidiscovery.operations.invoke import InvocationArtifact, preflight_operation
from scidiscovery.operations.input_validation import OperationInvocationError
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN


@pytest.fixture
def catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))


def test_material_budget_rejects_before_any_content_read(catalog):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    compiled=catalog.operation('science.experiment.v1')
    def artifact(name,size,schema='opaque',media='application/pdf'):
        return InvocationArtifact(name, ArtifactRef(artifact_id=name,kind='material',sha256='a'*64,schema_id=schema),schema,media,size)
    inputs={p.name:() for p in compiled.spec.inputs}
    goal = _foundation()
    source = artifact('objective',len(goal),'scidiscovery.scientific-foundation.v1','application/json')
    source = replace(source, ref=source.ref.model_copy(update={'sha256': hashlib.sha256(goal).hexdigest()}))
    proposal = canonical_json(_proposal(hypothesis_keys=('bounded_mechanism',)))
    hypothesis = artifact('hypothesis', len(proposal), 'scidiscovery.hypothesis-proposal.v2', 'application/json')
    hypothesis = replace(hypothesis, ref=hypothesis.ref.model_copy(update={'sha256': hashlib.sha256(proposal).hexdigest()}),
        labels=(('operation_id', 'science.hypothesis.propose.v1'), ('operation_output_port', 'hypothesis_portfolio')),
        producer_run_id='fixture_hypothesis_author')
    inputs['subject']=inputs['hypothesis_portfolio']=(hypothesis,)
    inputs['objective_source']=(source,)
    inputs['scientific_materials']=(artifact('paper',4_714_974),)
    def forbidden(ref):raise AssertionError('Rejected inputs must not be read')
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(compiled,name='large',artifacts_by_port=inputs,instruction='Read',read_artifact=forbidden,
            material_settings=MaterialInputSettings(max_item_bytes=4_000_000))
    assert error.value.reason_code=='input_item_too_large'
    assert 'paper' in error.value.details[0]['message'] and '4714974' in error.value.details[0]['message']
    inputs['scientific_files']=(artifact('grid',10),)
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(compiled,name='total',artifacts_by_port=inputs,instruction='Read',read_artifact=forbidden,
            material_settings=MaterialInputSettings(max_total_bytes=4_714_974))
    assert error.value.reason_code=='input_total_too_large'
    assert 'grid' in error.value.details[0]['message'] and 'max_total_bytes' in error.value.details[0]['message']

    # Metadata-only boundary checks exercise GB budgets without allocating GBs.
    inputs['scientific_files']=()
    inputs['scientific_materials']=(artifact('paper',2_000_000_000),)
    originals = {source.ref: goal, hypothesis.ref: proposal}
    bound=preflight_operation(compiled,name='boundary',artifacts_by_port=inputs,instruction='Read',read_artifact=lambda ref: originals[ref] if ref in originals else forbidden(ref))
    assert next(v for v in bound.inputs if v.artifact_name=='paper').exposure=='file_reference'
    inputs['scientific_materials']=(artifact('paper',2_000_000_001),)
    with pytest.raises(OperationInvocationError) as error:
        preflight_operation(compiled,name='over',artifacts_by_port=inputs,instruction='Read',read_artifact=forbidden)
    assert error.value.reason_code=='input_item_too_large'
    bound=preflight_operation(compiled,name='configured',artifacts_by_port=inputs,instruction='Read',read_artifact=lambda ref: originals[ref] if ref in originals else forbidden(ref),
        material_settings=MaterialInputSettings(max_item_bytes=3_000_000_000,max_total_bytes=3_000_000_000))
    assert next(v for v in bound.inputs if v.artifact_name=='paper').exposure=='file_reference'


def test_configuration_owned_declarations_use_default_and_explicit_frozen_limits(catalog):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.invoke import material_input_limit
    compiled = catalog.operation('science.evidence.extract.v1')
    port = next(p for p in compiled.spec.inputs if p.name == 'source_material')
    assert port.max_item_bytes is None
    assert material_input_limit(port, MaterialInputSettings()) == 2_000_000_000
    attachment = next(p for p in compiled.spec.outputs if p.name == 'attachments')
    assert attachment.max_item_bytes is None and attachment.collection.max_total_bytes is None
    assert port.model_copy(update={'exposure': 'on_demand'}).issue() == 'port_size_invalid'
    assert attachment.model_copy(update={'agent_visible': True}).issue() == 'port_size_invalid'
    def bound(size, **kwargs):
        artifact = InvocationArtifact('paper', ArtifactRef(artifact_id='paper', kind='material',
            sha256='a' * 64, schema_id='opaque'), 'opaque', 'application/pdf', size)
        inputs = {p.name: () for p in compiled.spec.inputs}
        inputs['source_material'] = (artifact,)
        return preflight_operation(compiled, name='extract', artifacts_by_port=inputs,
            instruction='Read the exact material.', read_artifact=lambda _: pytest.fail('file must stay lazy'), **kwargs)
    assert bound(2_000_000_000).inputs[0].exposure == 'file_reference'
    with pytest.raises(OperationInvocationError, match='input_item_too_large'):
        bound(2_000_000_001)
    assert bound(2_000_000_001, material_settings=MaterialInputSettings(
        max_item_bytes=3_000_000_000, max_total_bytes=3_000_000_000)).inputs[0].exposure == 'file_reference'


def test_file_delivery_preserves_declared_limits_and_bounds_aggregate_inline(catalog):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.operations.invoke import material_input_limit
    compiled=catalog.operation('science.experiment.v1')
    port=next(p for p in compiled.spec.inputs if p.name=='scientific_files')
    concrete=port.model_copy(update={'schema_id':'opaque','media_types':('image/png',),'max_item_bytes':100})
    assert concrete.issue() is None
    assert material_input_limit(concrete,MaterialInputSettings(max_item_bytes=500))==100
    assert material_input_limit(concrete,MaterialInputSettings(max_item_bytes=50))==50
    inputs={p.name:() for p in compiled.spec.inputs}
    def item(name, size, schema, media):
        return InvocationArtifact(name,ArtifactRef(artifact_id=name,kind='material',schema_id=schema,sha256='a'*64),schema,media,size)
    goal = _foundation()
    source = item('objective',len(goal),'scidiscovery.scientific-foundation.v1','application/json')
    source = replace(source, ref=source.ref.model_copy(update={'sha256': hashlib.sha256(goal).hexdigest()}))
    proposal = canonical_json(_proposal(hypothesis_keys=('bounded_mechanism',)))
    hypothesis = item('hypothesis', len(proposal), 'scidiscovery.hypothesis-proposal.v2', 'application/json')
    hypothesis = replace(hypothesis, ref=hypothesis.ref.model_copy(update={'sha256': hashlib.sha256(proposal).hexdigest()}),
        labels=(('operation_id', 'science.hypothesis.propose.v1'), ('operation_output_port', 'hypothesis_portfolio')),
        producer_run_id='fixture_hypothesis_author')
    inputs['subject']=inputs['hypothesis_portfolio']=(hypothesis,)
    inputs['objective_source']=(source,)
    raw = b'x'*100
    inputs['scientific_materials']=tuple(replace(value, ref=value.ref.model_copy(update={'sha256':hashlib.sha256(raw).hexdigest()}))
        for value in (item(name,100,'opaque','text/csv') for name in ('a','b','c')))
    bound=preflight_operation(compiled,name='inline',artifacts_by_port=inputs,instruction='Read',
        material_settings=MaterialInputSettings(inline_max_bytes=100,inline_total_bytes=2*len(proposal)+len(goal)+200),
        read_artifact=lambda ref: goal if ref==source.ref else proposal if ref==hypothesis.ref else raw)
    assert {x.artifact_name:x.exposure for x in bound.inputs if x.port_name=='scientific_materials'}=={
        'a':'on_demand','b':'on_demand','c':'file_reference'}
