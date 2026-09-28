# Образ стенда с Hermes Agent

Это отдельный внутренний образ для испытательного стенда. Он наследуется от
базового образа из соседнего каталога и добавляет официальную CLI-установку
Hermes Agent без пользовательского состояния.

В образе закреплены:

- Hermes Agent `0.21.3`, стабильный официальный выпуск под тегом `v2026.9.14`
- исходный commit `345cd2b057a452236de401d3534b8502a7465e8d`
- архив исходников из официального репозитория `NousResearch/hermes-agent`
- SHA-256 архива: `ed17fdd4423bfc7faee02399a866d5ee30a04a09523da6ea39d794f664526e55`
- Python 3.13 из базового образа, совместимый с требованием Hermes `>=3.11,<3.14`
- базовые зависимости Hermes из `pyproject.toml` и `uv.lock`

Используется официальный образ `uv 0.11.6` и зафиксированный исходный архив. Каталог
исходников сохраняется для официальной editable-установки Hermes. Варианты
установки с `[all]` и официальный полный Dockerfile Hermes не применяются,
поскольку они добавляют браузер, Node/TUI, Computer Use, gateway и другие
необязательные компоненты. В образ не включаются репозиторий потребителя,
коллекция навыков проекта, пользовательские конфиги, авторизация или ключи.

## Сборка

Команды выполняются из корня репозитория:

```bash
BASE_IMAGE_TAG=compatibility-base:local
HERMES_IMAGE_TAG=compatibility-hermes:local

docker build \
  --tag "$BASE_IMAGE_TAG" \
  --file tools/compatibility/image/Dockerfile \
  tools/compatibility/image

docker build \
  --build-arg BASE_IMAGE="$BASE_IMAGE_TAG" \
  --tag "$HERMES_IMAGE_TAG" \
  tools/compatibility/image/hermes

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$HERMES_IMAGE_TAG")"
printf 'Образ Hermes: %s\n' "$IMAGE_ID"
```

## Немодельная проверка

Проверки выполняются без сети, с read-only rootfs, без новых привилегий, от
UID/GID текущего пользователя и с отдельным временным `HERMES_HOME`:

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
    --env HERMES_HOME=/tmp/hermes-home \
    "$IMAGE_ID" \
    "$@"
}

run_isolated hermes --version
run_isolated hermes --help
run_isolated hermes chat --help
run_isolated hermes model --help
run_isolated python --version
run_isolated git --version
run_isolated apm --version
run_isolated sh -c \
  '! find /opt/hermes -type f \( -name auth.json -o -name .env -o -name config.yaml \) -print -quit | grep -q . && test -f /opt/hermes/source/pyproject.toml && test ! -e /opt/hermes/source/.git && test ! -e /opt/hermes/skills'
```

Параметры однократного запуска и передачи задачи включают `-z` или `--oneshot`
с текстом запроса, `chat -q` или `--query`, `--query-file` и `-Q` или `--quiet`.
Выбор модели и провайдера доступен через `-m` или `--model` и `--provider`.
Однократный запуск может сохранить JSON-отчёт расхода через `--usage-file PATH`.
Сессии автоматически сохраняются в SQLite под `HERMES_HOME`, их можно
продолжить через `--resume` или `--continue`, а `sessions` показывает список.
Команда `logs` просматривает `agent.log` и `errors.log`. Эти параметры
перечислены в справке конкретной версии и не запускаются в стенде, поскольку
потребовали бы модельный запрос или пользовательскую авторизацию.
