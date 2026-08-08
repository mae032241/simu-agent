from __future__ import annotations

import json
from pathlib import Path


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "scientific_cycles"
    / "fig4_clean"
)


def test_fig4_clean_namespace_starts_without_historical_scientific_data() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["fixture_name"] == "fig4_clean"
    assert manifest["status"] == "empty_pending_provenance_review"
    assert manifest["scientific_claim_allowed"] is False
    assert manifest["allow_historical_discovery"] is False
    assert manifest["allowed_files"] == []


def test_fig4_clean_namespace_contains_only_documentation_and_manifest() -> None:
    paths = {
        item.relative_to(FIXTURE).as_posix()
        for item in FIXTURE.rglob("*")
        if item.is_file()
    }
    assert paths == {"README.md", "manifest.json"}
    assert not any(item.is_symlink() for item in FIXTURE.rglob("*"))


def test_new_fig4_tests_do_not_scan_historical_resource_roots() -> None:
    test_root = Path(__file__).parent
    new_tests = (
        "test_control_equivalence.py",
        "test_layered_diagnosis.py",
        "test_layered_knowledge_update.py",
        "test_dynamic_readiness.py",
    )
    forbidden_roots = (
        "agent" + "/" + "runtime",
        "results" + "/" + "agent_pilots",
        "results" + "/" + "material_rebuild",
    )
    for name in new_tests:
        source = (test_root / name).read_text(encoding="utf-8")
        assert all(root not in source for root in forbidden_roots)
