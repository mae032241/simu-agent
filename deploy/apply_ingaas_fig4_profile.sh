#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export SCID_WORKSPACE="${SCID_WORKSPACE:-${SOURCE_ROOT}/workspace/ingaas_inalas_photodetector}"
export SCID_PLUGINS="${SCID_PLUGINS:-tcad_artifact,curve_score,curve_figure_evidence,ingaas_fig4}"
export SCID_TCAD_COMMAND_CONFIG="${SCID_TCAD_COMMAND_CONFIG:-/etc/scidiscovery/command-adapter.json}"

exec "$SOURCE_ROOT/deploy/reinstall.sh" "$@"
