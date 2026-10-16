"""Small shared administrator policy fixture; no installer or solver side effects."""
import json
from pathlib import Path


def policy_fields():
    source = Path(__file__).resolve().parents[2] / "plugins/tcad_artifact/config/execution-policy.example.json"
    value = json.loads(source.read_text())
    return {key: value[key] for key in ("agent_execution_policy", "runner", "debug")}


def policy_snapshot():
    from tcad_artifact.execution_policy import ExecutionPolicySnapshot
    return ExecutionPolicySnapshot.model_validate_json(json.dumps(policy_fields()), strict=True)
