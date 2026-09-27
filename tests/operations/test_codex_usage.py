import pytest

from scidiscovery.platforms.codex_usage import observe_usage, usage_summary


def event(thread="thread-1", *, input=100, cached=20, output=10):
    return {"threadId": thread, "turnId": "turn-1", "tokenUsage": {"total": {
        "inputTokens": input, "cachedInputTokens": cached, "outputTokens": output}}}


def test_cumulative_usage_deduplicates_snapshots_and_keeps_failed_cost():
    first = observe_usage(event(), role="root", owner="instance-1")
    duplicate = observe_usage(event(), previous=first, role="root", owner="instance-1")
    assert set(duplicate["delta_tokens"].values()) == {0}
    failed = observe_usage(event(input=140, cached=30, output=25), previous=duplicate,
                           role="root", owner="instance-1", outcome="failed",
                           elapsed_seconds=1.5, response_bytes=512)
    assert failed["delta_tokens"] == {"input_tokens": 40, "cached_input_tokens": 10, "output_tokens": 15}
    assert failed["counted_tokens"]["input_tokens"] == 140
    assert usage_summary([failed])["groups"]["root"]["failed_threads"] == 1
    assert failed["response_bytes"] == 512  # Never added to any token measurement.


def test_counter_regression_preserves_high_water_and_gap_after_recovery():
    first = observe_usage(event())
    lower = observe_usage(event(input=20, cached=5, output=2), previous=first)
    assert lower["coverage"] == "counter_regressed"
    assert set(lower["delta_tokens"].values()) == {None}
    recovered = observe_usage(event(input=120, cached=25, output=15), previous=lower)
    assert recovered["delta_tokens"]["input_tokens"] == 20
    assert usage_summary([recovered])["coverage"] == "partial"
    # A distinct actual platform thread starts a new cumulative series.
    new = observe_usage(event("thread-2", input=20))
    assert new["delta_tokens"]["input_tokens"] == 20
    with pytest.raises(ValueError, match="different platform threads"):
        observe_usage(event("thread-2"), previous=first)


def test_missing_metrics_and_known_roles_remain_explicit():
    rows = [observe_usage(event(role), role=role, owner="task-1")
            for role in ("root", "worker", "helper")]
    missing = observe_usage({"threadId": "unknown"}, outcome="failed")
    rows.append(missing)
    assert set(missing["delta_tokens"].values()) == {None}
    summary = usage_summary(rows)
    assert summary["coverage"] == "partial"
    assert set(summary["groups"]) == {"root", "worker", "helper", "unattributed"}
    assert summary["groups"]["unattributed"]["unmeasured_threads"] == 1
    assert summary["individual_request_usage"] == "unavailable"
    assert usage_summary([])["coverage"] == "missing"
    with pytest.raises(ValueError, match="one latest"):
        usage_summary([rows[0], rows[0]])


def test_resumed_thread_baseline_excludes_prior_usage_and_keeps_limitation():
    baseline = observe_usage(event(), baseline=True)
    assert set(baseline["counted_tokens"].values()) == {0}
    current = observe_usage(event(input=150), previous=baseline)
    assert current["counted_tokens"]["input_tokens"] == 50
    assert usage_summary([current])["coverage"] == "partial"
    with pytest.raises(ValueError, match="first observation"):
        observe_usage(event(), previous=current, baseline=True)


@pytest.mark.parametrize("invalid", [True, -1, "100", None])
def test_invalid_token_measurements_are_missing(invalid):
    result = observe_usage(event(input=invalid))
    assert result["delta_tokens"]["input_tokens"] is None
    assert result["missing_fields"] == ["input_tokens"]


def test_attribution_cannot_silently_move_between_owners():
    first = observe_usage(event(), role="worker", owner="task-1")
    with pytest.raises(ValueError, match="attribution changed"):
        observe_usage(event(), previous=first, role="helper", owner="task-2")
