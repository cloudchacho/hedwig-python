#!/usr/bin/env bash

set -eo pipefail

if [[ "${GITHUB_CI}" == "true" ]]; then
    set -x
fi

pip install -e .
pushd docs
SETTINGS_MODULE=tests.settings make html
popd
