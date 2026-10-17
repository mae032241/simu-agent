"""Root rotation through the production factory and a bounded Python protocol peer."""

import pytest


@pytest.mark.parametrize('sticky',[False,True])
def test_recovery_usage_summary_does_not_conflate_counter_gaps(sticky):
    from scidiscovery.platforms.codex_usage import observe_usage,usage_summary
    params=dict(threadId='measured',turnId='measured-turn',tokenUsage=dict(total=dict(
        inputTokens=10,cachedInputTokens=2,outputTokens=1)))
    record=observe_usage(params,role='worker',owner='fixture-owner')
    record['has_gaps']=sticky
    record['recovery_usage_unconfirmed']=True
    summary=usage_summary([record])
    assert summary['coverage']=='partial' and summary['groups']['worker']['unmeasured_threads']==1
    record.pop('recovery_usage_unconfirmed')
    assert usage_summary([record])['coverage']==('partial' if sticky else 'observed')
    assert record['has_gaps'] is sticky
