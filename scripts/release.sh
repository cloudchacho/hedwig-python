#!/usr/bin/env bash

set -ex

exit_cleanup() {
    git reset --hard upstream/master
    git checkout upstream/master
    git branch -D new_master
}

err_cleanup() {
    git fetch upstream

    if [[ -n "${released_version}" ]]; then
        git tag -d ${released_version}
        git push upstream :${released_version} || true
    fi
}

trap err_cleanup ERR

trap exit_cleanup EXIT

if [[ -z "${PART}" ]]; then
    echo "Unspecified PART, can't proceed"
    exit 1
fi

git fetch upstream
git checkout upstream/master
git reset --hard upstream/master

pip install -U bumpversion

# go to a branch so we can ref it
git checkout -b new_master

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

git push upstream new_master:master --tags

git checkout master
