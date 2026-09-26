"""Replay real summary producer; no VM, solver or tool-interface substitute."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tcad_artifact.local_debug_service import debug_summary
from tcad_artifact.role_pack import role_prompt
from scidiscovery.artifact_agent.service.input_reader import page


@pytest.mark.parametrize('state,timed_out', [('running',False), ('failed',False), ('cancelled',False), ('failed',True)])
def test_author_reads_saved_diagnostic_detail(tmp_path, state, timed_out):
    from tests.operations.tcad_policy_fixtures import policy_fields
    context = SimpleNamespace(workspace=tmp_path, state={"debug_policy": policy_fields()["debug"]}, remaining_seconds=60)
    (tmp_path/'deck/reports').mkdir(parents=True)
    log = tmp_path/'deck/reports/solver.log';log.write_text('specific solver diagnostic\n')
    original = dict(run_name='probe', mode='initialization', state=state,
        progress={'elapsed_seconds':3, 'log_tails':[{'source':'solver','tail':'specific solver diagnostic'}]},
        log_excerpt='specific solver diagnostic', log_relative_path='deck/reports/solver.log')
    if timed_out:
        original['source_diagnostic'] = {'code':'development_timeout', 'message':'wall-clock limit exceeded'}
    short = debug_summary(context, 'probe', original)
    if timed_out:
        assert short['source_diagnostic'] == original['source_diagnostic']
    assert 'log_tails' not in short['progress'] and 'log_excerpt' not in short
    selected = page(tmp_path, short['details_path'], pointer='/progress/log_tails')
    assert json.loads(selected['fragment']) == original['progress']['log_tails']
    assert (tmp_path/short['log_relative_path']).read_text() == log.read_text()
    prompt = role_prompt('author')
    assert 'open details_path' in prompt and '/progress/log_tails' in prompt
    assert 'Locate keys/sections before reading' in prompt
