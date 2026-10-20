"""Structured declarations retain originals and use the CLI preparation path."""
from html.parser import HTMLParser
from pathlib import Path

import pytest

from scidiscovery.research_loop import configuration_form as form, contracts, research_config


class Controls(HTMLParser):
    """Submit successful HTML controls without needing a browser or framework."""
    def __init__(self, html):
        super().__init__()
        self.fields = {}
        self.textarea = None
        self.select = None
        self.option = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name'):
            if attrs.get('type') != 'checkbox' or 'checked' in attrs:
                self.fields[attrs['name']] = attrs.get('value', '')
        if tag == 'textarea':
            self.textarea = attrs.get('name')
            self.fields[self.textarea] = ''
        if tag == 'select':
            self.select = attrs.get('name')
            self.fields[self.select] = ''
        if tag == 'option':
            self.option = attrs.get('value', '')
            if 'selected' in attrs:
                self.fields[self.select] = self.option

    def handle_endtag(self, tag):
        if tag == 'textarea': self.textarea = None
        if tag == 'select': self.select = None

    def handle_data(self, data):
        if self.textarea:
            self.fields[self.textarea] += data


def submitted(draft):
    return Controls(form.render(draft)).fields


def complete(tmp_path):
    public = tmp_path / 'public'
    public.mkdir()
    return form.imported(dict(version=1,
        research=dict(root='instance', public_root='public', objective_text='Compare exact alternatives.\nRetain limitations.'),
        agent=dict(launcher=['never-launched']),
        budget=dict(max_tokens=1000, max_seconds=120, max_steps=8)), base=tmp_path)


def test_blank_page_has_no_implicit_inputs_or_budgets(tmp_path):
    (tmp_path / 'research.toml').write_text('must not be read')
    draft = form.blank(base=tmp_path)
    fields = submitted(draft)
    assert fields['task_text'] == ''
    for key in ('research.root', 'research.public_root', 'budget.max_tokens', 'budget.max_seconds', 'budget.max_steps', 'agent.model'):
        assert fields['cfg.'+key] == ''
    assert form.parse(fields, base=tmp_path)['document'] == {}
    with pytest.raises(ValueError, match='新实例目录：必填'):
        form.preview(draft)
    draft['document'] = dict(research=dict(root='new', public_root='public'))
    with pytest.raises(ValueError, match='总 tokens 预算：必填'):
        form.preview(draft)
    assert sorted(p.name for p in tmp_path.iterdir()) == ['research.toml']


def test_complex_cov_declaration_roundtrips_all_typed_controls_and_export(tmp_path):
    draft = complete(tmp_path)
    document = draft['document']
    document['research']['source_restrictions'] = [dict(source='public/dataset.bin', sha256='a'*64, restriction='restricted')]
    document['research']['user_updates'] = []
    document['agent'].update(backend='codex', model='global', reasoning_effort='high', service_tier='default',
        roles={role:dict(model='model-'+role, reasoning_effort='high', service_tier='priority') for role in 'HWAE'},
        native=dict(sandbox_workspace_write=dict(writable_roots=['runs'], network_access=False,
            exclude_tmpdir_env_var=True, exclude_slash_tmp=True), features=dict(fast_mode=False)))
    document['permissions'] = dict(workspace='workspace-write', network=False, web='cached', subagents=False)
    document['budget'].update(node_targets={role:dict(max_observed_tokens=400,max_seconds=30) for role in 'HWAE'},
        role_shares=dict(version=1, shares=dict(H=0.1,W=0.5,A=0.3,E=0.1)),
        breadth=dict(max_w_seconds=60,max_w_observed_tokens=500,max_requested_repairs=2,initial_calls=1),
        correction=dict(review_after=3,pause_after=2),candidate_extra_slots=2,portfolio_review_after_cycles=3,
        max_output_item_bytes=10000,max_output_total_bytes=20000)
    document['executor'] = dict(mode='local', config=dict(executor='cov_execution:CovExecution',
        configuration=dict(runs_root='runs', nested=dict(enabled=True, groups=[1, 'two', dict(key='value')]))),
        resource_policy=dict(version=1,allowance=dict(wall_time_seconds=120,max_storage_bytes=1024)))
    document['delivery'] = dict(closeout_a=dict(max_observed_tokens=100,max_seconds=20), inflight_tokens=100,
        cleanup_seconds=1,submit_seconds=5,confirm_seconds=5,
        adapter=dict(adapter='adapter.py',launcher_argv=['./harness','literal-relative-arg'],config=dict(evaluation_key='v1'),
            target=dict(destination='original'),inputs=[dict(label='dataset',path='data/file')], source_roots=['public'],
            capabilities=['audit','submit'],effect_scope=dict(kind='declared')))
    document['policies'] = dict(formal_review=True,execution_authority=True,candidate_audit=False,decision_contract=True,
        worker_context='new_context',selection=dict(version=1,extra=dict(keep=[])),
        resume=dict(max_attempts=2,protocol='codex_exec_resume',usage_scope='turn',native_home='/private/native'),
        history_observer=dict(adapter='/host/observer.py',config=dict(runs='runs',evaluation_key='v1')))
    document['ui'] = dict(port=0,open_browser=False,approval_secret_file='private/operator.key')
    fields = submitted(draft)
    parsed = form.parse(fields, base=tmp_path)
    assert form.declaration(parsed) == document
    exported = research_config.tomllib.loads(form.export_toml(parsed))
    # Canonical declared paths keep their meaning when the optional file moves.
    assert research_config.from_document(exported, base=tmp_path/'elsewhere') == research_config.from_document(document,base=tmp_path)
    assert exported['executor']['config'] == document['executor']['config']
    assert exported['delivery']['adapter']['launcher_argv'][1] == 'literal-relative-arg'


