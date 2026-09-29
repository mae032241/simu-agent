"""Public original paging and actual background omission links."""
import json
import pytest
from tests.operations.test_progression import progression, row
from scidiscovery.artifact_agent.service.progression import INSTRUCTION
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerNameNotFound


def test_original_pages_follow_brief_link_and_keep_unicode(progression, monkeypatch):
    p = progression
    text = '完成标准🌏a' * 5000
    ref = p.runtime.intake.ingest_text(content=text.encode())
    p.runtime.scheduler_bindings.bind(instance=p.instance, namespace='artifact', name='large-goal', object_id=ref.artifact_id)
    selected = {**row(p), 'objective_name':'large-goal', 'objective_ref_json':ref.canonical_json()}
    p.coordinator.instance = p.instance
    settings = p.runtime.runs.agent_settings
    p.runtime.runs.agent_settings = settings.model_copy(update={'input_materials':settings.input_materials.model_copy(update={'original_read_page_bytes':16385})})
    read = p.runtime.artifacts.read
    def no_bulk(target):
        assert target != ref, 'Large omitted text must not be loaded into memory'
        return read(target)
    monkeypatch.setattr(p.runtime.artifacts, 'read', no_bulk)
    snapshot = {'runs':[], 'messages':[{'name':'large-goal', 'artifact_ref':ref.model_dump(mode='json')}], 'approvals':[]}
    brief = json.loads(p.coordinator._brief(selected, snapshot, 49152)[len(INSTRUCTION)+1:])
    assert brief['objective']['view'] == 'content'
    assert any(item.get('view') == 'content' for item in brief['omissions'])
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
    from tests.operations.test_unified_mcp import call, result
    gateway = UnifiedMCPRouter(p.root, worker_backend='local')
    cursor, recovered = None, ''
    while True:
        page = result(call(gateway, 'artifact_catalog', {'name':'large-goal', 'view':'content', 'content_cursor':cursor}))
        assert page['returned_bytes'] <= 16385
        recovered += page['text']
        if page['complete']:
            assert page['next_cursor'] is None
            break
        cursor = page['next_cursor']
        assert cursor
    assert recovered == text
    with pytest.raises(RootToolError, match='content_cursor'):
        p.root.facade.artifact_catalog(name='goal', view='content', content_cursor=cursor)


def test_original_reading_is_instance_scoped(progression):
    from copy import copy
    p = progression
    other = p.runtime.scheduler_bindings.create_instance(name='other',title='Other',objective='Separate')
    facade = copy(p.root.facade)
    facade.session_key = None
    facade.instance = other.instance_id
    with pytest.raises(SchedulerNameNotFound):
        facade.artifact_catalog(name='goal', view='content')


@pytest.mark.parametrize('schema,media,confidentiality,raw', [
    ('scidiscovery.tool-evidence-manifest.v1','application/json','project',b'{}'),
    ('opaque','text/plain','approval_only',b'private'),
    ('opaque','application/octet-stream','project',b'\x00\xff'),
    ('opaque','text/plain','project',b'\xff'),
])
def test_content_rejects_private_control_and_non_text_originals(progression,schema,media,confidentiality,raw):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    p = progression
    envelope = p.runtime.artifacts.register(raw, ArtifactRegistration(kind='source',schema_id=schema,
        media_type=media,confidentiality=confidentiality,payload_schema_version=1,creator=p.runtime.actor),idempotency_key='private')
    p.runtime.scheduler_bindings.bind(instance=p.instance,namespace='artifact',name='private',object_id=envelope.artifact_id)
    with pytest.raises(RootToolError):
        p.root.facade.artifact_catalog(name='private',view='content')
