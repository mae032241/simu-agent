"""Native participant routing and durable access; no model or CLI transport fixture."""
import json
from pathlib import Path

import pytest


def _result(reply):
    assert 'error' not in reply, reply
    return reply['result']['structuredContent']


def test_stage_and_submission_authority_are_declared_once():
    from scidiscovery.general_science_experiment_task import STAGE_TOOL
    from scidiscovery.operations.lifecycle import AGENT_LIFECYCLE_PROTOCOL
    assert STAGE_TOOL.owner_only
    assert next(item for item in AGENT_LIFECYCLE_PROTOCOL.tools if item.name == 'worker_submit_result').owner_only
