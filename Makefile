PYTHON_VERSIONS:=3.13

export PYTHON_VERSIONS

.PHONY: test docs bash rebuild

build: Dockerfile docker-compose.yml
	@docker compose build app

rebuild:
	docker compose build --no-cache --progress=plain

bash: build
	@docker compose run --rm app bash

test_setup:
	./scripts/test-setup.sh

test: clean test_setup
	./scripts/run-tests.sh

black:
	@docker compose run --rm app black .

docs:
	cd docs && SETTINGS_MODULE=tests.settings make html

coverage_report: test
	@coverage html && echo 'Please open "htmlcov/index.html" in a browser.'

pip-compile:
	# need to run outside docker, script would re-execute once for every python version
	./scripts/pip-compile.sh

proto_compile:
	@docker compose run --rm app ./scripts/proto-compile.sh

release_setup: clean
	git clean -ffdx -e .idea

release: release_setup
	@docker compose run --rm app ./scripts/release.sh

clean:
	rm -rf usr/ etc/ *.deb build dist docs/_build
	find . -name "*.pyc" -delete
