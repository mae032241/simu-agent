"""One lifecycle policy for failures anywhere in a Run submission.

This classifies declared failures, not scientific conclusions. Unknown exceptions
require intervention; only explicitly transient failures recommend unchanged retry.
"""
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SubmissionFailure:
    disposition: str
    category: str
    details: tuple


def classify_submission_error(error, *, deadline_expired=False):
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