def test_extensions_are_editable_and_optional_groups_can_be_omitted(tmp_path):
    draft = complete(tmp_path)
    draft['document']['executor'] = dict(config=dict(configuration=dict(flag=True,deep=[dict(value=5)])))
    fields = submitted(draft)
    flag = next(name[:-4] for name,value in fields.items() if name.endswith('.key') and value=='flag')
    fields[flag+'.value'] = 'false'
    parsed = form.parse(fields,base=tmp_path)
    assert parsed['document']['executor']['config']['configuration']['flag'] is False
    del fields['enabled.executor.config']
    assert 'executor' not in form.parse(fields,base=tmp_path)['document']
    with pytest.raises(ValueError,match='有效的整数'):
        form.parse(dict(fields, **{'cfg.budget.max_tokens':'not-integer'}),base=tmp_path)
    with pytest.raises(ValueError,match='不支持的表单字段'):
        form.parse(dict(fields, surprise='ignored?'),base=tmp_path)


def test_unknown_imported_values_are_retained_then_rejected_not_dropped(tmp_path):
    draft = complete(tmp_path)
    draft['document']['agent']['misspelled'] = dict(exact=['a',2,True])
    parsed = form.parse(submitted(draft),base=tmp_path)
    assert parsed['document']['agent']['misspelled'] == dict(exact=['a',2,True])
    with pytest.raises(ValueError,match='unknown misspelled'):
        form.preview(parsed)
    assert not (tmp_path/'instance').exists()


def test_inline_preview_has_no_writes_create_freezes_exact_original_and_update_mapping(tmp_path):
    draft = complete(tmp_path)
    update = tmp_path/'update.md'; update.write_text('Exact user update.')
    draft['document']['research']['user_updates'] = ['update.md']
    original = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob('*'))
    preview = form.preview(draft)
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob('*')) == original
    created = form.create(draft)
    root = tmp_path/'instance'
    assert created['objective'] == preview['objective'] == draft['task_text']
    objective = root/'project/global/objective.md'
    assert objective.read_bytes() == draft['task_text'].encode()
    assert objective.stat().st_mode & 0o222 == 0
    provenance = contracts.read(root/created['source_provenance']['path'])
    assert [row['origin']['path'] for row in provenance['globals']] == [str(objective),str(update)]
    assert [row['material']['source'] for row in provenance['globals']] == ['project/global/objective.md','project/global/updates/001.md']
    with pytest.raises(ValueError,match='fresh directory'):
        form.create(draft)


def test_file_and_inline_are_exclusive_and_protocol_needs_explicit_model(tmp_path):
    draft = complete(tmp_path)
    draft['document']['research']['objective'] = 'other.md'
    with pytest.raises(ValueError,match='只能选择一项'):
        form.imported(draft['document'],base=tmp_path)
    with pytest.raises(ValueError,match='exactly one'):
        research_config.from_document(draft['document'],base=tmp_path)
    del draft['document']['research']['objective']
    draft['document']['agent']['backend'] = 'protocol'
    with pytest.raises(ValueError,match='explicit model'):
        form.preview(draft)
    draft['document']['agent']['model'] = 'protocol-model'
    checked = form.preview(draft)
    assert checked['model'] == 'protocol-model'
    assert checked['reasoning_effort'] is None
    assert checked['service_tier'] is None


def test_shared_parser_file_and_document_path_meaning_agree(tmp_path):
    draft = complete(tmp_path)
    path = tmp_path/'optional.toml'
    path.write_text(form.export_toml(draft))
    assert research_config.load(path) == research_config.from_document(form.declaration(draft),base=tmp_path)
    assert form.declaration(form.load(path)) == research_config.read_declaration(path)


def test_invalid_edit_retains_all_controls_for_correction(tmp_path):
    draft = complete(tmp_path)
    draft['document']['executor'] = dict(config=dict(nested=dict(number=3)))
    fields = submitted(draft)
    fields['task_text'] = 'New exact task'
    fields['cfg.agent.model'] = 'new-model'
    fields['cfg.budget.max_tokens'] = 'oops'
    key = next(name[:-4] for name,value in fields.items() if name.endswith('.key') and value == 'number')
    fields[key+'.value'] = 'bad nested number'
    with pytest.raises(form.FormError) as caught:
        form.parse(fields,base=tmp_path)
    retained = submitted(caught.value.draft)
    assert retained['cfg.budget.max_tokens'] == 'oops'
    assert retained['cfg.agent.model'] == 'new-model'
    assert retained['task_text'] == 'New exact task'
    assert retained[key+'.kind'] == 'integer'
    assert retained[key+'.value'] == 'bad nested number'
    with pytest.raises(ValueError,match='类型错误'):
        form.create(caught.value.draft)
    assert not (tmp_path/'instance').exists()
