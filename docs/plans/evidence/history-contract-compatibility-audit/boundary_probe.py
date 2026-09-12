from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from tests.operations.test_m6c_producer_topology_removal import _catalog, _produced_artifact, _routes, _bound, _input
from scidiscovery.artifact_agent.interfaces.mcp_root_run_routes import RootRunRoutes
from scidiscovery.operations.invoke import OperationInvocationError, _validate_input_content

@pytest.fixture(scope='module')
def catalog():
    return _catalog()

@pytest.mark.parametrize('consumer,port,producer,output',[
 ('science.experiment.materialize.v1','hypothesis_portfolio','science.hypothesis.revise.v1','hypothesis_portfolio'),
 ('science.experiment.revise.v1','prior_draft','science.experiment.revise.v1','experiment_plan'),
 ('tcad.deck.author.revise.v1','prior_project','tcad.deck.author.initial.v1','project'),
 ('science.evidence.qualify.v1','extraction_primary','science.evidence.extract.v1','scientific_intake'),
 ('tcad.deck.author.initial.v1','experiment_plan','science.experiment.revise.v1','experiment_plan'),
])
def test_existing_gate_rejects_historical_even_with_current_review(catalog,consumer,port,producer,output):
    artifact,envelope=_produced_artifact(catalog,producer,output,'historical')
    envelope.labels['operation_digest']='0'*64
    routes=_routes(catalog,{artifact.ref.artifact_id:envelope})
    routes._is_exact_reviewer_output=Mock(return_value=True)
    op=catalog.operation(consumer)
    usage=next(p.usage for p in op.spec.inputs if p.name==port)
    with pytest.raises(OperationInvocationError) as err:
        routes._validate_producer_output_admission(_bound(op,_input(port,usage,artifact)))
    assert err.value.reason_code=='input_producer_contract_changed'
    assert err.value.port==port

def test_historical_payload_hidden_when_handoff_cannot_parse(catalog):
    op=catalog.operation('science.experiment.design.v1')
    routes=RootRunRoutes()
    routes._operation_catalog=catalog
    routes.artifacts=SimpleNamespace(read=Mock(return_value=b'{"sealed":true}'))
    status=SimpleNamespace(state='completed',output_ref=object(),operation_id=op.spec.operation_id,operation_version=op.spec.version,operation_digest='0'*64,signal=None)
    assert routes._sealed_output(status)==('invalid',None)
    routes.artifacts.read.assert_not_called()

def test_input_content_check_does_not_validate_historical_payload_shape(catalog):
    op=catalog.operation('science.object.review.v1')
    artifact,envelope=_produced_artifact(catalog,'science.experiment.revise.v1','experiment_plan','old_shape')
    envelope.labels['operation_digest']='0'*64
    routes=_routes(catalog,{artifact.ref.artifact_id:envelope})
    routes._validate_producer_output_admission(_bound(op,_input('experiment_plan','prior_signal',artifact)))
    reader=Mock(return_value=b'{}')
    _validate_input_content(op,(_input('experiment_plan','prior_signal',artifact),),reader)
    reader.assert_not_called()

def test_historical_run_provenance_family_disappears(catalog):
    artifact,envelope=_produced_artifact(catalog,'science.evidence.extract.v1','scientific_intake','old_family')
    envelope.ref=artifact.ref
    routes=_routes(catalog,{artifact.ref.artifact_id:envelope})
    op=catalog.operation('science.evidence.extract.v1')
    routes.runs=SimpleNamespace(completed_for_output=lambda ref:SimpleNamespace(output_ref=ref,operation_id=op.spec.operation_id,operation_version=op.spec.version,operation_digest='0'*64))
    assert routes._run_output_family(envelope) is None
