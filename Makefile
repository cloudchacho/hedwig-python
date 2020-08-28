PYTHON_VERSIONS:=3.6.11,3.7.7,3.8.2,3.9-dev

export PYTHON_VERSIONS

.PHONY: test docs

test_setup:
	./scripts/test-setup.sh

test: clean test_setup
	./scripts/run-tests.sh

docs:
	cd docs && SETTINGS_MODULE=tests.settings make html

coverage_report: test
	@coverage html && echo 'Please open "htmlcov/index.html" in a browser.'

pip_compile:
	./scripts/pip-compile.sh

proto_compile:
	protoc -I/usr/local/lib/protobuf/include -I. --python_out=. hedwig/container.proto hedwig/options.proto
	cd tests/schemas && protoc -I/usr/local/lib/protobuf/include -I. -I../.. --python_out=protos/ protobuf.proto protobuf_bad1.proto protobuf_bad2.proto protobuf_bad3.proto
	cd examples && protoc -I/usr/local/lib/protobuf/include -I. -I.. --python_out=protos/ schema.proto

release_setup: clean
	git clean -ffdx -e .idea

release: release_setup
	./scripts/release.sh

clean:
	rm -rf usr/ etc/ *.deb build dist docs/_build
	find . -name "*.pyc" -delete
