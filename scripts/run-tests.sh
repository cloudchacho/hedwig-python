#!/usr/bin/env bash

set -e

options="-v -s --strict"

if [ -z "${target}" ]; then
    target="tests"
fi

options="${target} ${options}"

python3 -bb -m pytest ${options}

flake8
