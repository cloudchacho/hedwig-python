#!/usr/bin/env bash

set -e

options="-v -s --strict --cov=hedwig"

if [ -z "${target}" ]; then
    target="tests"
fi

options="${target} ${options}"

mypy hedwig

python3 -bb -m pytest ${options}

flake8
