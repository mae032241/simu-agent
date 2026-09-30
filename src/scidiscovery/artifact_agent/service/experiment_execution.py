"""Control-owned execution commands scoped to one running experiment."""
from __future__ import annotations

import hashlib

from ...operation_contract import contract_diagnostic, DiagnosticError, ToolInputError

from ...operations.invoke import (ApprovalProjectorContext, ApprovalSubjectSnapshot,
    effect_operation_plan)
from ..execution_bridge import ExecutionAuthorizationRequired
from ..schema.approval import (ApprovalOption, ApprovalRequest, CompiledApprovalIdentity,
    HumanDecision, execution_approval_option_id, execution_decision_authorizes)
from ..schema.common import canonical_json
from ..schema.execution import ExecutionResultManifest
from ..schema.artifact import ArtifactRegistration


class ExperimentExecution:
    def __init__(self, *, runs, executions, bridge, collection, approval_base_url):
        self.runs, self.executions = runs, executions
        self.bridge, self.collection = bridge, collection
        self.approval_base_url = approval_base_url
        if runs is not None and executions is not None and executions.approvals is not None:
            runs.approval_database_path = executions.approvals.database_path
        self.services_for = None
        self.worker_services = {}

    def task_origin(self, run):
        return self.task_lineage(run)[-1].run_id

    def task_lineage(self, run):
        return self.runs.task_lineage(run.run_id)

    def _domain_active(self, run):
        if self.services_for is not None:
            self.worker_services.update(self.services_for(run.operation_id))
        ancestors = self.task_lineage(run)
        lineage = {item.run_id for item in ancestors}
        inputs = tuple(binding for item in ancestors for binding in item.inputs)
        details = []
        for service in {id(item): item for item in self.worker_services.values()}.values():
            if callable(getattr(service, "experiment_pending_diagnostics", None)):
                details.extend(service.experiment_pending_diagnostics(lineage, inputs))
            elif callable(getattr(service, "experiment_activity", None)) and service.experiment_activity(lineage, inputs, cancel=False):
                details.append(contract_diagnostic("experiment_diagnostics_pending", phase="protocol",
                    affected_action="submit", repairable=True,
                    message="An experiment diagnostic is still active. Finish or cancel the existing diagnostic, then resubmit the unchanged report."))
        return details

    def require_idle(self, run):
        from .run_outputs import RunOutputError
        origin = self.task_origin(run)
        active = self._domain_active(run)
        blockers = []
        for binding in self.runs.scheduler_bindings.list(instance=run.instance_id, namespace="execution",
                name_prefix="experiment-" + origin + "-"):
            if self._execution_owner(binding.object_id) != origin:
                continue
            self._reconcile_authorization(binding.object_id)
            status = self.executions.status(binding.object_id)
            if status.external_run_id is not None and status.state in {"submitted", "running", "cancelling"}:
                # Final delivery must not depend on the next background observation.
                self.bridge.sync(execution_id=binding.object_id, diagnostic_scope="instance:" + run.instance_id)
                status = self.executions.status(binding.object_id)
            if status.state not in {"succeeded", "failed", "cancelled", "collected", "abandoned"}:
                name = binding.name.removeprefix("experiment-" + origin + "-")
                blockers.append(contract_diagnostic("experiment_outstanding_work", phase="protocol",
                    affected_action="submit", repairable=True,
                    message=f"Execution {name!r} is {status.state}. Read worker_experiment_execute(action='status', name={name!r}); finish it or call action='cancel' with the same name, then resubmit the unchanged report."))
        blockers.extend(active)
        if blockers:
            from ...operation_contract import bounded_diagnostics
            raise RunOutputError("Outstanding experiment work must finish before final delivery.",
                category="execution_pending", details=bounded_diagnostics(blockers, phase="protocol", action="submit"))

    def _execution_owner(self, execution_id):
        envelope = self.executions.artifacts.get_by_id(self.executions.request_artifact_id(execution_id))
        return envelope.labels.get("experiment_run")

    def implementation(self, context, alias):
        from .sealed_materials import material_error
        record = self.runs.sealed_material_record(self.runs.status(context.run_id), alias)
        if record is None or record.get("metadata", {}).get("kind") != "experiment_implementation":
            raise material_error("experiment_implementation_unavailable",
                "Choose a sealed implementation created in or explicitly bound to this task.")
        return self._implementation_payload(record)

    def _implementation_payload(self, record):
        from ..schema.refs import ArtifactRef
        from .sealed_materials import material_error
        material = ArtifactRef.model_validate(record["artifact_ref"])
        packages = [ref for ref in self.executions.artifacts.verify(material).parent_refs
            if self.executions.artifacts.verify(ref).kind == "experiment_execution_package"]
        if len(packages) != 1:
            raise material_error("experiment_implementation_package_invalid",
                "The sealed implementation has no unique controlled execution package.")
        return packages[0]

    def _contract(self, context):
        run = self.runs.running_task(context.run_id)
        return self._contract_for_run(run)

    def _contract_for_run(self, run):
        compiled = self.runs.compiled_operation(run)
        ref = compiled.spec.executor.capability
        if ref is None:
            raise ValueError("No execution method is configured for this experiment.")
        capability = compiled.implementations[f"{ref.plugin_id or compiled.plugin_id}:{ref.component_id}"]
        effect = self.runs.operation_catalog.operation(capability.execution_operation)
        identity = effect.approval_identity
        if identity is None:
            raise ValueError("The configured execution method has no authorization contract.")
        return run, effect, CompiledApprovalIdentity(operation_id=identity.operation_id,
            operation_version=identity.version, operation_digest=identity.operation_digest,
            approval_contract_digest=identity.approval_contract_digest), capability

    def capabilities(self, context):
        _, effect, _, _ = self._contract(context)
        return self.bridge.capabilities(executor=effect_operation_plan(effect).executor)

    def seal_implementation(self, context, *, payload, scientific_material, sources, private_outputs=()):
        run, effect, _, capability = self._contract(context)
        plan = effect_operation_plan(effect)
        port = next(item for item in effect.spec.inputs if item.name == plan.payload_port)
        parents = tuple(context.source_descriptor(alias).artifact_ref for alias in sources)
        private = self.executions.artifacts.register(payload, ArtifactRegistration(
            kind="experiment_execution_package", schema_id=port.schema_id,
            payload_schema_version=capability.execution_package_schema_version,
            media_type="application/json", creator=self.executions.service_actor, parent_refs=parents,
            confidentiality="approval_only", labels={"experiment_run": run.run_id, "experiment_task": self.task_origin(run)}),
            idempotency_key="experiment-package:" + hashlib.sha256(canonical_json({
                "run": run.run_id, "payload": hashlib.sha256(payload).hexdigest(), "parents": parents})).hexdigest()).ref
        record = context.accept_evidence(raw=scientific_material, media_type="application/json",
            derived_from=sources, trusted_parent_refs=(private,), metadata={"kind": "experiment_implementation", "private_outputs":list(private_outputs)})
        if (run.recovery_policy or {}).get("require_execution_review"):
            record["review"] = self.review_handoff(run, record)
        return record

    def review_handoff(self, run, implementation):
        """Give the scheduler an exact public request, without starting a reviewer."""
        name = self.runs.publish_sealed_material(run, implementation["alias"])
        request_name = name + ".review"
        if len(request_name) > 256:
            request_name = name[:230] + ".review-" + hashlib.sha256(name.encode()).hexdigest()[:16]
        return {"required": bool((run.recovery_policy or {}).get("require_execution_review")),
            "read_guidance": "After the review completes, call worker_experiment_execute(action='review', implementation=<the same reference>) again. It returns review_result.verdict and a read_request for worker_reference_read, including revise/blocked findings, without ending this Run.",
            "subject_artifact_name": name,
            "request": {"name": request_name, "operation_id": "science.object.review.v1",
                "inputs": [{"port": "subject", "artifact_names": [name]}],
                "instruction": "Independently review this exact sealed implementation against its bound research objective, scientific constraints and required observables. Report missing evidence and limitations explicitly; execution permission does not establish scientific validity."}}

    def _implementation_record(self, context, payload_ref):
        return self._run_implementation_record(self.runs.status(context.run_id), payload_ref)

    def _run_implementation_record(self, run, payload_ref):
        records = [item for item in self.runs.available_material_records(run)
            if item.get("metadata", {}).get("kind") == "experiment_implementation"
            and self._implementation_payload(item) == payload_ref]
        if not records:
            from .sealed_materials import material_error
            raise material_error("experiment_implementation_unavailable",
                "Bind the exact sealed implementation used by this execution.")
        if len({canonical_json(item["artifact_ref"]) for item in records}) != 1:
            raise ValueError("Execution has conflicting implementation receipts.")
        return records[0]

    def _cancel(self, execution_id):
        self.bridge.submissions.require_idle(execution_id)
        status = self.executions.status(execution_id)
        if status.state == "abandoned":
            self.executions.abandon(execution_id)  # Complete any interrupted approval cleanup.
            return
        if status.state in {"created", "authorized"}:
            prepared = self.executions.prepared_submission(execution_id)
            if prepared is None:
                self.bridge.abandon(execution_id)
                return
            found = self.bridge._adapter(status.executor).lookup_submission(prepared)
            if found is None:
                message = "Cancellation could not be confirmed: the exact prepared submission is not yet visible and an earlier submit may still be processing. Its identity and budget remain reserved. Recover the same execution after service recovery, then cancel the confirmed job; do not create a replacement."
                raise DiagnosticError(message, details=(contract_diagnostic("experiment_execution_submission_unknown",
                    phase="tool_execution", affected_action="tool_call", repairable=False, message=message),))
            self.bridge._record_started(execution_id, *found)
        if self.executions.status(execution_id).state != "abandoned":
            self.bridge.cancel(execution_id=execution_id)

    def _io_settings(self, context):
        from ...agent_execution_settings import ExecutionIOSettings
        run = self.runs.running_task(context.run_id)
        return ExecutionIOSettings.model_validate((run.recovery_policy or {}).get("execution_io", {}))

    def _export(self, context, request, envelope):
        import os
        import time
        import uuid
        from pathlib import Path
        name = request.output_name
        if name in {".", ".."} or any(value in name for value in ("/", "\\", "\0")):
            raise ValueError("The collected output has no safe scientific filename.")
        if envelope.size_bytes > self._io_settings(context).max_export_bytes:
            raise ToolInputError("experiment_export_limit", "The collected output exceeds this workspace's file limit.", path="$.output_name")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        handles, temporary = [], ".export-" + uuid.uuid4().hex
        deadline = time.monotonic() + min(context.remaining_seconds, self._io_settings(context).file_timeout_seconds)
        try:
            parent = os.open(context.workspace, flags)
            handles.append(parent)
            for part in ("scratch", "collected", request.name):
                try:
                    os.mkdir(part, mode=0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                parent = os.open(part, flags, dir_fd=parent)
                handles.append(parent)
            target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=parent)
            with os.fdopen(target, "wb") as destination, self.executions.artifacts.open_original(envelope.ref) as original:
                while chunk := original.read(1024*1024):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Scientific output export exceeded the remaining task time.")
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        finally:
            if handles:
                try:
                    os.unlink(temporary, dir_fd=handles[-1])
                except FileNotFoundError:
                    pass
            for descriptor in reversed(handles):
                os.close(descriptor)
        return {"name":name, "path":str(Path("scratch/collected") / request.name / name),
            "media_type":envelope.media_type, "size_bytes":envelope.size_bytes}

    def _implementation_review(self, run, implementation):
        from ..schema.refs import ArtifactRef
        from .sealed_materials import material_error
        from ...general_science_experiment_review import ExperimentReview
        subject = ArtifactRef.model_validate(implementation["artifact_ref"])
        review = self.runs.latest_subject_review(run.instance_id, subject)
        if review is None or review.output_ref is None:
            return None
        compiled = self.runs.operation_catalog.operation("science.object.review.v1")
        if review.operation_version != compiled.spec.version or "subject" not in compiled.spec.independent_review_ports:
            raise material_error("experiment_execution_review_incompatible",
                "The exact implementation review uses a different installed review contract. Call worker_experiment_execute(action='review', implementation=<the same reference>) for a compatible review request; dispatch a new independent review.")
        envelope = self.runs.artifacts.catalog(review.output_ref)
        if envelope.schema_id != "scidiscovery.experiment-review.v1" or envelope.size_bytes > compiled.spec.limits.max_output_bytes:
            raise material_error("experiment_execution_review_invalid", "The exact implementation review has no valid sealed review result. Use worker_experiment_execute(action='review', implementation=<the same reference>) to obtain the exact review subject for repair.")
        raw = self.runs.artifacts.read(review.output_ref)
        result = ExperimentReview.model_validate_json(raw, strict=True)
        return review.output_ref, raw, result

    def _required_review(self, run, implementation):
        if not (run.recovery_policy or {}).get("require_execution_review"):
            return None
        from .sealed_materials import material_error
        review = self._implementation_review(run, implementation)
        if review is None:
            raise material_error("experiment_execution_review_required",
                "Independent implementation review is required. Call worker_experiment_execute(action='review', implementation=<the same reference>) for the exact public subject and operation_invoke request. Ask the scheduler to dispatch an independent reviewer, then retry start with the same implementation after a sealed pass. No execution was created.")
        ref, _, result = review
        if result.verdict != "pass":
            raise material_error("experiment_execution_review_not_passed",
                "The latest independent review of this exact implementation did not pass. Resolve its findings and review any revised implementation before execution; budget approval does not override this requirement. Call worker_experiment_execute(action='review', implementation=<the chosen reference>) for the exact review request.")
        return ref

    def command(self, context, request):
        run = self.runs.running_task(context.run_id)
        execution_id = "exe_" + hashlib.sha256(canonical_json({
            "task": self.task_origin(run), "name": request.name})).hexdigest()
        if request.action in {"status", "cancel"}:
            from .executions import ExecutionNotFound
            try:
                self.executions.status(execution_id)
            except ExecutionNotFound:
                return {"name": request.name, "state": "not_created", "submission": "not_submitted"}
            if self._execution_owner(execution_id) != self.task_origin(run):
                raise ToolInputError("experiment_execution_owner_mismatch", "This execution does not belong to the current task.")
            if request.action == "cancel":
                self._cancel(execution_id)
            else:
                self.bridge.submissions.refresh(execution_id, scope="instance:" + run.instance_id)
                self._reconcile_authorization(execution_id)
                approval = self._approval_status(execution_id)
                status = self.executions.status(execution_id)
                if approval is not None and status.state in {"created", "abandoned"}:
                    self._bind_approval(run, request.name, execution_id)
                    return self._authorization_response(run, request.name, execution_id, approval)
                if status.external_run_id is not None and status.state in {"submitted", "running", "cancelling"}:
                    self.bridge.sync(execution_id=execution_id, diagnostic_scope="instance:" + run.instance_id)
            implementation = None
            if request.action == "status" and self.executions.status(execution_id).state == "collected":
                try:
                    implementation = self._implementation_record(context, self.executions.request(execution_id).payload_ref)
                except DiagnosticError:
                    pass  # State remains readable even when scientific originals need rebinding.
            return self._execution_status(context, request, execution_id, implementation, seal=False)
        if request.action in {"capabilities", "review", "start", "advance"}:
            run, effect, identity, _ = self._contract(context)
            plan = effect_operation_plan(effect)
        if request.action == "capabilities":
            return {"methods": [{"method": item.key,
                **{k: v for k, v in item.public_summary.items()
                   if k in {"solver_kind", "release", "description", "limitations", "capabilities"}}}
                for item in self.capabilities(context)]}
        if request.action == "review":
            payload = self.implementation(context, request.implementation)
            implementation = self._implementation_record(context, payload)
            result = {"implementation": request.implementation,
                "review": self.review_handoff(run, implementation)}
            review = self._implementation_review(run, implementation)
            if review is not None:
                ref, raw, assessment = review
                # Deliver unchanged reviewer bytes through the existing immutable,
                # bounded material channel. This copy never grants review authority:
                # execution admission continues to check the original exact review.
                record = context.accept_evidence(raw=raw, media_type="application/json",
                    derived_from=(request.implementation,), trusted_parent_refs=(ref,),
                    metadata={"kind": "experiment_review", "review_ref": ref.model_dump(mode="json")})
                result["review_result"] = {"state": "completed", "verdict": assessment.verdict,
                    "reference": record["alias"], "read_request": {"action": "read",
                        "source": record["alias"], "reference": "content"}}
            else:
                result["review_result"] = {"state": "not_available"}
            return result
        if request.action == "start":
            if request.implementation is None:
                raise ToolInputError("experiment_implementation_required", "Choose a sealed implementation before starting execution.", path="$.implementation")
            payload = self.implementation(context, request.implementation)
            reviewed = self._required_review(run, self._implementation_record(context, payload))
            self.executions.create(executor=plan.executor, preparation_profile=plan.preparation_profile,
                payload_ref=payload, execution_id=execution_id, compiled_identity=identity,
                labels={"operation_id": identity.operation_id, "operation_version": identity.operation_version,
                    "operation_digest": identity.operation_digest, "approval_contract_digest": identity.approval_contract_digest,
                    "experiment_run": self.task_origin(run),
                    **({"implementation_review": reviewed.model_dump_json()} if reviewed is not None else {})})
            self.runs.scheduler_bindings.bind(instance=run.instance_id, namespace="execution",
                name="experiment-" + self.task_origin(run) + "-" + request.name, object_id=execution_id)
        from .executions import ExecutionNotFound
        try:
            current = self.executions.request(execution_id)
        except ExecutionNotFound as error:
            raise ToolInputError("experiment_execution_not_created",
                "No execution exists under this name. Use status with the original name; start only after confirming no earlier submission.", path="$.name") from error
        if self._execution_owner(execution_id) != self.task_origin(run):
            raise ToolInputError("experiment_execution_owner_mismatch", "This execution does not belong to the current task.")
        if request.action in {"start", "advance"} and current.compiled_identity != identity:
            raise ToolInputError("experiment_execution_contract_changed", "Execution configuration changed; the existing execution cannot be restarted.", path="$.action")
        if request.action == "logs":
            if request.offset:
                from .execution_log_reader import invalid
                raise invalid("For logs use direction and its returned cursor; offset is only for collected output read.")
            return self.executions.cached_log(execution_id, log_index=request.log_index,
                direction=request.direction, cursor=request.cursor, max_bytes=self._io_settings(context).read_page_bytes)
        implementation = self._implementation_record(context, current.payload_ref)
        private_outputs = implementation["metadata"].get("private_outputs", ())
        if request.action in {"read", "export"}:
            outputs = [item for item in self.executions.outputs(execution_id) if item.logical_name not in private_outputs]
            item = next((item for item in outputs if item.logical_name == request.output_name), None)
            if item is None:
                raise ToolInputError("experiment_output_unknown", "Select one collected output by its scientific name.", path="$.output_name")
            envelope = self.executions.artifacts.get_by_id(item.artifact_id)
            if request.action == "export":
                return self._export(context, request, envelope)
            if not (item.media_type.startswith("text/") or item.media_type == "application/json"):
                return {"name": item.logical_name, "media_type": item.media_type, "size_bytes": item.size_bytes,
                    "availability": "retained_binary", "instruction": "Use export to obtain the exact file for local domain analysis."}
            with self.executions.artifacts.open_original(envelope.ref) as stream:
                stream.seek(request.offset)
                page_bytes = self._io_settings(context).read_page_bytes
                raw = stream.read(page_bytes + 1)
            return {"name": item.logical_name, "text": raw[:page_bytes].decode("utf-8", errors="replace"),
                "next_offset": request.offset + page_bytes if len(raw) > page_bytes else None}
        if request.action in {"start", "advance"}:
            approval = self._approval_status(execution_id)
            if approval is not None:
                self._bind_approval(run, request.name, execution_id)
                response = self._authorization_response(run, request.name, execution_id, approval)
                if self.executions.status(execution_id).state in {"created", "abandoned"} and (
                        response["state"] not in {"created", "awaiting_authorization"}):
                    return response
        if request.action in {"start", "advance"}:
            if self.executions.status(execution_id).external_run_id is None:
                self._required_review(run, implementation)
            try:
                self._start_request(execution_id, effect, identity, approval)
            except ExecutionAuthorizationRequired:
                self._bind_approval(run, request.name, execution_id)
                return self._authorization_response(run, request.name, execution_id, self._approval_status(execution_id))
            if request.action == "advance" and self.executions.status(execution_id).external_run_id is not None:
                self.bridge.sync(execution_id=execution_id, diagnostic_scope="instance:" + run.instance_id)
        elif request.action == "collect":
            if self.collection is None:
                raise ValueError("The controlled collection service is unavailable.")
            self.collection.collect(execution_id, scope="instance:" + run.instance_id,
                total_seconds=min(context.remaining_seconds, self._io_settings(context).collection_timeout_seconds),
                file_timeout_seconds=self._io_settings(context).file_timeout_seconds,
                idle_timeout_seconds=self._io_settings(context).idle_timeout_seconds)
        return self._execution_status(context, request, execution_id, implementation, seal=True)

    def _execution_status(self, context, request, execution_id, implementation, *, seal):
        status = self.executions.status(execution_id)
        result = {"name": request.name, "state": status.state,
            "submission": self.bridge.submissions.summary(execution_id)}
        observation = self.executions.observation(execution_id)
        result["observation"] = {
            "state": "refresh_failed" if observation.get("observation_error") else
                "recorded" if observation.get("status_observed_at") else "unobserved",
            "observed_at": observation.get("status_observed_at"),
            "progress_observed_at": observation.get("progress_observed_at"),
        }
        if isinstance(observation.get("progress"), dict):
            from ...plugin_runtime.experiment import progress_summary
            result["progress"] = progress_summary(observation["progress"])
        if status.result_ref is not None:
            manifest = ExecutionResultManifest.model_validate_json(self.executions.artifacts.read(status.result_ref), strict=True)
            result["terminal_state"] = manifest.terminal_state
            if implementation is None:
                result["outputs_status"] = "Bind the original implementation to read collected scientific outputs. Execution state is available."
                return result
            private_outputs = implementation["metadata"].get("private_outputs", ())
            result["outputs"] = [{"name": item.logical_name, "media_type": item.media_type,
                "size_bytes": item.size_bytes} for item in self.executions.outputs(execution_id)
                if item.logical_name not in private_outputs]
            # A control observation is sealed without exposing control identities.
            if seal:
                # Operational progress is mutable; the scientific receipt stays stable.
                sealed = {key: value for key, value in result.items() if key not in {"progress", "observation", "submission"}}
                record = context.accept_evidence(raw=canonical_json(sealed), media_type="application/json",
                    derived_from=("research_objective", implementation["alias"]), trusted_parent_refs=(status.result_ref,),
                    metadata={"kind": "experiment_execution", "name": request.name, "implementation": implementation["alias"]})
                result["reference"] = record["alias"]
                result["artifact_name"] = record["artifact_name"]
        return result

    def recover_start(self, execution_id, *, instance_id):
        """Advance the original request after its entire scientific task has failed."""
        from .executions import ExecutionServiceError
        owner = self._execution_owner(execution_id)
        if owner is None or not self.runs.task_recovery_available(owner, instance_id=instance_id):
            raise ExecutionServiceError("Execution recovery requires an entirely failed task lineage")
        run = self.runs.status(owner)
        state = self.executions.status(execution_id)
        if state.external_run_id is not None:
            return  # Already submitted: recovery must not create another solver.
        if state.state not in {"created", "authorized"}:
            raise ExecutionServiceError("This execution cannot be started; inspect its terminal state")
        _, effect, identity, _ = self._contract_for_run(run)
        request = self.executions.request(execution_id)
        plan = effect_operation_plan(effect)
        if (request.compiled_identity != identity or request.executor != plan.executor
                or request.preparation_profile != plan.preparation_profile):
            raise ExecutionServiceError("Execution recovery contract differs from the original request")
        implementation = self._run_implementation_record(run, request.payload_ref)
        self._required_review(run, implementation)
        approval = self._approval_status(execution_id)
        if approval is not None and (approval.status != "decided" or self._authorization_state(approval) != "created"):
            raise ExecutionServiceError("The original execution approval has not authorized this request")
        try:
            self._start_request(execution_id, effect, identity, approval)
        except ExecutionAuthorizationRequired:
            pass  # Background handoff already published the exact approval.

    def _start_request(self, execution_id, effect, identity, approval):
        # Worker continuation and explicit Root recovery have identical authorization
        # and scientific budget ownership; neither uses standalone Effect bindings.
        run = self.runs.status(self._execution_owner(execution_id))
        from ...agent_execution_settings import ExecutionIOSettings
        io = ExecutionIOSettings.model_validate((run.recovery_policy or {}).get("execution_io", {}))
        def request_approval():
            self._approval(execution_id, effect, identity)
            name = self.runs.scheduler_bindings.find_name(instance=run.instance_id,
                namespace="execution", object_id=execution_id)
            if name is not None:
                self._bind_approval(run, name.removeprefix("experiment-" + self.task_origin(run) + "-"), execution_id)
        self.bridge.submissions.start(execution_id=execution_id,
            scope="instance:" + run.instance_id,
            wait_seconds=io.submission_response_wait_seconds,
            on_authorization_required=request_approval,
            approval_id="apr_" + execution_id if approval is not None and approval.status == "decided" else None,
            compiled_identity=identity,
            allow_policy_authorization=effect.spec.review.approval.allow_policy_authorization,
            budget_subject_schemas=("scidiscovery.research-objective.v1",))

    def recovery_actions(self, execution_id):
        state = self.executions.status(execution_id)
        actions = ["execution_status", "execution_sync", "execution_logs", "execution_collect", "execution_outputs"]
        if state.state in {"created", "authorized"} and state.external_run_id is None:
            actions.append("execution_abandon")
            approval = self._approval_status(execution_id)
            if approval is None or (approval.status == "decided" and self._authorization_state(approval) == "created"):
                actions.append("execution_start")
        elif state.state in {"submitted", "running", "cancelling"}:
            actions.append("execution_cancel")
        return actions

    def _approval_status(self, execution_id):
        from .approvals import ApprovalAccessDenied
        if self.executions.approvals is not None:
            try:
                return self.executions.approvals.status("apr_" + execution_id)
            except ApprovalAccessDenied:
                pass
        return None

    def _bind_approval(self, run, name, execution_id):
        bindings = self.runs.scheduler_bindings
        approval_id = "apr_" + execution_id
        if bindings.find_name(instance=run.instance_id, namespace="approval", object_id=approval_id) is None:
            task = bindings.find_name(instance=run.instance_id, namespace="run", object_id=self.task_origin(run))
            if task is None:
                raise ValueError("Execution approval requires its owning task's instance name.")
            semantic_name = task + ".execution." + name + ".approval"
            if len(semantic_name) > 256:
                semantic_name = semantic_name[:231] + "." + hashlib.sha256(semantic_name.encode()).hexdigest()[:24]
            bindings.bind(instance=run.instance_id, namespace="approval", name=semantic_name,
                object_id=approval_id)

    def _authorization_response(self, run, name, execution_id, approval):
        if approval.status == "pending":
            self.runs.record_approval_wait(run.run_id, "apr_" + execution_id)
        state = self._authorization_state(approval)
        self._reconcile_authorization(execution_id, approval)
        authorization = self.executions.authorization(execution_id)
        result = {"name": name, "state": state,
            "execution_state": self.executions.status(execution_id).state, "authorization": {"status": approval.status,
            **{key: authorization[key] for key in ("reason", "budget", "allowance", "per_execution_allowance", "budget_usage", "accounting") if key in authorization}}}
        bound = self.runs.scheduler_bindings.find_name(instance=run.instance_id, namespace="approval", object_id="apr_" + execution_id)
        if bound is not None:
            result["approval_name"] = bound
        if approval.status == "pending" and approval.review_path and self.approval_base_url:
            result["review_url"] = self.approval_base_url.rstrip("/") + approval.review_path
        return result

    def _authorization_state(self, approval):
        state = {"pending": "awaiting_authorization", "expired": "authorization_expired",
            "cancelled_by_human": "authorization_cancelled"}.get(approval.status, "created")
        if approval.status == "decided":
            stored = ApprovalRequest.model_validate_json(self.executions.artifacts.read(approval.approval_request_ref), strict=True)
            decision = HumanDecision.model_validate_json(self.executions.artifacts.read(approval.decision_ref), strict=True)
            if not execution_decision_authorizes(stored, decision):
                state = "authorization_rejected"
        return state

    def _reconcile_authorization(self, execution_id, approval=None):
        approval = approval or self._approval_status(execution_id)
        if approval is None or self._authorization_state(approval) not in {
                "authorization_expired", "authorization_cancelled", "authorization_rejected"}:
            return
        status = self.executions.status(execution_id)
        # No prepared submission means there is no uncertain external side effect.
        # Prepared/started requests require explicit status/cancel reconciliation.
        if (status.state == "created" and status.external_run_id is None
                and self.executions.prepared_submission(execution_id) is None):
            self.executions.abandon(execution_id)

    def _approval(self, execution_id, effect, identity):
        if self.executions.approvals is None or self.approval_base_url is None:
            raise ValueError("This execution needs the configured approval service; no execution has been submitted.")
        contract = effect.spec.review.approval
        refs = self.executions.approval_subject_refs(execution_id)
        existing = self._approval_status(execution_id)
        if existing is not None:
            stored = ApprovalRequest.model_validate_json(self.executions.artifacts.read(existing.approval_request_ref), strict=True)
            if stored.kind != "execution_authorization" or stored.subject_refs != refs or stored.compiled_identity != identity:
                raise ValueError("Execution approval does not bind the exact request and contract.")
            if existing.status == "pending":
                self.executions.approvals.refresh_access("apr_" + execution_id)
            return
        snapshots = []
        for index, (port, ref) in enumerate(zip(contract.subject_ports, refs, strict=True)):
            envelope = self.executions.artifacts.verify(ref)
            snapshots.append(ApprovalSubjectSnapshot(index, port, 0, ref, envelope.schema_id,
                envelope.media_type, envelope.size_bytes, envelope.parent_refs,
                tuple(envelope.labels.items()), None, self.executions.artifacts.read(ref)))
        projector = contract.projector
        document = effect.implementations[f"{projector.plugin_id or effect.plugin_id}:{projector.component_id}"](
            ApprovalProjectorContext(effect.spec.operation_id, effect.spec.version, effect.digest, tuple(snapshots)))
        self.executions.approvals.create_request(approval_id="apr_" + execution_id,
            kind="execution_authorization", subject_refs=refs, question=contract.question,
            options=tuple(ApprovalOption(option_id=execution_approval_option_id(item.decision),
                label=item.label, description=item.description or "Record the declared execution authorization decision.",
                requires_rationale=item.requires_reason) for item in contract.options),
            requested_by=self.executions.service_actor, idempotency_key="execution-approval:" + execution_id,
            review_document=document, compiled_identity=identity)


