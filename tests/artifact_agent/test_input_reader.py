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
    assert result.stdout.decode() == '1e-999\n[read_input: end]\n'
    assert not script.stat().st_mode & 0o222


def body(reply):
    return reply.rsplit('\n[read_input: ', 1)[0]


def collect_view(root, name, **kwargs):
    from scidiscovery.artifact_agent.service.input_reader import read
    reply = read(root, name, **kwargs)
    parts = []
    while True:
        assert len(reply.encode()) <= kwargs.get('budget', 4096)
        parts.append(body(reply))
        if reply.endswith('[read_input: end]\n'):
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
    assert json.loads(collect_view(tmp_path, 'experiment_plan', directory=True)) == list(json.loads(text))


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
    assert read(tmp_path, 'empty', file=True, action='next') == '[read_input: end]\n'
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
        if reply.endswith('[read_input: end]\n'):break
    assert ''.join(parts)==json.dumps(text,ensure_ascii=False)
    assert read(tmp_path,action='next')=='[read_input: end]\n'
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
