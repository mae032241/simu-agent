"""Optional local declarations preserve science without qualifying it."""
import copy
import json

import jsonschema
import pytest

from scidiscovery.research_loop import experiments as e, generic_results
from scidiscovery.research_loop.local_experiments import LocalExecution
from test_local_managed import execution_registry, local


def declaration(direction='max'):
    return dict(version=1, metrics=[dict(name='score',value=.5,evaluation_key='declared-observation-v1',direction=direction)],
        outputs=[dict(path='artifacts/model.bin',label='Retained evaluated object')],
        candidate=dict(label='Author choice',metric='score',artifact='artifacts/model.bin'))


def observed(result):
    return dict(call_id='call-1',scope=dict(step=2),status='known_success',result_protocol=e.LOCAL_RESULT_PROTOCOL,
        completed=dict(retention='archived'),execution=dict(result=result),outputs=[dict(name='model.bin')])


def test_describe_exposes_optional_scientific_descriptions_without_direction_default():
    public = json.loads(next(row.content for row in LocalExecution.capabilities() if row.key == 'local_command'))
    result = public['optional_result']
    assert result['path'] == 'artifacts/result.json'
    schema = result['schema']
    assert schema['required'] == ['version','metrics','outputs']
    direction = schema['properties']['metrics']['items']['properties']['direction']
    assert 'enum' not in direction and 'default' not in direction
    for description in ('min','maximize','target is zero',None,dict(target=0)):
        jsonschema.validate(declaration(description),schema)
    value=declaration();value['candidate']={'artifact':'artifacts/model.bin'}
    jsonschema.validate(value,schema)
    assert public['domain_metrics'] is False


@pytest.mark.parametrize('direction', ['min','max','maximize','target is zero',None,[],dict(target=0)])
def test_result_preserves_scientific_direction_value_and_raw(tmp_path, direction):
    value = declaration(direction)
    path = tmp_path/'result.json';path.write_text(json.dumps(value))
    original = path.read_bytes()
    result = LocalExecution.read_result(tmp_path, [dict(name='model.bin')])
    assert result['status'] == 'available'
    assert result['metrics'] == value['metrics']
    assert result['candidate'] == value['candidate']
    candidate=generic_results.candidates([observed(result)])[0]
    assert candidate['direction']==direction and candidate['metric']==.5
    assert path.read_bytes() == original


@pytest.mark.parametrize('field', ['value','artifact','metric'])
def test_invalid_single_declaration_preserves_other_observations_and_raw(tmp_path, field):
    value = copy.deepcopy(declaration())
    value['metrics'].append(dict(name='other',value=7))
    if field == 'value':value['metrics'][0]['value'] = 'unmeasured'
    elif field == 'artifact':value['candidate']['artifact'] = 'artifacts/unretained.bin'
    else:value['candidate']['metric'] = ['unresolved']
    path = tmp_path/'result.json';path.write_text(json.dumps(value))
    original = path.read_bytes()
    result = LocalExecution.read_result(tmp_path, [dict(name='model.bin')])
    assert result['status'] == 'available' and result['diagnostics']
    assert dict(name='other',value=7) in result['metrics']
    assert result['outputs']==value['outputs']
    candidates=generic_results.candidates([observed(result)])
    if field=='artifact':assert candidates==[]
    else:
        assert len(candidates)==1
        assert candidates[0]['metric'] is candidates[0]['direction'] is candidates[0]['evaluation_key'] is None
    assert path.read_bytes() == original


def test_artifact_candidate_needs_no_metric_and_never_chooses_first_measurement(tmp_path):
    value=declaration();value['candidate']={'artifact':'artifacts/model.bin'}
    value['metrics'].append(dict(name='another',value=100,direction='min'))
    (tmp_path/'result.json').write_text(json.dumps(value))
    result=LocalExecution.read_result(tmp_path,[dict(name='model.bin')])
    candidate=generic_results.candidates([observed(result)])[0]
    assert candidate['label'] is None
    assert candidate['metric'] is candidate['direction'] is candidate['evaluation_key'] is None
    assert result['metrics']==value['metrics']


