#!/usr/bin/env bash

set -eo pipefail
set +x

if [[ "${GITHUB_CI}" == "true" ]]; then
    echo "$0 cannot be run in CI env, use github 'pip-compile' workflow instead.";
    exit 1;
fi


# Create docker containers for each python version required and compile inside docker
if [[ -z "${PYTHON_VERSIONS}" ]]; then
    echo "Unspecified PYTHON_VERSIONS, cannot proceed";
    exit 1
fi

for PYTHON_VERSION in ${PYTHON_VERSIONS}; do
    export SC_PYTHON_VERSION="${PYTHON_VERSION}"
    docker compose build
    COMPILE_PUBLISH_REQUIREMENTS=""
    # for latest python version, compile publish requirements
    if [[ "${PYTHON_VERSION}" == "${PYTHON_VERSIONS##* }" ]]; then
        COMPILE_PUBLISH_REQUIREMENTS='-e COMPILE_PUBLISH_REQUIREMENTS=true'
    fi
    docker compose run --rm ${COMPILE_PUBLISH_REQUIREMENTS} \
        -e GITHUB_CI=${GITHUB_CI} \
        app ./scripts/pip-compile.sh
    exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        exit $exit_code
    fi
done