class _TaskExperimentTools:
    """Control adapter bound by the tool host; a template never mutates its scope."""
    __slots__ = ("__coordinator", "__operation_id", "__run_id")

    def __init__(self, coordinator, *, operation_id, run_id=None):
        self.__coordinator = coordinator
        self.__operation_id = operation_id
        self.__run_id = run_id

    def _for_run(self, run_id):
        if self.__run_id is not None and self.__run_id != run_id:
            raise ValueError("Experiment capability cannot be rebound to another Run.")
        return self if self.__run_id is not None else _TaskExperimentTools(
            self.__coordinator, operation_id=self.__operation_id, run_id=run_id)

    def __scope(self, context):
        run = self.__coordinator.runs.running_task(context.run_id)
        if run.operation_id != self.__operation_id:
            raise ValueError("Experiment capability belongs to another operation.")
        if run.run_id != self.__run_id:
            raise ValueError("Experiment capability belongs to another Run.")
        return run

    def capabilities(self, context):
        self.__scope(context)
        return self.__coordinator.capabilities(context)

    def seal_implementation(self, context, *, payload, scientific_material, sources, private_outputs=()):
        self.__scope(context)
        return self.__coordinator.seal_implementation(context, payload=payload,
            scientific_material=scientific_material, sources=sources, private_outputs=private_outputs)

    def read_implementation(self, context, alias):
        from ...plugin_runtime.experiment import SealedImplementation
        self.__scope(context)
        ref = self.__coordinator.implementation(context, alias)
        return SealedImplementation(ref, self.__coordinator.executions.artifacts.read(ref))

    def source_alias(self, context, ref):
        from .sealed_materials import material_error
        run = self.__scope(context)
        alias = self.__coordinator.runs.material_source_aliases(run).get(ref)
        if alias is None:
            raise material_error("experiment_source_not_bound",
                "Bind the exact original scientific file required by this sealed implementation.",
                path="$.implementation")
        return alias

    def diagnostic_context(self, context, *, service_name):
        from dataclasses import replace
        run = self.__scope(context)
        service = context.require_service(service_name)
        private = service.exchange_root / "experiment-workspaces" / self.__coordinator.task_origin(run)
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        return replace(context, workspace=private, output_directory=private / "output")

    def cancel_diagnostics(self, context, *, service_name, name):
        run = self.__scope(context)
        service = context.require_service(service_name)
        ancestors = self.__coordinator.task_lineage(run)
        lineage = {item.run_id for item in ancestors}
        inputs = tuple(binding for item in ancestors for binding in item.inputs)
        return bool(service.experiment_activity(lineage, inputs, cancel=True, name=name))

    def command(self, context, request):
        self.__scope(context)
        return self.__coordinator.command(context, request)


