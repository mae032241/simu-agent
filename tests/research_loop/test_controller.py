"""Scientific routing and recovery controls, without native model execution."""
from __future__ import annotations

import hashlib
import importlib
import json
import multiprocessing
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def scene(tmp_path, monkeypatch):
    # Controller dependencies are owned separately; the fake implements their
    # transport contract and retains byte identities for recovery checks.
    for name in ("contracts", "native"):
        full = "scidiscovery.research_loop." + name
        if importlib.util.find_spec(full) is None:
            monkeypatch.setitem(sys.modules, full, ModuleType(full))
    controller = importlib.import_module("scidiscovery.research_loop.controller")

    def read(path):
        return json.loads(Path(path).read_text())

    def write(path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def workspace(root, step):
        return root / "project/.local/roles" / f"{step:03d}"

    def build_job(root, step, role, parents, instruction="", evidence_return=None):
        settings = read(root / "settings.json")
        work = workspace(root, step)
        work.mkdir(parents=True, exist_ok=True)
        refs = []
        for parent in parents:
            source = root / "native-evidence" / f"{parent:03d}" / "science-output.json"
            ref = dict(path=f"inputs/{parent:03d}.json", sha256=digest(source))
            destination = work / ref["path"]
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, destination)
            refs.append(ref)
        job = dict(step=step, role=role, goal_text=settings["objective"],
            public_root=settings["public_root"], direct_refs=refs,
            instruction=instruction, evidence_return=evidence_return)
        authority = root / "jobs" / f"{step:03d}.json"
        if authority.exists() and read(authority) != job:
            raise ValueError("Job changed")
        write(authority, job)
        return job

    root = tmp_path / "research"

    def validate(work):
        identity = read(root / "native-evidence" / work.name / "result-identity.json")
        if identity["sha256"] != digest(work / "result.json"):
            raise ValueError("Result changed")
        if identity["raw_sha256"] != digest(root / "native-evidence" / work.name / "science-output.json"):
            raise ValueError("Original science changed")
        job = read(root / "jobs" / (work.name + ".json"))
        if identity["job_sha256"] != digest(root / "jobs" / (work.name + ".json")):
            raise ValueError("Job changed")
        result = read(work / "result.json")
        assert result["role"] == job["role"]
        assert result["direct_refs"] == job["direct_refs"]
        for ref in job["direct_refs"]:
            if digest(work / ref["path"]) != ref["sha256"]:
                raise ValueError("Direct original changed")
        return result

    calls = []
    plan = []

    def usage(root):
        intents = sorted((root / "native-evidence").glob("*/native-intent.json"))
        unknown = [int(path.parent.name) for path in intents
                   if not (path.parent / "native-outcome.json").exists()]
        known = len(intents) - len(unknown)
        return dict(observed_tokens=known * 10, unknown_steps=unknown,
                    input_tokens=known * 7, cached_input_tokens=0, output_tokens=known * 3)

    def execute_native(root, step):
        calls.append(step)
        job_path = root / "jobs" / f"{step:03d}.json"
        job = read(job_path)
        role, action = plan[step - 1]
        assert role == job["role"]
        record = root / "native-evidence" / f"{step:03d}"
        write(record / "native-intent.json", dict(step=step, task_sha256=digest(job_path)))
        result = dict(role=role, next_action=action, route_reason="Evidence requests this route" if action else "",
            direct_refs=job["direct_refs"], summary=f"Contribution {step}",
            scientific_result="A bounded finding", limitations=["Goal is not fully tested"])
        payload = {key: value for key, value in result.items() if key not in {"role", "direct_refs"}}
        if role in {"W", "E"}:
            payload.pop("next_action")
            payload.pop("route_reason")
        write(record / "science-output.json", payload)
        work = workspace(root, step)
        write(work / "result.json", result)
        write(record / "native-outcome.json", dict(returncode=0, stop_reason=None,
            usage=dict(observed_tokens=10, unknown_steps=[])))
        write(record / "result-identity.json", dict(sha256=digest(work / "result.json"),
            job_sha256=digest(job_path), raw_sha256=digest(record / "science-output.json")))

    contracts = SimpleNamespace(read=read, write=write, digest=digest,
        workspace=workspace, build_job=build_job, validate=validate,
        settings=importlib.import_module('scidiscovery.research_loop.contracts').settings)
    native = SimpleNamespace(execute_native=execute_native, usage=usage)
    monkeypatch.setattr(controller, "contracts", contracts)
    monkeypatch.setattr(controller, "native", native)
    objective = tmp_path / "objective.txt"
    objective.write_text("Measure the unresolved mechanism")
    public = tmp_path / "public"
    public.mkdir()
    controller.prepare(root, objective, public, ["fake-launcher"], max_tokens=1000,
        max_seconds=60, max_steps=20, model="fake-model", reasoning_effort="high")

    def configure(**values):
        # Test setup only: establish a fresh frozen configuration before launch.
        settings = read(root / "settings.json")
        write(root / "settings.json", dict(settings, **values))
        write(root / "settings-identity.json", dict(sha256=digest(root / "settings.json")))

    return SimpleNamespace(controller=controller, root=root, plan=plan, calls=calls,
        read=read, write=write, workspace=workspace, native=native, configure=configure)


