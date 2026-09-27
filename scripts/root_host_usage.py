"""Audit real host notifications using the installed A3 reducer and control bindings."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from scidiscovery.platforms.codex_usage import observe_usage, usage_summary


def audit(root, evidence):
    identity = json.loads((evidence / "thread.json").read_text())
    root_thread = identity["thread_id"]
    attribution = {root_thread: ("root", root_thread)}
    progress = json.loads((root / "progress.json").read_text())
    outcomes = {root_thread: "completed" if progress.get("state") == "root_returned_requires_sealed_audit"
                else "failed" if progress.get("state") == "failed" else "unknown"}
    with closing(sqlite3.connect((root / "state/database/runs.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        for run, thread, state in db.execute("SELECT c.run_id,c.thread_id,r.state FROM worker_connections c JOIN runs r ON r.run_id=c.run_id WHERE c.platform_session=?", (identity["session_id"],)):
            attribution[thread] = ("worker", run)
            outcomes[thread] = state if state in ("completed", "failed") else "running"
        for run, thread in db.execute("SELECT run_id,thread_id FROM worker_participants WHERE platform_session=? AND thread_id IS NOT NULL", (identity["session_id"],)):
            attribution.setdefault(thread, ("helper", run))
    baseline = {}
    source = evidence / "task-source.json"
    if source.exists():
        prior = Path(json.loads(source.read_text())["prior_evidence"]) / "usage.json"
        baseline = json.loads(prior.read_text())["threads"]
    rows, latest, events = {}, {}, 0
    for line in (evidence / "fixture-logs/events.log").open():
        event = json.loads(line)
        if event.get("method") != "thread/tokenUsage/updated":
            continue
        params = event["params"]
        thread = params["threadId"]
        role, owner = attribution.get(thread, ("unattributed", None))
        if thread not in rows and thread in baseline:
            rows[thread] = observe_usage({"threadId": thread, "tokenUsage": {"total": baseline[thread]}},
                                         role=role, owner=owner, baseline=True, outcome=outcomes.get(thread, "unknown"))
        rows[thread] = observe_usage(params, previous=rows.get(thread), role=role, owner=owner,
                                     outcome=outcomes.get(thread, "unknown"))
        latest[thread] = params
        events += 1
    if not rows:
        raise ValueError("no real usage notifications were captured")
    report = {"scope": "Installed reducer over this host interval; no product daemon ingestion claim",
              "baseline_evidence": json.loads(source.read_text()).get("prior_evidence") if source.exists() else None,
              "notification_count": events, "records": rows, "summary": usage_summary(list(rows.values()))}
    output = evidence / "usage-reduced.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output)
    # Load the persisted state as a restarted consumer and replay the exact last
    # notification. It must not count the same observed tokens a second time.
    restored = json.loads(output.read_text())["records"]
    for thread, previous in restored.items():
        replay = observe_usage(latest[thread], previous=previous,
                               role=previous["role"], owner=previous["owner"])
        assert replay["counted_tokens"] == previous["counted_tokens"]
        assert not any(value for value in replay["delta_tokens"].values() if value is not None)
    print(json.dumps({"scope": report["scope"], "summary": report["summary"],
                      "persisted_replay_deduplicated": True}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    audit(args.candidate.resolve(), args.evidence.resolve())
