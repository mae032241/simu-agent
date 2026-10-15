"""Optional audit admission preserves one later author, including soft budgets."""
import pytest

from scidiscovery.research_loop import candidate_audit, contracts as c
from test_closeout_protocol import command, scene


@pytest.mark.parametrize('dimension',['tokens','seconds'])
def test_optional_audit_keeps_followup_author_budget(tmp_path,dimension):
    root=scene(tmp_path,[dict(action='audit',candidate='run-1'),dict(action='deliver',candidate='run-1')],
        max_tokens=1120 if dimension=='tokens' else 100000,
        max_seconds=75 if dimension=='seconds' else 600)
    result=command(root)
    assert result['status']==('closeout_budget_unavailable' if dimension=='tokens' else 'delivery_confirmed'),result
    outcome=c.read(candidate_audit._directory(root,3)/'outcome.json')
    assert outcome['accepted'] is False
    assert outcome['result']['status']=='unavailable' and outcome['result']['note']=='candidate_audit_reserve_unavailable'
    assert not (candidate_audit._directory(root,3)/'intent.json').exists()
    assert not list(candidate_audit.facts(root))


def test_multibyte_candidate_preview_keeps_whole_ids_and_reports_omissions():
    from scidiscovery.research_loop import delivery
    rows=[dict(candidate_id='候'*77+f'{n:02}',status='available',source_step=2) for n in range(32)]
    refs=dict(catalogue=True,items=rows,omitted_count=0,source_nodes=[])
    view=delivery.public_sources(refs)
    assert len(delivery._bytes(view))<=4096
    assert view['omitted_count']==len(rows)-len(view['items'])
    assert view['catalogue']=='inputs/delivery-candidates.json'
    assert {r['candidate_id'] for r in view['items']} <= {r['candidate_id'] for r in rows}