def job(scene, step):
    return scene.read(scene.root / "jobs" / f"{step:03d}.json")


def parents(scene, step):
    return [int(Path(ref["path"]).stem) for ref in job(scene, step)["direct_refs"]]


def test_h_to_a_and_first_experiment_from_a(scene):
    scene.plan[:] = [("H", "analyze"), ("A", "continue_w"), ("W", ""), ("A", "finish")]
    result = scene.controller.run(scene.root)
    assert scene.calls == [1, 2, 3, 4]
    assert parents(scene, 2) == [1]
    assert parents(scene, 3) == [1, 2]
    assert parents(scene, 4) == [1, 3]
    assert result["status"] == "finish"
    assert result["goal_completion"] == "not_asserted"
    assert result["unmet_goal"] == "Measure the unresolved mechanism"
    assert result["limitations"] == ["Goal is not fully tested"]


def test_extractions_return_to_requester_and_preserve_h_w(scene):
    scene.plan[:] = [("H", "experiment"), ("W", ""), ("A", "extract"), ("E", ""),
        ("A", "revise_h"), ("H", "extract"), ("E", ""), ("H", "analyze"), ("A", "finish")]
    assert scene.controller.run(scene.root)["status"] == "finish"
    assert job(scene, 4)["evidence_return"] == {"role": "A", "step": 3}
    assert parents(scene, 5) == [1, 2, 3, 4]
    assert parents(scene, 6) == [1, 2, 5]
    assert job(scene, 7)["evidence_return"] == {"role": "H", "step": 6}
    assert parents(scene, 8) == [6, 2, 7]
    assert parents(scene, 9) == [8, 2]
    assert len(parents(scene, 8)) == 3  # No recursive ancestry inventory.


def test_restart_reuses_only_complete_sealed_nodes(scene):
    scene.plan[:] = [("H", "experiment"), ("W", ""), ("A", "finish")]
    original = scene.native.execute_native

    def pause_after_h(root, step):
        original(root, step)
        if step == 1:
            (root / "pause.request").write_text("Pause before further work")

    scene.native.execute_native = pause_after_h
    assert scene.controller.run(scene.root)["status"] == "paused"
    start = scene.read(scene.root / "host-started.json")
    (scene.root / "pause.request").unlink()
    assert scene.controller.run(scene.root)["status"] == "finish"
    assert scene.calls == [1, 2, 3]
    assert scene.read(scene.root / "host-started.json") == start
    assert scene.controller.run(scene.root)["status"] == "finish"
    assert scene.calls == [1, 2, 3]


