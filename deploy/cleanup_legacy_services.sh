#!/usr/bin/env bash
set -Eeuo pipefail

readonly ACTION="${1:---dry-run}"
readonly SERVICE_USER="${SCID_SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
readonly BACKUPS_TO_KEEP="${SCID_BACKUPS_TO_KEEP:-3}"
readonly CURRENT_INSTALL_ROOT="/opt/scidiscovery"
readonly CURRENT_CONFIG_ROOT="/etc/scidiscovery"
readonly CURRENT_STATE_ROOT="/var/lib/scidiscovery"
readonly CURRENT_TCAD_STATE_ROOT="/var/lib/scidiscovery-tcad"
readonly CURRENT_BACKUP_ROOT="/var/backups/scidiscovery"

readonly -a CURRENT_UNITS=(
    scidiscovery-control.service
    scidiscovery-worker.service
    scidiscovery-approval-ui.service
)

readonly -a RETIRED_UNITS=(
    artifact-agent-control.service
    artifact-agent-worker.service
    artifact-agent-approval-ui.service
    tcad-artifact-execution.service
    tcad-artifact-runner.service
)

readonly -a LEGACY_ROOTS=(
    /var/lib/artifact-agent-vnext
    /etc/artifact-agent-vnext
    /opt/artifact-agent-vnext
    /var/backups/artifact-agent-vnext
    /var/lib/tcad-control
    /etc/tcad-control
    /opt/tcad-control
    /var/backups/tcad-control
)

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: deploy/cleanup_legacy_services.sh [--dry-run|clean]

--dry-run  Audit exact legacy paths without deleting anything (default).
clean      Delete retired service roots and user-local duplicate packages,
           then retain only the newest SCID_BACKUPS_TO_KEEP SciDiscovery
           installation backups (default: 3). Requires sudo.
EOF
}

validate_action() {
    case "$ACTION" in
        --dry-run) ;;
        clean) [[ "$(id -u)" -eq 0 ]] || die "clean requires sudo" ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "unknown action: ${ACTION}" ;;
    esac
    [[ "$BACKUPS_TO_KEEP" =~ ^[1-9][0-9]*$ ]] || \
        die "SCID_BACKUPS_TO_KEEP must be a positive integer"
}

validate_current_installation() {
    local unit rendered legacy
    [[ -d "$CURRENT_INSTALL_ROOT/site/scidiscovery" ]] || \
        die "current package installation is unavailable: ${CURRENT_INSTALL_ROOT}"
    [[ -d "$CURRENT_CONFIG_ROOT" && -d "$CURRENT_STATE_ROOT" ]] || \
        die "current SciDiscovery configuration or state is unavailable"
    for unit in "${CURRENT_UNITS[@]}"; do
        systemctl is-active --quiet "$unit" || die "current service is not active: ${unit}"
    done
    rendered="$({
        for unit in "${CURRENT_UNITS[@]}" tcad-control.service; do
            systemctl cat "$unit" --no-pager 2>/dev/null || true
        done
        find "$CURRENT_CONFIG_ROOT" -maxdepth 1 -type f -name '*.json' -print0 2>/dev/null \
            | xargs -0 -r cat
    })"
    for legacy in "${LEGACY_ROOTS[@]}"; do
        [[ "$rendered" != *"$legacy"* ]] || \
            die "current configuration still references legacy path: ${legacy}"
    done
    for unit in "${RETIRED_UNITS[@]}"; do
        if systemctl is-active --quiet "$unit" 2>/dev/null; then
            die "retired service is still active: ${unit}"
        fi
    done
    return 0
}

human_size() {
    local path="$1"
    local size
    size="$(du -sh "$path" 2>/dev/null | awk 'NR == 1 {print $1}')" || true
    printf '%s' "${size:-unreadable}"
}

list_legacy_roots() {
    local path
    printf '%s\n' 'Retired service roots:'
    for path in "${LEGACY_ROOTS[@]}"; do
        if [[ -e "$path" ]]; then
            [[ ! -L "$path" ]] || die "refusing legacy symlink: ${path}"
            printf '  remove  %-8s %s\n' "$(human_size "$path")" "$path"
        else
            printf '  absent           %s\n' "$path"
        fi
    done
}

