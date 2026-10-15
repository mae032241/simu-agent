"""Bounded local control over immutable scientific role handoffs."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import uuid

from . import budget, contracts, history, native, runtime, search, correction, semantic, execution, continuation, guidance, checkpoint, role_share, shortlist, engineering
from .output_repair import OutputRepairRequired


def prepare(root: Path, objective: Path, public_root: Path, launcher: list[str], *,
            max_tokens: int, max_seconds: float, max_steps: int,
            model: str, reasoning_effort: str, service_tier: str = "default",
            max_output_item_bytes: int = 32 * 1024 * 1024,
            max_output_total_bytes: int = 64 * 1024 * 1024,
            user_updates: list[Path] | None = None,
            history_observer: dict | None = None,
            search_policy: dict | None = search.DEFAULT_POLICY,
            correction_policy: dict | None = None,
            node_budget_policy: dict | None = None,
            delivery_policy: dict | None = None,
            resume_policy: dict | None = None,
            lineage_projection_version: int | None = 1,
            role_guidance: dict | None = guidance.DEFAULT,
            selection_protocol: int | None = 1,
            node_budget_mode: str = 'soft', candidate_audit_policy: dict | None = None,
            handoff_authority_version: int | None = 1, decision_contract_version: int | None = None,
            portfolio_policy: dict | None = None, exploration_order_version: int | None = None,
            worker_fragment_policy: dict | None = None, role_budget_policy: dict | None = None,
            selection_policy: dict | None = None, role_profiles: dict | None = None) -> dict:
    """Freeze an explicit goal and finite launch budgets in a fresh directory."""
    portfolio_limits = search.portfolio_policy(portfolio_policy) if portfolio_policy is not None else None
    if exploration_order_version is not None:
        raise ValueError('Author priority-table strategy is retired; current science declares intent directly')
    if portfolio_limits is not None:
        if search_policy is None or lineage_projection_version != 1:
            raise ValueError('Portfolio review requires H commitment search and unified lineage projection')
        decision_contract_version = 1
    if decision_contract_version is not None and (type(decision_contract_version) is not int or decision_contract_version != 1):
        raise ValueError('Unsupported scientific decision contract')
    if handoff_authority_version is not None and (type(handoff_authority_version) is not int or handoff_authority_version != 1):
        raise ValueError('Unsupported scientific handoff authority version')
    if lineage_projection_version is not None and (type(lineage_projection_version) is not int or lineage_projection_version != 1):
        raise ValueError('Unsupported lineage projection version')
    if selection_protocol is not None and (type(selection_protocol) is not int or selection_protocol != 1):
        raise ValueError('Unsupported public selection protocol')
    if node_budget_mode not in ('soft', 'hard'):
        raise ValueError('Node budget mode must be soft or hard')
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
    from . import profiles
    frozen_profiles = profiles.normalize(role_profiles, dict(model=model, reasoning_effort=reasoning_effort,
        service_tier=service_tier)) if role_profiles is not None else None
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
    observer = history.observer_config(history_observer) if history_observer is not None else None
    literal_guidance = (guidance.OPPORTUNITY if portfolio_limits is not None and portfolio_limits.get('version', 1) == 2
                        and role_guidance is guidance.DEFAULT else role_guidance)
    advice = guidance.policy(literal_guidance) if literal_guidance is not None else None
    search_limits = search.policy(search_policy) if search_policy is not None else None
    correction_limits = correction.policy(correction_policy) if correction_policy is not None else None
    if correction_limits is not None and search_limits is None:
        raise ValueError('Correction requires the frozen search policy')
    node_limits = budget.node_policy(node_budget_policy) if node_budget_policy is not None else None
    resume_limits = continuation.policy(resume_policy, launcher) if resume_policy is not None else None
    fragment_limits = checkpoint.policy(worker_fragment_policy) if worker_fragment_policy is not None else None
    if fragment_limits is not None:
        if resume_limits is None or node_limits is None:
            raise ValueError('W fragments require frozen turn-scoped launcher and original node budgets')
        if 'stage_intent' not in contracts.result_schema('W', contracts.HANDOFF_PROTOCOL)['properties']:
            raise ValueError('W fragments require the complete stage-intent schema; protocol13 is not enabled')
    if resume_limits is not None and node_limits is None:
        raise ValueError('Continuation requires explicit original node budgets')
    share_limits = role_share.policy(role_budget_policy) if role_budget_policy is not None else None
    if share_limits is not None and node_limits is None:
        raise ValueError('Role budget shares require explicit original node budgets')
    delivery_limits = None
    if delivery_policy is not None:
        from . import delivery
        delivery_limits = delivery.policy(delivery_policy)
        if node_limits is None:
            raise ValueError('Delivery requires explicitly frozen all-role node budgets')
    if candidate_audit_policy is not None:
        if candidate_audit_policy != {'version': 1} or type(candidate_audit_policy.get('version')) is not int:
            raise ValueError('Unsupported candidate audit policy')
        if delivery_limits is None or delivery_limits['adapter'] is None:
            raise ValueError('Candidate audit requires an explicit isolated delivery adapter')
    production = delivery_limits is not None and delivery_limits['adapter'] is not None and observer is not None
    selection_limits = shortlist.policy(selection_policy) if selection_policy is not None else None
    if selection_limits is not None and not production:
        raise ValueError('Control selection requires a public metric observer and an isolated delivery adapter')
    settings = dict(goal_id="scid-hwa-" + uuid.uuid4().hex[:12], objective=text,
        public_root=str(public_root.resolve()), native_launcher_argv=list(launcher),
        max_tokens=max_tokens, max_seconds=max_seconds, max_steps=max_steps, time_budget_basis="active",
        model=model, reasoning_effort=reasoning_effort, service_tier=service_tier,
        max_output_item_bytes=max_output_item_bytes,
        max_output_total_bytes=max_output_total_bytes)
    from .protocol import CURRENT
    if frozen_profiles is not None:
        settings['role_profiles'] = frozen_profiles
    settings['handoff_protocol']=CURRENT
    settings['handoff_authority_version']=settings['lineage_projection_version']=settings['selection_protocol']=1
    settings['node_budget_mode'] = node_budget_mode
    settings['live_feedback_version'] = 1
    settings['experiment_interface_version'] = 1
    settings['managed_admission_version'] = 1
    if handoff_authority_version is not None:
        settings['handoff_authority_version'] = handoff_authority_version
    if decision_contract_version is not None:
        settings['decision_contract_version'] = decision_contract_version
    if portfolio_limits is not None:
        settings['portfolio_policy'] = portfolio_limits
    if fragment_limits is not None:
        settings['worker_fragment_policy'] = fragment_limits
    if candidate_audit_policy is not None:
        settings['candidate_audit_policy'] = dict(candidate_audit_policy)
    if selection_protocol is not None and lineage_projection_version == 1:
        settings['selection_protocol'] = selection_protocol
    if advice is not None:
        settings['role_guidance'] = advice
    if lineage_projection_version is not None:
        settings['lineage_projection_version'] = lineage_projection_version
    if delivery_limits is not None:
        settings['delivery_policy'] = delivery_limits
        reserve = budget.delivery_reserve(settings)
        if reserve['tokens'] > max_tokens or reserve['seconds'] > max_seconds or reserve['steps'] > max_steps:
            raise ValueError('Delivery reservation exceeds original total authorization')
    if resume_limits is not None:
        settings['resume_policy'] = resume_limits
    if node_limits is not None:
        settings['node_budget_policy'] = node_limits
    if share_limits is not None:
        settings['role_budget_policy'] = share_limits
    if selection_limits is not None:
        settings['selection_policy'] = selection_limits
    if observer is not None:
        settings['history_observer'] = observer
    if search_limits is not None:
        settings['search_policy'] = search_limits
    if correction_limits is not None:
        settings['correction_policy'] = correction_limits
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
    from .protocol import require_current
    require_current(root)
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
    from .protocol import require_current
    require_current(root)
    root = Path(root).resolve()
    with _writer(root):
        return _run(root)


def _record(root, step):
    return root / "native-evidence" / f"{step:03d}"


def _parents(*steps):
    return list(dict.fromkeys(step for step in steps if step is not None))


def _launch_limit(root, settings):
    limits = budget.snapshot(root, settings)
    if limits['seconds_remaining'] <= 0:
        return "wall_limit"
    observed = native.usage(root)
    if observed["unknown_steps"]:
        return "usage_unknown"
    if observed["observed_tokens"] >= limits["max_tokens"]:
        return "token_limit"
    return None


def _finish(root, settings, status, completed, last, *, reason=None, next_role=None, correction_trigger=None):
    budget.inactive(root, status)
    result = dict(status=status, goal_id=settings["goal_id"], completed_steps=completed,
        last_step=completed or None, usage=native.usage(root),
        goal_completion="not_asserted", unmet_goal=settings["objective"])
    if last is not None:
        result.update(role=last["role"], scientific_route=last.get("next_action", ""),
            route_reason=last.get("route_reason", ""), summary=last["summary"],
            limitations=last["limitations"],
            scientific_output_path=str(execution.raw(root, completed)))
        control = contracts.read(_record(root, completed) / 'result-identity.json').get('control_outcome')
        if control is not None:
            result['control_outcome'] = control
    if reason is not None:
        result["reason"] = reason
    if next_role is not None:
        result["next_role"] = next_role
    if correction_trigger is not None:
        result['correction_trigger'] = correction_trigger
    return result


def _check_job(root, settings, step, role, parents, instruction, evidence_return, correction_request=None, author_correction=None, role_budget=None):
    """A retained node must be the exact job selected by its sealed predecessor."""
    job = contracts.read(root / "jobs" / f"{step:03d}.json")
    expected_refs = [dict(path=f"inputs/parents/{parent:03d}/conclusion.json",
        sha256=contracts.digest(execution.raw(root, parent)))
        for parent in parents]
    if (job.get("step") != step or job.get("role") != role
            or job.get("goal_text") != settings["objective"]
            or job.get("public_root") != settings["public_root"]
            or job.get("direct_refs") != expected_refs
            or job.get("instruction", "") != instruction
            or job.get("evidence_return") != evidence_return
            or job.get('correction_request') != correction_request
            or job.get('author_correction') != author_correction
            or job.get('role_budget') != role_budget):
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
        record = execution.record(root, step)
        ended = checkpoint.stage_end(root, job, record) if (record / 'stage-end.json').exists() else None
        question = 'Review the scientific contribution and original goal limits; control ended this stage for ' + ended['reason'] + '.' if ended else ''
        outcome = contracts.read(_record(root,step)/'result-identity.json')['control_outcome']
        delivery = outcome.get('worker_delivery') or {}
        if delivery.get('status') == 'partial':
            question = 'Review the retained partial scientific contribution and original goal limits; assigned work remains incomplete for ' + delivery['reason'] + '.'
        elif not ended and outcome.get('stage_end_reason')=='continuation_unavailable':
            question='Frozen context continuation was unavailable; judge the original retained contribution and its limitations.'
        route = ("A", _parents(current_h, step), question, None)
    elif role == "A":
        action = result["next_action"]
        parents = _parents(current_h, current_w, step)
        if action == "continue_w":
            route = ("W", parents, instruction, None)
        elif action == "revise_h":
            route = ("H", parents, instruction, None)
        elif action == "audit":
            from . import engineering
            repair=engineering.request(root,step)
            if repair is not None:
                engineering.admit(root,repair,step+1)
                route=('W',sorted(set([*parents,repair['source']['step']])),engineering.public(repair)['scope'],None)
            else:
                route = ("A", parents, instruction, None)
        elif action == "extract":
            route = ("E", parents, instruction, dict(role="A", step=step))
        elif action in {"finish", "deliver", "wait"}:
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
    """Known terminal turn, including diagnosed missing output, never unknown work."""
    try:
        outcome = contracts.read(record / 'native-outcome.json')
        if (type(outcome.get('returncode')) is not int or outcome['returncode'] != 0
                or outcome.get('stop_reason') or outcome['usage']['unknown_steps']):
            return False
        raw, pending = record / 'science-output.json', record / 'result.pending.json'
        if outcome.get('output_status') == 'missing':
            return (outcome.get('raw_sha256') is None and outcome.get('cleanup') == 'observed_group_cleaned'
                    and not raw.exists() and not raw.is_symlink() and not pending.exists() and not pending.is_symlink())
        return outcome.get('raw_sha256') == contracts.digest(contracts.regular(raw))
    except (KeyError, ValueError, OSError, TypeError):
        return False


def _seal_reason(error):
    return str(error) if isinstance(error, ValueError) else type(error).__name__


def _run(root):
    from .protocol import require_current
    require_current(root)
    settings = contracts.settings(root)
    if budget.closeout_state(root)['begin'] is not None:
        return _run_closeout(root)
    started_path = root / "host-started.json"
    if not started_path.exists():
        contracts.write(started_path, budget.clock_stamp())
    role, parents, instruction, evidence_return, correction_request = "H", [], "", None, None
    author_correction = role_budget = None
    current_h = current_w = last = None
    completed = 0
    for step in range(1, settings["max_steps"] + 1):
        record = _record(root, step)
        work = contracts.workspace(root, step)
        identity = record / "result-identity.json"
        if not identity.exists():
            retained = any(path.exists() for path in (record / "native-intent.json",
                record / "native-outcome.json", record / "science-output.json", record / "result.json"))
            if retained:
                budget.transition(root, 'advance', 'recover_original')
                job_path = root / 'jobs' / f'{step:03d}.json'
                if not job_path.exists():
                    return _finish(root, settings, "native_outcome_unsealed", completed, last,
                        reason="The original scientific job is missing; retained work is preserved without replay", next_role=role)
                retained_job = contracts.read(job_path)
                if runtime.node_state(root, step) == "running" or checkpoint.enabled(root, retained_job):
                    try:
                        native.wait_native(root, step)
                    except continuation.ResumeUnavailable as error:
                        return _finish(root, settings, 'output_repair_unavailable', completed, last, reason=str(error), next_role=role)
                    except OutputRepairRequired as error:
                        return _finish(root, settings, 'output_repair_required', completed, last, reason=error.code, next_role=role)
                    except Exception:
                        if not _terminal_success(execution.record(root, step)):
                            return _finish(root, settings, "native_outcome_unsealed", completed, last,
                                reason="Original execution lost its verified completion; preserved without replay",
                                next_role=role)
                if not _terminal_success(execution.record(root, step)):
                    return _finish(root, settings, "native_outcome_unsealed", completed, last,
                        reason="Retain the original native work; its terminal scientific output is unverified",
                        next_role=role)
                try:
                    _check_job(root, settings, step, role, parents, instruction, evidence_return, correction_request, author_correction, role_budget)
                    continuation.seal_or_repair(root, step)
                except continuation.ResumeUnavailable as error:
                    return _finish(root, settings, 'output_repair_unavailable', completed, last, reason=str(error), next_role=role)
                except OutputRepairRequired as error:
                    return _finish(root, settings, 'output_repair_required', completed, last, reason=error.code, next_role=role)
                except budget.NodeBudgetUnavailable as error:
                    return _finish(root, settings, error.reason, completed, last, next_role=role)
                except Exception as error:
                    return _finish(root, settings, "seal_pending", completed, last,
                        reason=f"Native turn completed; host sealing requires repair: {_seal_reason(error)}",
                        next_role=role)
        if not identity.exists():
            stopped = correction.gate(root, completed)
            if stopped is not None:
                return _finish(root, settings, 'correction_paused', completed, last,
                    reason=stopped['reason'], next_role=role, correction_trigger=stopped)
            if (root / "pause.request").exists():
                return _finish(root, settings, "paused", completed, last,
                    reason="User pause.request prevents further native launches", next_role=role)
            if author_correction is not None and role in {'H', 'A'} and semantic.accepted(root, author_correction, step) >= semantic.MAX_AUTHOR_CORRECTIONS:
                return _finish(root, settings, 'semantic_correction_required', completed, last,
                    reason='semantic_correction_limit', next_role=role)
            if role=='W' and parents:
                from . import engineering
                pending_repair=engineering.request(root,max(parents))
                if pending_repair is not None and not _repair_funds(root):
                    return _finish(root,settings,'engineering_repair_budget_unavailable',completed,last,next_role='W')
            reserve_stop = budget.exploration_admission(root, dict(step=step, role=role))
            if reserve_stop and settings.get('delivery_policy') is not None:
                return _start_closeout(root, completed, step, reserve_stop)
            budget.transition(root, 'advance', 'controller_launch_boundary')
            limit = _launch_limit(root, settings)
            if limit:
                return _finish(root, settings, limit, completed, last, next_role=role)
            node_limit = budget.node_admission(root, dict(step=step, role=role))
            if node_limit:
                return _finish(root, settings, node_limit, completed, last, next_role=role)
            if (root / 'jobs' / f'{step:03d}.json').exists():
                try:
                    _check_job(root, settings, step, role, parents, instruction, evidence_return,
                               correction_request, author_correction, role_budget)
                except ValueError:
                    return _finish(root, settings, 'retained_job_conflict', completed, last,
                        reason='A prepared task differs from the exact retained scientific route', next_role=role)
            try:
                job = contracts.build_job(root, step, role, parents, instruction=instruction,
                    evidence_return=evidence_return, correction_request=correction_request,
                    **(dict(author_correction=author_correction) if author_correction is not None else {}),
                    **(dict(role_budget=role_budget) if role_budget is not None else {}))
            except engineering.RepairUnavailable as error:
                return _finish(root,settings,str(error),completed,last,next_role=role)
            search_limit = search.launch_reason(root, job)
            if search_limit:
                return _finish(root, settings, 'search_pending', completed, last,
                    reason=search_limit, next_role=role)
            # Job creation is reversible; check again at the actual launch boundary.
            if (root / "pause.request").exists():
                return _finish(root, settings, "paused", completed, last, next_role=role)
            limit = _launch_limit(root, settings)
            if limit:
                return _finish(root, settings, limit, completed, last, next_role=role)
            try:
                native.execute_native(root, step)
            except budget.NodeBudgetUnavailable as error:
                return _finish(root, settings, error.reason, completed, last, next_role=role)
            except continuation.ResumeUnavailable as error:
                return _finish(root, settings, 'output_repair_unavailable', completed, last, reason=str(error), next_role=role)
            except OutputRepairRequired as error:
                return _finish(root, settings, 'output_repair_required', completed, last, reason=error.code, next_role=role)
            except Exception as error:
                if _terminal_success(execution.record(root, step)):
                    return _finish(root, settings, "seal_pending", completed, last,
                        reason=f"Native turn completed; host sealing requires repair: {_seal_reason(error)}",
                        next_role=role)
                if settings.get('delivery_policy') is not None and (record / 'native-outcome.json').exists():
                    stopped = contracts.read(record / 'native-outcome.json')
                    if str(stopped.get('stop_reason', '')).startswith('closeout_protected_'):
                        return _start_closeout(root, completed, step + 1, stopped['stop_reason'])
                return _finish(root, settings, "native_stopped", completed, last,
                    reason=f"Native work did not seal ({type(error).__name__}); original intent is retained",
                    next_role=role)
            if not identity.exists():
                return _finish(root, settings, "native_outcome_unsealed", completed, last,
                    reason="Native work returned without a complete seal", next_role=role)
        try:
            outcome = contracts.read(execution.record(root, step) / "native-outcome.json")
            if (type(outcome.get("returncode")) is not int or outcome["returncode"] != 0 or outcome.get("stop_reason")
                    or outcome["usage"]["unknown_steps"]):
                raise ValueError("Native outcome is ineligible for sealed continuation")
            job = _check_job(root, settings, step, role, parents, instruction, evidence_return, correction_request, author_correction, role_budget)
            result = contracts.validate(work)
            if result["role"] != role:
                raise ValueError("Sealed result role differs from its job")
            if role == 'A' and result.get('next_action') == 'audit':
                from . import candidate_audit
                audit_status = candidate_audit.execute(root, job, result)
                if audit_status is not None:
                    return _finish(root, settings, audit_status, step, result, next_role='A')
                receipt=candidate_audit._outcome(root,step)['result']
                from . import engineering
                repair=engineering.request(root,step)
                if repair is not None or receipt['status'] in {'engineering_error','unclassified'}:
                    if repair is None:
                        return _finish(root,settings,'candidate_audit_'+receipt['status'],step,result,reason=receipt['note'])
                    try:engineering.admit(root,repair,step+1)
                    except engineering.RepairUnavailable as error:
                        return _finish(root,settings,str(error),step,result)
            correction.publish(root, step)
            next_role, next_parents, next_instruction, next_return, current_h, current_w, next_correction = correction.effective_route(
                root, step, result, job, _route(root, step, role, result, job, current_h, current_w))
            next_role, next_parents, next_instruction, next_return, current_h, current_w, next_correction, next_author = semantic.effective_route(
                root, step, result, job, (next_role, next_parents, next_instruction, next_return, current_h, current_w, next_correction))
            (next_role, next_parents, next_instruction, next_return, current_h, current_w, next_correction, next_author,
             next_budget, share_stop) = role_share.effective_route(root, step, result, job,
                (next_role, next_parents, next_instruction, next_return, current_h, current_w, next_correction, next_author))
        except (KeyError, ValueError, OSError, TypeError) as error:
            return _finish(root, settings, "sealed_node_invalid", completed, last,
                reason=f"Retained node is not eligible for routing ({type(error).__name__})", next_role=role)
        completed, last = step, result
        if share_stop is not None:
            if settings.get('delivery_policy') is not None:
                return _start_closeout(root, completed, step + 1, share_stop)
            return _finish(root, settings, 'role_budget_stop', completed, last, reason=share_stop)
        if next_role is None:
            if settings.get('delivery_policy') is not None and result.get('next_action') in {'finish', 'deliver'}:
                return _start_closeout(root, completed, step + 1, 'scientific_finish',
                    authorization_step=step if result['next_action'] == 'deliver' else None)
            if result.get('next_action') == 'deliver':
                return _finish(root, settings, 'delivery_unavailable', completed, last, reason='No frozen delivery policy')
            return _finish(root, settings, result["next_action"], completed, last,
                reason="Scientific role suggestion; overall goal success is not asserted")
        role, parents, instruction, evidence_return, correction_request = next_role, next_parents, next_instruction, next_return, next_correction
        author_correction, role_budget = next_author, next_budget
    return _finish(root, settings, "bounded_steps_exhausted", completed, last, next_role=role)


def _closeout_result(root, status, *, reason=None, step=None, read_only=False):
    state = budget.closeout_state(root)
    begin = state['begin']
    closed = []
    if begin is not None:
        for path in sorted((root / 'jobs').glob('*.json')):
            job = contracts.read(path)
            if job.get('purpose') == 'closeout' and (_record(root, job['step']) / 'result-identity.json').exists():
                contracts.validate(contracts.workspace(root, job['step']))
                closed.append(job['step'])
    cutoff = begin['source_cutoff'] if begin else 0
    previous = history.candidate_overview(history.rebuild(root, cutoff + 1, write_cache=False))
    latest = history.candidate_overview(history.rebuild(root, max(closed, default=cutoff) + 1,
        source_cutoff=cutoff, extra_steps=closed, write_cache=False))
    screened = shortlist.summary(root) if contracts.settings(root).get('selection_policy') else None
    last = max(closed, default=cutoff) or None
    confirmed = [row['outcome']['result'] for row in state['actions'] if row['outcome'] is not None
                 and row['intent']['action_kind'] == 'confirm' and row['outcome']['result']['status'] == 'confirmed']
    last_action=state['actions'][-1] if state['actions'] else None
    last_outcome=last_action['outcome']['result'] if last_action and last_action['outcome'] is not None else None
    pending_confirmation=bool(last_action and (last_outcome is None or last_outcome['status']=='unknown'
        or last_action['intent']['action_kind']=='submit' and last_outcome['status']=='confirmed'))
    if not read_only:
        budget.inactive(root, status)
    last_science = contracts.validate(contracts.workspace(root, last)) if last is not None else None
    if status == 'closeout_status':
        from . import candidate_audit, delivery
        pending = [contracts.read(path)['step'] for path in sorted((root / 'jobs').glob('*.json'))
            if contracts.read(path).get('purpose') == 'closeout' and contracts.read(path)['step'] not in closed]
        if begin['mode'] == 'export_only':
            status = 'exported_unsubmitted'
        elif state['unresolved_operations']:
            status = 'delivery_unknown'
        elif candidate_audit.blocked(root):
            status = 'candidate_audit_unknown'
        elif pending:
            step = pending[-1]
            status = ('closeout_running' if runtime.node_state(root, step) == 'running' else
                'closeout_native_unsealed' if (_record(root, step) / 'native-intent.json').exists() else 'closeout_pending')
        elif state['actions'] and state['actions'][-1]['intent']['decision']['step'] == last:
            row = state['actions'][-1]
            outcome = row['outcome']['result'] if row['outcome'] else None
            status = ('delivery_unknown' if outcome is None else
                'delivery_reselect' if outcome['status'] == 'rejected' and outcome.get('failure_phase') == 'audit' else
                'delivery_confirmation_pending' if outcome['status'] == 'confirmed' and row['intent']['action_kind'] == 'submit' else
                'delivery_' + outcome['status'])
        elif last in closed and last_science['role']=='W':
            status='engineering_repair_review_pending'
        elif last in closed or last == begin.get('authorization_step'):
            status = {'wait':'closeout_waiting', 'finish':'exported_unsubmitted', 'audit':'candidate_audit_pending',
                'deliver':'closeout_preparation_pending'}.get(last_science['next_action'], 'closeout_correction_pending')
            if last == begin.get('authorization_step') and contracts.settings(root).get('selection_policy') is not None:
                status = 'selection_comparison_pending'
        else:
            status = 'closeout_pending'
        if last_science is not None and last_science['role']=='A' and not pending and not state['unresolved_operations'] and not candidate_audit.blocked(root):
            from . import engineering
            repair=engineering.request(root,last)
            if repair is not None:
                try:
                    engineering.admit(root,repair,last+1)
                    status='engineering_repair_pending' if _repair_funds(root) else 'engineering_repair_budget_unavailable'
                except engineering.RepairUnavailable as error:status=str(error)
            elif engineering.screen_failure(root,last) is not None:
                failure=engineering.screen_failure(root,last)[0]
                status,reason='closeout_preparation_unavailable',failure['note']
            elif last_science.get('next_action')=='audit':
                receipt=candidate_audit._outcome(root,last)
                if receipt is not None:
                    kind=receipt['result']['status']
                    status='candidate_audit_'+kind if kind in {'engineering_error','unclassified'} else 'candidate_audit_review_pending'
        screening=shortlist.pending_status(root) if contracts.settings(root).get('selection_policy') is not None else None
        if screening is not None and not pending and not state['unresolved_operations'] and not candidate_audit.blocked(root):
            status=screening
        if status in {'closeout_correction_pending', 'closeout_preparation_pending'}:
            errors = semantic.closeout_errors(root, (last or 0) + 1)
            if errors > semantic.MAX_AUTHOR_CORRECTIONS:
                status, reason = 'closeout_unresolved', 'semantic_correction_limit'
            elif status == 'closeout_preparation_pending':
                preparation = delivery.preparation_status(root)
                if preparation is not None and preparation['candidate_id'] == last_science.get('candidate_recommendation'):
                    status, reason = 'closeout_preparation_unavailable', preparation['last_failure']
        if status in {'closeout_pending', 'closeout_correction_pending', 'candidate_audit_pending', 'delivery_reselect', 'selection_comparison_pending','engineering_repair_review_pending','candidate_audit_review_pending'} and not _closeout_funds(
                root, preparation_seconds=begin['preparation_seconds'], step=step):
            status = 'closeout_budget_unavailable'
    result = dict(status=status, goal_completion='not_asserted', objective_ref=str(root / 'project/global/objective.md'),
        scientific_output_ref=str(execution.raw(root,last)) if last is not None else None,
        scientific_limitations=last_science['limitations'][:4] if last_science is not None else [],
        source_cutoff=cutoff, last_step=last, completed_scientific_nodes=cutoff + len(closed),
        used_steps=budget.used_steps(root), usage=native.usage(root), budget=budget.snapshot(root),
        previous_submission_observation=previous['actual_submission'], existing_A_recommendation=latest['a_recommended'],
        last_confirmed=confirmed[-1] if confirmed else None,
        current_actual='unknown' if state['unresolved_operations'] or pending_confirmation else (confirmed[-1] if confirmed else None))
    if screened is not None:
        result['control_selection'] = screened
    if reason is not None:
        result['reason'] = reason
    if step is not None:
        result['attempt_step'] = step
    return result


def _closeout_funds(root, *, preparation_seconds=0., step=None, author_required=True):
    settings = contracts.settings(root)
    policy = settings.get('delivery_policy')
    if policy is None:
        return False
    meter, limits = native.usage(root), budget.snapshot(root)
    external = policy['adapter'] is not None
    floor = budget.closeout_floor(settings, preparation_seconds=preparation_seconds)
    additional = int(author_required and not (step is not None and (root / 'jobs' / f'{step:03d}.json').exists()))
    author = policy['closeout_a'] if author_required else dict(max_observed_tokens=0,max_seconds=0)
    return (not meter['unknown_steps']
        and limits['max_tokens'] - meter['observed_tokens'] > 0
        and limits['max_tokens'] - meter['observed_tokens'] >= author['max_observed_tokens'] + floor['tokens']
        and limits['seconds_remaining'] >= author['max_seconds'] + floor['seconds']
        and settings['max_steps'] - budget.used_steps(root) >= additional + (2 if external else 0))


def _start_closeout(root, cutoff, first_step, reason, *, export_only=False, authorization_step=None):
    from . import delivery
    if budget.closeout_state(root)['begin'] is not None:
        return _run_closeout(root)
    if (root / 'jobs' / f'{first_step:03d}.json').exists():
        return _closeout_result(root, 'retained_job_conflict', reason='Closeout cannot replace a prepared scientific task', step=first_step)
    if budget.execution_blocked(root):
        return _closeout_result(root, 'closeout_blocked', reason='Original execution remains live or unknown')
    if (root / 'pause.request').exists() or correction.gate(root, cutoff) is not None:
        return _closeout_result(root, 'closeout_blocked', reason='Original pause requires its existing release or exact ack')
    # Validate the exact prefix, never globally ignore a stopped scientific node.
    for step in range(1, cutoff + 1):
        contracts.validate(contracts.workspace(root, step))
    policy = contracts.settings(root).get('delivery_policy')
    configured = not export_only and policy is not None and policy['adapter'] is not None
    use_model = configured
    sources, preparation = None, 0.
    if use_model:
        budget.transition(root, 'advance', 'prepare_closeout_inputs')
        at = budget.snapshot(root)['advance_seconds']
        nodes = [dict(step=step, seal_sha256=contracts.digest(_record(root, step) / 'result-identity.json'))
                 for step in range(1, cutoff + 1)]
        try:
            sources = delivery.catalogue_sources(root, nodes)
        except delivery.DeliveryUnresolved as error:
            # No accepted external effect or immutable boundary exists yet.
            # Retain the failure without converting a transient preparation
            # problem into permanent operator export authorization.
            delivery.preparation_failure(root, error.code, nodes)
            return _closeout_result(root, 'closeout_preparation_unavailable', reason=error.code)
        preparation = budget.snapshot(root)['advance_seconds'] - at
        use_model = _closeout_funds(root, preparation_seconds=preparation, author_required=authorization_step is None)
    budget.begin_closeout(root, cutoff, first_step, reason, export_only=not configured,
                          delivery_sources=sources, preparation_seconds=preparation, authorization_step=authorization_step)
    if not use_model:
        return _closeout_result(root, 'closeout_budget_unavailable' if configured else 'exported_unsubmitted',
            reason='closeout_budget_unavailable' if configured else 'export_only')
    return _run_closeout(root)


def _run_delivery_actions(root, job, result):
    from . import delivery
    state = budget.closeout_state(root)
    policy = contracts.settings(root)['delivery_policy']
    if policy['adapter'] is None:
        return _closeout_result(root, 'exported_unsubmitted', reason='No external delivery adapter was configured')
    actions = [row for row in state['actions'] if row['intent']['decision']['step'] == job['step']]
    if actions:
        original = actions[0]['intent']
        completed = actions[-1]['outcome']
        if completed is not None and completed['result']['status'] == 'confirmed' and actions[-1]['intent']['action_kind'] == 'confirm':
            return _closeout_result(root, 'delivery_confirmed')
        if completed is not None and completed['result']['status'] in {'failed', 'rejected', 'engineering_error', 'unclassified'} and completed['result']['cleanup_confirmed']:
            return _closeout_result(root, 'delivery_reselect' if completed['result']['status']=='rejected' else 'delivery_' + completed['result']['status'], reason=completed['result']['note'])
        kind, binding = 'confirm', original['binding']
        if budget.execution_blocked(root, ignore_operation=binding['operation_id']):
            return _closeout_result(root, 'delivery_unknown', reason='Original operation remains live or unverified; never resubmit')
    else:
        try:
            binding = delivery.binding(root, job, result)
        except delivery.DeliveryUnresolved as error:
            return _closeout_result(root, 'closeout_unresolved', reason=error.code)
        kind = 'submit'
    while True:
        try:
            intent = budget.accept_action(root, kind, binding['operation_id'], binding['decision'], binding,
                                          policy['submit_seconds' if kind == 'submit' else 'confirm_seconds'])
        except budget.NodeBudgetUnavailable:
            return _closeout_result(root, 'closeout_budget_unavailable')
        budget.transition(root, 'advance', 'delivery_' + kind)
        remaining = min(intent['max_seconds'], budget.snapshot(root)['seconds_remaining'])
        reply = delivery.invoke(root, intent, remaining,
            on_process=lambda phase, identity: budget.action_process(root, intent, phase, identity))
        budget.action_outcome(root, intent, reply)
        if reply['status'] != 'confirmed':
            status = ('delivery_reselect' if reply['status'] == 'rejected' and reply.get('failure_phase') == 'audit'
                and reply['cleanup_confirmed'] else 'delivery_' + reply['status'])
            return _closeout_result(root, status, reason=reply['note'])
        if kind == 'confirm':
            return _closeout_result(root, 'delivery_confirmed')
        kind = 'confirm'  # First confirmation is explicitly reserved and accepted once.


def _repair_funds(root):
    settings=contracts.settings(root)
    limits,meter=budget.snapshot(root),native.usage(root)
    if budget.execution_blocked(root) or meter['unknown_steps']:return False
    worker=(settings.get('node_budget_policy') or {}).get('W')
    if worker is None:return False
    policy=settings['delivery_policy'];author=policy['closeout_a']
    floor=budget.closeout_floor(settings)
    return (limits['max_tokens']-meter['observed_tokens'] >= worker['max_observed_tokens']+author['max_observed_tokens']+floor['tokens']
        and limits['seconds_remaining'] >= worker['max_seconds']+author['max_seconds']+floor['seconds']
        and settings['max_steps']-budget.used_steps(root) >= 2+floor['steps'])


def _run_closeout(root):
    from . import delivery,engineering
    begin = budget.closeout_state(root)['begin']
    if begin is None:
        raise ValueError('Closeout continuation has no immutable boundary')
    if begin['mode'] == 'export_only':
        return _closeout_result(root, 'exported_unsubmitted', reason=begin['stop_reason'])
    if (root / 'pause.request').exists() or correction.gate(root, begin['source_cutoff']) is not None:
        return _closeout_result(root, 'closeout_blocked', reason='Original pause remains effective')
    initial_repair=None
    first_job=root/'jobs'/f'{begin["first_step"]:03d}.json'
    if first_job.exists():initial_repair=contracts.read(first_job).get('engineering_repair')
    if contracts.settings(root).get('selection_policy') and not first_job.exists():
        try:
            stopped = shortlist.screen(root, begin)  # Control shortlist, smoke and audit before the first closeout A.
        except delivery.DeliveryUnresolved as error:
            return _closeout_result(root, 'closeout_preparation_unavailable', reason=error.code)
        if stopped is not None:return _closeout_result(root,stopped)
    parents = []
    for role in ('H', 'W', 'A'):
        matching = [step for step in range(1, begin['source_cutoff'] + 1)
                    if contracts.read(root / 'jobs' / f'{step:03d}.json')['role'] == role]
        if matching:
            parents.append(matching[-1])
    instruction = ('Choose a scientifically justified frozen candidate to retain or replace for delivery within the remaining authorization. '
        'Candidates marked audit_pending are not qualified: the adapter performs the public audit after your choice and permits delivery only if it passes. '
        'Do not perform or manufacture mechanical audit qualification. '
        'Use next_action=deliver to explicitly authorize adapter delivery and candidate_recommendation for its exact candidate. '
        'Use finish to decline delivery or wait to pause. Neither delivery nor finish asserts global goal completion. '
        'Explain science, limitations and unmet objectives. E only extracts scientific evidence; control resolves, packages and submits originals. '
        'Exploration is closed; continue_w/revise_h/extract require bounded clarification, never automatic dispatch.')
    if contracts.settings(root).get('selection_policy') and shortlist.marker(root) is not None:
        instruction = ('Compare every closeout.comparison row by the same fields and fill candidate_comparison. '
            'Control pre-registered the default; candidate_recommendation null keeps it, another choice requires override. '
            'Candidates without a passed audit are qualified only by the adapter public audit at submission. '
            'Use next_action=deliver to explicitly authorize adapter delivery, finish to decline, or wait to pause. '
            'Explain science, limitations and unmet objectives; global completion remains unasserted. '
            'E extracts scientific evidence only. Exploration is closed; new H/W/E requests require bounded clarification.')
    from . import engineering
    repair=initial_repair
    if repair:parents=sorted({repair['decision_step'],repair['source']['step']})
    author_request, corrections = None, 0
    if begin.get('authorization_step') is not None and repair is None:
        step = begin['authorization_step']
        if not budget.closeout_state(root)['actions'] and not _closeout_funds(root,
                preparation_seconds=begin['preparation_seconds'], author_required=False):
            return _closeout_result(root, 'closeout_budget_unavailable', step=step)
        job = contracts.read(root / 'jobs' / f'{step:03d}.json')
        result = contracts.validate(contracts.workspace(root, step))
        if job['role'] != 'A' or job.get('purpose') is not None or result['next_action'] != 'deliver' or step != begin['source_cutoff']:
            raise ValueError('Original direct delivery authorization changed')
        try:
            if job.get('selection') and engineering.screen_failure(root,step) is not None:
                raise delivery.PreparationUnavailable('selection_candidate_engineering_failed')
            delivery.prepare_binding(root, job, result)
        except delivery.PreparationUnavailable as error:
            repair=engineering.request(root,step)
            if repair is None:return _closeout_result(root,'closeout_preparation_unavailable',reason=error.code,step=step)
            try:engineering.admit(root,repair,begin['first_step'])
            except engineering.RepairUnavailable as blocked:return _closeout_result(root,str(blocked),step=step)
        except delivery.DeliveryUnresolved as error:
            if error.code == 'selection_comparison_required':
                instruction = ('Control screening is ready under the frozen selection policy. Compare every closeout.comparison row '
                    'and fill candidate_comparison. Null keeps the control default; another choice requires an exact override. '
                    'The original A selection and limitations remain retained. Use deliver to authorize, finish to decline, audit or wait.')
            else:
                source = semantic._source(root, step)
                author_request = dict(root=source, source=source, reason=error.code)
                corrections = 1
                instruction = ('Clarify the original unresolved delivery authorization: ' + error.code
                    + '. Use deliver for exact adapter delivery, audit for qualification, finish to decline or wait. E extracts scientific evidence only.')
        else:
            delivered = _run_delivery_actions(root, job, result)
            if delivered['status']=='delivery_engineering_error':
                repair=engineering.request(root,step)
                if repair is None:return delivered
                try:engineering.admit(root,repair,begin['first_step'])
                except engineering.RepairUnavailable as error:return _closeout_result(root,str(error))
            elif delivered['status'] != 'delivery_reselect':
                return delivered
            instruction = ('The adapter failed audit before submission: ' + delivered.get('reason', '')
                + '. Select another candidate with deliver, request audit, decline with finish or wait. The original budget remains binding.')
        parents = sorted({step,repair['source']['step']}) if repair else [step]
    # Normal audit/selection turns are bounded by the original shared budget.
    # Only an invalid author decision consumes the separate correction allowance.
    for step in range(begin['first_step'], contracts.settings(root)['max_steps'] + 1):
        record = _record(root, step)
        path = root / 'jobs' / f'{step:03d}.json'
        if not (record / 'result-identity.json').exists():
            if (root / 'pause.request').exists() or correction.gate(root, begin['source_cutoff']) is not None:
                return _closeout_result(root, 'closeout_blocked', reason='Original pause remains effective', step=step)
            if author_request is not None and corrections > semantic.MAX_AUTHOR_CORRECTIONS:
                return _closeout_result(root, 'closeout_unresolved', reason='semantic_correction_limit', step=step)
            if (record / 'native-intent.json').exists():
                try:
                    if runtime.node_state(root, step) == 'running':
                        native.wait_native(root, step)
                    elif _terminal_success(execution.record(root, step)):
                        continuation.seal_or_repair(root, step)
                    else:
                        return _closeout_result(root, 'closeout_native_unsealed', step=step,
                            reason='Use worker-resume for this exact known failed task/session; unknown work is never replayed')
                except continuation.ResumeUnavailable as error:
                    return _closeout_result(root, 'output_repair_unavailable', step=step, reason=str(error))
                except OutputRepairRequired as error:
                    return _closeout_result(root, 'output_repair_required', step=step, reason=error.code)
                except Exception:
                    return _closeout_result(root, 'closeout_native_unsealed', step=step)
            else:
                if repair is not None and not _repair_funds(root):
                    return _closeout_result(root,'engineering_repair_budget_unavailable',step=step)
                if budget.execution_blocked(root) or repair is None and not _closeout_funds(root, preparation_seconds=begin['preparation_seconds'], step=step):
                    return _closeout_result(root, 'closeout_budget_unavailable', step=step)
                budget.transition(root, 'advance', 'closeout_engineering_repair_admission' if repair else 'closeout_author_admission')
                if path.exists():
                    prior = contracts.read(path)
                    if prior.get('purpose') != 'closeout' or prior.get('source_cutoff') != begin['source_cutoff'] or prior['direct_refs'] != [dict(path=f'inputs/parents/{parent:03d}/conclusion.json',sha256=contracts.digest(execution.raw(root,parent))) for parent in parents]:
                        return _closeout_result(root, 'retained_job_conflict', step=step)
                if repair is None and contracts.settings(root).get('selection_policy') is not None:
                    stopped=shortlist.screen(root,begin,before_step=step)
                    if stopped is not None:return _closeout_result(root,stopped,step=step)
                try:
                    contracts.build_job(root, step, 'W' if repair else 'A', parents,
                        instruction=engineering.public(repair)['scope'] if repair else instruction, purpose='closeout',
                        source_cutoff=begin['source_cutoff'], delivery_sources=engineering.sources(root,step),
                        author_correction=author_request if repair is None else None, engineering_repair=repair)
                except engineering.RepairUnavailable as error:
                    return _closeout_result(root,str(error),step=step)
                try:
                    native.execute_native(root, step)
                except budget.NodeBudgetUnavailable:
                    return _closeout_result(root, 'closeout_budget_unavailable', step=step)
                except continuation.ResumeUnavailable as error:
                    return _closeout_result(root, 'output_repair_unavailable', step=step, reason=str(error))
                except OutputRepairRequired as error:
                    return _closeout_result(root, 'output_repair_required', step=step, reason=error.code)
                except Exception:
                    return _closeout_result(root, 'closeout_native_unsealed', step=step)
        job = contracts.read(path)
        result = contracts.validate(contracts.workspace(root, step))
        if job['role']=='W':
            repair=None
            parents=sorted({step,*engineering.steps(root,step),*parents})
            instruction='Judge the bounded implementation repair and new candidate from exact evidence. Old delivery authorization does not cover new bytes. Use deliver only for an explicit new choice, or report unresolved science.'
            author_request=None
            continue
        if result['next_action'] == 'audit':
            from . import candidate_audit
            screened_failure=engineering.screen_failure(root,step)
            if screened_failure is None:
                audit_status = candidate_audit.execute(root, job, result)
                if audit_status is not None:
                    return _closeout_result(root, audit_status, step=step)
                receipt=candidate_audit._outcome(root,step)['result']
            else:receipt=screened_failure[0]
            repair=engineering.request(root,step)
            if repair is not None or receipt['status'] in {'engineering_error','unclassified'}:
                if repair is None:return _closeout_result(root,'closeout_preparation_unavailable' if screened_failure is not None else 'candidate_audit_'+receipt['status'],reason=receipt['note'],step=step)
                try:engineering.admit(root,repair,step+1)
                except engineering.RepairUnavailable as error:return _closeout_result(root,str(error),step=step)
            parents, author_request = sorted({step,*engineering.steps(root,step),*([repair['source']['step']] if repair else [])}), None
            instruction = 'Reassess the requested candidate using the bound audit receipt; exploration remains closed.'
            continue
        if result['next_action'] in {'finish', 'wait'}:
            return _closeout_result(root, 'exported_unsubmitted' if result['next_action'] == 'finish' else 'closeout_waiting',
                reason='scientific_delivery_declined' if result['next_action'] == 'finish' else 'scientific_wait', step=step)
        # There is no implicit replacement or retention on missing choice/qualification.
        try:
            if job.get('selection') and engineering.screen_failure(root,step) is not None:
                raise delivery.PreparationUnavailable('selection_candidate_engineering_failed')
            delivery.prepare_binding(root, job, result)
        except delivery.PreparationUnavailable as error:
            repair=engineering.request(root,step)
            if repair is None:return _closeout_result(root,'closeout_preparation_unavailable',reason=error.code,step=step)
            try:engineering.admit(root,repair,step+1)
            except engineering.RepairUnavailable as blocked:return _closeout_result(root,str(blocked),step=step)
            parents=sorted({step,repair['source']['step'],*engineering.steps(root,step)})
            author_request=None
            continue
        except delivery.DeliveryUnresolved as error:
            corrections += 1
            source = semantic._source(root, step)
            author_request = dict(root=author_request['root'] if author_request else source, source=source,
                                  reason=author_request['reason'] if author_request else error.code)
            parents = [step]
            instruction = ('Correct only this unresolved delivery choice: ' + error.code + '. '
                'Use deliver to explicitly authorize adapter delivery of an exact candidate, audit for qualification, finish to decline or wait. '
                'extract means scientific evidence extraction; it never authorizes copying or submission. Exploration is closed.')
            continue
        delivered = _run_delivery_actions(root, job, result)
        if delivered['status']=='delivery_engineering_error':
            repair=engineering.request(root,step)
            if repair is None:return delivered
            try:engineering.admit(root,repair,step+1)
            except engineering.RepairUnavailable as error:return _closeout_result(root,str(error),step=step)
        elif delivered['status'] != 'delivery_reselect':
            return delivered
        parents, author_request = sorted({step,*engineering.steps(root,step),*([repair['source']['step']] if repair else [])}), None
        instruction = ('The completed public audit rejected candidate '
            + str(result.get('candidate_recommendation')) + ': ' + delivered.get('reason', '')
            + '. Select an alternative candidate with deliver, request audit, decline with finish or wait. '
            'No unknown external operation may be repeated; original science and budget remain binding.')
    return _closeout_result(root, 'closeout_budget_unavailable', reason='original_steps_exhausted')


def closeout(root, *, export_only=False):
    from .protocol import require_current
    require_current(root)
    root = Path(root).resolve()
    with _writer(root):
        if budget.closeout_state(root)['begin'] is not None:
            return _closeout_result(root, 'exported_unsubmitted', reason='operator_export_only') if export_only else _run_closeout(root)
        cutoff = 0
        for step in range(1, contracts.settings(root)['max_steps'] + 1):
            record = _record(root, step)
            if (record / 'result-identity.json').exists():
                contracts.validate(contracts.workspace(root, step));cutoff = step
            elif not export_only and (record / 'native-intent.json').exists() and _terminal_success(execution.record(root, step)):
                continuation.seal_or_repair(root, step);cutoff = step
            else:
                break
        first = max((int(path.stem) for path in (root / 'jobs').glob('*.json')), default=0) + 1
        if not (root / 'host-started.json').exists():
            contracts.write(root / 'host-started.json', budget.clock_stamp())
        return _start_closeout(root, cutoff, first, 'operator_closeout', export_only=export_only)


def worker_resume(root: Path, step: int):
    """Explicitly accept one continuation, or collect its already accepted work."""
    from .protocol import require_current
    require_current(root)
    root = Path(root).resolve()
    with _writer(root):
        settings = contracts.settings(root)
        try:
            if type(step) is not int or not 0 < step <= settings['max_steps']:
                raise ValueError('An exact prepared node is required')
            continuation.start(root, step)
            return _run(root)
        except (continuation.ResumeUnavailable, budget.NodeBudgetUnavailable) as error:
            budget.inactive(root, 'worker_resume_unavailable')
            return dict(status='worker_resume_unavailable', reason=getattr(error, 'reason', str(error)), usage=native.usage(root))
        except Exception:
            budget.inactive(root, 'worker_resume_failed')
            raise
