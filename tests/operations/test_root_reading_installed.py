"""Scheduler resources survive packaging and platform installation."""
from scidiscovery.platforms.scheduler_prompt import load_scheduler_guides


def test_installed_scheduler_guides_match_source(installed_probe):
    installed_probe("core", "expected = " + repr(load_scheduler_guides()) + r'''
import tempfile
from pathlib import Path
from scidiscovery.platforms import initialize_platform
from scidiscovery.platforms.scheduler_prompt import load_scheduler_guides
assert load_scheduler_guides() == expected
root = Path(tempfile.mkdtemp())
project = root / "project"
initialize_platform("codex", project, control_socket=root / "control.sock")
for name, content in expected.items():
    assert (project / ".codex/scidiscovery-guides" / name).read_text() == content
''')
