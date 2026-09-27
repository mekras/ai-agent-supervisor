# Базовый образ стенда совместимости

Это внутренний образ для механического сценария `tools/compatibility/run.py`.
Он не содержит репозиторий, коллекцию навыков, настройки пользователя,
авторизацию или секреты. Агентские оснастки в образ не устанавливаются.

Закреплено в Dockerfile:

- официальный `python:3.13.15-slim-trixie`
- digest образа: `sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b`
- APM CLI `0.31.0`, установленный официальным Unix-установщиком
- Git из Debian Trixie устанавливается без фиксации версии

Наблюдалось при проверенной сборке:

- Python `3.13.15`
- Git `2.47.3`
- APM CLI `0.31.0`

Сборку выполняйте из корня репозитория. Контекстом служит только этот каталог:

```text
IMAGE_ID="$(docker build -q -f tools/compatibility/image/Dockerfile tools/compatibility/image)"
```

Проверьте состав образа по его фактическому ID:

```text
docker run --rm --network none "$IMAGE_ID" sh -c 'python --version && git --version && apm --version && apm --help >/dev/null'
```

Для проверки существующей заглушки подготовьте временный проект и временно
скопируйте в него только её файл:

```text
TEST_PROJECT="$(mktemp -d)"
RESULTS_DIR="$(mktemp -d)"
cp evals/compatibility/edit-agents/fixture/AGENTS.md "$TEST_PROJECT/AGENTS.md"
mkdir -p "$TEST_PROJECT/tools/compatibility"
cp tools/compatibility/edit_agents_stub.py "$TEST_PROJECT/tools/compatibility/edit_agents_stub.py"
python3 tools/compatibility/run.py --project "$TEST_PROJECT" --image "$IMAGE_ID" --results-dir "$RESULTS_DIR" --timeout 30 --command python3 /workspace/tools/compatibility/edit_agents_stub.py
rm -rf "$TEST_PROJECT" "$RESULTS_DIR"
```

Запускатель сам использует `--network none`, read-only rootfs, временный
домашний каталог, произвольный UID:GID и `/workspace`, а после испытания удаляет
контейнер. Образ пока проверен только для механики стенда. Установка коллекции и
работа агентских сред ещё не проверялись.
