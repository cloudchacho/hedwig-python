#!/bin/bash

set -eo pipefail

if [[ "${GITHUB_CI}" == "true" ]]; then
    set -x
fi

if [[ "${GITHUB_CI}" != "true" ]] && [[ "${INSIDE_DOCKER}" != "true" ]]; then
    docker-compose run --rm -e INSIDE_DOCKER=true app ./scripts/test-setup.sh
    exit $? # exit with the exit code of the docker-compose command
fi

if [[ "${GITHUB_CI}" == "true" ]]; then
    pip install -U pip wheel
    python_version=$(python --version | cut -f2 -d' ')
    python_major_version=$(echo "${python_version}" | cut -f1 -d'.')
    python_minor_version=$(echo "${python_version}" | cut -f2 -d'.')
    requirements_file="requirements/dev-${python_major_version}.${python_minor_version}.txt"
    if [[ "${python_version}" =~ "b" ]]; then
        requirements_file="requirements/dev-${python_major_version}.${python_minor_version}-dev.txt"
    fi
    pip install -r "${requirements_file}"
    pip install -q -e .
fi

if [[ "${ISOLATED_VALIDATOR_TEST}" == "protobuf" ]]; then
    pip uninstall --yes jsonschema
elif [[ "${ISOLATED_VALIDATOR_TEST}" == "jsonschema" ]]; then
    pip uninstall --yes protobuf
fi

if [[ "${ISOLATED_BACKEND_TEST}" == "google" ]]; then
    pip uninstall --yes boto3
elif [[ "${ISOLATED_BACKEND_TEST}" == "aws" ]]; then
    pip uninstall --yes google-cloud-pubsub
fi

if [[ "${ISOLATED_INSTRUMENTATION_TEST}" == "off" ]]; then
    pip uninstall --yes opentelemetry-api opentelemetry-sdk
elif [[ -n "${ISOLATED_INSTRUMENTATION_TEST}" ]]; then
    pip uninstall --yes opentelemetry-api opentelemetry-sdk
    pip install "opentelemetry-api==${ISOLATED_INSTRUMENTATION_TEST}" "opentelemetry-sdk==${ISOLATED_INSTRUMENTATION_TEST}"
fi
