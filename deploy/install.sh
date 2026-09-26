#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly WORKSPACE="${SCID_WORKSPACE:-${SOURCE_ROOT}/workspace/default}"
readonly CODEX_LAUNCH_ROOT="${SCID_CODEX_LAUNCH_ROOT:-}"
readonly PYTHON="${SCID_PYTHON:-$(command -v python3 || true)}"
readonly SERVICE_USER="${SCID_SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
readonly SERVICE_GROUP="${SCID_SERVICE_GROUP:-$(id -gn "$SERVICE_USER")}"
readonly PLATFORM="${SCID_PLATFORM:-codex}"
readonly WORKER_BACKEND="${SCID_WORKER_BACKEND:-local}"
readonly PLUGIN_SPECIFICATION="${SCID_PLUGINS:-}"
readonly INSTALL_ROOT="${SCID_INSTALL_ROOT:-/opt/scidiscovery}"
readonly SITE_ROOT="${INSTALL_ROOT}/site"
readonly SCID_STATE="${SCID_STATE_ROOT:-/var/lib/scidiscovery}"
readonly LOCAL_WORKSPACE_ROOT="${WORKSPACE}/.scidiscovery-runs"
readonly INSTANCE_ARCHIVE_ROOT="${WORKSPACE}/.scidiscovery-archive/instances"
readonly TCAD_STATE="${TCAD_STATE_ROOT:-${SCID_STATE}/tcad}"
readonly CONFIG_ROOT="${SCID_CONFIG_ROOT:-/etc/scidiscovery}"
readonly BACKUP_ROOT="${SCID_BACKUP_ROOT:-/var/backups/scidiscovery}"
readonly CONTROL_SOCKET="/run/scidiscovery/control.sock"
readonly TCAD_SOCKET="/run/scidiscovery-tcad/control.sock"
readonly TCAD_COMMAND_CONFIG="${SCID_TCAD_COMMAND_CONFIG:-}"
readonly APPROVAL_PORT="${SCID_APPROVAL_PORT:-8765}"
declare -a PLATFORM_SKILLS=()
PACKAGE_STAGE=""
TRANSACTION_ROOT=""
ROLLBACK_ARMED=0
TCAD_ENABLED=0
TCAD_LOCAL_SERVICE=0
FIGURE_DEPENDENCY_CONTRACT=""
declare -a SELECTED_PLUGINS=()
declare -a SELECTED_PLUGIN_DISTRIBUTIONS=()

die() {
    printf 'ERROR: %s\n' "$*" >&2
    if [[ "$ROLLBACK_ARMED" -eq 1 ]]; then
        rollback_install 1
    fi
    exit 1
}

validate_systemd_value() {
    local name="$1" value="$2"
    [[ ! "$value" =~ [[:cntrl:]] && "$value" != *'"'* && \
       "$value" != *'%'* && "$value" != *'$'* && "$value" != *'@'* && \
       "$value" != *'\\'* ]] || \
        die "${name} contains a character unsafe for systemd templates"
}

codex_launch_root_is_distinct() {
    [[ -n "$CODEX_LAUNCH_ROOT" ]] || return 1
    [[ "$(realpath -e -- "$CODEX_LAUNCH_ROOT")" != "$(realpath -e -- "$SOURCE_ROOT")" && \
       "$(realpath -e -- "$CODEX_LAUNCH_ROOT")" != "$(realpath -e -- "$WORKSPACE")" ]]
}

validate_local_workspace_root() {
    [[ "$WORKER_BACKEND" == "local" ]] || return 0
    [[ ! -L "$LOCAL_WORKSPACE_ROOT" ]] || \
        die "local Run workspace must not be a symbolic link"
    local workspace_real local_real state_real
    workspace_real="$(realpath -e -- "$WORKSPACE")"
    local_real="$(realpath -m -- "$LOCAL_WORKSPACE_ROOT")"
    state_real="$(realpath -m -- "$SCID_STATE")"
    [[ "$local_real" == "$workspace_real/"* ]] || \
        die "local Run workspace must be inside SCID_WORKSPACE"
    if [[ "$local_real" == "$state_real" || \
          "$local_real" == "$state_real/"* || \
          "$state_real" == "$local_real/"* ]]; then
        die "local Run workspace must not overlap SCID_STATE_ROOT"
    fi
}

create_local_workspace_root() {
    [[ "$WORKER_BACKEND" == "local" ]] || return 0
    "$PYTHON" - "$WORKSPACE" "$SERVICE_USER" "$SERVICE_GROUP" <<'PY'
import grp
import os
import pwd
import sys

workspace, user, group = sys.argv[1:]
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent = os.open(workspace, flags)
try:
    try:
        os.mkdir(".scidiscovery-runs", mode=0o700, dir_fd=parent)
    except FileExistsError:
        pass
    child = os.open(".scidiscovery-runs", flags, dir_fd=parent)
    try:
        os.fchown(child, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid)
        os.fchmod(child, 0o700)
    finally:
        os.close(child)
finally:
    os.close(parent)
PY
}

create_instance_archive_root() {
    # Only these two owned directories receive permissions; never chmod the workspace.
    "$PYTHON" - "$WORKSPACE" "$SERVICE_USER" "$SERVICE_GROUP" <<'PY'
import grp
import os
import pwd
import sys

workspace, user, group = sys.argv[1:]
uid, gid = pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent = os.open(workspace, flags)
try:
    for name in (".scidiscovery-archive", "instances"):
        try:
            os.mkdir(name, mode=0o750, dir_fd=parent)
        except FileExistsError:
            pass
        child = os.open(name, flags, dir_fd=parent)
        os.close(parent)
        parent = child
        os.fchown(parent, uid, gid)
        os.fchmod(parent, 0o750)
finally:
    os.close(parent)
PY
}

