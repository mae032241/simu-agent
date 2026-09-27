"""Standalone Python 3.6 remote half of the local installation transaction."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def digest(path):
    if path.is_symlink():
        raise ValueError("deployment target must not be a symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def write(path, raw, mode=0o600):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def probe(runner, config):
    result = {}
    for name in ("tcad_capabilities", "tcad_execution_policy"):
        request = {"schema_version": 1, "operation": "rpc", "payload": {"request": {
            "jsonrpc": "2.0", "id": "deployment", "method": "tools/call",
            "params": {"name": name, "arguments": {}}}}}
        completed = subprocess.run([sys.executable, str(runner), "--config", str(config)],
            input=json.dumps(request).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if completed.returncode:
            raise RuntimeError("Remote runner/config validation failed: " + completed.stderr.decode(errors="replace")[-1000:])
        value = json.loads(completed.stdout)
        response = value.get("payload", {}).get("response", {})
        if value.get("ok") is not True or "error" in response:
            raise RuntimeError("Remote capability/policy discovery failed during deployment")
        result[name] = response["result"]["structuredContent"]
    if not result["tcad_capabilities"].get("capabilities"):
        raise RuntimeError("Remote runner has no capabilities")
    if not {"agent_execution_policy", "runner", "debug"}.issubset(result["tcad_execution_policy"]):
        raise RuntimeError("Remote policy discovery is incomplete")
    return {"capabilities": len(result["tcad_capabilities"]["capabilities"]), "policy_available": True}


def require_idle(config):
    value = json.loads(config.read_bytes())
    root = Path(value["result_root"])
    if root.exists() and any((p / "submitted_at").exists() and not (p / "done").exists()
                             for p in root.iterdir() if p.is_dir()):
        raise RuntimeError("Remote TCAD jobs may still be active; deployment stopped")


def deploy(request):
    runner, config = Path(request["runner"]), Path(request["config"])
    root = runner.parent.parent
    if (not runner.is_absolute() or runner != root / "bin/scidiscovery-tcad-ssh-runner"
            or config != root / "config/runner.json"):
        raise ValueError("Remote deployment requires canonical runner/config paths")
    token = request["transaction"]
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("Invalid deployment transaction identity")
    directory = root / ".deployments"
    if directory.is_symlink():
        raise ValueError("Remote deployment directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = directory / token
    phase = request["phase"]
    with (directory / "lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if phase == "prepare":
            stage.mkdir(mode=0o700)
            originals = {"runner": digest(runner), "config": digest(config)}
            if config.exists():
                require_idle(config)
            raw = (base64.b64decode(request["configuration"], validate=True)
                   if request.get("configuration") is not None else config.read_bytes())
            write(stage / "runner.candidate", base64.b64decode(request["source"], validate=True), 0o750)
            write(stage / "config.candidate", raw)
            # Probe both protocols before replacing either existing file.
            health = probe(stage / "runner.candidate", stage / "config.candidate")
            for key, path in (("runner", runner), ("config", config)):
                if originals[key] is not None:
                    shutil.copy2(str(path), str(stage / (key + ".before")))
            manifest = {"state": "prepared", "originals": originals,
                "candidates": {key: digest(stage / (key + ".candidate")) for key in originals},
                "modes": {"runner": runner.stat().st_mode & 0o777 if runner.exists() else 0o750,
                    "config": config.stat().st_mode & 0o777 if config.exists() else 0o640}}
            write(stage / "manifest.json", json.dumps(manifest).encode())
            return dict(health, state="prepared")
        if not (stage / "manifest.json").exists() and phase == "rollback":
            return {"state": "not_activated"}
        manifest = json.loads((stage / "manifest.json").read_bytes())
        if phase == "activate":
            if manifest["state"] != "prepared":
                raise RuntimeError("Remote deployment is not prepared")
            for key, path in (("runner", runner), ("config", config)):
                if digest(path) != manifest["originals"][key]:
                    raise RuntimeError("Remote deployment target changed after preparation")
            if config.exists():
                require_idle(config)
            manifest["state"] = "activating"
            write(stage / "manifest.json", json.dumps(manifest).encode())
            for key, path in (("config", config), ("runner", runner)):
                path.parent.mkdir(parents=True, exist_ok=True)
                candidate = stage / (key + ".candidate")
                if digest(candidate) != manifest["candidates"][key]:
                    raise RuntimeError("Remote staged candidate changed")
                write(path, candidate.read_bytes(), manifest["modes"][key])
            health = probe(runner, config)
            manifest["state"] = "activated"
        elif phase == "rollback":
            if manifest["state"] in ("activating", "activated", "complete"):
                for key, path in (("runner", runner), ("config", config)):
                    if digest(path) not in (manifest["originals"][key], manifest["candidates"][key]):
                        raise RuntimeError("Remote rollback conflicts with a later change")
                for key, path in (("config", config), ("runner", runner)):
                    if manifest["originals"][key] is None:
                        if path.exists(): path.unlink()
                    else:
                        write(path, (stage / (key + ".before")).read_bytes(), manifest["modes"][key])
            manifest["state"] = "rolled_back"
            health = {}
        elif phase == "finish":
            if manifest["state"] != "activated":
                raise RuntimeError("Remote deployment was not activated")
            for key, path in (("runner", runner), ("config", config)):
                if digest(path) != manifest["candidates"][key]:
                    raise RuntimeError("Remote deployed file differs from this installation candidate")
            health = probe(runner, config)
            manifest["state"] = "complete"
        else:
            raise ValueError("Unknown remote deployment phase")
        write(stage / "manifest.json", json.dumps(manifest).encode())
        return dict(health, state=manifest["state"])


if __name__ == "__main__":
    print(json.dumps(deploy(json.load(sys.stdin))))
