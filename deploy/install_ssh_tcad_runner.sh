#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROJECT_ROOT="${SCID_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
readonly SSH_EXE="${SCID_SSH_EXE:-$(command -v ssh || true)}"
readonly IDENTITY="${SCID_SSH_IDENTITY:-}"
readonly DESTINATION_OVERRIDE="${SCID_SSH_DESTINATION:-}"
readonly DESTINATION_FALLBACK="${SCID_SSH_DESTINATION_FALLBACK:-}"
readonly VMRUN_EXE="${SCID_VMRUN_EXE:-}"
readonly VMX_PATH="${SCID_VMX_PATH:-}"
readonly HOST_KEY_ALIAS="${SCID_SSH_HOST_KEY_ALIAS:-}"
readonly KNOWN_HOSTS="${SCID_SSH_KNOWN_HOSTS:-${HOME}/.ssh/known_hosts}"
readonly REMOTE_ROOT="${SCID_REMOTE_RUNNER_ROOT:-/home/${USER}/scidiscovery-tcad}"
readonly RUNNER_SOURCE="${PROJECT_ROOT}/plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"
readonly CONFIG_SOURCE="${SCID_REMOTE_RUNNER_CONFIG:-${PROJECT_ROOT}/plugins/tcad_artifact/config/remote-runner.example.json}"

validate_local() {
    [[ -n "$SSH_EXE" && -x "$SSH_EXE" ]] || {
        printf 'Windows SSH client is unavailable: %s\n' "$SSH_EXE" >&2
        exit 66
    }
    [[ -f "$RUNNER_SOURCE" && -f "$CONFIG_SOURCE" ]] || {
        printf 'Runner sources are incomplete.\n' >&2
        exit 66
    }
    [[ "$REMOTE_ROOT" =~ ^/[A-Za-z0-9_./-]+$ ]] || {
        printf 'Remote runner root is not a safe absolute path: %s\n' "$REMOTE_ROOT" >&2
        exit 66
    }
    python3 -m py_compile "$RUNNER_SOURCE"
    python3 - "$CONFIG_SOURCE" <<'PY'
from pathlib import Path
import json
import sys

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for name in ("exchange_root", "state_root", "result_root"):
    assert Path(config[name]).is_absolute()
assert config["tools"]
assert len({tool["profile_id"] for tool in config["tools"]}) == len(config["tools"])
print("SSH TCAD runner local validation: pass")
PY
}

resolve_destination() {
    local address user
    if [[ -n "$DESTINATION_OVERRIDE" ]]; then
        printf '%s\n' "$DESTINATION_OVERRIDE"
        return
    fi
    if [[ -n "$DESTINATION_FALLBACK" && ( -z "$VMRUN_EXE" || -z "$VMX_PATH" || ! -x "$VMRUN_EXE" ) ]]; then
        printf '%s\n' "$DESTINATION_FALLBACK"
        return
    fi
    if [[ -z "$DESTINATION_FALLBACK" || -z "$VMRUN_EXE" || -z "$VMX_PATH" ]]; then
        printf 'Set SCID_SSH_DESTINATION, or set SCID_SSH_DESTINATION_FALLBACK, SCID_VMRUN_EXE, and SCID_VMX_PATH.\n' >&2
        return 66
    fi
    address="$("$VMRUN_EXE" getGuestIPAddress "$VMX_PATH" -wait)" || {
        printf 'VMware guest address discovery failed.\n' >&2
        return 66
    }
    address="${address//$'\r'/}"
    [[ "$address" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
        printf 'VMware guest address is invalid: %s\n' "$address" >&2
        return 66
    }
    user="${DESTINATION_FALLBACK%@*}"
    printf '%s@%s\n' "$user" "$address"
}

install_remote() {
    local stage remote_command destination
    local -a ssh_args
    destination="$(resolve_destination)"
    stage="$(mktemp -d)"
    trap "rm -rf -- $(printf '%q' "$stage")" EXIT
    install -d "$stage/bin" "$stage/config"
    install -m 0750 "$RUNNER_SOURCE" "$stage/bin/scidiscovery-tcad-ssh-runner"
    python3 - "$CONFIG_SOURCE" "$stage/config/runner.json" "$REMOTE_ROOT" <<'PY'
from pathlib import Path
import json
import sys

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = sys.argv[3].rstrip("/")
config.update({
    "exchange_root": root + "/exchange",
    "state_root": root + "/state",
    "result_root": root + "/state/runs",
})
Path(sys.argv[2]).write_text(
    json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
    chmod 0640 "$stage/config/runner.json"
    remote_command="umask 027; mkdir -p '$REMOTE_ROOT/bin' '$REMOTE_ROOT/config' '$REMOTE_ROOT/exchange' '$REMOTE_ROOT/state/runs'; tar --no-same-owner -xf - -C '$REMOTE_ROOT'; chmod 0750 '$REMOTE_ROOT/bin/scidiscovery-tcad-ssh-runner'; chmod 0640 '$REMOTE_ROOT/config/runner.json'; python3 -m py_compile '$REMOTE_ROOT/bin/scidiscovery-tcad-ssh-runner'; printf 'SSH TCAD user runner installation: pass\\n'"
    ssh_args=(
        -o BatchMode=yes
        -o ConnectTimeout=5
        -o StrictHostKeyChecking=yes
        -o "UserKnownHostsFile=$KNOWN_HOSTS"
    )
    [[ -z "$IDENTITY" ]] || ssh_args+=( -i "$IDENTITY" )
    [[ -z "$HOST_KEY_ALIAS" ]] || ssh_args+=( -o "HostKeyAlias=$HOST_KEY_ALIAS" )
    tar --format=ustar --mtime=@0 --owner=0 --group=0 --numeric-owner \
        -C "$stage" -cf - bin config | "$SSH_EXE" "${ssh_args[@]}" \
        "$destination" "bash -lc \"$remote_command\""
    rm -rf -- "$stage"
    trap - EXIT
}

validate_local
case "${1:---dry-run}" in
    --dry-run)
        printf '%s\n' \
            'No VM file, service, SSH key, or local service was changed.' \
            "Install target: ${DESTINATION_OVERRIDE:-${DESTINATION_FALLBACK:-<set SCID_SSH_DESTINATION>}}:${REMOTE_ROOT}"
        ;;
    install)
        install_remote
        ;;
    *)
        printf 'Usage: %s [--dry-run|install]\n' "$0" >&2
        exit 64
        ;;
esac
