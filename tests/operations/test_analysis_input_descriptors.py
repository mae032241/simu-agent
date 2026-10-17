"""Shared exact-source descriptors remain immutable without a Run host."""
from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operations.input_validation import InputBindingDescriptor, ValidationSources


def _source_values():
    ref = ArtifactRef(artifact_id='original', kind='material', schema_id='opaque', sha256='a' * 64)
    contents = {'a': b'{}', 'b': b'{}'}
    descriptors = {name: InputBindingDescriptor(source_name=name, port_name='materials',
        artifact_ref=ref, media_type='application/json', size_bytes=2, sha256=ref.sha256)
        for name in contents}
    return contents, descriptors


def test_descriptors_are_deeply_readonly_and_legacy_dict_reads_work():
    contents, descriptors = _source_values()
    sources = ValidationSources(contents, descriptors)
    assert list(sources.keys()) == ['a', 'b']
    assert list(sources.items()) == [('a', b'{}'), ('b', b'{}')]
    assert sources.get('a') == b'{}'
    descriptor = sources.binding_descriptors['a']
    with pytest.raises(TypeError):
        sources.binding_descriptors['a'] = descriptor
    with pytest.raises(AttributeError):
        sources.binding_descriptors = {}
    with pytest.raises(AttributeError):
        sources.validation_deadline = 0
    with pytest.raises(FrozenInstanceError):
        descriptor.output_name = 'b'
    with pytest.raises(ValidationError):
        descriptor.artifact_ref.artifact_id = 'replacement'
    second = ValidationSources(contents, descriptors)
    assert second.binding_descriptors == sources.binding_descriptors
    assert second.binding_descriptors is not sources.binding_descriptors


def test_validation_sources_owns_its_descriptor_mapping():
    contents, descriptors = _source_values()
    sources = ValidationSources(contents, descriptors)
    descriptors.clear()
    assert set(sources.binding_descriptors) == set(contents)
