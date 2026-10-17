"""Goals follow exact scientific lineage without a Root-owned projection task."""

import pytest

from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import scheduler_operation_view
from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal


def test_generic_analysis_is_available_without_domain_plugins():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL))
    analysis = catalog.operation('science.result.analyze.v1')
    assert not any(tool.name.startswith('worker_experiment') for tool in analysis.worker_tools)
    assert not any(tool.name.startswith('worker_experiment') for tool in
        catalog.operation('science.hypothesis.propose.v1').worker_tools)
    assert {port.name for port in scheduler_operation_view(analysis.spec).inputs} == {
        'subject', 'scientific_materials', 'user_context'}


def test_structured_hypothesis_cannot_omit_its_objective_key():
    from scidiscovery.general_science_components import _hypothesis_objective_context
    from scidiscovery.operation_contract import SemanticRuleViolation
    proposal = _proposal(hypothesis_keys=('mechanism',))
    proposal.pop('research_objective_key')
    with pytest.raises(SemanticRuleViolation, match='research_objective_key differs'):
        _hypothesis_objective_context(proposal, {'scientific_foundation': _foundation()}, {})
