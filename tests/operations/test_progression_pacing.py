"""Independent pacing, bounded local retries, and unchanged native authority."""

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings


@pytest.mark.parametrize('field,value', [('event_wait_seconds', 2.), ('resource_sample_seconds', 0.),
    ('budget_snapshot_seconds', float('inf')), ('observation_retries', -1), ('observation_retry_seconds', 6.)])
def test_pacing_configuration_bounds(field, value):
    with pytest.raises(ValueError):
        ProgressionSettings.model_validate({field:value})
