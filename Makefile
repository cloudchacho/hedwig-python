PYTHON_VERSIONS:=3.9.14 3.10.8 3.11.11 3.12.9 3.13.2

export PYTHON_VERSIONS

.PHONY: test docs bash rebuild

build: Dockerfile
	docker-compose build app

rebuild:
	docker-compose build --no-cache --progress=plain

bash: build
	docker-compose run --rm app bash

test_setup:
	./scripts/test-setup.sh

test: clean test_setup
	./scripts/run-tests.sh

docs:
	cd docs && SETTINGS_MODULE=tests.settings make html

coverage_report: test
	@coverage html && echo 'Please open "htmlcov/index.html" in a browser.'

pip-compile:
	docker run -it --rm -v $(PWD):/app -e PYTHON_VERSIONS='${PYTHON_VERSIONS}' hedwig-python ./scripts/pip-compile.sh

proto_compile:
	[ -d /usr/local/lib/protobuf/include/hedwig ] || (echo "Ensure github.com/cloudchacho/hedwig is cloned at /usr/local/lib/protobuf/include/hedwig/"; exit 2)
	protoc -I/usr/local/lib/protobuf/include -I. --python_out=. --mypy_out=. /usr/local/lib/protobuf/include/hedwig/protobuf/container.proto /usr/local/lib/protobuf/include/hedwig/protobuf/options.proto
	cd tests/schemas && protoc -I/usr/local/lib/protobuf/include -I. -I../.. --python_out=protos/ --mypy_out=protos/ protobuf.proto protobuf_minor_versioned.proto protobuf_bad.proto
	cd examples && protoc -I/usr/local/lib/protobuf/include -I. -I.. --python_out=protos/ --mypy_out=protos/ schema.proto

release_setup: clean
	git clean -ffdx -e .idea

release: release_setup
	./scripts/release.sh

clean:
	rm -rf usr/ etc/ *.deb build dist docs/_build
	find . -name "*.pyc" -delete
