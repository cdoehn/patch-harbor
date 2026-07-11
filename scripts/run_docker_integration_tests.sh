#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/run_docker_integration_tests.sh [24.04|26.04]...

With no arguments, both supported Ubuntu versions are built and tested.
Pass one version to run only that container integration test.
USAGE
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

command -v docker >/dev/null 2>&1 || {
  printf 'ERROR: docker is not installed or not in PATH.\n' >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  printf 'ERROR: the Docker daemon is not available.\n' >&2
  exit 1
}

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_root"

versions=("$@")
if (( ${#versions[@]} == 0 )); then
  versions=("24.04" "26.04")
fi

for version in "${versions[@]}"; do
  case "$version" in
    24.04|26.04) ;;
    *)
      printf 'ERROR: unsupported Ubuntu version: %s\n' "$version" >&2
      usage >&2
      exit 2
      ;;
  esac

done

for version in "${versions[@]}"; do
  image_tag="patchharbor-integration:ubuntu-${version//./-}"

  printf '\n== Build PatchHarbor on Ubuntu %s ==\n' "$version"
  docker build \
    --file docker/Dockerfile.integration \
    --build-arg "UBUNTU_VERSION=$version" \
    --tag "$image_tag" \
    .

  printf '\n== Run PatchHarbor tests on Ubuntu %s ==\n' "$version"
  docker run --rm "$image_tag"
done

printf '\nDocker integration tests passed for: %s\n' "${versions[*]}"
