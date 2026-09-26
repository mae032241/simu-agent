"""Controlled feedback handoff; fixture outputs test transport, not LLM judgement."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_agent_contract_alignment import (
    experiment_case, _catalog, _feedback_record,
)
from tests.operations.test_general_transform_operations import _intake, _register, _root
from tests.operations.test_hypothesis_review_routing import _critic


def start(runtime, root, request):
    checked = root.call_tool('operation_preflight', request)
    assert checked['admissible'], checked
    queued = root.call_tool('operation_invoke', checked['normalized_request'])['result']
    assert queued['state'] == 'queued' and queued['agent_type'] and queued['execution_profile']
    assert 'bound_inputs' not in queued
    operation = runtime.runs.operation_catalog.operation(request['operation_id'])
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=request['operation_id'], operation_digest=operation.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    return worker, opened


def seal(worker, opened, payload, verdict='pass'):
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({
        'schema_version': 1, 'payload': payload,
        'handoff': {'verdict': verdict, 'summary': 'Synthetic engineering fixture; no scientific inference.'}}))
    return worker.call_tool('worker_submit_result', {})


def request(name, operation, ports):
    return dict(name=name, operation_id=operation,
        inputs=[dict(port=k, artifact_names=v if isinstance(v, list) else [v]) for k,v in ports.items()],
        instruction='Use the exact bound records and their stated limits.')
