"""Real task-local seal, immutable versions, inventory and original readers."""

import pytest


@pytest.mark.parametrize('invalid', ['private_root','whole_scratch','source_port','capability'])
def test_capture_contract_invalid_scope_or_capability_fails_at_compile(invalid):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import compile_catalog, CatalogCompileError
    op = next(op for op in PLUGIN.operations if op.operation_id == 'science.evidence.extract.v1')
    changes = {'private_root':{'roots':('scratch/credentials',)}, 'whole_scratch':{'roots':('scratch',)},
        'source_port':{'required_source_ports':('absent',)}}
    if invalid == 'capability':
        changed = op.model_copy(update={'executor':op.executor.model_copy(update={
            'native_tools':op.executor.native_tools.model_copy(update={'shell':'none'})})})
    else:
        changed = op.model_copy(update={'artifact_capture':op.artifact_capture.model_copy(update=changes[invalid])})
    revised = PLUGIN.model_copy(update={'operations':tuple(changed if current.operation_id == changed.operation_id else current for current in PLUGIN.operations)})
    with pytest.raises(CatalogCompileError) as failure:
        compile_catalog((CORE_PLUGIN,revised))
    assert failure.value.reason_code == 'artifact_capture_invalid'


def test_source_capture_roots_and_stage_authoring_schema_preserve_sealed_contract(source_catalog, tmp_path):
    source_catalog()
    from jsonschema import Draft202012Validator
    from pydantic import ValidationError
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.artifact_agent.schema.validation import ValidationCheckResult
    from scidiscovery.general_science_experiment_task import StageSubmission
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import compile_catalog, compile_installed_catalog
    catalog = compile_installed_catalog()
    stage = next(tool for tool in catalog.operation('science.experiment.v1').worker_tools if tool.name == 'worker_experiment_stage')
    old = 'file@tool_evidence_001:scratch/artifacts/result.csv'
    request = {'stage':'validity', 'conclusion':'Compare the exact old version.', 'comparison':{
        'prediction':'tool_evidence_002', 'observations':[old], 'result':{
            'check_key':'sum', 'status':'pass', 'evaluation_mode':'deterministic_threshold',
            'observed_value':4.0, 'observed_text':'The retained sum is 4.', 'unit':'dimensionless',
            'evidence_keys':[old], 'rationale':'Retain the declared criterion.'}}}
    Draft202012Validator(stage.input_model.model_json_schema()).validate(request)
    stage.input_model.model_validate_json(canonical_json(request), strict=True)
    assert ValidationCheckResult.model_json_schema()['properties']['evidence_keys']['items']['pattern'] == r'^[A-Za-z0-9][A-Za-z0-9_.:/-]*$'
    try:
        StageSubmission.model_validate_json(canonical_json(request), strict=True)
    except ValidationError:
        pass
    else:
        raise AssertionError('sealed identifiers accepted raw file@ navigation')
    request['comparison']['result'].pop('unit')
    try:
        stage.input_model.model_validate_json(canonical_json(request), strict=True)
    except ValidationError:
        pass
    else:
        raise AssertionError('draft input lost scientific unit validation')
