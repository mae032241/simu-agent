"""Default bulk-reading division preserves owner contracts and original access."""


def test_analysis_own_helper_does_not_replace_owner_judgment_or_numerical_checks():
    from scidiscovery.general_science_result_analysis import CORE_PROMPT
    core = CORE_PROMPT.replace('\n', ' ')
    assert "your own fresh helper" in core
    assert "independently of W's" in core
    assert "without routine rereading" in core
    assert "Read goal/constraints yourself" in core
    assert "Scientific judgments and required independent numerical checks remain yours" in core
