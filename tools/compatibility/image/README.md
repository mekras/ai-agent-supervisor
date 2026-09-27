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
REPORT_PATH="$(find "$RESULTS_DIR" -name report.json -print -quit)"
printf 'Отчёт: %s\n' "$REPORT_PATH"
printf 'Diff: %s\n' "$(dirname "$REPORT_PATH")/agents.diff"
rm -rf "$TEST_PROJECT"
# Необязательно после просмотра отчёта и diff:
# rm -rf "$RESULTS_DIR"
```

Для режима Codex используйте ID отдельного образа с Codex CLI. Модель и усилие
обязательны и не имеют значений по умолчанию:

```text
CODEX_IMAGE_ID='sha256:01e0e32919da1638eb9a9f8ffc6f29773db4ed760c50ba6b6891957229847aaf'
MODEL_NAME='укажите-модель'
EFFORT_NAME='укажите-усилие'
RESULTS_DIR="$(mktemp -d)"
python3 tools/compatibility/run.py \
  --project "$TEST_PROJECT" \
  --image "$CODEX_IMAGE_ID" \
  --results-dir "$RESULTS_DIR" \
  --timeout 180 \
  --mode codex \
  --model "$MODEL_NAME" \
  --effort "$EFFORT_NAME"
```

Запускатель берёт задачу из поля `prompt` файла `scenario.json` и передаёт её
через stdin без добавления текста навыка. Внутри контейнера используется
`codex exec --json --output-last-message ... -`. Встроенная песочница Codex и
запросы разрешений отключены флагом
`--dangerously-bypass-approvals-and-sandbox`. Границей доступа остаётся
внешняя изоляция Docker: непривилегированный UID:GID, сеть `none`, read-only
rootfs, ограниченные ресурсы, временный `HOME`, без Docker socket, репозитория
разработчика и пользовательского домашнего каталога.

Рядом с `report.json` сохраняются `codex.jsonl` и отдельный
`final-answer.txt`. Для режима Codex также сохраняется точная команда в
`codex-command.json`. Запрошенные модель и усилие фиксируются в отчёте как
запрошенные параметры, их фактическое применение пока не подтверждается.

Для подготовки без создания контейнера и выполнения задачи добавьте
`--prepare` к команде режима Codex. Подготовка показывает команду Docker и
параметры Codex, но не передаёт задачу и не создаёт контейнер.

Проверка этого режима пока не является готовностью к живому прогону: сеть и
авторизация не подключены. Применение навыка намеренно остаётся
неподтверждённым, разбор свидетельств ещё не реализован.

Запускатель сам использует `--network none`, read-only rootfs, временный
домашний каталог, произвольный UID:GID и `/workspace`, а после испытания удаляет
контейнер. Образ пока проверен только для механики стенда. Установка коллекции и
работа агентских сред ещё не проверялись.

Для отдельной проверки штатной установки опубликованной коллекции только для
цели Codex используйте уже существующий локальный ID образа. Команда не
пересобирает и не скачивает образ:

```text
RESULTS_DIR="$(mktemp -d)"
python3 tools/compatibility/install_published.py --image "$IMAGE_ID" --results-dir "$RESULTS_DIR" --timeout 180
```

Сценарий создаёт пустой проект потребителя, разрешает контейнерную сеть для
получения публичного реестра и пакета, сохраняет проект и отчёт в `RESULTS_DIR`,
а затем удаляет контейнер. В контейнер не передаются авторизация, переменные
окружения или домашний каталог пользователя. Docker socket и каталог репозитория
разработчика не монтируются. Сохраняются stdout, stderr и коды обеих команд APM,
версия APM, сведения из lock-файла, список навыков и сверка хэшей проекции Codex.
При ошибке частичные результаты остаются на месте.
