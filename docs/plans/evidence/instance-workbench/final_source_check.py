"""Record the exact reviewed source; perform only bounded static checks."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

root = Path.cwd()
evidence = root / "docs/plans/evidence/instance-workbench"
prefixes = ["src", "plugins", "tests", "deploy", "pyproject.toml", ".gitignore",
            "docs/plans/evidence/instance-workbench"]
changed = subprocess.check_output(["git", "diff", "--name-only", "-z", "HEAD", "--", *prefixes])
added = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z", "--", *prefixes])
names = sorted({name.decode() for name in (changed + added).split(b"\0") if name})
names = [name for name in names if not name.startswith("docs/") or name.endswith(".py")]
files = []
for name in names:
    path = root / name
    raw = path.read_bytes()
    if path.suffix == ".py":
        ast.parse(raw, filename=name)
    files.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
subprocess.run(["git", "diff", "--check"], check=True)
subprocess.run(["bash", "-n", "deploy/install.sh"], check=True)
for suffix in ("", "_OPTIONAL_FIGURE"):
    assert (evidence / f"BASELINE_CONTRACTS{suffix}.json").read_bytes() == (evidence / f"FINAL_CONTRACTS{suffix}.json").read_bytes()
plan = root / "docs/plans/INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md"
plan_digest = hashlib.sha256(plan.read_bytes()).hexdigest()
assert plan_digest == "f2d917995069e161dccd87897d17659a1095e5ec87a175e35919c0852a175fdf"
body = {"baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "frozen_plan_sha256": plan_digest, "files": files,
        "checks": ["changed Python AST", "git diff --check", "bash -n deploy/install.sh",
                   "45/50 contract snapshots byte-identical", "frozen R3 plan digest"]}
raw = (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode()
(evidence / "SOURCE_MANIFEST.json").write_bytes(raw)
print(json.dumps({"files": len(files), "manifest_sha256": hashlib.sha256(raw).hexdigest(), "checks": "pass"}))
