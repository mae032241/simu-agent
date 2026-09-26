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


class PreparationOnlyAdapter:
    """Exercise real control preparation/authorization with no submit capability."""

    def lookup_submission(self, submission):
        raise AssertionError("preparation must not query/submit")

    def supports_preparation_profile(self, value):
        return value == "tcad.execution-package.v2"

    def validate_preparation_payload(self, raw, *, preparation_profile):
        from tcad_artifact.project_packager import ExecutionPackage, validate_execution_package_eligibility
        assert self.supports_preparation_profile(preparation_profile)
        validate_execution_package_eligibility(ExecutionPackage.model_validate_json(raw, strict=True))
