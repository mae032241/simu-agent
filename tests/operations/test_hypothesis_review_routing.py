from __future__ import annotations

from dataclasses import replace

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import (
    RootOperationRoutes,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.cognitive import (
    CriticReview,
    HypothesisReviewForm,
    critic_progress_fingerprint,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.schema.run_signal import SchedulerSignal
from scidiscovery.artifact_agent.service.run_records import RunSlotBusy
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_components import _critic_portfolio_context
from scidiscovery.general_science_experiment_components import _object_review_context
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    InvocationArtifact,
    OperationInvocationError,
    preflight_operation,
)


def _catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))


def _ref(name: str, kind: str, schema: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"art_{name}",
        sha256=(name.encode().hex() + "0" * 64)[:64],
        kind=kind,
        schema_id=schema,
    )


def _artifact(
    name: str,
    schema: str,
    *,
    kind: str = "scientific_object",
    parents: tuple[ArtifactRef, ...] = (),
    verdict: str | None = None,
    media_type: str = "application/json",
) -> InvocationArtifact:
    return InvocationArtifact(
        artifact_name=name,
        ref=_ref(name, kind, schema),
        schema_id=schema,
        media_type=media_type,
        size_bytes=32,
        parent_refs=parents,
        handoff_verdict=verdict,
    )


def _critic(
    *,
    disposition: str = "revise_hypothesis",
    physical: str = "fail",
    falsifiability: str = "pass",
    discriminability: str = "pass",
    issue: str = "The mechanism statement is incomplete.",
) -> CriticReview:
    return CriticReview(
        disposition=disposition,
        reviews=(
            HypothesisReviewForm(
                hypothesis_key="hypothesis_a",
                physical_plausibility=physical,
                falsifiability=falsifiability,
                finite_discriminability=discriminability,
                issues=(issue,),
                smallest_resolving_action="Make one bounded correction.",
            ),
        ),
    )


def _critic_bytes(**values: str) -> bytes:
    return canonical_json(_critic(**values).model_dump(mode="json"))


def _revision_foundation_bytes() -> bytes:
    return canonical_json(
        {
            "title": "Bounded foundation",
            "objective": "Separate one bounded mechanism.",
            "summary": "One immutable observation is available.",
            "objective_contract": {
                "objective_key": "objective_a",
                "intent": "mechanism_discrimination",
                "statement": "Separate one bounded mechanism.",
                "mandatory_targets": [
                    {
                        "target_key": "target_a",
                        "observable": "A bounded response",
                        "support_requirement": "complete_observation",
                        "evidence_item_keys": ["observation_a"],
                        "rationale": "The response is the frozen target.",
                    }
                ],
                "closure_requirements": [
                    {
                        "requirement_key": "cover_target_a",
                        "description": "The bounded target must be covered.",
                        "target_keys": ["target_a"],
                    }
                ],
            },
            "items": [
                {
                    "item_key": "observation_a",
                    "item_type": "prior_observation",
                    "epistemic_status": "paper_fact",
                    "statement": "The bounded response was observed.",
                    "scope": "Fixture only.",
                    "evidence_keys": ["source_a"],
                }
            ],
            "evidence": [
                {
                    "source_key": "source_a",
                    "source_type": "frozen_input",
                    "title": "Fixture source",
                    "locator": "fixture.txt",
                }
            ],
        }
    )


def _revision_portfolio_bytes() -> bytes:
    return canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective_a",
            "stage_objective": "Separate one bounded mechanism.",
            "contradiction": "The present evidence leaves one mechanism open.",
            "evidence": [],
            "hypotheses": [
                {
                    "hypothesis_key": "hypothesis_a",
                    "statement": "A bounded mechanism changes the observable.",
                    "mechanism": "The mechanism has one finite intervention.",
                    "scope": "Fixture only.",
                    "parameters": [],
                    "predictions": [
                        {
                            "prediction_key": "prediction_a",
                            "observable": "A bounded response",
                            "expected_outcome": "The response changes direction.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "falsifier_a",
                            "observable": "A bounded response",
                            "rejection_condition": "No directional change occurs.",
                        }
                    ],
                    "competing_hypothesis_keys": [],
                    "evidence_keys": [],
                }
            ],
        }
    )