def test_long_scientific_text_is_retained_with_bounded_public_preview(tmp_path):
    text='科学说明'*5000
    value=declaration(dict(target=text));metric=value['metrics'][0]
    metric.update(name=text,unit=text,evaluation_key=text)
    value['candidate'].update(label=text,metric=text)
    value['outputs'][0]['label']=text
    path=tmp_path/'result.json';path.write_text(json.dumps(value));original=path.read_bytes()
    result=LocalExecution.read_result(tmp_path,[dict(name='model.bin')])
    assert result['status']=='available' and result['metrics']==value['metrics']
    candidate=generic_results.candidates([observed(result)])[0]
    assert candidate['label']==text and candidate['evaluation_key']==text
    public=LocalExecution.public_result(dict(call_id='call-1',status='known_success',result=result))
    assert len(e.encoded(public['result']))<=16_000
    assert public['result']['candidate_details_ref']=='result.json'
    assert all(row['details_ref']=='result.json' for row in public['result']['metrics']+public['result']['outputs'])
    assert e._run_view(public)['result']==public['result']
    assert path.read_bytes()==original


def test_bad_metric_or_output_does_not_discard_valid_neighbors(tmp_path):
    value=declaration()
    value['metrics']=[None,dict(name='score',value=.5),dict(name='score',value=4),dict(name='bad',value=True),dict(name='valid',value=9)]
    value['outputs'].extend([dict(path='artifacts/missing',label='unretained'),None])
    (tmp_path/'result.json').write_text(json.dumps(value))
    result=LocalExecution.read_result(tmp_path,[dict(name='model.bin')])
    assert result['metrics']==[dict(name='valid',value=9)]
    assert result['outputs']==value['outputs'][:1]
    assert len(result['diagnostics'])==7
    assert len(generic_results.candidates([observed(result)]))==1


@pytest.mark.parametrize('section,key', [('metric','direction'),('metric','unit'),('metric','evaluation_key'),
    ('metric','extra'),('output','label'),('output','extra'),('candidate','label'),('candidate','extra')])
def test_nonfinite_nested_description_is_locally_omitted_with_original_reference(tmp_path,section,key):
    value=declaration();value['metrics'].append(dict(name='neighbor',value=7))
    target={'metric':value['metrics'][0],'output':value['outputs'][0],'candidate':value['candidate']}[section]
    target[key]={'nested':[{'target':'EXPONENT_OUT_OF_RANGE'}]}
    content=json.dumps(value).replace('"EXPONENT_OUT_OF_RANGE"','1e999')
    path=tmp_path/'result.json';path.write_text(content);original=path.read_bytes()
    result=LocalExecution.read_result(tmp_path,[dict(name='model.bin')])
    assert result['status']=='available' and dict(name='neighbor',value=7) in result['metrics']
    projected={'metric':result['metrics'][0],'output':result['outputs'][0],'candidate':result['candidate']}[section]
    assert key not in projected
    assert any(row['code']=='scientific_description_projection_unavailable' and row['details_ref']=='result.json'
        for row in result['diagnostics'])
    assert json.loads(e.encoded(result))==result
    candidate=generic_results.candidates([observed(result)])[0]
    assert candidate['metric']==.5
    assert len(e.encoded(LocalExecution.public_result(dict(status='known_success',result=result))))<16_000
    assert path.read_bytes()==original


def test_overflowing_metric_value_stays_unknown_without_discarding_candidate(tmp_path):
    content=json.dumps(declaration()).replace('"value": 0.5','"value": 1e999')
    (tmp_path/'result.json').write_text(content)
    result=LocalExecution.read_result(tmp_path,[dict(name='model.bin')])
    assert result['status']=='available' and result['metrics']==[]
    assert result['outputs'] and result['diagnostics']
    candidate=generic_results.candidates([observed(result)])[0]
    assert candidate['metric'] is candidate['direction'] is candidate['evaluation_key'] is None
    assert json.loads(e.encoded(result))==result


