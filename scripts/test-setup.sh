#!/bin/bash

set -x

if [[ "${TRAVIS}" == "true" ]]; then
    python_major_version=$(echo ${TRAVIS_PYTHON_VERSION} | cut -f1 -d'.')
    python_minor_version=$(echo ${TRAVIS_PYTHON_VERSION} | cut -f2 -d'.')
    pip install -r requirements/dev-${python_major_version}.${python_minor_version}.txt
    pip install -q -e .

    if [[ "${ISOLATED_BACKEND_TEST}" == "google" ]]; then
        pip uninstall --yes google-cloud-pubsub
    elif [[ "${ISOLATED_BACKEND_TEST}" == "aws" ]]; then
        pip uninstall --yes boto3
    fi
fi
