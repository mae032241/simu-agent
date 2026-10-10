"""One lifecycle policy for failures anywhere in a Run submission.

This classifies declared failures, not scientific conclusions. Unknown exceptions
require intervention; only explicitly transient failures recommend unchanged retry.
"""
from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
import errno

from ...operation_contract import contract_diagnostic, DiagnosticError, ToolInputError
from ..storage import CASIntegrityError
from .local_workspace import WorkspaceError, WorkspaceOutputError
from .reference_proofs import ReferenceProofError
from .run_records import RunContractUnavailable
from .run_outputs import RunCheckerError, RunOutputError


# These tool-owned static diagnostics identify editable candidate material, not
# control bindings. A code alone is insufficient: attachment_publication_invalid
# also denotes a task with no attachment capability. Unknown variants stay closed.
_CANDIDATE_CORRECTIONS = {
    'attachment_publication_invalid': {
        'Publish files below scratch/. Move extra output files there; output/ holds only result.json and runtime receipts.',
        'Attachment is not a regular file',
        'Attachment changed while being published',
        'Duplicate attachment paths',
    },
    'attachment_file_missing': {'Finish writing the attachment below scratch/ before publication.'},
    'capture_scope_invalid': {
        'Declare a real task-local subdirectory below scratch/; whole scratch and external paths are unavailable',
        'Repair the capture_sources batch declaration to match its task-local contract',
        'At most four declared task-local capture directories',
        'capture_sources must contain at most four scientific batch declarations',
    },
    'capture_reference_invalid': {
        'run: is navigation only; cite an exact file or original alias and its existing locator',
        'Use the exact returned sealed stage reference',
    },
    'capture_reference_ambiguous': {
        'Basename conflicts with an alias; use the exact task-relative file path',
        'File is missing or ambiguous in this exact capture; use its full task-relative path',
    },
}
_CAPTURE_BUDGETS = {
    'attachment_publication_invalid': {
        'Attachment byte budget exceeded',
        'Attachment grew beyond the byte budget',
        'Attachment count or total byte budget exceeded',
    },
    'capture_inventory_limit': {'Capture index exceeds its encoded budget; narrow the declared batch'},
    'capture_ledger_limit': {'Derived ledger exceeds attachment byte budget'},
}
_ATTACHMENT_RECOVERY_LIMITS = (
    'draft_from preserves original nodes; it does not reset actual execution budgets. '
    'A new bounded task is allowed only if its fixed capture contract can contain required evidence. '
    'Never reset global budgets, remove old receipts or increase caps.')


@dataclass(frozen=True)
class SubmissionFailure:
    disposition: str
    category: str
    details: tuple


