ARG BASE_IMAGE=compatibility-base:local
FROM ${BASE_IMAGE} AS base

FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b AS uv

FROM base

ARG HERMES_VERSION=0.21.3
ARG HERMES_TAG=v2026.9.14
ARG HERMES_COMMIT=345cd2b057a452236de401d3534b8502a7465e8d
ARG HERMES_SOURCE_SHA256=ed17fdd4423bfc7faee02399a866d5ee30a04a09523da6ea39d794f664526e55

ENV HERMES_HOME=/tmp/hermes-home \
    PATH=/opt/hermes/venv/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=uv /usr/local/bin/uv /usr/local/bin/uv
COPY --from=uv /usr/local/bin/uvx /usr/local/bin/uvx

RUN set -eux \
    && test "$HERMES_VERSION" = "0.21.3" \
    && test "$HERMES_TAG" = "v2026.9.14" \
    && test "$HERMES_COMMIT" = "345cd2b057a452236de401d3534b8502a7465e8d" \
    && test "$HERMES_SOURCE_SHA256" = "ed17fdd4423bfc7faee02399a866d5ee30a04a09523da6ea39d794f664526e55" \
    && mkdir -p /opt/hermes/source /opt/hermes/venv \
    && curl --fail --silent --show-error --location --retry 3 --connect-timeout 15 \
        "https://github.com/NousResearch/hermes-agent/archive/${HERMES_COMMIT}.tar.gz" \
        --output /tmp/hermes-source.tar.gz \
    && printf '%s  %s\n' "$HERMES_SOURCE_SHA256" /tmp/hermes-source.tar.gz \
        | sha256sum --check --strict \
    && tar --extract --file /tmp/hermes-source.tar.gz --gzip \
        --strip-components=1 --directory /opt/hermes/source \
    && test "$(git -C /opt/hermes/source rev-parse --verify HEAD 2>/dev/null || true)" = "" \
    && test "$(sed -n 's/^version = "\([^"]*\)"$/\1/p' /opt/hermes/source/pyproject.toml | head -1)" = "$HERMES_VERSION" \
    && cd /opt/hermes/source \
    && UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/hermes/venv \
        uv sync --frozen --no-dev --python /usr/local/bin/python3.13 \
    && rm -f /tmp/hermes-source.tar.gz \
    && rm -rf /root/.cache/uv \
    && hermes --version \
    && python --version \
    && git --version \
    && apm --version \
    && find /opt/hermes -type f \( -name 'auth.json' -o -name '.env' -o -name 'config.yaml' \) -print -quit \
        | (! read unexpected) \
    && test ! -e /opt/hermes/skills \
    && test -f /opt/hermes/source/pyproject.toml \
    && test ! -e /opt/hermes/source/.git

WORKDIR /workspace

CMD ["hermes"]
