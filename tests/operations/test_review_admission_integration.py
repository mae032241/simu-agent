"""Root admission checks exact subjects of real completed reviewer Runs."""
from __future__ import annotations

import json

from tests.operations.test_l4_local_tcad import (
    _complete_plan_fixture,
    _plan_producer_plugin,
    _review_context_fixture,
    _system,
)


def test_shared_review_requires_every_exact_subject_across_producer_runs(tmp_path):
    plugin = _plan_producer_plugin()
    producer = next(op for op in plugin.operations if op.operation_id == "science.fixture.plan.v1")
    reviewer = next(op for op in plugin.operations if op.operation_id == "science.object.review.v1")
    plan_port = reviewer.inputs[0].model_copy(update={"max_items": 2})
    # This fixture isolates control-plane identity, without a single-plan domain checker.
    review_output = reviewer.outputs[0].model_copy(update={
        "context_validator": None, "context_rule_id": None, "context_sources": (),
    })
    reviewer = reviewer.model_copy(update={
        "operation_id": "science.fixture.collection-review.v1",
        "input_validation": None,
        "inputs": (plan_port, *reviewer.inputs[1:]), "outputs": (review_output,),
    })
    producer = producer.model_copy(update={
        "review": producer.review.model_copy(update={"reviewer_operation": reviewer.operation_id}),
    })
    from scidiscovery.operations.spec import InputPortSpec

    review_port = InputPortSpec(
        name="reviews", description="Exact independent witnesses for the bound plans.",
        schema_id=review_output.schema_id, media_types=review_output.media_types,
        codec=review_output.codec, schema_resource=review_output.schema_resource,
        min_items=0, max_items=2, usage="prior_signal",
    )
    consumer = reviewer.model_copy(update={
        "operation_id": "science.fixture.collection-consume.v1",
        "inputs": (*reviewer.inputs, review_port),
    })
    plugin = plugin.model_copy(update={"operations": (
        *(op for op in plugin.operations if op.operation_id != producer.operation_id),
        producer, reviewer, consumer,
    )})
    catalog, runtime, root, _ = _system(tmp_path, science_plugin=plugin)
    _, sources, _ = _review_context_fixture("case")
    plans = [
        _complete_plan_fixture(catalog, runtime, root, f"plan_{index}", producer.operation_id,
                               {**json.loads(sources["experiment_plan"]), "priority_rationale": f"Plan {index}."})
        for index in range(3)
    ]

    def review(name, subjects):
        return _complete_plan_fixture(
            catalog, runtime, root, name, reviewer.operation_id,
            {"review_target": "experiment_portfolio", "verdict": "pass", "summary": name},
            [{"port": "experiment_plan", "artifact_names": subjects}],
        )

    def preflight(subjects, reviews):
        return root.call_tool("operation_preflight", {
            "name": "consume", "operation_id": consumer.operation_id,
            "instruction": "Consume only exactly reviewed fixture plans.",
            "inputs": [
                {"port": "experiment_plan", "artifact_names": subjects},
                {"port": "reviews", "artifact_names": reviews},
            ],
        })

    shared = review("shared_review", plans[:2])
    shared_preflight = preflight(plans[:2], [shared])
    assert shared_preflight["admissible"] is True, shared_preflight
    partial = preflight([plans[0], plans[2]], [shared])
    assert partial["admissible"] is False
    assert partial["reason_code"] == "input_independent_review_missing"
    third = review("third_review", [plans[2]])
    assert preflight([plans[0], plans[2]], [shared, third])["admissible"] is True
    first = review("first_review", [plans[0]])
    second = review("second_review", [plans[1]])
    assert preflight(plans[:2], [first])["admissible"] is False
    assert preflight(plans[:2], [first, second])["admissible"] is True
