#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly MODE="${1:-install}"
[[ "$#" -le 1 ]] || { printf 'Usage: %s [--dry-run|install|reinstall|status]\n' "${0##*/}" >&2; exit 2; }
if [[ "${SCID_DEPLOY_MODE:-thin}" != thin ]]; then
    printf 'ERROR: legacy service deployment is retired; use the thin CLI.\n' >&2
    exit 2
fi
case "$MODE" in
    status|--dry-run) exec "$SOURCE_ROOT/deploy/install.sh" "$MODE" ;;
    install|reinstall) ;;
    *) printf 'Usage: %s [--dry-run|install|reinstall|status]\n' "${0##*/}" >&2; exit 2 ;;
esac
[[ "$(id -u)" -ne 0 ]] || {
    printf 'ERROR: run this wrapper as the operator; it invokes sudo itself.\n' >&2
    exit 1
}
command -v sudo >/dev/null || { printf 'ERROR: sudo is unavailable.\n' >&2; exit 1; }
readonly PYTHON="${SCID_PYTHON:-$(command -v python3 || true)}"
[[ "$PYTHON" = /* && -x "$PYTHON" ]] || {
    printf 'ERROR: SCID_PYTHON must resolve to an executable absolute path.\n' >&2
    exit 1
}
# Pass only the supported installer settings, never the whole login environment.
declare -a INSTALL_ENV=("SCID_PYTHON=$PYTHON")
for name in SCID_BIN_ROOT SCID_PLUGINS SCID_INSTALL_ROOT SCID_BACKUP_ROOT; do
    [[ ! -v "$name" ]] || INSTALL_ENV+=("$name=${!name}")
done
exec sudo env "${INSTALL_ENV[@]}" "$SOURCE_ROOT/deploy/install.sh" install
