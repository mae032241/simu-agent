"""Compiled, bounded access to exact citations; no scientific dependency inference."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from .artifact_agent.schema.common import SchemaModel

REFERENCE_RESPONSE_DEFAULT_BYTES = 4096
REFERENCE_RESPONSE_MAX_BYTES = 8192


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
        ReferenceRule('scidiscovery.evidence-audit.v1', '/checks/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.scientific-foundation.v1', '/items/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.scientific-intake.v1', '/scientific_foundation/items/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.scientific-review.v1', '/findings/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.experiment-review.v1', '/scientific_test/result/evidence_keys/*'),

        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/source_references/*/input_alias'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/evidence/*/source_key'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/evidence/*/locator', locator_prefix=True),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/gates/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/objective_assessment/evidence_keys/*'),
        ReferenceRule('scidiscovery.layered-diagnosis.v1', '/hypothesis_assessments/*/evidence_keys/*'),
        ReferenceRule('scidiscovery.experiment-scientific-skeleton.v1', '', producer_input_alias='research_objective'),
        ReferenceRule('scidiscovery.experiment-report.v1', '/adopted_stages/*'),
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


LEGACY_REFERENCE_HISTORY_DESCRIPTION = 'Exact terminal task name from worker_read_history. Authorizes only its allowed sealed report and visible frozen scientific inputs in this assignment frozen range, not arbitrary instance artifacts. Directory listing is navigation; only successful original read registers a citation alias. No review or qualification is inherited.'


class ReferenceReadRequest(SchemaModel):
    history_task: str | None = Field(default=None, min_length=1, max_length=256, description="Exact task name in this assignment frozen history or its immutable recovery parent chain. Authorizes only that node's allowed sealed report, visible inputs and sealed tool originals, never arbitrary instance tasks or artifacts. List pages are navigation; only a successful selected original read registers this call's citation alias. Ancestor receipts and references are not inherited; no review or qualification is inherited.")
    source: str | None = Field(default=None, min_length=1, max_length=256, description='Frozen input, sealed stage, published attachment (including recovered files), or current controlled access alias; not an Artifact ID.')
    view: Literal['originals', 'boundaries'] = Field(default='originals', description='boundaries reads complete immutable owner declarations paired with this exact sealed primary, including provenance checks. It does not certify interpretation or user authorization; unknown references cannot relax current H boundaries. Original JSON Pointer semantics are unchanged.')
    action: Literal['list', 'read'] = 'list'
    delivery: Literal['fragment', 'file'] = Field(default='fragment', description='Read a bounded text fragment, or expose the exact complete original as a native read-only file.')
    reference: str | None = Field(default=None, max_length=256, description='Exact reference handle returned by list; required for read.')
    pointer: str | None = Field(default=None, max_length=1024, description='JSON Pointer selecting a field or one inline calculation; omitted means text.')
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=REFERENCE_RESPONSE_DEFAULT_BYTES, ge=512, le=REFERENCE_RESPONSE_MAX_BYTES,
        description='Maximum encoded response bytes, including navigation and file-delivery metadata. Keep the default 4096 unless a measured response supports less; 512 may not hold one entry or file receipt. A reference_response_budget diagnostic gives an explicit limit-only retry patch for this same selection when feasible. Verify one item before batching the same budget; limits are never increased automatically.')
    cursor: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def _selection(self):
        if self.history_task is None and self.source is None:
            raise ValueError('source is required unless selecting history_task')
        if self.history_task is not None and self.source is not None:
            raise ValueError('history_task selects its exact directory; do not supply source')
        if self.view == 'boundaries' and self.delivery == 'file':
            raise ValueError('boundaries uses bounded fragment reads; follow next_offset for the complete declaration')
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
        import json
        from .operation_contract import DiagnosticError, contract_diagnostic
        details = (contract_diagnostic(
            response['code'], phase='tool_execution', affected_action='tool_call',
            path='$.reference', message=response['message'], repairable=True),)
        if response.get('code') == 'reference_response_limit' and 'response_budget' in response:
            details += (contract_diagnostic('reference_response_budget', phase='tool_execution',
                affected_action='tool_call', path='$.limit', repairable=response['response_budget']['retry'] is not None,
                message=json.dumps(response['response_budget'], separators=(',', ':'))),)
        raise DiagnosticError(response['message'], details=details)
    return response


def reference_tool():
    # Local import keeps declarations independent of the service implementation.
    from .operations.tooling import WorkerToolDefinition
    return WorkerToolDefinition(
        name='worker_reference_read',
        description='List direct citations and published attachments of one exact bound report, or read a selected original. Exactly one of source and history_task is required. history_task instead lists one exact frozen history task’s allowed report and visible scientific inputs; choose its returned reference for read. History handles are navigation only; successful read returns the registered citation source alias. Current and recovered stage/file aliases also support list: content reads that material, while stage references open its currently bound scientific sources. Use delivery=file for images and large originals (streamed under frozen input_materials budgets); fragment reads have bounded memory. Select one calculation before requesting its inputs. view=boundaries lists or reads complete sealed owner boundary declarations paired with the exact report, including frozen history; follow fragment continuation. Citation matching is location evidence only, not authorization or interpretation validation.',
        input_model=ReferenceReadRequest, capability='reference.read',
        contextual_handler=reference_handler, reference_policy=ReferencePolicy(),
    )


REFERENCE_READ_TOOL = reference_tool()