user_home() {
    getent passwd "$SERVICE_USER" | awk -F: '{print $6}'
}

list_user_duplicates() {
    local home path
    home="$(user_home)"
    [[ -n "$home" && -d "$home" ]] || die "service-user home not found: ${SERVICE_USER}"
    printf 'User-local duplicate packages for %s:\n' "$SERVICE_USER"
    while IFS= read -r -d '' path; do
        printf '  remove  %-8s %s\n' "$(human_size "$path")" "$path"
    done < <(
        find "$home/.local/lib" -maxdepth 5 \
            \( -type d -o -type l \) \
            \( -name scidiscovery -o -name 'scidiscovery-*.dist-info' \
               -o -name tcad_artifact -o -name 'tcad_artifact-*.dist-info' \
               -o -name 'tcad_artifact_runner-*.dist-info' \) \
            -print0 2>/dev/null
    )
}

list_backup_policy() {
    local -a backups
    mapfile -t backups < <(
        find "$CURRENT_BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
            -printf '%f\n' 2>/dev/null | sort -r
    )
    printf 'Current-install backups: total=%d keep_newest=%d remove=%d\n' \
        "${#backups[@]}" "$BACKUPS_TO_KEEP" \
        "$(( ${#backups[@]} > BACKUPS_TO_KEEP ? ${#backups[@]} - BACKUPS_TO_KEEP : 0 ))"
}

delete_tree() {
    local path="$1"
    [[ -e "$path" ]] || return 0
    [[ ! -L "$path" ]] || die "refusing to recursively delete symlink: ${path}"
    rm -rf --one-file-system -- "$path"
}

remove_legacy_roots() {
    local path
    for path in "${LEGACY_ROOTS[@]}"; do
        delete_tree "$path"
    done
}

remove_user_duplicates() {
    local home path
    home="$(user_home)"
    while IFS= read -r -d '' path; do
        delete_tree "$path"
    done < <(
        find "$home/.local/lib" -maxdepth 5 \
            \( -type d -o -type l \) \
            \( -name scidiscovery -o -name 'scidiscovery-*.dist-info' \
               -o -name tcad_artifact -o -name 'tcad_artifact-*.dist-info' \
               -o -name 'tcad_artifact_runner-*.dist-info' \) \
            -print0 2>/dev/null
    )
    for path in \
        artifact-agent artifact-agent-legacy-readonly artifact-agent-mcp \
        scid scid-legacy-readonly \
        tcad-artifact-runner-daemon tcad-artifact-execution-daemon \
        tcad-artifact-execution-mcp tcad-artifact-init
    do
        path="$home/.local/bin/$path"
        [[ ! -e "$path" && ! -L "$path" ]] || rm -f -- "$path"
    done
}

prune_current_backups() {
    local -a backups
    local index
    mapfile -t backups < <(
        find "$CURRENT_BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
            -printf '%f\n' 2>/dev/null | sort -r
    )
    for ((index=BACKUPS_TO_KEEP; index<${#backups[@]}; index++)); do
        delete_tree "$CURRENT_BACKUP_ROOT/${backups[$index]}"
    done
}

main() {
    validate_action
    validate_current_installation
    printf '%s\n' \
        "Current install preserved: ${CURRENT_INSTALL_ROOT}" \
        "Current config preserved: ${CURRENT_CONFIG_ROOT}" \
        "Current state preserved: ${CURRENT_STATE_ROOT}" \
        "Current TCAD state preserved: ${CURRENT_TCAD_STATE_ROOT}"
    list_legacy_roots
    list_user_duplicates
    list_backup_policy
    if [[ "$ACTION" == --dry-run ]]; then
        printf '%s\n' 'Dry run complete. Nothing was deleted.'
        exit 0
    fi
    remove_legacy_roots
    remove_user_duplicates
    prune_current_backups
    validate_current_installation
    printf '%s\n' 'Legacy service cleanup: pass'
}

main
