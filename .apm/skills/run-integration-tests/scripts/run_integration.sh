#!/usr/bin/env bash

set -euo pipefail

MIN_AVAILABLE_GIB="${INTEGRATION_MIN_AVAILABLE_GIB:-10}"
MAX_LOAD_PER_CPU="${INTEGRATION_MAX_LOAD_PER_CPU:-0.75}"
STAGGER_SECONDS="${INTEGRATION_STAGGER_SECONDS:-120}"

MODULE=""
TOX_ENV=""
TOX_WORKDIR=""
ALLOW_UNVERIFIED_TARGET=false
FORCE_RESOURCES=false
PYTEST_ARGS=()
RUN_FILE=""
LOCK_FD=9

usage() {
    cat <<'EOF'
Usage: run_integration.sh <module> [options] [-- <extra pytest args>]

Run one integration test module through a verified tox environment.

Arguments:
  <module>                    Module path or name, such as
                              tests/integration/test_charm.py or charm.

Options:
  --env <name>                Tox environment. If omitted, try
                              integration-<normalized-module-name>.
  --workdir <path>            Explicit tox work directory.
  --min-available-gib <GiB>   Memory required for an additional run (default: 10).
  --max-load-per-cpu <ratio>  Maximum 1-minute load / logical CPUs (default: 0.75).
  --stagger-seconds <seconds> Minimum interval between concurrent starts (default: 120).
  --allow-unverified-target   Run when tox configuration does not visibly name the module.
  --force-resources           Bypass memory, CPU, and stagger checks.
  -h, --help                  Show this help.

Repository-specific pytest arguments belong after --. This helper does not build artifacts,
choose images, manage Juju models, or infer fixture options.
EOF
}

log() {
    printf '\n==> %s\n' "$*"
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

temporarily_unavailable() {
    printf 'Resource gate declined this concurrent run: %s\n' "$*" >&2
    exit 75
}

require_value() {
    [[ $# -ge 2 && -n "$2" ]] || die "$1 requires a value."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            require_value "$@"
            TOX_ENV="$2"
            shift 2
            ;;
        --workdir)
            require_value "$@"
            TOX_WORKDIR="$2"
            shift 2
            ;;
        --min-available-gib)
            require_value "$@"
            MIN_AVAILABLE_GIB="$2"
            shift 2
            ;;
        --max-load-per-cpu)
            require_value "$@"
            MAX_LOAD_PER_CPU="$2"
            shift 2
            ;;
        --stagger-seconds)
            require_value "$@"
            STAGGER_SECONDS="$2"
            shift 2
            ;;
        --allow-unverified-target)
            ALLOW_UNVERIFIED_TARGET=true
            shift
            ;;
        --force-resources)
            FORCE_RESOURCES=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            PYTEST_ARGS+=("$@")
            break
            ;;
        -*)
            die "Unknown option: $1"
            ;;
        *)
            [[ -z "$MODULE" ]] || die "Only one module may be run by each process."
            MODULE="$1"
            shift
            ;;
    esac
done

[[ -n "$MODULE" ]] || {
    usage >&2
    exit 1
}

for value in "$MIN_AVAILABLE_GIB" "$MAX_LOAD_PER_CPU"; do
    [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] \
        || die "Resource thresholds must be non-negative numbers."
done
[[ "$STAGGER_SECONDS" =~ ^[0-9]+$ ]] \
    || die "--stagger-seconds must be a non-negative integer."

command -v git >/dev/null || die "git not found."
command -v tox >/dev/null || die "tox not found."

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
    || die "Run this command from inside the target repository."
cd "$REPO_ROOT"

MODULE_BASENAME="$(basename "$MODULE")"
MODULE_BASENAME="${MODULE_BASENAME%.py}"
MODULE_BASENAME="${MODULE_BASENAME#test_}"
TEST_FILE="test_${MODULE_BASENAME}.py"