def test_critic_routes_current_uncertainty_to_experiment_design() -> None:
    portfolio = canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective_a",
            "stage_objective": "Separate two bounded mechanisms.",
            "contradiction": "The current evidence does not distinguish them.",
            "evidence": [],
            "hypotheses": [
                {
                    "hypothesis_key": "hypothesis_a",
                    "statement": "A bounded mechanism changes the observable.",
                    "mechanism": "The mechanism has one finite intervention.",
                    "scope": "Only the supplied system.",
                    "parameters": [],
                    "predictions": [
                        {
                            "prediction_key": "prediction_a",
                            "observable": "A bounded response",
                            "expected_outcome": "The response changes direction.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "falsifier_a",
                            "observable": "The same bounded response",
                            "rejection_condition": "No directional change occurs.",
                        }
                    ],
                    "competing_hypothesis_keys": [],
                    "evidence_keys": [],
                }
            ],
        }
    )
    review = _critic(
        disposition="ready_for_experiment",
        physical="pass",
        falsifiability="pass",
        discriminability="pass",
    )
    _critic_portfolio_context(
        review.model_dump(mode="json"),
        {"hypothesis_portfolio": portfolio},
        {"verdict": "pass"},
    )


def test_critic_progress_fingerprint_ignores_prose_but_not_open_dimensions() -> None:
    first = _critic_bytes(issue="First wording.")
    reworded = _critic_bytes(issue="Different wording of the same defect.")
    progressed = _critic_bytes(physical="pass", falsifiability="fail")
    assert critic_progress_fingerprint(first) == critic_progress_fingerprint(reworded)
    assert critic_progress_fingerprint(first) != critic_progress_fingerprint(progressed)


def test_experiment_review_reports_a_verdict_without_selecting_an_operation() -> None:
    from tests.operations.test_m2_curve_analysis_boundary import _plan

    payload = {
        "review_target": "experiment_portfolio",
        "verdict": "revise",
        "summary": "One bounded correction is required.",
    }
    _object_review_context(payload, {"experiment_plan": canonical_json(_plan())}, {"verdict": "revise"})
    catalog = _catalog()
    assert catalog.operation("science.experiment.revise.v1").spec.accepts_actions == ()
    assert next(
        item
        for item in catalog.operation("science.experiment.design.v1").spec.inputs
        if item.name == "critic_review"
    ).usage == "prior_signal"


def test_evidence_revision_requires_the_exact_review_lineage() -> None:
    operation = _catalog().operation("science.evidence.revise-from-critic.v1")
    source = _artifact(
        "paper",
        "opaque",
        kind="source_file",
        media_type="application/pdf",
    )
    source_table = _artifact(
        "paper_table",
        "opaque",
        kind="source_file",
        media_type="text/csv",
    )
    prior = _artifact(
        "intake",
        "scidiscovery.scientific-intake.v1",
        parents=(source.ref, source_table.ref),
    )
    audit = _artifact(
        "audit",
        "scidiscovery.evidence-audit.v1",
        parents=(prior.ref, source.ref, source_table.ref),
        verdict="pass",
    )
    foundation = _artifact(
        "foundation",
        "scidiscovery.scientific-foundation.v1",
        parents=(prior.ref, audit.ref),
    )
    portfolio = _artifact(
        "portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        parents=(foundation.ref,),
    )
    request = _artifact(
        "critic",
        "scidiscovery.critic-review.v2",
        parents=(portfolio.ref, foundation.ref),
        verdict="inconclusive",
    )
    audit = replace(audit, producer_inputs=(("scientific_intake", prior.ref),
        ("source_material", source.ref), ("source_material", source_table.ref)))
    inputs = {
        "user_context": (),
        "prior_draft": (prior,),
        "intake_audit": (audit,),
        "scientific_foundation": (foundation,),
        "hypothesis_portfolio": (portfolio,),
        "change_request": (request,),
        "source_material": (source, source_table),
        "source_manifest": (),
    }
    assert preflight_operation(
        operation,
        name="evidence_gap_revision",
        artifacts_by_port=inputs,
        instruction="Revise only the exact missing factual premise.",
    ).compiled is operation
    unrelated = _artifact(
        "unrelated_critic",
        "scidiscovery.critic-review.v2",
        verdict="inconclusive",
    )
    with pytest.raises(OperationInvocationError) as caught:
        preflight_operation(
            operation,
            name="unrelated_evidence_gap_revision",
            artifacts_by_port={**inputs, "change_request": (unrelated,)},
            instruction="Do not accept an unrelated review.",
        )
    assert caught.value.reason_code == "guard_rejected"

    alternate_audit = _artifact(
        "alternate_audit",
        "scidiscovery.evidence-audit.v1",
        parents=(prior.ref, source.ref, source_table.ref),
        verdict="pass",
    )
    alternate_audit = replace(alternate_audit, producer_inputs=audit.producer_inputs)
    with pytest.raises(OperationInvocationError) as caught:
        preflight_operation(
            operation,
            name="mismatched_intake_audit",
            artifacts_by_port={**inputs, "intake_audit": (alternate_audit,)},
            instruction="Do not detach the foundation from its exact intake audit.",
        )
    assert caught.value.reason_code == "guard_rejected"

    with pytest.raises(OperationInvocationError) as caught:
        preflight_operation(
            operation,
            name="omitted_evidence_source",
            artifacts_by_port={**inputs, "source_material": (source,)},
            instruction="Do not omit one frozen evidence source.",
        )
    assert caught.value.reason_code == "guard_rejected"

    replacement = _artifact(
        "replacement_paper",
        "opaque",
        kind="source_file",
        media_type="application/pdf",
    )
    with pytest.raises(OperationInvocationError) as caught:
        preflight_operation(
            operation,
            name="replaced_evidence_source",
            artifacts_by_port={
                **inputs,
                "source_material": (replacement, source_table),
            },
            instruction="Do not replace the frozen evidence source.",
        )
    assert caught.value.reason_code == "guard_rejected"

    with pytest.raises(OperationInvocationError) as caught:
        preflight_operation(
            operation,
            name="extended_evidence_source",
            artifacts_by_port={
                **inputs,
                "source_material": (source, source_table, replacement),
            },
            instruction="Do not add an undeclared source through bounded revision.",
        )
    assert caught.value.reason_code == "guard_rejected"


