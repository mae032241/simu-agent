"""Real scientific task fixtures reusing existing frame/foundation objects."""
import json
from urllib.parse import parse_qs, urlparse

from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.research_objective import declared_objective
from tests.operations.test_general_transform_operations import _intake
from tests.operations.test_historical_compatibility_paths import _artifact, _complete
from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal


def sealed_hypothesis(runtime, root, instance, goal_name):
    source = _artifact(runtime, instance, goal_name)
    raw = runtime.artifacts.read(source.ref)
    try:
        _, goal = declared_objective(json.loads(raw))
    except ValueError:
        goal = None
    if goal is None:
        proposal = _proposal(hypothesis_keys=('mechanism',))
        proposal.pop('research_objective_key')
        subject = _complete(runtime, root, goal_name + '.hypothesis', 'science.hypothesis.propose.v1',
            {'subject': goal_name}, proposal)
        return subject, goal_name
    foundation = json.loads(_foundation(goal['objective_key']))
    foundation.update(objective=goal['statement'], objective_contract=goal)
    frame = _intake().model_dump(mode='json')['problem_frame']
    frame.update(objective=goal['statement'], foundation_item_keys=['target_item'])
    for observable in frame['observables']:
        observable['foundation_item_keys'] = ['target_item']
    intake_payload = {'problem_frame': frame, 'scientific_foundation': foundation}
    intake_payload = json.loads(canonical_json(intake_payload).replace(b'"source"', b'"source_material"'))
    intake = _complete(runtime, root, goal_name + '.prepare', 'science.evidence.extract.v1',
        {'source_material': goal_name}, intake_payload)
    audit = _complete(runtime, root, goal_name + '.audit', 'science.evidence.audit.intake.v1',
        {'scientific_intake': intake}, {'checks': [{'check_key': 'source_traceability',
            'subject': 'Fixture source', 'status': 'pass', 'basis': 'Exact source.',
            'evidence_keys': ['source_material']}], 'evidence': [{'source_key': 'source_material',
                'source_type': 'frozen_input', 'locator': 'source'}]})
    frame_name = goal_name + '.prepared'
    root.call_tool('operation_invoke', {'name': frame_name, 'operation_id': 'science.intake.split.v1',
        'inputs': [{'port': 'scientific_intake', 'artifact_names': [intake]},
                   {'port': 'evidence_audit', 'artifact_names': [audit]}]})
    foundation_name = frame_name + '.scientific_foundation'
    name = goal_name + '.qualify'
    root.call_tool('operation_invoke', {'name': name, 'operation_id': 'science.evidence.qualify.v1',
        'inputs': [{'port': 'scientific_foundation', 'artifact_names': [foundation_name]}]})
    approval_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='approval', name=name)
    status = runtime.approvals.status(approval_id)
    token = parse_qs(urlparse(status.review_path).query)['token'][0]
    review = runtime.approvals.review(approval_id, access_token=token)
    runtime.approvals.record_ui_decision(approval_id=approval_id, access_token=token,
        csrf_token=review.csrf_token, decision_nonce=review.decision_nonce,
        selected_option='approve', rationale='Existing fixture foundation is qualified.',
        decided_by=LocalIdentityRef(identity_id='fixture_reviewer', display_name='Fixture reviewer'),
        ui_session_id='scientific-chain-fixture')
    subject = _complete(runtime, root, goal_name + '.hypothesis', 'science.hypothesis.propose.v1',
        {'scientific_foundation': foundation_name, 'problem_frame': frame_name},
        _proposal(goal['objective_key'], hypothesis_keys=('mechanism',)))
    return subject, foundation_name
