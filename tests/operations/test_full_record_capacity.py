"""Complete control records are independent of compact presentation limits."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.service.reference_proofs import encode_snapshot
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.plugin_runtime.workspace import read_json, read_control_workspace_file
from scidiscovery.plugin_runtime.observation import effective_timeout
from scidiscovery.research_loop import selection


def test_complete_manifest_exceeds_old_size_and_collection_caps():
    document=dict(records=[dict(note='x'*9000) for _ in range(140)], accesses=[dict(alias=str(i)) for i in range(40)])
    raw=encode_snapshot(document)
    assert len(raw)>1024*1024
    assert json.loads(raw)==document


def test_complete_calculation_preserves_large_result_and_semantics():
    record=CalculationRecord(record_key='large',request={},algorithm_version='v1',status='computed',result={'values':list(range(10000))})
    assert len(record.model_dump_json())>32768
    assert record.result['values'][-1]==9999
    with pytest.raises(ValueError):
        CalculationRecord(record_key='invalid',request={},algorithm_version='v1',status='computed',result=None)


def test_complete_json_and_control_workspace_read_keep_identity_guards(tmp_path):
    p=tmp_path/'record.json';raw=json.dumps(dict(data='x'*(5*1024*1024))).encode();p.write_bytes(raw)
    assert read_json(p)['data']== 'x'*(5*1024*1024)
    assert read_control_workspace_file(tmp_path,Path('record.json'),max_bytes=None)==raw
    with pytest.raises(ValueError):read_json(p,max_bytes=100)
    link=tmp_path/'link.json';link.symlink_to(p)
    with pytest.raises((OSError,ValueError)):read_json(link)


def test_large_assignment_keeps_deadline_enforcement(tmp_path):
    deadline=datetime.now(timezone.utc)+timedelta(seconds=30)
    (tmp_path/'assignment.json').write_text(json.dumps(dict(budget=dict(deadline_at=deadline.isoformat()),data='x'*(1024*1024))))
    seconds,source=effective_timeout(tmp_path,100,5)
    assert source=='run_deadline' and 0<seconds<30


def test_full_candidate_history_exceeds_input_caps_but_view_is_small():
    candidates=[dict(id=f'c{i}',label='x'*640,evaluation_key='evaluation',metric=float(i),direction='max',status='ok') for i in range(6000)]
    records=[dict(step=1,role='W',recommendation=None,coverage='complete',candidates=candidates,current_candidate=None,actual_submission=None)]
    assert len(json.dumps(records).encode())>4*1024*1024
    view=selection.project(records)
    assert view['candidate_count']==6000
    assert len(selection._bytes(view))<=selection.MAX_BRIEF_BYTES
    assert view['proxy_highest'][0]['candidate_ids']==['c5999']


def test_material_closure_preserves_more_than_32_accesses(tmp_path):
    from scidiscovery.artifact_agent.service.reference_proofs import material_snapshot, ReferenceProofError
    from tests.operations.test_sealed_reference_replay import evidence_submission
    runs, owner, args = evidence_submission(tmp_path)
    runs.accept_tool_evidence(**args)
    original = runs.tool_evidence(owner.run_id)[0]
    accesses = [dict(alias=f'ref_{i}',artifact_ref=original['artifact_ref']) for i in range(40)]
    selected = dict(original,metadata=dict(derived_from=[row['alias'] for row in accesses]))
    document = json.loads(material_snapshot(owner,selected,[selected],accesses,[],None))
    assert len(document['accesses']) == 40
    with pytest.raises(ReferenceProofError):
        material_snapshot(owner,selected,[selected],accesses[:-1],[],None)


def test_selection_omission_preserves_downstream_shape(monkeypatch):
    from scidiscovery.research_loop import lineage
    # Force the optional projection fallback; original records remain untouched.
    monkeypatch.setattr(selection,'MAX_BRIEF_BYTES',1000)
    candidate='x'*150
    rows=[dict(step=i,role='A',recommendation=candidate,coverage='complete',
        candidates=[dict(id=candidate,label='a',evaluation_key='v',metric=1.,direction='max',status='ok')],
        current_candidate=dict(candidate_id=candidate),actual_submission=dict(candidate_id=candidate,artifact_retention='unknown')) for i in (1,2)]
    view=selection.project(rows)
    assert view['view_status']=='details_omitted'
    assert view['audits_omitted_count']==1 and view['public_audits']==[]
    brief=dict(node_count=0,recent=[],candidates=dict(view,selection_protocol=1),mechanisms={})
    assert lineage.bounded_brief(brief)['candidates']['proxy_highest']==[]


def test_large_calculation_metadata_is_registered_without_truncation(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.analysis_artifacts import retain_calculation
    from tests.operations.test_sealed_reference_replay import evidence_submission
    runs, owner, args=evidence_submission(tmp_path)
    values=list(range(20000))
    response=dict(record_key='large',request={},algorithm_version='fixture-v1',
        status='computed',input_digests={},result={'values':values})
    workspace=tmp_path/'calculation';workspace.mkdir()
    context=SimpleNamespace(workspace=workspace,
        input_names_for_port=lambda port:args['derived_from'],
        accept_evidence=lambda **kwargs:runs.accept_tool_evidence(**dict(args,**kwargs)))
    result=retain_calculation(context,response,summary=True)
    saved=next(row for row in runs.tool_evidence(owner.run_id) if row['alias']==result['calculation_ref'])
    assert saved['metadata']['calculation_proof']['result']['values']==values
    assert saved['metadata']['derived_from']==list(args['derived_from'])
    original=json.loads(runs.artifacts.read(ArtifactRef.model_validate(saved['artifact_ref'])))
    assert original['result']['values']==values
    assert json.loads(runs._evidence_snapshot(owner.run_id))['records'][0]['metadata']==saved['metadata']
    assert 'values' not in json.dumps(result)  # Compact response does not copy the full calculation.