@pytest.mark.parametrize("known_outcome", [False, True])
def test_unsealed_original_is_never_replayed(scene, known_outcome):
    scene.plan[:] = [("H", "experiment")]
    record = scene.root / "native-evidence/001"
    scene.write(record / "native-intent.json", {"step": 1})
    if known_outcome:
        scene.write(record / "native-outcome.json", dict(returncode=0, stop_reason=None,
            usage=dict(unknown_steps=[])))
    assert scene.controller.run(scene.root)["status"] == "native_outcome_unsealed"
    assert scene.calls == []


def test_native_failure_stops_without_a_replacement(scene):
    def crash(root, step):
        scene.calls.append(step)
        scene.write(root / "native-evidence/001/native-intent.json", {"step": step})
        raise RuntimeError("Submission acceptance was lost")

    scene.native.execute_native = crash
    assert scene.controller.run(scene.root)["status"] == "native_stopped"
    assert scene.controller.run(scene.root)["status"] == "native_outcome_unsealed"
    assert scene.calls == [1]


def test_tampered_sealed_result_cannot_route(scene):
    scene.plan[:] = [("H", "wait")]
    assert scene.controller.run(scene.root)["status"] == "wait"
    output = scene.workspace(scene.root, 1) / "result.json"
    modified = scene.read(output)
    modified["next_action"] = "experiment"
    scene.write(output, modified)
    assert scene.controller.run(scene.root)["status"] == "sealed_node_invalid"
    assert scene.calls == [1]


def test_pause_before_launch_and_after_job_construction(scene):
    (scene.root / "pause.request").write_text("Pause")
    assert scene.controller.run(scene.root)["status"] == "paused"
    assert scene.calls == []
    (scene.root / "pause.request").unlink()
    build = scene.controller.contracts.build_job

    def pause_during_build(*args, **kwargs):
        job = build(*args, **kwargs)
        (scene.root / "pause.request").write_text("Pause")
        return job

    scene.controller.contracts.build_job = pause_during_build
    assert scene.controller.run(scene.root)["status"] == "paused"
    assert scene.calls == []


@pytest.mark.parametrize("limit,value,status", [
    ("max_tokens", 10, "token_limit"), ("max_steps", 1, "bounded_steps_exhausted")])
def test_explicit_budget_prevents_next_scientific_launch(scene, limit, value, status):
    scene.configure(**{limit: value})
    scene.plan[:] = [("H", "experiment")]
    result = scene.controller.run(scene.root)
    assert result["status"] == status
    assert result["next_role"] == "W"
    assert result["goal_completion"] == "not_asserted"
    assert scene.calls == [1]


def test_wall_budget_survives_restart(scene):
    scene.write(scene.root / "host-started.json", {"at_unix": 0})
    assert scene.controller.run(scene.root)["status"] == "wall_limit"
    assert scene.calls == []


def test_job_materialization_cannot_start_work_after_wall_limit(scene, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(scene.controller.time, "time", lambda: now[0])
    build = scene.controller.contracts.build_job

    def slow_build(*args, **kwargs):
        result = build(*args, **kwargs)
        now[0] += 61
        return result

    scene.controller.contracts.build_job = slow_build
    assert scene.controller.run(scene.root)["status"] == "wall_limit"
    assert scene.calls == []


def test_unknown_usage_blocks_new_launch(scene):
    scene.native.usage = lambda _: dict(observed_tokens=0, unknown_steps=[99])
    assert scene.controller.run(scene.root)["status"] == "usage_unknown"
    assert scene.calls == []


@pytest.mark.parametrize("changed", [dict(max_tokens=2000), dict(model="replacement-model")])
def test_changed_frozen_settings_cannot_launch(scene, changed):
    settings = scene.read(scene.root / "settings.json")
    scene.write(scene.root / "settings.json", dict(settings, **changed))
    with pytest.raises(ValueError, match="Frozen instance settings changed"):
        scene.controller.run(scene.root)
    assert scene.calls == []
    assert not (scene.root / "host-started.json").exists()


def _hold_writer(controller, root, ready, release):
    with controller._writer(root):
        ready.set()
        release.wait(10)


def test_concurrent_controller_is_rejected_by_process_lock(scene):
    context = multiprocessing.get_context("fork")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_writer,
        args=(scene.controller, scene.root, ready, release))
    process.start()
    try:
        assert ready.wait(5)
        with pytest.raises(RuntimeError, match="already has a running controller"):
            scene.controller.run(scene.root)
        assert scene.calls == []
    finally:
        release.set()
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0