if [[ "$MODULE" == */* ]]; then
    TEST_PATH="${MODULE%.py}.py"
else
    TEST_PATH="tests/integration/${TEST_FILE}"
fi
[[ -f "$TEST_PATH" ]] || die "No such integration module: ${TEST_PATH}"

log "Discovering tox environments"
TOX_LIST="$(tox list)" \
    || die "Could not list tox environments. Inspect tox.ini and repository instructions."

env_exists() {
    awk -v wanted="$1" '$1 == wanted { found = 1 } END { exit !found }' <<<"$TOX_LIST"
}

if [[ -z "$TOX_ENV" ]]; then
    CANDIDATE_ENV="integration-${MODULE_BASENAME//_/-}"
    env_exists "$CANDIDATE_ENV" \
        || die "No inferred tox environment '${CANDIDATE_ENV}'. Available integration environments:
$(awk '$1 ~ /^integration([_-]|$)/ { print "  " $1 }' <<<"$TOX_LIST")
Inspect tox.ini and pass the verified environment with --env."
    TOX_ENV="$CANDIDATE_ENV"
elif ! env_exists "$TOX_ENV"; then
    die "tox environment '${TOX_ENV}' does not exist. Run 'tox list' and inspect tox.ini."
fi

TOX_COMMANDS="$(tox c -e "$TOX_ENV" -k commands 2>/dev/null)" \
    || die "Could not inspect commands for tox environment '${TOX_ENV}'."
if [[ "$ALLOW_UNVERIFIED_TARGET" == false ]] \
    && ! grep -Fq "$TEST_FILE" <<<"$TOX_COMMANDS"; then
    die "tox environment '${TOX_ENV}' does not visibly target '${TEST_FILE}'. Refusing a possible full-suite run.
Inspect 'tox c -e ${TOX_ENV} -k commands'. Use --allow-unverified-target only if repository source proves the indirect command selects this module."
fi

# Coordinate only runs started through this helper. The first run is always admitted; resource
# checks apply when another registered run is active.
command -v flock >/dev/null || die "flock not found; cannot coordinate concurrent runs safely."
RUNTIME_BASE="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
GATE_DIR="${RUNTIME_BASE}/copilot-integration-${UID:-$(id -u)}"
mkdir -p "$GATE_DIR"
exec 9>"$GATE_DIR/lock"
flock "$LOCK_FD"

shopt -s nullglob
ACTIVE_RUNS=0
for pid_file in "$GATE_DIR"/run-*.pid; do
    read -r run_pid < "$pid_file" || run_pid=""
    if [[ "$run_pid" =~ ^[0-9]+$ ]] \
        && kill -0 "$run_pid" 2>/dev/null \
        && [[ -r "/proc/${run_pid}/cmdline" ]] \
        && grep -aq 'run_integration.sh' "/proc/${run_pid}/cmdline"; then
        ((ACTIVE_RUNS += 1))
    else
        rm -f "$pid_file"
    fi
done

if (( ACTIVE_RUNS > 0 )) && [[ "$FORCE_RESOURCES" == false ]]; then
    NOW="$(date +%s)"
    LAST_START=0
    [[ -f "$GATE_DIR/last-start" ]] && read -r LAST_START < "$GATE_DIR/last-start"
    if [[ "$LAST_START" =~ ^[0-9]+$ ]] && (( NOW - LAST_START < STAGGER_SECONDS )); then
        REMAINING=$((STAGGER_SECONDS - (NOW - LAST_START)))
        flock -u "$LOCK_FD"
        temporarily_unavailable "wait ${REMAINING}s before considering another module."
    fi

    if [[ -r /proc/meminfo ]]; then
        AVAILABLE_KIB="$(awk '/^MemAvailable:/ { print $2; exit }' /proc/meminfo)"
        REQUIRED_KIB="$(awk -v gib="$MIN_AVAILABLE_GIB" \
            'BEGIN { printf "%.0f", gib * 1024 * 1024 }')"
        if (( AVAILABLE_KIB < REQUIRED_KIB )); then
            AVAILABLE_GIB="$(awk -v kib="$AVAILABLE_KIB" \
                'BEGIN { printf "%.1f", kib / 1024 / 1024 }')"
            flock -u "$LOCK_FD"
            temporarily_unavailable \
                "${AVAILABLE_GIB} GiB available; ${MIN_AVAILABLE_GIB} GiB required."
        fi
    else
        flock -u "$LOCK_FD"
        temporarily_unavailable "cannot read MemAvailable from /proc/meminfo."
    fi

    if [[ -r /proc/loadavg ]] && command -v nproc >/dev/null; then
        read -r LOAD_ONE _ < /proc/loadavg
        CPU_COUNT="$(nproc)"
        if ! awk -v load="$LOAD_ONE" -v cpus="$CPU_COUNT" -v max="$MAX_LOAD_PER_CPU" \
            'BEGIN { exit !((load / cpus) <= max) }'; then
            LOAD_PER_CPU="$(awk -v load="$LOAD_ONE" -v cpus="$CPU_COUNT" \
                'BEGIN { printf "%.2f", load / cpus }')"
            flock -u "$LOCK_FD"
            temporarily_unavailable \
                "1-minute load per CPU is ${LOAD_PER_CPU}; maximum is ${MAX_LOAD_PER_CPU}."
        fi
    else
        flock -u "$LOCK_FD"
        temporarily_unavailable "cannot determine normalized CPU load."
    fi
fi

RUN_FILE="$GATE_DIR/run-$$.pid"
printf '%s\n' "$$" > "$RUN_FILE"
date +%s > "$GATE_DIR/last-start"
flock -u "$LOCK_FD"

cleanup_registration() {
    flock "$LOCK_FD"
    rm -f "$RUN_FILE"
    flock -u "$LOCK_FD"
}
trap cleanup_registration EXIT

TOX_ARGS=(-e "$TOX_ENV")
if [[ -n "$TOX_WORKDIR" ]]; then
    mkdir -p "$TOX_WORKDIR"
    TOX_ARGS+=(--workdir "$TOX_WORKDIR")
fi

printf 'repository=%s\nmodule=%s\ntox-env=%s\n' "$REPO_ROOT" "$TEST_PATH" "$TOX_ENV"
printf 'active-helper-runs-before-start=%s\n' "$ACTIVE_RUNS"
[[ -z "$TOX_WORKDIR" ]] || printf 'tox-workdir=%s\n' "$TOX_WORKDIR"

log "Running ${TEST_FILE}"
tox "${TOX_ARGS[@]}" -- "${PYTEST_ARGS[@]}"
