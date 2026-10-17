"""Upgrade, failed collection, proof admission and error settlement boundaries."""
import json
from pathlib import Path
import pytest


def test_abi23_golden_contracts_are_not_aliased_to_current_abi():
    # Generated once by importing the actual archived commit, not by modifying
    # current schema definitions. The fixture needs neither git nor old code in CI.
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
    from curve_score.plugin import PLUGIN as CURVE_PLUGIN
    from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    golden = json.loads((Path(__file__).parents[1] / 'fixtures/operation_digests_964713f.json').read_bytes())
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    for operation_id, digest in golden['operation_digests'].items():
        current = catalog.operation(operation_id)
        assert current.digest != digest
        with pytest.raises(KeyError):
            catalog.recorded_operation(operation_id, version=current.spec.version, digest=digest)
        assert catalog.recorded_contract_status(operation_id, version=current.spec.version, digest=digest) == 'unavailable'
        assert not catalog.can_recover(operation_id, digest, current.digest)
