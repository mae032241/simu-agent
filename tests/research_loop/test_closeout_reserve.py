"""A protected final return cannot spend an unavailable optional-audit follow-up."""
import pytest

from scidiscovery.research_loop import budget, candidate_audit, contracts as c, native
from test_closeout_protocol import command, scene


@pytest.mark.parametrize('dimension',['tokens','seconds'])
def test_optional_audit_keeps_followup_author_budget(tmp_path,dimension):
    max_tokens=1120 if dimension=='tokens' else 100000
    max_seconds=75 if dimension=='seconds' else 600
    root=scene(tmp_path,[dict(action='audit',candidate='run-1'),dict(action='deliver',candidate='run-1')],
        max_tokens=max_tokens,max_seconds=max_seconds)
    settings=(root/'settings.json').read_bytes()
    result=command(root)
    # A last-allocation return preserves the authored audit request as science;
    # it cannot start an optional audit that would require another A.
    assert result['status']=='final_a_completed' and result['goal_completion']=='not_asserted',result
    grant=budget.final_a_barrier(root)
    assert grant['step']==3 and grant['basis']=='last_closeout_allocation'
    assert grant['anchor']['shared_limits']==dict(max_tokens=max_tokens,max_seconds=max_seconds)
    science=c.host_record(c.workspace(root,3))/'science-output.json'
    original=science.read_bytes()
    assert c.read(science)['next_action']=='audit' and c.read(science)['candidate_recommendation']=='run-1'
    assert not (candidate_audit._directory(root,3)/'intent.json').exists()
    assert not (candidate_audit._directory(root,3)/'outcome.json').exists()
    assert not list(candidate_audit.facts(root))
    assert [c.read(path)['role'] for path in sorted((root/'jobs').glob('*.json'))]==['H','W','A']
    assert not budget.closeout_state(root)['actions'] and not (root/'submission/model.pkl').exists()
    assert native.usage(root)['observed_tokens']==30 and budget.used_steps(root)==3
    assert command(root)['status']=='final_a_completed'
    assert science.read_bytes()==original and (root/'settings.json').read_bytes()==settings
    assert native.usage(root)['observed_tokens']==30 and budget.used_steps(root)==3
    assert budget.final_a_barrier(root)==grant
    assert not (root/'jobs/004.json').exists() and not list(candidate_audit.facts(root))


def test_multibyte_candidate_preview_keeps_whole_ids_and_reports_omissions():
    from scidiscovery.research_loop import delivery
    rows=[dict(candidate_id='候'*77+f'{n:02}',status='available',source_step=2) for n in range(32)]
    refs=dict(catalogue=True,items=rows,omitted_count=0,source_nodes=[])
    view=delivery.public_sources(refs)
    assert len(delivery._bytes(view))<=4096
    assert view['omitted_count']==len(rows)-len(view['items'])
    assert view['catalogue']=='inputs/delivery-candidates.json'
    assert {r['candidate_id'] for r in view['items']} <= {r['candidate_id'] for r in rows}
