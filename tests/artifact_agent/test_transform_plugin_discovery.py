from __future__ import annotations

from dataclasses import dataclass

from scidiscovery.artifact_agent import transforms


class _Adapter:
    def supports_transform_profile(self, profile: str) -> bool:
        return profile == "fixture.profile"

    def transform(self, *, profile: str, inputs):
        return ()


@dataclass(frozen=True)
class _EntryPoint:
    name: str

    def load(self):
        return _Adapter


class _EntryPoints(tuple):
    def select(self, *, group: str):
        assert group == "scidiscovery.transform_adapters"
        return self


def test_domain_transform_adapters_are_discovered_without_core_imports(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        transforms,
        "entry_points",
        lambda: _EntryPoints((_EntryPoint("zeta"), _EntryPoint("alpha"))),
    )
    adapters = transforms.load_transform_adapters()
    assert len(adapters) == 2
    assert all(item.supports_transform_profile("fixture.profile") for item in adapters)
