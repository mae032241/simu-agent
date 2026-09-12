from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from deploy.install_transaction import _directory_digest
from scidiscovery.operation_declaration import OPERATION_AGENT_PREAMBLE
from tcad_artifact import role_pack


REPOSITORY = Path(__file__).resolve().parents[2]
SKILL = REPOSITORY / "skills/sentaurus-tcad-code"


def test_role_prompts_use_only_packaged_role_resources():
    assert "Read only the exact assignment, declared inputs" in OPERATION_AGENT_PREAMBLE
    assert "Skill" not in OPERATION_AGENT_PREAMBLE
    for role in ("author", "reviewer"):
        prompt = role_pack.role_prompt(role)
        assert prompt == (role_pack.role_directory() / f"tcad_deck_{role}.md").read_text("utf-8")
        assert (SKILL / "SKILL.md").read_text("utf-8") not in prompt
        assert "sentaurus-tcad-code" in prompt
        assert "frozen Sentaurus" not in prompt


def test_sdist_wheel_compiles_without_repository_or_host_skill(tmp_path):
    package = tmp_path / "source/tcad_artifact"
    shutil.copytree(REPOSITORY / "plugins/tcad_artifact", package,
                    ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"))
    dist = tmp_path / "dist"
    dist.mkdir()
    subprocess.run([sys.executable, "-c",
                    "import setuptools.build_meta, sys; setuptools.build_meta.build_sdist(sys.argv[1])",
                    str(dist)], cwd=package, check=True, capture_output=True, timeout=60)
    archive = next(dist.glob("*.tar.gz"))
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                    "--wheel-dir", str(tmp_path / "wheels"), str(archive)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=60)
    installed = tmp_path / "installed"
    with zipfile.ZipFile(next((tmp_path / "wheels").glob("*.whl"))) as wheel:
        assert not any("sentaurus_knowledge" in name or "SKILL.md" in name for name in wheel.namelist())
        wheel.extractall(installed)
    subprocess.run([sys.executable, "-c", """
import sys
from pathlib import Path
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
Path.home = lambda: (_ for _ in ()).throw(AssertionError('host skill lookup'))
from tcad_artifact import plugin, role_pack
assert Path(plugin.__file__).resolve().is_relative_to(Path(sys.argv[1]))
catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, plugin.PLUGIN))
for operation in ('tcad.deck.author.initial.v1', 'tcad.deck.author.revise.v1', 'tcad.deck.review.v1'):
    assert catalog.operation(operation).digest
assert plugin.AUTHOR_PROMPT == role_pack.role_prompt('author')
assert plugin.REVIEWER_PROMPT == role_pack.role_prompt('reviewer')
""", str(installed)], cwd=tmp_path, check=True, capture_output=True, timeout=60,
                   env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (
                       installed, REPOSITORY / "src", REPOSITORY / "plugins/curve_score"))),
                        "PYTHONDONTWRITEBYTECODE": "1"})


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext is required")
def test_all_manual_topics_have_real_anchors_and_helpers_preserve_skill(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = {**os.environ, "TMPDIR": str(scratch), "XDG_CACHE_HOME": str(scratch),
           "PYTHONDONTWRITEBYTECODE": "1"}
    before = _directory_digest(SKILL)

    def helper(script, *args, expected=0):
        result = subprocess.run([sys.executable, str(SKILL / "scripts" / script), *args],
                                cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
        assert result.returncode == expected, result.stderr
        return json.loads(result.stdout) if expected == 0 else result.stderr

    anchors = {
        "preflight_modes": ("--FastMode", "--syntax"),
        "structure_1d": ("line command", "region command", "init command"),
        "mesh_refinement": ("refinebox", "grid remesh"),
        "custom_conservative_state": ("solution name=CX add !negative !damp solve", "pdbSetString Silicon CX Equation"),
        "equation_callback": ("EquationProc", "UserDiffPreProcess"),
        "diffuse_command": ("diffuse", "[isolve]", "[maxstep=<n>]"),
        "raw_plx_output": ("SetPlxList {Temperature Potential}", "WritePlx T_and_P.plx"),
        "development_modes": ("-i", "Prints the initial solution", "-P <commandfile>"),
    }
    topics = json.loads((SKILL / "references/manuals/topics.json").read_text("utf-8"))["topics"]
    assert {topic["topic"] for topic in topics} == set(anchors)
    for topic in topics:
        common = ("--release", topic["release"], "--solver-kind", topic["solver_kind"])
        found = helper("manual_search.py", *common, "--topic", topic["topic"])
        extract = helper("manual_extract.py", *common, "--start-page", str(found["start_page"]),
                         "--end-page", str(found["end_page"]))
        assert extract["manual_sha256"] == found["manual_sha256"]
        for anchor in anchors[topic["topic"]]:
            assert anchor in extract["text"], (topic["topic"], anchor)
    common = ("--release", "R-2020.09", "--solver-kind", "sprocess")
    assert helper("manual_search.py", *common, "--query", "solution name=CX")["hits"]
    assert "unavailable" in helper("manual_search.py", *common, "--topic", "unknown", expected=1)
    assert "unavailable" in helper("manual_search.py", "--release", "unknown", "--solver-kind",
                                   "sprocess", "--topic", "structure_1d", expected=1)
    assert "exceeds" in helper("manual_extract.py", *common, "--start-page", "9999",
                               "--end-page", "9999", expected=1)
    assert "positive ordered" in helper("manual_extract.py", *common, "--start-page", "0",
                                       "--end-page", "1", expected=1)
    assert _directory_digest(SKILL) == before
    assert list(scratch.rglob("*.layout.txt"))
    assert {path.name for path in tmp_path.iterdir()} == {"scratch"}
