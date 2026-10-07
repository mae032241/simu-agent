"""Generated reader and explicit owner write->submit through the public gateway."""
import json
from pathlib import Path
import shlex
import subprocess
import sys

from scidiscovery.artifact_agent.interfaces.mcp_gateway import CallInput, UnifiedMCPRouter
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.input_reader import read
from tests.artifact_agent.test_input_reader import body
from tests.operations.test_native_experiment import installed, _start_native, _publish
from tests.operations.test_unified_mcp import rpc, result
from tests.operations.worker_fixtures import attached_worker


def test_generated_closeout_entry_reads_fields_and_explicitly_submits_after_write(tmp_path, installed):
    f = _start_native(tmp_path)
    original = _publish(f, 'observation.json', b'{"outcome":"inconclusive","limitation":"Bounded observation only."}',
        ['objective_source'])
    stage = f.worker.call_tool('worker_experiment_stage', dict(stage='validity',
        conclusion='This bounded observation does not settle the mechanism.', materials=[original]))['reference']
    (f.workspace/'output/result.json').write_bytes(canonical_json(dict(payload=dict(summary='Finite observations retained.',
        outcome='inconclusive', remaining_question='Independent interpretation remains.', adopted_stages=[stage]))))
    assert f.worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    subject = f.root.call_tool('run_status', dict(name='compute'))['output_artifact_name']
    f.root.call_tool('operation_invoke', dict(name='analysis', operation_id='science.result.analyze.v1',
        inputs=[dict(port='subject', artifact_names=[subject])], instruction='Interpret the finite question before closeout.'))
    analyst = attached_worker(f.runtime, f.root, 'analysis')
    opened = analyst.call_tool('worker_open_assignment', {})
    workspace = Path(opened['workspace_path'])
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    submit = start['output']['submit']
    CallInput.model_validate(submit)  # These are actual scid_call arguments.
    command = shlex.split(start['output']['read'])
    overview_raw = subprocess.check_output([sys.executable, '-I', *command[1:]], cwd=workspace, timeout=10)
    overview = json.loads(overview_raw)
    assert len(overview_raw) < 8192 and overview['format'] == 'reading_sections'
    required = overview['overview']['properties']['payload']['required']
    assert set(required) == {'summary', 'overall_verdict', 'claim_allowed'}
    detail = json.loads(subprocess.check_output([sys.executable, '-I', *command[1:],
        '--field', 'hypothesis_assessments', '--field', 'evidence'], cwd=workspace, timeout=10))
    assert detail['definitions']
    hypothesis = json.loads(body(read(workspace, 'hypothesis_portfolio', pointers=['/hypotheses/0/hypothesis_key'])))
    report = dict(summary='The retained finite observations leave the mechanism unresolved.', overall_verdict='inconclusive',
        claim_allowed=False, limitations=['No unobserved conditions are validated.'],
        evidence=[dict(source_key='experiment_results', source_type='frozen_input',
            title='Exact sealed experiment observations', locator='experiment_results')],
        hypothesis_assessments=[dict(hypothesis_key=hypothesis, outcome='inconclusive',
            evidence_keys=['experiment_results'], rationale='The exact bounded observation is insufficient.')])
    run_id = analyst._run_id
    profile = f.runtime.runs.status(run_id).execution_profile['profile']
    gateway = UnifiedMCPRouter(f.root)
    target = Path(opened['output_directory'])/'result.json'
    denied = rpc(gateway, 'scid_call', submit, session='source-test-session', child='unattached', profile=profile)
    assert 'error' in denied  # The generated entry grants no ownership.
    assert f.runtime.runs.status(run_id).state == 'running'

    def owner_write_then_submit(payload):
        target.write_bytes(canonical_json(dict(payload=payload)))
        # A written draft is never auto-sealed. The owner explicitly invokes
        # the generated submit call immediately after successful writing.
        assert f.runtime.runs.status(run_id).state == 'running'
        return result(rpc(gateway, 'scid_call', submit, session='source-test-session',
            child='worker-'+run_id, profile=profile))

    rejected = owner_write_then_submit(dict(summary='Missing required verdict.'))
    assert rejected['state'] == 'rejected' and rejected['diagnostics']
    assert f.runtime.runs.status(run_id).state == 'running'
    completed = owner_write_then_submit(report)
    assert completed['state'] == 'completed', completed.get('diagnostics')
    assert f.runtime.runs.status(run_id).state == 'completed'
    assert f.root.call_tool('run_status', dict(name='analysis'))['state'] == 'completed'
