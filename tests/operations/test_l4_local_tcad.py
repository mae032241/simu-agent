from __future__ import annotations


import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentCase, ExperimentPortfolio, ExperimentProposal, ExperimentValueAssessment, ResourceEstimate, ValidationCheck, ValidationDimensionPlan, ValidationPlan
from scidiscovery.operation_contract import SemanticRuleViolation
from tcad_artifact.debug_adapter import _development_arguments, _earliest_diagnostic, _source_diagnostic


def test_sdevice_initialization_uses_the_manual_backed_initial_solution_mode() -> None:
    assert _development_arguments(
        release="R-2020.09",
        solver_kind="sdevice",
        entrypoint="initialize.cmd",
        mode="initialization",
    ) == ("-i", "initialize.cmd")
    with pytest.raises(ValueError, match="unsupported for the solver"):
        _development_arguments(
            release="R-2020.09",
            solver_kind="sdevice",
            entrypoint="main.cmd",
            mode="smoke",
        )


def _portfolio() -> ExperimentPortfolio:
    proposal = ExperimentProposal(
        experiment_key="entrypoint_smoke",
        objectives=(
            "Verify one direct solver entrypoint.",
            "Verify one bounded direct solver entrypoint.",
        ),
        current_objectives=("Verify one bounded direct solver entrypoint.",),
        frozen_invariants=("No scientific claim is made.",),
        cases=(
            ExperimentCase(
                case_key="smoke",
                scientific_role="baseline",
                purpose="Check parser and terminal state.",
            ),
        ),
        required_observables=("terminal state",),
        resource_estimate=ResourceEstimate(
            case_count=1,
            relative_cost="low",
            runtime_basis="One bounded invocation.",
        ),
        stop_conditions=("Stop after terminal state.",),
        value_assessment=ExperimentValueAssessment(
            evidence_support="high",
            discrimination_power="low",
            information_gain="medium",
            cost="low",
            added_free_parameters=0,
            rationale="This closes an implementation invariant only.",
        ),
    )
    check = ValidationCheck(
        check_key="clean_completion",
        observable="terminal state",
        metric="clean completion",
        evaluation_mode="reviewed_qualitative",
        acceptance_condition="The run completes.",
        failure_action="Reject the implementation.",
        basis="Engineering smoke contract.",
    )
    required = ValidationDimensionPlan(
        applicability="required",
        rationale="The entrypoint must terminate cleanly.",
        checks=(check,),
    )
    not_applicable = ValidationDimensionPlan(
        applicability="not_applicable",
        rationale="This bounded engineering test makes no scientific claim.",
    )
    return ExperimentPortfolio(
        study_kind="engineering",
        objective="Verify one direct solver entrypoint.",
        proposals=(proposal,),
        validation_plans=(
            ValidationPlan(
                plan_key="entrypoint_smoke_plan",
                experiment_key=proposal.experiment_key,
                numerical=required,
                physical=not_applicable,
                experimental=not_applicable,
            ),
        ),
        priority_order=(proposal.experiment_key,),
        priority_rationale="Only one implementation check is required.",
    )


def test_experiment_revision_changes_content_without_replacing_identity() -> None:
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificReview
    from scidiscovery.general_science_experiment_components import (
        _experiment_revision_context,
    )
    from scidiscovery.operation_contract import SemanticRuleViolation

    prior = _portfolio()
    review = ScientificReview(
        review_target="experiment_portfolio",
        verdict="revise",
        summary="Clarify the bounded validation rationale.",
    )
    sources = {
        "prior_draft": canonical_json(prior.model_dump(mode="json")),
        "change_request": canonical_json(review.model_dump(mode="json")),
    }
    revised = prior.model_copy(
        update={"priority_rationale": "The review requested this clarification."}
    )
    _experiment_revision_context(revised.model_dump(mode="json"), sources, {})

    replacement = revised.model_copy(
        update={
            "selected_hypothesis_keys": (
                *revised.selected_hypothesis_keys, "replacement_hypothesis",
            ),
        }
    )
    with pytest.raises(SemanticRuleViolation, match="experiment identity"):
        _experiment_revision_context(
            replacement.model_dump(mode="json"), sources, {}
        )


