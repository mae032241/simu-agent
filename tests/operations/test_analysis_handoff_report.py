"""Compact reading and delivery through the existing production analysis lifecycle."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport


def pointer(value, path):
    for part in path.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def test_formal_summary_projection_leaves_other_role_contracts_unchanged():
    from scidiscovery.plugin_runtime.results import materialize_general_result
    for schema, payload in [
        ('scidiscovery.critic-review.v2', dict(disposition='ready_for_experiment')),
        ('scidiscovery.evidence-audit.v1', dict(checks=[dict(status='pass')])),
    ]:
        value = dict(payload=payload)
        materialize_general_result(value, schema)
        assert value['handoff'] == {'verdict': 'pass'}  # Summary remains the reviewer-authored conclusion.
    malformed = dict(payload=dict(summary=None, verdict='pass'), handoff=dict(summary=None))
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    with pytest.raises(WorkspaceProtocolError) as error:
        materialize_general_result(malformed, 'scidiscovery.scientific-review.v1')
    assert error.value.details[0]['path'] == '$.payload.summary'
    assert malformed['payload']['summary'] is malformed['handoff']['summary'] is None
