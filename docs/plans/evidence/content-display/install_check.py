"""Serial isolated wheel validation. Invoke only through run_bounded.py."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

repository = Path.cwd()
evidence = Path(__file__).resolve().parent
label = sys.argv[1] if len(sys.argv) > 1 else "installed"
with tempfile.TemporaryDirectory(prefix="scid-workbench-install-") as temporary:
    root = Path(temporary)
    source, wheels = root / "source", root / "wheels"
    wheels.mkdir()
    with (evidence / f"{label}-build.log").open("w") as log:
        def run(arguments, timeout=150):
            subprocess.run([str(value) for value in arguments], cwd=root, stdout=log,
                stderr=subprocess.STDOUT, check=True, timeout=timeout)
        run([sys.executable, repository / "scripts/build_git_release.py", "--source", repository, "--output", source])
        for package in (source, source / "plugins/tcad_artifact", source / "plugins/curve_score", source / "plugins/curve_figure_evidence"):
            run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", wheels, package])
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
        sys.path.insert(0, str(repository))
        from tests.operations.conftest import _supply_runtime_dependencies, _copy_runtime_distribution
        _supply_runtime_dependencies(environment)
        site = environment / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
        for name in ("pytest", "pluggy", "iniconfig", "packaging", "pygments"):
            _copy_runtime_distribution(name, site)
        python = environment / "bin/python"
        run([python, "-m", "pip", "install", "--no-index", "--no-deps", *sorted(wheels.glob("*.whl"))])
        for name, probe, arguments in (
            ("workbench", evidence / "install_probe.py", [evidence / "CONTRACTS_BEFORE.json"]),
            ("continuation", evidence.parent / "user-text-context/install_probe.py", [repository]),
        ):
            result = subprocess.run([str(python), "-I", str(probe), *map(str, arguments)],
                cwd=root, capture_output=True, text=True, timeout=150)
            (evidence / f"{label}-{name}.stdout").write_text(result.stdout)
            (evidence / f"{label}-{name}.stderr").write_text(result.stderr)
            print(result.stdout, flush=True)
            if result.returncode:
                print(result.stderr, flush=True)
            result.check_returncode()
print(json.dumps({"isolated_wheels": 4, "system_site_packages": False, "temporary_install_removed": True}))
