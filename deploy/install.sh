#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly WORKSPACE="${SCID_WORKSPACE:-$SCRIPT_ROOT}"
readonly PYTHON="${SCID_PYTHON:-$(command -v python3 || true)}"
readonly SERVICE_USER="${SCID_SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
readonly SERVICE_GROUP="${SCID_SERVICE_GROUP:-$(id -gn "$SERVICE_USER")}"
readonly PLATFORM="${SCID_PLATFORM:-codex}"
readonly ENABLE_INGAAS_FIG4="${SCID_ENABLE_INGAAS_FIG4:-0}"
readonly INSTALL_ROOT="${SCID_INSTALL_ROOT:-/opt/scidiscovery}"
readonly SITE_ROOT="${INSTALL_ROOT}/site"
readonly SCID_STATE="${SCID_STATE_ROOT:-/var/lib/scidiscovery}"
readonly TCAD_STATE="${TCAD_STATE_ROOT:-/var/lib/scidiscovery-tcad}"
readonly CONFIG_ROOT="${SCID_CONFIG_ROOT:-/etc/scidiscovery}"
readonly BACKUP_ROOT="${SCID_BACKUP_ROOT:-/var/backups/scidiscovery}"
readonly CONTROL_SOCKET="/run/scidiscovery/control.sock"
readonly WORKER_SOCKET="/run/scidiscovery-worker/worker.sock"
readonly TCAD_SOCKET="/run/scidiscovery-tcad/control.sock"
readonly TCAD_COMMAND_CONFIG="${SCID_TCAD_COMMAND_CONFIG:-}"
readonly APPROVAL_PORT="${SCID_APPROVAL_PORT:-8765}"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_sources() {
    local path
    for path in \
        pyproject.toml \
        skills/sentaurus-tcad-code/SKILL.md \
        skills/sentaurus-tcad-code/scripts/validate_deck_project.py \
        plugins/tcad_artifact/pyproject.toml \
        deploy/systemd/scidiscovery-control.service.in \
        deploy/systemd/scidiscovery-worker.service.in \
        deploy/systemd/scidiscovery-approval-ui.service.in \
        plugins/tcad_artifact/deploy/systemd/tcad-control.service.in
    do
        [[ -f "${WORKSPACE}/${path}" ]] || die "missing source: ${path}"
    done
    [[ -n "$PYTHON" && -x "$PYTHON" ]] || die "base Python is unavailable: ${PYTHON}"
    [[ "$PLATFORM" =~ ^(codex|claude|both)$ ]] || \
        die "SCID_PLATFORM must be codex, claude, or both"
    [[ "$ENABLE_INGAAS_FIG4" =~ ^(0|1)$ ]] || \
        die "SCID_ENABLE_INGAAS_FIG4 must be 0 or 1"
    if [[ "$ENABLE_INGAAS_FIG4" == 1 ]]; then
        [[ -f "$WORKSPACE/plugins/ingaas_fig4/pyproject.toml" ]] || \
            die "optional InGaAs Fig.4 plugin source is missing"
    fi
    command -v pdftotext >/dev/null || die "pdftotext is required for task PDF inputs"
    command -v bwrap >/dev/null || die "bubblewrap is required for isolated worker analysis"
    if [[ -n "$TCAD_COMMAND_CONFIG" ]]; then
        [[ "$TCAD_COMMAND_CONFIG" = /* && -f "$TCAD_COMMAND_CONFIG" && ! -L "$TCAD_COMMAND_CONFIG" ]] || \
            die "SCID_TCAD_COMMAND_CONFIG must name an absolute regular file"
    fi
}

validate_source() {
    local pythonpath="src:plugins/tcad_artifact"
    [[ ! -f "$WORKSPACE/plugins/ingaas_fig4/pyproject.toml" ]] || \
        pythonpath+=":plugins/ingaas_fig4"
    (
        cd "$WORKSPACE"
        if [[ -f research/current.yaml ]]; then
            PYTHONNOUSERSITE=1 PYTHONPATH="$pythonpath" \
                "$PYTHON" -m scidiscovery.research_state validate
        fi
        PYTHONNOUSERSITE=1 PYTHONPATH="$pythonpath" "$PYTHON" - <<'PY'
import scidiscovery.artifact_agent
import tcad_artifact
try:
    import ingaas_fig4
except ImportError:
    pass
print('source imports: pass')
PY
    )
}

require_root() {
    [[ "$(id -u)" -eq 0 ]] || die "install and uninstall require sudo"
    command -v systemctl >/dev/null || die "systemctl is unavailable"
}

render_unit() {
    local template="$1" output="$2"
    shift 2
    "$PYTHON" - "$template" "$output" "$@" <<'PY'
from pathlib import Path
import os
import re
import sys

text = Path(sys.argv[1]).read_text(encoding='utf-8')
for assignment in sys.argv[3:]:
    key, separator, value = assignment.partition('=')
    if not separator:
        raise SystemExit(f'invalid template assignment: {assignment}')
    text = text.replace(f'@{key}@', value)
remaining = sorted(set(re.findall(r'@[A-Z0-9_]+@', text)))
if remaining:
    raise SystemExit('unresolved placeholders: ' + ', '.join(remaining))
target = Path(sys.argv[2])
target.parent.mkdir(parents=True, exist_ok=True)
temporary = target.with_name('.' + target.name + '.tmp')
temporary.write_text(text, encoding='utf-8')
os.replace(temporary, target)
PY
}

render_units() {
    local output="$1" adapter_args
    if [[ -n "$TCAD_COMMAND_CONFIG" ]]; then
        adapter_args="--tcad-command-config ${TCAD_COMMAND_CONFIG}"
    else
        adapter_args="--tcad-socket ${TCAD_SOCKET}"
    fi
    local common=(
        "PROJECT_ROOT=${WORKSPACE}"
        "STATE_ROOT=${SCID_STATE}"
        "CONTROL_GROUP=${SERVICE_GROUP}"
        "PYTHON_ACCESS_GROUP=${SERVICE_GROUP}"
        "PYTHONPATH=${SITE_ROOT}"
        "PYTHON=${PYTHON}"
        "TASK_SECRET=${CONFIG_ROOT}/task-token.key"
        "APPROVAL_SECRET=${CONFIG_ROOT}/approval-receipt.key"
    )
    render_unit \
        "${WORKSPACE}/deploy/systemd/scidiscovery-control.service.in" \
        "${output}/scidiscovery-control.service" \
        "${common[@]}" \
        "CONTROL_USER=${SERVICE_USER}" \
        "CONTROL_SOCKET=${CONTROL_SOCKET}" \
        "TCAD_ADAPTER_ARGS=${adapter_args}" \
        "APPROVAL_PORT=${APPROVAL_PORT}" \
        "RUNTIME_ROOT=/run/scidiscovery"
    render_unit \
        "${WORKSPACE}/deploy/systemd/scidiscovery-worker.service.in" \
        "${output}/scidiscovery-worker.service" \
        "${common[@]}" \
        "CONTROL_USER=${SERVICE_USER}" \
        "WORKER_SOCKET=${WORKER_SOCKET}" \
        "RUNTIME_ROOT=/run/scidiscovery-worker"
    render_unit \
        "${WORKSPACE}/deploy/systemd/scidiscovery-approval-ui.service.in" \
        "${output}/scidiscovery-approval-ui.service" \
        "${common[@]}" \
        "APPROVAL_USER=${SERVICE_USER}" \
        "APPROVAL_PORT=${APPROVAL_PORT}" \
        "LOCAL_IDENTITY=local_user" \
        "LOCAL_DISPLAY_NAME=Local_user"
    render_unit \
        "${WORKSPACE}/plugins/tcad_artifact/deploy/systemd/tcad-control.service.in" \
        "${output}/tcad-control.service" \
        "PROJECT_ROOT=${WORKSPACE}" \
        "PYTHONPATH=${SITE_ROOT}" \
        "EXECUTION_USER=${SERVICE_USER}" \
        "CONTROL_GROUP=${SERVICE_GROUP}" \
        "EXECUTION_PYTHON=${PYTHON}" \
        "EXECUTION_STATE_ROOT=${TCAD_STATE}" \
        "EXECUTION_POLICY=${CONFIG_ROOT}/tcad-policy.json" \
        "EXECUTION_SOCKET=${TCAD_SOCKET}" \
        "EXECUTION_RUNTIME_ROOT=/run/scidiscovery-tcad"
}

preview() {
    local stage
    stage="$(mktemp -d)"
    render_units "$stage"
    (
        cd "$WORKSPACE"
        PYTHONPATH="src:plugins/tcad_artifact" "$PYTHON" - <<PY
from pathlib import Path
from scidiscovery.platforms import initialize_platform

initialize_platform(
    '$PLATFORM', Path('$WORKSPACE'), python_executable=Path('$PYTHON'),
    control_socket=Path('$CONTROL_SOCKET'),
    worker_socket=Path('$WORKER_SOCKET'), codex_config_root=Path('$stage/codex'),
    dry_run=True,
)
print('deployment preview: pass')
PY
    )
    rm -rf "$stage"
    printf '%s\n' 'No package, state, service, or platform configuration was changed.'
}

ensure_secret() {
    local path="$1"
    if [[ ! -e "$path" ]]; then
        umask 077
        "$PYTHON" - "$path" <<'PY'
from pathlib import Path
import os
import sys
Path(sys.argv[1]).write_bytes(os.urandom(32))
PY
    fi
    [[ -f "$path" && ! -L "$path" ]] || die "unsafe secret path: ${path}"
    [[ "$(stat -c %s "$path")" -eq 32 ]] || die "secret must be 32 bytes: ${path}"
    chown "$SERVICE_USER:$SERVICE_GROUP" "$path"
    chmod 0600 "$path"
}

install_packages() {
    local stage previous source_stage source_root plugin_root task_plugin_root
    local has_task_plugin=0
    local -a package_roots
    stage="${INSTALL_ROOT}/.site.new.$$"
    previous="${INSTALL_ROOT}/.site.previous.$$"
    source_stage="$(mktemp -d)"
    source_root="${source_stage}/scidiscovery"
    plugin_root="${source_stage}/tcad-artifact"
    task_plugin_root="${source_stage}/ingaas-fig4"
    install -d -o root -g root -m 0755 "$INSTALL_ROOT"
    rm -rf "$stage" "$previous"
    install -d "$source_root/src" "$plugin_root"
    cp -a "$WORKSPACE/pyproject.toml" "$WORKSPACE/README.md" \
        "$WORKSPACE/roles" "$WORKSPACE/deploy" "$source_root/"
    [[ ! -f "$WORKSPACE/README.zh-CN.md" ]] || \
        cp -a "$WORKSPACE/README.zh-CN.md" "$source_root/"
    cp -a "$WORKSPACE/src/scidiscovery" "$source_root/src/"
    cp -a "$WORKSPACE/plugins/tcad_artifact/pyproject.toml" \
        "$WORKSPACE/plugins/tcad_artifact/README.md" \
        "$WORKSPACE/plugins/tcad_artifact/config" \
        "$WORKSPACE/plugins/tcad_artifact/deploy" \
        "$WORKSPACE/plugins/tcad_artifact/tcad_artifact" "$plugin_root/"
    package_roots=("$source_root" "$plugin_root")
    if [[ "$ENABLE_INGAAS_FIG4" == 1 ]]; then
        install -d "$task_plugin_root"
        cp -a "$WORKSPACE/plugins/ingaas_fig4/pyproject.toml" \
            "$WORKSPACE/plugins/ingaas_fig4/ingaas_fig4" "$task_plugin_root/"
        package_roots+=("$task_plugin_root")
        has_task_plugin=1
    fi
    find "$source_stage" -type d \( -name __pycache__ -o -name '*.egg-info' \) \
        -prune -exec rm -rf {} +
    "$PYTHON" -m pip install --disable-pip-version-check --no-input \
        --root-user-action=ignore --upgrade \
        --target "$stage" "${package_roots[@]}" \
        >/dev/null
    rm -rf "$source_stage"
    SCID_HAS_INGAAS="$has_task_plugin" PYTHONNOUSERSITE=1 PYTHONPATH="$stage" "$PYTHON" - <<'PY'
import os
from scidiscovery.platforms.roles import load_roles
from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
from scidiscovery.artifact_agent.interfaces.mcp_worker import WORKER_TOOLS
from scidiscovery.artifact_agent.transforms import load_transform_adapters
from tcad_artifact.execution_control import EXECUTION_TOOLS
assert len(ROOT_TOOLS) == 31
assert len(WORKER_TOOLS) == 16
assert len(EXECUTION_TOOLS) == 4
assert len(load_roles()) == 9
adapters = load_transform_adapters()
expected_adapters = 2 if os.environ['SCID_HAS_INGAAS'] == '1' else 1
assert len(adapters) == expected_adapters
assert sum(item.supports_transform_profile("tcad.reviewed-deck-package.v1") for item in adapters) == 1
assert sum(item.supports_transform_profile("ingaas.fig4-baseline-recovery.v2") for item in adapters) == (expected_adapters - 1)
print('installed package probe: pass')
PY
    [[ ! -d "$SITE_ROOT" ]] || mv "$SITE_ROOT" "$previous"
    mv "$stage" "$SITE_ROOT"
    rm -rf "$previous"
    chmod -R a-w "$SITE_ROOT"
    find "$SITE_ROOT" -type d -exec chmod a+rx {} +
    cat > /usr/local/bin/scid <<EOF
#!/usr/bin/env bash
exec env PYTHONNOUSERSITE=1 PYTHONPATH=${SITE_ROOT} ${PYTHON} -m scidiscovery.artifact_agent.interfaces.cli "\$@"
EOF
    chown root:root /usr/local/bin/scid
    chmod 0755 /usr/local/bin/scid
    cat > /usr/local/bin/scidiscovery-tcad-transport <<EOF
#!/usr/bin/env bash
exec env PYTHONNOUSERSITE=1 PYTHONPATH=${SITE_ROOT} SCIDISCOVERY_TCAD_RESULT_ROOT=${SCID_STATE}/executor-results ${PYTHON} -m tcad_artifact.ssh_transport "\$@"
EOF
    chown root:root /usr/local/bin/scidiscovery-tcad-transport
    chmod 0755 /usr/local/bin/scidiscovery-tcad-transport
}

write_policy() {
    if [[ -e "${CONFIG_ROOT}/tcad-policy.json" ]]; then
        [[ -f "${CONFIG_ROOT}/tcad-policy.json" && ! -L "${CONFIG_ROOT}/tcad-policy.json" ]] || \
            die "unsafe existing TCAD policy"
        PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" - "${CONFIG_ROOT}/tcad-policy.json" <<'PY'
from pathlib import Path
import sys
from tcad_artifact.execution_control import TCADExecutionPolicy
TCADExecutionPolicy.model_validate_json(Path(sys.argv[1]).read_bytes(), strict=True)
print('existing TCAD policy preserved: pass')
PY
        chown root:"$SERVICE_GROUP" "${CONFIG_ROOT}/tcad-policy.json"
        chmod 0640 "${CONFIG_ROOT}/tcad-policy.json"
        return
    fi
    "$PYTHON" - "${CONFIG_ROOT}/tcad-policy.json" "$WORKSPACE" "$SCID_STATE" <<'PY'
from pathlib import Path
import json
import os
import sys

payload = {
    'allowed_input_roots': [
        str(Path(sys.argv[3]).joinpath('execution-exchange').absolute()),
    ],
    'max_concurrent_runs': 1,
    'tools': [{
        'arguments': [],
        'environment': {},
        'executable': str(Path('/bin/true').resolve()),
        'profile_id': 'deployment_smoke',
    }],
}
raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
path = Path(sys.argv[1])
temporary = path.with_name('.' + path.name + '.tmp')
temporary.write_bytes(raw)
os.replace(temporary, path)
PY
    chown root:"$SERVICE_GROUP" "${CONFIG_ROOT}/tcad-policy.json"
    chmod 0640 "${CONFIG_ROOT}/tcad-policy.json"
}

retire_old_deployment() {
    local unit
    for unit in \
        tcad-artifact-execution.service \
        tcad-artifact-runner.service \
        artifact-agent-control.service \
        artifact-agent-worker.service \
        artifact-agent-approval-ui.service \
        scidiscovery-control.service \
        scidiscovery-worker.service \
        scidiscovery-approval-ui.service \
        tcad-control.service
    do
        systemctl disable --now "$unit" >/dev/null 2>&1 || true
    done
    if mountpoint -q "$WORKSPACE/.codex"; then
        umount "$WORKSPACE/.codex"
    fi
    rm -f \
        /etc/systemd/system/tcad-artifact-execution.service \
        /etc/systemd/system/tcad-artifact-runner.service \
        /etc/systemd/system/artifact-agent-control.service \
        /etc/systemd/system/artifact-agent-worker.service \
        /etc/systemd/system/artifact-agent-approval-ui.service \
        /etc/systemd/system/tcad-control.service.d/m9-packet-store.conf
    rmdir /etc/systemd/system/tcad-control.service.d >/dev/null 2>&1 || true
    systemctl daemon-reload
}

backup_legacy_user_entrypoints() {
    local backup="$1" home bin name moved=0
    home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    bin="${home}/.local/bin"
    for name in \
        artifact-agent artifact-agent-legacy-readonly artifact-agent-mcp \
        scid scid-legacy-readonly tcad-artifact-execution-daemon \
        tcad-artifact-execution-mcp tcad-artifact-init \
        tcad-artifact-runner-daemon
    do
        if [[ -f "${bin}/${name}" || -L "${bin}/${name}" ]]; then
            install -d -o root -g root -m 0755 "${backup}/legacy-user-bin"
            mv "${bin}/${name}" "${backup}/legacy-user-bin/${name}"
            moved=1
        fi
    done
    [[ "$moved" -eq 0 ]] || printf 'Legacy user CLI backup: %s\n' "${backup}/legacy-user-bin"
}

install_platform_skill() {
    local backup="$1" platform="$2" skill_root="$3"
    local source target stage
    source="${WORKSPACE}/skills/sentaurus-tcad-code"
    target="${skill_root}/sentaurus-tcad-code"
    stage="${skill_root}/.sentaurus-tcad-code.new.$$"
    [[ -f "${source}/SKILL.md" ]] || die "missing Sentaurus TCAD code Skill"
    install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$skill_root"
    if [[ -e "$target" ]]; then
        install -d -o root -g root -m 0755 "${backup}/skills/${platform}"
        cp -a "$target" "${backup}/skills/${platform}/sentaurus-tcad-code"
    fi
    rm -rf "$stage"
    cp -a "$source" "$stage"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$stage"
    find "$stage" -type d -exec chmod 0755 {} +
    find "$stage" -type f -exec chmod 0644 {} +
    find "$stage/scripts" -type f -exec chmod 0755 {} +
    rm -rf "$target"
    mv "$stage" "$target"
    printf '%s Skill installed: %s\n' "$platform" "$target"
}

install_platform_skills() {
    local backup="$1" service_home
    service_home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    [[ -n "$service_home" && "$service_home" = /* ]] || \
        die "cannot resolve home directory for ${SERVICE_USER}"
    if [[ "$PLATFORM" == "codex" || "$PLATFORM" == "both" ]]; then
        install_platform_skill "$backup" codex \
            "${SCID_CODEX_SKILL_ROOT:-${service_home}/.codex/skills}"
    fi
    if [[ "$PLATFORM" == "claude" || "$PLATFORM" == "both" ]]; then
        install_platform_skill "$backup" claude \
            "${SCID_CLAUDE_SKILL_ROOT:-${service_home}/.claude/skills}"
    fi
}

configure_platform() {
    local timestamp backup
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup="${BACKUP_ROOT}/${timestamp}"
    install -d -o root -g root -m 0755 "$BACKUP_ROOT" "$backup"
    [[ ! -e "$WORKSPACE/.codex" ]] || cp -a "$WORKSPACE/.codex" "$backup/codex"
    [[ ! -e "$WORKSPACE/.claude" ]] || cp -a "$WORKSPACE/.claude" "$backup/claude"
    [[ ! -e "$WORKSPACE/.mcp.json" ]] || cp -a "$WORKSPACE/.mcp.json" "$backup/mcp.json"
    [[ ! -e "$WORKSPACE/AGENTS.md" ]] || cp -a "$WORKSPACE/AGENTS.md" "$backup/AGENTS.md"
    [[ ! -e "$WORKSPACE/CLAUDE.md" ]] || cp -a "$WORKSPACE/CLAUDE.md" "$backup/CLAUDE.md"
    backup_legacy_user_entrypoints "$backup"
    install_platform_skills "$backup"
    if [[ "$PLATFORM" == "codex" || "$PLATFORM" == "both" ]]; then
        rm -rf "$WORKSPACE/.codex"
        install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$WORKSPACE/.codex"
    fi
    runuser -u "$SERVICE_USER" -- env PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" - <<PY
from pathlib import Path
from scidiscovery.platforms import initialize_platform

root = Path('$WORKSPACE')
prompt = root / 'AGENTS.md'
if prompt.exists():
    text = prompt.read_text(encoding='utf-8')
    begin = '<!-- BEGIN TCAD CONTROL -->'
    end = '<!-- END TCAD CONTROL -->'
    if begin in text and end in text:
        before, remainder = text.split(begin, 1)
        _, after = remainder.split(end, 1)
        text = before.rstrip() + '\n' + after.lstrip()
    legacy_begin = '<!-- LEGACY EXECUTION ENTRY BEGIN:'
    legacy_end = '<!-- LEGACY EXECUTION ENTRY END -->'
    if legacy_begin in text and legacy_end in text:
        before, remainder = text.split(legacy_begin, 1)
        _, after = remainder.split(legacy_end, 1)
        text = before.rstrip() + '\n' + after.lstrip()
    prompt.write_text(text, encoding='utf-8')
initialize_platform(
    '$PLATFORM', root, python_executable=Path('$PYTHON'),
    python_path=Path('$SITE_ROOT'),
    control_socket=Path('$CONTROL_SOCKET'),
    worker_socket=Path('$WORKER_SOCKET'), codex_config_root=root / '.codex',
)
PY
    [[ ! -e "$WORKSPACE/.codex" ]] || chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/.codex"
    [[ ! -e "$WORKSPACE/.claude" ]] || chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/.claude"
    [[ ! -e "$WORKSPACE/.mcp.json" ]] || chown "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/.mcp.json"
    [[ ! -e "$WORKSPACE/AGENTS.md" ]] || chown "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/AGENTS.md"
    [[ ! -e "$WORKSPACE/CLAUDE.md" ]] || chown "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/CLAUDE.md"
    printf 'Platform configuration backup: %s\n' "$backup"
}

install_units() {
    local stage unit
    stage="$(mktemp -d)"
    render_units "$stage"
    for unit in \
        scidiscovery-control.service \
        scidiscovery-worker.service \
        scidiscovery-approval-ui.service \
        tcad-control.service
    do
        install -o root -g root -m 0644 "$stage/$unit" "/etc/systemd/system/$unit"
    done
    systemd-analyze verify "$stage"/*.service
    rm -rf "$stage"
    systemctl daemon-reload
}

wait_for_socket() {
    local socket="$1" service="$2" count
    for count in $(seq 1 50); do
        [[ -S "$socket" ]] && return 0
        systemctl is-active --quiet "$service" || break
        sleep 0.1
    done
    systemctl --no-pager --full status "$service" >&2 || true
    die "service socket did not become ready: ${socket}"
}

probe_mcp() {
    local module="$1" socket="$2" expected="$3"
    printf '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n' | \
        PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" -m "$module" --socket "$socket" | \
        "$PYTHON" -c '
import json, sys
payload = json.load(sys.stdin)
observed = len(payload["result"]["tools"])
expected = int(sys.argv[1])
if observed != expected:
    raise SystemExit(f"tool count mismatch: expected={expected} observed={observed}")
print(f"MCP tool probe: pass ({observed})")
' "$expected"
}

verify_installation() {
    local unit
    local units=(
        scidiscovery-control.service \
        scidiscovery-worker.service \
        scidiscovery-approval-ui.service
    )
    if [[ -z "$TCAD_COMMAND_CONFIG" ]]; then
        units+=(tcad-control.service)
    fi
    for unit in "${units[@]}"
    do
        systemctl is-active --quiet "$unit" || die "service is not active: ${unit}"
    done
    wait_for_socket "$CONTROL_SOCKET" scidiscovery-control.service
    wait_for_socket "$WORKER_SOCKET" scidiscovery-worker.service
    probe_mcp scidiscovery.artifact_agent.interfaces.mcp_proxy "$CONTROL_SOCKET" 31
    printf '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n' | \
        PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" -m \
        scidiscovery.artifact_agent.interfaces.mcp_worker_proxy \
        --socket "$WORKER_SOCKET" --worker-id ideator | \
        "$PYTHON" -c 'import json,sys; assert len(json.load(sys.stdin)["result"]["tools"]) == 16; print("worker MCP probe: pass (16)")'
    if [[ -z "$TCAD_COMMAND_CONFIG" ]]; then
        wait_for_socket "$TCAD_SOCKET" tcad-control.service
        probe_mcp tcad_artifact.execution_mcp "$TCAD_SOCKET" 4
    fi
    [[ "$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${APPROVAL_PORT}/")" == 200 ]] || \
        die "approval UI health probe failed"
    PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" - \
        "$WORKSPACE" "$SITE_ROOT" "$PLATFORM" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
site = sys.argv[2]
platform = sys.argv[3]
if platform in {'codex', 'both'}:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    config = tomllib.loads(root.joinpath('.codex/config.toml').read_text(encoding='utf-8'))
    assert set(config['mcp_servers']) == {'scidiscovery'}
    assert config['mcp_servers']['scidiscovery']['enabled'] is True
    assert config['mcp_servers']['scidiscovery']['env']['PYTHONPATH'] == site
    assert config['mcp_servers']['scidiscovery']['env']['PYTHONNOUSERSITE'] == '1'
    assert len(tuple(root.joinpath('.codex/agents').glob('*.toml'))) == 9
    print('Codex profile probe: pass (1 MCP, 9 roles)')
if platform in {'claude', 'both'}:
    config = json.loads(root.joinpath('.mcp.json').read_text(encoding='utf-8'))
    server = config['mcpServers']['scidiscovery']
    assert server['env']['PYTHONPATH'] == site
    assert server['env']['PYTHONNOUSERSITE'] == '1'
    assert len(tuple(root.joinpath('.claude/agents').glob('*.md'))) == 9
    assert '<!-- BEGIN SCIDISCOVERY SCHEDULER -->' in root.joinpath('CLAUDE.md').read_text(encoding='utf-8')
    print('Claude profile probe: pass (1 MCP, 9 roles)')
PY
}

install_all() {
    require_root
    retire_old_deployment
    install_packages
    install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0750 "$SCID_STATE" "$TCAD_STATE"
    install -d -o root -g "$SERVICE_GROUP" -m 0750 "$CONFIG_ROOT"
    ensure_secret "${CONFIG_ROOT}/task-token.key"
    ensure_secret "${CONFIG_ROOT}/approval-receipt.key"
    write_policy
    install_units
    configure_platform
    systemctl enable --now \
        scidiscovery-control.service \
        scidiscovery-worker.service \
        scidiscovery-approval-ui.service
    if [[ -z "$TCAD_COMMAND_CONFIG" ]]; then
        systemctl enable --now tcad-control.service
    else
        systemctl disable --now tcad-control.service >/dev/null 2>&1 || true
    fi
    verify_installation
    printf '%s\n' \
        'Clean SciDiscovery/TCAD deployment: pass' \
        "Approval UI: http://127.0.0.1:${APPROVAL_PORT}" \
        "$([[ -n "$TCAD_COMMAND_CONFIG" ]] && printf 'External TCAD transport configured.' || printf 'Local deployment smoke profile configured.')" \
        "Restart ${PLATFORM} so the SciDiscovery MCP definition and role files reload."
}

status() {
    systemctl --no-pager --full status \
        scidiscovery-control.service \
        scidiscovery-worker.service \
        scidiscovery-approval-ui.service \
        tcad-control.service || true
    for socket in "$CONTROL_SOCKET" "$WORKER_SOCKET" "$TCAD_SOCKET"; do
        [[ -S "$socket" ]] && printf 'socket ready: %s\n' "$socket" || printf 'socket missing: %s\n' "$socket"
    done
}

uninstall_services() {
    require_root
    local unit
    for unit in \
        scidiscovery-control.service \
        scidiscovery-worker.service \
        scidiscovery-approval-ui.service \
        tcad-control.service \
        artifact-agent-control.service \
        artifact-agent-worker.service \
        artifact-agent-approval-ui.service \
        tcad-artifact-execution.service \
        tcad-artifact-runner.service
    do
        systemctl disable --now "$unit" >/dev/null 2>&1 || true
        rm -f "/etc/systemd/system/$unit"
    done
    systemctl daemon-reload
    printf '%s\n' 'Services removed. State and backups were preserved.'
}

case "${1:---dry-run}" in
    --dry-run)
        require_sources
        validate_source
        preview
        ;;
    install)
        require_sources
        install_all
        ;;
    status) status ;;
    uninstall) uninstall_services ;;
    *) die "usage: $0 [--dry-run|install|status|uninstall]" ;;
esac
