"""Unified configuration uses real preparation validation without native calls."""
import json

import pytest

from scidiscovery.research_loop import cli, contracts as c, research_config


def declaration(tmp_path, extra='', *, root='instance'):
    public = tmp_path / 'public'
    public.mkdir(exist_ok=True)
    (public / 'objective.md').write_text('Compare alternatives and retain limitations.')
    path = tmp_path / 'research.toml'
    path.write_text(f'''version = 1
[research]
root = {json.dumps(root)}
objective = "public/objective.md"
public_root = "public"
[agent]
launcher = ["never-launched"]
[budget]
max_tokens = 1000
max_seconds = 120
max_steps = 8
''' + extra)
    return path


def output(capsys):
    return json.loads(capsys.readouterr().out)


def test_basic_token_budget_edit_retains_all_other_declaration_semantics(tmp_path):
    path = declaration(tmp_path, '\n[permissions]\nweb = "cached"\nnetwork = false\n')
    for original in (path.read_text(), path.read_text().replace('max_tokens = 1000\n', '')):
        edited = research_config.with_token_budget(original, 1234)
        expected = research_config.tomllib.loads(original)
        expected['budget']['max_tokens'] = 1234
        assert research_config.tomllib.loads(edited) == expected
        assert '[permissions]\nweb = "cached"\nnetwork = false' in edited
    assert research_config.read_declaration(path)['budget']['max_tokens'] == 1000
    for invalid in (None, 0, -1, True, '1000'):
        with pytest.raises(ValueError, match='positive integer'):
            research_config.with_token_budget(path.read_text(), invalid)


def test_basic_budget_editor_fails_closed_for_unsupported_layout():
    original = 'budget = {max_tokens = 1, max_steps = 2, max_seconds = 3}\n'
    with pytest.raises(ValueError, match='advanced editor'):
        research_config.with_token_budget(original, 1000)


def test_real_cli_config_check_is_read_only_and_prepare_freezes_effective_fields(tmp_path, capsys, monkeypatch):
    config = declaration(tmp_path, '''
[agent.roles.W]
model = "worker-model"
[permissions]
workspace = "danger-full-access"
network = true
web = "cached"
subagents = true
[ui]
port = 7000
approval_secret_file = "private/operator.key"
''')
    # Credential references are not files to import, copy, or disclose as science.
    monkeypatch.chdir(tmp_path.parent)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*'))
    assert cli.main(['config-check', '--config', str(config)]) == 0
    checked = output(capsys)
    assert checked['source'] == 'research_config'
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*')) == before
    assert not (tmp_path / 'instance').exists()
    assert cli.main(['prepare', '--config', str(config)]) == 0
    assert output(capsys)['status'] == 'prepared'
    root = tmp_path / 'instance'
    original = (root / 'settings.json').read_bytes()
    settings = c.settings(root)
    assert settings['native_options']['network'] is True
    assert settings['native_options']['workspace'] == 'danger-full-access'
    assert settings['role_profiles']['W']['model'] == 'worker-model'
    assert settings['role_profiles']['H']['model'] == research_config.DEFAULT_MODEL
    assert settings['ui']['approval_secret_file'] == str(tmp_path / 'private/operator.key')
    assert not (tmp_path / 'private').exists()
    config.write_text('invalid TOML = [')
    assert cli.main(['config-inspect', '--root', str(root)]) == 0
    assert output(capsys)['settings'] == settings
    assert (root / 'settings.json').read_bytes() == original
    job = c.build_job(root, 1, 'H', [])
    science = json.dumps(c.read(c.workspace(root, 1) / 'science-task.json'))
    assert 'approval_secret_file' not in science
    assert 'operator.key' not in science
    assert job['native_profile']['model'] == research_config.DEFAULT_MODEL


