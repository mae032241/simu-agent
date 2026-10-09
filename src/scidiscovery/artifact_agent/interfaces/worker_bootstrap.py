"""Exact queued-task bootstrap; native spawn remains a scheduler choice.

The signed claim transports control authority, never a model-chosen native ID.
Existing attachment rows provide atomic single-owner/replay protection.
"""
import base64
import hashlib
import hmac
import json

from ...operation_contract import DiagnosticError
from ...agent_execution_settings import canonical_model_id


def _signature(secret, payload):
    return hmac.new(secret, b"scidiscovery.worker-bootstrap.v1\0" + payload, hashlib.sha256).hexdigest()


def offer(facade, context, reply):
    secret = facade.instance_management_secret
    if not secret or not isinstance(reply, dict):
        return reply
    task = reply.get("result", reply)
    if not isinstance(task, dict) or task.get("state") != "queued" or not task.get("dispatch"):
        return reply
    run_id = facade._resolve("run", task["name"])
    instance = facade._instance_id()
    generation = facade.bindings.progression_status(instance_id=instance, internal=True)["generation"]
    payload = json.dumps(dict(run_id=run_id, instance=instance, generation=generation,
        scheduler=facade.session_key, session=context.session, parent=context.thread),
        sort_keys=True, separators=(",", ":")).encode()
    token = base64.urlsafe_b64encode(payload).decode() + "." + _signature(secret, payload)
    task["dispatch"] = {**task["dispatch"],
        "instruction": "Spawn once with the returned agent_type and frozen model/reasoning profile, without parent history. "
            "Pass bootstrap unchanged as the child's first scid_call. Control attaches its actual platform identity "
            "and opens the assignment. Do not ask for identity, call worker_attach or send a second start message. "
            "If spawn acceptance is uncertain, reconcile; never spawn a replacement automatically. "
            "Use sealed run_status after completion.",
        "bootstrap": {"name": "worker_open_assignment", "arguments": {"dispatch_token": token}}}
    task["dispatch"].pop("attachment", None)
    return reply


def attach(facade, connections, context, token):
    try:
        if not facade.instance_management_secret or not context.worker:
            raise ValueError()
        encoded, signature = token.split(".")
        payload = base64.b64decode(encoded, altchars=b"-_", validate=True)
        if not hmac.compare_digest(signature, _signature(facade.instance_management_secret, payload)):
            raise ValueError()
        claim = json.loads(payload)
        if (claim["session"] != context.session or claim["parent"] != context.session
                or context.parent_thread != claim["parent"]):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise DiagnosticError("Worker bootstrap is invalid for this native parent/session; report the error to Root for exact worker_attach fallback, without spawning a replacement")
    run_id = claim["run_id"]
    runs = facade.runs
    with runs.instance_maintenance.global_guard(), runs.instance_maintenance.guard(claim["instance"]):
        runs.scheduler_bindings.require_active_instance(instance_id=claim["instance"])
        status = runs.status(run_id)
        if status.instance_id != claim["instance"]:
            raise DiagnosticError("Worker bootstrap instance mismatch")
        profile = (status.execution_profile or {}).get("profile")
        if (not profile or canonical_model_id(context.model) != canonical_model_id(profile["model"])
                or context.effort != profile["reasoning_effort"]):
            raise DiagnosticError("Worker bootstrap platform profile mismatch")
        # A retry by the exact accepted owner is not a new dispatch. Match the
        # explicit attachment path: pause/restart must not strand accepted work.
        with runs._connect() as db:
            existing = db.execute("SELECT platform_session, thread_id FROM worker_connections WHERE run_id=?",
                (run_id,)).fetchone()
        if existing is not None and tuple(existing) == (context.session, context.thread):
            current = connections.resolve(platform_session=context.session, thread_id=context.thread)
            if current.run_id != run_id:
                raise DiagnosticError("Worker bootstrap belongs to an earlier task; use the current assignment")
            return
        # Each native proxy has its own unbound facade. Scheduling authority is
        # the signed Root issuer, not the Worker's transport session key.
        with facade.bindings.scheduling_guard(instance_id=claim["instance"], session_key=claim["scheduler"],
                expected_generation=claim["generation"], continuation=("run", run_id)) as generation:
            facade.bindings.require_dispatch_intent(instance_id=claim["instance"], run_id=run_id,
                session_key=claim["scheduler"], generation=generation)
            connections.attach(run_id=run_id, platform_session=context.session, thread_id=context.thread,
                allow_rebind=False)
