"""Current sealed figure Intake attachments reach UI without author-supplied IDs."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from curve_figure_evidence.instance_views import build_presentation as figures
from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.presentation_render import render_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_instance_read_model import system, bind, run, approval
from tests.operations.test_instance_content_display import picture, register
from tests.operations.test_instance_browser_http import _request
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from urllib.parse import urlencode
from tests.operations.test_instance_archive import archive_system, save_archive, restore_archive


@pytest.fixture
def figure_providers(monkeypatch):
    monkeypatch.setattr(presentation, 'entry_points', lambda **_: (
        SimpleNamespace(name='curve_figure_evidence', load=lambda: figures),))


def _seed_family(system):
    labels = {'operation_id': 'science.evidence.extract.figure.v3', 'operation_version': '1',
              'operation_digest': 'a' * 64, 'tool_producer_run': 'extract'}
    def save(name, payload, schema='opaque', media='application/json', parents=(), port='tool_evidence'):
        return system.artifacts.register(payload if isinstance(payload, bytes) else canonical_json(payload),
            ArtifactRegistration(kind='fixture', schema_id=schema, payload_schema_version=1,
                media_type=media, creator=system.actor, parent_refs=parents,
                labels={**labels, 'operation_output_port': port}), idempotency_key=name)
    images, records, bindings = [], [], {}
    for i, name in enumerate(('source_panels/main.png', 'audit_overlays/main--numeric-redraw.png',
                              'audit_overlays/main--identity-fidelity.png', 'curve_tables/main--line.csv'), 1):
        media = 'text/csv' if name.endswith('.csv') else 'image/png'
        image = save(name, b'x,y\n1,2\n2,3\n' if media == 'text/csv' else picture(('white', 'blue', 'red')[i-1]), media=media)
        images.append(image)
        alias = f'tool_evidence_{i:03d}'
        records.append({'alias': alias, 'artifact_ref': image.ref.model_dump(mode='json'),
            'media_type': media, 'size_bytes': image.size_bytes,
            'tool_name': 'worker_curve_figure_save', 'metadata': {'kind': 'figure_file', 'data_item': name}})
        bindings[alias] = {'port_name': 'tool_evidence', 'artifact_ref': image.ref.model_dump(mode='json')}
    manifest = save('manifest', {'records': records, 'bindings': bindings},
        schema='scidiscovery.tool-evidence-manifest.v1', parents=tuple(i.ref for i in images),
        port='recovery_manifest_output')
    intake = save('intake', {'scientific_foundation': {'summary': 'Extracted figure', 'evidence': []}},
        schema='scidiscovery.scientific-intake.v1', parents=(manifest.ref,), port='scientific_intake')
    bind(system, system.a, 'artifact', 'intake', intake.artifact_id)
    return system, intake, manifest, images


@pytest.fixture
def figure_context(system, figure_providers):
    family = _seed_family(system)
    run(system, 'extract', output=family[1].ref)
    return family


@pytest.mark.parametrize('key', ['artifact:intake', 'run:extract'])
def test_sealed_intake_images_render_without_manual_evidence_citations(figure_context, key):
    s, intake, manifest, images = figure_context
    context = s.model.node_context(s.a, key)
    result = presentation.build_presentation(context['artifacts'], focus_artifact_ids=context['focus_artifact_ids'])
    assert [f['label'] for f in result['figures']] == ['论文原图', 'CSV 数值重绘', '原图叠点检查']
    assert {f['artifact_id'] for f in result['figures']} == {i.artifact_id for i in images[:3]}
    assert all(f['source']['artifact_id'] == manifest.artifact_id for f in result['figures'])
    html = render_presentation(result, evidence_href=lambda aid, p: f'/evidence/{aid}?pointer={p}',
                               image_href=lambda aid: f'/image/{aid}')
    assert html.count('<img ') == 3
    assert '图件与结果对照' in html
    assert '下载 CSV' in html


@pytest.mark.parametrize('damage', ['missing_image', 'wrong_hash', 'wrong_size', 'wrong_binding',
    'missing_parent', 'duplicate_alias', 'different_operation', 'different_run', 'partial_manifest'])
def test_intake_does_not_display_unbound_or_partial_images(figure_context, damage):
    s, intake, manifest, images = figure_context
    context = deepcopy(s.model.node_context(s.a, 'run:extract'))
    cohort = context['artifacts']
    m = next(a for a in cohort if a['artifact_id'] == manifest.artifact_id)
    image = next(a for a in cohort if a['artifact_id'] == images[0].artifact_id)
    record = m['payload']['records'][0]
    if damage == 'missing_image': cohort.remove(image)
    elif damage == 'wrong_hash': image['ref']['sha256'] = 'b' * 64
    elif damage == 'wrong_size': image['size_bytes'] += 1
    elif damage == 'wrong_binding': m['payload']['bindings'][record['alias']]['port_name'] = 'other'
    elif damage == 'missing_parent': m['provenance'] = m['provenance'][1:]
    elif damage == 'duplicate_alias': m['payload']['records'].append(deepcopy(record))
    elif damage == 'different_operation': m['family']['operation_digest'] = 'b' * 64
    elif damage == 'different_run': m['family']['tool_producer_run'] = 'other_run'
    elif damage == 'partial_manifest': m['gaps'].append({'code': 'display_field_partial'})
    result = presentation.build_presentation(cohort, focus_artifact_ids=context['focus_artifact_ids'])
    assert images[0].artifact_id not in {f['artifact_id'] for f in result['figures']}
    assert any(g['code'].startswith('figure_intake_') for g in result['gaps'])
    assert not any(g['code'] == 'provider_unavailable' for g in result['gaps'])


@pytest.mark.parametrize('schema', ['scidiscovery.evidence-audit.v1', 'scidiscovery.curve-bundle.v1',
    'scidiscovery.scientific-foundation.v1', 'scidiscovery.experiment-review.v1'])
def test_downstream_deliveries_keep_exact_figure_ancestry(figure_context, schema):
    s, intake, manifest, images = figure_context
    register(s, 'downstream', schema, {}, parents=(intake.ref,))
    context = s.model.node_context(s.a, 'artifact:downstream')
    result = presentation.build_presentation(context['artifacts'], focus_artifact_ids=context['focus_artifact_ids'])
    assert {f['artifact_id'] for f in result['figures']} == {i.artifact_id for i in images[:3]}
    assert all(f['source']['artifact_id'] == manifest.artifact_id for f in result['figures'])


def test_intake_http_images_csv_and_frozen_approval_scope(figure_context):
    s, intake, manifest, images = figure_context
    outsider = register(s, 'outsider', 'opaque', {}, raw=picture('green'), media='image/png', instance=s.b)
    launch = approval(s, 'figure-review', (intake.ref,))
    ui = ApprovalUI(s.approvals, bindings=s.bindings, read_model=s.model, instance_management_secret=b'p'*32)
    base = ui.start()
    cookie = access_cookie(s.a, ui.browser_access.issue(s.a))
    try:
        status, _, page = _request(base, 'GET', f'/instance/{s.a}/nodes/artifact%3Aintake', cookie=cookie)
        assert status == 200 and page.count(b'<img ') == 3 and '下载 CSV' in page.decode()
        for member in images:
            mode = 'download' if member.media_type == 'text/csv' else 'image'
            path = f'/instance/{s.a}/evidence/{member.artifact_id}?format={mode}'
            status, _, content = _request(base, 'GET', path, cookie=cookie)
            assert status == 200 and content == s.artifacts.read(member.ref)
            path = f'/review/figure-review/evidence/{member.artifact_id}?' + urlencode({'token':launch.access_token,'format':mode})
            assert _request(base, 'GET', path)[0] == 200
        path = f'/review/figure-review/evidence/{outsider.artifact_id}?' + urlencode({'token':launch.access_token,'format':'image'})
        assert _request(base, 'GET', path)[0] == 403
    finally:
        ui.stop()


def test_archived_figure_family_retains_rendering_and_exact_originals(archive_system, figure_providers):
    runtime, archive, instance, _ = archive_system
    s = SimpleNamespace(actor=runtime.actor, artifacts=runtime.artifacts,
        bindings=runtime.scheduler_bindings, a=instance)
    _, intake, manifest, files = _seed_family(s)
    originals = {f.ref: runtime.artifacts.read(f.ref) for f in files}
    save_archive(archive, instance)
    model = archive.archived_model(instance)
    context = model.node_context(instance, 'artifact:intake')
    result = presentation.build_presentation(context['artifacts'], focus_artifact_ids=context['focus_artifact_ids'])
    assert len(result['figures']) == 3
    assert any(section.get('kind') == 'curve_evidence' for section in result['sections'])
    for ref, raw in originals.items():
        assert model.artifact_reference(instance, ref.artifact_id) == ref
        with model.artifacts.open_original(ref) as stream:
            assert stream.read() == raw
    restore_archive(archive, instance)
    assert all(runtime.artifacts.read(ref) == raw for ref, raw in originals.items())