def classify_candidate_attachment_error(error, *, runs=None, run_id=None, affected_action='submit'):
    """One exact candidate overflow; legal old receipts do not prove a repair exists."""
    if not isinstance(error, ToolInputError) or len(error.details) != 1:
        return None
    item = error.details[0]
    if (item['code'], item['message']) != ('attachment_publication_invalid',
            'Attachment count or total byte budget exceeded'):
        return None
    try:
        if runs is None or run_id is None or error.__cause__ is not None:
            raise ValueError('Candidate budget context is unavailable')
        from ...agent_execution_settings import AttachmentSettings, EvidenceCapacitySettings
        # Read only this exact Run. Policy and committed receipts share one
        # transaction; this is current state, not the original requested batch.
        with closing(runs._connect()) as connection:
            connection.execute('PRAGMA query_only = ON')
            connection.execute('BEGIN')
            row = runs._row(connection, run_id)
            if (row['state'] != 'running' or row['accepted_candidate_digest'] is not None
                    or datetime.fromisoformat(row['deadline_at'].replace('Z', '+00:00')) <= datetime.now(timezone.utc)):
                raise ValueError('Candidate is not editable')
            policy = json.loads(row['recovery_policy_json'])
            raw_settings = policy['attachments']
            if not all(key in raw_settings for key in ('max_files', 'max_item_bytes', 'max_total_bytes')):
                raise ValueError('Frozen attachment settings are unavailable')
            settings = AttachmentSettings.model_validate(raw_settings, strict=True)
            capacities = EvidenceCapacitySettings.model_validate(policy.get('evidence_capacity', {}), strict=True)
            rows = connection.execute("SELECT record_json FROM run_tool_evidence WHERE run_id=? "
                "AND (COALESCE(json_extract(CAST(record_json AS TEXT),'$.record_type'),'')!='reference_access' "
                "OR json_extract(CAST(record_json AS TEXT),'$.output_port')='attachments') "
                "ORDER BY ordinal LIMIT 129", (run_id,)).fetchall()
            records = [json.loads(record[0]) for record in rows]
            if len(records) > capacities.max_new_records or any(not isinstance(record, dict)
                    or type(record.get('size_bytes')) is not int or record['size_bytes'] < 0
                    or (record.get('record_type') == 'reference_access' and record.get('output_port') == 'attachments')
                    for record in records):
                raise ValueError('Committed receipt state is invalid')
            receipt_count = sum(record.get('record_type') != 'reference_access' for record in records)
            attachments = [record for record in records if record.get('output_port') == 'attachments']
            sizes = [record['size_bytes'] for record in attachments]
            if (any(type(size) is not int or size < 0 or size > settings.max_item_bytes for size in sizes)
                    or len(attachments) > settings.max_files or sum(sizes) > settings.max_total_bytes):
                raise ValueError('Committed attachments exceed frozen settings')
    except Exception:
        details = (contract_diagnostic(item['code'], phase=item['phase'], affected_action=affected_action,
            path=item['path'], repairable=False, message=item['message']),
            contract_diagnostic('submission_intervention_required', phase='protocol',
                affected_action=affected_action, repairable=False,
                message='Control cannot establish a legal editable candidate budget. Preserve the draft; Root must inspect this exact task. '
                    'Do not retry unchanged, clear receipts, raise budgets, change sources or rerun execution. ' + _ATTACHMENT_RECOVERY_LIMITS))
        return SubmissionFailure('intervene', 'runtime_failure', details)
    usage = (f'Current committed attachments: {len(attachments)}/{settings.max_files} files, '
        f'{sum(sizes)}/{settings.max_total_bytes} bytes; remaining '
        f'{settings.max_files-len(attachments)} files, {settings.max_total_bytes-sum(sizes)} bytes. '
        f'Non-reference receipts: {receipt_count}/{capacities.max_new_records}; remaining {capacities.max_new_records-receipt_count}. '
        'The rejected batch amounts and exact triggering dimension are unknown. ')
    if len(usage) > 512:
        usage = ('Current committed receipts fit the frozen caps. Numeric amounts are omitted because their text exceeds the diagnostic bound. '
            'Read the frozen budget and retained receipt inventory. Rejected batch amounts and the exact triggering dimension are unknown.')
    def detail(code, message):
        return contract_diagnostic(code, phase=item['phase'], affected_action=affected_action,
            path=item['path'], repairable=True, message=message)
    return SubmissionFailure('reject', 'output_rejected', (
        detail(item['code'], item['message']), detail('attachment_candidate_budget', usage),
        detail('attachment_candidate_correction',
            'Immutable receipts cannot be deleted or cleared; frozen caps/roots stay binding. Reuse exact retained aliases. '
            'Correct only the unaccepted candidate if required evidence fits: reduce or move drafts that no longer need capture within task scratch, '
            'but retain required originals and source associations; do not evade capture of required unretained evidence or substitute summaries. '
            'Retry after correction, not unchanged; do not raise budgets or rerun execution.'),
        detail('attachment_candidate_recovery',
            'Legal existing receipts do not prove required new evidence can fit. A compliant correction is not guaranteed. '
            'If it cannot fit, preserve the draft and ask Root to inspect this exact task and choose qualified recovery. ' + _ATTACHMENT_RECOVERY_LIMITS)))


