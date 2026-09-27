"""Control-owned execution commands scoped to one running experiment."""
from __future__ import annotations

import hashlib

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
        self.services_for = None
        self.worker_services = {}

    def task_origin(self, run):
        return self.task_lineage(run)[-1].run_id

    def task_lineage(self, run):
        return self.runs.task_lineage(run.run_id)

    def cancel_owned(self, run):
        if self.runs.compiled_operation(run).spec.executor.capability is None:
            return
        self._domain_active(run, cancel=True)
        origin = self.task_origin(run)
        for binding in self.runs.scheduler_bindings.list(instance=run.instance_id, namespace="execution",
                name_prefix="experiment-" + origin + "-"):
            if self._execution_owner(binding.object_id) == origin:
                self._cancel(binding.object_id)

    def _domain_active(self, run, *, cancel=False):
        if self.services_for is not None:
            self.worker_services.update(self.services_for(run.operation_id))
        lineage = {item.run_id for item in self.task_lineage(run)}
        return any([service.experiment_activity(lineage, run.inputs, cancel=cancel)
            for service in self.worker_services.values()
            if callable(getattr(service, "experiment_activity", None))])

    def require_idle(self, run):
        from .run_outputs import RunOutputError
        origin = self.task_origin(run)
        active = self._domain_active(run)
        for binding in self.runs.scheduler_bindings.list(instance=run.instance_id, namespace="execution",
                name_prefix="experiment-" + origin + "-"):
            if self._execution_owner(binding.object_id) != origin:
                continue
            if self.executions.status(binding.object_id).state not in {"succeeded", "failed", "cancelled", "collected", "abandoned"}:
                active = True
        if active:
            raise RunOutputError("Finish or cancel this experiment's outstanding execution and diagnostics before final delivery.",
                details=({"path":"$.payload", "message":"Outstanding work has not reached a real terminal state.",
                    "type":"value_error", "rule_id":"experiment.sealed_material"},))

    def _execution_owner(self, execution_id):
        envelope = self.executions.artifacts.get_by_id(self.executions.request_artifact_id(execution_id))
        return envelope.labels.get("experiment_run")

    def implementation(self, context, alias):
        from ..schema.refs import ArtifactRef
        from .sealed_materials import material_error
        record = self.runs.sealed_material_record(self.runs.status(context.run_id), alias)
        if record is None or record.get("metadata", {}).get("kind") != "experiment_implementation":
            raise material_error("experiment_implementation_unavailable",
                "Choose a sealed implementation created in or explicitly bound to this task.")
        material = ArtifactRef.model_validate(record["artifact_ref"])
        packages = [ref for ref in self.executions.artifacts.verify(material).parent_refs
            if self.executions.artifacts.verify(ref).kind == "experiment_execution_package"]
        if len(packages) != 1:
            raise material_error("experiment_implementation_package_invalid",
                "The sealed implementation has no unique controlled execution package.")
        return packages[0]

    def _contract(self, context):
        run = self.runs.running_task(context.run_id)
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
        return context.accept_evidence(raw=scientific_material, media_type="application/json",
            derived_from=sources, trusted_parent_refs=(private,), metadata={"kind": "experiment_implementation", "private_outputs":list(private_outputs)})

    def _implementation_record(self, context, payload_ref):
        records = [item for item in self.runs.available_material_records(self.runs.status(context.run_id))
            if item.get("metadata", {}).get("kind") == "experiment_implementation"
            and self.implementation(context, item["alias"]) == payload_ref]
        if not records:
            from .sealed_materials import material_error
            raise material_error("experiment_implementation_unavailable",
                "Bind the exact sealed implementation used by this execution.")
        if len({canonical_json(item["artifact_ref"]) for item in records}) != 1:
            raise ValueError("Execution has conflicting implementation receipts.")
        return records[0]

    def _cancel(self, execution_id):
        status = self.executions.status(execution_id)
        if status.state in {"created", "authorized"}:
            prepared = self.executions.prepared_submission(execution_id)
            found = None if prepared is None else self.bridge._adapter(status.executor).lookup_submission(prepared)
            if found is None:
                self.executions.abandon(execution_id)
                return
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
            raise ValueError("The collected output exceeds this workspace's file limit.")
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

    def command(self, context, request):
        run, effect, identity, _ = self._contract(context)
        plan = effect_operation_plan(effect)
        if request.action == "capabilities":
            return {"methods": [{"method": item.key,
                **{k: v for k, v in item.public_summary.items()
                   if k in {"solver_kind", "release", "description", "limitations", "capabilities"}}}
                for item in self.capabilities(context)]}
        execution_id = "exe_" + hashlib.sha256(canonical_json({
            "task": self.task_origin(run), "name": request.name})).hexdigest()
        if request.action == "start":
            if request.implementation is None:
                raise ValueError("Choose a sealed implementation before starting execution.")
            payload = self.implementation(context, request.implementation)
            self.executions.create(executor=plan.executor, preparation_profile=plan.preparation_profile,
                payload_ref=payload, execution_id=execution_id, compiled_identity=identity,
                labels={"operation_id": identity.operation_id, "operation_version": identity.operation_version,
                    "operation_digest": identity.operation_digest, "approval_contract_digest": identity.approval_contract_digest,
                    "experiment_run": self.task_origin(run)})
            self.runs.scheduler_bindings.bind(instance=run.instance_id, namespace="execution",
                name="experiment-" + self.task_origin(run) + "-" + request.name, object_id=execution_id)
        current = self.executions.request(execution_id)
        if current.compiled_identity != identity:
            raise ValueError("Execution configuration changed; the existing execution cannot be restarted.")
        implementation = self._implementation_record(context, current.payload_ref)
        private_outputs = implementation["metadata"].get("private_outputs", ())
        if request.action in {"read", "export"}:
            outputs = [item for item in self.executions.outputs(execution_id) if item.logical_name not in private_outputs]
            item = next((item for item in outputs if item.logical_name == request.output_name), None)
            if item is None:
                raise ValueError("Select one collected output by its scientific name.")
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
        if request.action in {"start", "advance", "status"}:
            approval = self._approval_status(execution_id)
            if approval is not None:
                if request.action != "status":
                    self._bind_approval(run, request.name, execution_id)
                response = self._authorization_response(run, request.name, execution_id, approval)
                if self.executions.status(execution_id).state == "created" and (
                        request.action == "status" or response["state"] not in {"created", "awaiting_authorization"}):
                    return response
        if request.action in {"start", "advance"}:
            try:
                self.bridge.start(execution_id=execution_id,
                    approval_id="apr_" + execution_id if approval is not None and approval.status == "decided" else None,
                    compiled_identity=identity,
                    allow_policy_authorization=effect.spec.review.approval.allow_policy_authorization,
                    budget_subject_schemas=("scidiscovery.research-objective.v1",))
            except ExecutionAuthorizationRequired:
                self._approval(execution_id, effect, identity)
                self._bind_approval(run, request.name, execution_id)
                return self._authorization_response(run, request.name, execution_id, self._approval_status(execution_id))
            self.bridge.sync(execution_id=execution_id, diagnostic_scope="instance:" + run.instance_id)
        elif request.action == "cancel":
            self._cancel(execution_id)
        elif request.action == "collect":
            if self.collection is None:
                raise ValueError("The controlled collection service is unavailable.")
            self.collection.collect(execution_id, scope="instance:" + run.instance_id,
                total_seconds=min(context.remaining_seconds, self._io_settings(context).collection_timeout_seconds),
                file_timeout_seconds=self._io_settings(context).file_timeout_seconds,
                idle_timeout_seconds=self._io_settings(context).idle_timeout_seconds)
        status = self.executions.status(execution_id)
        result = {"name": request.name, "state": status.state}
        if status.result_ref is not None:
            manifest = ExecutionResultManifest.model_validate_json(self.executions.artifacts.read(status.result_ref), strict=True)
            result["terminal_state"] = manifest.terminal_state
            result["outputs"] = [{"name": item.logical_name, "media_type": item.media_type,
                "size_bytes": item.size_bytes} for item in self.executions.outputs(execution_id)
                if item.logical_name not in private_outputs]
            # A control observation is sealed without exposing control identities.
            if request.action != "status":
                record = context.accept_evidence(raw=canonical_json(result), media_type="application/json",
                    derived_from=("research_objective", implementation["alias"]), trusted_parent_refs=(status.result_ref,),
                    metadata={"kind": "experiment_execution", "name": request.name, "implementation": implementation["alias"]})
                result["reference"] = record["alias"]
        return result

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
        state = {"pending": "awaiting_authorization", "expired": "authorization_expired",
            "cancelled_by_human": "authorization_cancelled"}.get(approval.status, "created")
        if approval.status == "decided":
            stored = ApprovalRequest.model_validate_json(self.executions.artifacts.read(approval.approval_request_ref), strict=True)
            decision = HumanDecision.model_validate_json(self.executions.artifacts.read(approval.decision_ref), strict=True)
            if not execution_decision_authorizes(stored, decision):
                state = "authorization_rejected"
        authorization = self.executions.authorization(execution_id)
        result = {"name": name, "state": state, "authorization": {"status": approval.status,
            **{key: authorization[key] for key in ("reason", "budget", "allowance") if key in authorization}}}
        bound = self.runs.scheduler_bindings.find_name(instance=run.instance_id, namespace="approval", object_id="apr_" + execution_id)
        if bound is not None:
            result["approval_name"] = bound
        if approval.status == "pending" and approval.review_path and self.approval_base_url:
            result["review_url"] = self.approval_base_url.rstrip("/") + approval.review_path
        return result

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
        lineage = {item.run_id for item in self.__coordinator.task_lineage(run)}
        return bool(service.experiment_activity(lineage, run.inputs, cancel=True, name=name))

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