# The real Root preflight/invoke source-continuity path is covered in
# test_user_context_contract, with completed producers and an actual fixture approval.


def test_same_critic_problem_cannot_trigger_a_second_text_only_revision() -> None:
    catalog = _catalog()
    operation = catalog.operation("science.hypothesis.revise.v1")
    original = _artifact("portfolio_0", "scidiscovery.hypothesis-proposal.v2")
    first_review = _artifact("critic_0", "scidiscovery.critic-review.v2")
    first_revision = _artifact("portfolio_1", "scidiscovery.hypothesis-proposal.v2")
    repeated_review = _artifact("critic_1", "scidiscovery.critic-review.v2")
    first_status = SimpleNamespace(
        operation_id=operation.spec.operation_id,
        operation_digest="0" * 64,
        inputs=(
            SimpleNamespace(usage="revision_base", artifact_ref=original.ref),
            SimpleNamespace(usage="change_request", artifact_ref=first_review.ref),
        ),
    )
    statuses = {first_revision.ref: first_status}
    payloads = {
        first_review.ref: _critic_bytes(issue="First wording."),
        repeated_review.ref: _critic_bytes(issue="Reworded but unchanged."),
    }
    routes = object.__new__(RootOperationRoutes)
    routes._instance_id = lambda: "instance_no_progress"
    routes.runs = SimpleNamespace(
        completed_for_output=lambda ref: statuses.get(ref),
        revision_successor=lambda **values: None,
    )
    routes.artifacts = SimpleNamespace(read=lambda ref: payloads[ref])
    bound = SimpleNamespace(
        compiled=operation,
        inputs=(
            SimpleNamespace(
                port_name="prior_draft",
                usage="revision_base",
                artifact=first_revision,
            ),
            SimpleNamespace(
                port_name="change_request",
                usage="change_request",
                artifact=repeated_review,
            ),
        ),
    )
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_revision_policy(bound)
    assert caught.value.reason_code == "revision_no_progress"


def test_hypothesis_review_edge_has_a_hard_two_revision_limit() -> None:
    catalog = _catalog()
    operation = catalog.operation("science.hypothesis.revise.v1")
    original = _artifact("limit_portfolio_0", "scidiscovery.hypothesis-proposal.v2")
    review_0 = _artifact("limit_critic_0", "scidiscovery.critic-review.v2")
    revision_1 = _artifact("limit_portfolio_1", "scidiscovery.hypothesis-proposal.v2")
    review_1 = _artifact("limit_critic_1", "scidiscovery.critic-review.v2")
    revision_2 = _artifact("limit_portfolio_2", "scidiscovery.hypothesis-proposal.v2")
    review_2 = _artifact("limit_critic_2", "scidiscovery.critic-review.v2")
    statuses = {
        revision_2.ref: SimpleNamespace(
            operation_id=operation.spec.operation_id,
            operation_digest="0" * 64,
            inputs=(
                SimpleNamespace(usage="revision_base", artifact_ref=revision_1.ref),
                SimpleNamespace(usage="change_request", artifact_ref=review_1.ref),
            ),
        ),
        revision_1.ref: SimpleNamespace(
            operation_id=operation.spec.operation_id,
            operation_digest="0" * 64,
            inputs=(
                SimpleNamespace(usage="revision_base", artifact_ref=original.ref),
                SimpleNamespace(usage="change_request", artifact_ref=review_0.ref),
            ),
        ),
    }
    routes = object.__new__(RootOperationRoutes)
    routes._instance_id = lambda: "instance_revision_limit"
    routes.runs = SimpleNamespace(
        completed_for_output=lambda ref: statuses.get(ref),
        revision_successor=lambda **values: None,
    )
    routes.artifacts = SimpleNamespace(read=Mock())
    bound = SimpleNamespace(
        compiled=operation,
        inputs=(
            SimpleNamespace(
                port_name="prior_draft",
                usage="revision_base",
                artifact=revision_2,
            ),
            SimpleNamespace(
                port_name="change_request",
                usage="change_request",
                artifact=review_2,
            ),
        ),
    )
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_revision_policy(bound)
    assert caught.value.reason_code == "revision_limit_reached"
    routes.artifacts.read.assert_not_called()


