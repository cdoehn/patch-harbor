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

for command_name in docker timeout; do
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
build_timeout_seconds="${PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS:-1200}"
run_timeout_seconds="${PATCHHARBOR_DOCKER_RUN_TIMEOUT_SECONDS:-900}"
test_timeout_seconds="${PATCHHARBOR_TEST_TIMEOUT_SECONDS:-120}"

printf 'Building PatchHarbor integration image for Ubuntu %s ...\n' "$ubuntu_version"
timeout --foreground "${build_timeout_seconds}s" \
    docker build \
        --file "$dockerfile" \
        --build-arg "UBUNTU_VERSION=$ubuntu_version" \
        --tag "$image_tag" \
        "$repository_root"

printf 'Running PatchHarbor tests on Ubuntu %s ...\n' "$ubuntu_version"
timeout --foreground "${run_timeout_seconds}s" \
    docker run --rm --init "$image_tag" \
        python -m pytest -q --timeout="$test_timeout_seconds" tests