def classify_submission_error(error, *, deadline_expired=False, runs=None, run_id=None):
    # Some lower-level adapters wrap storage failures. Preserve their causes
    # without making every checker/ValueError automatically retryable.
    causes, seen, cause = [], set(), error
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        causes.append(cause)
        # Implicit context means only "occurred while handling", not causation.
        # It remains in engineering traces but cannot authorize retry.
        cause = cause.__cause__
    integrity = next((e for e in causes if isinstance(e, CASIntegrityError)), None)
    proof = next((e for e in causes if isinstance(e, ReferenceProofError)), None)
    if integrity is not None:
        return _failure('fail', 'integrity_failure', 'submission_integrity_failure',
            'Exact evidence failed integrity verification. This task has stopped; restore the original control evidence before Root chooses recovery. Retained drafts are not sealed scientific results.')
    if proof is not None:
        details = tuple(contract_diagnostic(item['code'], phase='protocol', affected_action='submit',
            repairable=False, message=(item['message'] + ' This task has stopped and its existing materials are retained. '
                'Root should inspect run_status diagnostics and recovery. Start a new task with selected exact materials; '
                'use draft_from or resume_from only if the retained proof fits after repair. Do not resubmit unchanged or rerun the solver.'))
            for item in proof.details)
        category = 'runtime_failure' if all(item['code'] in {'reference_proof_limit', 'reference_proof_contract_limit'} for item in proof.details) else 'integrity_failure'
        return SubmissionFailure('fail', category, details)
    if deadline_expired:
        return _failure('fail', 'run_timeout', 'submission_deadline_exhausted',
            'The task deadline has expired. Retain the existing draft and evidence; Root must choose recovery, not repeat submission in this task.')
    if any(isinstance(e, OSError) and e.errno in {errno.ENOSPC, errno.EDQUOT} for e in causes):
        return _failure('fail', 'runtime_failure', 'submission_storage_exhausted',
            'Control storage space or quota is exhausted. Root must restore storage capacity and recover the retained task; do not modify the scientific report or rerun the solver.')
    if any(isinstance(e, RunCheckerError) and e.category == 'tool_timeout' for e in causes):
        return _failure('fail', 'tool_timeout', 'submission_step_timeout',
            'A bounded finalization or validation step exhausted its time budget. Root must inspect the diagnostic and choose recovery; unchanged automatic resubmission is not advised.')
    if isinstance(error, RunCheckerError) and error.category in {'integrity_failure', 'admission_defect'}:
        return _failure('fail', error.category, 'submission_control_failure',
            'A declared control invariant failed. Root must inspect the retained diagnostic and repair control state before choosing recovery; a preceding connection or lock error does not authorize retry.')
    for e in causes:
        if isinstance(e, sqlite3.OperationalError) and (
                (getattr(e, 'sqlite_errorcode', 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
                or str(e) in {'database is locked', 'database table is locked'}):
            return _retry()
    if any(isinstance(e, ConnectionError) for e in causes):
        return _retry()
    if any(isinstance(e, TimeoutError) for e in causes):
        return _failure('intervene', 'runtime_failure', 'submission_timeout_unclassified',
            'A timeout outside a declared finalization or validation budget needs investigation. Root must inspect whether it was a connection interruption or an exhausted budget before retrying; preserve the report and do not rerun the solver.')
    if isinstance(error, (RunCheckerError, RunContractUnavailable)):
        return _failure('fail', getattr(error, 'category', 'integrity_failure'), 'submission_control_failure',
            'The task cannot complete under its frozen control contract. Root must inspect the retained diagnostic and recovery details before continuing; do not rewrite scientific conclusions to bypass this failure.')
    if isinstance(error, RunOutputError):
        return SubmissionFailure('reject', error.category, error.details)
    if isinstance(error, ToolInputError) and len(error.details) == 1:
        item = error.details[0]
        if item['message'] in _CANDIDATE_CORRECTIONS.get(item['code'], ()):
            return SubmissionFailure('reject', 'output_rejected', (contract_diagnostic(
                item['code'], phase='output_payload', affected_action='submit', path=item['path'],
                repairable=True, message=item['message'] + ' Correct the current candidate file, capture declaration or citation within the frozen task contract, then resubmit. Do not change sealed evidence or permissions, or rerun execution.'),))
        candidate = classify_candidate_attachment_error(error, runs=runs, run_id=run_id)
        if candidate is not None:
            return candidate
        if item['message'] in _CAPTURE_BUDGETS.get(item['code'], ()):
            # Failure to fit this candidate does not prove that a compliant
            # correction exists. Immutable receipts consume the same fixed cap.
            details = (contract_diagnostic(item['code'], phase='output_payload',
                affected_action='submit', path=item['path'], repairable=False,
                message=item['message']), *_failure('intervene', 'runtime_failure',
                    'submission_intervention_required',
                    'Fixed capture budget exceeded. Existing immutable attachment receipts cannot be deleted; capture_sources cannot shrink frozen contract roots. Do not retry unchanged, alter provenance, raise budgets or rerun execution. Correct current files/declarations only if required evidence fits the frozen contract. Otherwise Root must start a new task using selected exact sealed materials, or use run_record_failure to close this task and retain its draft.').details)
            return SubmissionFailure('intervene', 'runtime_failure', details)
    if isinstance(error, DiagnosticError):
        # repairable does not identify the repair owner or make a frozen binding
        # editable by this Worker. Only the explicit candidate allowlist above
        # and output errors promise a caller-correctable submission.
        return _failure('intervene', 'runtime_failure', 'submission_intervention_required',
            'Submission requires control intervention. Root must inspect the retained diagnostic and repair the exact control binding, or use run_record_failure to close this task and retain its draft. The Worker must not repeatedly resubmit or rerun the solver.')
    if isinstance(error, WorkspaceOutputError):
        return _failure('reject', 'output_rejected', 'output_invalid',
            'Correct the declared candidate files before resubmitting.', repairable=True)
    if isinstance(error, WorkspaceError):
        return _failure('fail', 'integrity_failure', 'submission_integrity_failure',
            'Candidate workspace integrity could not be established. Root must inspect the retained diagnostic before recovery.')
    return _failure('intervene', 'runtime_failure', 'submission_intervention_required',
        'An unclassified control failure interrupted submission. Preserve the unchanged report. Root must inspect the stored engineering diagnostic before retrying, or use run_record_failure to close the task and recover its materials; automatic retry is not advised.')


def _failure(disposition, category, code, message, *, repairable=False):
    return SubmissionFailure(disposition, category, (contract_diagnostic(code,
        phase='protocol', affected_action='submit', repairable=repairable, message=message),))


def _retry():
    return _failure('retry', 'runtime_failure', 'submission_temporarily_unavailable',
        'A temporary storage or connection failure interrupted submission. Preserve the unchanged report and retry after the control service recovers. Existing receipts and publication identities will be reused; do not rerun the solver.', repairable=True)