def test_root_preflight_distinguishes_idempotency_from_a_sibling_revision(
    tmp_path,
) -> None:
    catalog = _catalog()
    operation = catalog.operation("science.hypothesis.revise.v1")
    project = tmp_path / "root_revision_project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "root_revision_state",
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="root_revision",
        title="Root revision",
        objective="Distinguish exact replay from a sibling revision.",
    )

    def register(name: str, schema: str, content: bytes):
        envelope = runtime.artifacts.register(
            content,
            ArtifactRegistration(
                kind="scientific_object",
                schema_id=schema,
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"root-revision:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=envelope.artifact_id,
        )
        return envelope

    register(
        "branch_portfolio",
        "scidiscovery.hypothesis-proposal.v2",
        _revision_portfolio_bytes(),
    )
    first_review = register(
        "first_critic",
        "scidiscovery.critic-review.v2",
        _critic_bytes(issue="First bounded correction."),
    )
    second_review = register(
        "second_critic",
        "scidiscovery.critic-review.v2",
        _critic_bytes(issue="A different bounded correction."),
    )
    register(
        "branch_foundation",
        "scidiscovery.scientific-foundation.v1",
        _revision_foundation_bytes(),
    )
    signals = {
        first_review.ref: SchedulerSignal(
            verdict="revise",
            summary="First correction.",
        ),
        second_review.ref: SchedulerSignal(
            verdict="revise",
            summary="Different correction.",
        ),
    }
    facade = RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )
    facade._scheduler_signal_for_output = lambda ref: signals.get(ref)
    facade._validate_producer_output_admission = lambda bound: None
    facade._validate_compiled_input_admission = lambda bound: None
    root = RootMCPRouter(facade)

    def request(review_name: str, *, on_conflict: str = "reject"):
        return {
            "name": "bounded_revision",
            "operation_id": operation.spec.operation_id,
            "inputs": [
                {"port": "prior_draft", "artifact_names": ["branch_portfolio"]},
                {"port": "change_request", "artifact_names": [review_name]},
                {
                    "port": "scientific_foundation",
                    "artifact_names": ["branch_foundation"],
                },
            ],
            "instruction": "Apply only the bound critic correction.",
            "on_conflict": on_conflict,
        }

    first = request("first_critic")
    assert root.call_tool("operation_invoke", first)["result"]["state"] == "queued"
    assert root.call_tool("operation_preflight", first)["admissible"] is True

    sibling = request("second_critic", on_conflict="create_revision")
    rejected = root.call_tool("operation_preflight", sibling)
    assert rejected["admissible"] is False
    assert rejected["reason_code"] == "revision_branch_forbidden"
    with pytest.raises(RootToolError, match="revision_branch_forbidden"):
        root.call_tool("operation_invoke", sibling)


