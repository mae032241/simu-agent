#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly WORKSPACE="${SCID_WORKSPACE:-${SOURCE_ROOT}/workspace/default}"
readonly PYTHON="${SCID_PYTHON:-$(command -v python3 || true)}"
readonly SERVICE_USER="${SCID_SERVICE_USER:-$(id -un)}"
readonly SERVICE_GROUP="${SCID_SERVICE_GROUP:-$(id -gn)}"
readonly PLATFORM="${SCID_PLATFORM:-codex}"
readonly WORKER_BACKEND="${SCID_WORKER_BACKEND:-local}"
readonly PLUGINS="${SCID_PLUGINS:-}"
readonly COMMAND_CONFIG="${SCID_TCAD_COMMAND_CONFIG:-}"
readonly INSTALL_ROOT="${SCID_INSTALL_ROOT:-/opt/scidiscovery}"
readonly STATE_ROOT="${SCID_STATE_ROOT:-/var/lib/scidiscovery}"
readonly TCAD_STATE_ROOT_VALUE="${TCAD_STATE_ROOT:-/var/lib/scidiscovery-tcad}"
readonly CONFIG_ROOT="${SCID_CONFIG_ROOT:-/etc/scidiscovery}"
readonly BACKUP_ROOT="${SCID_BACKUP_ROOT:-/var/backups/scidiscovery}"
readonly APPROVAL_PORT="${SCID_APPROVAL_PORT:-8765}"
readonly CODEX_SKILL_ROOT="${SCID_CODEX_SKILL_ROOT:-}"
readonly MODE="${1:-install}"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf 'Usage: %s [--dry-run|install|reinstall|status]\n' "${0##*/}" >&2
}

[[ "$#" -le 1 ]] || { usage; exit 2; }
case "$MODE" in
    status)
        exec "$SOURCE_ROOT/deploy/install.sh" status
        ;;
    --dry-run|install|reinstall) ;;
    *) usage; exit 2 ;;
esac

[[ -d "$WORKSPACE" && ! -L "$WORKSPACE" ]] || \
    die "workspace not found: ${WORKSPACE}; set SCID_WORKSPACE"
[[ -n "$PYTHON" && -x "$PYTHON" ]] || die "base Python not found: ${PYTHON}"
if [[ -n "$COMMAND_CONFIG" ]]; then
    [[ -f "$COMMAND_CONFIG" && ! -L "$COMMAND_CONFIG" ]] || \
        die "TCAD command adapter config not found: ${COMMAND_CONFIG}"
fi
if [[ "$MODE" != "--dry-run" ]]; then
    [[ "$(id -u)" -ne 0 ]] || \
        die "run this wrapper as the service user; it invokes sudo itself"
    command -v sudo >/dev/null || die "sudo is unavailable"
fi

printf '%s\n' \
    "Source: ${SOURCE_ROOT}" \
    "Workspace: ${WORKSPACE}" \
    "Python: ${PYTHON}" \
    "Platform: ${PLATFORM}" \
    "Worker backend: ${WORKER_BACKEND}" \
    "Plugins: ${PLUGINS}" \
    "TCAD adapter: ${COMMAND_CONFIG:-local socket}"

declare -a INSTALL_ENV=(
    "SCID_WORKSPACE=${WORKSPACE}"
    "SCID_PYTHON=${PYTHON}"
    "SCID_SERVICE_USER=${SERVICE_USER}"
    "SCID_SERVICE_GROUP=${SERVICE_GROUP}"
    "SCID_PLATFORM=${PLATFORM}"
    "SCID_WORKER_BACKEND=${WORKER_BACKEND}"
    "SCID_PLUGINS=${PLUGINS}"
    "SCID_INSTALL_ROOT=${INSTALL_ROOT}"
    "SCID_STATE_ROOT=${STATE_ROOT}"
    "TCAD_STATE_ROOT=${TCAD_STATE_ROOT_VALUE}"
    "SCID_CONFIG_ROOT=${CONFIG_ROOT}"
    "SCID_BACKUP_ROOT=${BACKUP_ROOT}"
    "SCID_APPROVAL_PORT=${APPROVAL_PORT}"
)
if [[ -n "$COMMAND_CONFIG" ]]; then
    INSTALL_ENV+=("SCID_TCAD_COMMAND_CONFIG=${COMMAND_CONFIG}")
fi
if [[ -n "$CODEX_SKILL_ROOT" ]]; then
    INSTALL_ENV+=("SCID_CODEX_SKILL_ROOT=${CODEX_SKILL_ROOT}")
fi
readonly -a INSTALL_ENV

if [[ "$MODE" == "--dry-run" ]]; then
    exec env "${INSTALL_ENV[@]}" "$SOURCE_ROOT/deploy/install.sh" --dry-run
fi
exec sudo env "${INSTALL_ENV[@]}" "$SOURCE_ROOT/deploy/install.sh" install
