ARG SC_PYTHON_VERSION=3.13

FROM python:${SC_PYTHON_VERSION}-slim-bookworm AS local

ARG SC_PYTHON_VERSION=3.13

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements/dev-${SC_PYTHON_VERSION}.txt /app/requirements/dev-${SC_PYTHON_VERSION}.txt
RUN pip3 install -r /app/requirements/dev-${SC_PYTHON_VERSION}.txt

WORKDIR /app