def test_run_transaction_rejects_a_second_revision_successor(tmp_path) -> None:
    catalog = _catalog()
    operation = catalog.operation("science.hypothesis.revise.v1")
    project = tmp_path / "revision_project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "revision_state")
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="revision_successor",
        title="Revision successor",
        objective="Allow one successor for each bounded revision base.",
    )

    def register(name: str, content: bytes, schema: str):
        envelope = runtime.artifacts.register(
            content,
            ArtifactRegistration(
                kind="scientific_object",
                schema_id=schema,
                payload_schema_version=1,
                media_type="application/json",
                creator=runtime.actor,
            ),
            idempotency_key=f"revision-successor:{name}",
        )
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id,
            namespace="artifact",
            name=name,
            object_id=envelope.artifact_id,
        )
        return InvocationArtifact(
            artifact_name=name,
            ref=envelope.ref,
            schema_id=schema,
            media_type="application/json",
            size_bytes=len(content),
        )

    portfolio_bytes = _revision_portfolio_bytes()
    base = register(
        "base_portfolio",
        portfolio_bytes,
        "scidiscovery.hypothesis-proposal.v2",
    )
    request = register(
        "critic_request",
        _critic_bytes(),
        "scidiscovery.critic-review.v2",
    )
    foundation = register(
        "foundation",
        _revision_foundation_bytes(),
        "scidiscovery.scientific-foundation.v1",
    )
    bound = preflight_operation(
        operation,
        name="first_revision",
        artifacts_by_port={
            "current_progress": (), "experiment_results": (), "result_analysis": (),
            "user_context": (),
            "prior_draft": (base,),
            "change_request": (request,),
            "scientific_foundation": (foundation,),
        },
        instruction="Apply the bounded critic correction.",
        read_artifact=runtime.artifacts.read,
    )
    runtime.runs.schedule(
        bound,
        instance_id=instance.instance_id,
        output_binding_name="first_revision.output",
        output_logical_name="first_revision.output",
        output_revision=1,
        output_binding_fingerprint="1" * 64,
    )
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=operation.spec.operation_id,
        operation_digest=operation.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        canonical_json(
            {
                "schema_version": 1,
                "handoff": {
                    "verdict": "pass",
                    "summary": "The bounded correction preserves stable keys.",
                },
                "payload": {
                    **json.loads(portfolio_bytes),
                    "stage_objective": (
                        "Separate one bounded mechanism after review correction."
                    ),
                },
            }
        )
    )
    assert worker.call_tool("worker_submit_result", {})["state"] == "completed"

    with pytest.raises(RunSlotBusy, match="already has a successor"):
        runtime.runs.schedule(
            bound,
            instance_id=instance.instance_id,
            output_binding_name="second_revision.output",
            output_logical_name="second_revision.output",
            output_revision=1,
            output_binding_fingerprint="2" * 64,
        )

    retry_base = register(
        "retry_base_portfolio",
        portfolio_bytes,
        "scidiscovery.hypothesis-proposal.v2",
    )
    retry_bound = preflight_operation(
        operation,
        name="retry_revision",
        artifacts_by_port={
            "current_progress": (), "experiment_results": (), "result_analysis": (),
            "user_context": (),
            "prior_draft": (retry_base,),
            "change_request": (request,),
            "scientific_foundation": (foundation,),
        },
        instruction="Retry only after an explicit failed Run.",
        read_artifact=runtime.artifacts.read,
    )
    failed_run = runtime.runs.schedule(
        retry_bound,
        instance_id=instance.instance_id,
        output_binding_name="failed_revision.output",
        output_logical_name="failed_revision.output",
        output_revision=1,
        output_binding_fingerprint="3" * 64,
    )
    runtime.runs.record_failure(
        failed_run,
        reason="intentional test failure",
        expected_state="queued",
        expected_last_activity_at=None,
    )
    retry_run = runtime.runs.schedule(
        retry_bound,
        instance_id=instance.instance_id,
        output_binding_name="retry_revision.output",
        output_logical_name="retry_revision.output",
        output_revision=1,
        output_binding_fingerprint="4" * 64,
    )
    assert runtime.runs.status(retry_run).state == "queued"


def test_nonpassing_review_signal_can_justify_scheduler_selected_remediation() -> None:
    catalog = _catalog()
    operation = catalog.operation("science.evidence.revise-from-critic.v1")
    portfolio = _artifact("remediation_portfolio", "scidiscovery.hypothesis-proposal.v2")
    critic = _artifact(
        "remediation_critic",
        "scidiscovery.critic-review.v2",
        verdict="inconclusive",
    )
    routes = object.__new__(RootOperationRoutes)
    routes._operation_output_contract = Mock(
        side_effect=lambda artifact, **_kwargs: (
            (object(), ("science.hypothesis.criticize.v1", "hypothesis_portfolio", ("pass",)))
            if artifact.ref == portfolio.ref
            else None
        )
    )
    routes._is_exact_reviewer_output = Mock(return_value=True)
    bound = SimpleNamespace(
        compiled=operation,
        inputs=(
            SimpleNamespace(
                port_name="hypothesis_portfolio",
                usage="prior_signal",
                artifact=portfolio,
            ),
            SimpleNamespace(
                port_name="change_request",
                usage="review_signal",
                artifact=critic,
            ),
        ),
    )
    routes._validate_producer_output_admission(bound)
    assert routes._is_exact_reviewer_output.call_args.kwargs[
        "accepted_verdicts"
    ] == ("revise", "blocked", "inconclusive")
