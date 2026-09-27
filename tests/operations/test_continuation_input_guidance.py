"""Input equivalence is navigation, never a claim about model memory."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.run_records import RunInputBinding
from scidiscovery.artifact_agent.service.runs import RunNotFound


def descriptor(binding, **extra):
    return dict(source_name=binding.source_name, port=binding.port_name,
                media_type=binding.media_type, usage=binding.usage,
                exposure=binding.exposure, historical=False, **extra)


def fixture_router(old, new):
    router = object.__new__(LocalWorkerMCPRouter)
    router._previous_run_id, router._run_id = 'before', 'after'
    states = {'before': SimpleNamespace(inputs=old), 'after': SimpleNamespace(inputs=new)}
    router.runs = SimpleNamespace(status=states.__getitem__)
    return router


def binding():
    return RunInputBinding(port_name='research_objective', source_name='objective',
        artifact_name='original', artifact_ref=ArtifactRef(
            artifact_id='artifact_original', sha256='a'*64, kind='objective', schema_id='objective.v1'),
        media_type='application/json', exposure='full', usage='prior_signal', require_current=False)


def test_exact_binding_alias_change_and_new_input():
    old = binding()
    new = replace(old, source_name='current_objective')
    added = replace(old, source_name='new_review', port_name='current_progress',
                    artifact_ref=old.artifact_ref.model_copy(update={'artifact_id': 'artifact_review'}))
    router = fixture_router([old], [new, added])
    result = router._input_changes({'inputs': [descriptor(new), descriptor(added)]},
                                   {'inputs': [descriptor(old)]})
    assert result == [dict(source_name='current_objective', status='unchanged', previous_source_name='objective'),
                      dict(source_name='new_review', status='new')]
    assert 'sha256' not in str(result) and 'artifact_original' not in str(result)


@pytest.mark.parametrize('change', ['content', 'identity', 'port', 'usage', 'exposure', 'historical', 'currentness', 'origin'])
def test_content_or_use_change_never_claims_reuse(change):
    old = binding(); new = old
    prior = descriptor(old); current = descriptor(new)
    if change in {'content', 'identity'}:
        field, value = ('sha256', 'b'*64) if change == 'content' else ('artifact_id', 'artifact_other')
        new = replace(old, artifact_ref=old.artifact_ref.model_copy(update={field: value}))
    elif change == 'historical':
        current['historical'] = True
    elif change == 'origin':
        current['source_origin'] = 'user_via_scheduler'
    else:
        field, value = {'port': ('port_name', 'current_progress'), 'usage': ('usage', 'evidence_inventory'),
                        'exposure': ('exposure', 'on_demand'), 'currentness': ('require_current', True)}[change]
        new = replace(old, **{field: value}); current = descriptor(new)
    router = fixture_router([old], [new])
    assert router._input_changes({'inputs': [current]}, {'inputs': [prior]})[0]['status'] == 'changed'


def test_unavailable_or_ambiguous_history_is_unknown():
    old = binding(); router = fixture_router([old], [old]); current = {'inputs': [descriptor(old)]}
    assert router._input_changes(current, None)[0]['status'] == 'unknown'
    assert router._input_changes(current, {})[0]['status'] == 'unknown'
    assert router._input_changes(current, {'inputs': [{'source_name': 'unresolved'}]})[0]['status'] == 'unknown'
    assert router._input_changes(current, {'inputs': [descriptor(old), descriptor(old)]})[0]['status'] == 'unknown'
    router.runs = SimpleNamespace(status=lambda _: (_ for _ in ()).throw(RunNotFound('unavailable')))
    assert router._input_changes(current, {'inputs': [descriptor(old)]})[0]['status'] == 'unknown'
