#!/bin/bash

set -ex

if [[ "${GITHUB_CI}" == "true" ]]; then
    pip install -U pip wheel
    python_version=$(python --version | cut -f2 -d' ')
    python_major_version=$(echo ${python_version} | cut -f1 -d'.')
    python_minor_version=$(echo ${python_version} | cut -f2 -d'.')
    pip install -r requirements/dev-${python_major_version}.${python_minor_version}.txt
    pip install -q -e .
fi

if [[ "${ISOLATED_BACKEND_TEST}" == "google" ]]; then
    pip uninstall --yes google-cloud-pubsub
elif [[ "${ISOLATED_BACKEND_TEST}" == "aws" ]]; then
    pip uninstall --yes boto3
fi
