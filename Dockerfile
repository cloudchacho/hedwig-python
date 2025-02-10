FROM python:3.10.12-slim-bullseye AS local

# pin exact version so docker invalidates on every change of this file
RUN pip3 install pip==23.2.1

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements/dev-3.10.txt /app/requirements/dev-3.10.txt
RUN set -e; \
        buildDeps=' \
                # n/a
        '; \
        runtimeDeps=' \
                # TODO cleanup: trying to figure out container \
                protobuf-compiler \
                build-essential \
                libprotobuf-dev \
                # instead of twice? \
                vim \
                git \

         '; \
    apt-get update; \
    apt-get install -y --no-install-recommends $buildDeps $runtimeDeps; \
    rm -rf /var/lib/apt/lists/*; \
    pip3 install -r /app/requirements/dev-3.10.txt; \
    apt-get purge -y --auto-remove $buildDeps


RUN pip3 install --no-deps -r /app/requirements/dev-3.10.txt

# RUN apt-get update && apt-get install -y --no-install-recommends \
    # edit pip installed libraries
    # vim \
    # needed for publishing
    # git
    # needed for builds
    # protobuf-compiler \
    # build-essential \
    # libprotobuf-dev

WORKDIR /app
