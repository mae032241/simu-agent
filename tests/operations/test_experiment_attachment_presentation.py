"""Completed experiment pictures survive large input histories and manifest records."""
from types import SimpleNamespace
from copy import deepcopy
from urllib.parse import urlencode

import pytest

from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.presentation_render import render_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.general_science_views import build_presentation as general
from tests.operations.test_instance_read_model import system, bind, approval
from tests.operations.test_instance_trajectory_read import trajectory, artifact, stored_run
from tests.operations.test_instance_content_display import picture


@pytest.fixture(params=(12, 110), ids=("short-history", "over-100-parents"))
def experiment_figures(trajectory, monkeypatch, request):
    s = trajectory
    s.runs.artifacts = s.artifacts
    labels = dict(operation_id='science.experiment.v1', operation_version='1', operation_digest='a'*64)
    wide = tuple((f'source_{i}', artifact(s, f'wide_{i}', {'value': 'wide input ' * 2600}).ref) for i in range(request.param))
    records, images = [], []
    # These records used to consume the /records display quota before pictures.
    for i in range(20):
        records.append({'alias':f'tool_evidence_{i:03d}', 'metadata':{'calculation': 'unrelated calculation detail ' * 200}})
    for index, (name, media, raw) in enumerate((('fig4_overlay.svg', 'image/svg+xml', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
                                               ('fig4_overlay.png', 'image/png', picture('blue'))), 4):
        image = s.artifacts.register(raw, ArtifactRegistration(kind='scientific_attachment',schema_id='opaque',
            payload_schema_version=1,media_type=media,creator=s.actor,parent_refs=tuple(ref for _, ref in wide),
            labels={**labels, 'tool_producer_run':'experiment', 'operation_output_port':'attachments'}),idempotency_key=name)
        images.append(image)
        records.append({'alias':f'attachment_{index:03d}', 'artifact_ref':image.ref.model_dump(mode='json'),
            'media_type':media,'size_bytes':image.size_bytes,'output_port':'attachments',
            'metadata':{'kind':'scientific_attachment','file_name':name,'purpose':'Fig.4 measured and H0/H1 curves'}})
    manifest = artifact(s, 'manifest', {'records': records, 'bindings': {
        r['alias']:{'artifact_ref':r['artifact_ref'],'port_name':'attachments'} for r in records if 'artifact_ref' in r}},
        schema='scidiscovery.tool-evidence-manifest.v1', parents=tuple(ref for _, ref in wide)+tuple(x.ref for x in images),
        labels={**labels,'tool_producer_run':'experiment','operation_output_port':'recovery_manifest_output'})
    report = artifact(s,'report',dict(outcome='inconclusive',summary='Actual experiment comparison',
        limitations=['fixture'],remaining_question='next',adopted_stages=[]),schema='scidiscovery.experiment-report.v1',
        parents=tuple(ref for _, ref in wide)+(manifest.ref,), labels={**labels,'operation_output_port':'experiment_report'},instance=s.a)
    stored_run(s,'experiment',inputs=wide,output=report.ref,operation='science.experiment.v1')
    monkeypatch.setattr(presentation,'entry_points',lambda **_: (SimpleNamespace(name='general',load=lambda:general),))
    return s, report, manifest, images


@pytest.mark.parametrize('surface',['run','artifact','approval'])
def test_experiment_attachments_render_without_author_evidence_fields(experiment_figures, surface):
    s, report, manifest, images = experiment_figures
    if surface=='approval':
        launch=approval(s,'review',(report.ref,))
        context=s.model.approval_context(s.a,s.approvals.review('review',access_token=launch.access_token),presentation=True)
    else:
        context=s.model.node_context(s.a,'run:experiment' if surface=='run' else 'artifact:report')
    ids=[a['artifact_id'] for a in context['artifacts']]
    assert ids[:4]==[report.artifact_id,manifest.artifact_id,images[1].artifact_id,images[0].artifact_id]
    result=presentation.build_presentation(context['artifacts'],focus_artifact_ids=[report.artifact_id])
    assert [f['artifact_id'] for f in result['figures']]==[images[1].artifact_id]
    assert result['figures'][0]['source']=={'artifact_id':manifest.artifact_id,'json_pointer':'/records/21'}
    page=render_presentation(result,evidence_href=lambda a,p:f'/evidence/{a}',image_href=lambda a:f'/image/{a}')
    assert 'fig4_overlay.png' in page and 'fig4_overlay.svg' in page and '<img ' in page
    assert '不代表已审查' in page and '下载原图' in page


@pytest.mark.parametrize('damage',['binding','digest','duplicate'])
def test_attachment_projection_preserves_exact_binding_checks(experiment_figures, damage):
    s, report, manifest, images=experiment_figures
    context=s.model.node_context(s.a,'run:experiment')
    cohort=deepcopy(context['artifacts'])
    view=next(a for a in cohort if a['artifact_id']==manifest.artifact_id)
    if damage=='binding':view['payload']['bindings']['attachment_005']['port_name']='tool_evidence'
    elif damage=='digest':view['payload']['records'][21]['artifact_ref']['sha256']='f'*64
    else:view['payload']['records'].append(deepcopy(view['payload']['records'][21]))
    result=presentation.build_presentation(cohort,focus_artifact_ids=[report.artifact_id])
    assert result['figures']==[]
    assert any(g['code']=='attachment_reference_missing_or_ambiguous' for g in result['gaps'])


@pytest.mark.process_e2e
def test_experiment_page_serves_full_png_and_svg_download_with_exact_scope(experiment_figures):
    from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
    from scidiscovery.artifact_agent.approval_ui.access import access_cookie
    from tests.operations.test_instance_browser_http import _request
    s, report, _, images=experiment_figures
    launch=approval(s,'frozen-figure',(report.ref,))
    ui=ApprovalUI(s.approvals,bindings=s.bindings,read_model=s.model,instance_management_secret=b'p'*32)
    base=ui.start()
    cookie=access_cookie(s.a,ui.browser_access.issue(s.a))
    try:
        status,_,page=_request(base,'GET',f'/instance/{s.a}/nodes/run%3Aexperiment',cookie=cookie)
        assert status==200 and 'fig4_overlay.png' in page.decode() and '<img ' in page.decode()
        for image,mode in zip(images,('download','image')):
            route=f'/instance/{s.a}/evidence/{image.artifact_id}?format={mode}'
            status,headers,body=_request(base,'GET',route,cookie=cookie)
            assert status==200 and body==s.artifacts.read(image.ref)
            if mode=='download':
                assert 'attachment' in headers['Content-Disposition']
            frozen=f'/review/frozen-figure/evidence/{image.artifact_id}?'+urlencode({'token':launch.access_token,'format':mode})
            assert _request(base,'GET',frozen)[0]==200
            assert _request(base,'GET',route.replace(s.a,s.b),cookie=cookie)[0]==403
        outsider=s.artifacts.register(picture('red'),ArtifactRegistration(kind='scientific_attachment',schema_id='opaque',
            payload_schema_version=1,media_type='image/png',creator=s.actor),idempotency_key='not-published')
        assert _request(base,'GET',f'/instance/{s.a}/evidence/{outsider.artifact_id}?format=image',cookie=cookie)[0]==403
    finally:
        ui.stop()
