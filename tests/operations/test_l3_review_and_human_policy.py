from __future__ import annotations


from blind_csv_plugin.plugin import REVIEWER


def test_reviewer_declares_the_native_workspace_capability_needed_for_review():
    assert REVIEWER.executor.native_tools.shell == "inherited_prototype"
