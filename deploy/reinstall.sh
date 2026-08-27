#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly WORKSPACE="${SCID_WORKSPACE:-${SOURCE_ROOT}/workspace/default}"
readonly PYTHON="${SCID_PYTHON:-$(command -v python3 || true)}"
readonly SERVICE_USER="${SCID_SERVICE_USER:-$(id -un)}"
readonly SERVICE_GROUP="${SCID_SERVICE_GROUP:-$(id -gn)}"
readonly PLATFORM="${SCID_PLATFORM:-codex}"
readonly PLUGINS="${SCID_PLUGINS:-tcad_artifact,curve_score}"
readonly COMMAND_CONFIG="${SCID_TCAD_COMMAND_CONFIG:-}"
readonly WEB_FETCH_ALLOW_FAKE_IP="${SCID_WEB_FETCH_ALLOW_FAKE_IP:-0}"
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
    "Plugins: ${PLUGINS}" \
    "Web fetch Fake-IP: ${WEB_FETCH_ALLOW_FAKE_IP}" \
    "TCAD adapter: ${COMMAND_CONFIG:-local socket}"

declare -a INSTALL_ENV=(
    "SCID_WORKSPACE=${WORKSPACE}"
    "SCID_PYTHON=${PYTHON}"
    "SCID_SERVICE_USER=${SERVICE_USER}"
    "SCID_SERVICE_GROUP=${SERVICE_GROUP}"
    "SCID_PLATFORM=${PLATFORM}"
    "SCID_PLUGINS=${PLUGINS}"
    "SCID_WEB_FETCH_ALLOW_FAKE_IP=${WEB_FETCH_ALLOW_FAKE_IP}"
)
if [[ -n "$COMMAND_CONFIG" ]]; then
    INSTALL_ENV+=("SCID_TCAD_COMMAND_CONFIG=${COMMAND_CONFIG}")
fi
readonly -a INSTALL_ENV

if [[ "$MODE" == "--dry-run" ]]; then
    exec env "${INSTALL_ENV[@]}" "$SOURCE_ROOT/deploy/install.sh" --dry-run
fi
exec sudo env "${INSTALL_ENV[@]}" "$SOURCE_ROOT/deploy/install.sh" install
