"""Real owner-tool delivery and sealed H-W-A-W-A, without models or solvers."""

import pytest

from scidiscovery.agent_execution_settings import ProgressionSettings


@pytest.mark.parametrize('value', [1, 29, 86401, True])
def test_checkpoint_configuration_rejects_out_of_bounds(value):
    with pytest.raises(ValueError, match='worker_checkpoint_seconds'):
        ProgressionSettings(worker_checkpoint_seconds=value)
