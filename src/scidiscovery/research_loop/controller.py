"""Bounded local control over immutable scientific role handoffs."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import time
import uuid

from . import contracts, native


def prepare(root: Path, objective: Path, public_root: Path, launcher: list[str], *,
            max_tokens: int, max_seconds: float, max_steps: int,
            model: str, reasoning_effort: str, service_tier: str = "default",
            max_output_item_bytes: int = 32 * 1024 * 1024,
            max_output_total_bytes: int = 64 * 1024 * 1024,
            user_updates: list[Path] | None = None) -> dict:
    """Freeze an explicit goal and finite launch budgets in a fresh directory."""
    root, objective, public_root = map(Path, (root, objective, public_root))
    for name, value in (("max_tokens", max_tokens), ("max_steps", max_steps),
                        ("max_output_item_bytes", max_output_item_bytes),
                        ("max_output_total_bytes", max_output_total_bytes)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if (type(max_seconds) not in (int, float) or not 0 < max_seconds < float("inf")):
        raise ValueError("max_seconds must be positive and finite")
    if max_output_item_bytes > max_output_total_bytes:
        raise ValueError("Output item capacity exceeds total capacity")
    if not all(isinstance(value, str) and value.strip()
               for value in (model, reasoning_effort, service_tier)):
        raise ValueError("Explicit model, reasoning effort and service tier are required")
    if (not isinstance(launcher, list) or not launcher
            or not all(isinstance(item, str) and item.strip() for item in launcher)):
        raise ValueError("An explicit native launcher argument list is required")
    if root.exists() or root.is_symlink():
        raise ValueError("Preparation requires a fresh directory")
    if not objective.is_file() or not public_root.is_dir():
        raise ValueError("Explicit objective file and public directory are required")
    text = objective.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("The objective must contain original user text")
    updates = [contracts.regular(Path(path)).read_text(encoding='utf-8')
               for path in (user_updates or [])]
    if any(not update.strip() for update in updates):
        raise ValueError('Global user updates must contain original user text')
    settings = dict(goal_id="scid-hwa-" + uuid.uuid4().hex[:12], objective=text,
        public_root=str(public_root.resolve()), native_launcher_argv=list(launcher),
        max_tokens=max_tokens, max_seconds=max_seconds, max_steps=max_steps,
        model=model, reasoning_effort=reasoning_effort, service_tier=service_tier,
        max_output_item_bytes=max_output_item_bytes,
        max_output_total_bytes=max_output_total_bytes)
    root.mkdir(parents=True)
    globals_ = root / 'project/global'
    (globals_ / 'updates').mkdir(parents=True)
    sources = [(globals_ / 'objective.md', text), *[
        (globals_ / 'updates' / f'{index:03d}.md', update)
        for index, update in enumerate(updates, 1)]]
    settings['global_materials'] = []
    for source, contents in sources:
        source.write_text(contents, encoding='utf-8')
        source.chmod(0o400)
        settings['global_materials'].append(dict(source=source.relative_to(root).as_posix(),
            path='inputs/global/' + source.relative_to(globals_).as_posix(),
            sha256=contracts.digest(source)))
    contracts.write(root / "settings.json", settings)
    contracts.write(root / "settings-identity.json",
                    dict(sha256=contracts.digest(root / "settings.json")))
    return settings


@contextmanager
def _writer(root):
    descriptor = os.open(root / "host-run.lock",
        os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("This research loop already has a running controller") from error
        yield
    finally:
        os.close(descriptor)


def run(root: Path) -> dict:
    """Reconstruct routing from sealed nodes; never replay an uncertain launch."""
    root = Path(root).resolve()
    with _writer(root):
        return _run(root)


def _record(root, step):
    return root / "native-evidence" / f"{step:03d}"


def _parents(*steps):
    return list(dict.fromkeys(step for step in steps if step is not None))


def _launch_limit(root, settings, deadline):
    if time.time() >= deadline:
        return "wall_limit"
    observed = native.usage(root)
    if observed["unknown_steps"]:
        return "usage_unknown"
    if observed["observed_tokens"] >= settings["max_tokens"]:
        return "token_limit"
    return None


def _finish(root, settings, status, completed, last, *, reason=None, next_role=None):
    result = dict(status=status, goal_id=settings["goal_id"], completed_steps=completed,
        last_step=completed or None, usage=native.usage(root),
        goal_completion="not_asserted", unmet_goal=settings["objective"])
    if last is not None:
        result.update(role=last["role"], scientific_route=last.get("next_action", ""),
            route_reason=last.get("route_reason", ""), summary=last["summary"],
            limitations=last["limitations"],
            scientific_output_path=str(_record(root, completed) / 'science-output.json'))
    if reason is not None:
        result["reason"] = reason
    if next_role is not None:
        result["next_role"] = next_role
    return result


def _check_job(root, settings, step, role, parents, instruction, evidence_return):
    """A retained node must be the exact job selected by its sealed predecessor."""
    job = contracts.read(root / "jobs" / f"{step:03d}.json")
    expected_refs = [dict(path=f"inputs/parents/{parent:03d}/conclusion.json",
        sha256=contracts.digest(_record(root, parent) / "science-output.json"))
        for parent in parents]
    if (job.get("step") != step or job.get("role") != role
            or job.get("goal_text") != settings["objective"]
            or job.get("public_root") != settings["public_root"]
            or job.get("direct_refs") != expected_refs
            or job.get("instruction", "") != instruction
            or job.get("evidence_return") != evidence_return):
        raise ValueError("Retained job differs from the sealed scientific route")
    return job


def _route(root, step, role, result, job, current_h, current_w):
    instruction = result.get("route_reason", "")
    if role == "H":
        current_h = step
        action = result["next_action"]
        if action == "experiment":
            route = ("W", [step], instruction, None)
        elif action == "analyze":
            route = ("A", _parents(current_h, current_w), instruction, None)
        elif action == "extract":
            route = ("E", _parents(current_h, current_w), instruction,
                     dict(role="H", step=step))
        elif action == "wait":
            route = (None, [], "", None)
        else:
            raise ValueError("Invalid sealed H route")
    elif role == "W":
        current_w = step
        route = ("A", _parents(current_h, step), "", None)
    elif role == "A":
        action = result["next_action"]
        parents = _parents(current_h, current_w, step)
        if action == "continue_w":
            route = ("W", parents, instruction, None)
        elif action == "revise_h":
            route = ("H", parents, instruction, None)
        elif action == "extract":
            route = ("E", parents, instruction, dict(role="A", step=step))
        elif action in {"finish", "wait"}:
            route = (None, [], "", None)
        else:
            raise ValueError("Invalid sealed A route")
    elif role == "E":
        target = job["evidence_return"]
        if (not isinstance(target, dict) or target.get("role") not in {"H", "A"}
                or type(target.get("step")) is not int or not 0 < target["step"] < step):
            raise ValueError("Extraction has no exact scientific requester")
        requester = contracts.validate(contracts.workspace(root, target["step"]))
        if requester["role"] != target["role"] or requester["next_action"] != "extract":
            raise ValueError("Extraction requester identity differs")
        route = (target["role"], _parents(current_h, current_w, target["step"], step),
                 requester["route_reason"], None)
    else:
        raise ValueError("Unknown scientific role")
    return (*route, current_h, current_w)


def _terminal_success(record):
    try:
        outcome = contracts.read(record / 'native-outcome.json')
        raw = contracts.regular(record / 'science-output.json')
        return (type(outcome.get('returncode')) is int and outcome['returncode'] == 0
                and not outcome.get('stop_reason') and not outcome['usage']['unknown_steps']
                and outcome.get('raw_sha256') == contracts.digest(raw))
    except (KeyError, ValueError, OSError, TypeError):
        return False


def _seal_reason(error):
    return str(error) if isinstance(error, ValueError) else type(error).__name__


def _run(root):
    settings = contracts.settings(root)
    started_path = root / "host-started.json"
    if not started_path.exists():
        contracts.write(started_path, dict(at_unix=time.time()))
    deadline = contracts.read(started_path)["at_unix"] + settings["max_seconds"]
    role, parents, instruction, evidence_return = "H", [], "", None
    current_h = current_w = last = None
    completed = 0
    for step in range(1, settings["max_steps"] + 1):
        if (root / "pause.request").exists():
            return _finish(root, settings, "paused", completed, last,
                reason="User pause.request prevents further native launches", next_role=role)
        record = _record(root, step)
        work = contracts.workspace(root, step)
        identity = record / "result-identity.json"
        if not identity.exists():
            retained = any(path.exists() for path in (record / "native-intent.json",
                record / "native-outcome.json", record / "science-output.json", record / "result.json"))
            if retained:
                if not _terminal_success(record):
                    return _finish(root, settings, "native_outcome_unsealed", completed, last,
                        reason="Retain the original native work; its terminal scientific output is unverified",
                        next_role=role)
                try:
                    _check_job(root, settings, step, role, parents, instruction, evidence_return)
                    contracts.seal_result(root, step)
                except Exception as error:
                    return _finish(root, settings, "seal_pending", completed, last,
                        reason=f"Native science succeeded; host sealing requires repair: {_seal_reason(error)}",
                        next_role=role)
        if not identity.exists():
            limit = _launch_limit(root, settings, deadline)
            if limit:
                return _finish(root, settings, limit, completed, last, next_role=role)
            contracts.build_job(root, step, role, parents, instruction=instruction,
                                evidence_return=evidence_return)
            # Job creation is reversible; check again at the actual launch boundary.
            if (root / "pause.request").exists():
                return _finish(root, settings, "paused", completed, last, next_role=role)
            limit = _launch_limit(root, settings, deadline)
            if limit:
                return _finish(root, settings, limit, completed, last, next_role=role)
            try:
                native.execute_native(root, step)
            except Exception as error:
                if _terminal_success(record):
                    return _finish(root, settings, "seal_pending", completed, last,
                        reason=f"Native science succeeded; host sealing requires repair: {_seal_reason(error)}",
                        next_role=role)
                return _finish(root, settings, "native_stopped", completed, last,
                    reason=f"Native work did not seal ({type(error).__name__}); original intent is retained",
                    next_role=role)
            if not identity.exists():
                return _finish(root, settings, "native_outcome_unsealed", completed, last,
                    reason="Native work returned without a complete seal", next_role=role)
        try:
            outcome = contracts.read(record / "native-outcome.json")
            if (type(outcome.get("returncode")) is not int or outcome["returncode"] != 0 or outcome.get("stop_reason")
                    or outcome["usage"]["unknown_steps"]):
                raise ValueError("Native outcome is ineligible for sealed continuation")
            job = _check_job(root, settings, step, role, parents, instruction, evidence_return)
            result = contracts.validate(work)
            if result["role"] != role:
                raise ValueError("Sealed result role differs from its job")
            next_role, next_parents, next_instruction, next_return, current_h, current_w = _route(
                root, step, role, result, job, current_h, current_w)
        except (KeyError, ValueError, OSError, TypeError) as error:
            return _finish(root, settings, "sealed_node_invalid", completed, last,
                reason=f"Retained node is not eligible for routing ({type(error).__name__})", next_role=role)
        completed, last = step, result
        if next_role is None:
            return _finish(root, settings, result["next_action"], completed, last,
                reason="Scientific role suggestion; overall goal success is not asserted")
        role, parents, instruction, evidence_return = next_role, next_parents, next_instruction, next_return
    return _finish(root, settings, "bounded_steps_exhausted", completed, last, next_role=role)