@pytest.mark.process_e2e
def test_nonfinite_descriptions_preserve_real_completion_publish_and_original(local):
    root,script,config,_=local
    value=declaration();value['metrics'].append(dict(name='neighbor',value=7))
    value['metrics'][0]['direction']={'target':'EXPONENT_OUT_OF_RANGE'}
    value['metrics'][0]['extra']={'nested':['EXPONENT_OUT_OF_RANGE']}
    value['outputs'][0]['label']={'target':'EXPONENT_OUT_OF_RANGE'}
    value['candidate']['label']={'target':'EXPONENT_OUT_OF_RANGE'}
    value['candidate']['extra']={'nested':['EXPONENT_OUT_OF_RANGE']}
    content=json.dumps(value).replace('"EXPONENT_OUT_OF_RANGE"','1e999')
    script.write_text('import pathlib\npathlib.Path("artifacts/model.bin").write_bytes(b"original")\n'
        'pathlib.Path("artifacts/result.json").write_text('+repr(content)+')\n')
    result=e.dispatch(config,script,command_options=dict(experiment_directory=str(root),arguments=[]))
    assert result['status']=='known_success' and result['result']['status']=='available'
    directory=e.Records(config).directory(result['call_id'])
    assert json.loads((directory/'completed.json').read_text())==result
    assert (directory/'outputs/result.json').read_text()==content
    assert e.load(config).result(result['call_id'])==result
    candidate=generic_results.candidates([observed(result['result'])])[0]
    assert candidate['metric']==.5 and candidate['direction'] is None and candidate['label'] is None
    assert dict(name='neighbor',value=7) in result['result']['metrics']
    assert e.progress(config)['calls'][0]['result']['status']=='available'
    assert len(e.Records(config).calls())==1


def test_unreadable_json_has_fixed_bounded_detail(tmp_path):
    (tmp_path/'result.json').write_text('{')
    result=LocalExecution.read_result(tmp_path,[])
    assert result['status']=='invalid' and result['diagnostic']=='result_json_invalid'
    assert str(tmp_path) not in result['detail']
    original=dict(result,detail='字'*512,private_control=dict(path='/private/control'))
    public=e._run_view(dict(result=original))['result']
    assert len(public['detail'].encode())<=512 and 'private_control' not in public


@pytest.mark.process_e2e
def test_actual_run_query_and_progress_preserve_freeform_direction(local, capsys):
    root,script,config,config_path = local
    value = declaration('maximize')
    script.write_text('import json,pathlib\n'
        'pathlib.Path("artifacts/model.bin").write_bytes(b"fixture object; no scientific qualification")\n'
        'pathlib.Path("artifacts/result.json").write_text('+repr(json.dumps(value))+')\n')
    prefix = ['--config',str(config_path)]
    assert e.main([*prefix,'run','--experiment-dir',str(root),'--script',str(script)]) == 0
    run = json.loads(capsys.readouterr().out)
    assert run['status'] == 'known_success'
    call = run['call_id']
    original = e.Records(config).directory(call)/'outputs/result.json'
    retained = original.read_bytes()
    assert e.main([*prefix,'query','--call-id',call]) == 0
    query = json.loads(capsys.readouterr().out)
    assert e.main([*prefix,'lineage-status']) == 0
    progress = json.loads(capsys.readouterr().out)
    for result in (run['result'],query['result'],progress['calls'][0]['result']):
        assert result['status']=='available' and result['metrics']==value['metrics']
        assert result['candidate']==value['candidate']
    assert original.read_bytes() == retained
    assert len(e.Records(config).calls()) == 1
