"""Deterministic bridge between generic execution state and local adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol

from .schema.execution import LocalFileDescriptor
from .service.executions import ExecutionService, ExecutionServiceError


class ExecutionAdapter(Protocol):
    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor: ...

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]: ...

    def status(self, external_run_id: str) -> str: ...

    def cancel(self, external_run_id: str) -> str: ...

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]: ...


class ExecutionBridge:
    """Advance execution state only from one configured adapter's responses."""

    def __init__(
        self,
        executions: ExecutionService,
        *,
        adapters: Mapping[str, ExecutionAdapter],
    ) -> None:
        self.executions = executions
        self.adapters = dict(adapters)

    def start(self, *, execution_id: str, approval_id: str) -> None:
        request = self.executions.request(execution_id)
        adapter = self._adapter(request.executor)
        payload = self.executions.authorize(
            execution_id=execution_id,
            approval_id=approval_id,
        )
        submission = adapter.prepare(
            payload,
            preparation_profile=request.preparation_profile,
            exchange_directory=Path(payload.local_path).parent,
        )
        external_run_id, external_state = adapter.submit(submission)
        self.executions.record_submission(
            execution_id=execution_id,
            external_run_id=external_run_id,
        )
        if external_state != "accepted":
            self.executions.record_status(
                execution_id=execution_id,
                external_run_id=external_run_id,
                state=external_state,
            )

    def validate_request(self, *, executor: str, preparation_profile: str) -> None:
        adapter = self._adapter(executor)
        checker = getattr(adapter, "supports_preparation_profile", None)
        if checker is not None and checker(preparation_profile) is not True:
            raise ExecutionServiceError(
                f"execution adapter {executor} does not support preparation profile "
                f"{preparation_profile}"
            )

    def sync(self, *, execution_id: str) -> None:
        current = self.executions.status(execution_id)
        if current.state == "collected":
            return
        if current.external_run_id is None:
            raise ExecutionServiceError("execution has no submitted external run")
        adapter = self._adapter(current.executor)
        if current.state in {"succeeded", "failed", "cancelled"}:
            external_state = current.state
        else:
            external_state = adapter.status(current.external_run_id)
            self.executions.record_status(
                execution_id=execution_id,
                external_run_id=current.external_run_id,
                state=external_state,
            )
        if external_state in {"succeeded", "failed", "cancelled"}:
            outputs = adapter.collect(current.external_run_id)
            self.executions.ingest_result(
                execution_id=execution_id,
                external_run_id=current.external_run_id,
                outputs=outputs,
            )

    def cancel(self, *, execution_id: str) -> None:
        current = self.executions.status(execution_id)
        if current.state in {"succeeded", "failed", "cancelled", "collected"}:
            return
        if current.state not in {"submitted", "running", "cancelling"}:
            raise ExecutionServiceError("execution is not cancellable from current state")
        if current.external_run_id is None:
            raise ExecutionServiceError("execution has no submitted external run")
        adapter = self._adapter(current.executor)
        external_state = adapter.cancel(current.external_run_id)
        self.executions.record_status(
            execution_id=execution_id,
            external_run_id=current.external_run_id,
            state=external_state,
        )

    def _adapter(self, executor: str) -> ExecutionAdapter:
        try:
            return self.adapters[executor]
        except KeyError as error:
            raise ExecutionServiceError(
                f"no execution adapter is configured for {executor}"
            ) from error


__all__ = ["ExecutionAdapter", "ExecutionBridge"]