@pytest.mark.parametrize("max_tokens,max_seconds,max_steps", [
    (0, 60, 1), (100, float("inf"), 1), (100, 60, True), (100, -1, 1)])
def test_prepare_requires_explicit_finite_budgets(scene, tmp_path, max_tokens, max_seconds, max_steps):
    with pytest.raises(ValueError):
        scene.controller.prepare(tmp_path / "invalid", tmp_path / "objective.txt", tmp_path / "public",
            ["fake-launcher"], max_tokens=max_tokens, max_seconds=max_seconds,
            max_steps=max_steps, model="fake-model", reasoning_effort="high")
    assert not (tmp_path / "invalid").exists()


def test_real_sealing_and_materials_compose_with_controller(tmp_path, monkeypatch):
    controller = importlib.import_module("scidiscovery.research_loop.controller")
    contracts = importlib.import_module("scidiscovery.research_loop.contracts")
    native = importlib.import_module("scidiscovery.research_loop.native")
    monkeypatch.setattr(controller, "contracts", contracts)
    root = tmp_path / "research"
    objective = tmp_path / "objective.txt"
    objective.write_text("Resolve an open scientific question")
    public = tmp_path / "public"
    public.mkdir()
    controller.prepare(root, objective, public, ["fake-launcher"], max_tokens=1000,
        max_seconds=60, max_steps=5, model="fake", reasoning_effort="high")
    plan = [("H", "experiment"), ("W", ""), ("A", "extract"), ("E", ""), ("A", "finish")]
    calls = []

    def execute(root, step):
        calls.append(step)
        role, action = plan[step - 1]
        work = contracts.workspace(root, step)
        job_path = root / "jobs" / f"{step:03d}.json"
        assert contracts.read(job_path)["role"] == role
        record = contracts.host_record(work)
        contracts.write(record / "native-intent.json", dict(task_sha256=contracts.digest(job_path)))
        payload = dict(summary=f"Original contribution {step}", scientific_result="Bounded evidence",
            limitations=["Unobserved goal conditions"])
        if role in {"H", "A"}:
            payload.update(next_action=action, route_reason="The direct evidence supports this route")
        artifacts = work / "artifacts"
        artifacts.mkdir()
        (artifacts / f"evidence-{step}.txt").write_text(f"Original {role} observation")
        contracts.write(record / "science-output.json", payload)
        contracts.write(record / "usage.json", dict(input_tokens=7, cached_input_tokens=2, output_tokens=3))
        contracts.write(record / "native-outcome.json", dict(returncode=0, stop_reason=None,
            usage=native.usage(root)))
        contracts.seal_result(root, step)

    monkeypatch.setattr(controller, "native", SimpleNamespace(execute_native=execute, usage=native.usage))
    result = controller.run(root)
    assert result["status"] == "finish"
    assert result["usage"]["observed_tokens"] == 50
    assert result["usage"]["cached_input_tokens"] == 10
    final_job = contracts.read(root / "jobs/005.json")
    assert [item["path"] for item in final_job["direct_refs"]] == [
        "inputs/001.json", "inputs/002.json", "inputs/003.json", "inputs/004.json"]
    assert len(final_job["direct_materials"]) == 4
    for item in final_job["direct_refs"]:
        payload = contracts.read(contracts.workspace(root, 5) / item["path"])
        assert "role" not in payload
        assert "direct_refs" not in payload
    assert controller.run(root)["status"] == "finish"
    assert calls == [1, 2, 3, 4, 5]
