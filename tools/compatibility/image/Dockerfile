FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

ENV APM_NO_MODIFY_PATH=1

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates curl git \
    && curl --fail --silent --show-error --location https://aka.ms/apm-unix \
        --output /tmp/apm-install.sh \
    && sh /tmp/apm-install.sh --prefix /usr/local @v0.31.0 \
    && rm /tmp/apm-install.sh \
    && chmod 755 /usr/local/lib/apm \
    && apm --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