require_sources() {
    local path plugin_ids plugin_distributions
    local -a deployment_paths=(
        "$WORKSPACE" "$PYTHON" "$INSTALL_ROOT" "$SCID_STATE"
        "$LOCAL_WORKSPACE_ROOT" "$INSTANCE_ARCHIVE_ROOT" "$CONFIG_ROOT" "$BACKUP_ROOT"
    )
    for path in \
        pyproject.toml \
        src/scidiscovery/default_agent_settings.json \
        deploy/agent_settings_previous_default.json \
        deploy/plugin_selection.py \
        deploy/systemd/scidiscovery-control.service.in \
        deploy/systemd/scidiscovery-approval-ui.service.in
    do
        [[ -f "${SOURCE_ROOT}/${path}" ]] || die "missing source: ${path}"
    done
    [[ "$WORKSPACE" = /* && -d "$WORKSPACE" && ! -L "$WORKSPACE" ]] || \
        die "SCID_WORKSPACE must name an existing absolute project directory"
    [[ "$WORKSPACE" != "$SOURCE_ROOT" ]] || \
        die "SCID_WORKSPACE must be separate from the source repository"
    if [[ -n "$CODEX_LAUNCH_ROOT" ]]; then
        [[ "$CODEX_LAUNCH_ROOT" = /* && -d "$CODEX_LAUNCH_ROOT" && \
           ! -L "$CODEX_LAUNCH_ROOT" ]] || \
            die "SCID_CODEX_LAUNCH_ROOT must name an existing absolute directory"
    fi
    for path in "${deployment_paths[@]}"; do
        [[ "$path" = /* ]] || die "deployment paths must be absolute: ${path}"
        validate_systemd_value "deployment path" "$path"
    done
    [[ "$SERVICE_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || \
        die "SCID_SERVICE_USER is invalid"
    [[ "$SERVICE_GROUP" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || \
        die "SCID_SERVICE_GROUP is invalid"
    [[ "$APPROVAL_PORT" =~ ^[0-9]+$ && "$APPROVAL_PORT" -ge 1 && "$APPROVAL_PORT" -le 65535 ]] || \
        die "SCID_APPROVAL_PORT must be in 1..65535"
    [[ -n "$PYTHON" && -x "$PYTHON" ]] || die "base Python is unavailable: ${PYTHON}"
    [[ "$PLATFORM" == "codex" ]] || \
        die "SCID_PLATFORM must be codex"
    [[ "$WORKER_BACKEND" == "local" || "$WORKER_BACKEND" == "hardened" ]] || \
        die "SCID_WORKER_BACKEND must be local or hardened"
    validate_local_workspace_root
    if [[ -n "$PLUGIN_SPECIFICATION" ]]; then
        plugin_ids="$(
            "$PYTHON" "$SOURCE_ROOT/deploy/plugin_selection.py" \
                --source-root "$SOURCE_ROOT" --plugins "$PLUGIN_SPECIFICATION" --field id
        )" || die "SCID_PLUGINS validation failed"
        plugin_distributions="$(
            "$PYTHON" "$SOURCE_ROOT/deploy/plugin_selection.py" \
                --source-root "$SOURCE_ROOT" --plugins "$PLUGIN_SPECIFICATION" \
                --field distribution
        )" || die "SCID_PLUGINS distribution resolution failed"
        mapfile -t SELECTED_PLUGINS <<<"$plugin_ids"
        mapfile -t SELECTED_PLUGIN_DISTRIBUTIONS <<<"$plugin_distributions"
    fi
    if [[ " ${SELECTED_PLUGINS[*]} " == *" tcad_artifact "* ]]; then
        TCAD_ENABLED=1
        [[ -n "$TCAD_COMMAND_CONFIG" ]] || TCAD_LOCAL_SERVICE=1
        PLATFORM_SKILLS+=(sentaurus-tcad-code)
        for path in \
            skills/sentaurus-tcad-code/SKILL.md \
            skills/sentaurus-tcad-code/references/control-materialization.md \
            skills/sentaurus-tcad-code/references/diagnostics.md \
            skills/sentaurus-tcad-code/references/execution-contract.md \
            skills/sentaurus-tcad-code/references/review.md \
            skills/sentaurus-tcad-code/references/sdevice.md \
            skills/sentaurus-tcad-code/references/sprocess.md \
            skills/sentaurus-tcad-code/references/sprocess-r2020.09-recipes.md \
            skills/sentaurus-tcad-code/references/manuals/catalog.json \
            skills/sentaurus-tcad-code/references/manuals/topics.json \
            skills/sentaurus-tcad-code/references/manuals/R-2020.09/sprocess_ug.pdf \
            skills/sentaurus-tcad-code/references/manuals/R-2020.09/sdevice_ug.pdf \
            skills/sentaurus-tcad-code/references/manuals/R-2020.09/sentaurus_relnote.pdf \
            skills/sentaurus-tcad-code/scripts/manual_search.py \
            skills/sentaurus-tcad-code/scripts/manual_extract.py \
            skills/sentaurus-tcad-code/scripts/validate_deck_project.py \
            plugins/tcad_artifact/deploy/configure_runtime.py \
            plugins/tcad_artifact/deploy/systemd/tcad-control.service.in
        do
            [[ -f "${SOURCE_ROOT}/${path}" ]] || die "missing TCAD source: ${path}"
        done
        if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
            [[ "$TCAD_STATE" = /* ]] || die "TCAD_STATE_ROOT must be absolute"
            validate_systemd_value "TCAD state path" "$TCAD_STATE"
        fi
    elif [[ -n "$TCAD_COMMAND_CONFIG" ]]; then
        die "SCID_TCAD_COMMAND_CONFIG requires the tcad_artifact plugin"
    fi
    printf 'Selected plugins: %s\n' "${PLUGIN_SPECIFICATION:-none}"
    printf 'Worker backend: %s\n' "$WORKER_BACKEND"
    command -v pdftotext >/dev/null || die "pdftotext is required for task PDF inputs"
    command -v systemd-analyze >/dev/null || die "systemd-analyze is required to validate service units"
    if [[ "$TCAD_ENABLED" -eq 1 && -n "$TCAD_COMMAND_CONFIG" ]]; then
        [[ "$TCAD_COMMAND_CONFIG" = /* && -f "$TCAD_COMMAND_CONFIG" && ! -L "$TCAD_COMMAND_CONFIG" ]] || \
            die "SCID_TCAD_COMMAND_CONFIG must name an absolute regular file"
        validate_systemd_value "SCID_TCAD_COMMAND_CONFIG" "$TCAD_COMMAND_CONFIG"
    fi
}

validate_source() {
    local plugin pythonpath="${SOURCE_ROOT}/src"
    for plugin in "${SELECTED_PLUGINS[@]}"; do
        pythonpath+=":${SOURCE_ROOT}/plugins/${plugin}"
    done
    (
        cd "$WORKSPACE"
        PYTHONNOUSERSITE=1 PYTHONPATH="$pythonpath" "$PYTHON" - <<'PY'
import scidiscovery.artifact_agent
print('source imports: pass')
PY
    )
}

validate_base_python() {
    "$PYTHON" -m pip --version
    "$PYTHON" - <<'PY'
from importlib.metadata import PackageNotFoundError, version
from packaging.version import Version
import sys


def parsed_version(distribution: str) -> Version:
    try:
        raw = version(distribution)
    except PackageNotFoundError as exc:
        raise SystemExit(
            f"missing base Python dependency: {distribution}; "
            "install it with Conda or the system Python package manager"
        ) from exc
    print(f"base dependency: {distribution}={raw}")
    return Version(raw)


if not Version("2") <= parsed_version("pydantic") < Version("3"):
    raise SystemExit("base Python requires pydantic>=2,<3")
if not Version("10") <= parsed_version("Pillow") < Version("13"):
    raise SystemExit("base Python requires Pillow>=10,<13")
if not Version("4") <= parsed_version("jsonschema") < Version("5"):
    raise SystemExit("base Python requires jsonschema>=4,<5")
if parsed_version("setuptools") < Version("68"):
    raise SystemExit("base Python requires setuptools>=68")
if sys.version_info < (3, 11):
    parsed_version("tomli")
print("base Python dependency check: pass")
PY
}

service_python() {
    local pythonpath="$1" service_path service_home manager_environment
    shift
    service_path="$(systemd-path search-binaries-default)" || die "cannot resolve systemd service PATH"
    # Rendered units do not override PATH; honor a manager-level PATH if supplied.
    manager_environment="$(systemctl show-environment)" || die "cannot inspect systemd service environment"
    while IFS= read -r assignment; do
        [[ "$assignment" != PATH=* ]] || service_path="${assignment#PATH=}"
    done <<<"$manager_environment"
    # systemctl can emit shell quoting. Do not interpret it or accept partial paths.
    [[ "$service_path" =~ ^/[A-Za-z0-9_./+-]*(:/[A-Za-z0-9_./+-]*)*$ ]] || \
        die "unsafe systemd service PATH; require unquoted absolute entries without empty segments"
    service_home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    [[ -n "$service_path" && -n "$service_home" ]] || die "cannot resolve service environment"
    local -a command=(env -i "PATH=$service_path" "HOME=$service_home"
        "USER=$SERVICE_USER" "LOGNAME=$SERVICE_USER" PYTHONNOUSERSITE=1
        "PYTHONPATH=$pythonpath" OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1
        OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 "$PYTHON" "$@")
    (
        cd "$WORKSPACE"
        if [[ "$(id -un)" == "$SERVICE_USER" && "$(id -gn)" == "$SERVICE_GROUP" ]]; then
            "${command[@]}"
        elif [[ "$(id -u)" -eq 0 ]]; then
            runuser -u "$SERVICE_USER" -g "$SERVICE_GROUP" -- "${command[@]}"
        else
            sudo -n -u "$SERVICE_USER" -g "$SERVICE_GROUP" -- "${command[@]}"
        fi
    )
}

validate_figure_dependencies() {
    [[ " ${SELECTED_PLUGINS[*]} " == *" curve_figure_evidence "* ]] || return 0
    local prefix="${1:-}" observed
    if [[ -n "$prefix" ]]; then
        observed="$(service_python "$prefix" "$prefix/curve_figure_evidence/figure_dependencies.py" --installed)" || \
            die "installed figure dependency preflight failed"
        [[ "$observed" == "$FIGURE_DEPENDENCY_CONTRACT" ]] || die "installed figure dependency contract changed"
    else
        FIGURE_DEPENDENCY_CONTRACT="$(service_python "${SOURCE_ROOT}/plugins/curve_figure_evidence" \
            "$SOURCE_ROOT/plugins/curve_figure_evidence/curve_figure_evidence/figure_dependencies.py")" || \
            die "figure dependency preflight failed before installation transaction"
        printf 'Verified figure dependencies: %s\n' "$FIGURE_DEPENDENCY_CONTRACT"
    fi
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
    local output="$1"
    local plugin_config_args=""
    local local_workspace_args=""
    local local_workspace_access=""
    if [[ "$TCAD_ENABLED" -eq 1 ]]; then
        plugin_config_args="--plugin-config \"tcad_artifact=${CONFIG_ROOT}/tcad-plugin.json\""
    fi
    if [[ "$WORKER_BACKEND" == "local" ]]; then
        local_workspace_args="--local-workspace-root \"${LOCAL_WORKSPACE_ROOT}\""
        local_workspace_access="\"${LOCAL_WORKSPACE_ROOT}\""
    fi
    local common=(
        "PROJECT_ROOT=${WORKSPACE}"
        "STATE_ROOT=${SCID_STATE}"
        "LOCAL_WORKSPACE_ARGS=${local_workspace_args}"
        "LOCAL_WORKSPACE_ACCESS=${local_workspace_access}"
        "CONTROL_GROUP=${SERVICE_GROUP}"
        "PYTHON_ACCESS_GROUP=${SERVICE_GROUP}"
        "PYTHONPATH=${SITE_ROOT}"
        "PYTHON=${PYTHON}"
        "RUNTIME_IDENTITY=${SITE_ROOT}/runtime-identity.json"
        "APPROVAL_SECRET=${CONFIG_ROOT}/approval-receipt.key"
        "AGENT_SETTINGS_FILE=${CONFIG_ROOT}/agent-settings.json"
        "WORKER_BACKEND=${WORKER_BACKEND}"
    )
    render_unit \
        "${SOURCE_ROOT}/deploy/systemd/scidiscovery-control.service.in" \
        "${output}/scidiscovery-control.service" \
        "${common[@]}" \
        "CONTROL_USER=${SERVICE_USER}" \
        "CONTROL_SOCKET=${CONTROL_SOCKET}" \
        "PLUGIN_CONFIG_ARGS=${plugin_config_args}" \
        "APPROVAL_PORT=${APPROVAL_PORT}" \
        "RUNTIME_ROOT=/run/scidiscovery"
    render_unit \
        "${SOURCE_ROOT}/deploy/systemd/scidiscovery-approval-ui.service.in" \
        "${output}/scidiscovery-approval-ui.service" \
        "${common[@]}" \
        "APPROVAL_USER=${SERVICE_USER}" \
        "INSTANCE_ARCHIVE_ROOT=${INSTANCE_ARCHIVE_ROOT}" \
        "PLUGIN_CONFIG_ARGS=${plugin_config_args}" \
        "APPROVAL_PORT=${APPROVAL_PORT}" \
        "LOCAL_IDENTITY=local_user" \
        "LOCAL_DISPLAY_NAME=Local_user"
    if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
        render_unit \
            "${SOURCE_ROOT}/plugins/tcad_artifact/deploy/systemd/tcad-control.service.in" \
            "${output}/tcad-control.service" \
            "PROJECT_ROOT=${WORKSPACE}" \
            "PYTHONPATH=${SITE_ROOT}" \
            "EXECUTION_USER=${SERVICE_USER}" \
            "CONTROL_GROUP=${SERVICE_GROUP}" \
            "EXECUTION_PYTHON=${PYTHON}" \
            "RUNTIME_IDENTITY=${SITE_ROOT}/runtime-identity.json" \
            "EXECUTION_STATE_ROOT=${TCAD_STATE}" \
            "EXECUTION_POLICY=${CONFIG_ROOT}/tcad-policy.json" \
            "EXECUTION_SOCKET=${TCAD_SOCKET}" \
            "EXECUTION_RUNTIME_ROOT=/run/scidiscovery-tcad"
    fi
}

preview() {
    local stage plugin pythonpath="${SOURCE_ROOT}/src" launch_is_distinct=0
    for plugin in "${SELECTED_PLUGINS[@]}"; do
        pythonpath+=":${SOURCE_ROOT}/plugins/${plugin}"
    done
    stage="$(mktemp -d)"
    if codex_launch_root_is_distinct; then
        launch_is_distinct=1
    fi
    render_units "$stage"
    printf 'Rendered services: %s\n' "$(cd "$stage" && printf '%s ' *.service)"
    systemd-analyze verify "$stage"/*.service
    (
        cd "$SOURCE_ROOT"
        SCID_INSTALL_CODEX_LAUNCH_ROOT="$CODEX_LAUNCH_ROOT" \
        SCID_INSTALL_CODEX_LAUNCH_DISTINCT="$launch_is_distinct" \
        PYTHONPATH="$pythonpath" "$PYTHON" - <<PY
import os
from pathlib import Path
from scidiscovery.platforms import initialize_platform
from scidiscovery.operations.catalog import compile_installed_catalog

catalog = compile_installed_catalog()
runtime_plugin_configs = (
    {'tcad_artifact': Path('${CONFIG_ROOT}/tcad-plugin.json')}
    if int('${TCAD_ENABLED}') and 'tcad_artifact' in catalog.runtime_plugin_ids()
    else {}
)

common = {
    'python_executable': Path('$PYTHON'),
    'control_socket': Path('$CONTROL_SOCKET'),
    'state_root': Path('$SCID_STATE'),
    'local_workspace_root': Path('$LOCAL_WORKSPACE_ROOT'),
    'worker_backend': '$WORKER_BACKEND',
    'dry_run': True,
    'operation_catalog': catalog,
    'runtime_plugin_configs': runtime_plugin_configs,
}
initialize_platform(
    'codex', Path('$SOURCE_ROOT'),
    codex_config_root=Path('$stage/codex'), **common,
)
try:
    Path('$WORKSPACE').resolve().relative_to(Path('$SOURCE_ROOT').resolve())
except ValueError:
    initialize_platform(
        'codex', Path('$WORKSPACE'),
        codex_config_root=Path('$stage/external-workspace-codex'), **common,
    )
if int(os.environ['SCID_INSTALL_CODEX_LAUNCH_DISTINCT']):
    initialize_platform(
        'codex', Path(os.environ['SCID_INSTALL_CODEX_LAUNCH_ROOT']),
        codex_config_root=Path('$stage/launch-root-codex'), **common,
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

normalize_database_ownership() {
    local directory link
    local -a directories=("${SCID_STATE}/database")
    [[ "$TCAD_LOCAL_SERVICE" -eq 0 ]] || directories+=("$TCAD_STATE")
    for directory in "${directories[@]}"; do
        if [[ -e "$directory" ]]; then
            [[ -d "$directory" && ! -L "$directory" ]] || \
                die "unsafe database directory: ${directory}"
            chown "$SERVICE_USER:$SERVICE_GROUP" "$directory"
        else
            install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0770 "$directory"
        fi
        link="$(find "$directory" -maxdepth 1 -type l -name '*.sqlite3*' -print -quit)"
        [[ -z "$link" ]] || die "database directory contains a symlink: ${link}"
        find "$directory" -maxdepth 1 -type f -name '*.sqlite3*' \
            -exec chown "$SERVICE_USER:$SERVICE_GROUP" {} +
    done
}

validate_distribution_cohort() {
    local stage="$1" selected_distributions
    [[ -d "$stage" ]] || die "package cohort stage is unavailable: ${stage}"
    selected_distributions="$(IFS=,; printf '%s' "${SELECTED_PLUGIN_DISTRIBUTIONS[*]}")"
    SCID_SELECTED_DISTRIBUTIONS="$selected_distributions" \
        PYTHONNOUSERSITE=1 PYTHONPATH="$stage" "$PYTHON" - "$stage" <<'PY'
import os
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

stage = Path(__import__('sys').argv[1]).resolve()
names = ('scidiscovery', *(name for name in os.environ[
    'SCID_SELECTED_DISTRIBUTIONS'].split(',') if name))
cohort = {canonicalize_name(name) for name in names}
packages = {}
for name in names:
    try:
        package = distribution(name)
    except PackageNotFoundError as error:
        raise SystemExit(f'missing staged distribution: {name}') from error
    location = Path(package.locate_file('')).resolve()
    if not location.is_relative_to(stage):
        raise SystemExit(f'staged distribution resolved outside package stage: {name}={location}')
    packages[canonicalize_name(name)] = package

for source_name, package in packages.items():
    for raw in package.requires or ():
        requirement = Requirement(raw)
        target = canonicalize_name(requirement.name)
        if target not in cohort or (
            requirement.marker is not None and not requirement.marker.evaluate()
        ):
            continue
        observed = packages[target].version
        if requirement.specifier and observed not in requirement.specifier:
            raise SystemExit(
                'incompatible staged distribution cohort: '
                f'{package.metadata["Name"]}=={package.version} requires {requirement}; '
                f'found {packages[target].metadata["Name"]}=={observed}'
            )
print('staged distribution cohort: pass')
PY
}

install_packages() {
    local stage source_stage source_root plugin plugin_root selected_distributions
    local -a package_roots
    stage="${INSTALL_ROOT}/.site.new.$$"
    source_stage="$(mktemp -d)"
    source_root="${source_stage}/scidiscovery"
    install -d -o root -g root -m 0755 "$INSTALL_ROOT"
    rm -rf "$stage"
    install -d "$source_root/src"
    cp -a "$SOURCE_ROOT/pyproject.toml" "$SOURCE_ROOT/README.md" \
        "$SOURCE_ROOT/roles" "$SOURCE_ROOT/deploy" "$SOURCE_ROOT/skills" \
        "$source_root/"
    [[ ! -f "$SOURCE_ROOT/README.zh-CN.md" ]] || \
        cp -a "$SOURCE_ROOT/README.zh-CN.md" "$source_root/"
    cp -a "$SOURCE_ROOT/src/scidiscovery" "$source_root/src/"
    package_roots=("$source_root")
    for plugin in "${SELECTED_PLUGINS[@]}"; do
        plugin_root="${source_stage}/plugin-${plugin}"
        install -d "$plugin_root"
        cp -a "$SOURCE_ROOT/plugins/${plugin}/." "$plugin_root/"
        package_roots+=("$plugin_root")
    done
    find "$source_stage" -type d \( -name __pycache__ -o -name '*.egg-info' -o -name build \) \
        -prune -exec rm -rf {} +
    printf 'Building local application packages (offline, without dependencies)...\n'
    "$PYTHON" -m pip install --disable-pip-version-check --no-input --no-index \
        --root-user-action=ignore --no-deps --no-build-isolation \
        --progress-bar off --upgrade \
        --target "$stage" "${package_roots[@]}"
    rm -rf "$source_stage"
    if [[ -n "$FIGURE_DEPENDENCY_CONTRACT" ]]; then
        # This is the sole runtime binding for exact PDF image recovery.
        "$PYTHON" - "$stage/curve_figure_evidence/figure_dependencies.json" \
            "$FIGURE_DEPENDENCY_CONTRACT" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[1]).write_text(sys.argv[2] + '\n', encoding='utf-8')
PY
        validate_figure_dependencies "$stage"
    fi
    selected_distributions="$(IFS=,; printf '%s' "${SELECTED_PLUGIN_DISTRIBUTIONS[*]}")"
    validate_distribution_cohort "$stage"
    SCID_SELECTED_DISTRIBUTIONS="$selected_distributions" \
        PYTHONNOUSERSITE=1 PYTHONPATH="$stage" "$PYTHON" - <<'PY'
import os
from importlib.metadata import distribution, entry_points
from scidiscovery.artifact_agent.interfaces.mcp_gateway import DescribeInput
from scidiscovery.artifact_agent.interfaces.mcp_root import ArtifactCatalogInput, RunStatusInput
from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
from scidiscovery.operations.catalog import compile_installed_catalog
selected = tuple(
    name for name in os.environ['SCID_SELECTED_DISTRIBUTIONS'].split(',') if name
)
for name in selected:
    package = distribution(name)
    assert any(
        item.group == 'scidiscovery.plugins' for item in package.entry_points
    ), f'{name} does not publish a scidiscovery.plugins entry point'
for retired in (
    'scidiscovery.agent_role_packs',
    'scidiscovery.transform_adapters',
    'scidiscovery.operation_specs',
):
    assert not tuple(entry_points(group=retired)), retired
root_names = {item.name for item in ROOT_TOOLS}
assert {
    'operation_catalog', 'operation_preflight', 'operation_invoke'
} <= root_names
assert not {
    'task_schedule', 'artifact_transform',
    'approval_request_create', 'execution_request_create',
    'execution_approval_request_create',
} & root_names
catalog = compile_installed_catalog()
assert len(catalog.operation_ids()) == len(set(catalog.operation_ids()))
assert DescribeInput.model_json_schema()['properties']['view']['enum'] == ['full', 'invoke']
assert RunStatusInput.model_json_schema()['properties']['intent']['enum'] == [
    'decision', 'status', 'navigation', 'full'
]
assert RunStatusInput.model_json_schema()['properties']['intent']['default'] == 'decision'
assert 'view' not in RunStatusInput.model_json_schema()['properties']
assert DescribeInput.model_json_schema()['properties']['surface']['default'] == 'research'
assert all(item.surface == 'execution' for item in ROOT_TOOLS if item.name.startswith('execution_'))
assert 'producer_inputs' in ArtifactCatalogInput.model_json_schema()['properties']['view']['enum']
print('installed package probe: pass')
PY
    PYTHONNOUSERSITE=1 PYTHONPATH="$stage" "$PYTHON" -m \
        scidiscovery.runtime_identity write \
        --manifest "$stage/runtime-identity.json"
    PYTHONNOUSERSITE=1 PYTHONPATH="$stage" "$PYTHON" -m \
        scidiscovery.runtime_identity verify \
        --manifest "$stage/runtime-identity.json"
    PACKAGE_STAGE="$stage"
}

activate_packages() {
    local replaced quoted_python quoted_site_root quoted_tcad_result_root
    [[ -n "$PACKAGE_STAGE" && -d "$PACKAGE_STAGE" ]] || \
        die "validated package stage is unavailable"
    replaced="${INSTALL_ROOT}/.site.replaced.$$"
    rm -rf "$replaced"
    [[ ! -e "$SITE_ROOT" ]] || mv "$SITE_ROOT" "$replaced"
    mv "$PACKAGE_STAGE" "$SITE_ROOT"
    PACKAGE_STAGE=""
    rm -rf "$replaced"
    chmod -R a-w "$SITE_ROOT"
    find "$SITE_ROOT" -type d -exec chmod a+rx {} +
    printf -v quoted_python '%q' "$PYTHON"
    printf -v quoted_site_root '%q' "$SITE_ROOT"
    cat > /usr/local/bin/scid <<EOF
#!/usr/bin/env bash
env PYTHONNOUSERSITE=1 PYTHONPATH=${quoted_site_root} ${quoted_python} -m scidiscovery.runtime_identity verify --manifest ${quoted_site_root}/runtime-identity.json || exit
exec env PYTHONNOUSERSITE=1 PYTHONPATH=${quoted_site_root} ${quoted_python} -m scidiscovery.artifact_agent.interfaces.cli "\$@"
EOF
    chown root:root /usr/local/bin/scid
    chmod 0755 /usr/local/bin/scid
    if [[ "$TCAD_ENABLED" -eq 1 ]]; then
        printf -v quoted_tcad_result_root '%q' "${SCID_STATE}/executor-results"
        cat > /usr/local/bin/scidiscovery-tcad-transport <<EOF
#!/usr/bin/env bash
env PYTHONNOUSERSITE=1 PYTHONPATH=${quoted_site_root} ${quoted_python} -m scidiscovery.runtime_identity verify --manifest ${quoted_site_root}/runtime-identity.json || exit
exec env PYTHONNOUSERSITE=1 PYTHONPATH=${quoted_site_root} SCIDISCOVERY_TCAD_RESULT_ROOT=${quoted_tcad_result_root} ${quoted_python} -m tcad_artifact.ssh_transport "\$@"
EOF
        chown root:root /usr/local/bin/scidiscovery-tcad-transport
        chmod 0755 /usr/local/bin/scidiscovery-tcad-transport
    else
        rm -f /usr/local/bin/scidiscovery-tcad-transport
    fi
}

configure_tcad_runtime() {
    local -a command=(
        "$PYTHON" "${SOURCE_ROOT}/plugins/tcad_artifact/deploy/configure_runtime.py"
        --policy "${CONFIG_ROOT}/tcad-policy.json"
        --plugin-config "${CONFIG_ROOT}/tcad-plugin.json"
        --state-root "$SCID_STATE"
        --socket "$TCAD_SOCKET"
    )
    [[ -z "$TCAD_COMMAND_CONFIG" ]] || command+=(--command-config "$TCAD_COMMAND_CONFIG")
    PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "${command[@]}"
    chown root:"$SERVICE_GROUP" \
        "${CONFIG_ROOT}/tcad-policy.json" "${CONFIG_ROOT}/tcad-plugin.json"
    chmod 0640 "${CONFIG_ROOT}/tcad-policy.json" "${CONFIG_ROOT}/tcad-plugin.json"
}

retire_legacy_worker_unit() {
    local path="${1:-/etc/systemd/system/scidiscovery-worker.service}"
    [[ -n "$TRANSACTION_ROOT" ]] || die "legacy Worker retirement requires an install transaction"
    "$PYTHON" "${SOURCE_ROOT}/deploy/install_transaction.py" remove-target \
        --root "$TRANSACTION_ROOT" \
        --name unit-scidiscovery-worker \
        --path "$path"
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
    retire_legacy_worker_unit
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

retire_inactive_tcad_surfaces() {
    local service_home skill_target
    local transport_target="${1:-/usr/local/bin/scidiscovery-tcad-transport}"
    local unit_target="${2:-/etc/systemd/system/tcad-control.service}"
    service_home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    [[ -n "$service_home" && "$service_home" = /* ]] || \
        die "cannot resolve home directory for ${SERVICE_USER}"
    skill_target="${3:-${SCID_CODEX_SKILL_ROOT:-${service_home}/.codex/skills}/sentaurus-tcad-code}"
    [[ "$ROLLBACK_ARMED" -eq 1 && -f "${TRANSACTION_ROOT}/manifest.json" ]] || \
        die "TCAD surface retirement requires an active install transaction"
    if [[ "$TCAD_ENABLED" -eq 0 ]]; then
        "$PYTHON" "$SOURCE_ROOT/deploy/install_transaction.py" remove-target \
            --root "$TRANSACTION_ROOT" --name codex-skill-sentaurus-tcad-code \
            --path "$skill_target" \
            --managed-directory-name codex-skill-sentaurus-tcad-code
        "$PYTHON" "$SOURCE_ROOT/deploy/install_transaction.py" remove-target \
            --root "$TRANSACTION_ROOT" --name tcad-transport-cli \
            --path "$transport_target"
    fi
    if [[ "$TCAD_LOCAL_SERVICE" -eq 0 ]]; then
        "$PYTHON" "$SOURCE_ROOT/deploy/install_transaction.py" remove-target \
            --root "$TRANSACTION_ROOT" --name unit-tcad-control \
            --path "$unit_target"
    fi
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
    local backup="$1" platform="$2" skill_root="$3" skill="$4"
    local source target stage
    source="${SOURCE_ROOT}/skills/${skill}"
    target="${skill_root}/${skill}"
    stage="${skill_root}/.${skill}.new.$$"
    [[ -f "${source}/SKILL.md" ]] || die "missing platform Skill: ${skill}"
    install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$skill_root"
    if [[ -e "$target" ]]; then
        install -d -o root -g root -m 0755 "${backup}/skills/${platform}"
        cp -a "$target" "${backup}/skills/${platform}/${skill}"
    fi
    rm -rf "$stage"
    cp -a "$source" "$stage"
    "$PYTHON" "$SOURCE_ROOT/deploy/install_transaction.py" \
        mark-managed-directory --path "$stage" --name "codex-skill-${skill}"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$stage"
    find "$stage" -type d -exec chmod 0755 {} +
    find "$stage" -type f -exec chmod 0644 {} +
    find "$stage/scripts" -type f -exec chmod 0755 {} +
    rm -rf "$target"
    mv "$stage" "$target"
    printf '%s Skill installed: %s\n' "$platform" "$target"
}

install_platform_skills() {
    local backup="$1" service_home skill
    service_home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    [[ -n "$service_home" && "$service_home" = /* ]] || \
        die "cannot resolve home directory for ${SERVICE_USER}"
    for skill in "${PLATFORM_SKILLS[@]}"; do
        install_platform_skill "$backup" codex \
            "${SCID_CODEX_SKILL_ROOT:-${service_home}/.codex/skills}" "$skill"
    done
}

prepare_managed_platform_paths() {
    local path link
    local -a directories=("$SOURCE_ROOT/.codex" "$WORKSPACE/.codex")
    local -a files=("$SOURCE_ROOT/AGENTS.md" "$WORKSPACE/AGENTS.md")
    if codex_launch_root_is_distinct; then
        directories+=("$CODEX_LAUNCH_ROOT/.codex")
        files+=("$CODEX_LAUNCH_ROOT/AGENTS.md")
    fi
    for path in "${directories[@]}"; do
        [[ -e "$path" ]] || continue
        [[ -d "$path" && ! -L "$path" ]] || die "unsafe managed platform directory: ${path}"
        link="$(find "$path" -type l -print -quit)"
        [[ -z "$link" ]] || die "managed platform directory contains a symlink: ${link}"
        chown -R "$SERVICE_USER:$SERVICE_GROUP" "$path"
        chmod -R u+rwX "$path"
    done
    for path in "${files[@]}"; do
        [[ -e "$path" ]] || continue
        [[ -f "$path" && ! -L "$path" ]] || die "unsafe managed platform file: ${path}"
        chown "$SERVICE_USER:$SERVICE_GROUP" "$path"
        chmod u+rw "$path"
    done
}

configure_platform() {
    local timestamp backup workspace_is_nested=0 launch_is_distinct=0
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup="${BACKUP_ROOT}/${timestamp}"
    install -d -o root -g root -m 0755 "$BACKUP_ROOT" "$backup"
    [[ ! -e "$SOURCE_ROOT/.codex" ]] || cp -a "$SOURCE_ROOT/.codex" "$backup/framework-codex"
    [[ ! -e "$SOURCE_ROOT/AGENTS.md" ]] || cp -a "$SOURCE_ROOT/AGENTS.md" "$backup/framework-AGENTS.md"
    [[ ! -e "$WORKSPACE/.codex" ]] || cp -a "$WORKSPACE/.codex" "$backup/workspace-codex"
    [[ ! -e "$WORKSPACE/AGENTS.md" ]] || cp -a "$WORKSPACE/AGENTS.md" "$backup/AGENTS.md"
    if codex_launch_root_is_distinct; then
        launch_is_distinct=1
        [[ ! -e "$CODEX_LAUNCH_ROOT/.codex" ]] || \
            cp -a "$CODEX_LAUNCH_ROOT/.codex" "$backup/launch-codex"
        [[ ! -e "$CODEX_LAUNCH_ROOT/AGENTS.md" ]] || \
            cp -a "$CODEX_LAUNCH_ROOT/AGENTS.md" "$backup/launch-AGENTS.md"
    fi
    backup_legacy_user_entrypoints "$backup"
    install_platform_skills "$backup"
    prepare_managed_platform_paths
    if [[ "$(realpath -e "$WORKSPACE")" == "$SOURCE_ROOT/"* ]]; then
        workspace_is_nested=1
        rm -rf "$WORKSPACE/.codex"
    else
        install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$WORKSPACE/.codex"
    fi
    install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$SOURCE_ROOT/.codex"
    if [[ "$launch_is_distinct" -eq 1 ]]; then
        install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 \
            "$CODEX_LAUNCH_ROOT/.codex"
    fi
    runuser -u "$SERVICE_USER" -- env PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" \
        SCID_INSTALL_CODEX_LAUNCH_ROOT="$CODEX_LAUNCH_ROOT" \
        SCID_INSTALL_CODEX_LAUNCH_DISTINCT="$launch_is_distinct" \
        "$PYTHON" - <<PY
import os
from pathlib import Path
from scidiscovery.platforms import initialize_platform

source_root = Path('$SOURCE_ROOT')
workspace = Path('$WORKSPACE')
workspace_is_nested = bool($workspace_is_nested)
prompt = workspace / 'AGENTS.md'
if prompt.exists():
    text = prompt.read_text(encoding='utf-8')
    managed_blocks = [
        ('<!-- BEGIN TCAD CONTROL -->', '<!-- END TCAD CONTROL -->'),
        ('<!-- LEGACY EXECUTION ENTRY BEGIN:', '<!-- LEGACY EXECUTION ENTRY END -->'),
    ]
    if workspace_is_nested:
        managed_blocks.append((
            '<!-- BEGIN SCIDISCOVERY SCHEDULER -->',
            '<!-- END SCIDISCOVERY SCHEDULER -->',
        ))
    for begin, end in managed_blocks:
        if begin not in text and end not in text:
            continue
        if text.count(begin) != 1 or text.count(end) != 1:
            raise RuntimeError(f'malformed managed block in {prompt}: {begin}')
        before, remainder = text.split(begin, 1)
        _, after = remainder.split(end, 1)
        text = before.rstrip() + '\n' + after.lstrip()
    prompt.write_text(text, encoding='utf-8')
common = {
    'python_executable': Path('$PYTHON'),
    'python_path': Path('$SITE_ROOT'),
    'control_socket': Path('$CONTROL_SOCKET'),
    'state_root': Path('$SCID_STATE'),
    'local_workspace_root': Path('$LOCAL_WORKSPACE_ROOT'),
    'worker_backend': '$WORKER_BACKEND',
    'runtime_plugin_configs': (
        {'tcad_artifact': Path('${CONFIG_ROOT}/tcad-plugin.json')}
        if int('${TCAD_ENABLED}') else {}
    ),
}
initialize_platform(
    'codex', source_root,
    codex_config_root=source_root / '.codex', **common,
)
if not workspace_is_nested:
    initialize_platform(
        'codex', workspace,
        codex_config_root=workspace / '.codex', **common,
    )
if int(os.environ['SCID_INSTALL_CODEX_LAUNCH_DISTINCT']):
    launch_root = Path(os.environ['SCID_INSTALL_CODEX_LAUNCH_ROOT'])
    initialize_platform(
        'codex', launch_root,
        codex_config_root=launch_root / '.codex', **common,
    )
PY
    [[ ! -e "$SOURCE_ROOT/.codex" ]] || chown -R "$SERVICE_USER:$SERVICE_GROUP" "$SOURCE_ROOT/.codex"
    [[ ! -e "$SOURCE_ROOT/AGENTS.md" ]] || chown "$SERVICE_USER:$SERVICE_GROUP" "$SOURCE_ROOT/AGENTS.md"
    [[ ! -e "$WORKSPACE/.codex" ]] || chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/.codex"
    [[ ! -e "$WORKSPACE/AGENTS.md" ]] || chown "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE/AGENTS.md"
    if [[ "$launch_is_distinct" -eq 1 ]]; then
        chown -R "$SERVICE_USER:$SERVICE_GROUP" "$CODEX_LAUNCH_ROOT/.codex"
        chown "$SERVICE_USER:$SERVICE_GROUP" "$CODEX_LAUNCH_ROOT/AGENTS.md"
    fi
    printf 'Platform configuration backup: %s\n' "$backup"
}

install_units() {
    local stage unit
    local -a units=(
        scidiscovery-control.service
        scidiscovery-approval-ui.service
    )
    [[ "$TCAD_LOCAL_SERVICE" -eq 0 ]] || units+=(tcad-control.service)
    stage="$(mktemp -d)"
    render_units "$stage"
    for unit in "${units[@]}"; do
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
    local module="$1" socket="$2" worker_id="$3" mode="$4"
    local -a arguments=(--socket "$socket")
    [[ -z "$worker_id" ]] || arguments+=(--worker-id "$worker_id")
    printf '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n' | \
        PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" -m "$module" "${arguments[@]}" | \
        PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" -c '
import json, sys
listed_names = [item["name"] for item in json.load(sys.stdin)["result"]["tools"]]
names = set(listed_names)
mode = sys.argv[1]
required = {
    "worker": {"worker_open_assignment", "worker_heartbeat",
               "worker_submit_result"},
}.get(mode, set())
if mode == "root":
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import GATEWAY_TOOLS
    required = set(GATEWAY_TOOLS)
if mode == "tcad":
    from tcad_artifact.execution_control import EXECUTION_TOOLS
    required = {tool.name for tool in EXECUTION_TOOLS}
if mode.isdigit() and len(listed_names) != int(mode):
    raise SystemExit(f"tool count mismatch: expected={mode} observed={len(listed_names)}")
if not required <= names or (mode in {"root", "tcad"} and
        (names != required or len(listed_names) != len(required))):
    raise SystemExit(f"MCP tool authority mismatch: {mode}; "
                     f"missing={sorted(required - names)}; unexpected={sorted(names - required)}; "
                     f"observed_count={len(listed_names)}")
print(f"MCP tool probe: pass ({mode}, {len(listed_names)})")
' "$mode"
}

probe_root_context_contract() {
    local module="$1" socket="$2"
    PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" - "$module" "$socket" <<'PY'
import json
import select
import subprocess
import sys

module, socket = sys.argv[1:]
metadata = {
    "session_id": "installation_probe",
    "thread_id": "installation_probe",
    "thread_source": "user",
}
process = subprocess.Popen(
    [sys.executable, "-m", module, "--socket", socket],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)
request_id = 0

def call(stage, name, arguments):
    global request_id
    request_id += 1
    request = {
        "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
            "_meta": {"x-codex-turn-metadata": metadata},
        },
    }
    if process.stdin is None or process.stdout is None:
        raise SystemExit("Root context proxy pipes are unavailable")
    try:
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
    except BrokenPipeError:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise SystemExit(stderr or "Root context proxy exited before request delivery")
    ready, _, _ = select.select([process.stdout], [], [], 10)
    if not ready:
        process.terminate()
        raise SystemExit(json.dumps({"stage": stage, "entry": name,
            "operation_id": arguments.get("name") if arguments.get("view") == "invoke" else None,
            "error": "Root context proxy response timed out"}))
    line = process.stdout.readline()
    if not line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise SystemExit(stderr or "Root context proxy returned no response")
    response = json.loads(line)
    if response.get("id") != request_id:
        raise SystemExit(json.dumps({"stage": stage, "entry": name,
            "error": "Root context proxy response id mismatch"}))
    if "error" in response:
        raise SystemExit(json.dumps({"stage": stage, "entry": name,
            "operation_id": arguments.get("name") if arguments.get("view") == "invoke" else None,
            "error": response["error"]}, ensure_ascii=False))
    return response["result"]["structuredContent"]

try:
    describe = call("describe_gateway", "scid_describe", {"name": "scid_describe"})
    assert describe["inputSchema"]["properties"]["view"]["enum"] == ["full", "invoke"]
    run_status = call("describe_run_status", "scid_describe", {"name": "run_status"})
    assert run_status["inputSchema"]["properties"]["intent"]["enum"] == [
        "decision", "status", "navigation", "full"
    ]
    assert run_status["inputSchema"]["properties"]["intent"]["default"] == "decision"
    assert "view" not in run_status["inputSchema"]["properties"]
    assert describe["inputSchema"]["properties"]["surface"]["default"] == "research"
    artifact_catalog = call("describe_artifact_catalog", "scid_describe", {"name": "artifact_catalog"})
    assert "producer_inputs" in artifact_catalog["inputSchema"]["properties"]["view"]["enum"]
    catalog = call("catalog_public", "scid_catalog", {})
    operation_id = catalog["operations"][0]["operation_id"]
    invoke = call("describe_first_public_invoke", "scid_describe", {
        "name": operation_id, "view": "invoke"})
    operation = invoke["operations"][0]
    assert invoke["view"] == "invoke"
    assert operation["operation_id"] == operation_id
    assert "operation_digest" not in operation
    assert "inputs" in operation and "revision_policy" in operation
    assert operation["contract_view_version"] == "invoke.scientific.v2"
    assert all(set(item) == {"operation_id", "purpose"} for item in catalog["operations"])
    assert catalog["complete"] == (catalog["next_before"] is None)
    print(f"Root context contract probe: pass ({operation_id})")
finally:
    if process.stdin is not None:
        process.stdin.close()
        process.stdin = None
    try:
        returncode = process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.terminate()
        returncode = process.wait(timeout=3)
    if returncode:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise SystemExit(stderr or f"Root context proxy exited with status {returncode}")
PY
}

probe_approval_ui() {
    local status
    printf 'Checking approval UI: http://127.0.0.1:%s/ (10s timeout)...\n' "$APPROVAL_PORT"
    if ! status="$(curl --noproxy '*' --connect-timeout 3 --max-time 10 \
        -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${APPROVAL_PORT}/")"; then
        journalctl -u scidiscovery-approval-ui.service -n 12 --no-pager >&2 || true
        die "approval UI health probe connection failed or timed out on port ${APPROVAL_PORT}"
    fi
    [[ "$status" == 200 ]] || die "approval UI health probe failed: HTTP ${status}"
    printf 'Approval UI health probe: pass\n'
}

verify_installation() {
    validate_figure_dependencies "$SITE_ROOT"
    local unit
    local units=(
        scidiscovery-control.service \
        scidiscovery-approval-ui.service
    )
    if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
        units+=(tcad-control.service)
    fi
    for unit in "${units[@]}"
    do
        systemctl is-active --quiet "$unit" || die "service is not active: ${unit}"
    done
    wait_for_socket "$CONTROL_SOCKET" scidiscovery-control.service
    probe_mcp scidiscovery.artifact_agent.interfaces.mcp_proxy "$CONTROL_SOCKET" "" root
    probe_root_context_contract scidiscovery.artifact_agent.interfaces.mcp_proxy "$CONTROL_SOCKET"
    if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
        wait_for_socket "$TCAD_SOCKET" tcad-control.service
        probe_mcp tcad_artifact.execution_mcp "$TCAD_SOCKET" "" tcad
    fi
    probe_approval_ui
    printf 'Checking Codex installation profiles...\n'
    PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_ROOT" "$PYTHON" - \
        "$SOURCE_ROOT" "$WORKSPACE" "$SITE_ROOT" "$PLATFORM" \
        "$SCID_STATE" "$LOCAL_WORKSPACE_ROOT" "$WORKER_BACKEND" "$TCAD_ENABLED" \
        "${CONFIG_ROOT}/tcad-plugin.json" "$CODEX_LAUNCH_ROOT" <<'PY'
from pathlib import Path
import sys
from scidiscovery.platforms import initialize_platform
from scidiscovery.platforms.codex import validate_installation_profile
source_root = Path(sys.argv[1])
workspace = Path(sys.argv[2])
site = sys.argv[3]
platform = sys.argv[4]
state_root = Path(sys.argv[5])
local_workspace_root = Path(sys.argv[6])
worker_backend = sys.argv[7]
runtime_plugin_configs = (
    {'tcad_artifact': Path(sys.argv[9])} if bool(int(sys.argv[8])) else {}
)
assert platform == 'codex'
if platform == 'codex':
    mcp_count, agent_count = validate_installation_profile(
        source_root, workspace=workspace, python_path=site,
        state_root=state_root,
        local_workspace_root=local_workspace_root,
        worker_backend=worker_backend,
        runtime_plugin_configs=runtime_plugin_configs,
    )
    print(
        f'Codex framework profile probe: pass '
        f'({mcp_count} MCP, {agent_count} agents)'
    )
    if sys.argv[10]:
        launch_root = Path(sys.argv[10])
        if launch_root.resolve() not in {source_root.resolve(), workspace.resolve()}:
            report = initialize_platform(
                'codex', launch_root,
                python_executable=Path(sys.executable),
                python_path=Path(site),
                control_socket=Path('/run/scidiscovery/control.sock'),
                state_root=state_root,
                local_workspace_root=local_workspace_root,
                worker_backend=worker_backend,
                codex_config_root=launch_root / '.codex',
                runtime_plugin_configs=runtime_plugin_configs,
                dry_run=True,
            )
            if report.changed:
                raise RuntimeError('Codex launch-root profile differs from compiled catalog')
            print('Codex launch-root profile probe: pass')
PY
}

begin_install_transaction() {
    local timestamp service_home unit name skill
    local -a command units database_names
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    TRANSACTION_ROOT="${BACKUP_ROOT}/.transaction-${timestamp}-$$"
    install -d -o root -g root -m 0700 "$BACKUP_ROOT"
    service_home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    [[ -n "$service_home" && "$service_home" = /* ]] || \
        die "cannot resolve home directory for ${SERVICE_USER}"
    command=(
        "$PYTHON" "${SOURCE_ROOT}/deploy/install_transaction.py" begin
        --root "$TRANSACTION_ROOT"
        --target "site=${SITE_ROOT}"
        --target "scid-cli=/usr/local/bin/scid"
        --target "approval-secret=${CONFIG_ROOT}/approval-receipt.key"
        --target "agent-settings=${CONFIG_ROOT}/agent-settings.json"
        --target "framework-codex=${SOURCE_ROOT}/.codex"
        --target "framework-agents=${SOURCE_ROOT}/AGENTS.md"
        --target "workspace-codex=${WORKSPACE}/.codex"
        --target "workspace-agents=${WORKSPACE}/AGENTS.md"
    )
    if codex_launch_root_is_distinct; then
        command+=(
            --target "launch-codex=${CODEX_LAUNCH_ROOT}/.codex"
            --target "launch-agents=${CODEX_LAUNCH_ROOT}/AGENTS.md"
        )
    fi
    command+=(
        --target "tcad-transport-cli=/usr/local/bin/scidiscovery-tcad-transport"
    )
    if [[ "$TCAD_ENABLED" -eq 1 ]]; then
        command+=(
            --target "tcad-policy=${CONFIG_ROOT}/tcad-policy.json"
            --target "tcad-plugin=${CONFIG_ROOT}/tcad-plugin.json"
        )
    fi
    for skill in sentaurus-tcad-code; do
        command+=(
            --target "codex-skill-${skill}=${SCID_CODEX_SKILL_ROOT:-${service_home}/.codex/skills}/${skill}"
        )
    done
    units=(
        scidiscovery-control.service
        scidiscovery-worker.service
        scidiscovery-approval-ui.service
        tcad-control.service
        artifact-agent-control.service
        artifact-agent-worker.service
        artifact-agent-approval-ui.service
        tcad-artifact-execution.service
        tcad-artifact-runner.service
    )
    for unit in "${units[@]}"; do
        name="unit-${unit%.service}"
        command+=(--target "${name}=/etc/systemd/system/${unit}")
    done
    command+=(
        --target "tcad-dropin=/etc/systemd/system/tcad-control.service.d"
    )
    database_names=(
        artifact_agent runs approvals executions scheduler-bindings
    )
    for name in "${database_names[@]}"; do
        command+=(--sqlite "db-${name}=${SCID_STATE}/database/${name}.sqlite3")
    done
    if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
        command+=(--sqlite "db-tcad-submissions=${TCAD_STATE}/submissions.sqlite3")
    fi
    "${command[@]}"
    : > "${TRANSACTION_ROOT}/active-units.txt"
    : > "${TRANSACTION_ROOT}/enabled-units.txt"
    for unit in "${units[@]}"; do
        systemctl is-active --quiet "$unit" >/dev/null 2>&1 && \
            printf '%s\n' "$unit" >> "${TRANSACTION_ROOT}/active-units.txt"
        systemctl is-enabled --quiet "$unit" >/dev/null 2>&1 && \
            printf '%s\n' "$unit" >> "${TRANSACTION_ROOT}/enabled-units.txt"
    done
    ROLLBACK_ARMED=1
    trap 'rollback_install $?' ERR
    trap 'rollback_install 130' INT TERM
}

rollback_install() {
    local status="${1:-1}" unit secret
    trap - ERR INT TERM
    set +e
    ROLLBACK_ARMED=0
    for unit in \
        scidiscovery-control.service scidiscovery-worker.service \
        scidiscovery-approval-ui.service tcad-control.service
    do
        systemctl disable --now "$unit" >/dev/null 2>&1
    done
    if [[ -n "$TRANSACTION_ROOT" && -f "${TRANSACTION_ROOT}/manifest.json" ]]; then
        "$PYTHON" "${SOURCE_ROOT}/deploy/install_transaction.py" rollback \
            --root "$TRANSACTION_ROOT"
        for secret in "${CONFIG_ROOT}/approval-receipt.key"
        do
            if [[ -e "$secret" ]]; then
                if [[ -f "$secret" && ! -L "$secret" && "$(stat -c %s "$secret")" -eq 32 ]]; then
                    chown "$SERVICE_USER:$SERVICE_GROUP" "$secret"
                    chmod 0600 "$secret"
                else
                    printf 'WARNING: restored secret needs manual inspection: %s\n' \
                        "$secret" >&2
                fi
            fi
        done
        systemctl daemon-reload
        while IFS= read -r unit; do
            [[ -z "$unit" ]] || systemctl enable "$unit" >/dev/null 2>&1
        done < "${TRANSACTION_ROOT}/enabled-units.txt"
        while IFS= read -r unit; do
            [[ -z "$unit" ]] || systemctl start "$unit" >/dev/null 2>&1
        done < "${TRANSACTION_ROOT}/active-units.txt"
        printf 'Installation rolled back from transaction: %s\n' \
            "$TRANSACTION_ROOT" >&2
    fi
    [[ -z "$PACKAGE_STAGE" ]] || rm -rf "$PACKAGE_STAGE"
    exit "$status"
}

complete_install_transaction() {
    local destination
    destination="${BACKUP_ROOT}/transactions/${TRANSACTION_ROOT##*/.transaction-}"
    "$PYTHON" "${SOURCE_ROOT}/deploy/install_transaction.py" seal \
        --root "$TRANSACTION_ROOT" --destination "$destination"
    ROLLBACK_ARMED=0
    trap - ERR INT TERM
    printf 'Install transaction evidence: %s\n' "$destination"
}

ensure_agent_settings() {
    local target="${CONFIG_ROOT}/agent-settings.json"
    if [[ -e "$target" || -L "$target" ]]; then
        [[ -f "$target" && ! -L "$target" ]] || die "agent settings must be a regular non-symlink file"
        if cmp -s "$target" "${SOURCE_ROOT}/deploy/agent_settings_previous_default.json"; then
            "$PYTHON" - "$target" "${SOURCE_ROOT}/src/scidiscovery/default_agent_settings.json" <<'PYSETTINGS'
import os, stat, sys, tempfile
from pathlib import Path
target = Path(sys.argv[1])
replacement = Path(sys.argv[2]).read_bytes()
original = target.stat()
fd, staged = tempfile.mkstemp(prefix=".agent-settings-", dir=target.parent)
try:
    os.fchmod(fd, stat.S_IMODE(original.st_mode))
    os.fchown(fd, original.st_uid, original.st_gid)
    with os.fdopen(fd, "wb") as stream:
        stream.write(replacement)
    os.replace(staged, target)
except BaseException:
    os.unlink(staged)
    raise
PYSETTINGS
        fi
        return 0
    fi
    "$PYTHON" - "$target" "${SOURCE_ROOT}/src/scidiscovery/default_agent_settings.json" <<'PYSETTINGS'
import os, sys
with open(sys.argv[2], encoding="utf-8") as source:
    contents = source.read()
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.write(contents)
PYSETTINGS
    chown root:"$SERVICE_GROUP" "$target"
}

install_all() {
    require_root
    printf '[1/6] Validating source and selected base Python...\n'
    validate_source
    validate_base_python
    validate_figure_dependencies
    printf '[2/6] Building and validating local application packages...\n'
    install_packages
    begin_install_transaction
    printf '[3/6] Retiring the previous service deployment...\n'
    retire_old_deployment
    retire_inactive_tcad_surfaces
    printf '[4/6] Installing state, policy, service, and platform configuration...\n'
    activate_packages
    install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0750 "$SCID_STATE"
    create_local_workspace_root
    create_instance_archive_root
    if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
        install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0750 "$TCAD_STATE"
    fi
    normalize_database_ownership
    install -d -o root -g "$SERVICE_GROUP" -m 0750 "$CONFIG_ROOT"
    ensure_secret "${CONFIG_ROOT}/approval-receipt.key"
    ensure_agent_settings
    if [[ "$TCAD_ENABLED" -eq 1 ]]; then
        configure_tcad_runtime
    fi
    install_units
    configure_platform
    printf '[5/6] Starting services...\n'
    systemctl enable --now \
        scidiscovery-control.service \
        scidiscovery-approval-ui.service
    if [[ "$TCAD_LOCAL_SERVICE" -eq 1 ]]; then
        systemctl enable --now tcad-control.service
    else
        systemctl disable --now tcad-control.service >/dev/null 2>&1 || true
    fi
    printf '[6/6] Verifying installed services and MCP interfaces...\n'
    verify_installation
    complete_install_transaction
    printf '%s\n' \
        'Clean SciDiscovery deployment: pass' \
        "Approval UI: http://127.0.0.1:${APPROVAL_PORT}" \
        "$([[ "$TCAD_ENABLED" -eq 0 ]] && printf 'No domain runtime selected.' || ([[ -n "$TCAD_COMMAND_CONFIG" ]] && printf 'External TCAD transport configured.' || printf 'Local TCAD smoke profile configured.'))" \
        "Restart Codex so the SciDiscovery MCP definition and role files reload."
}

status() {
    systemctl --no-pager --full status \
        scidiscovery-control.service \
        scidiscovery-approval-ui.service \
        tcad-control.service || true
    for socket in "$CONTROL_SOCKET" "$TCAD_SOCKET"; do
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

main() {
    case "${1:---dry-run}" in
        --dry-run) require_sources; validate_source; validate_base_python; validate_figure_dependencies; preview ;;
        install) require_sources; install_all ;;
        status) status ;;
        uninstall) uninstall_services ;;
        *) die "usage: $0 [--dry-run|install|status|uninstall]" ;;
    esac
}

[[ "${BASH_SOURCE[0]}" != "$0" ]] || main "$@"
