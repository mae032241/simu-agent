"""Deployment offline debug policy; real control fixtures, no native/model/network."""

import pytest

from scidiscovery.agent_execution_settings import AgentSettings, effective_settings, parse_settings


def test_debug_policy_is_global_and_default_off():
    assert effective_settings(AgentSettings(), {})['debug_disable_task_network'] is False
    offline = parse_settings({'debug_disable_task_network': True})
    assert effective_settings(offline, {})['progression']['root_network_access'] is False
    with pytest.raises(ValueError, match='deployment'):
        effective_settings(offline, {'debug_disable_task_network': False})
