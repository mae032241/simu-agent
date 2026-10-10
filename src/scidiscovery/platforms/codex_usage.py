"""Codex cumulative usage reduction for a host's existing observation storage.

The host passes authenticated thread notifications and control-owned attribution.
This module neither reads conversations nor creates storage or model requests.
Persist returned records in the host's existing event/state transaction.
"""
from __future__ import annotations

import math

TOKEN_FIELDS = {"input_tokens": "inputTokens", "cached_input_tokens": "cachedInputTokens",
                "output_tokens": "outputTokens"}
ROLES = {"root", "worker", "helper", "unattributed"}


def observe_usage(params: dict, *, previous: dict | None = None,
                  role: str = "unattributed", owner: str | None = None,
                  outcome: str = "unknown", baseline: bool = False,
                  elapsed_seconds: float | None = None,
                  response_bytes: int | None = None) -> dict:
    """Reduce one ``thread/tokenUsage/updated`` notification, including failures.

    ``previous`` must be the last record for this exact platform thread. A lower
    counter is an unmeasured interval, never an inferred new request/session.
    Use baseline=True when first observing an already running/resumed thread.
    Time and byte observations describe this observation interval, not tokens.
    Attribution comes from the host's exact binding, never from Agent text.
    """
    thread = params.get("threadId")
    turn = params.get("turnId")
    if not isinstance(thread, str) or not thread or len(thread) > 256:
        raise ValueError("usage requires an exact platform thread identity")
    if turn is not None and (not isinstance(turn, str) or len(turn) > 256):
        raise ValueError("usage turn identity is invalid")
    if role not in ROLES or outcome not in {"unknown", "running", "completed", "failed", "cancelled"}:
        raise ValueError("usage attribution is invalid")
    if role != "unattributed" and (not isinstance(owner, str) or not owner or len(owner) > 256):
        raise ValueError("attributed usage requires a control-owned owner")
    if role == "unattributed":
        owner = None
    if previous is not None and (previous["thread_id"] != thread or previous["platform"] != "codex"):
        raise ValueError("usage snapshots belong to different platform threads")
    if previous is not None and (previous["role"], previous["owner"]) != (role, owner):
        raise ValueError("usage attribution changed; reconcile the original binding")
    if baseline and previous is not None:
        raise ValueError("baseline is only valid for the first observation")
    if elapsed_seconds is not None and (type(elapsed_seconds) not in (int, float)
            or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0):
        raise ValueError("elapsed time must be a finite nonnegative observation")
    if response_bytes is not None and (type(response_bytes) is not int or response_bytes < 0):
        raise ValueError("response bytes must be a nonnegative observation")
    usage = params.get("tokenUsage")
    raw = usage.get("total") if isinstance(usage, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    totals = {key: raw.get(wire) if type(raw.get(wire)) is int and raw[wire] >= 0 else None
              for key, wire in TOKEN_FIELDS.items()}
    high = dict(previous["high_water"]) if previous else {key: None for key in TOKEN_FIELDS}
    counted = dict(previous["counted_tokens"]) if previous else {key: 0 for key in TOKEN_FIELDS}
    delta, missing, regressed = {}, [], []
    for key, value in totals.items():
        if value is None:
            delta[key] = None
            missing.append(key)
        elif high[key] is not None and value < high[key]:
            delta[key] = None
            regressed.append(key)
        else:
            delta[key] = 0 if baseline else value - (high[key] or 0)
            high[key] = value
            counted[key] += delta[key]
    gaps = bool(missing or regressed or baseline or (previous and previous["has_gaps"]))
    return {"platform": "codex", "thread_id": thread, "turn_id": turn,
            "role": role, "owner": owner, "outcome": outcome,
            "cumulative_tokens": totals, "delta_tokens": delta,
            "high_water": high, "counted_tokens": counted,
            "coverage": "missing" if missing else "counter_regressed" if regressed else "observed",
            "missing_fields": missing, "regressed_fields": regressed,
            "has_gaps": gaps,
            "baseline": baseline,
            "elapsed_seconds": elapsed_seconds, "response_bytes": response_bytes,
            "limitations": ["Thread cumulative counters do not identify individual model requests.",
                            "Cached input is a subset of input; do not add it to input."]}


def usage_summary(records: list[dict]) -> dict:
    """Sum the latest reduced record per thread; reject duplicate thread rows.

    Unknown/missing measurements remain visible alongside known partial sums.
    This function makes no request-count or monetary-cost estimate.
    """
    if len({record["thread_id"] for record in records}) != len(records):
        raise ValueError("supply exactly one latest usage record per thread")
    groups = {}
    for record in records:
        group = groups.setdefault(record["role"], {"tokens": dict.fromkeys(TOKEN_FIELDS, 0),
            "failed_threads": 0, "unmeasured_threads": 0})
        for key in TOKEN_FIELDS:
            group["tokens"][key] += record["counted_tokens"][key]
        group["failed_threads"] += record["outcome"] == "failed"
        group["unmeasured_threads"] += bool(record["has_gaps"] or record.get("recovery_usage_unconfirmed"))
    return {"platform": "codex", "groups": groups,
            "coverage": "missing" if not records else "partial" if any(
                row["has_gaps"] or row.get("recovery_usage_unconfirmed") for row in records) else "observed",
            "individual_request_usage": "unavailable"}
