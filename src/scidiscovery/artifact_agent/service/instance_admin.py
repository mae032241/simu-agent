"""Loopback-only ownership-aware research-instance administration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from ..schema.refs import ArtifactRef
from ..storage import ArtifactNotFoundError
from .approvals import ApprovalService
from .artifacts import ArtifactService
from .executions import ExecutionService, ExecutionServiceError
from .scheduler_bindings import (
    SchedulerBinding,
    SchedulerBindingService,
    SchedulerInstance,
)
from .tasks import TaskService, TaskServiceError


class InstanceAdministrationError(RuntimeError):
    pass


class InstanceDeletionBlocked(InstanceAdministrationError):
    pass


@dataclass(frozen=True)
class InstanceDeletionPlan:
    instance: SchedulerInstance
    bindings: tuple[SchedulerBinding, ...]
    exclusive_artifact_ids: tuple[str, ...]
    exclusive_task_ids: tuple[str, ...]
    exclusive_approval_ids: tuple[str, ...]
    exclusive_execution_ids: tuple[str, ...]
    shared_bindings: tuple[SchedulerBinding, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class InstanceDeletionReceipt:
    instance_name: str
    deleted_bindings: int
    deleted_tasks: int
    deleted_approvals: int
    deleted_executions: int
    deleted_artifact_registrations: int
    preserved_shared_objects: int


class InstanceAdministrationService:
    """Coordinate explicit destructive cleanup across control-plane stores."""

    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        approvals: ApprovalService,
        bindings: SchedulerBindingService,
        tasks: TaskService | None = None,
        executions: ExecutionService | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.approvals = approvals
        self.bindings = bindings
        self.tasks = tasks
        self.executions = executions

    def plan(self, *, instance_id: str) -> InstanceDeletionPlan:
        instance = self.bindings.get_instance(instance_id=instance_id)
        bindings = self.bindings.instance_bindings(instance=instance_id)
        exclusive: dict[str, list[str]] = {
            "artifact": [],
            "task": [],
            "approval": [],
            "execution": [],
        }
        shared: list[SchedulerBinding] = []
        for binding in bindings:
            if self.bindings.object_owner_count(
                namespace=binding.namespace, object_id=binding.object_id
            ) == 1:
                exclusive[binding.namespace].append(binding.object_id)
            else:
                shared.append(binding)
        approval_ids = list(exclusive["approval"])
        for approval_id in self.bindings.instance_history_approval_ids(
            instance=instance_id
        ):
            owners = self.bindings.object_owner_count(
                namespace="approval", object_id=approval_id
            )
            if owners <= 1:
                approval_ids.append(approval_id)

        task_ids = _unique(exclusive["task"])
        execution_ids = _unique(exclusive["execution"])
        blockers: list[str] = []
        pending_binding_approvals = self.bindings.instance_pending_binding_approval_ids(
            instance=instance_id
        )
        if pending_binding_approvals:
            blockers.append(
                "待处理的进程绑定审批仍包含该实例："
                + "、".join(pending_binding_approvals)
            )
        if self.tasks is None and task_ids:
            blockers.append("任务服务未挂载，不能安全删除实例专属任务")
        elif self.tasks is not None:
            for task_id in task_ids:
                try:
                    state = self.tasks.status(task_id).state
                except TaskServiceError:
                    continue
                if state in {"dispatched", "claimed", "finalizing"}:
                    blockers.append(f"任务仍在运行：{task_id} ({state})")
            for task_id in self.tasks.active_development_debug_tasks(
                task_ids=task_ids
            ):
                blockers.append(f"开发调试执行尚未关闭：{task_id}")
        if self.executions is None and execution_ids:
            blockers.append("执行服务未挂载，不能安全删除实例专属执行")
        elif self.executions is not None:
            for execution_id in execution_ids:
                try:
                    state = self.executions.status(execution_id).state
                except ExecutionServiceError:
                    continue
                if state not in {"collected", "abandoned"}:
                    blockers.append(
                        f"执行尚未完成采集或明确放弃：{execution_id} ({state})"
                    )
        return InstanceDeletionPlan(
            instance=instance,
            bindings=bindings,
            exclusive_artifact_ids=_unique(exclusive["artifact"]),
            exclusive_task_ids=task_ids,
            exclusive_approval_ids=_unique(approval_ids),
            exclusive_execution_ids=execution_ids,
            shared_bindings=tuple(shared),
            blockers=tuple(blockers),
        )

    def delete(
        self, *, instance_id: str, confirmation_name: str
    ) -> InstanceDeletionReceipt:
        plan = self.plan(instance_id=instance_id)
        if confirmation_name != plan.instance.name:
            raise InstanceAdministrationError("实例名称确认不匹配")
        if plan.blockers:
            raise InstanceDeletionBlocked("；".join(plan.blockers))

        deletion = self.bindings.begin_instance_deletion(
            instance=instance_id,
            fingerprint=_plan_fingerprint(plan),
        )
        owned_refs = [
            ArtifactRef.model_validate_json(raw, strict=True)
            for raw in deletion.owned_ref_json
        ]
        stage = deletion.stage
        purged_count = 0
        try:
            if stage == "planned":
                for artifact_id in plan.exclusive_artifact_ids:
                    try:
                        owned_refs.append(self.artifacts.get_by_id(artifact_id).ref)
                    except ArtifactNotFoundError:
                        continue
                if self.tasks is not None:
                    owned_refs.extend(
                        self.tasks.delete_tasks(plan.exclusive_task_ids)
                    )
                owned_refs = list(_unique_refs(owned_refs))
                deletion = self.bindings.advance_instance_deletion(
                    instance=instance_id,
                    stage="tasks_deleted",
                    owned_ref_json=tuple(
                        reference.canonical_json().decode("utf-8")
                        for reference in owned_refs
                    ),
                )
                stage = deletion.stage
            if stage == "tasks_deleted":
                if self.executions is not None:
                    owned_refs.extend(
                        self.executions.delete_executions(
                            plan.exclusive_execution_ids
                        )
                    )
                owned_refs = list(_unique_refs(owned_refs))
                deletion = self.bindings.advance_instance_deletion(
                    instance=instance_id,
                    stage="executions_deleted",
                    owned_ref_json=tuple(
                        reference.canonical_json().decode("utf-8")
                        for reference in owned_refs
                    ),
                )
                stage = deletion.stage
            if stage == "executions_deleted":
                owned_refs.extend(
                    self.approvals.delete_requests(plan.exclusive_approval_ids)
                )
                owned_refs = list(_unique_refs(owned_refs))
                deletion = self.bindings.advance_instance_deletion(
                    instance=instance_id,
                    stage="approvals_deleted",
                    owned_ref_json=tuple(
                        reference.canonical_json().decode("utf-8")
                        for reference in owned_refs
                    ),
                )
                stage = deletion.stage
            if stage == "approvals_deleted":
                purged = self.artifacts.purge_registrations(
                    _unique_refs(owned_refs)
                )
                purged_count = len(purged)
                deletion = self.bindings.advance_instance_deletion(
                    instance=instance_id,
                    stage="artifacts_purged",
                    owned_ref_json=tuple(
                        reference.canonical_json().decode("utf-8")
                        for reference in owned_refs
                    ),
                )
                stage = deletion.stage
            if stage == "artifacts_purged":
                self.bindings.delete_instance_records(instance=instance_id)
                deletion = self.bindings.advance_instance_deletion(
                    instance=instance_id,
                    stage="bindings_deleted",
                    owned_ref_json=tuple(
                        reference.canonical_json().decode("utf-8")
                        for reference in owned_refs
                    ),
                )
                stage = deletion.stage
            if stage != "bindings_deleted":
                raise InstanceAdministrationError(
                    "实例删除停留在未知的维护阶段"
                )
            receipt = InstanceDeletionReceipt(
                instance_name=plan.instance.name,
                deleted_bindings=len(plan.bindings),
                deleted_tasks=len(plan.exclusive_task_ids),
                deleted_approvals=len(plan.exclusive_approval_ids),
                deleted_executions=len(plan.exclusive_execution_ids),
                deleted_artifact_registrations=purged_count,
                preserved_shared_objects=len(plan.shared_bindings),
            )
            self.bindings.complete_instance_deletion(
                instance=instance_id,
                receipt_json=json.dumps(
                    asdict(receipt), ensure_ascii=False, sort_keys=True
                ),
            )
            return receipt
        except Exception as error:
            self.bindings.fail_instance_deletion(
                instance=instance_id, error=str(error)
            )
            raise


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _unique_refs(values: list[ArtifactRef]) -> tuple[ArtifactRef, ...]:
    return tuple(
        {
            reference.canonical_json(): reference
            for reference in values
        }.values()
    )


def _plan_fingerprint(plan: InstanceDeletionPlan) -> str:
    payload = {
        "instance_id": plan.instance.instance_id,
        "bindings": [
            (item.namespace, item.name, item.object_id) for item in plan.bindings
        ],
        "exclusive_artifact_ids": plan.exclusive_artifact_ids,
        "exclusive_task_ids": plan.exclusive_task_ids,
        "exclusive_approval_ids": plan.exclusive_approval_ids,
        "exclusive_execution_ids": plan.exclusive_execution_ids,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "InstanceAdministrationError",
    "InstanceAdministrationService",
    "InstanceDeletionBlocked",
    "InstanceDeletionPlan",
    "InstanceDeletionReceipt",
]
