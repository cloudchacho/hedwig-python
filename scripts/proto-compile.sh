#!/usr/bin/env bash

set -eo pipefail

if [[ "${GITHUB_CI}" == "true" ]]; then
    echo "Running in CI, aborting"
    exit 1
fi

[ -d /usr/local/lib/protobuf/include/hedwig ] || (echo "Ensure github.com/cloudchacho/hedwig is cloned at /usr/local/lib/protobuf/include/hedwig/"; exit 2)
protoc -I/usr/local/lib/protobuf/include -I. --python_out=. --mypy_out=. /usr/local/lib/protobuf/include/hedwig/protobuf/container.proto /usr/local/lib/protobuf/include/hedwig/protobuf/options.proto
cd tests/schemas && protoc -I/usr/local/lib/protobuf/include -I. -I../.. --python_out=protos/ --mypy_out=protos/ protobuf.proto protobuf_minor_versioned.proto protobuf_bad.proto
cd examples && protoc -I/usr/local/lib/protobuf/include -I. -I.. --python_out=protos/ --mypy_out=protos/ schema.proto