# Bounded excerpts from the 2026-09-08 R-2020.09 author tool returns.
# Banners, host/user details and unrelated scientific source are omitted.
_AUTHOR_INIT_FAILURE = '''Checking syntax of fig4_initialization.cmd:
Syntax check complete.
Starting Tcl interpreter with inputfile: fig4_initialization.cmd
Creating structure...
Points: 545
Nodes: 547
Creating structure...
** Error **
No regions specified !
 ... aborting
'''
_AUTHOR_PARSER_FAILURE = '''Checking syntax of fig4_initialization.cmd:
space required after '=' in: 'fields.values={ZnMain=0.0'
    while executing
"init fields.values={ZnMain=0.0 ZnTail=0.0}"
    (file "fig4_initialization.cmd" line 12)
Failure during syntax check, aborting.
'''


@pytest.mark.parametrize("log,layer,message,line", (
    (_AUTHOR_INIT_FAILURE, "initialization", "No regions specified !", None),
    (_AUTHOR_PARSER_FAILURE, "parser", "space required after '='", 12),
))
def test_author_failure_log_has_the_actual_error_layer_and_locator(log, layer, message, line):
    assert _earliest_diagnostic(terminal="failed", exit_code=1, error="", log=log, output_count=0)[0] == layer
    locator = _source_diagnostic(error="", log=log)
    assert locator is not None and message in locator.message
    assert locator.source_relative_path == "fig4_initialization.cmd"
    assert locator.reported_line == line


@pytest.mark.parametrize("error,exit_code,layer", (
    ("syntax error near init", 1, "parser"),
    ("Newton failed to converge", 1, "numerical"),
    ("Failed to converge", 1, "numerical"),
    ("wall_time_exceeded", 124, "resource_limit"),
    ("required output missing", 0, "output_contract"),
))
def test_tcad_success_markers_do_not_override_the_actual_failure(error, exit_code, layer):
    log = "Checking syntax of main.cmd:\nSyntax check complete.\nContact setup complete.\nNewton iteration complete.\n"
    assert _earliest_diagnostic(terminal="failed", exit_code=exit_code, error=error, log=log, output_count=0)[0] == layer


def test_tcad_source_locator_stays_in_one_error_stack():
    log = '''Checking syntax of main.cmd:
syntax error in inner command
    while executing
"bad_command"
    (file "lib/inner.cmd" line 4)
    invoked from within
"source lib/inner.cmd"
    (file "main.cmd" line 99)
Checking syntax of other.cmd:
parse error in unrelated command
    (file "other.cmd" line 72)
'''
    locator = _source_diagnostic(error="", log=log)
    assert locator.source_relative_path == "lib/inner.cmd"
    assert locator.reported_line == 4 and locator.command_excerpt == "bad_command"
    private = _source_diagnostic(error="", log=log.replace("lib/inner.cmd", "/private/inner.cmd"))
    assert private.source_relative_path is None
    assert private.reported_line == 4 and private.line_basis == "solver_reported"
    assert _source_diagnostic(error="", log="Checking syntax of ../private.cmd:\nNo regions specified !").source_relative_path is None


@pytest.mark.parametrize("marker", (
    "--- bounded diagnostic omission ---", "--- bounded log omission ---",
))
def test_tcad_source_locator_does_not_cross_log_omissions(marker):
    head = "Checking syntax of main.cmd:\n"
    failure = "syntax error in first fragment\n"
    tail = '    while executing\n"unrelated_tail_command"\n    (file "other.cmd" line 72)\n'
    locator = _source_diagnostic(error="", log=head + failure + marker + "\n" + tail)
    assert locator.message == failure.strip()
    assert locator.source_relative_path == "main.cmd"
    assert locator.reported_line is None and locator.command_excerpt is None
    assert locator.line_basis == "log_only"
    # A header before an omitted region cannot locate a later error either.
    later = _source_diagnostic(error="", log=head + marker + "\n" + failure)
    assert later.source_relative_path is None and later.reported_line is None


from scidiscovery.operation_contract import semantic_contract
from scidiscovery.operations.spec import SemanticRuleSpec


PLAN_FIXTURE_SEMANTIC_CONTRACT = semantic_contract(SemanticRuleSpec(
    rule_id="fixture.plan.schema", description="The fixture output is a valid experiment portfolio.",
))
