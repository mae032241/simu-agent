#!/usr/bin/env bash
set -Eeuo pipefail
umask 0027

readonly SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly WORKSPACE_ROOT="${SCID_WORKSPACE_ROOT:-${SOURCE_ROOT}/workspace}"

usage() {
    printf 'Usage: %s <project-name>\n' "${0##*/}" >&2
}

[[ "$#" -eq 1 ]] || { usage; exit 2; }
readonly PROJECT_NAME="$1"
[[ "$PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || {
    printf 'ERROR: project name must match [a-z0-9][a-z0-9_-]{0,63}\n' >&2
    exit 2
}

readonly PROJECT_ROOT="${WORKSPACE_ROOT}/${PROJECT_NAME}"
install -d -m 0750 \
    "$WORKSPACE_ROOT" \
    "$PROJECT_ROOT"
install -d -m 0750 \
    "$PROJECT_ROOT/config" \
    "$PROJECT_ROOT/docs" \
    "$PROJECT_ROOT/inputs" \
    "$PROJECT_ROOT/inputs/papers" \
    "$PROJECT_ROOT/inputs/tables" \
    "$PROJECT_ROOT/inputs/user" \
    "$PROJECT_ROOT/logs" \
    "$PROJECT_ROOT/research" \
    "$PROJECT_ROOT/results" \
    "$PROJECT_ROOT/runtime" \
    "$PROJECT_ROOT/scripts" \
    "$PROJECT_ROOT/sentaurus" \
    "$PROJECT_ROOT/skills" \
    "$PROJECT_ROOT/targets"

printf 'Workspace initialized: %s\n' "$PROJECT_ROOT"
printf 'Use for deployment: SCID_WORKSPACE=%q deploy/reinstall.sh reinstall\n' "$PROJECT_ROOT"
