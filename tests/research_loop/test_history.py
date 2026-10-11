"""Bounded role history and independent candidate facts, without model calls."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scidiscovery.research_loop import contracts as c, history
from test_history_handoff import finish, source, scene, REUSED


def test_role_index_paging_and_complete_scientific_text_are_readable_now(scene):
    source(scene)
    roles = ('A', 'H', 'E', 'H', 'W', 'A', 'H', 'W', 'A')
    for step, role in enumerate(roles, 3):
        finish(scene, step, role, [step - 1], text='Scientific original ' + ('evidence ' * 1000))
    work = c.workspace(scene, 12)
    work.mkdir()
    binding = history.bind(scene, 12)
    assert binding['view']['node_count'] == 11
    page = c.read(work / binding['view']['index'])
    assert len(page['records']) == 8 and page['omitted_count'] == 3
    second = c.read(work / page['next_page'])
    assert len(second['records']) == 3 and second['next_page'] is None
    assert {row['role'] for row in [*page['records'], *second['records']]} == {'H', 'W', 'A', 'E'}
    old = page['records'][2]
    detail = ''.join(c.read(work / path)['text'] for path in old['conclusion_pages'])
    assert json.loads(detail) == c.read(c.host_record(c.workspace(scene, 3)) / 'science-output.json')
    assert (work / old['conclusion_pages'][0]).stat().st_mode & 0o222 == 0
    assert not list((work / 'inputs/history').rglob('candidate.py'))
    assert len(binding['view']['recent']) == 3
    assert binding['view']['h_lineage'][-1] == {'step': 9, 'parents': [6]}
    assert 'failed' not in binding['view']  # limitations are author's declarations, no semantic guess.
    history.validate(scene, work, binding)


def test_deleted_projection_rebuilds_without_duplicate_attempts(scene):
    source(scene)
    work = c.workspace(scene, 3);work.mkdir()
    first = history.bind(scene, 3)
    shutil.rmtree(scene / 'host-history/nodes')
    assert history.bind(scene, 3) == first
    assert len(list((scene / 'host-history/nodes').glob('*.json'))) == 2
    assert len(first['nodes']) == 2


def test_history_exact_implementation_handle_uses_original_seal(scene):
    source(scene)
    work = c.workspace(scene, 3);work.mkdir()
    bound = history.bind(scene, 3)
    row = history.resolve(scene, 'history/nodes/002/artifacts/candidate.py', bound['nodes'])
    assert row['path'] == REUSED and Path(row['source']) == c.workspace(scene, 2) / 'artifacts/candidate.py'
    for target in ('history/nodes/003/artifacts/candidate.py', 'history/nodes/002/artifacts/missing.py',
                   'history/nodes/2/artifacts/candidate.py', 'history/nodes/002/artifacts/../candidate.py'):
        with pytest.raises(ValueError):
            history.resolve(scene, target, bound['nodes'])


@pytest.mark.parametrize('changed', ['page', 'source', 'seal'])
def test_tampered_history_is_rejected(scene, changed):
    source(scene)
    work = c.workspace(scene, 3);work.mkdir()
    bound = history.bind(scene, 3)
    path = work / bound['files'][0]['path'] if changed == 'page' else c.host_record(c.workspace(scene, 2)) / ('science-output.json' if changed == 'source' else 'result-identity.json')
    path.chmod(0o600);path.write_text('{}')
    with pytest.raises((ValueError, KeyError)):
        history.validate(scene, work, bound)


def test_page_and_total_bounds_are_explicit(scene, monkeypatch):
    source(scene)
    work = c.workspace(scene, 3);work.mkdir()
    monkeypatch.setattr(history, 'MAX_HISTORY_BYTES', 10)
    with pytest.raises(ValueError, match='bounded page capacity'):
        history.bind(scene, 3)


def test_candidate_slots_do_not_overwrite_each_other_or_compare_other_evaluation():
    def candidate(name, metric, key):
        return dict(id=name, label=name, implementation=None, evaluation_key=key,
                    metric=metric, direction='max', status='ok', evidence=[])
    records = [dict(step=2, observation=dict(candidates=[candidate('low', .6, 'proxy-a'),
                    candidate('high', .9, 'proxy-a'), candidate('different', 900, 'proxy-b')],
                    actual_submission=dict(candidate_id='low')), recommendation=None),
               dict(step=3, observation=None, recommendation='different')]
    view = history.candidate_overview(records)
    assert {row['id'] for row in view['proxy_highest']} == {'high', 'different'}
    assert view['a_recommended']['candidate_id'] == 'different'
    assert view['actual_submission']['candidate_id'] == 'low'
    assert history.candidate_overview(records) == view
    records.append(dict(step=4, observation=None, recommendation='unknown'))
    with pytest.raises(ValueError, match='unknown candidate'):
        history.candidate_overview(records)


def setup_observer(scene, tmp_path, body):
    path = tmp_path / 'adapter.py';path.write_text(body)
    config = history.observer_config(dict(adapter=str(path), config={}))
    settings = c.settings(scene);settings['history_observer'] = config
    c.write(scene / 'settings.json', settings)
    c.write(scene / 'settings-identity.json', dict(sha256=c.digest(scene / 'settings.json')))
    return path


def test_generic_observer_snapshot_is_bounded_frozen_and_replay_stable(scene, tmp_path):
    setup_observer(scene, tmp_path, '''import json,sys
q=json.load(sys.stdin)
if q["step"] != 2:
 print(json.dumps({"candidates":[],"current_candidate":None,"actual_submission":None,"coverage":{"status":"complete","note":"Fixture"}}));raise SystemExit
print(json.dumps({"current_candidate":None,"coverage":{"status":"complete","note":"Fixture"},"candidates":[{"id":"mechanism-a","label":"A measured implementation","implementation":"history/nodes/002/artifacts/candidate.py","evaluation_key":"measured-v1","metric":0.7,"direction":"max","status":"ok","evidence":["fact.json"]}],"actual_submission":{"candidate_id":"mechanism-a","artifact":"artifact.bin","evidence":["fact.json"]}}))
''')
    (scene / 'fact.json').write_text('{"measured":0.7}')
    (scene / 'artifact.bin').write_bytes(b'not a pickle, never executed')
    source(scene)
    job = c.read(scene / 'jobs/002.json');raw = c.read(c.host_record(c.workspace(scene, 2)) / 'science-output.json')
    materials = c.read(c.host_record(c.workspace(scene, 2)) / 'result-identity.json')['materials']
    first = history.capture(scene, job, raw, materials)
    observation = c.read(scene / first['path'])
    assert observation['actual_submission']['artifact']['sha256'] == c.digest(scene / 'artifact.bin')
    (scene / 'fact.json').write_text('{"measured":999}')
    assert history.capture(scene, job, raw, materials) == first
    assert c.read(scene / first['path']) == observation


@pytest.mark.parametrize('body', ['import time; time.sleep(2)', 'print("x"*300000)'])
def test_observer_timeout_and_output_bound_stop_without_model(scene, tmp_path, monkeypatch, body):
    setup_observer(scene, tmp_path, body)
    job = c.build_job(scene, 1, 'H', [])
    c.write(c.host_record(c.workspace(scene, 1)) / 'science-output.json', {'summary':'Unsealed fixture'})
    monkeypatch.setattr(history, 'OBSERVER_SECONDS', .1)
    receipt = history.capture(scene, job, {}, [])
    fact = c.read(scene / receipt['path'])
    assert fact['coverage']['status'] == 'unavailable'
    assert history.capture(scene, job, {}, []) == receipt


def test_observer_adapter_and_observation_tamper_are_not_rebuilt(scene, tmp_path):
    adapter = setup_observer(scene, tmp_path, 'print(\'{"candidates":[],"current_candidate":null,"actual_submission":null,"coverage":{"status":"complete","note":"Fixture"}}\')')
    source(scene)
    job = c.read(scene / 'jobs/002.json')
    history.capture(scene, job, {}, [])
    adapter.write_text('raise Exception("changed")')
    with pytest.raises(ValueError, match='adapter changed'):
        history.capture(scene, job, {}, [])


def test_cov_adapter_uses_public_facts_and_keeps_unexported_code_unknown(scene):
    import importlib.util
    path = Path(__file__).resolve().parents[2] / 'scripts/observe_covshift_candidates.py'
    spec = importlib.util.spec_from_file_location('cov_observer', path)
    adapter = importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    runs = scene / 'runs';runs.mkdir()
    (runs / 'results.jsonl').write_text(json.dumps(dict(run_id=1, val_score=.91, ok=True,
        script=str(scene / 'project/nodes/002/work/unexported.py'))) + '\n')
    (runs / 'submitted.json').write_text(json.dumps(dict(run_id=1)))
    (runs / 'submitted_model.pkl').write_bytes(b'Never unpickle this')
    # This unrelated private file is not part of the adapter input surface.
    (scene / 'hidden-score.json').write_text('not even valid JSON')
    request = dict(root=str(scene), config=dict(runs='runs', evaluation_key='public-proxy-v1'),
                   materials=[], known_candidates=[])
    value = adapter.observe(request)
    assert value['candidates'][0]['implementation'] is None
    assert value['candidates'][0]['metric'] == .91
    assert value['actual_submission']['candidate_id'] == 'run-1'
    request['known_candidates'] = ['run-1']
    assert adapter.observe(request)['candidates'] == []


def test_revised_h_reads_old_science_now_and_selects_only_old_code_for_successor(scene):
    source(scene)
    finish(scene, 3, 'A', [2], action='revise_h')
    finish(scene, 4, 'H', [3], action='extract')
    finish(scene, 5, 'E', [4])
    job = c.build_job(scene, 6, 'H', [5])
    work = c.workspace(scene, 6)
    assert not (work / REUSED).exists()
    page = c.read(work / job['history']['view']['index'])
    old = next(row for row in page['records'] if row['step'] == 2)
    assert old['implementations'][0]['path'] == 'history/nodes/002/artifacts/candidate.py'
    assert json.loads(''.join(c.read(work / path)['text'] for path in old['conclusion_pages']))['summary'] == 'A contribution'
    finish(scene, 6, 'H', [5], text='[Retained code](history/nodes/002/artifacts/candidate.py#reuse-implementation)', action='experiment')
    successor = c.build_job(scene, 7, 'W', [6])
    assert (c.workspace(scene, 7) / REUSED).read_text() == 'def predict(): return 42\n'
    assert [row['path'] for row in successor['direct_refs']] == ['inputs/parents/006/conclusion.json']
    assert not list((c.workspace(scene, 7) / 'inputs').rglob('unused.txt'))


def test_handoff_v2_packets_are_byte_compatible_after_history_upgrade(scene):
    source(scene)
    job = c.build_job(scene, 3, 'A', [2])
    job['handoff_protocol'] = 2;job.pop('history')
    work = c.workspace(scene, 3)
    c.write(scene / 'jobs/003.json', job)
    c.write(work / 'science-task.json', c.science_view(job))
    c.write(c.host_record(work) / 'science-result.schema.json', c.result_schema('A', 2))
    finish(scene, 3, 'A', [2], action='revise_h')
    paths = [scene / 'jobs/003.json', work / 'science-task.json', c.host_record(work) / 'result-identity.json']
    original = {path: path.read_bytes() for path in paths}
    assert 'candidate_recommendation' not in c.result_schema('A', 2)['properties']
    assert 'history' not in c.science_view(job)
    assert c.build_job(scene, 3, 'A', [2]) == job
    next_job = c.build_job(scene, 4, 'H', [3])
    assert next_job['handoff_protocol'] == 3 and next_job['history']['view']['node_count'] == 3
    assert all(path.read_bytes() == data for path, data in original.items())
    c.validate(work)


def test_utf8_history_default_brief_is_at_most_4096_bytes(scene):
    text = '科学限制' * 500
    for step in range(1, 9):
        role = ('H', 'W', 'A', 'E')[(step - 1) % 4]
        finish(scene, step, role, [step - 1] if step > 1 else [], summary=text,
               limitations=[text] * 5, text=text)
    job = c.build_job(scene, 9, 'H', [8])
    brief = c.science_view(job)['history']
    assert len(history._bytes(brief)) <= history.MAX_BRIEF_BYTES == 4096
    assert all(len(row['summary'].encode()) <= 160 for row in brief['recent'])
    assert all('implementations' not in row for row in brief['recent'])
    assert all('summary' not in row for row in brief['declared_limitations'])
    assert all(row['summary_truncated'] for row in brief['recent'])


def test_nodes_paginate_by_bytes_as_well_as_row_count(scene):
    finish(scene, 1, 'H', [])
    directory = '/'.join(['界' * 60] * 3)
    files = {f'{directory}/implementation{i:02d}.py': '' for i in range(16)}
    for step in range(2, 7):
        finish(scene, step, 'W', [1], files=files, summary='界' * 512, limitations=['界' * 256] * 4)
    job = c.build_job(scene, 7, 'H', [6])
    work = c.workspace(scene, 7)
    pages = [row for row in job['history']['files'] if '/pages/' in row['path']]
    assert len(pages) > 1  # All 6 rows would exceed one byte bound despite count <8.
    assert all(row['size_bytes'] <= history.MAX_PAGE_BYTES for row in pages)
    assert sum(len(c.read(work / row['path'])['records']) for row in pages) == 6


def test_observer_originals_survive_append_overwrite_and_are_deduplicated(scene, tmp_path):
    adapter = setup_observer(scene, tmp_path, '''import json,sys
q=json.load(sys.stdin)
print(json.dumps({"candidates":[],"current_candidate":None,"coverage":{"status":"complete","note":"Fixture"},"actual_submission":{"candidate_id":None,"artifact":"artifact.bin","evidence":["fact.json"]}}))
''')
    (scene / 'fact.json').write_text('{"observation":1}')
    (scene / 'artifact.bin').write_bytes(b'original submitted bytes')
    source(scene)
    old = c.read(scene / 'host-history/observations/002.json')
    proof = old['actual_submission']['artifact']
    assert proof['retention'] == 'archived'
    assert (scene / proof['snapshot']).read_bytes() == b'original submitted bytes'
    assert len(list((scene / 'host-history/objects').iterdir())) == 2
    (scene / 'fact.json').write_text('{"observation":2}')
    (scene / 'artifact.bin').write_bytes(b'new submitted bytes')
    finish(scene, 3, 'A', [2])
    assert (scene / proof['snapshot']).read_bytes() == b'original submitted bytes'
    assert len(list((scene / 'host-history/objects').iterdir())) == 4
    c.validate(c.workspace(scene, 2))  # Mutable public sources are not mistaken for frozen originals.
    (scene / proof['snapshot']).chmod(0o600);(scene / proof['snapshot']).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='Archived observer original changed'):
        c.validate(c.workspace(scene, 2))


def test_optional_observer_unavailable_does_not_block_scientific_seal(scene, tmp_path):
    setup_observer(scene, tmp_path, 'print("this is not observer JSON")')
    finish(scene, 1, 'H', [], action='experiment')
    seal = c.read(c.host_record(c.workspace(scene, 1)) / 'result-identity.json')
    snapshot = c.read(scene / seal['observations']['path'])
    assert snapshot['coverage']['status'] == 'unavailable'
    c.validate(c.workspace(scene, 1))
    job = c.build_job(scene, 2, 'W', [1])
    overview = c.read(c.workspace(scene, 2) / job['history']['view']['candidates'])
    assert overview['coverage']['status'] == 'unavailable'


def test_actual_unknown_id_is_unavailable_not_a_false_submission(scene, tmp_path):
    setup_observer(scene, tmp_path, '''print('{"candidates":[],"current_candidate":null,"coverage":{"status":"complete","note":"Fixture"},"actual_submission":{"candidate_id":"invented","artifact":"artifact.bin","evidence":["fact.json"]}}')''')
    (scene / 'fact.json').write_text('{}');(scene / 'artifact.bin').write_bytes(b'unknown')
    finish(scene, 1, 'H', [])
    snapshot = c.read(scene / 'host-history/observations/001.json')
    assert snapshot['coverage']['status'] == 'unavailable' and snapshot['actual_submission'] is None


def test_cov_adapter_new_record_bound_is_not_total_history_bound(scene):
    import importlib.util
    path = Path(__file__).resolve().parents[2] / 'scripts/observe_covshift_candidates.py'
    spec = importlib.util.spec_from_file_location('cov_observer_many', path)
    adapter = importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    runs = scene / 'runs';runs.mkdir()
    (runs / 'results.jsonl').write_text(''.join(json.dumps(dict(run_id=i, val_score=i/1000, ok=True))+'\n' for i in range(1, 201)))
    request = dict(root=str(scene), config=dict(runs='runs', evaluation_key='public-proxy-v1'), materials=[], known_candidates=[f'run-{i}' for i in range(1, 200)])
    value = adapter.observe(request)
    assert [row['id'] for row in value['candidates']] == ['run-200']
    assert value['coverage']['status'] == 'complete'
    request['known_candidates'] = []
    value = adapter.observe(request)
    assert len(value['candidates']) == 128 and value['coverage']['status'] == 'partial'


def test_candidate_pages_pack_valid_multibyte_rows_without_expanding_brief(scene, tmp_path):
    setup_observer(scene, tmp_path, '''import json,sys
q=json.load(sys.stdin)
rows=[]
if q["step"]==2:
 for i in range(20):
  rows.append({"id":"candidate-"+str(i),"label":"界"*160,"implementation":None,"evaluation_key":"条件"*256,"metric":i,"direction":"max","status":"ok","evidence":["fact.json"]})
print(json.dumps({"candidates":rows,"current_candidate":None,"actual_submission":None,"coverage":{"status":"complete","note":"Fixture"}}))
''')
    (scene / 'fact.json').write_text('{}')
    source(scene)
    job = c.build_job(scene, 3, 'A', [2])
    work = c.workspace(scene, 3)
    pages = [row for row in job['history']['files'] if '/candidates/' in row['path']]
    assert len(pages) >= 2 and all(row['size_bytes'] <= history.MAX_PAGE_BYTES for row in pages)
    assert sum(len(c.read(work / row['path'])['candidates']) for row in pages) == 20
    overview = c.read(work / 'inputs/history/candidates.json')
    assert overview['proxy_highest'][0]['id'] == 'candidate-19'
    assert overview['proxy_highest'][0]['evaluation_key_truncated']
    assert len(history._bytes(job['history']['view'])) <= 4096
    finish(scene, 3, 'A', [2], recommendation='candidate-4')
    next_job = c.build_job(scene, 4, 'H', [3])
    next_overview = c.read(c.workspace(scene, 4) / next_job['history']['view']['candidates'])
    assert next_overview['a_recommended']['candidate_id'] == 'candidate-4'
    assert next_overview['proxy_highest'][0]['id'] == 'candidate-19'
    assert next_overview['actual_submission'] is None


def test_unknown_a_recommendation_and_tampered_current_history_block_seal(scene):
    source(scene)
    with pytest.raises(ValueError, match='frozen listed candidate'):
        finish(scene, 3, 'A', [2], recommendation='invented')
    assert not (c.host_record(c.workspace(scene, 3)) / 'result-identity.json').exists()


def test_retention_capacity_is_explicit_and_does_not_block_seal(scene, tmp_path, monkeypatch):
    setup_observer(scene, tmp_path, '''print('{"candidates":[],"current_candidate":null,"coverage":{"status":"complete","note":"Fixture"},"actual_submission":{"candidate_id":null,"artifact":"artifact.bin","evidence":["fact.json"]}}')''')
    (scene / 'fact.json').write_text('{}');(scene / 'artifact.bin').write_bytes(b'larger than capacity')
    monkeypatch.setattr(history, 'MAX_OBJECT_BYTES', 3)
    finish(scene, 1, 'H', [])
    fact = c.read(scene / 'host-history/observations/001.json')
    assert fact['actual_submission']['artifact']['retention'] in ('digest_only', 'unavailable')
    c.validate(c.workspace(scene, 1))
    assert c.read(scene / 'host-history/overview.json')['actual_submission']['retention'] != 'archived'


def test_repeated_known_candidate_becomes_unavailable_without_poisoning_seals(scene, tmp_path):
    setup_observer(scene, tmp_path, '''import json,sys
q=json.load(sys.stdin)
rows=[]
if q["step"]>=2:
 rows=[{"id":"retained","label":"Measured","implementation":None,"evaluation_key":"proxy-v1","metric":0.7 if q["step"]==2 else 999,"direction":"max","status":"ok","evidence":["fact.json"]}]
print(json.dumps({"candidates":rows,"current_candidate":None,"actual_submission":None,"coverage":{"status":"complete","note":"Fixture"}}))
''')
    (scene / 'fact.json').write_text('{"metric":0.7}')
    source(scene)
    old = c.read(scene / 'host-history/observations/002.json')
    proof = old['candidates'][0]['evidence'][0]
    (scene / 'fact.json').write_text('{"metric":999}')
    finish(scene, 3, 'A', [2])
    snapshot = c.read(scene / 'host-history/observations/003.json')
    assert snapshot['coverage']['status'] == 'unavailable'
    assert snapshot['diagnostic']['error_code'] == 'invalid_output'
    overview = c.read(scene / 'host-history/overview.json')
    assert overview['proxy_highest'][0]['metric'] == .7
    assert overview['proxy_highest'][0]['candidate_h_scope'] is None
    assert overview['proxy_highest'][0]['observation_step'] == 2
    assert (scene / proof['snapshot']).read_text() == '{"metric":0.7}'
    c.validate(c.workspace(scene, 2));c.validate(c.workspace(scene, 3))
