"""Delivered strategy policy and sealed continuation, using synthetic evidence.

These checks cover engineering contracts, not a live model's research choices or
performance on an unidentified distribution.
"""
import json

import pytest

from scidiscovery.operations.tooling import operation_role_instructions
from scidiscovery.operations.invoke import operation_port_json_schema, operation_primary_output
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_hypothesis_objective_boundary import _proposal


@pytest.fixture(scope="module")
def catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL))


def _assert_conditional_proposal_policy(role):
    role = " ".join(role.split())
    assert "Factual premises require exact evidence" in role
    assert "uncertain assumptions may be explicit conditional hypotheses" in role
    assert "Prior proof of efficacy or generalization is not required" in role
    assert "cannot be specified or prospectively tested remain blockers" in role
    assert "no supported candidate can be delivered" not in role


def test_generated_proposal_contract_allows_prospective_evidence(catalog):
    operation = "science.hypothesis.propose.v1"
    _assert_conditional_proposal_policy(operation_role_instructions(catalog.operation(operation)))
    compiled = catalog.operation(operation)
    schema = operation_port_json_schema(compiled, operation_primary_output(compiled))
    semantic = json.dumps(schema["x-scidiscovery-semantic-constraints"])
    assert "Unresolved assumptions may be explicitly conditional" in semantic
    assert "prior efficacy or generalization is not a prerequisite" in semantic
    assert "prior efficacy is not required" in catalog.operation(operation).spec.description.purpose


def test_stale_supported_candidate_prerequisite_fails_delivered_policy(monkeypatch):
    from scidiscovery.general_science_resources import Resources
    monkeypatch.setattr(Resources, "ideator_prompt",
        "If the current model set is insufficient and no supported candidate can be delivered, report the bounded gap.")
    stale = compile_catalog((CORE_PLUGIN, GENERAL))
    with pytest.raises(AssertionError):
        _assert_conditional_proposal_policy(operation_role_instructions(stale.operation("science.hypothesis.propose.v1")))


@pytest.mark.parametrize("blocker", [
    "A required original is unavailable and cannot be obtained within permissions.",
    "No remaining budget permits the minimal test plus analysis and closeout.",
])
def test_existing_fields_accept_specific_incomplete_closeout(catalog, blocker):
    from scidiscovery.general_science_result_analysis import validate_context
    from scidiscovery.operations.input_validation import ValidationSources
    from scidiscovery.artifact_agent.schema.common import canonical_json
    proposal = _proposal(hypothesis_keys=("local_refinement",))
    report = {"summary": "Local route suspended; global work remains incomplete.",
        "overall_verdict": "inconclusive", "claim_allowed": False,
        "limitations": [blocker], "remaining_contradiction": "Unfinished original requirements remain.",
        "next_action": "Close out honestly incomplete and retain the best eligible candidate."}
    validate_context(report, ValidationSources({"hypothesis_portfolio": canonical_json(proposal)}, {}), {})