def scope_experiment_services(services, *, run_id):
    """Scope only the compiled tool's selected services, without mutating cached bindings."""
    return {key: value._for_run(run_id) if isinstance(value, _TaskExperimentTools) else value
            for key, value in services.items()}


def bind_experiment_services(runs, compiled, services, *, coordinator=None, run_id=None):
    """Shared tool-service binding for unified and standalone Worker hosts."""
    if compiled.spec.executor.capability is None:
        return services
    coordinator = coordinator or getattr(runs, "experiment_executions", None)
    if coordinator is None:
        raise ValueError("The experiment execution service is not configured.")
    coordinator.worker_services.update(services)
    capability = _TaskExperimentTools(coordinator, operation_id=compiled.spec.operation_id, run_id=run_id)
    for tool in compiled.worker_tools:
        for key in (*tool.required_services, *tool.optional_services):
            if key.partition(":")[2] == "experiment.execution":
                services[key] = capability
    return services


def open_experiment_services(runs, catalog, *, state_root, plugin_configs,
                             approval_secret_file=None, approval_base_url=None):
    from ..runtime_plugin_bindings import load_runtime_plugin_contributions
    from ..execution_bridge import ExecutionBridge
    from .execution_collection import ExecutionCollection, open_collection_executions
    executions = open_collection_executions(state_root)
    if approval_secret_file is not None:
        from ..runtime import read_secret_file
        from .approvals import ApprovalService
        executions.approvals = ApprovalService(artifacts=executions.artifacts,
            database_path=state_root / "database/approvals.sqlite3", service_actor=executions.service_actor,
            receipt_secret=read_secret_file(approval_secret_file, label="approval receipt"))
    adapters = load_runtime_plugin_contributions(catalog, plugin_configs,
        mode="control", state_root=state_root).execution_adapters
    coordinator = ExperimentExecution(runs=runs, executions=executions,
        bridge=ExecutionBridge(executions, adapters=adapters),
        collection=ExecutionCollection(executions, plugin_configs={key: str(path) for key, path in plugin_configs.items()}),
        approval_base_url=approval_base_url)
    from ..worker_services import load_operation_services
    runs.experiment_executions = coordinator
    coordinator.services_for = lambda operation_id: load_operation_services(catalog, operation_id, plugin_configs, state_root)
    return coordinator
