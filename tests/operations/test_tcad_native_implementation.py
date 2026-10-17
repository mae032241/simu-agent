"""Small local contracts; no runtime/Root/installation or solver fixture."""
import hashlib
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.execution_control import SolverCapabilitySnapshot
from tcad_artifact.native_implementation import compile_native_implementation
from tcad_artifact.project_packager import (
    ExecutionPackage, NativeExecutionPackage, NativeResolvedProjectInput,
    ScientificDeckImplementation, validate_execution_package_json,
)


def _old_document():
    return json.loads((Path(__file__).parents[1] / 'fixtures/tcad_analysis_package.json').read_bytes())


def test_v2_keeps_fixed_legacy_package_bytes():
    # Fixed legacy fixture + the old v2 envelope. Expected bytes do not come
    # from the new model/serializer; the digest pins this 2,902-byte vector.
    old = _old_document()
    raw = json.dumps(dict(schema_version=2, project=old['project'], capability=old['capability'],
        review=old['review'], resolved_inputs=[]), ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(raw).hexdigest() == '3a91a6302f39e63626a9ed1982d4f4a432803d5b51785a129b47b8874ad074c3'
    package = validate_execution_package_json(raw)
    assert type(package) is ExecutionPackage
    assert canonical_json(package.model_dump(mode='json')) == raw


def test_native_compiler_preserves_exact_origin_and_control_capture():
    # Ref objects here are declarations only; producer membership and source
    # authorization are tested at the host loader, not asserted by this test.
    old = _old_document()
    capability = SolverCapabilitySnapshot.model_validate_json(canonical_json(old['capability']), strict=True)
    slot = dict(semantic_name='mesh', target_relative_path='inputs/mesh.tdr',
                media_type='application/octet-stream')
    authored = ScientificDeckImplementation.model_validate_json(canonical_json(dict(
        solver_kind='sdevice', files=[dict(relative_path='main.cmd', content='Solve {}\n')],
        input_slots=[slot], entrypoint='main.cmd', resource_limits=old['project']['resource_limits'])), strict=True)
    original = dict(instance_id='scid-hwa-native-test', producer_step=1,
        producer_seal=dict(path='native-evidence/001/result-identity.json', sha256='a'*64, size_bytes=100),
        material_path='inputs/parents/001/artifacts/mesh.tdr',
        sha256=hashlib.sha256(b'mesh').hexdigest(), size_bytes=4)
    resolved = NativeResolvedProjectInput.model_validate_json(canonical_json(
        dict(slot, original=original, size_bytes=4)), strict=True)
    raw = compile_native_implementation(authored, capability=capability, resolved_inputs=(resolved,))
    package = NativeExecutionPackage.model_validate_json(raw, strict=True)
    assert package.schema_version == 3
    assert package.review is None
    assert package.project.preflight_attestation is None
    assert package.project.collect_generated_outputs is True
    assert package.project.tool_profile == capability.profile_id
    assert package.project.expected_outputs[0].model_dump(mode='json') == dict(
        name='process_log', capture='process_log', relative_path='.scid-capture/solver_stdout.log',
        media_type='text/plain', max_bytes=old['project']['resource_limits']['max_output_bytes'],
        required=True, experiment_key=None, case_key=None)
    assert package.resolved_inputs[0].original.model_dump(mode='json') == original
    assert 'artifact_ref' not in json.loads(raw)['resolved_inputs'][0]
    another = dict(original, producer_step=2,
        producer_seal=dict(original['producer_seal'], path='native-evidence/002/result-identity.json'),
        material_path='inputs/parents/002/artifacts/mesh.tdr')
    other = NativeResolvedProjectInput.model_validate_json(canonical_json(
        dict(slot, original=another, size_bytes=4)), strict=True)
    # Same scientific bytes do not erase the exact native producer identity.
    assert compile_native_implementation(authored, capability=capability, resolved_inputs=(other,)) != raw
    with pytest.raises(ValueError):
        NativeResolvedProjectInput.model_validate_json(canonical_json(
            dict(slot, original=original, size_bytes=5)), strict=True)
    with pytest.raises(ValueError):
        compile_native_implementation(authored, capability=capability, resolved_inputs=())
    limited = authored.model_copy(update={'resource_limits': authored.resource_limits.model_copy(
        update={'max_storage_bytes': len('Solve {}\n'.encode())+3})})
    with pytest.raises(ValueError, match='storage'):
        compile_native_implementation(limited, capability=capability, resolved_inputs=(resolved,))
