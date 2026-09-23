"""Compiled Operation routing for the single Root scheduler facade."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any, Protocol

from ..schema.approval import ApprovalOption, CompiledApprovalIdentity, ReviewDocument
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_sha256
from ..service.scheduler_bindings import SchedulerNameConflict
from ..service.run_records import RunAttemptLimit
from ...operation_contract import contract_diagnostic
from ...operations.invoke import (
    ApprovalProjectorContext,
    ApprovalSubjectSnapshot,
    BoundOperationCall,
    EffectExecutorPlan,
    InvocationArtifact,
    OperationInvocationError,
    OperationEngineeringError,
    ProducerEvidenceSource,
    ProducerFamilyMember,
    ProducerInputProjection,
    ProducerOutputFamily,
    active_direct_revision_ports,
    direct_revision_ports,
    effect_executor_plan,
    effect_operation_plan,
    execute_compiled_transform,
    preflight_operation,
    preflight_result,
)
from ...operations.tooling import (
    operation_local_worker_missing_tools,
    operation_worker_tools,
)
from ...operations.review_admission import review_input_mode
from .mcp_root_shared import (
    APPROVAL_OPTION_IDS as _APPROVAL_OPTION_IDS,
    NONQUALIFYING_HANDOFF_VERDICTS as _NONQUALIFYING_HANDOFF_VERDICTS,
    CreationTarget as _CreationTarget,
    RootToolError,
    claim_admissible as _claim_admissible,
    derived_name as _derived_name,
    operation_artifact_labels as _operation_artifact_labels,
)


_NONPASSING_REVIEW_VERDICTS = ("revise", "blocked", "inconclusive")


class _OperationInputSelection(Protocol):
    """Structural input required by routing, independent of MCP decoding DTOs."""

    port: str
    artifact_names: tuple[str, ...]


def _attempt_limit_error(error: RunAttemptLimit) -> OperationInvocationError:
    result = OperationInvocationError("recovery_attempt_limit_reached", message=str(error))
    result.details = (contract_diagnostic(
        "recovery_attempt_limit_reached", phase="input_admission", affected_action="invoke",
        path="$.max_attempts", message=str(error), repairable=True),)
    return result


class RootOperationRoutes:
    def operation_catalog(self, *, scope: str) -> dict[str, Any]:
        projection = self._operation_catalog.scheduler_projection()
        items = [
            self._operation_catalog_item(item)
            for item in projection
            if scope == "all" or item.catalog_scope == scope
        ]
        if scope == "public":
            items = [
                item
                for item in items
                if self._scheduler_operation_available(item["operation_id"])
            ]
        return {
            "scope": scope,
            "operations": items,
        }

    def _operation_catalog_item(self, item: Any) -> dict[str, Any]:
        value = item.model_dump(mode="json", by_alias=True)
        compiled = self._operation_catalog.operation(item.operation_id)
        value["operation_digest"] = compiled.digest
        if compiled.spec.executor.kind == "effect":
            try:
                plan = effect_operation_plan(compiled)
            except OperationInvocationError:
                value["runtime_binding"] = {
                    "process": "control",
                    "required": [],
                    "status": "invalid_declaration",
                }
                return value
            available = bool(
                self.execution_bridge is not None
                and self.execution_bridge.has_adapter(plan.executor)
            )
            value["runtime_binding"] = {
                "process": "control",
                "required": [plan.executor],
                "status": "available" if available else "unavailable",
            }
        elif compiled.spec.executor.kind == "agent":
            value["executor_model_usage"] = "Operation compatibility default; dispatch uses the Run execution_profile."
            value["default_max_attempts"] = compiled.spec.limits.max_attempts
            if self.runs is not None:
                if not self.runs.backend.supports_operation(compiled):
                    value["runtime_binding"] = {
                        "process": "worker",
                        "required": list(
                            self.runs.backend.unsupported_requirements(compiled)
                        ),
                        "status": "unavailable",
                    }
                    return value
                missing = operation_local_worker_missing_tools(compiled)
                if missing:
                    value["runtime_binding"] = {
                        "process": "local_worker",
                        "required": list(missing),
                        "status": "unavailable",
                    }
                    return value
            services = sorted(
                {
                    service
                    for tool in operation_worker_tools(compiled)
                    for service in tool.required_services
                }
            )
            if services:
                value["runtime_binding"] = {
                    "process": "worker",
                    "required": services,
                    "status": "verified_on_worker_claim",
                }
            optional = sorted({service for tool in operation_worker_tools(compiled) for service in tool.optional_services})
            if optional:
                value["optional_runtime_services"] = optional
        return value

    def _scheduler_operation_available(
        self, operation_id: str, seen: frozenset[str] = frozenset()
    ) -> bool:
        if operation_id in seen:
            return False
        try:
            compiled = self._operation_catalog.operation(operation_id)
        except KeyError:
            return False
        if compiled.spec.catalog_scope == "internal":
            return False
        if compiled.spec.executor.kind == "agent" and (
            self.runs is None
            or not self.runs.backend.supports_operation(compiled)
            or bool(operation_local_worker_missing_tools(compiled))
        ):
            return False
        if compiled.spec.executor.kind == "effect":
            try:
                plan = effect_operation_plan(compiled)
            except OperationInvocationError:
                return False
            if (
                self.execution_bridge is None
                or not self.execution_bridge.has_adapter(plan.executor)
            ):
                return False
        review = compiled.spec.review
        if (
            compiled.spec.catalog_scope == "public"
            and review is not None
            and review.reviewer_operation is not None
        ):
            return self._scheduler_operation_available(
                review.reviewer_operation, seen | {operation_id}
            )
        return True

    def _configured_operation_call(self, values):
        self._require_scheduling_enabled()
        values = dict(values)
        profile = values.pop("execution_profile", None)
        bound = self._prepare_operation_call(**values)
        if bound.compiled.spec.executor.kind != "agent":
            if profile is not None:
                raise OperationInvocationError("execution_profile_not_applicable",
                    message="execution_profile applies only to Agent Runs")
            return bound, values
        if self.runs is None:
            raise OperationInvocationError("runtime_backend_unavailable")
        source_name = values.get("resume_from") or values.get("draft_from")
        try:
            settings = self.runs.execution_settings(bound.compiled, instance_id=self._instance_id(),
                profile=profile, recovery_source=self._resolve("run", source_name) if source_name else None,
                max_attempts=values.get("max_attempts"))
        except ValueError as error:
            raise OperationInvocationError("execution_configuration_invalid", message=str(error)) from error
        if values.get("max_attempts") is None and source_name is None:
            values["max_attempts"] = settings["default_max_attempts"]
        bound = replace(bound, execution_profile={key: settings[key] for key in ("profile", "sources")})
        values["execution_profile"] = settings["profile"]
        return bound, values

    def operation_preflight(self, **values: Any) -> dict[str, Any]:
        normalized = {}
        def prepare() -> BoundOperationCall:
            bound, configured = self._configured_operation_call(values)
            normalized.update(configured)
            if bound.compiled.spec.executor.kind == "agent":
                self._prepare_local_run(
                    bound,
                    values["on_conflict"],
                    resume_from=values.get("resume_from"),
                    draft_from=values.get("draft_from"),
                    max_attempts=normalized.get("max_attempts"),
                )
            elif bound.compiled.spec.executor.kind == "approval":
                self._prepare_approval_projection(bound)
            return bound

        result = preflight_result(prepare)
        if result["admissible"] and result["executor_kind"] == "agent":
            result["normalized_request"] = {**normalized,
                "inputs": [{"port": item.port, "artifact_names": list(item.artifact_names)}
                           for item in normalized["inputs"]]}
        return result

    def operation_invoke(self, **values: Any) -> dict[str, Any]:
        with self._create_lock:
            try:
                bound, values = self._configured_operation_call(values)
                kind = bound.compiled.spec.executor.kind
                if kind == "agent":
                    result = self._invoke_agent_operation(
                        bound,
                        values["on_conflict"],
                        resume_from=values.get("resume_from"),
                        draft_from=values.get("draft_from"),
                        max_attempts=values.get("max_attempts"),
                    )
                elif kind == "transform":
                    result = self._invoke_compiled_transform(
                        bound, values["on_conflict"]
                    )
                elif kind == "effect":
                    plan = self._effect_operation_plan(bound)
                    payloads = tuple(
                        item for item in bound.inputs if item.port_name == plan.payload_port
                    )
                    if len(payloads) != 1 or len(bound.inputs) != 1:
                        raise OperationInvocationError("effect_payload_not_singular")
                    result = self._invoke_compiled_effect(
                        bound, plan, values["on_conflict"]
                    )
                elif kind == "approval":
                    result = self._invoke_approval_operation(
                        bound, values["on_conflict"]
                    )
                else:
                    raise OperationInvocationError("executor_kind_unknown")
            except OperationInvocationError as error:
                raise RootToolError(
                    f"operation invocation rejected [{error.reason_code}]", details=error.details
                ) from error
        return {
            "operation_id": bound.compiled.spec.operation_id,
            "executor_kind": bound.compiled.spec.executor.kind,
            "result": result,
        }

    def _invoke_agent_operation(
        self,
        bound: BoundOperationCall,
        on_conflict: str,
        *,
        resume_from: str | None = None,
        draft_from: str | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        if self.runs is None:
            raise OperationInvocationError("runtime_backend_unavailable")
        return self._invoke_local_run(
            bound, on_conflict, resume_from=resume_from, draft_from=draft_from, max_attempts=max_attempts
        )

    def _invoke_local_run(
        self,
        bound: BoundOperationCall,
        on_conflict: str,
        *,
        resume_from: str | None,
        draft_from: str | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        resume_run_id, draft_run_id, draft_digest, fingerprint, target = self._prepare_local_run(
            bound, on_conflict, resume_from=resume_from, draft_from=draft_from, max_attempts=max_attempts
        )
        if target.existing_object_id is not None:
            return self.run_status(name=target.name)
        output_name = _derived_name(target.name, "output")
        output_logical_name = _derived_name(target.logical_name, "output")
        output_fingerprint = canonical_sha256(
            {"run_request": fingerprint, "output": "primary"}
        )
        try:
            run_id = self.runs.schedule(
                bound,
                instance_id=self._instance_id(),
                output_binding_name=output_name,
                output_logical_name=output_logical_name,
                output_revision=target.revision,
                output_binding_fingerprint=output_fingerprint,
                resume_from=resume_run_id,
                draft_from=draft_run_id,
                draft_digest=draft_digest,
                max_attempts=max_attempts,
            )
        except RunAttemptLimit as error:
            raise _attempt_limit_error(error) from error
        except Exception as error:
            raise OperationEngineeringError("local_run_creation_failed") from error
        self._bind_target("run", target, run_id, fingerprint)
        return self.run_status(name=target.name)

    def _prepare_local_run(
        self,
        bound: BoundOperationCall,
        on_conflict: str,
        *,
        resume_from: str | None,
        draft_from: str | None = None,
        max_attempts: int | None = None,
    ) -> tuple[str | None, str | None, str | None, str, _CreationTarget]:
        if self.runs is None:
            raise OperationInvocationError("runtime_backend_unavailable")
        resume_run_id = (
            None if resume_from is None else self._resolve("run", resume_from)
        )
        draft_run_id = None
        draft_digest = None
        if draft_from is not None:
            try:
                draft_run_id = self._resolve("run", draft_from)
                draft_digest = self.runs.validate_draft_source(
                    draft_run_id, compiled=bound.compiled,
                    instance_id=self._instance_id(), check_attempts=False,
                )
            except Exception as error:
                raise OperationInvocationError("draft_source_unavailable") from error
        fingerprint = canonical_sha256(
            {
                "operation": bound.compiled.spec.operation_id,
                "operation_version": bound.compiled.spec.version,
                "operation_digest": bound.compiled.digest,
                "execution_profile": bound.execution_profile["profile"],
                "instruction": bound.instruction,
                "inputs": [
                    {
                        "port": item.port_name,
                        "source": item.source_name,
                        "artifact_name": item.artifact_name,
                        "artifact_ref": item.artifact.ref,
                        "usage": item.usage,
                        "exposure": item.exposure,
                    }
                    for item in bound.inputs
                ],
                "resume_from": resume_run_id,
                **({"max_attempts": max_attempts} if max_attempts is not None else {}),
                **(
                    {"draft_from": draft_run_id, "draft_digest": draft_digest}
                    if draft_run_id is not None else {}
                ),
            }
        )
        try:
            target = self._creation_target(
                "run", bound.name, fingerprint, on_conflict
            )
        except SchedulerNameConflict as error:
            raise OperationInvocationError("semantic_name_conflict") from error
        if target.existing_object_id is None:
            try:
                if draft_run_id is not None:
                    self.runs.validate_draft_source(draft_run_id, compiled=bound.compiled,
                        instance_id=self._instance_id(), scheduler_max_attempts=max_attempts)
                if resume_run_id is not None:
                    self.runs.validate_resume(resume_run_id, operation_digest=bound.compiled.digest,
                        input_refs=tuple(item.artifact.ref for item in bound.inputs),
                        max_attempts=bound.compiled.spec.limits.max_attempts,
                        scheduler_max_attempts=max_attempts)
            except RunAttemptLimit as error:
                raise _attempt_limit_error(error) from error
            self._validate_revision_successor_slot(bound)
        return resume_run_id, draft_run_id, draft_digest, fingerprint, target

    def _validate_revision_successor_slot(self, bound: BoundOperationCall) -> None:
        review = bound.compiled.spec.review
        if review is None or review.max_revisions == 0:
            return
        if direct_revision_ports(bound.compiled) is None or self.runs is None:
            raise OperationInvocationError("revision_policy_unavailable")
        direct = active_direct_revision_ports(
            bound.compiled, (item.port_name for item in bound.inputs)
        )
        if direct is None:
            return
        base = next(
            item for item in bound.inputs if item.port_name == direct[0].name
        )
        if self.runs.revision_successor(
            instance_id=self._instance_id(),
            operation_digest=bound.compiled.digest,
            base_ref=base.artifact.ref,
        ) is not None:
            raise OperationInvocationError("revision_branch_forbidden")

    def _invoke_approval_operation(
        self, bound: BoundOperationCall, on_conflict: str
    ) -> dict[str, Any]:
        document, snapshots = self._prepare_approval_projection(bound)
        review = bound.compiled.spec.review
        contract = review.approval if review is not None else None
        identity = bound.compiled.approval_identity
        if contract is None or identity is None:
            raise OperationInvocationError("approval_contract_missing")
        subject_refs = tuple(item.ref for item in snapshots)
        options = tuple(
            ApprovalOption(
                option_id=_APPROVAL_OPTION_IDS[item.decision],
                label=item.label,
                description=item.description or item.label,
                requires_rationale=item.requires_reason,
            )
            for item in contract.options
        )
        compiled_identity = CompiledApprovalIdentity(
            operation_id=identity.operation_id,
            operation_version=identity.version,
            operation_digest=identity.operation_digest,
            approval_contract_digest=identity.approval_contract_digest,
        )
        fingerprint = canonical_sha256(
            {
                "operation": bound.compiled.spec.operation_id,
                "operation_version": bound.compiled.spec.version,
                "operation_digest": bound.compiled.digest,
                "approval_contract_digest": identity.approval_contract_digest,
                "kind": contract.kind,
                "subject_refs": subject_refs,
                "question": contract.question,
                "options": options,
                "review_document": document,
            }
        )
        target = self._creation_target(
            "approval", bound.name, fingerprint, on_conflict
        )
        if target.existing_object_id is not None:
            return self.approval_status(name=target.name)
        approval_id = f"apr_{uuid.uuid4().hex}"
        self.approvals.create_request(
            approval_id=approval_id,
            kind=contract.kind,
            subject_refs=subject_refs,
            question=contract.question,
            options=options,
            requested_by=self.intake.creator,
            idempotency_key=f"approval:{approval_id}",
            review_document=document,
            compiled_identity=compiled_identity,
        )
        self._bind_target("approval", target, approval_id, fingerprint)
        return self.approval_status(name=target.name)

    def _prepare_approval_projection(
        self, bound: BoundOperationCall
    ) -> tuple[ReviewDocument, tuple[ApprovalSubjectSnapshot, ...]]:
        """Read and project the exact approval subjects without changing state."""

        review = bound.compiled.spec.review
        contract = review.approval if review is not None else None
        identity = bound.compiled.approval_identity
        if contract is None or contract.projector is None or identity is None:
            raise OperationInvocationError("approval_contract_missing")
        grouped = {
            port_name: tuple(
                item for item in bound.inputs if item.port_name == port_name
            )
            for port_name in contract.subject_ports
        }
        port_specs = {port.name: port for port in bound.compiled.spec.inputs}
        if any(
            not values and port_specs[port_name].min_items > 0
            for port_name, values in grouped.items()
        ):
            raise OperationInvocationError("approval_subject_missing")
        snapshots: list[ApprovalSubjectSnapshot] = []
        for port_name in contract.subject_ports:
            for item_index, item in enumerate(grouped[port_name]):
                snapshots.append(
                    ApprovalSubjectSnapshot(
                        subject_index=len(snapshots),
                        port_name=port_name,
                        item_index=item_index,
                        ref=item.artifact.ref,
                        schema_id=item.artifact.schema_id,
                        media_type=item.artifact.media_type,
                        size_bytes=item.artifact.size_bytes,
                        parent_refs=item.artifact.parent_refs,
                        labels=item.artifact.labels,
                        handoff_verdict=(
                            signal.verdict if (signal := self._scheduler_signal_for_output(
                                item.artifact.ref
                            )) is not None else None
                        ),
                        content=self.artifacts.read(item.artifact.ref),
                    )
                )
        context = ApprovalProjectorContext(
            operation_id=bound.compiled.spec.operation_id,
            operation_version=bound.compiled.spec.version,
            operation_digest=bound.compiled.digest,
            subjects=tuple(snapshots),
            producer_families=self._approval_producer_families(bound),
        )
        projector_key = (
            f"{contract.projector.plugin_id or bound.compiled.plugin_id}:"
            f"{contract.projector.component_id}"
        )
        try:
            document = bound.compiled.implementations[projector_key](context)
        except OperationInvocationError:
            raise
        except Exception as error:
            raise OperationEngineeringError("approval_projector_failed") from error
        if not isinstance(document, ReviewDocument):
            raise OperationEngineeringError("approval_projector_result_invalid")
        return document, tuple(snapshots)

    def _producer_output_family(
        self, item: Any
    ) -> ProducerOutputFamily | None:
        return self._producer_output_family_from_envelope(
            item.artifact_name,
            self.artifacts.catalog(item.artifact.ref),
        )

    def _approval_producer_families(
        self, bound: BoundOperationCall
    ) -> tuple[ProducerOutputFamily, ...]:
        """Resolve and de-duplicate complete producer families for all subjects."""

        by_identity: dict[str, ProducerOutputFamily] = {}
        by_members: dict[tuple[tuple[str, str | None, str], ...], ProducerOutputFamily] = {}
        for item in bound.inputs:
            family = self._producer_output_family(item)
            if family is None:
                continue
            if family.family_identity is None:
                raise OperationInvocationError("producer_family_identity_missing")
            prior = by_identity.get(family.family_identity)
            if prior is not None and prior != family:
                raise OperationInvocationError("producer_family_inconsistent")
            by_identity[family.family_identity] = family
            member_key = tuple(
                sorted(
                    (
                        member.port_name,
                        member.item_name,
                        member.ref.canonical_json(),
                    )
                    for member in family.members
                )
            )
            existing = by_members.get(member_key)
            if existing is not None:
                if existing != family:
                    raise OperationInvocationError("producer_family_inconsistent")
                continue
            by_members[member_key] = family
        return tuple(by_members.values())

    def _producer_output_family_from_envelope(
        self,
        artifact_name: str,
        envelope: Any,
    ) -> ProducerOutputFamily | None:
        run_family = self._run_output_family(envelope)
        if run_family is not None:
            return run_family
        return self._transform_output_family(artifact_name, envelope)

    def _run_output_family(self, envelope: Any) -> ProducerOutputFamily | None:
        if self.runs is None:
            return None
        status = self.runs.completed_for_output(envelope.ref)
        if status is None or status.output_ref is None:
            return None
        is_primary_output = status.output_ref == envelope.ref
        if not is_primary_output and not any(
            ref == envelope.ref for _, ref in self.runs.evidence_output_refs(status)
        ):
            return None
        if any(envelope.labels.get(key) != expected for key, expected in (
            ("operation_id", status.operation_id),
            ("operation_version", status.operation_version),
            ("operation_digest", status.operation_digest),
        )):
            raise OperationInvocationError("producer_family_inconsistent")
        port_name = envelope.labels.get("operation_output_port")
        counts: dict[str, int] = {}
        producer_inputs = []
        for item in status.inputs:
            counts[item.port_name] = counts.get(item.port_name, 0) + 1
            producer_inputs.append(
                ProducerInputProjection(
                    port_name=item.port_name,
                    item_index=counts[item.port_name],
                    ref=item.artifact_ref,
                    artifact_name=item.artifact_name,
                    source_name=item.source_name,
                )
            )
        sources = tuple(
            ProducerEvidenceSource(
                source_kind="run_input",
                source_name=value.source_name,
                ref=value.artifact_ref,
            )
            for value in status.inputs
            if value.usage
            in {"claim_evidence", "evidence_inventory", "cached_excerpt"}
        )
        family_identity = canonical_sha256(
            {
                "producer": "run",
                "operation": status.operation_id,
                "operation_version": status.operation_version,
                "operation_digest": status.operation_digest,
                "run_id": status.run_id,
                "primary_ref": status.output_ref,
            }
        )
        try:
            producer = self._operation_catalog.operation(status.operation_id)
        except KeyError:
            producer = None
        if (
            producer is None
            or producer.spec.version != status.operation_version
            or producer.digest != status.operation_digest
        ):
            return ProducerOutputFamily(
                primary_ref=status.output_ref,
                operation_id=status.operation_id,
                operation_version=status.operation_version,
                operation_digest=status.operation_digest,
                producer_kind="run",
                producer_instance_id=status.instance_id,
                producer_run_id=status.run_id,
                contract_availability="historical",
                unavailable_reason="producer_contract_unavailable",
                members=(
                    ProducerFamilyMember(port_name=port_name, item_name=None, ref=envelope.ref),
                ) if isinstance(port_name, str) else (),
                evidence_sources=sources,
                producer_inputs=tuple(producer_inputs),
                family_identity=family_identity,
            )
        if producer.spec.executor.kind != "agent":
            return None
        selected_port = next(
            (
                port
                for port in producer.spec.outputs
                if port.name == port_name
                and ((port.collection is None) == is_primary_output)
            ),
            None,
        )
        if selected_port is None or not self._artifact_matches_output_port(
            envelope, selected_port
        ):
            return None
        return ProducerOutputFamily(
            primary_ref=status.output_ref,
            operation_id=producer.spec.operation_id,
            operation_version=status.operation_version,
            operation_digest=status.operation_digest,
            producer_kind="run",
            producer_instance_id=status.instance_id,
            producer_run_id=status.run_id,
            contract_availability="current",
            unavailable_reason=None,
            members=(
                ProducerFamilyMember(
                    port_name=selected_port.name,
                    item_name=None,
                    ref=envelope.ref,
                ),
            ),
            evidence_sources=sources,
            producer_inputs=tuple(producer_inputs),
            reviewer_operation=(
                producer.spec.review.reviewer_operation
                if producer.spec.review is not None
                else None
            ),
            review_subject_outputs=(
                producer.spec.review.subject_outputs
                if producer.spec.review is not None
                else ()
            ),
            family_identity=family_identity,
        )

    def _transform_output_family(
        self,
        artifact_name: str,
        envelope: Any,
    ) -> ProducerOutputFamily | None:
        labels = envelope.labels
        operation_id = labels.get("operation_id")
        operation_version = labels.get("operation_version")
        operation_digest = labels.get("operation_digest")
        invocation_fingerprint = labels.get("operation_invocation_fingerprint")
        if (
            not isinstance(operation_id, str)
            or not isinstance(operation_version, str)
            or not isinstance(operation_digest, str)
            or not isinstance(invocation_fingerprint, str)
            or labels.get("transform_profile") != operation_id
        ):
            return None
        family_identity = canonical_sha256(
            {
                "producer": "transform",
                "operation": operation_id,
                "operation_version": operation_version,
                "operation_digest": operation_digest,
                "invocation_fingerprint": invocation_fingerprint,
                "ordered_parents": envelope.parent_refs,
            }
        )

        instance_bindings = self.bindings.list(
            instance=self._instance_id(), namespace="artifact"
        )
        subject_bindings = tuple(
            binding
            for binding in instance_bindings
            if binding.object_id == envelope.artifact_id
        )
        if not any(
            binding.name == artifact_name
            and binding.request_fingerprint == invocation_fingerprint
            for binding in subject_bindings
        ):
            return None
        siblings: dict[str, Any] = {}
        for binding in instance_bindings:
            if binding.request_fingerprint != invocation_fingerprint:
                continue
            candidate = self.artifacts.get_by_id(binding.object_id)
            candidate_labels = candidate.labels
            if candidate.parent_refs != envelope.parent_refs or any(
                candidate_labels.get(key) != expected
                for key, expected in (
                    ("operation_id", operation_id),
                    ("operation_version", operation_version),
                    ("operation_digest", operation_digest),
                    ("transform_profile", operation_id),
                    ("operation_invocation_fingerprint", invocation_fingerprint),
                )
            ):
                raise OperationInvocationError("producer_family_inconsistent")
            output_label = candidate_labels.get("output_label")
            if not isinstance(output_label, str):
                raise OperationInvocationError("producer_family_inconsistent")
            existing = siblings.get(output_label)
            if existing is not None and existing.ref != candidate.ref:
                raise OperationInvocationError("producer_family_inconsistent")
            siblings[output_label] = candidate
        if "primary" not in siblings or envelope.ref not in {
            value.ref for value in siblings.values()
        }:
            return None

        def unavailable(reason: str) -> ProducerOutputFamily:
            return ProducerOutputFamily(
                primary_ref=siblings["primary"].ref,
                operation_id=operation_id,
                operation_version=operation_version,
                operation_digest=operation_digest,
                producer_kind="transform",
                producer_instance_id=self._instance_id(),
                producer_run_id=None,
                contract_availability="historical",
                unavailable_reason=reason,
                members=(),
                evidence_sources=(),
                producer_inputs=(),
                family_identity=family_identity,
            )
        try:
            compiled = self._operation_catalog.operation(operation_id)
        except KeyError:
            return unavailable("producer_contract_unavailable")
        if (
            compiled.spec.version != operation_version
            or compiled.digest != operation_digest
            or compiled.spec.executor.kind != "transform"
        ):
            return unavailable("producer_contract_unavailable")
        input_groups = self._transform_input_groups(compiled, envelope.parent_refs)
        if input_groups is None:
            return unavailable("producer_input_mapping_ambiguous")
        ordered_members = self._validated_transform_members(compiled, siblings)
        if ordered_members is None:
            return None
        return ProducerOutputFamily(
            primary_ref=siblings["primary"].ref,
            operation_id=operation_id,
            operation_version=operation_version,
            operation_digest=operation_digest,
            producer_kind="transform",
            producer_instance_id=self._instance_id(),
            producer_run_id=None,
            contract_availability="current",
            unavailable_reason=None,
            members=ordered_members,
            evidence_sources=(),
            producer_inputs=tuple(
                ProducerInputProjection(
                    port_name=port.name,
                    item_index=index,
                    ref=item.ref,
                )
                for port in compiled.spec.inputs
                for index, item in enumerate(input_groups[port.name], start=1)
            ),
            reviewer_operation=(
                compiled.spec.review.reviewer_operation
                if compiled.spec.review is not None
                else None
            ),
            review_subject_outputs=(
                compiled.spec.review.subject_outputs
                if compiled.spec.review is not None
                else ()
            ),
            family_identity=family_identity,
        )

    def _transform_input_groups(
        self, compiled: Any, parent_refs: tuple[Any, ...]
    ) -> dict[str, tuple[Any, ...]] | None:
        if len(parent_refs) != len(set(parent_refs)):
            return None
        envelopes = tuple(self.artifacts.verify(ref) for ref in parent_refs)
        ports = compiled.spec.inputs
        solutions: list[dict[str, tuple[Any, ...]]] = []

        def visit(port_index: int, offset: int, values: dict[str, tuple[Any, ...]]) -> None:
            if len(solutions) > 1:
                return
            if port_index == len(ports):
                if offset == len(envelopes):
                    solutions.append(dict(values))
                return
            port = ports[port_index]
            remaining_min = sum(item.min_items for item in ports[port_index + 1 :])
            remaining_max = sum(item.max_items for item in ports[port_index + 1 :])
            lower = max(port.min_items, len(envelopes) - offset - remaining_max)
            upper = min(port.max_items, len(envelopes) - offset - remaining_min)
            for count in range(lower, upper + 1):
                selected = envelopes[offset : offset + count]
                if not all(self._artifact_matches_input_port(item, port) for item in selected):
                    continue
                values[port.name] = selected
                visit(port_index + 1, offset + count, values)
            values.pop(port.name, None)

        visit(0, 0, {})
        return solutions[0] if len(solutions) == 1 else None

    def _validated_transform_members(
        self, compiled: Any, siblings: dict[str, Any]
    ) -> tuple[ProducerFamilyMember, ...] | None:
        by_port: dict[str, list[Any]] = {}
        valid_ports = {port.name for port in compiled.spec.outputs}
        for candidate in siblings.values():
            port_name = candidate.labels.get("operation_output_port")
            if port_name not in valid_ports:
                return None
            by_port.setdefault(port_name, []).append(candidate)
        expected_labels: list[tuple[str, str, int]] = []
        output_count = 0
        for port in compiled.spec.outputs:
            values = by_port.get(port.name, [])
            if not port.min_items <= len(values) <= port.max_items:
                return None
            if not all(self._artifact_matches_output_port(item, port) for item in values):
                return None
            for index in range(1, len(values) + 1):
                label = (
                    "primary"
                    if output_count == 0
                    else port.name
                    if port.collection is None and len(values) == 1
                    else f"{port.name}_{index:03d}"
                )
                expected_labels.append((label, port.name, index))
                output_count += 1
        if {label for label, _, _ in expected_labels} != set(siblings):
            return None
        if any(
            siblings[label].labels.get("operation_output_port") != port_name
            for label, port_name, _ in expected_labels
        ):
            return None
        return tuple(
            ProducerFamilyMember(
                port_name=port_name,
                item_name=(None if label == "primary" else label),
                ref=siblings[label].ref,
            )
            for label, port_name, _ in expected_labels
        )

    @staticmethod
    def _artifact_matches_input_port(envelope: Any, port: Any) -> bool:
        return bool(
            (port.schema_id == "*" or envelope.schema_id == port.schema_id)
            and (port.media_types == ("*/*",) or envelope.media_type in port.media_types)
            and envelope.size_bytes <= port.max_item_bytes
        )

    @staticmethod
    def _artifact_matches_output_port(envelope: Any, port: Any) -> bool:
        return bool(
            envelope.kind == port.kind
            and envelope.schema_id == port.schema_id
            and envelope.payload_schema_version == port.payload_schema_version
            and envelope.media_type in port.media_types
            and envelope.size_bytes <= port.max_item_bytes
        )

    def _effect_operation_plan(
        self, bound: BoundOperationCall
    ) -> EffectExecutorPlan:
        plan = (
            bound.executor_plan
            if isinstance(bound.executor_plan, EffectExecutorPlan)
            else effect_executor_plan(bound)
        )
        payloads = tuple(
            item for item in bound.inputs if item.port_name == plan.payload_port
        )
        if len(payloads) != 1 or len(bound.inputs) != 1:
            raise OperationInvocationError("effect_payload_not_singular")
        if self.execution_bridge is None:
            raise OperationInvocationError("effect_bridge_unavailable")
        if not self.execution_bridge.has_adapter(plan.executor):
            raise OperationInvocationError("runtime_binding_unavailable")
        try:
            self.execution_bridge.validate_request(
                executor=plan.executor,
                preparation_profile=plan.preparation_profile,
                payload=self.artifacts.read(payloads[0].artifact.ref),
            )
        except Exception as error:
            raise OperationInvocationError("effect_preparation_invalid") from error
        return plan

    def _invoke_compiled_transform(
        self,
        bound: BoundOperationCall,
        on_conflict: str,
    ) -> dict[str, Any]:
        name = bound.name
        profile = bound.compiled.spec.operation_id
        inputs = bound.inputs
        source_names = tuple(item.source_name for item in inputs)
        artifact_names = tuple(item.artifact_name for item in inputs)
        if len(source_names) != len(set(source_names)):
            raise RootToolError("transform source names must be unique")
        if len(artifact_names) != len(set(artifact_names)):
            raise RootToolError("transform artifacts must be unique")
        allowed_nonqualifying = frozenset(
            item.source_name
            for item in inputs
            if bound.compiled.spec.consequence == "explore"
            or item.usage != "claim_evidence"
        )

        envelopes = tuple(
            self.artifacts.get_by_id(
                self._resolve_input_artifact(
                    item.artifact_name,
                    allow_nonqualifying=(
                        item.source_name in allowed_nonqualifying
                    ),
                )
            )
            for item in inputs
        )
        derived_from_nonqualifying = any(
            item.source_name in allowed_nonqualifying
            and (
                envelope.labels.get("scientific_claim_admissible") == "false"
                or (
                    (signal := self.runs.signal_for_output(envelope.ref, require_current=False)
                     if self.runs is not None else None)
                    is not None
                    and signal.verdict in _NONQUALIFYING_HANDOFF_VERDICTS
                )
            )
            for item, envelope in zip(inputs, envelopes, strict=True)
        )
        selected_payload_names = tuple(
            item.source_name for item in inputs if item.exposure != "handoff_only"
        )
        selected = set(selected_payload_names)
        payloads = {
            item.source_name: (
                self.artifacts.read(envelope.ref)
                if item.source_name in selected
                else b""
            )
            for item, envelope in zip(inputs, envelopes, strict=True)
        }
        try:
            outputs = execute_compiled_transform(bound, payloads)
        except Exception as error:
            raise RootToolError("deterministic transform failed", details=getattr(error, "details", ())) from error
        labels = tuple(output.label for output in outputs)
        if not outputs or "primary" not in labels or len(labels) != len(set(labels)):
            raise RootToolError(
                "deterministic transform must return unique outputs including primary"
            )

        fingerprint = canonical_sha256(
            {
                "operation": bound.compiled.spec.operation_id,
                "operation_version": bound.compiled.spec.version,
                "operation_digest": bound.compiled.digest,
                "profile": profile,
                "inputs": [
                    {"source_name": item.source_name, "artifact_ref": envelope.ref}
                    for item, envelope in zip(inputs, envelopes, strict=True)
                ],
            }
        )
        parent_refs = tuple(envelope.ref for envelope in envelopes)
        with self._create_lock:
            target = self._creation_target("artifact", name, fingerprint, on_conflict)
            registered = []
            for output in outputs:
                output_name = (
                    target.name
                    if output.label == "primary"
                    else _derived_name(target.name, output.label)
                )
                existing_id = self._optional("artifact", output_name)
                if existing_id is None:
                    envelope = self.artifacts.register(
                        output.content,
                        ArtifactRegistration(
                            kind=output.kind,
                            schema_id=output.schema,
                            payload_schema_version=output.payload_schema_version,
                            media_type=output.media_type,
                            creator=self.intake.creator,
                            parent_refs=parent_refs,
                            labels={
                                "transform_profile": profile,
                                "output_label": output.label,
                                "operation_invocation_fingerprint": fingerprint,
                                **(
                                    {"operation_output_port": output.port_name}
                                    if output.port_name is not None else {}
                                ),
                                **_operation_artifact_labels(bound),
                                **(
                                    {"scientific_claim_admissible": "false"}
                                    if derived_from_nonqualifying
                                    else {}
                                ),
                            },
                        ),
                        idempotency_key=(
                            "artifact-transform:"
                            + canonical_sha256(
                                {
                                    "instance": self._instance_id(),
                                    "name": output_name,
                                    "fingerprint": fingerprint,
                                    "label": output.label,
                                }
                            )
                        ),
                    )
                    if output.label == "primary":
                        binding = self._bind_target(
                            "artifact", target, envelope.artifact_id, fingerprint
                        )
                    else:
                        binding = self._bind(
                            "artifact",
                            output_name,
                            envelope.artifact_id,
                            request_fingerprint=fingerprint,
                        )
                else:
                    envelope = self.artifacts.get_by_id(existing_id)
                    if self.artifacts.read(envelope.ref) != output.content:
                        raise RootToolError(
                            "existing transform output differs from deterministic result"
                        )
                    binding = self._binding("artifact", output_name)
                registered.append(
                    {
                        "output_label": output.label,
                        "artifact_name": binding.name,
                        "kind": envelope.kind,
                        "schema": envelope.schema_id,
                        "media_type": envelope.media_type,
                        "size_bytes": envelope.size_bytes,
                    }
                )
        return {"name": target.name, "profile": profile, "outputs": registered}

    def _prepare_operation_call(
        self,
        *,
        name: str,
        operation_id: str,
        inputs: tuple[_OperationInputSelection, ...],
        instruction: str | None,
        parameters: dict[str, Any],
        on_conflict: str,
        resume_from: str | None = None,
        draft_from: str | None = None,
        max_attempts: int | None = None,
    ) -> BoundOperationCall:
        del on_conflict
        if resume_from is not None and draft_from is not None:
            raise OperationInvocationError("recovery_sources_mutually_exclusive")
        try:
            compiled = self._operation_catalog.operation(operation_id)
        except KeyError as error:
            raise OperationInvocationError("operation_unknown") from error
        if max_attempts is not None:
            if type(max_attempts) is not int or max_attempts < 1:
                raise OperationInvocationError("invalid_attempt_limit", message="max_attempts must be a positive integer")
            if compiled.spec.executor.kind != "agent":
                raise OperationInvocationError("attempt_limit_not_applicable", message="max_attempts applies only to Agent Runs")
        if compiled.spec.catalog_scope == "internal":
            raise OperationInvocationError("operation_scope_forbidden")
        review = compiled.spec.review
        if (
            compiled.spec.catalog_scope == "public"
            and review is not None
            and review.reviewer_operation is not None
            and not self._scheduler_operation_available(review.reviewer_operation)
        ):
            raise OperationInvocationError("operation_runtime_unavailable")
        ports = tuple(item.port for item in inputs)
        if len(ports) != len(set(ports)):
            raise OperationInvocationError("input_port_duplicate")
        current_selections = tuple(
            self.bindings.scientific_selections(instance=self._instance_id())
        )
        current_lineages = {
            item.logical_name
            for item in current_selections
            if item.artifact_ref is None
        }
        current_refs = tuple(
            item.artifact_ref
            for item in current_selections
            if item.artifact_ref is not None
        )
        resolved: dict[str, tuple[InvocationArtifact, ...]] = {}
        for selection in inputs:
            try:
                port = next(
                    item for item in compiled.spec.inputs if item.name == selection.port
                )
            except StopIteration:
                resolved[selection.port] = ()
                continue
            artifacts: list[InvocationArtifact] = []
            for artifact_name in selection.artifact_names:
                try:
                    self._resolve("artifact", artifact_name)
                    artifact_id = self._resolve_input_artifact(
                        artifact_name,
                        allow_nonqualifying=True,
                    )
                    binding = self._binding("artifact", artifact_name)
                    envelope = self.artifacts.get_by_id(artifact_id)
                except Exception as error:
                    raise OperationInvocationError(
                        "input_artifact_unavailable", port=selection.port
                    ) from error
                # Frozen history is an input fact; current review/approval
                # eligibility is checked separately by admission and projection.
                signal = self.runs.signal_for_output(envelope.ref, require_current=False)
                producer_family = self._producer_output_family_from_envelope(
                    artifact_name, envelope
                )
                artifacts.append(
                    InvocationArtifact(
                        artifact_name=artifact_name,
                        ref=envelope.ref,
                        schema_id=envelope.schema_id,
                        media_type=envelope.media_type,
                        size_bytes=envelope.size_bytes,
                        current=(
                            self.runs.input_is_current(
                                instance_id=self._instance_id(),
                                artifact_name=artifact_name,
                                artifact_ref=envelope.ref,
                            )
                            if self.runs is not None
                            else (
                                binding.logical_name in current_lineages
                                or self._artifact_descends_from(
                                    envelope.ref, current_refs
                                )
                            )
                        ),
                        parent_refs=envelope.parent_refs,
                        labels=tuple(sorted(envelope.labels.items())),
                        handoff_verdict=(signal.verdict if signal is not None else None),
                        historical=self._is_historical(envelope),
                        producer_run_id=(
                            producer_family.producer_run_id
                            if producer_family is not None
                            else None
                        ),
                        producer_inputs=(
                            tuple(
                                (item.port_name, item.ref)
                                for item in producer_family.producer_inputs
                            )
                            if producer_family is not None
                            else None
                        ),
                    )
                )
            resolved[selection.port] = tuple(artifacts)
        for port in compiled.spec.inputs:
            if port.min_items == 0:
                resolved.setdefault(port.name, ())
        bound = preflight_operation(
            compiled,
            name=name,
            artifacts_by_port=resolved,
            instruction=instruction,
            parameters=parameters,
            read_artifact=self.artifacts.read,
        )
        if (
            self.runs is not None
            and compiled.spec.executor.kind == "agent"
            and not self.runs.backend.supports_operation(compiled)
        ):
            raise OperationInvocationError("runtime_backend_capability_missing")
        if (
            self.runs is not None
            and compiled.spec.executor.kind == "agent"
            and operation_local_worker_missing_tools(compiled)
        ):
            raise OperationInvocationError("runtime_backend_capability_missing")
        if resume_from is not None:
            if compiled.spec.executor.kind != "agent" or self.runs is None:
                raise OperationInvocationError("runtime_backend_capability_missing")
            try:
                self.runs.validate_resume(
                    self._resolve("run", resume_from),
                    operation_digest=compiled.digest,
                    input_refs=tuple(item.artifact.ref for item in bound.inputs),
                    max_attempts=compiled.spec.limits.max_attempts, check_attempts=False,
                )
            except Exception as error:
                raise OperationInvocationError("recovery_source_unavailable") from error
        if draft_from is not None:
            if compiled.spec.executor.kind != "agent" or self.runs is None:
                raise OperationInvocationError("runtime_backend_capability_missing")
            try:
                self.runs.validate_draft_source(
                    self._resolve("run", draft_from), compiled=compiled,
                    instance_id=self._instance_id(), check_attempts=False,
                )
            except Exception as error:
                raise OperationInvocationError("draft_source_unavailable") from error
        self._validate_operation_input_admission(bound)
        if compiled.spec.executor.kind == "effect":
            return replace(
                bound, executor_plan=self._effect_operation_plan(bound)
            )
        return bound

    def _artifact_descends_from(
        self, reference: Any, anchors: tuple[Any, ...]
    ) -> bool:
        if not anchors:
            return False
        pending = [reference]
        seen = set()
        anchor_set = set(anchors)
        while pending:
            current = pending.pop()
            if current in anchor_set:
                return True
            if current in seen:
                continue
            seen.add(current)
            if len(seen) > 4096:
                raise OperationInvocationError("current_provenance_too_large")
            pending.extend(self.artifacts.catalog(current).parent_refs)
        return False

    def _validate_operation_input_admission(self, bound: BoundOperationCall) -> None:
        reviewed = self._validate_producer_output_admission(bound)
        self._validate_complete_transform_family(bound)
        self._validate_revision_policy(bound)
        self._validate_compiled_input_admission(bound)
        for item in bound.inputs:
            if (
                bound.compiled.spec.consequence != "explore"
                and item.usage == "claim_evidence"
                and not _claim_admissible(
                    dict(item.artifact.labels), item.artifact.handoff_verdict
                )
                and not (
                    item.artifact.ref in reviewed
                    and self._claim_restriction_is_reviewable(item.artifact)
                )
            ):
                raise OperationInvocationError(
                    "input_scientific_claim_forbidden", port=item.port_name,
                    message="This input has a scientific-use restriction. Only an exact passing review can resolve a producer's blocked/revise restriction; explicit non-scientific sources remain restricted.",
                )

    def _claim_restriction_is_reviewable(self, artifact: InvocationArtifact) -> bool:
        """Distinguish a historical verdict from an intrinsic source restriction.

        Older transforms stored both as the same false label. Recover its cause
        from the registered transform family, without changing immutable history.
        Explicitly restricted parents (including exploratory outputs) stay blocked.
        """
        if dict(artifact.labels).get("scientific_claim_admissible") != "false":
            return artifact.handoff_verdict in _NONQUALIFYING_HANDOFF_VERDICTS
        envelope = self.artifacts.catalog(artifact.ref)
        family = self._transform_output_family(artifact.artifact_name, envelope)
        if family is None:
            return False
        producer = self._operation_catalog.operation(family.operation_id)
        if producer.spec.consequence == "explore" or producer.spec.catalog_scope == "internal":
            return False
        found_historical_verdict = False
        for reference in envelope.parent_refs:
            parent = self.artifacts.catalog(reference)
            if parent.labels.get("scientific_claim_admissible") == "false":
                return False
            signal = self.runs.signal_for_output(reference, require_current=False)
            if signal is not None and signal.verdict in _NONQUALIFYING_HANDOFF_VERDICTS:
                found_historical_verdict = True
        return found_historical_verdict

    def _validate_complete_transform_family(
        self, bound: BoundOperationCall
    ) -> None:
        """Verify one declared transform family using only frozen metadata."""

        requirement = bound.compiled.spec.complete_transform_family
        if requirement is None:
            return
        grouped: dict[str, tuple[Any, ...]] = {
            name: tuple(item for item in bound.inputs if item.port_name == name)
            for name in (*requirement.output_ports, *requirement.input_ports)
        }
        anchors = grouped[requirement.output_ports[0]]
        if not anchors:
            raise OperationInvocationError(
                "input_producer_family_mismatch",
                port=requirement.output_ports[0],
            )
        anchor = anchors[0]
        envelope = self.artifacts.catalog(anchor.artifact.ref)
        family = self._transform_output_family(anchor.artifact_name, envelope)
        if family is None:
            raise OperationInvocationError(
                "input_producer_family_mismatch", port=anchor.port_name
            )
        try:
            producer = self._operation_catalog.operation(family.operation_id)
        except KeyError as error:
            raise OperationInvocationError(
                "input_producer_family_mismatch", port=anchor.port_name
            ) from error
        if (
            producer.spec.executor.kind != "transform"
            or set(requirement.output_ports)
            != {port.name for port in producer.spec.outputs}
            or set(requirement.input_ports)
            != {port.name for port in producer.spec.inputs}
        ):
            raise OperationInvocationError("input_producer_family_mismatch")

        expected_outputs: dict[str, list[Any]] = {}
        for member in family.members:
            expected_outputs.setdefault(member.port_name, []).append(member.ref)
        for port_name in requirement.output_ports:
            actual = tuple(item.artifact.ref for item in grouped[port_name])
            expected = tuple(expected_outputs.get(port_name, ()))
            if len(actual) != len(expected) or set(actual) != set(expected):
                raise OperationInvocationError(
                    "input_producer_family_mismatch", port=port_name
                )

        producer_inputs = self._transform_input_groups(
            producer, envelope.parent_refs
        )
        if producer_inputs is None:
            raise OperationInvocationError("input_producer_family_mismatch")
        for port_name in requirement.input_ports:
            actual = tuple(item.artifact.ref for item in grouped[port_name])
            expected = tuple(item.ref for item in producer_inputs[port_name])
            if actual != expected:
                raise OperationInvocationError(
                    "input_producer_family_mismatch", port=port_name
                )

    def _validate_revision_policy(self, bound: BoundOperationCall) -> None:
        review = bound.compiled.spec.review
        if review is None or review.max_revisions == 0:
            return
        if direct_revision_ports(bound.compiled) is None or self.runs is None:
            raise OperationInvocationError("revision_policy_unavailable")
        direct = active_direct_revision_ports(
            bound.compiled, (item.port_name for item in bound.inputs)
        )
        if direct is None:
            return
        base_item = next(
            item for item in bound.inputs if item.port_name == direct[0].name
        )
        requests = tuple(
            item for item in bound.inputs if item.usage == "change_request"
        )
        if len(requests) != 1:
            raise OperationInvocationError("revision_progress_request_invalid")
        revision_count = 0
        previous_request = None
        current_ref = base_item.artifact.ref
        while True:
            prior_run = self.runs.completed_for_output(current_ref)
            if (
                prior_run is None
                or prior_run.operation_id != bound.compiled.spec.operation_id
            ):
                break
            bases = tuple(
                item for item in prior_run.inputs if item.usage == "revision_base"
            )
            prior_requests = tuple(
                item for item in prior_run.inputs if item.usage == "change_request"
            )
            if not bases and not prior_requests:
                if direct[0].min_items > 0:
                    raise OperationInvocationError("revision_history_invalid")
                break
            if len(bases) != 1 or len(prior_requests) != 1:
                raise OperationInvocationError("revision_history_invalid")
            if revision_count == 0:
                previous_request = prior_requests[0].artifact_ref
            revision_count += 1
            if revision_count >= review.max_revisions:
                raise OperationInvocationError("revision_limit_reached")
            current_ref = bases[0].artifact_ref
        if previous_request is None:
            return
        assert review.progress_fingerprint is not None
        key = (
            f"{review.progress_fingerprint.plugin_id or bound.compiled.plugin_id}:"
            f"{review.progress_fingerprint.component_id}"
        )
        fingerprint = bound.compiled.implementations[key]
        try:
            current_value = fingerprint(
                self.artifacts.read(requests[0].artifact.ref)
            )
            previous_value = fingerprint(self.artifacts.read(previous_request))
        except Exception as error:
            raise OperationInvocationError("revision_progress_unavailable") from error
        if (
            not isinstance(current_value, str)
            or not current_value
            or len(current_value) > 256
            or not isinstance(previous_value, str)
            or not previous_value
            or len(previous_value) > 256
        ):
            raise OperationInvocationError("revision_progress_unavailable")
        if current_value == previous_value:
            raise OperationInvocationError("revision_no_progress")

    def _validate_compiled_input_admission(self, bound: BoundOperationCall) -> None:
        """Apply the Operation's single compiled all-or-none/approval contract."""

        admission = bound.compiled.spec.input_admission
        if admission is None:
            return
        actual = {item.port_name: item for item in bound.inputs}
        if not any(name in actual for name in admission.member_ports):
            return
        if admission.approval_kind is None:
            return
        providers = bound.compiled.approval_providers
        if not providers or self.approvals is None:
            raise OperationInvocationError(
                "input_cohort_approval_missing", port=admission.cohort_id
            )
        refs = tuple(
            actual[name].artifact.ref for name in admission.approval_subject_ports
        )
        approved = self.approvals.are_subjects_approved_by_provider(
            refs,
            kind=admission.approval_kind,
            accepted_options=admission.accepted_options,
            allow_compatible_provider=bound.compiled.spec.executor.kind != "effect",
            accepted_providers=tuple(
                CompiledApprovalIdentity(
                    operation_id=provider.operation_id,
                    operation_version=provider.version,
                    operation_digest=provider.operation_digest,
                    approval_contract_digest=provider.approval_contract_digest,
                )
                for provider in providers
            ),
        )
        if not approved:
            raise OperationInvocationError(
                "input_cohort_approval_missing", port=admission.cohort_id
            )

    def _validate_producer_output_admission(
        self,
        bound: BoundOperationCall,
    ) -> set[Any]:
        reviewed: set[Any] = set()
        direct_revision = active_direct_revision_ports(
            bound.compiled, (item.port_name for item in bound.inputs)
        )
        direct_base_port = (
            direct_revision[0].name if direct_revision is not None else None
        )
        change_requests = tuple(
            item for item in bound.inputs if item.usage == "change_request"
        )
        review_signals = tuple(
            item
            for item in bound.inputs
            if item.usage in {"change_request", "review_signal"}
        )
        consumed_review_signals: set[Any] = set()
        for item in bound.inputs:
            mode = review_input_mode(
                operation_id=bound.compiled.spec.operation_id,
                port_name=item.port_name, usage=item.usage,
                direct_base_port=direct_base_port,
            )
            if mode == "background":
                continue
            artifact = item.artifact
            port_name = item.port_name
            try:
                contract = self._operation_output_contract(
                    artifact,
                    allow_historical=(
                        item.usage in {"prior_signal", "revision_base"}
                    ),
                )
            except OperationInvocationError as error:
                raise OperationInvocationError(
                    error.reason_code, port=port_name, field=error.field,
                    message=error.details[0]["message"],
                ) from error
            if contract is None:
                if mode == "direct_revision":
                    raise OperationInvocationError(
                        "input_output_usage_forbidden", port=port_name
                    )
                continue
            _, review = contract
            if review is None:
                if mode == "direct_revision":
                    self._validate_direct_revision_request(
                        bound,
                        base=artifact,
                        frozen_review=None,
                        change_requests=change_requests,
                    )
                continue
            if mode == "direct_revision":
                consumed_review_signals.update(
                    self._validate_direct_revision_request(
                        bound,
                        base=artifact,
                        frozen_review=review,
                        change_requests=change_requests,
                    )
                )
                continue
            required_reviewer, reviewer_input_port, accepted_verdicts = review
            if review_input_mode(
                operation_id=bound.compiled.spec.operation_id,
                port_name=port_name, usage=item.usage,
                direct_base_port=direct_base_port,
                reviewer_operation=required_reviewer,
                reviewer_input_port=reviewer_input_port,
            ) == "review_subject":
                continue
            def exact_review(candidate: Any, *, require_compatible: bool = True) -> bool:
                return candidate.artifact.ref != artifact.ref and self._is_exact_reviewer_output(
                    candidate.artifact.ref,
                    reviewer_operation=required_reviewer,
                    reviewer_input_port=reviewer_input_port,
                    accepted_verdicts=(
                        _NONPASSING_REVIEW_VERDICTS
                        if candidate.usage in {"change_request", "review_signal"}
                        else accepted_verdicts
                    ),
                    subject_ref=artifact.ref,
                    require_compatible=require_compatible,
                )

            reviewer_output = next((candidate for candidate in bound.inputs if exact_review(candidate)), None)
            if reviewer_output is None:
                if any(exact_review(candidate, require_compatible=False) for candidate in bound.inputs):
                    raise OperationInvocationError(
                        "input_independent_review_incompatible", port=port_name,
                        message="An exact completed review exists, but its Operation version or output type is no longer supported. Request a new review of this same subject.",
                    )
                raise OperationInvocationError(
                    "input_independent_review_missing", port=port_name,
                    message="No bound completed review from the declared reviewer covers this exact subject with an accepted verdict.",
                )
            if reviewer_output.usage in {"change_request", "review_signal"}:
                consumed_review_signals.add(reviewer_output.artifact.ref)
            elif (
                reviewer_output.artifact.handoff_verdict == "pass"
                and _claim_admissible(
                    dict(reviewer_output.artifact.labels),
                    reviewer_output.artifact.handoff_verdict,
                )
            ):
                reviewed.add(artifact.ref)
        unbound_signal = next(
            (
                item
                for item in review_signals
                if item.artifact.ref not in consumed_review_signals
            ),
            None,
        )
        if unbound_signal is not None:
            raise OperationInvocationError(
                "input_review_signal_unbound", port=unbound_signal.port_name
            )
        return reviewed

    def _validate_direct_revision_request(
        self,
        bound: BoundOperationCall,
        *,
        base: InvocationArtifact,
        frozen_review: tuple[str, str, tuple[str, ...]] | None,
        change_requests: tuple[Any, ...],
    ) -> tuple[Any, ...]:
        declared = bound.compiled.spec.review
        assert declared is not None
        assert declared.reviewer_operation is not None
        assert declared.reviewer_input_port is not None
        direct_review = (
            declared.reviewer_operation,
            declared.reviewer_input_port,
            declared.accepted_verdicts,
        )
        if frozen_review is not None and frozen_review != direct_review:
            raise OperationInvocationError(
                "input_revision_review_contract_mismatch"
            )
        if not change_requests:
            return ()
        if frozen_review is None:
            raise OperationInvocationError("input_change_request_mismatch")
        reviewer_operation, reviewer_input_port, _ = frozen_review
        invalid = next(
            (
                item
                for item in change_requests
                if not self._is_exact_reviewer_output(
                    item.artifact.ref,
                    reviewer_operation=reviewer_operation,
                    reviewer_input_port=reviewer_input_port,
                    accepted_verdicts=_NONPASSING_REVIEW_VERDICTS,
                    subject_ref=base.ref,
                )
            ),
            None,
        )
        if invalid is not None:
            if self._is_exact_reviewer_output(
                invalid.artifact.ref,
                reviewer_operation=reviewer_operation,
                reviewer_input_port=reviewer_input_port,
                accepted_verdicts=_NONPASSING_REVIEW_VERDICTS,
                subject_ref=base.ref,
                require_compatible=False,
            ):
                raise OperationInvocationError(
                    "input_independent_review_incompatible", port=invalid.port_name,
                    message="The exact change request exists, but its reviewer version or output type is no longer supported. Request a new review of this same prior draft.",
                )
            raise OperationInvocationError(
                "input_change_request_mismatch", port=invalid.port_name,
                message="The change request must be a compatible completed non-passing review of the exact prior draft by its declared reviewer.",
            )
        return tuple(item.artifact.ref for item in change_requests)

    def _is_historical(self, envelope: Any) -> bool:
        operation_id = envelope.labels.get("operation_id")
        if operation_id is None:
            return False
        try:
            producer = self._operation_catalog.operation(operation_id)
        except KeyError:
            return True
        return (
            envelope.labels.get("operation_version") != producer.spec.version
            or envelope.labels.get("operation_digest") != producer.digest
        )

    def _operation_output_contract(
        self, artifact: InvocationArtifact, *, allow_historical: bool = False
    ) -> tuple[Any, tuple[str, str, tuple[str, ...]] | None] | None:
        envelope = self.artifacts.catalog(artifact.ref)
        operation_id = envelope.labels.get("operation_id")
        version = envelope.labels.get("operation_version")
        digest = envelope.labels.get("operation_digest")
        port_name = envelope.labels.get("operation_output_port")
        if operation_id is None and digest is None and port_name is None:
            return None
        if not all(isinstance(value, str) and value for value in (
            operation_id, version, digest, port_name,
        )):
            raise OperationInvocationError("input_producer_contract_unavailable")
        try:
            compiled = self._operation_catalog.operation(str(operation_id))
        except KeyError as error:
            raise OperationInvocationError("input_producer_contract_unavailable") from error
        if compiled.spec.version != version and not allow_historical:
            raise OperationInvocationError(
                "input_producer_contract_changed",
                message="The producer Operation version is incompatible with current scientific use. Review or revise the historical record under the supported version; changing Agent output fields cannot repair this admission failure.",
            )
        try:
            port = next(value for value in compiled.spec.outputs if value.name == port_name)
        except StopIteration as error:
            raise OperationInvocationError("input_producer_port_unknown") from error
        # Same-version runtime drift does not revoke sealed science. The
        # current typed port and review edge still govern its consumption.
        if (allow_historical or compiled.digest != digest) and (
            port.schema_id != artifact.schema_id
            or port.kind != artifact.ref.kind
            or artifact.media_type not in port.media_types
        ):
            raise OperationInvocationError(
                "input_producer_port_incompatible",
                message="The historical output no longer matches the producer port's schema, kind or media type.",
            )
        declared = compiled.spec.review
        review = None
        if (
            declared is not None and declared.reviewer_operation is not None
            and port.name in declared.subject_outputs
        ):
            assert declared.reviewer_input_port is not None
            review = (
                declared.reviewer_operation,
                declared.reviewer_input_port,
                declared.accepted_verdicts,
            )
        return port, review



__all__ = ["RootOperationRoutes"]
