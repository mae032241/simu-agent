"""Materialize mechanical copies in new drafts; never rewrite bound Artifacts."""
from __future__ import annotations

import json
from typing import Callable

from ...operations.workspace import WorkspaceFinalizationRequest, WorkspaceProtocolError
from ..schema.common import canonical_json


def finalize_result(request: WorkspaceFinalizationRequest, project: Callable[[dict], None]) -> bytes:
    path = request.workspace / 'output' / 'result.json'
    # This runs before the regular output seal. Keep the same bounded file boundary.
    if path.is_symlink() or not path.is_file():
        raise WorkspaceProtocolError('output/result.json must be a regular file')
    with path.open('rb') as stream:
        raw = stream.read(request.output_limit_bytes + 1)
    if len(raw) > request.output_limit_bytes:
        raise WorkspaceProtocolError('output/result.json exceeds its byte limit')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        # The existing envelope checker owns malformed JSON and its diagnostics.
        return raw
    if isinstance(value, dict) and isinstance(value.get('payload'), dict):
        original = json.loads(raw)
        project(value)
        if value != original:
            return canonical_json(value)
    return raw


def materialize_intake(value: dict) -> None:
    foundation = value.get('scientific_foundation')
    if not isinstance(foundation, dict):
        return
    contract = foundation.get('objective_contract')
    # The formal objective contract is authoritative when present. Otherwise the
    # foundation's objective is the one authored statement. Never pick by text similarity.
    if isinstance(contract, dict) and isinstance(contract.get('statement'), str):
        foundation['objective'] = contract['statement']
    if isinstance(value.get('problem_frame'), dict) and isinstance(foundation.get('objective'), str):
        value['problem_frame']['objective'] = foundation['objective']


def materialize_analysis_handoff(value: dict) -> None:
    """Project only duplicate transport fields from the analyst's formal report."""
    payload = value['payload']
    verdict = {'pass': 'pass', 'fail': 'blocked', 'invalid_study': 'blocked',
               'inconclusive': 'inconclusive'}.get(str(payload.get('overall_verdict')))
    if verdict is None or not isinstance(payload.get('summary'), str):
        return  # Missing scientific content belongs to the existing output checker.
    handoff = value.setdefault('handoff', {})
    if isinstance(handoff, dict):
        handoff['verdict'] = verdict
        handoff['summary'] = 'Read run_status.sealed_output.payload.summary for the scientific conclusion; payload.next_action contains any scientific recommendation.'


def materialize_summary_handoff(value: dict, verdict: str | None) -> None:
    """Fill omitted transport fields from a formal summary; preserve explicit notes."""
    # A draft may omit handoff. Name the actual source of an impossible copy,
    # before envelope validation mistakes absent generated fields for authored omissions.
    if verdict is None:
        raise WorkspaceProtocolError('Cannot derive handoff verdict from the formal result', details=({
            'path': '$.payload.verdict', 'message': 'Formal verdict must use a value allowed by the output Schema to generate handoff.verdict.',
            'type': 'field_projection_unavailable'},))
    if not isinstance(value['payload'].get('summary'), str):
        raise WorkspaceProtocolError('Cannot reference the formal summary', details=({
            'path': '$.payload.summary', 'message': 'Formal summary must be a string as declared by the output Schema.',
            'type': 'field_projection_unavailable'},))
    handoff = value.setdefault('handoff', {})
    if isinstance(handoff, dict):
        handoff['verdict'] = verdict
        handoff.setdefault('summary', 'Read the sealed payload.summary for the scientific conclusion.')


def materialize_general_result(value: dict, schema_id: str) -> None:
    payload = value['payload']
    verdict = None
    if schema_id == 'scidiscovery.layered-diagnosis.v1':
        materialize_analysis_handoff(value)
    elif schema_id == 'scidiscovery.scientific-intake.v1':
        materialize_intake(payload)
    elif schema_id == 'scidiscovery.experiment-portfolio.v1':
        for proposal in (payload['proposals'] if isinstance(payload.get('proposals'), list) else ()):
            if not isinstance(proposal, dict):
                continue
            cases, estimate = proposal.get('cases'), proposal.get('resource_estimate')
            if isinstance(cases, list) and isinstance(estimate, dict):
                estimate['case_count'] = len(cases)
            objectives = proposal.get('objectives', [])
            if isinstance(objectives, list) and all(isinstance(item, str) for item in objectives) and isinstance(payload.get('objective'), str):
                proposal['objectives'] = list(dict.fromkeys([payload['objective'], *objectives]))
    elif schema_id == 'scidiscovery.scientific-review.v1':
        verdict = {'pass': 'pass', 'revise': 'revise', 'reject': 'blocked', 'blocked': 'blocked', 'inconclusive': 'inconclusive'}.get(str(payload.get('verdict')))
        materialize_summary_handoff(value, verdict)
    elif schema_id == 'scidiscovery.critic-review.v2':
        verdict = {'ready_for_experiment': 'pass', 'revise_hypothesis': 'revise',
                   'revise_evidence': 'inconclusive', 'design_model_counterfactual': 'pass',
                   'inconclusive': 'inconclusive', 'reject': 'blocked'}.get(str(payload.get('disposition')))
    elif schema_id == 'scidiscovery.evidence-audit.v1':
        checks = payload.get('checks')
        if isinstance(checks, list) and checks and all(isinstance(item, dict) for item in checks):
            statuses = {str(item.get('status')) for item in checks}
            verdict = 'blocked' if 'fail' in statuses else 'inconclusive' if 'unknown' in statuses else 'pass'
    if verdict is not None and isinstance(value.get('handoff'), dict):
        value['handoff']['verdict'] = verdict


def finalize_general_result(request: WorkspaceFinalizationRequest) -> bytes:
    return finalize_result(request, lambda value: materialize_general_result(value, request.output_schema_id))
