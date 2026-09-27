# Образ стенда с Codex CLI

Это отдельный внутренний образ для испытательного стенда. Он наследуется от
базового образа из соседнего каталога и добавляет только официальный
дистрибутив Codex CLI. Базовый образ остаётся без Codex и других агентских
оснасток.

В образ закреплены:

- Codex CLI `0.155.1`, стабильный официальный выпуск OpenAI `rust-v0.155.1`
- архитектура `x86_64-unknown-linux-musl`
- архив `codex-package-x86_64-unknown-linux-musl.tar.gz`
- источник: `https://releases.openai.com/codex/releases/0.155.1/codex-package-x86_64-unknown-linux-musl.tar.gz`
- SHA-256 архива: `a65b895c6ac1a73629bbe4b864640c86133e94a43b4d67b3103044e1a306d5a2`

Архив проверяется до распаковки. В образ не включаются репозиторий,
коллекция навыков, `auth.json`, API-ключи и пользовательские настройки Codex.
При запуске не используется автоматическое обновление.

## Сборка

Выполните команды из корня репозитория. Сначала соберите базовый образ и
присвойте ему локальное имя, затем передайте это имя через build argument:

```bash
BASE_IMAGE_TAG=compatibility-base:local
CODEX_IMAGE_TAG=compatibility-codex:local

docker build \
  --tag "$BASE_IMAGE_TAG" \
  --file tools/compatibility/image/Dockerfile \
  tools/compatibility/image

docker build \
  --build-arg BASE_IMAGE="$BASE_IMAGE_TAG" \
  --tag "$CODEX_IMAGE_TAG" \
  tools/compatibility/image/codex

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$CODEX_IMAGE_TAG")"
printf 'Образ Codex: %s\n' "$IMAGE_ID"
```

`x86_64-unknown-linux-musl` соответствует образу `linux/amd64`. Для другой
архитектуры нужен отдельный проверенный официальный архив и отдельная запись
его SHA-256.

## Проверка

Команды ниже используют ID собранного образа. Они работают без сети,
с read-only rootfs, без новых привилегий, от UID/GID текущего пользователя и
с отдельными временными каталогами `/tmp` и `/home/sandbox`. Каждая команда
ограничена тайм-аутом 30 секунд.

```bash
TEST_UID="$(id -u)"
TEST_GID="$(id -g)"

run_isolated() {
  timeout --signal=KILL 30s docker run --rm \
    --pull=never \
    --network none \
    --read-only \
    --security-opt no-new-privileges:true \
    --user "$TEST_UID:$TEST_GID" \
    --workdir /workspace \
    --memory 512m \
    --cpus 1.0 \
    --pids-limit 64 \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs "/home/sandbox:rw,noexec,nosuid,size=64m,uid=$TEST_UID,gid=$TEST_GID,mode=700" \
    --env HOME=/home/sandbox \
    "$IMAGE_ID" \
    "$@"
}

run_isolated codex --version
run_isolated codex --help
run_isolated codex exec --help
run_isolated python --version
run_isolated git --version
run_isolated apm --version
run_isolated apm --help >/dev/null
```

Подтверждён только запуск CLI и доступность Python, Git и APM в новом образе.
Авторизация, встроенная песочница при выполнении команд и применение навыков
пока не проверены.
