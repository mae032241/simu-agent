"""Current task outputs retain bounded scientific decisions and exact UI sources."""
from copy import deepcopy
import json
import pytest
from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.presentation_render import render_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_instance_presentations import installed, view
from tests.operations.test_instance_read_model import system, bind
from tests.operations.test_m2_parameter_package import _package
from tcad_artifact.parameter_operations import ParameterEvidencePackage
from tcad_artifact.device_parameters import evaluate_device_parameter_coverage


@pytest.mark.parametrize('schema,payload,label,path', [
    ('scidiscovery.experiment-report.v1', {'summary':'实验仍缺少有效观测。','outcome':'blocked','limitations':['不足以判断'],'remaining_question':'需要哪项观测？'}, '实验结果', '/outcome'),
    ('scidiscovery.experiment-review.v1', {'summary':'需要修订证据。','verdict':'revise','findings':['补充原始观测'],'limitations':[]}, '审查结论','/verdict'),
])
def test_current_reports_have_exact_conclusion_cards(installed, schema, payload, label, path):
    result = presentation.build_presentation((view('report', schema, payload),), focus_artifact_ids=['report'])
    facts = [item for section in result['sections'] for item in section['items']]
    assert any(item['label']==label and item['source']=={'artifact_id':'report','json_pointer':path} for item in facts)
    html = render_presentation(result, evidence_href=lambda aid,p:f'/evidence/{aid}?pointer={p}', image_href=lambda aid:f'/image/{aid}')
    assert 'tone-attention' in html and payload['summary'] in html
    assert 'schema_presentation_unavailable' not in str(result)


def test_intake_open_questions_keep_exact_nested_source(installed):
    payload = _package().scientific_intake.model_dump(mode='json')
    payload['scientific_foundation']['open_questions'] = ['关键未解决问题']
    result = presentation.build_presentation((view('intake','scidiscovery.scientific-intake.v1',payload),), focus_artifact_ids=['intake'])
    facts = [item for section in result['sections'] for item in section['items']]
    assert any(item['value']==['关键未解决问题'] and item['source']['json_pointer']=='/scientific_foundation/open_questions' for item in facts)
    assert '/scientific_foundation/open_questions' in presentation.presentation_pointers('scidiscovery.scientific-intake.v1')


def _large_package():
    raw = _package().model_dump(mode='json')
    original_requirement = raw['parameter_requirements']['parameters'][0]
    original_claim = raw['device_parameters']['claims'][0]
    raw['parameter_requirements']['parameters'] = []
    raw['device_parameters']['claims'] = []
    for i in range(24):
        key = f'scale_{i}'
        raw['parameter_requirements']['parameters'].append({**deepcopy(original_requirement),'parameter_key':key,'display_name':f'Scale {i}'})
        raw['device_parameters']['claims'].append({**deepcopy(original_claim),'parameter_key':key,'selection_rationale':'Exact source rationale. '*150})
    package = ParameterEvidencePackage.model_validate_json(canonical_json(raw), strict=True)
    raw['coverage'] = evaluate_device_parameter_coverage(package.parameter_requirements, package.device_parameters, package.source_catalog).model_dump(mode='json')
    ParameterEvidencePackage.model_validate_json(canonical_json(raw), strict=True)
    assert 65536 < len(canonical_json(raw)) < 4*1024*1024
    return raw


def test_large_parameter_package_summary_and_paginated_nested_sources(system, installed):
    raw = _large_package()
    envelope = system.artifacts.register(canonical_json(raw), ArtifactRegistration(kind='parameter_evidence_package',
        schema_id='scidiscovery.parameter-evidence-package.v1',payload_schema_version=1,media_type='application/json',creator=system.actor),idempotency_key='package')
    bind(system, system.a, 'artifact', 'package', envelope.artifact_id)
    projected = system.model._presentation_view(system.a, envelope)
    assert projected['payload_state'] == 'available'
    assert len(canonical_json(projected['payload'])) <= 65536
    result = presentation.build_presentation((projected,),focus_artifact_ids=[envelope.artifact_id])
    facts = [item for section in result['sections'] for item in section['items']]
    assert any(item['source']['json_pointer']=='/coverage/status' and item['value']==raw['coverage']['status'] for item in facts)
    assert any(item['source']['json_pointer']=='/scientific_intake/scientific_foundation/summary' for item in facts)
    assert result['parameter_documents'] == [{'artifact_id':envelope.artifact_id,'json_pointer':''}]
    context = system.model.parameter_context(system.a,envelope.artifact_id)
    # A same-key catalog elsewhere in the authorized cohort cannot replace the package's own source.
    unrelated = view('unrelated', 'scidiscovery.evidence-source-catalog.v1', {'sources':[{
        **raw['source_catalog']['sources'][0], 'title':'UNRELATED_PRIVATE_CONTROL_MARKER'}]})
    paths = []
    for offset in (0,8,16):
        page = presentation.build_parameter_page(context['artifact'],[*context['dependencies'], unrelated],after=offset,limit=8)
        assert page['parameter_page']['total']==24
        assert len(page['parameters'])==8
        for index,row in enumerate(page['parameters'],offset):
            assert row['name']==f'Scale {index}'
            assert row['source']=={'artifact_id':envelope.artifact_id,'json_pointer':f'/device_parameters/claims/{index}'}
            assert row['sources'][0]['source']['json_pointer']=='/source_catalog/sources/0'
            assert row['field_sources']['name']['json_pointer']==f'/parameter_requirements/parameters/{index}/display_name'
            paths.append(row['source']['json_pointer'])
        assert not any(gap['code']=='provider_unavailable' for gap in page['gaps'])
        assert 'UNRELATED_PRIVATE_CONTROL_MARKER' not in json.dumps(page)
        assert len(canonical_json(page)) < presentation.MAX_PRESENTATION_BYTES
    assert len(set(paths))==24
    assert 'recovery_manifest_output' not in json.dumps(result)
    assert '/scientific_intake/scientific_foundation/evidence' not in presentation.presentation_pointers(envelope.schema_id)
