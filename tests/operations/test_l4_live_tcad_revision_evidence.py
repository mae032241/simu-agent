from __future__ import annotations

from scripts.l4_live_tcad_revision_probe import _is_qualified_debug_report


SOURCE = "a" * 64


def _report(*, mode: str = "initialization", source: str = SOURCE):
    return {
        "schema_version": 1,
        "profile": f"tcad.project-{mode}.v1",
        "source_tree_sha256": source,
        "mode": mode,
        "terminal_state": "succeeded",
        "exit_code": 0,
        "diagnostic_layer": "complete",
        "qualified": True,
        "summary": "bounded fixture",
    }


def test_revision_evidence_accepts_exact_initialization_report() -> None:
    assert _is_qualified_debug_report(
        _report(), mode="initialization", source_tree_sha256=SOURCE
    )


def test_revision_evidence_rejects_preflight_as_initialization() -> None:
    value = _report(mode="preflight")
    assert not _is_qualified_debug_report(
        value, mode="initialization", source_tree_sha256=SOURCE
    )


def test_revision_evidence_rejects_stale_initialization_source() -> None:
    assert not _is_qualified_debug_report(
        _report(source="b" * 64),
        mode="initialization",
        source_tree_sha256=SOURCE,
    )
