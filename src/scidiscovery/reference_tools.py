"""Compiled, bounded access to exact citations; no scientific dependency inference."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from .artifact_agent.schema.common import SchemaModel


@dataclass(frozen=True, slots=True)
class ReferenceRule:
    schema_id: str
    path: str
    keys: bool = False
    selected_only: bool = False
    locator_prefix: bool = False
    producer_input_alias: str | None = None


@dataclass(frozen=True, slots=True)
class ReferencePolicy:
    rules: tuple[ReferenceRule, ...] = (
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/source_references/*/input_alias'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/evidence/*/source_key'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/evidence/*/locator', locator_prefix=True),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/gates/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/objective_assessment/evidence_keys/*'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/hypothesis_assessments/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.experiment-scientific-skeleton.v1', '', producer_input_alias='research_objective'),
    )
    max_file_bytes: int = 32 * 1024 * 1024
    max_unique_bytes: int = 256 * 1024 * 1024
    max_io_bytes: int = 256 * 1024 * 1024
    max_calls: int = 128
    max_response_bytes: int = 2 * 1024 * 1024
    max_io_seconds: int = 120
    max_call_seconds: int = 10
    max_records: int = 32
    max_depth: int = 16


class ReferenceReadRequest(SchemaModel):
    source: str = Field(min_length=1, max_length=256, description='Frozen input or current controlled access alias; not an Artifact ID.')
    action: Literal['list', 'read'] = 'list'
    delivery: Literal['fragment', 'file'] = Field(default='fragment', description='Read a bounded text fragment, or expose the exact complete original as a native read-only file.')
    reference: str | None = Field(default=None, max_length=256, description='Exact reference handle returned by list; required for read.')
    pointer: str | None = Field(default=None, max_length=1024, description='JSON Pointer selecting a field or one inline calculation; omitted means text.')
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=4096, ge=512, le=8192, description='Maximum encoded response bytes, including navigation.')
    cursor: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def _selection(self):
        if self.delivery == 'file' and (self.action != 'read' or self.pointer is not None or self.offset != 0):
            raise ValueError('file delivery requires read without pointer or offset')
        if self.action == 'read' and not self.reference:
            raise ValueError('read requires the reference handle returned by list')
        if self.action == 'list' and self.reference is not None:
            raise ValueError('list selects source and optional pointer, not reference')
        return self


def reference_handler(request, context):
    response = context.read_reference(request)
    if response.get('state') == 'rejected':
        from .operation_contract import DiagnosticError, contract_diagnostic
        raise DiagnosticError(response['message'], details=(contract_diagnostic(
            response['code'], phase='tool_execution', affected_action='tool_call',
            path='$.reference', message=response['message'], repairable=True),))
    return response


def reference_tool():
    # Local import keeps declarations independent of the service implementation.
    from .operations.tooling import WorkerToolDefinition
    return WorkerToolDefinition(
        name='worker_reference_read',
        description='List direct citations and published attachments of one exact bound report, or read a selected original. Use delivery=file for large originals (streamed under frozen input_materials budgets); fragment reads have bounded memory. Select one calculation before requesting its inputs.',
        input_model=ReferenceReadRequest, capability='reference.read',
        contextual_handler=reference_handler, reference_policy=ReferencePolicy(),
    )


REFERENCE_READ_TOOL = reference_tool()
