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

python3 -bb -m pytest -p no:hedwig -p no:authedwig ${options}

black --skip-string-normalization --skip-numeric-underscore-normalization --line-length=120 --check .

flake8

pip install -e .
make docs
