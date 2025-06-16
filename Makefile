PYTHON_VERSIONS:=3.9 3.10 3.11 3.12 3.13

export PYTHON_VERSIONS

.PHONY: test docs bash rebuild

build: Dockerfile docker-compose.yml
	@docker compose build app

rebuild:
	docker compose build --no-cache --progress=plain

bash: build
	@docker compose run --rm app bash

test: clean
	@docker compose run --rm \
	    -e GITHUB_CI=${GITHUB_CI} \
	    -e ISOLATED_BACKEND_TEST=${ISOLATED_BACKEND_TEST} \
	    -e ISOLATED_INSTRUMENTATION_TEST=${ISOLATED_INSTRUMENTATION_TEST} \
	    -e ISOLATED_VALIDATOR_TEST=${ISOLATED_VALIDATOR_TEST} \
	    app ./scripts/run-tests.sh

black:
	@docker compose run --rm app black .

docs:
	@docker compose run --rm -e GITHUB_CI=${GITHUB_CI} app ./scripts/make-docs.sh

pip-compile-all-versions:
	# need to run outside docker, script would call ./scripts/pip-compile.sh for every python version
	./scripts/pip-compile-all-versions.sh

pip-compile:
	@docker compose run --rm \
	    -e COMPILE_PUBLISH_REQUIREMENTS=${COMPILE_PUBLISH_REQUIREMENTS}
	    -e GITHUB_CI=${GITHUB_CI} \
	    app ./scripts/pip-compile.sh

proto_compile: build
	@docker compose run --rm -e GITHUB_CI=${GITHUB_CI} app bash -c ./scripts/proto-compile.sh

release_setup: clean
	git clean -ffdx -e .idea

release: release_setup
	./scripts/release.sh

clean:
	rm -rf usr/ etc/ *.deb build dist docs/_build
	find . -name "*.pyc" -delete
