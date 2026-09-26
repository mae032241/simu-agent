"""Distinct transform behavior and lineage checks, without repeating Run lifecycle."""
from types import SimpleNamespace
import json

import pytest

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    OperationInvocationError, _executor_callable, _run_guards, _transform_outputs,
)
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tests.operations.test_m2_curve_analysis_boundary import _bundle, _contract, _plan
from tests.operations.transform_fixtures import (
    _objective_fixture,
)


@pytest.fixture(scope="module")
def component_catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))


_GUARD_GRAPHS = (("tcad.runtime-attestation.v1", {
    "execution_package": (), "runtime_manifest": ("execution_package",),
    "runtime_outputs": ("execution_package",),
}),)


@pytest.mark.parametrize("operation_id,graph", _GUARD_GRAPHS)
def test_compiled_transform_guards_reject_missing_lineage(component_catalog, operation_id, graph):
    operation = component_catalog.operation(operation_id)
    assert operation.spec.guards

    def inputs(omitted=None):
        return tuple(SimpleNamespace(port_name=port, artifact=SimpleNamespace(
            ref=port, parent_refs=tuple(parent for parent in parents if (port, parent) != omitted),
        )) for port, parents in graph.items())

    _run_guards(operation, inputs(), {})
    for port, parents in graph.items():
        for parent in parents:
            with pytest.raises(OperationInvocationError) as caught:
                _run_guards(operation, inputs((port, parent)), {})
            assert caught.value.reason_code == "guard_rejected"
