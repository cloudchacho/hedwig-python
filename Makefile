PYTHON_VERSIONS:=3.6,3.6-dev,3.7

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

release_setup: clean
	git clean -ffdx -e .idea

release: release_setup
	./scripts/release.sh

clean:
	rm -rf usr/ etc/ *.deb build dist docs/_build
	find . -name "*.pyc" -delete
