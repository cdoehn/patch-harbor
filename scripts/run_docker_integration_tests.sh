#!/usr/bin/env bash
# PATCHHARBOR
set -Eeuo pipefail

usage() {
    printf 'Usage: %s <24.04|26.04>\n' "$(basename "$0")" >&2
}

if (( $# != 1 )); then
    usage
    exit 2
fi

ubuntu_version="$1"
case "$ubuntu_version" in
    24.04|26.04)
        ;;
    *)
        usage
        exit 2
        ;;
esac

for command_name in docker tee timeout; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'patchharbor: required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
dockerfile="$repository_root/docker/Dockerfile.integration"
[[ -f "$dockerfile" ]] || {
    printf 'patchharbor: integration Dockerfile not found: %s\n' "$dockerfile" >&2
    exit 1
}

image_tag="patchharbor-integration:ubuntu-${ubuntu_version//./-}"
build_timeout_seconds="${PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS:-2400}"
preflight_timeout_seconds="${PATCHHARBOR_DOCKER_PREFLIGHT_TIMEOUT_SECONDS:-180}"
suite_timeout_seconds="${PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS:-2400}"
test_timeout_seconds="${PATCHHARBOR_TEST_TIMEOUT_SECONDS:-120}"
test_durations="${PATCHHARBOR_TEST_DURATIONS:-20}"
default_log_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/patchharbor-docker-integration"
log_directory="${PATCHHARBOR_DOCKER_LOG_DIR:-$default_log_root/ubuntu-${ubuntu_version//./-}}"
mkdir -p -- "$log_directory"

current_stage="initialization"
current_log=""
summary_path="$log_directory/summary.txt"

write_summary() {
    local status="$1"
    local temporary_summary="$summary_path.tmp.$$"
    {
        printf 'ubuntu_version=%s\n' "$ubuntu_version"
        printf 'status=%s\n' "$status"
        printf 'stage=%s\n' "$current_stage"
        printf 'log=%s\n' "$current_log"
    } >"$temporary_summary"
    mv -f -- "$temporary_summary" "$summary_path"
}

finish() {
    local status="$?"
    trap - EXIT
    write_summary "$status"
    if (( status != 0 )); then
        printf 'PatchHarbor Docker integration failed during %s.\n' "$current_stage" >&2
        printf 'Complete diagnostics: %s\n' "$log_directory" >&2
    fi
    exit "$status"
}
trap finish EXIT

run_logged() {
    local label="$1"
    local timeout_seconds="$2"
    local log_name="$3"
    shift 3

    current_stage="$label"
    current_log="$log_directory/$log_name"
    : >"$current_log"
    printf 'Running %s on Ubuntu %s ...\n' "$label" "$ubuntu_version"

    set +e
    timeout --foreground "${timeout_seconds}s" "$@" 2>&1 | tee "$current_log"
    local pipeline_status=("${PIPESTATUS[@]}")
    set -e
    if (( pipeline_status[0] != 0 )); then
        return "${pipeline_status[0]}"
    fi
    return "${pipeline_status[1]}"
}

run_container() {
    local label="$1"
    local timeout_seconds="$2"
    local log_name="$3"
    shift 3
    run_logged "$label" "$timeout_seconds" "$log_name" \
        docker run --rm --init --network none --workdir /workspace \
        "$image_tag" "$@"
}

run_pytest_gate() {
    local label="$1"
    local log_name="$2"
    local marker_expression="$3"
    run_container "$label" "$suite_timeout_seconds" "$log_name" \
        python -m pytest -q \
        --timeout="$test_timeout_seconds" \
        --durations="$test_durations" \
        -m "$marker_expression" \
        tests
}

run_logged "image build" "$build_timeout_seconds" "00-build.log" \
    docker build \
        --progress=plain \
        --file "$dockerfile" \
        --build-arg "UBUNTU_VERSION=$ubuntu_version" \
        --tag "$image_tag" \
        "$repository_root"

run_container "environment preflight" "$preflight_timeout_seconds" \
    "10-environment-preflight.log" \
    python scripts/check_docker_integration_environment.py --require-init
run_pytest_gate \
    "core and architecture tests" \
    "20-core-and-architecture.log" \
    "not e2e and not acceptance and not platform and not packaging"
run_pytest_gate \
    "E2E and acceptance tests" \
    "30-e2e-and-acceptance.log" \
    "e2e or acceptance"
run_pytest_gate "platform tests" "40-platform.log" "platform"
run_pytest_gate "packaging tests" "50-packaging.log" "packaging"
