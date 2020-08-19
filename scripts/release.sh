#!/usr/bin/env bash

set -ex

err_cleanup() {
    if [[ -n "${released_version}" ]]; then
        git tag -d ${released_version}
        git push origin :${released_version} || true
    fi
}

trap err_cleanup ERR

if [[ -z "${PART}" ]]; then
    echo "Unspecified PART, can't proceed"
    exit 1
fi

pip install -U bumpversion

# go to a branch so we can ref it
git checkout -b new_master

if [[ "${CI}" == "true" ]]; then
    git config --global user.email "actions@github"
    git config --global user.name "${GITHUB_ACTOR}"
fi

if [[ "${PART}" != "patch" ]]; then
    # Versioning assumes you're releasing patch
    bumpversion --verbose ${PART} --no-tag
fi

# release current dev version
bumpversion --verbose release

released_version=$(git tag -l --points-at HEAD)

./scripts/distribute.sh

# prep next dev version
bumpversion --verbose patch --no-tag

git push origin new_master:master --tags
