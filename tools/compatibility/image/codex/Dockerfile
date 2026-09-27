ARG BASE_IMAGE=compatibility-base:local
FROM ${BASE_IMAGE}

ARG CODEX_VERSION=0.155.1
ARG CODEX_TARGET=x86_64-unknown-linux-musl
ARG CODEX_SHA256=a65b895c6ac1a73629bbe4b864640c86133e94a43b4d67b3103044e1a306d5a2

RUN set -eux \
    && test "$CODEX_VERSION" = "0.155.1" \
    && test "$CODEX_TARGET" = "x86_64-unknown-linux-musl" \
    && test "$CODEX_SHA256" = "a65b895c6ac1a73629bbe4b864640c86133e94a43b4d67b3103044e1a306d5a2" \
    && archive="/tmp/codex-package-${CODEX_TARGET}.tar.gz" \
    && url="https://releases.openai.com/codex/releases/${CODEX_VERSION}/codex-package-${CODEX_TARGET}.tar.gz" \
    && curl --fail --silent --show-error --location --retry 3 --connect-timeout 10 "$url" --output "$archive" \
    && printf '%s  %s\n' "$CODEX_SHA256" "$archive" | sha256sum --check --strict \
    && install_root="/usr/local/lib/codex/${CODEX_VERSION}-${CODEX_TARGET}" \
    && mkdir -p "$install_root" \
    && tar --extract --file "$archive" --gzip --directory "$install_root" \
    && chmod 0755 \
        "$install_root/bin/codex" \
        "$install_root/bin/codex-code-mode-host" \
        "$install_root/codex-path/rg" \
        "$install_root/codex-resources/bwrap" \
    && ln -s "$install_root" /usr/local/lib/codex/current \
    && ln -s /usr/local/lib/codex/current/bin/codex /usr/local/bin/codex \
    && /usr/local/bin/codex --version \
    && rm -f "$archive"

WORKDIR /workspace
