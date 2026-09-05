"""Deterministic bridge between generic execution state and local adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from .schema.approval import CompiledApprovalIdentity
from .schema.execution import LocalFileDescriptor
from .service.executions import ExecutionService, ExecutionServiceError


@dataclass(frozen=True)
class AdapterCapability:
    """One public immutable capability document supplied by an adapter."""

    key: str
    kind: str
    schema_id: str
    payload_schema_version: int
    media_type: str
    content: bytes
    public_summary: Mapping[str, object]


class ExecutionAdapter(Protocol):
    def capabilities(self) -> tuple[AdapterCapability, ...]: ...

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor: ...

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]:
        """Idempotently submit this exact frozen descriptor."""
        ...

    def lookup_submission(
        self, submission: LocalFileDescriptor
    ) -> tuple[str, str] | None:
        """Authoritatively return an existing exact submission, or None."""
        ...

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
        missing_lookup = next(
            (
                name
                for name, adapter in self.adapters.items()
                if not callable(getattr(adapter, "lookup_submission", None))
            ),
            None,
        )
        if missing_lookup is not None:
            raise ExecutionServiceError(
                f"execution adapter {missing_lookup} has no authoritative "
                "submission lookup"
            )

    def has_adapter(self, executor: str) -> bool:
        return executor in self.adapters

    def start(
        self,
        *,
        execution_id: str,
        approval_id: str,
        compiled_identity: CompiledApprovalIdentity,
    ) -> None:
        request = self.executions.request(execution_id)
        adapter = self._adapter(request.executor)
        self.validate_request(
            executor=request.executor,
            preparation_profile=request.preparation_profile,
            payload=self.executions.artifacts.read(request.payload_ref),
        )
        payload = self.executions.authorize(
            execution_id=execution_id,
            approval_id=approval_id,
            compiled_identity=compiled_identity,
        )
        submission = adapter.prepare(
            payload,
            preparation_profile=request.preparation_profile,
            exchange_directory=Path(payload.local_path).parent,
        )
        recovered = adapter.lookup_submission(submission)
        if recovered is None:
            external_run_id, external_state = adapter.submit(submission)
        else:
            external_run_id, external_state = recovered
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

    def validate_request(
        self,
        *,
        executor: str,
        preparation_profile: str,
        payload: bytes | None = None,
    ) -> None:
        adapter = self._adapter(executor)
        checker = getattr(adapter, "supports_preparation_profile", None)
        if checker is not None and checker(preparation_profile) is not True:
            raise ExecutionServiceError(
                f"execution adapter {executor} does not support preparation profile "
                f"{preparation_profile}"
            )
        payload_checker = getattr(adapter, "validate_preparation_payload", None)
        if payload is not None and payload_checker is not None:
            try:
                payload_checker(payload, preparation_profile=preparation_profile)
            except (TypeError, ValueError, RuntimeError) as error:
                raise ExecutionServiceError(
                    f"execution payload is invalid for preparation profile "
                    f"{preparation_profile}"
                ) from error

    def capabilities(self, *, executor: str) -> tuple[AdapterCapability, ...]:
        adapter = self._adapter(executor)
        reader = getattr(adapter, "capabilities", None)
        if reader is None:
            raise ExecutionServiceError(
                f"execution adapter {executor} does not expose capabilities"
            )
        values = tuple(reader())
        if not values:
            raise ExecutionServiceError(
                f"execution adapter {executor} returned no capabilities"
            )
        keys = tuple(item.key for item in values)
        if len(keys) != len(set(keys)):
            raise ExecutionServiceError(
                f"execution adapter {executor} returned duplicate capabilities"
            )
        if any(
            not item.key
            or not item.schema_id
            or type(item.content) is not bytes
            or len(item.content) > 1024 * 1024
            for item in values
        ):
            raise ExecutionServiceError(
                f"execution adapter {executor} returned an invalid capability"
            )
        return values

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


__all__ = ["AdapterCapability", "ExecutionAdapter", "ExecutionBridge"]
