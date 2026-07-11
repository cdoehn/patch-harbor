# Docker integration tests

The Docker integration tests are deliberately separate from the normal test
suite. They run only when explicitly requested.

## What each container run does

For the selected Ubuntu base image, the integration Dockerfile:

1. installs the minimal Python, Git, build, ZIP, and test tooling;
2. installs declared test or development dependency groups when present;
3. builds the PatchHarbor wheel with `python -m build`;
4. installs the built wheel and validates dependencies with `pip check`;
5. runs the complete `tests` directory when the container starts.

The same Dockerfile supports Ubuntu 24.04 and Ubuntu 26.04 through the
`UBUNTU_VERSION` build argument.

## Local execution

Run both supported environments:

    ./scripts/run_docker_integration_tests.sh

Run only one environment:

    ./scripts/run_docker_integration_tests.sh 24.04
    ./scripts/run_docker_integration_tests.sh 26.04

The normal local test command and normal CI are not changed by this feature.

## GitHub Actions

The workflow `.github/workflows/docker-integration-tests.yml` uses only the
`workflow_dispatch` trigger. GitHub requires a manually dispatched workflow
to exist on the repository's default branch. Until this commit is merged there,
run the Docker integration tests locally. Afterwards, start the workflow from
the Actions tab or with:

    gh workflow run docker-integration-tests.yml

When the workflow already exists on the default branch, a specific test ref can
also be selected explicitly:

    gh workflow run docker-integration-tests.yml --ref integrationstests

Each Ubuntu version runs as an independent matrix job, so GitHub can execute
them in parallel and report failures separately.
