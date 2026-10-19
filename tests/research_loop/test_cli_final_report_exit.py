"""CLI exit mapping for a completed final report; no scientific dispatch."""
import json
from unittest.mock import Mock

import pytest

from scidiscovery.research_loop import cli, protocol


@pytest.mark.parametrize('status,expected_exit', [
    ('final_a_completed', 0),
    ('sealed_node_invalid', 2),
    ('seal_pending', 2),
    ('native_outcome_unsealed', 2),
    ('unrecognized_status', 2),
])
def test_run_final_report_exit_preserves_controller_result(tmp_path, monkeypatch, capsys, status, expected_exit):
    root = tmp_path / 'instance'
    result = dict(status=status, goal_completion='not_asserted')
    run = Mock(return_value=result)
    # Sealing and protocol validation belong to controller tests; isolate CLI mapping.
    monkeypatch.setattr(protocol, 'require_current', Mock())
    monkeypatch.setattr(cli.controller, 'run', run)

    assert cli.main(['run', '--root', str(root)]) == expected_exit
    run.assert_called_once_with(root)
    assert json.loads(capsys.readouterr().out) == result
