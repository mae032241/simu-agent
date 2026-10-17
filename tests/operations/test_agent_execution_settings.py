"""Execution configuration ownership, precedence and persisted settings."""
import json

import pytest

from scidiscovery.agent_execution_settings import (
    AgentSettings, ExecutionProfile, load_settings, packaged_default_model, parse_settings, resolve_settings,
)


def test_sparse_precedence_and_unknown_operation_retention():
    global_settings = parse_settings({"defaults": {"model": "global", "narrative_language": "zh-CN"},
        "operations": {"fixture": {"model": "global-op", "max_attempts": 4}}})
    instance = parse_settings({"defaults": {"model": "instance", "reasoning_effort": "low"},
        "operations": {"fixture": {"reasoning_effort": "high"}, "disabled-plugin": {"model": "retained"}}})
    value = resolve_settings(global_settings, instance, operation_id="fixture",
                             operation_model="legacy", operation_max_attempts=2)
    assert value["profile"].model_dump() == dict(model="instance", reasoning_effort="high", narrative_language="zh-CN")
    assert value["max_attempts"] == 4
    assert value["sources"] == dict(model="instance.defaults", reasoning_effort="instance.operation",
                                   narrative_language="global.defaults", max_attempts="global.operation")
    assert instance.sparse()["operations"]["disabled-plugin"] == {"model": "retained"}
    cleared = resolve_settings(global_settings, parse_settings({}), operation_id="fixture",
                               operation_model="legacy", operation_max_attempts=2)
    assert cleared["profile"].model == "global-op"


def test_execution_profile_uses_canonical_platform_model_identity():
    profile = ExecutionProfile(
        model="gpt-6-Astra", reasoning_effort="high", narrative_language="zh-CN"
    )
    assert profile.model == "gpt-6-astra"


@pytest.mark.parametrize('settings', [
    {'evidence_capacity': {'max_new_records': 129}},
    {'evidence_capacity': {'max_controlled_attempts': 65}},
    {'evidence_capacity': {'max_controlled_attempts': 0}},
    {'evidence_capacity': {'max_new_records': 32}},
])
def test_evidence_capacity_rejects_wire_incompatible_or_attachment_combination(settings):
    with pytest.raises(ValueError):
        parse_settings(settings)


def test_evidence_capacity_can_tighten_admission_without_changing_wire_bounds():
    settings = parse_settings({'attachments': {'max_files': 16},
        'evidence_capacity': {'max_new_records': 32, 'max_controlled_attempts': 16}})
    assert settings.attachments.max_files == 16
    assert settings.evidence_capacity.max_new_records == 32
    assert settings.evidence_capacity.max_controlled_attempts == 16
    assert AgentSettings().evidence_capacity.model_dump() == dict(max_new_records=128, max_controlled_attempts=64)


def test_packaged_model_default_is_configured_and_overridable():
    assert packaged_default_model() == "gpt-6-sol"
    baseline = resolve_settings(AgentSettings(), AgentSettings(), operation_id="fixture",
        operation_model=None, operation_max_attempts=2)
    assert baseline["profile"].model == "gpt-6-sol"
    assert baseline["sources"]["model"] == "package_default"
    overridden = resolve_settings(parse_settings({"defaults": {"model": "global"}}),
        AgentSettings(), operation_id="fixture", operation_model=None, operation_max_attempts=2)
    assert overridden["profile"].model == "global"
    assert overridden["sources"]["model"] == "global.defaults"


@pytest.mark.parametrize("value,field", [
    ({"defaults": {"model": None}}, "model"),
    ({"defaults": {"max_attempts": True}}, "max_attempts"),
    ({"defaults": {"max_attempts": 0}}, "max_attempts"),
    ({"defaults": {"reasoning_effort": "invalid"}}, "reasoning_effort"),
    ({"operations": {"fixture": {"narrative_language": "en"}}}, "narrative_language"),
    ({"hidden_option": True}, "hidden_option"),
    ({"execution_io": {"max_export_bytes": True}}, "max_export_bytes"),
    ({"execution_io": {"file_timeout_seconds": 0}}, "file_timeout_seconds"),
    ({"execution_io": {"read_page_bytes": 262145}}, "read_page_bytes"),
])
def test_configuration_errors_retain_field(value, field):
    with pytest.raises(ValueError, match=field):
        parse_settings(value)


def test_file_missing_inherits_but_invalid_file_reports_path(tmp_path):
    path = tmp_path / "agent-settings.json"
    assert load_settings(path).sparse() == {}
    path.write_text(json.dumps({"defaults": {"reasoning_effort": "invalid"}}))
    with pytest.raises(ValueError, match="(?s)agent-settings.json.*reasoning_effort"):
        load_settings(path)
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="agent-settings.json"):
        load_settings(path)


def test_progression_disable_inherits_without_instance_reenabling_deployment():
    from scidiscovery.agent_execution_settings import effective_settings
    assert not effective_settings(parse_settings({'progression': {'enabled': False}}),
        {'progression': {'enabled': True}})['progression']['enabled']
    assert not effective_settings(parse_settings({}),
        {'progression': {'enabled': False}})['progression']['enabled']
    assert effective_settings(parse_settings({}), {})['progression']['enabled']


def test_background_root_permissions_are_configurable_but_keep_inherited_worker_needs():
    from types import SimpleNamespace
    from scidiscovery.agent_execution_settings import effective_settings, root_permission_conflicts
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from scidiscovery.operations.catalog import compile_catalog
    default = effective_settings(parse_settings({}), {})['progression']
    assert (default['root_approval_policy'], default['root_sandbox'], default['root_network_access']) == (
        'never', 'workspace-write', True)
    offline = {'root_sandbox': 'read-only', 'root_network_access': False}
    assert effective_settings(parse_settings({'progression': offline}), {})['progression']['root_sandbox'] == 'read-only'
    with pytest.raises(Exception, match='requires root_sandbox workspace-write'):
        parse_settings({'progression': {'root_sandbox': 'read-only'}})  # network cannot be declared read-only
    for value in ({'root_approval_policy': 'on-request'}, {'root_sandbox': 'danger-full-access'}):
        with pytest.raises(Exception):
            parse_settings({'progression': value})
    # Workers inherit Root permissions: a narrowing choice names every affected Operation.
    catalog = compile_catalog((CORE_PLUGIN, science))
    assert root_permission_conflicts(default, catalog) == []
    issues = root_permission_conflicts(offline, catalog)
    assert 'inherited native shell' in issues[0] and 'science.experiment.v1' in issues[0]
    assert 'declared network or web_search' in issues[1] and 'science.evidence.extract.v1' in issues[1]
    assert 'science.experiment.v1' not in issues[1]
    offline_catalog = SimpleNamespace(operation_ids=lambda: ('offline',), operation=lambda _: SimpleNamespace(spec=SimpleNamespace(
        operation_id='offline', executor=SimpleNamespace(kind='agent', native_tools=SimpleNamespace(shell='none', web_search='disabled')),
        limits=SimpleNamespace(network=SimpleNamespace(mode='none')))))
    assert root_permission_conflicts(offline, offline_catalog) == []
