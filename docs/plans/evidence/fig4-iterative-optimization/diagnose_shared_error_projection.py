"""Small serial model/diagnostic probes; synthetic data, no live mutations."""
import json
import resource
from pathlib import Path

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (45, 45))

from pydantic import ValidationError
from curve_score.schema import CurveInterval
from tcad_artifact.project_packager import RuntimeAssertion
from scidiscovery.artifact_agent.schema.layered_diagnosis import ScientificGateResult, CalculationRecord
from scidiscovery.artifact_agent.schema.scientific_output import ScientificRoleOutput
from scidiscovery.artifact_agent.service.run_outputs import _validation_details
from scidiscovery.operation_contract import SemanticRuleViolation, validation_diagnostics, sanitize_diagnostic_details, declared_violation

cases = [
    (ScientificRoleOutput, {'summary': 'synthetic diagnostic probe', 'findings': [
        {'finding_key': 'probe', 'statement': 'synthetic', 'epistemic_status': 'inference', 'evidence_keys': ['bound_source']}]}, 'output_payload', 'submit'),
    (ScientificGateResult, {'status': 'pass', 'summary': 'synthetic diagnostic probe'}, 'output_payload', 'submit'),
    (CurveInterval, {'start': 2.0, 'stop': 1.0}, 'tool_arguments', 'tool_call'),
    (RuntimeAssertion, {'description': 'synthetic diagnostic probe', 'expected_output_name': 'probe', 'assertion_kind': 'file_nonempty', 'required_columns': ['x']}, 'output_payload', 'submit'),
    (CalculationRecord, {'record_key': 'probe', 'input_digests': {}, 'request': {}, 'algorithm_version': 'probe', 'status': 'computed'}, 'output_payload', 'submit'),
]
rows = []
for model, payload, phase, action in cases:
    try:
        model.model_validate_json(json.dumps(payload), strict=True)
    except ValidationError as error:
        rows.append({'model': model.__name__, 'phase': phase,
            'raw': error.errors(include_input=False, include_context=False, include_url=False),
            'converted': validation_diagnostics(error, schema=model.model_json_schema(), phase=phase, action=action)})
    else:
        raise AssertionError('probe was unexpectedly accepted')

plain = _validation_details(SemanticRuleViolation('review evidence source_key must name an actual visible input alias'),
    schema={}, phase='output_context')
explicit = _validation_details(declared_violation('synthetic precise field relation', path='$.evidence'),
    schema={}, phase='output_context')
dict_projection = sanitize_diagnostic_details(({'path': '$.payload', 'message': 'synthetic precise static reason', 'type': 'value_error'},), schema={})
result = {'scope': 'Pure validator and diagnostic conversion probes; not a full Operation execution or full test suite.',
    'model_probes': rows, 'plain_semantic_exception': plain,
    'explicit_semantic_exception_control': explicit, 'plain_diagnostic_dictionary': dict_projection,
    'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
assert all(r['converted'][0]['message'] == 'Value violates the declared type, bounds, or field relationship.' for r in rows[:4])
assert rows[-1]['converted'][0]['path'] == '$.result'
assert rows[-1]['converted'][0]['message'] == 'computed record requires result and no reason'
Path(__file__).with_name('shared-diagnostic-probe-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
