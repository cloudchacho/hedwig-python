#!/usr/bin/env bash

set -e

options="-v -s --strict --cov=hedwig"

if [ -z "${target}" ]; then
    target="tests"
fi

options="${target} ${options}"

mypy hedwig

# make sure hedwig can be imported without SETTINGS_MODULE set
python3 -c 'import hedwig'

python3 -bb -m pytest ${options}

flake8
