import json
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.service.input_reader import encode, page
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend


def collect(root, path, **kwargs):
    parts, offset, version = [], 0, None
    while True:
        result = page(root, path, offset=offset, version=version, **kwargs)
        assert len((encode(result)+'\n').encode()) <= kwargs.get('budget', 4096)
        assert result['offset'] == offset
        parts.append(result['fragment'])
        if result['complete']:
            assert result['next_offset'] is None
            return ''.join(parts)
        assert result['next_offset'] > offset
        offset, version = result['next_offset'], result['version']


def test_exact_paging_numbers_and_utf8(tmp_path):
    text = '{"a/b~c":[0.123456789012345678901234567890,123456789012345678901234567890,1e-999,null,true,"' + ('中文\\n\\\"'*1600) + '"]}'
    (tmp_path/'plan.json').write_text(text)
    assert collect(tmp_path, 'plan.json', budget=1024) == text
    selected = collect(tmp_path, 'plan.json', pointer='/a~1b~0c', budget=1024)
    assert selected == text[len('{"a/b~c":'):-1]
    assert collect(tmp_path, 'plan.json', directory=True) == '["a/b~c"]'
    assert collect(tmp_path, 'plan.json', pointer='/a~1b~0c/3') == 'null'


def test_directory_structure_keeps_exact_pointers_without_expanding_arrays(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    raw = ('{"a/b~c":[' + ','.join(['1e-999'] * 2000) +
        '],"":[],"flag":false,"n":123456789012345678901234567890,"nil":null,"text":"中文"}')
    (tmp_path/'data.json').write_text(raw)
    listing = json.loads(body(read(tmp_path, 'data.json', file=True, directory=True)))
    fields = {entry['key']: entry for entry in listing['fields']}
    assert listing['type'] == 'object' and listing['count'] == 6
    assert fields['a/b~c']['pointer'] == '/a~1b~0c'
    assert fields['a/b~c']['type'] == 'array' and fields['a/b~c']['count'] == 2000
    assert fields['']['pointer'] == '/' and fields['']['count'] == 0
    assert [fields[key]['type'] for key in ('flag','n','nil','text')] == ['boolean','number','null','string']
    assert fields['text']['characters'] == 2
    for pointer, count, index_range in [('/a~1b~0c', 2000, [0,1999]), ('/', 0, [])]:
        reply = read(tmp_path, 'data.json', file=True, pointers=[pointer], directory=True, budget=512)
        assert len(reply.encode()) <= 512 and finished(reply)
        structure = json.loads(body(reply))
        assert structure['count'] == count and structure['index_range'] == index_range
        assert 'fields' not in structure  # Element values/types are not scanned or expanded.
    assert body(read(tmp_path,'data.json',file=True,pointers=['/a~1b~0c/1999'])) == '1e-999'
    assert body(read(tmp_path,'data.json',file=True,pointers=['/n'])) == '123456789012345678901234567890'
    assert collect_view(tmp_path,'data.json',file=True,budget=512) == raw


def test_version_selection_and_boundaries(tmp_path):
    path=tmp_path/'data';path.write_text('x'*9000)
    first=page(tmp_path,'data')
    with pytest.raises(ValueError,match='continuation version'):
        page(tmp_path,'data',offset=first['next_offset'])
    path.write_text('y'*9000)
    with pytest.raises(ValueError,match='changed'):
        page(tmp_path,'data',offset=first['next_offset'],version=first['version'])
    for candidate in ('../outside', '/etc/passwd'):
        with pytest.raises(ValueError,match='within'):
            page(tmp_path,candidate)
    (tmp_path/'link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError,match='within'):
        page(tmp_path,'link')
    path.write_text('{"x":1}')
    with pytest.raises(ValueError, match='--directory'):
        page(tmp_path,'data',pointer='/absent')
    with pytest.raises(ValueError):
        page(tmp_path,'data',pointer='/bad~2')
    with pytest.raises(ValueError,match='outside'):
        page(tmp_path,'data',offset=-1)
    path.write_text('')
    assert collect(tmp_path,'data') == ''


def test_directory_paging_and_metadata_limit(tmp_path):
    value={str(i): i for i in range(2000)}
    (tmp_path/'data').write_text(json.dumps(value))
    assert json.loads(collect(tmp_path,'data',directory=True,budget=1024)) == list(value)
    nested=tmp_path
    for i in range(4):
        nested=nested/('a'*120);nested.mkdir()
    (nested/'data').write_text('abc')
    with pytest.raises(ValueError,match='metadata'):
        page(tmp_path,str((nested/'data').relative_to(tmp_path)),budget=512)


def test_installed_helper_without_framework_imports(tmp_path):
    workspace=LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_reader',inputs=(),assignment=b'{}',result_schema=b'{}')
    script=workspace.root/'tools/read_input.py'
    (workspace.root/'inputs/data.json').write_text('{"n":1e-999}')
    result=subprocess.run([sys.executable,'-I',str(script),'inputs/data.json','--file','--pointer','/n'],cwd=tmp_path,capture_output=True,timeout=5)
    assert result.returncode == 0
    assert body(result.stdout.decode()) == '1e-999'
    assert finished(result.stdout.decode())
    assert not script.stat().st_mode & 0o222


def test_declared_scientific_default_keeps_negative_decision_and_exact_expansion(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    raw = '{"data":[' + ','.join(['1e-999'] * 2000) + '],"verdict":false,"summary":"Bounded contradiction.","limits":["Missing control."],"next":"Test the missing control."}'
    bind_reader_input(tmp_path, raw)
    assignment = json.loads((tmp_path/'assignment.json').read_text())
    assignment['inputs'][0].update(exposure='on_demand', media_type='application/json',
        scientific_view=dict(pointers=['/data', '/verdict', '/summary', '/limits', '/next'],
            handoff=dict(verdict='inconclusive', summary='Bounded contradiction.', assumptions=[],
                missing_inputs=['Missing control.'], next_actions=['Test the missing control.'])))
    (tmp_path/'assignment.json').write_text(json.dumps(assignment))
    original = (tmp_path/'inputs/opaque.json').read_bytes()
    overview_reply = read(tmp_path, 'plan_original', budget=8192)
    overview = json.loads(body(overview_reply))
    exact = {item['pointer']: item['value'] for item in overview['items'] if item['status']=='selected'}
    assert exact == {'/verdict':False, '/summary':'Bounded contradiction.', '/limits':['Missing control.'], '/next':'Test the missing control.'}
    assert overview['items'][0]['status']=='projected'
    assert overview['items'][0]['omitted_children'] > 0
    assert overview['sealed_handoff']['missing_inputs'] == ['Missing control.']
    assert overview['original_read']=='not_confirmed'
    full_reply = read(tmp_path, 'plan_original', full=True, budget=8192)
    assert full_reply != overview_reply
    assert collect_view(tmp_path, 'plan_original', full=True, budget=8192) == raw
    assert collect_view(tmp_path, 'plan_original', pointers=['/data'], budget=8192) == raw[len('{"data":'):raw.index(',"verdict"')]
    assert (tmp_path/'inputs/opaque.json').read_bytes() == original
    # Default and full continuations select independent content; replay survives
    # an interleaved full read and a changed declaration invalidates the handle.
    import re
    handle = re.search(r'--selection ([0-9a-f]{32})', overview_reply).group(1)
    assert read(tmp_path, selection_id=handle, offset=0, budget=8192) == overview_reply
    assignment['inputs'][0]['scientific_view']['pointers'] = ['/next']
    (tmp_path/'assignment.json').write_text(json.dumps(assignment))
    with pytest.raises(ValueError, match='changed'):
        read(tmp_path, selection_id=handle, offset=0, budget=8192)


def test_long_sealed_handoff_is_omitted_with_exact_assignment_pointer(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    bind_reader_input(tmp_path, '{"summary":"Small payload summary."}')
    assignment=json.loads((tmp_path/'assignment.json').read_text())
    handoff=dict(verdict='inconclusive', summary='文'*2000, assumptions=[], missing_inputs=[], next_actions=[])
    assignment['inputs'][0].update(exposure='on_demand', scientific_view=dict(pointers=['/summary'], handoff=handoff))
    (tmp_path/'assignment.json').write_text(json.dumps(assignment))
    overview=json.loads(collect_view(tmp_path, 'plan_original'))
    assert 'summary' not in overview['sealed_handoff']
    assert 'summary' in overview['handoff_omissions']
    assert json.loads(collect_view(tmp_path, 'assignment.json', pointers=[overview['handoff_original']['pointer']])) == handoff


def test_numeric_lexeme_never_replaces_handoff_prose(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    bind_reader_input(tmp_path, '{"number":123}')
    assignment=json.loads((tmp_path/'assignment.json').read_text())
    assignment['inputs'][0].update(exposure='on_demand', scientific_view=dict(pointers=['/number'],
        handoff=dict(verdict='pass', summary='123', assumptions=[], missing_inputs=[], next_actions=[])))
    (tmp_path/'assignment.json').write_text(json.dumps(assignment))
    view=json.loads(collect_view(tmp_path,'plan_original'))
    assert view['items'][0]['value']==123
    assert view['sealed_handoff']['summary']=='123' and 'summary_ref' not in view['sealed_handoff']


def body(reply):
    return reply.rsplit('\n[read_input: ', 1)[0]


def finished(reply):
    return reply.rsplit('[read_input: ', 1)[1].startswith('end;')


def collect_view(root, name, **kwargs):
    from scidiscovery.artifact_agent.service.input_reader import read
    reply = read(root, name, **kwargs)
    parts = []
    while True:
        assert len(reply.encode()) <= kwargs.get('budget', 4096)
        parts.append(body(reply))
        if finished(reply):
            return ''.join(parts)
        reply = read(root, name, action='next', **kwargs)


def bind_reader_input(root, text):
    (root/'inputs').mkdir(exist_ok=True)
    (root/'inputs/opaque.json').write_text(text)
    (root/'assignment.json').write_text(json.dumps({'inputs': [
        {'source_name': 'plan_original', 'port': 'experiment_plan', 'relative_path': 'inputs/opaque.json'}]}))


def test_semantic_multifield_navigation_exactness(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    values = ['0.123456789012345678901234567890', '1e-999', '123456789012345678901234567890']
    text = '{"hash":"scientific hash","path":"scientific path","version":1,"values":['+','.join(values)+'],"text":'+json.dumps('中文\n"'*2000)+'}'
    bind_reader_input(tmp_path, text)
    assert collect_view(tmp_path, 'experiment_plan', budget=512) == text
    selection = dict(pointers=['/values', '/text'], budget=1024)
    expected = '[field 1]\n['+','.join(values)+']\n[field 2]\n'+json.dumps('中文\n"'*2000, ensure_ascii=False)
    assert collect_view(tmp_path, 'plan_original', **selection) == expected
    first = read(tmp_path, 'experiment_plan', pointers=['/hash', '/path', '/version'])
    assert body(first) == '[field 1]\n"scientific hash"\n[field 2]\n"scientific path"\n[field 3]\n1'
    assert not any(marker in first for marker in ('sha256', 'next_offset', str(tmp_path)))
    assert collect_view(tmp_path, 'assignment.json', file=True, pointers=['/inputs/0/port']) == '"experiment_plan"'
    directory = json.loads(collect_view(tmp_path, 'experiment_plan', directory=True))
    assert [item['key'] for item in directory['fields']] == list(json.loads(text))


def test_registered_path_cli_and_shared_navigation(tmp_path):
    assignment = json.dumps({'inputs': [{'source_name': 'plan_original',
        'port': 'experiment_plan', 'relative_path': 'inputs/opaque.json'}]}).encode()
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(
        run_id='run_boundpath', inputs=(), assignment=assignment, result_schema=b'{}')
    (workspace.root/'inputs/opaque.json').write_text(json.dumps({'value': 'x'*2000}))
    cmd = [sys.executable, '-I', str(workspace.root/'tools/read_input.py')]
    def call(*args):
        return subprocess.check_output(cmd+list(args), cwd=tmp_path, timeout=5)
    assert call('inputs/opaque.json', '--directory') == call('experiment_plan', '--directory')
    first = call('inputs/opaque.json', '--pointer', '/value', '--budget', '512')
    assert call('--repeat') == first
    second = call('--next')
    assert second != first
    assert call('plan_original', '--pointer', '/value', '--budget', '512', '--repeat') == second


def test_registered_path_does_not_enable_implicit_file_access(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    bind_reader_input(tmp_path, 'bound')
    (tmp_path/'unbound.json').write_text('unbound')
    with pytest.raises(ValueError, match='missing or ambiguous'):
        read(tmp_path, 'unbound.json')
    assert body(read(tmp_path, 'unbound.json', file=True)) == 'unbound'
    # Even a registered path must still pass the workspace boundary check.
    (tmp_path/'inputs/opaque.json').unlink()
    (tmp_path/'inputs/opaque.json').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='within'):
        read(tmp_path, 'inputs/opaque.json')


def test_assignment_name_cli_without_file_flag(tmp_path):
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(
        run_id='run_assignmentname', inputs=(),
        assignment=json.dumps({'role_instructions': 'exact '*1000}).encode(), result_schema=b'{}')
    cmd = [sys.executable, '-I', str(workspace.root/'tools/read_input.py')]
    def call(*args):
        return subprocess.check_output(cmd+list(args), cwd=tmp_path, timeout=5)
    args = ('assignment.json', '--pointer', '/role_instructions', '--budget', '512')
    first = call(*args)
    assert first == call('--file', *args)
    assert call('--repeat') == first
    assert call('--next') != first


@pytest.mark.parametrize('text', ['用户补充：保留总体目标。', '{not JSON', ''])
def test_plain_text_directory_uses_declared_media_type(tmp_path, text):
    from scidiscovery.artifact_agent.service.input_reader import read
    bind_reader_input(tmp_path, text)
    assignment = tmp_path/'assignment.json'
    value = json.loads(assignment.read_text())
    value['inputs'][0]['media_type'] = 'text/plain; charset=utf-8'
    assignment.write_text(json.dumps(value))
    notice = read(tmp_path, 'experiment_plan', directory=True)
    assert 'plain text; no field directory' in notice
    assert 'without --directory' in notice
    assert read(tmp_path, action='repeat') == notice
    assert body(read(tmp_path, 'experiment_plan')) == text
    # Never hide malformed JSON by falling back to text on a parse failure.
    value['inputs'][0]['media_type'] = 'application/json'
    assignment.write_text(json.dumps(value))
    with pytest.raises(json.JSONDecodeError):
        read(tmp_path, 'experiment_plan', directory=True)


def test_implicit_assignment_still_checks_workspace_boundary(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    (tmp_path/'assignment.json').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='within'):
        read(tmp_path, 'assignment.json')


def test_interleaved_repeat_lost_reply_and_end(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    bind_reader_input(tmp_path, json.dumps({'a': '甲'*2000, 'b': '乙'*2000}, ensure_ascii=False))
    a = dict(pointers=['/a'], budget=512)
    b = dict(pointers=['/b'], budget=512)
    first = read(tmp_path, 'experiment_plan', **a)
    read(tmp_path, 'experiment_plan', **b)
    assert read(tmp_path, 'plan_original', action='repeat', **a) == first
    second = read(tmp_path, 'experiment_plan', action='next', **a)
    assert read(tmp_path, 'experiment_plan', action='repeat', **a) == second
    # If a later call already advanced the selection, repeat is not a receipt
    # for an earlier lost response. Restart is the explicit recovery.
    read(tmp_path, 'experiment_plan', action='next', **a)
    assert read(tmp_path, 'experiment_plan', action='restart', **a) == first
    (tmp_path/'empty').write_text('')
    assert body(read(tmp_path, 'empty', file=True)) == ''
    terminal = read(tmp_path, 'empty', file=True, action='next')
    assert finished(terminal) and body(terminal) == ''
    assert body(read(tmp_path, 'empty', file=True, action='repeat')) == ''


def test_navigation_damage_change_and_new_workspace(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    bind_reader_input(tmp_path, 'a'*9000)
    first = read(tmp_path, 'experiment_plan')
    cache = tmp_path/CACHE_DIRECTORY/'navigation.json'
    cache.write_text('not json')
    with pytest.raises(ValueError, match='damaged'):
        read(tmp_path, 'experiment_plan', action='next')
    assert read(tmp_path, 'experiment_plan', action='restart') == first
    (tmp_path/'inputs/opaque.json').write_text('b')
    with pytest.raises(ValueError, match='changed'):
        read(tmp_path, 'experiment_plan', action='repeat')
    assert body(read(tmp_path, 'experiment_plan', action='restart')).startswith('b')
    other = tmp_path/'new'; other.mkdir(); bind_reader_input(other, 'b'*9000)
    with pytest.raises(ValueError, match='missing'):
        read(other, 'experiment_plan', action='next')
    cache.unlink()
    with pytest.raises(ValueError, match='missing'):
        read(tmp_path, 'experiment_plan', action='repeat')
    # No claim of sealed-input attestation: a first read establishes current bytes.
    (tmp_path/'inputs/opaque.json').write_text('current')
    assert body(read(tmp_path, 'experiment_plan')) == 'current'


def test_reader_ambiguity_and_task_local_boundaries(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    bind_reader_input(tmp_path, 'one')
    path=tmp_path/'assignment.json'; value=json.loads(path.read_text())
    value['inputs'].append({**value['inputs'][0], 'source_name': 'another'})
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='ambiguous'):
        read(tmp_path, 'experiment_plan')
    assert body(read(tmp_path, 'plan_original')) == 'one'
    for candidate in ('../outside', '/etc/passwd'):
        with pytest.raises(ValueError, match='within'):
            read(tmp_path, candidate, file=True)
    (tmp_path/'escape').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='within'):
        read(tmp_path, 'escape', file=True)
    cache=tmp_path/CACHE_DIRECTORY/'navigation.json';cache.unlink();cache.symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='task-local'):
        read(tmp_path, 'plan_original')


def test_reader_serializes_concurrent_navigation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from scidiscovery.artifact_agent.service.input_reader import read
    text = ''.join(f'{i:06d}' for i in range(3000))
    bind_reader_input(tmp_path, text)
    first = read(tmp_path, 'experiment_plan', budget=512)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: read(tmp_path, 'experiment_plan', action='next', budget=512), range(2)))
    # Cache locking preserves successive ranges, not native response delivery order.
    parts = [body(value) for value in replies]
    assert parts[0] != parts[1]
    start = len(body(first))
    assert ''.join(parts) == text[start:start+sum(map(len, parts))] or ''.join(reversed(parts)) == text[start:start+sum(map(len, parts))]
    assert read(tmp_path, 'experiment_plan', action='restart', budget=512) == first


def test_private_cache_excluded_from_analysis_recovery(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    from curve_score.analysis_workspace import snapshot
    bind_reader_input(tmp_path, 'x'*9000)
    read(tmp_path, 'experiment_plan')
    (tmp_path/'output').mkdir(); (tmp_path/'output/note.txt').write_text('real draft')
    from scidiscovery.artifact_agent.service.output_schema_reader import workspace_view
    (tmp_path/'schema').mkdir(); (tmp_path/'schema/result.schema.json').write_text('{}')
    workspace_view(tmp_path)
    assert (tmp_path/CACHE_DIRECTORY/'schema.json').exists()
    result=snapshot(tmp_path)
    assert CACHE_DIRECTORY not in repr(result)
    assert (tmp_path/CACHE_DIRECTORY/'navigation.json').exists()
    assert 'real draft' in repr(result) or 'output/note.txt' in repr(result)


@pytest.mark.parametrize('changed', [b'{"other": 1}', b'{broken', b'\xff'])
def test_changed_unreadable_selection_reports_change_before_parsing(tmp_path, changed):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    bind_reader_input(tmp_path, '{"selected":"'+('x'*9000)+'"}')
    read(tmp_path, 'experiment_plan', pointers=['/selected'])
    cache=tmp_path/CACHE_DIRECTORY/'navigation.json';before=cache.read_bytes()
    (tmp_path/'inputs/opaque.json').write_bytes(changed)
    for action in ('next', 'repeat'):
        with pytest.raises(ValueError, match='material changed.*restart'):
            read(tmp_path, 'experiment_plan', pointers=['/selected'], action=action)
        assert cache.read_bytes()==before


def test_bare_navigation_retains_file_field_mode_and_budget(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    text='角色\n"'*1500
    (tmp_path/'assignment.json').write_text(json.dumps({'role_instructions':text,'other':'other'}))
    first=read(tmp_path,'assignment.json',file=True,pointers=['/role_instructions'],budget=512)
    assert read(tmp_path,action='repeat')==first
    second=read(tmp_path,action='next')
    assert len(second.encode())<=512 and second!=first
    assert read(tmp_path,action='repeat')==second
    assert read(tmp_path,action='restart')==first
    parts=[body(first)]
    while True:
        reply=read(tmp_path,action='next');parts.append(body(reply))
        if finished(reply):break
    assert ''.join(parts)==json.dumps(text,ensure_ascii=False)
    terminal = read(tmp_path, action='next')
    assert finished(terminal) and body(terminal) == ''
    assert read(tmp_path,action='repeat')==reply
    # Explicitly selecting another field and back updates the current selection.
    read(tmp_path,'assignment.json',file=True,pointers=['/other'])
    assert read(tmp_path,'assignment.json',file=True,pointers=['/role_instructions'],action='repeat')==reply
    assert read(tmp_path,action='repeat')==reply


def test_bare_selection_missing_corrupt_and_failed_switch(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read,CACHE_DIRECTORY
    with pytest.raises(ValueError,match='current selection'):
        read(tmp_path,action='next')
    bind_reader_input(tmp_path,'x'*9000)
    first=read(tmp_path,'experiment_plan')
    with pytest.raises(ValueError,match='ambiguous'):
        read(tmp_path,'missing')
    assert read(tmp_path,action='repeat')==first
    with pytest.raises(ValueError,match='complete source selection'):
        read(tmp_path,action='next',pointers=['/other'])
    (tmp_path/CACHE_DIRECTORY/'navigation.json').write_text('{}')
    with pytest.raises(ValueError,match='current selection'):
        read(tmp_path,action='restart')
    assert read(tmp_path,'experiment_plan',action='restart')==first


def test_installed_bare_continuation_cli(tmp_path):
    workspace=LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_navigation',inputs=(),
        assignment=json.dumps({'role_instructions':'exact '*2000}).encode(),result_schema=b'{}')
    cmd=[sys.executable,'-I',str(workspace.root/'tools/read_input.py')]
    def call(*args):return subprocess.check_output(cmd+list(args),cwd=tmp_path,timeout=5)
    first=call('--file','assignment.json','--pointer','/role_instructions','--budget','512')
    assert call('--repeat')==first
    second=call('--next');assert len(second)<=512 and second!=first
    assert call('--restart')==first


def equivalent_inputs(root, text):
    (root/'inputs').mkdir(exist_ok=True)
    entries = []
    for name in ('task', 'context'):
        path = 'inputs/' + name + '.txt'
        (root/path).write_text(text)
        entries.append(dict(source_name=name, relative_path=path, exposure='on_demand',
            media_type='text/plain', schema_id='opaque', size_bytes=len(text.encode())))
    entries[1]['same_source_as'] = 'task'
    (root/'assignment.json').write_text(json.dumps({'inputs':entries}))
    return entries


def test_equivalent_aliases_share_navigation_without_claiming_read_or_losing_pages(tmp_path):
    from pathlib import Path
    from scidiscovery.artifact_agent.service.input_reader import read
    text = '精确任务\n' * 1500
    entries = equivalent_inputs(tmp_path, text)
    # Measure the previous independent-alias entry behavior on the same originals.
    entries[1].pop('same_source_as')
    (tmp_path/'assignment.json').write_text(json.dumps({'inputs':entries}))
    before = [read(tmp_path, name, budget=512) for name in ('task', 'context')]
    assert body(before[0]) == body(before[1])
    entries[1]['same_source_as'] = 'task'
    (tmp_path/'assignment.json').write_text(json.dumps({'inputs':entries}))
    first = read(tmp_path, 'task', budget=512)
    reused = read(tmp_path, 'context', budget=512)
    assert 'cached navigation is not proof of reading' in reused and 'characters remain' in reused
    assert '[read_input: more; --selection ' in reused and len(reused.encode()) < len(first.encode())
    assert read(tmp_path, action='repeat') == first
    second = read(tmp_path, action='next')
    assert second != first
    assert read(tmp_path, 'task', budget=512, action='repeat') == second
    assert read(tmp_path, 'context', budget=512, action='restart') == first
    parts = [body(first)]
    while True:
        reply = read(tmp_path, action='next')
        parts.append(body(reply))
        if finished(reply):
            break
    assert ''.join(parts) == text
    complete_notice = read(tmp_path, 'task', budget=512)
    assert '0 characters remain' in complete_notice
    assert read(tmp_path, action='repeat') == reply
    assert read(tmp_path, action='restart') == first
    import os
    if directory := os.environ.get('SCID_TEST_LOG_DIR'):
        Path(directory).mkdir(exist_ok=True)
        Path(directory, 'd3-reader-metrics.json').write_text(json.dumps({
            'before_reply_bytes':sum(len(value.encode()) for value in before),
            'after_reply_bytes':len(first.encode())+len(reused.encode()),
            'before_content_pages':2, 'after_content_pages':1,
            'repeat_reply_bytes':len(first.encode()), 'all_characters_recovered':len(text)}))


@pytest.mark.parametrize('changes', [
    {'exposure':'file_reference'}, {'exposure':'handoff_only'}, {'exposure':'metadata_only'},
    {'agent_visible':False}, {'materialization':'controlled_tool_stream_only'},
    {'materialization':'metadata_only'},
    {'same_source_as':'context'}, {'relative_path':'../outside'}, {'schema_id':'different'},
])
def test_equivalence_hint_cannot_jump_through_unreadable_or_incompatible_alias(tmp_path, changes):
    from scidiscovery.artifact_agent.service.input_reader import read
    entries = equivalent_inputs(tmp_path, 'context bytes')
    entries[0].update(changes)
    (tmp_path/'inputs/task.txt').write_text('other bytes!!')
    (tmp_path/'assignment.json').write_text(json.dumps({'inputs':entries}))
    assert body(read(tmp_path, 'context')) == 'context bytes'


def test_alias_reuse_is_field_specific_and_recovers_damaged_navigation(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    entries = equivalent_inputs(tmp_path, json.dumps({'a':'a'*2000, 'b':'b'*2000}))
    for item in entries:
        item['media_type'] = 'application/json'
    (tmp_path/'assignment.json').write_text(json.dumps({'inputs':entries}))
    first = read(tmp_path, 'task', pointers=['/a'], budget=512)
    other = read(tmp_path, 'context', pointers=['/b'], budget=512)
    assert body(other).startswith('"bbb')
    assert 'same original' in read(tmp_path, 'context', pointers=['/a'], budget=512)
    assert read(tmp_path, action='repeat') == first
    cache = tmp_path/CACHE_DIRECTORY/'navigation.json'
    cache.write_text('damaged')
    with pytest.raises(ValueError, match='damaged'):
        read(tmp_path, 'context', pointers=['/a'], action='next', budget=512)
    assert read(tmp_path, 'context', pointers=['/a'], action='restart', budget=512) == first
    (tmp_path/'inputs/task.txt').write_text('{broken')
    with pytest.raises(ValueError, match='material changed'):
        read(tmp_path, 'context', pointers=['/a'], action='repeat', budget=512)


def test_stream_only_alias_is_denied_before_following_equivalence(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    entries = equivalent_inputs(tmp_path, 'large original')
    entries[1]['exposure'] = 'file_reference'
    (tmp_path/'assignment.json').write_text(json.dumps({'inputs':entries}))
    handle = replay_arguments(read(tmp_path, 'task', budget=512))[1]
    for name, file in (('context', False), ('inputs/context.txt', True)):
        for selection_id in (None, handle):
            with pytest.raises(ValueError, match='metadata only'):
                read(tmp_path, name, file=file, selection_id=selection_id, offset=0)


def replay_arguments(reply):
    import re
    import shlex
    match = re.search(r'\[read_input: (?:more|end); (.+?)(?:; next_offset ([0-9]+))?\]\n$', reply)
    assert match, reply[-200:]
    return shlex.split(match[1])


def next_arguments(reply):
    import re
    command = replay_arguments(reply)
    match = re.search(r'; next_offset ([0-9]+)\]\n$', reply)
    assert match
    command[command.index('--offset')+1] = match[1]
    return command


@pytest.mark.parametrize('source_flags', [
    ('worker-guides.json', '--file', '--pointer', '/guides/g0'),
    ('other-guides.json', '--file'),
])
def test_installed_source_selection_mismatch_returns_exact_bare_replay(tmp_path, source_flags):
    import re
    import shlex
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_guidesreplay',
        inputs=(), assignment=b'{}', result_schema=b'{}')
    root = workspace.root
    guides = {f'g{i}': ('原始细则'+str(i))*1000 for i in range(10)}
    source = root/'worker-guides.json'
    source.write_text(json.dumps({'guides': guides}, ensure_ascii=False))
    (root/'other-guides.json').write_bytes(source.read_bytes())
    (root/'helper-selection.json').write_text('{"different":"helper navigation"}')
    cmd = [sys.executable, '-I', str(root/'tools/read_input.py')]
    def call(*args):
        return subprocess.run(cmd+list(args), cwd=tmp_path, capture_output=True, timeout=5)
    pointers = [flag for name in guides for flag in ('--pointer', '/guides/'+name)]
    first = call('worker-guides.json', '--file', *pointers, '--budget', '8192')
    assert first.returncode == 0
    next_page = next_arguments(first.stdout.decode())
    # Owner and helper share navigation storage; an interleaved selection cannot
    # replace this handle's original source/field selection.
    assert call('helper-selection.json', '--file').returncode == 0
    cache = root/'.read-input/navigation.json'
    before = cache.read_bytes()
    mismatch = call(*source_flags, *next_page)
    assert mismatch.returncode == 1
    message = mismatch.stdout.decode()
    assert 'selection mismatch' in message and 'material changed' not in message
    assert cache.read_bytes() == before
    recovery = shlex.split(re.search(r'replay: ([^\]]+)', message).group(1))
    assert recovery[:2] == ['python', 'tools/read_input.py']
    assert recovery[2:] == next_page
    recovered = call(*recovery[2:])
    assert recovered.returncode == 0
    expected = '\n'.join(f'[field {i}]\n'+json.dumps(value, ensure_ascii=False)
                         for i, value in enumerate(guides.values(), 1))
    combined = body(first.stdout.decode())+body(recovered.stdout.decode())
    assert combined == expected[:len(combined)]


def test_installed_same_file_handle_restores_omitted_fields_after_interleaved_read(tmp_path):
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_guidescontinue',
        inputs=(), assignment=b'{}', result_schema=b'{}')
    root = workspace.root
    guides = {f'g{i}': ('原始细则'+str(i))*1000 for i in range(4)}
    (root/'worker-guides.json').write_text(json.dumps({'guides':guides}, ensure_ascii=False))
    (root/'other-guides.json').write_text('{"other":"unrelated helper selection"}')
    cmd = [sys.executable, '-I', str(root/'tools/read_input.py')]
    def call(*args):
        return subprocess.run(cmd+list(args), cwd=tmp_path, capture_output=True, timeout=5)
    pointers = [flag for name in guides for flag in ('--pointer','/guides/'+name)]
    first = call('worker-guides.json','--file',*pointers,'--budget','512')
    assert first.returncode == 0
    continuation = next_arguments(first.stdout.decode())
    expected = call(*continuation)
    assert expected.returncode == 0
    assert call('other-guides.json','--file').returncode == 0
    # The original source plus handle is sufficient; no pointer list is repeated.
    recovered = call('worker-guides.json','--file',*continuation)
    assert recovered.returncode == 0 and recovered.stdout == expected.stdout
    assert len(recovered.stdout) <= 512
    source = root/'worker-guides.json'
    source.write_text('{"changed":"different frozen bytes"}')
    before = (root/'.read-input/navigation.json').read_bytes()
    changed = call('worker-guides.json','--file',*continuation)
    assert changed.returncode == 1 and b'material changed' in changed.stdout
    assert (root/'.read-input/navigation.json').read_bytes() == before


@pytest.mark.parametrize('flags',[dict(pointers=['/a','/b']),dict(pointers=['/keys'],directory=True)])
def test_same_source_handle_restores_fields_and_rechecks_current_path_permissions(tmp_path, flags):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    values = {'a':'甲'*900,'b':'乙'*900,'keys':{f'字段{i}':i for i in range(200)}}
    bind_reader_input(tmp_path,json.dumps(values,ensure_ascii=False))
    first = read(tmp_path,'experiment_plan',budget=512,**flags)
    handle = replay_arguments(first)[1]; offset = int(next_arguments(first)[3])
    expected = read(tmp_path,selection_id=handle,offset=offset)
    assert read(tmp_path,'plan_original',selection_id=handle,offset=offset) == expected
    cache = tmp_path/CACHE_DIRECTORY/'navigation.json'; before = cache.read_bytes()
    with pytest.raises(ValueError,match='selection mismatch'):
        read(tmp_path,'plan_original',pointers=['/a'],selection_id=handle,offset=offset)
    assert cache.read_bytes() == before
    assignment = tmp_path/'assignment.json'
    document = json.loads(assignment.read_text())
    for item in document['inputs']:item['exposure'] = 'file_reference'
    assignment.write_text(json.dumps(document))
    with pytest.raises(ValueError,match='metadata only'):
        read(tmp_path,'plan_original',selection_id=handle,offset=offset)
    assert cache.read_bytes() == before


@pytest.mark.parametrize('repeat_pointers', [False, True])
def test_changed_handle_source_never_suggests_old_offset_replay(tmp_path, repeat_pointers):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    bind_reader_input(tmp_path, json.dumps({'selected': '原文'*3000}))
    first = read(tmp_path, 'plan_original', pointers=['/selected'], budget=512)
    handle = replay_arguments(first)[1]
    offset = int(next_arguments(first)[3])
    cache = tmp_path/CACHE_DIRECTORY/'navigation.json'
    before = cache.read_bytes()
    (tmp_path/'inputs/opaque.json').write_bytes(b'\xff')
    with pytest.raises(ValueError, match='material changed') as rejected:
        read(tmp_path, 'plan_original', pointers=['/selected'] if repeat_pointers else None,
             selection_id=handle, offset=offset, budget=512)
    assert 'selection mismatch' not in str(rejected.value)
    assert 'replay:' not in str(rejected.value)
    assert cache.read_bytes() == before


def test_installed_parallel_replay_pages_keep_source_fields_directory_and_alias(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    name = 'source $(touch forbidden); "quoted"'
    path = 'inputs/odd name;$(touch forbidden).json'
    values = {'a': '甲'*800, 'b': '乙'*900, 'small':'原文🌍'}
    directory = {f'key_{i:04d}': i for i in range(400)}
    text = json.dumps(values, ensure_ascii=False)
    metadata = dict(exposure='on_demand', media_type='application/json', schema_id='opaque',
        size_bytes=len(text.encode()))
    inputs = [dict(metadata, source_name=name, relative_path=path),
        dict(metadata, source_name='alias', relative_path=path, same_source_as=name),
        dict(source_name='keys', relative_path='inputs/keys.json', exposure='on_demand')]
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_selectedpages',
        inputs=(), assignment=json.dumps({'inputs': inputs}).encode(), result_schema=b'{}')
    root = workspace.root
    (root/path).write_text(text)
    (root/'inputs/keys.json').write_text(json.dumps(directory))
    cmd = [sys.executable, '-I', str(root/'tools/read_input.py')]
    def call(*args):
        return subprocess.check_output(cmd+list(args), cwd=tmp_path, timeout=5).decode()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(call, name, '--pointer', '/a', '--pointer', '/b', '--budget', '512')
        b = pool.submit(call, 'keys', '--directory', '--budget', '768')
        replies = [a.result(), b.result()]
    commands = [replay_arguments(reply) for reply in replies]
    assert commands[0][1] != commands[1][1] and len(commands[0][1]) == 32
    assert not any(value in ' '.join(commands[0]) for value in ('quoted', 'touch', 'inputs/'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        copies = list(pool.map(lambda _: call(*commands[0]), range(2)))
    assert copies == [replies[0], replies[0]]
    reused = call('alias', '--pointer', '/a', '--pointer', '/b', '--budget', '512')
    assert 'cached navigation is not proof of reading' in reused
    assert replay_arguments(reused) == commands[0]
    call('keys', '--directory', '--offset', '0', '--budget', '768')
    assert call(*replay_arguments(reused)) == replies[0]
    parts = [[body(reply)] for reply in replies]
    active = [True, True]
    while any(active):
        for index in range(2):
            if active[index]:
                reply = call(*next_arguments(replies[index]))
                assert len(reply.encode()) <= (512 if index == 0 else 768)
                assert call(*replay_arguments(reply)) == reply
                parts[index].append(body(reply))
                active[index] = not finished(reply)
                replies[index] = reply
    expected = '[field 1]\n'+json.dumps(values['a'], ensure_ascii=False)+'\n[field 2]\n'+json.dumps(values['b'], ensure_ascii=False)
    assert ''.join(parts[0]) == expected
    assert [item['key'] for item in json.loads(''.join(parts[1]))['fields']] == list(directory)
    assert not (tmp_path/'forbidden').exists() and not (root/'forbidden').exists()
    # Old pages and terminal alias notices remain replayable after other reads.
    assert body(call(*commands[0])).startswith('[field 1]')
    terminal_offset = replay_arguments(replies[0])[3]
    terminal = call(name, '--pointer', '/a', '--pointer', '/b', '--offset', terminal_offset, '--budget', '512')
    alias_end = call('alias', '--pointer', '/a', '--pointer', '/b', '--budget', '512')
    assert finished(alias_end) and '0 characters remain' in alias_end
    call('keys', '--directory', '--offset', '0')
    assert call(*replay_arguments(alias_end)) == terminal
    # Arbitrary-file selections also return shell-safe replay commands.
    file_page = call(path, '--file', '--pointer', '/b', '--budget', '512')
    call('keys', '--directory', '--offset', '0')
    assert call(*replay_arguments(file_page)) == file_page
    # Empty terminal pages retain the source selection, too.
    empty = call(*replay_arguments(terminal)[:2], '--offset', str(len(expected)), '--budget', '512')
    assert finished(empty) and body(empty) == ''
    assert call(*replay_arguments(empty)) == empty
    # A complete single field and a directory also expose replay at terminal aliases.
    for flags in (('--pointer', '/small'), ('--directory',)):
        page = call(name, *flags, '--budget', '512')
        notice = call('alias', *flags, '--budget', '512')
        assert finished(page) and finished(notice)
        assert 'cached navigation is not proof of reading' in notice
        call('keys', '--directory', '--offset', '0')
        assert call(*replay_arguments(notice)) == page


def test_replay_page_changes_cache_loss_unicode_positions_and_limits(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    text = '甲乙🌍\n'*2000
    bind_reader_input(tmp_path, text)
    first = read(tmp_path, 'experiment_plan', budget=512)
    handle = replay_arguments(first)[1]
    next_start = int(next_arguments(first)[3])
    second = read(tmp_path, selection_id=handle, offset=next_start, budget=512)
    assert body(first)+body(second) == text[:len(body(first))+len(body(second))]
    assert body(read(tmp_path, selection_id=handle, offset=1, budget=512)).startswith('乙🌍')
    assert read(tmp_path, selection_id=handle, offset=0, budget=512) == first
    larger = read(tmp_path, selection_id=handle, offset=0, budget=1024)
    assert len(larger.encode()) <= 1024 and len(body(larger)) > len(body(first))
    for kwargs, message in (({'budget':8193}, '8192'), ({'offset':-1}, 'nonnegative'),
            ({'offset':True}, 'nonnegative'), ({'offset':len(text)+1}, 'outside'),
            ({'offset':0, 'action':'next'}, 'without legacy')):
        with pytest.raises(ValueError, match=message):
            read(tmp_path, selection_id=handle, **kwargs)
    assert read(tmp_path, 'experiment_plan', selection_id=handle, offset=0, budget=512) == first
    with pytest.raises(ValueError, match='field flags require'):
        read(tmp_path, selection_id=handle, pointers=['/a'], offset=0)
    with pytest.raises(ValueError, match='selection missing'):
        read(tmp_path, selection_id='f'*32, offset=0)
    cache = tmp_path/CACHE_DIRECTORY/'navigation.json'
    cache.unlink()
    with pytest.raises(ValueError, match='selection missing'):
        read(tmp_path, selection_id=handle, offset=next_start)
    assert read(tmp_path, 'experiment_plan', selection_id=handle, offset=next_start, budget=512) == second
    cache.write_text('damaged')
    with pytest.raises(ValueError, match='damaged'):
        read(tmp_path, selection_id=handle, offset=0)
    assert read(tmp_path, 'experiment_plan', selection_id=handle, offset=0, budget=512) == first
    cache.unlink()
    (tmp_path/'inputs/opaque.json').write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        read(tmp_path, 'experiment_plan', selection_id=handle, offset=0, budget=512)
    assert read(tmp_path, 'experiment_plan', offset=0, budget=512) != first
    (tmp_path/'inputs/opaque.json').write_text(text)
    assert read(tmp_path, 'experiment_plan', offset=0, budget=512) == first
    (tmp_path/'inputs/opaque.json').write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        read(tmp_path, selection_id=handle, offset=0)
    with pytest.raises(ValueError, match='changed'):
        read(tmp_path, 'experiment_plan', offset=next_start, budget=512)
    current = read(tmp_path, 'experiment_plan', offset=0, budget=512)
    assert body(current) == 'changed' and replay_arguments(current)[1] != handle
    current_handle = replay_arguments(current)[1]
    (tmp_path/'inputs/opaque.json').unlink()
    (tmp_path/'inputs/opaque.json').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='within'):
        read(tmp_path, selection_id=current_handle, offset=0)


def test_complete_single_page_alias_replays_its_source_after_other_reads(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read
    equivalent_inputs(tmp_path, '原文🌍')
    (tmp_path/'other.txt').write_text('Other source')
    first = read(tmp_path, 'task', budget=512)
    alias = read(tmp_path, 'context', budget=512)
    assert finished(first) and finished(alias)
    assert 'cached navigation is not proof of reading' in alias
    assert replay_arguments(alias) == replay_arguments(first)
    read(tmp_path, 'other.txt', file=True)
    handle = replay_arguments(alias)[1]
    assert read(tmp_path, selection_id=handle, offset=0, budget=512) == first
    assert '--repeat' not in alias and '--restart' not in alias and '--next' not in alias


def test_source_field_and_directory_offset_recovery_without_cache(tmp_path):
    from scidiscovery.artifact_agent.service.input_reader import read, CACHE_DIRECTORY
    values = {'a': '甲'*900, 'b': '乙'*900, 'keys': {f'字段{i}': i for i in range(200)}}
    bind_reader_input(tmp_path, json.dumps(values, ensure_ascii=False))
    for flags in (dict(pointers=['/a','/b']), dict(pointers=['/keys'], directory=True)):
        first = read(tmp_path, 'experiment_plan', budget=512, **flags)
        offset = int(next_arguments(first)[3])
        second = read(tmp_path, selection_id=replay_arguments(first)[1], offset=offset, budget=512)
        (tmp_path/CACHE_DIRECTORY/'navigation.json').unlink()
        assert read(tmp_path, 'plan_original', selection_id=replay_arguments(first)[1], offset=offset, budget=512, **flags) == second


def test_installed_complete_selection_recovers_stale_cache_fingerprint(tmp_path):
    workspace = LocalTrustedBackend(tmp_path/'backend').prepare(run_id='run_stalefingerprint',
        inputs=(), assignment=json.dumps({'inputs': [dict(source_name='original',
            relative_path='inputs/text.txt')]}).encode(), result_schema=b'{}')
    source = workspace.root/'inputs/text.txt'
    source.write_text('原文🌍\n'*2000)
    cmd = [sys.executable, '-I', str(workspace.root/'tools/read_input.py')]
    def call(*args):
        return subprocess.run(cmd+list(args), cwd=tmp_path, capture_output=True, timeout=5)
    first = call('original', '--budget', '512')
    assert first.returncode == 0
    second = call(*next_arguments(first.stdout.decode()))
    assert second.returncode == 0
    replay = replay_arguments(second.stdout.decode())
    cache = workspace.root/'.read-input/navigation.json'
    state = json.loads(cache.read_text())
    for entry in state.values():
        if isinstance(entry, dict) and 'fingerprint' in entry:
            entry['fingerprint'] = '0'*64
    cache.write_text(json.dumps(state))
    # Without a retained version, a nonzero offset must fail closed on a stale
    # fingerprint. With the exact handle, current source bytes establish identity.
    versionless = call('original', '--offset', replay[3], '--budget', '512')
    assert versionless.returncode == 1 and b'material changed' in versionless.stdout
    recovered = call('original', *replay)
    assert recovered.returncode == 0 and recovered.stdout == second.stdout
    source.write_text('changed source\n'*2000)
    changed = call('original', *replay)
    assert changed.returncode == 1 and b'material changed' in changed.stdout
