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


def _transform(catalog, operation_id, values):
    operation = catalog.operation(operation_id)
    outputs = _executor_callable(operation)(values)
    # Retain the old corpus's output cardinality/codec boundary without creating Runs.
    assert _transform_outputs(operation, outputs)
    return outputs


@pytest.mark.parametrize("operation_id", (
    "scidiscovery.curve-reference-coverage.v1",
    "scidiscovery.objective-coverage.v1",
))
def test_curve_coverage_components(component_catalog, operation_id):
    values = {
        "experiment_plan": (_plan().canonical_json(),),
        "reference_bundles": (_bundle().canonical_json(),),
    }
    if operation_id == "scidiscovery.objective-coverage.v1":
        values.update(objective=(_objective_fixture()[2],),
                      curve_contracts=(_contract().canonical_json(),))
    else:
        values["curve_contract"] = (_contract().canonical_json(),)
    outputs = _transform(component_catalog, operation_id, values)
    assert set(outputs) == {"coverage_report"}
    assert json.loads(outputs["coverage_report"][0])


# Each graph names exact ports and required parent links. All links are removed one
# at a time, so negative coverage is broader than the old corpus's one edge per guard.
_GUARD_GRAPHS = (
    ("science.parameter.uncertainty.v1", {
        "parameter_requirements": (), "device_parameters": (),
        "parameter_coverage": ("parameter_requirements", "device_parameters"),
    }),
    ("scidiscovery.curve-score.v1", {
        "curve_contract": (), "experiment_plan": (),
        "curve_bundle": ("curve_contract", "experiment_plan"),
    }),
    ("scidiscovery.objective-coverage.v1", {
        "objective": (), "experiment_plan": ("objective",),
        "curve_contracts": ("experiment_plan",),
    }),
    ("tcad.study.execute", {
        "project": (), "capability": (), "experiment_plan": (),
        "review": ("project", "capability", "experiment_plan"),
    }),
    ("tcad.runtime-attestation.v1", {
        "execution_package": (), "runtime_manifest": ("execution_package",),
        "runtime_outputs": ("execution_package",),
    }),
    ("tcad.curve-bundle.sprocess-log.v1", {
        "solver_output": (), "runtime_attestation": ("solver_output",),
    }),
    ("tcad.curve-bundle.sprocess-plx.v1", {
        "runtime_manifest": (), "solver_outputs": (),
        "runtime_attestation": ("runtime_manifest", "solver_outputs"),
    }),
    ("science.experiment.materialize.v1", {
        "scientific_foundation": (),
        "research_objective": ("scientific_foundation",),
        "hypothesis_portfolio": ("scientific_foundation",),
        "critic_review": ("scientific_foundation", "hypothesis_portfolio"),
        "experiment_design_intent": ("scientific_foundation", "research_objective", "hypothesis_portfolio", "critic_review"),
    }),
)


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
