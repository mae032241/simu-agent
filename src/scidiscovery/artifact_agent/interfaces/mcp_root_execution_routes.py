"""External-execution routes for the single Root scheduler facade."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import ValidationError

from ..schema.approval import (
    ApprovalOption,
    ApprovalRequest,
    CompiledApprovalIdentity,
    ReviewDocument,
)
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_sha256
from ...operations.invoke import (
    ApprovalProjectorContext,
    ApprovalSubjectSnapshot,
    BoundOperationCall,
    EffectExecutorPlan,
    OperationInvocationError,
    effect_operation_plan,
)
from .mcp_root_shared import (
    RootToolError,
    derived_name as _derived_name,
    operation_artifact_labels as _operation_artifact_labels,
)

class RootExecutionRoutes:
    def execution_capabilities(self, *, operation_id: str) -> dict[str, Any]:
        executor = self._effect_executor(operation_id)
        capabilities = self._execution_capabilities(executor)
        return {
            "operation_id": operation_id,
            "capabilities": [dict(item.public_summary) for item in capabilities],
        }

    def execution_capability_bind(
        self,
        *,
        name: str,
        operation_id: str,
        profile: str,
        on_conflict: str,
    ) -> dict[str, Any]:
        executor = self._effect_executor(operation_id)
        matches = tuple(
            item
            for item in self._execution_capabilities(executor)
            if item.key == profile
        )
        if len(matches) != 1:
            raise RootToolError(
                "selected execution capability is not currently advertised"
            )
        capability = matches[0]
        fingerprint = canonical_sha256(
            {
                "operation": "execution_capability_bind",
                "operation_id": operation_id,
                "profile": profile,
                "schema": capability.schema_id,
                "payload_sha256": hashlib.sha256(capability.content).hexdigest(),
            }
        )
        with self._create_lock:
            target = self._creation_target(
                "artifact", name, fingerprint, on_conflict
            )
            if target.existing_object_id is None:
                envelope = self.artifacts.register(
                    capability.content,
                    ArtifactRegistration(
                        kind=capability.kind,
                        schema_id=capability.schema_id,
                        payload_schema_version=capability.payload_schema_version,
                        media_type=capability.media_type,
                        creator=self.intake.creator,
                        labels={
                            "execution_operation": operation_id,
                            "capability_profile": profile,
                            "source": "active_adapter",
                        },
                        confidentiality="run_private",
                    ),
                    idempotency_key=(
                        "execution-capability:"
                        + canonical_sha256(
                            {
                                "instance": self._instance_id(),
                                "name": target.name,
                                "fingerprint": fingerprint,
                            }
                        )
                    ),
                )
                binding = self._bind_target(
                    "artifact", target, envelope.artifact_id, fingerprint
                )
            else:
                binding = self._binding("artifact", target.name)
        return {
            **self._binding_value(binding),
            "operation_id": operation_id,
            "profile": profile,
            "schema": capability.schema_id,
            "state": "bound",
        }

    def _invoke_compiled_effect(
        self,
        bound: BoundOperationCall,
        plan: EffectExecutorPlan,
        on_conflict: str,
    ) -> dict[str, Any]:
        name = bound.name
        executor = plan.executor
        preparation_profile = plan.preparation_profile
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        with self._create_lock:
            identity = bound.compiled.approval_identity
            if identity is None:
                raise RootToolError(
                    "compiled external operation has no approval identity"
                )
            compiled_identity = CompiledApprovalIdentity(
                operation_id=identity.operation_id,
                operation_version=identity.version,
                operation_digest=identity.operation_digest,
                approval_contract_digest=identity.approval_contract_digest,
            )
            payloads = tuple(
                item for item in bound.inputs if item.port_name == plan.payload_port
            )
            if len(payloads) != 1 or len(bound.inputs) != 1:
                raise RootToolError("compiled Effect payload is ambiguous")
            payload_ref = payloads[0].artifact.ref
            self.execution_bridge.validate_request(
                executor=executor,
                preparation_profile=preparation_profile,
                payload=self.artifacts.read(payload_ref),
            )
            fingerprint = canonical_sha256(
                {
                    "operation": bound.compiled.spec.operation_id,
                    "operation_version": bound.compiled.spec.version,
                    "operation_digest": bound.compiled.digest,
                    "approval_contract_digest": (
                        compiled_identity.approval_contract_digest
                        if compiled_identity is not None
                        else None
                    ),
                    "executor": executor,
                    "preparation_profile": preparation_profile,
                    "payload_ref": payload_ref,
                }
            )
            target = self._creation_target(
                "execution", name, fingerprint, on_conflict
            )
            if target.existing_object_id is None:
                execution_id = "exe_" + canonical_sha256(
                    {
                        "instance": self._instance_id(),
                        "name": target.name,
                        "request_fingerprint": fingerprint,
                    }
                )
                execution_id = self.executions.create(
                    executor=executor,
                    preparation_profile=preparation_profile,
                    payload_ref=payload_ref,
                    compiled_identity=compiled_identity,
                    labels=_operation_artifact_labels(bound),
                    execution_id=execution_id,
                )
                self._bind_target("execution", target, execution_id, fingerprint)
            approval = self._ensure_execution_approval(name=target.name)
            status = self.execution_status(name=target.name)
        return {**status, "approval": approval}

    def _execution_capabilities(self, executor: str) -> tuple[Any, ...]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        try:
            return self.execution_bridge.capabilities(executor=executor)
        except Exception as error:
            raise RootToolError("execution capability discovery failed") from error

    def _effect_executor(self, operation_id: str) -> str:
        try:
            compiled = self._operation_catalog.operation(operation_id)
            return effect_operation_plan(compiled).executor
        except (KeyError, OperationInvocationError) as error:
            raise RootToolError(
                "execution capability operation is not a compiled Effect"
            ) from error

    def _ensure_execution_approval(self, *, name: str) -> dict[str, Any]:
        execution_id = self._resolve("execution", name)
        approval_name = _derived_name(name, "approval")
        request_ref, payload_ref = self.executions.approval_subject_refs(
            execution_id
        )
        (
            subject_refs,
            question,
            options,
            review_document,
            compiled_identity,
        ) = self._compiled_execution_approval(
            execution_id=execution_id,
            request_ref=request_ref,
            payload_ref=payload_ref,
        )
        with self._create_lock:
            existing = self._optional("approval", approval_name)
            if existing is not None:
                status = self.approvals.status(existing)
                try:
                    stored_request = ApprovalRequest.model_validate_json(
                        self.artifacts.read(status.approval_request_ref), strict=True
                    )
                except ValidationError as error:
                    raise RootToolError(
                        "stored execution approval request is invalid"
                    ) from error
                if (
                    stored_request.kind != "execution_authorization"
                    or stored_request.subject_refs != subject_refs
                    or stored_request.question != question
                    or stored_request.options != options
                    or stored_request.compiled_identity != compiled_identity
                    or stored_request.review_document != review_document
                ):
                    raise RootToolError(
                        "stored execution approval differs from the compiled contract"
                    )
                return self.approval_status(name=approval_name)
            approval_id = f"apr_{execution_id}"
            self.approvals.create_request(
                approval_id=approval_id,
                kind="execution_authorization",
                subject_refs=subject_refs,
                question=question,
                options=options,
                requested_by=self.intake.creator,
                idempotency_key=f"execution-approval:{execution_id}",
                review_document=review_document,
                compiled_identity=compiled_identity,
            )
            fingerprint = canonical_sha256(
                {
                    "operation": "compiled_effect_approval",
                    "execution_name": name,
                    "subject_refs": subject_refs,
                    "compiled_identity": compiled_identity,
                    "review_document": review_document,
                }
            )
            self._bind(
                "approval",
                approval_name,
                approval_id,
                request_fingerprint=fingerprint,
            )
        return self.approval_status(name=approval_name)

    def _current_execution_contract(
        self,
        *,
        execution_id: str,
        request_ref: Any,
    ) -> tuple[Any, CompiledApprovalIdentity]:
        request = self.executions.request(execution_id)
        identity = request.compiled_identity
        if identity is None:
            raise RootToolError(
                "execution request has no compiled approval identity"
            )
        try:
            compiled = self._operation_catalog.operation(identity.operation_id)
        except KeyError as error:
            raise RootToolError(
                "execution request operation is not installed"
            ) from error
        current = compiled.approval_identity
        if compiled.spec.executor.kind != "effect" or current is None:
            raise RootToolError(
                "execution request operation has no compiled external approval"
            )
        compiled_identity = CompiledApprovalIdentity(
            operation_id=current.operation_id,
            operation_version=current.version,
            operation_digest=current.operation_digest,
            approval_contract_digest=current.approval_contract_digest,
        )
        if identity != compiled_identity:
            raise RootToolError("execution request operation contract changed")
        try:
            plan = effect_operation_plan(compiled)
        except OperationInvocationError as error:
            raise RootToolError(
                "execution request operation is not a compiled Effect"
            ) from error
        if (
            request.executor != plan.executor
            or request.preparation_profile != plan.preparation_profile
        ):
            raise RootToolError(
                "execution request adapter contract differs from compiled Effect"
            )
        request_envelope = self.artifacts.verify(request_ref)
        expected_labels = {
            "operation_id": compiled_identity.operation_id,
            "operation_version": compiled_identity.operation_version,
            "operation_digest": compiled_identity.operation_digest,
            "approval_contract_digest": (
                compiled_identity.approval_contract_digest
            ),
        }
        if any(
            request_envelope.labels.get(key) != value
            for key, value in expected_labels.items()
        ):
            raise RootToolError(
                "execution request labels differ from compiled identity"
            )
        return compiled, compiled_identity

    def _compiled_execution_approval(
        self,
        *,
        execution_id: str,
        request_ref: Any,
        payload_ref: Any,
    ) -> tuple[
        tuple[Any, ...],
        str,
        tuple[ApprovalOption, ...],
        ReviewDocument,
        CompiledApprovalIdentity,
    ]:
        compiled, compiled_identity = self._current_execution_contract(
            execution_id=execution_id,
            request_ref=request_ref,
        )
        review = compiled.spec.review
        contract = review.approval if review is not None else None
        if contract is None or contract.projector is None:
            raise RootToolError("external operation has no compiled approval contract")
        if contract.kind != "execution_authorization":
            raise RootToolError("external operation has the wrong approval kind")
        if len(compiled.spec.inputs) != 1 or len(compiled.spec.outputs) != 1:
            raise RootToolError("external operation approval subjects are ambiguous")
        refs_by_port = {
            compiled.spec.outputs[0].name: request_ref,
            compiled.spec.inputs[0].name: payload_ref,
        }
        try:
            subject_refs = tuple(refs_by_port[name] for name in contract.subject_ports)
        except KeyError as error:
            raise RootToolError(
                "external operation approval subjects are ambiguous"
            ) from error
        snapshots: list[ApprovalSubjectSnapshot] = []
        for subject_index, (port_name, ref) in enumerate(
            zip(contract.subject_ports, subject_refs, strict=True)
        ):
            envelope = self.artifacts.verify(ref)
            signal = self._scheduler_signal_for_output(ref)
            snapshots.append(
                ApprovalSubjectSnapshot(
                    subject_index=subject_index,
                    port_name=port_name,
                    item_index=0,
                    ref=ref,
                    schema_id=envelope.schema_id,
                    media_type=envelope.media_type,
                    size_bytes=envelope.size_bytes,
                    parent_refs=envelope.parent_refs,
                    labels=tuple(sorted(envelope.labels.items())),
                    handoff_verdict=(signal.verdict if signal is not None else None),
                    content=self.artifacts.read(ref),
                )
            )
        projector_key = (
            f"{contract.projector.plugin_id or compiled.plugin_id}:"
            f"{contract.projector.component_id}"
        )
        context = ApprovalProjectorContext(
            operation_id=compiled.spec.operation_id,
            operation_version=compiled.spec.version,
            operation_digest=compiled.digest,
            subjects=tuple(snapshots),
        )
        try:
            review_document = compiled.implementations[projector_key](context)
        except Exception as error:
            raise RootToolError("compiled execution approval projector failed") from error
        if not isinstance(review_document, ReviewDocument):
            raise RootToolError(
                "compiled execution approval projector returned an invalid document"
            )
        option_ids = {
            "accept": "authorize_execution",
            "accept_with_exception": "authorize_execution_with_exception",
            "reject": "reject_execution",
            "revise": "revise_execution",
        }
        options = tuple(
            ApprovalOption(
                option_id=option_ids[item.decision],
                label=item.label,
                description="按已编译的操作审批契约记录这一选择。",
                requires_rationale=item.requires_reason,
            )
            for item in contract.options
        )
        if len({item.option_id for item in options}) != len(options):
            raise RootToolError("compiled approval decisions are ambiguous")
        return (
            subject_refs,
            contract.question,
            options,
            review_document,
            compiled_identity,
        )

    def execution_abandon(self, *, name: str) -> dict[str, Any]:
        self.executions.abandon(self._resolve("execution", name))
        return self.execution_status(name=name)

    def execution_cancel(self, *, name: str) -> dict[str, Any]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        self.execution_bridge.cancel(execution_id=self._resolve("execution", name))
        return self.execution_status(name=name)

    def execution_status(self, *, name: str) -> dict[str, Any]:
        binding = self._binding("execution", name)
        status = self.executions.status(binding.object_id)
        result_artifact_name = None
        if status.result_ref is not None:
            candidate = _derived_name(name, "result")
            existing = self._optional("artifact", candidate)
            if existing is not None:
                if existing != status.result_ref.artifact_id:
                    raise RootToolError(
                        "execution result name is bound to a different Artifact"
                    )
                result_artifact_name = candidate
        return {
            **self._binding_value(binding),
            "executor": status.executor,
            "state": status.state,
            "result_artifact_name": result_artifact_name,
            "created_at": status.created_at,
            **self.executions.observation(binding.object_id),
            **({"collection": self.execution_collection.summary(binding.object_id)}
               if self.execution_collection is not None else {}),
        }

    def execution_collect(self, *, name: str, total_seconds: float) -> dict:
        execution_id = self._resolve("execution", name)
        if self.execution_collection is None:
            raise RootToolError("execution collection requires the configured control-service coordinator")
        result = self.execution_collection.collect(execution_id,
            scope="instance:" + self._instance_id(), total_seconds=total_seconds)
        return {"execution_name": name, "collection": result}

    def execution_list(self, *, state: str | None, limit: int) -> dict[str, Any]:
        items = []
        for binding in self.bindings.list(instance=self._instance_id(), namespace="execution"):
            item = self.execution_status(name=binding.name)
            if state is not None and item["state"] != state:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {"executions": items}

    def execution_outputs(self, *, name: str) -> dict[str, Any]:
        execution_id = self._resolve("execution", name)
        self._publish_execution_result(name=name)
        outputs = []
        for value in self.executions.outputs(execution_id):
            output_name = _derived_name(name, "output", value.logical_name)
            self._bind("artifact", output_name, value.artifact_id)
            outputs.append(
                {
                    "output_label": value.logical_name,
                    "artifact_name": output_name,
                    "media_type": value.media_type,
                    "size_bytes": value.size_bytes,
                }
            )
        return {"execution_name": name, "outputs": outputs}

    def execution_start(self, *, name: str) -> dict[str, Any]:
        self._require_scheduling_enabled()
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        execution_id = self._resolve("execution", name)
        approval_id = self._resolve("approval", _derived_name(name, "approval"))
        request_ref, _ = self.executions.approval_subject_refs(execution_id)
        _, compiled_identity = self._current_execution_contract(
            execution_id=execution_id,
            request_ref=request_ref,
        )
        self.execution_bridge.start(
            execution_id=execution_id,
            approval_id=approval_id,
            compiled_identity=compiled_identity,
        )
        return self.execution_status(name=name)

    def execution_sync(self, *, name: str) -> dict[str, Any]:
        if self.execution_bridge is None:
            raise RootToolError("no execution bridge is configured")
        execution_id = self._resolve("execution", name)
        progress = self.execution_bridge.sync(execution_id=execution_id,
            diagnostic_scope="instance:" + self._instance_id())
        self._publish_execution_result(name=name)
        result = self.execution_status(name=name)
        if progress is not None:
            result["progress"] = progress
        return result

    def _publish_execution_result(self, *, name: str) -> str | None:
        status = self.executions.status(self._resolve("execution", name))
        if status.result_ref is None:
            return None
        result_name = _derived_name(name, "result")
        self._bind("artifact", result_name, status.result_ref.artifact_id)
        return result_name



__all__ = ["RootExecutionRoutes"]
