#!/usr/bin/env bash

set -eo pipefail

if [[ "${GITHUB_CI}" == "true" ]]; then
    set -x
fi

if [[ "${COMPILE_PUBLISH_REQUIREMENTS}" = "true" ]]; then
    out_file=requirements/publish.txt
    # always rebuild from scratch
    rm -f "$out_file"
    pip-compile --no-emit-index-url --no-header requirements/publish.in -o "$out_file"
fi

PYTHON_VERSION=$(python --version | cut -f2 -d' ')
python_major_version=$(echo "${PYTHON_VERSION}" | cut -f1 -d'.')
python_minor_version=$(echo "${PYTHON_VERSION}" | cut -f2 -d'.')
suffix="${python_major_version}.${python_minor_version}"
out_file=requirements/dev-${suffix}.txt

# always rebuild from scratch
rm -f "$out_file"

pip-compile --no-emit-index-url --no-header requirements/dev.in -o "$out_file"

# remove "-e ." line - it's expanded to full path by pip-compile
# which is most likely a developer's home directory
tail -n +3 "$out_file" > /tmp/tmp.txt
mv /tmp/tmp.txt "$out_file"
