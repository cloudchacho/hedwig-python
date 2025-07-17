ARG SC_PYTHON_VERSION=3.13

FROM python:${SC_PYTHON_VERSION}-slim-bookworm AS local

# since ARG is scoped to a stage, we need to define it again here
# to be able to use in the COPY command below.
ARG SC_PYTHON_VERSION=3.13
ARG PROTOBUF_VERSION=31.1

RUN set -e; \
    buildDeps=' \
        # to fetch protoc \
        wget \
        # to compile protoc \
        unzip \
        # to clone repo \
        git \
    '; \
    runtimeDeps=' \
    '; \
    apt-get update; \
    apt-get install -y --no-install-recommends $buildDeps $runtimeDeps; \
    rm -rf /var/lib/apt/lists/*; \
    wget -O /tmp/protoc-${PROTOBUF_VERSION}-linux-x86_64.zip https://github.com/protocolbuffers/protobuf/releases/download/v$PROTOBUF_VERSION/protoc-${PROTOBUF_VERSION}-linux-x86_64.zip; \
    unzip /tmp/protoc-${PROTOBUF_VERSION}-linux-x86_64.zip -d /usr/local; \
    rm /tmp/protoc-${PROTOBUF_VERSION}-linux-x86_64.zip; \
    git clone https://github.com/cloudchacho/hedwig /usr/local/include/hedwig; \
    apt-get purge -y --auto-remove $buildDeps;

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    vim;

COPY requirements/dev-${SC_PYTHON_VERSION}.txt /app/requirements/dev-${SC_PYTHON_VERSION}.txt
RUN pip3 install -r /app/requirements/dev-${SC_PYTHON_VERSION}.txt

WORKDIR /app
