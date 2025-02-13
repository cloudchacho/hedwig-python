#!/usr/bin/env bash

set -eo pipefail

if [[ "${GITHUB_CI}" == "true" ]]; then
    set -x
fi

if [[ "${GITHUB_CI}" != "true" ]] && [[ "${INSIDE_DOCKER}" != "true" ]]; then
    docker compose run --rm -e INSIDE_DOCKER=true app ./scripts/run-tests.sh
    exit $? # exit with the exit code of the docker compose command
fi

options="-v -s --strict --cov=hedwig --cov-report html --cov-report term"

if [ -z "${target}" ]; then
    target="tests"
fi

options="${target} ${options}"

mypy hedwig

# make sure hedwig can be imported without SETTINGS_MODULE set
python3 -c 'import hedwig'

python3 -b -m pytest -p no:hedwig -p no:authedwig ${options}

black --skip-string-normalization --line-length=120 --check .

flake8

pip install -e .
make docs