def test_toml_and_existing_cli_flags_share_defaults(tmp_path, capsys):
    config = declaration(tmp_path)
    assert cli.main(['prepare', '--config', str(config)]) == 0
    output(capsys)
    assert cli.main(['prepare', '--root', str(tmp_path / 'flags'),
        '--objective', str(tmp_path / 'public/objective.md'), '--public-root', str(tmp_path / 'public'),
        '--native-launcher-json', '["never-launched"]', '--max-tokens', '1000',
        '--max-seconds', '120', '--max-steps', '8']) == 0
    output(capsys)
    a, b = (c.settings(tmp_path / name) for name in ('instance', 'flags'))
    for settings in (a, b):
        for key in ('goal_id', 'source_provenance'):
            settings.pop(key)
    assert a == b


@pytest.mark.parametrize('extra, expected', [
    ('\n[permissions]\nnetwrok = true\n', 'unknown netwrok'),
    ('\n[agent.native]\napi_key = "private-value-must-not-appear"\n', 'unknown api_key'),
    ('\n[ui]\nport = -1\n', 'ui.port'),
    ('\n[budget.correction]\nreview_after = 0\npause_after = 2\n', 'positive integer'),
    ('\n[budget.breadth]\ninitial_calls = 1\n', 'Search policy'),
])
def test_meaningful_typos_and_invalid_policy_reject_before_creation(tmp_path, capsys, extra, expected):
    config = declaration(tmp_path, extra)
    assert cli.main(['prepare', '--config', str(config)]) == 1
    result = output(capsys)
    assert expected in result['error']
    assert 'private-value-must-not-appear' not in result['error']
    assert not (tmp_path / 'instance').exists()


def test_config_cannot_mix_an_override_or_write_existing_instance(tmp_path, capsys):
    config = declaration(tmp_path)
    assert cli.main(['prepare', '--config', str(config), '--model', 'other']) == 1
    assert 'cannot be combined' in output(capsys)['error']
    assert not (tmp_path / 'instance').exists()
    assert cli.main(['prepare', '--config', str(config)]) == 0
    output(capsys)
    original = (tmp_path / 'instance/settings.json').read_bytes()
    assert cli.main(['prepare', '--config', str(config)]) == 1
    assert 'fresh directory' in output(capsys)['error']
    assert (tmp_path / 'instance/settings.json').read_bytes() == original


def test_protocol_configuration_requires_its_own_model(tmp_path):
    path = declaration(tmp_path)
    path.write_text(path.read_text().replace('[agent]', '[agent]\nbackend = "protocol"'))
    with pytest.raises(ValueError, match='explicit model'):
        research_config.prepare(path, validate_only=True)
    assert not (tmp_path / 'instance').exists()


@pytest.mark.parametrize('enabled', [True, False])
def test_policy_preview_and_prepared_instance_agree_without_preview_artifacts(tmp_path, capsys, enabled):
    value = str(enabled).lower()
    config = declaration(tmp_path, f'\n[policies]\nformal_review = {value}\nexecution_authority = {value}\n')
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*'))
    assert cli.main(['config-check', '--config', str(config)]) == 0
    preview = output(capsys)['settings']
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*')) == before
    assert cli.main(['prepare', '--config', str(config)]) == 0
    output(capsys)
    root = tmp_path / 'instance'
    prepared = c.settings(root)
    for key in ('formal_review_policy', 'execution_authority_policy'):
        assert (key in preview) is enabled
        assert (key in prepared) is enabled
        if enabled:
            assert preview[key] == {'version': 1}
            assert prepared[key]['version'] == preview[key]['version']
            assert (root / prepared[key]['contract']['path']).is_file()
        else:
            assert not (root / 'qualification/review-contract.json').exists()
            assert not (root / 'execution-authority/contract.json').exists()


def test_policy_preview_rejects_authority_without_review_before_creation(tmp_path, capsys):
    config = declaration(tmp_path, '\n[policies]\nformal_review = false\nexecution_authority = true\n')
    assert cli.main(['config-check', '--config', str(config)]) == 1
    assert 'requires the explicit formal review contract' in output(capsys)['error']
    assert not (tmp_path / 'instance').exists()
