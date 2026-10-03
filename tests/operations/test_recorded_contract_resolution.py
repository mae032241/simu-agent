"""Exact recorded identity is distinct from current scientific admission."""
from dataclasses import replace
from types import SimpleNamespace as S
import pytest

from scidiscovery.operations.catalog import CompiledCatalog, compile_catalog
from tests.operations.test_tcad_result_analysis import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import RootOperationRoutes


def test_transform_checks_use_its_recorded_ports_and_consequence():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    old = catalog.operation('science.intake.split.v1')
    changed = replace(old, digest='f' * 64, spec=old.spec.model_copy(update={
        'consequence': 'explore', 'inputs': (), 'outputs': ()}))
    available = CompiledCatalog({old.spec.operation_id: changed},
        historical_operations={(old.spec.operation_id, old.digest): old})
    assert available.recorded_contract_status(old.spec.operation_id, version=old.spec.version,
        digest=old.digest) == 'supported_historical'
    assert available.recorded_contract_status(old.spec.operation_id, version=old.spec.version,
        digest=changed.digest) == 'current'
    assert available.recorded_contract_status(old.spec.operation_id, version='other',
        digest=old.digest) == 'unavailable'
    for digest in ('', '0' * 64):
        with pytest.raises(KeyError):
            available.recorded_operation(old.spec.operation_id, version=old.spec.version, digest=digest)
    refs = {p.name: 'output-' + p.name for p in old.spec.outputs}
    inputs = {p.name: [S(ref='input-' + p.name)] for p in old.spec.inputs}
    family = S(operation_id=old.spec.operation_id, operation_version=old.spec.version, contract_availability='current',
        operation_digest=old.digest, members=[S(port_name=key, ref=ref) for key, ref in refs.items()])
    envelope = S(parent_refs=('bound-parent',), labels={})
    facade = S(_operation_catalog=available, artifacts=S(catalog=lambda _: envelope),
        _transform_output_family=lambda *args: family,
        _transform_input_groups=lambda producer, _: inputs if producer is old else None,
        runs=S(signal_for_output=lambda *args, **kwargs: S(verdict='blocked')))
    # Current policy's explore consequence cannot rewrite the old source origin.
    artifact = S(ref='output', artifact_name='subject', labels=(('scientific_claim_admissible', 'false'),))
    assert RootOperationRoutes._claim_restriction_is_reviewable(facade, artifact)
    requirement = S(output_ports=tuple(refs), input_ports=tuple(inputs))
    bound = S(compiled=S(spec=S(complete_transform_family=requirement)),
        inputs=tuple(S(port_name=key, artifact_name=key, artifact=S(ref=ref)) for key, ref in
            [*refs.items(), *((key, values[0].ref) for key, values in inputs.items())]))
    RootOperationRoutes._validate_complete_transform_family(facade, bound)
    # The current contract is unchanged and still governs new requests.
    assert available.operation(old.spec.operation_id) is changed
    family.contract_availability = 'historical'
    assert not RootOperationRoutes._claim_restriction_is_reviewable(facade, artifact)
