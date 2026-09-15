from types import SimpleNamespace
import threading

from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore, TrajectoryObserver


def node(state="running", **extra):
    return {"key": "run:exact", "name": "exact", "kind": "run", "state": state,
            "created_at": "2020-01-01T00:00:00Z", **extra}


def test_observed_states_do_not_invent_source_time_or_duplicate_events(tmp_path):
    store = TrajectoryStore(tmp_path / "ui" / "workbench.sqlite3")
    initial = store.events("one")["cursor"]
    store.observe("one", [node()], observed_at="2026-09-14T00:00:00Z")
    store.observe("one", [node()], observed_at="2026-09-14T00:00:01Z")
    first = store.events("one", after=initial)
    assert len(first["events"]) == 1
    assert first["events"][0]["source_time"] is None
    assert first["events"][0]["observed_at"] == "2026-09-14T00:00:00Z"
    store.observe("one", [node("completed", source_time="2026-09-14T00:00:02Z")], observed_at="2026-09-14T00:00:05Z")
    changed = store.events("one", after=first["cursor"])
    assert changed["events"][0]["state"] == "completed"
    assert changed["events"][0]["source_time"] != changed["events"][0]["observed_at"]
    assert store.events("two")["events"] == []
    assert store.observations("one", limit=1)["next_before"] is not None
    assert store.unsettled("one") == []


def test_observation_cache_rebuild_invalidates_only_ui_cursor(tmp_path):
    store = TrajectoryStore(tmp_path / "ui" / "workbench.sqlite3")
    store.observe("one", [node()])
    old = store.events("one")["cursor"]
    store.path.unlink()
    rebuilt = store.events("one", after=old)
    assert rebuilt["reset_required"] is True and rebuilt["events"] == []
    assert rebuilt["cursor"] != old
    assert store.preferences("one") == {"show_artifacts": True}
    store.preferences("one", {"show_artifacts": False})
    assert store.preferences("two") == {"show_artifacts": True}


def test_observer_uses_one_thread_only_with_viewers_and_metadata_only(tmp_path):
    store = TrajectoryStore(tmp_path / "ui" / "workbench.sqlite3")
    seen = threading.Event()
    calls = []
    def nodes(instance, *, limit):
        calls.append((instance, limit, threading.get_ident()))
        seen.set()
        return {"items": [node()]}
    model = SimpleNamespace(nodes=nodes)
    observer = TrajectoryObserver(model, store, interval=10)
    assert observer._thread is None and calls == []
    with observer.subscribe("one"):
        with observer.subscribe("one"):
            assert seen.wait(2)
            thread = observer._thread
            assert observer._subscriptions == {"one": 2}
    observer.stop()
    assert not thread.is_alive()
    assert {call[0] for call in calls} == {"one"}
    assert all(call[1] == 100 for call in calls)
    assert len({call[2] for call in calls}) == 1


def test_cache_failure_never_becomes_scientific_failure(tmp_path):
    path = tmp_path / "ui"
    path.write_text("not a directory")
    model = SimpleNamespace(nodes=lambda *args, **kwargs: {"items": [node()]})
    observer = TrajectoryObserver(model, TrajectoryStore(path / "workbench.sqlite3"))
    assert observer.refresh("one") is False
    assert observer.errors["one"]["code"] == "trajectory_observation_unavailable"
