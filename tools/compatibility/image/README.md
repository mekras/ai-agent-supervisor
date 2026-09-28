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
CODEX_HOME_DIR="$(mktemp -d)"
python3 tools/compatibility/run.py \
  --project "$TEST_PROJECT" \
  --image "$CODEX_IMAGE_ID" \
  --results-dir "$RESULTS_DIR" \
  --timeout 180 \
  --mode codex \
  --model "$MODEL_NAME" \
  --effort "$EFFORT_NAME" \
  --codex-home "$CODEX_HOME_DIR" \
  --network none
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

`--codex-home` — обязательный явно указанный постоянный каталог состояния
Codex. Он монтируется отдельно от проекта и каталога результатов в
`/codex-home` с правом записи и передаётся через `CODEX_HOME`; запускатель его
не удаляет и не копирует содержимое в отчёт, снимок или образ. Каталог должен
существовать заранее и не пересекаться с проектом или результатами.
Пользовательский `~/.codex` автоматически не подставляется.

Чтобы использовать существующую файловую авторизацию и телеметрию, подготовьте
отдельный каталог локальным инструментом. Он читает только `auth.json` и раздел
`[otel]` из исходного `CODEX_HOME`, создаёт минимальный `config.toml` с
`cli_auth_credentials_store = "file"`, сохраняет `metrics_exporter`, endpoint,
protocol, headers и environment, устанавливает режим 700 для каталога и 600 для
файлов и отказывается перезаписывать целевые файлы:

```text
python3 tools/compatibility/prepare_codex_home.py \
  --source "$HOME/.codex" \
  --destination "/path/outside/repository/codex-home"
```

Каталог назначения содержит секреты. Исходный профиль при подготовке не
изменяется. Каталог можно обновлять отдельным входом и обновлением токенов;
обратной синхронизации с исходным профилем нет. Запускатель читает этот
минимальный пользовательский слой, поэтому `--ignore-user-config`
для режима Codex не используется. Секретные заголовки не попадают в аргументы
команд, `report.json` или другие результаты испытания.

Для отдельного входа через ChatGPT пользователь может вручную запустить в
контейнере Codex с подключённым этим каталогом команду
`CODEX_HOME=/codex-home codex login -c 'cli_auth_credentials_store="file"'` и
завершить браузерный вход. В headless-среде справка Codex также допускает
`codex login --device-auth`. Эти команды не выполняются запускателем; API-ключи
и автоматический перенос существующих учётных данных не предусмотрены. При
файловом хранении токен находится в `auth.json` внутри `CODEX_HOME`, поэтому
каталог нужно защищать как секрет. См. официальную документацию OpenAI:
https://developers.openai.com/codex/auth.

Параметр `--network none` сохраняет изоляцию по умолчанию. Значение `bridge`
включает обычный сетевой доступ Docker, а не доступ только к OpenAI; выбор
сохраняется в подготовленной команде и отчёте. Наличие каталога или файла
авторизации само по себе не подтверждает успешный вход и доступ к модели.

Для подготовки без создания контейнера и выполнения задачи добавьте
`--prepare` к команде режима Codex. Подготовка показывает команду Docker и
параметры Codex, но не передаёт задачу и не создаёт контейнер.

Один сценарий режима Codex успешно выполнен с подключённой файловой
авторизацией. Авторизация позволила выполнить этот запуск. Обновление токенов и
длительная работа не проверялись. Отправка и приём телеметрии также не
проверялись. Применение навыка намеренно остаётся
неподтверждённым, разбор свидетельств ещё не реализован.

Запускатель сам использует выбранную для режима Codex сеть (по умолчанию
`none`), read-only rootfs, временный
домашний каталог, произвольный UID:GID и `/workspace`, а после испытания удаляет
контейнер. Образ пока проверен только для механики стенда. Установка коллекции и
работа агентских сред ещё не проверялись.

Для режима Hermes используйте подготовленный проект с локальным Git-корнем и
отдельный `HERMES_HOME`:

```text
HERMES_IMAGE_ID='sha256:eff6ae1832649f11d229d89a10be93a68a7c89b6ad91e8d2dc548cf96217df21'
HERMES_PROJECT='/path/to/hermes-consumer'
HERMES_HOME_DIR='/path/to/hermes-home'
RESULTS_DIR="$(mktemp -d)"
python3 tools/compatibility/run.py \
  --project "$HERMES_PROJECT" \
  --image "$HERMES_IMAGE_ID" \
  --results-dir "$RESULTS_DIR" \
  --timeout 180 \
  --mode hermes \
  --hermes-home "$HERMES_HOME_DIR" \
  --provider PROVIDER \
  --model MODEL \
  --effort high \
  --network none
```

`PROVIDER`, `MODEL` и `--effort` обязательны. Запускатель передаёт исходный
`prompt` из `scenario.json` без изменений через stdin в
`hermes chat --query-file - --oneshot -Q`. Значение `--effort` передаётся
штатным параметром Hermes `--reasoning`, а не несуществующим флагом `--effort`.
Перед задачей выполняется `hermes skills trust /workspace`. Команда `chat`
запускается без `--ignore-user-config`, поэтому Hermes читает только
подключённый к контейнеру отдельный `HERMES_HOME`, а пользовательский профиль
не подключается и не копируется. Параметр `--prepare` записывает точную команду
и не создаёт контейнер, не устанавливает доверие и не передаёт задачу.

Проверка загрузки настроек выполняется без задачи и модели в том же образе с
сетью `none`: она загружает `HERMES_HOME/config.yaml` штатным
`hermes_cli.config.load_config`, проверяет сохранённое доверие к `/workspace`,
затем вызывает `agent.skill_utils.get_project_skills_dirs` и находит
`/workspace/.agents/skills/ai-agents-md-maintenance`. Исходники Hermes 0.21.3
показывают, что обычный `cmd_chat` без флагов обхода передаёт
`ignore_user_config=False`, а `cli.main` строит агент через обычный `load_config` и формирует
проектные навыки из доверенных каталогов. `hermes skills trust` изменяет только
раздел `skills.trusted_project_dirs` через `load_config` и `save_config`, поэтому
проверка также сохраняет отдельные настройки профиля, включая `_config_version`.

В отчёте Hermes отдельно сохраняются запрошенные provider, model и effort.
stdout, stderr, итоговый ответ, вывод доверия, JSONL-экспорт конкретной сессии,
`agent` и `errors` журналы сохраняются по отдельным именам. Версия `0.21.3`
для `chat --query-file -` не поддерживает `--usage-file`, поэтому доступные
поля расхода берутся из штатного JSONL-экспорта сессии. Содержимое всего
`HERMES_HOME` в результаты не копируется. Запускатель считает результат
неуспешным при ненулевом коде, сообщении Hermes о `failed` или `partial`,
неполном экспорте сессии, отсутствии итогового ответа или ошибке очистки.
Даже нулевой код процесса не отменяет эти условия. Применение навыка отдельно
не подтверждается автоматически.

Немодельная проверка закреплённого образа с сетью `none` подтвердила Hermes
`0.21.3`, справку CLI и `chat`, доверие `/workspace`, обнаружение
`ai-agents-md-maintenance` из `local`-проекции, Python `3.13.15`, Git `2.47.3`
и APM `0.31.0`. Режимы `command` и `codex` сохраняются без изменения.

Для отдельной проверки штатной установки опубликованной коллекции используйте
уже существующий локальный ID образа. По умолчанию выбирается прежний сценарий
Codex. Цель можно явно выбрать параметром `--target codex|hermes`. Команда не
пересобирает и не скачивает образ:

```text
RESULTS_DIR="$(mktemp -d)"
python3 tools/compatibility/install_published.py --image "$IMAGE_ID" --results-dir "$RESULTS_DIR" --timeout 180
```

Для испытательного образа Hermes используйте его уже закреплённый ID и отдельный
каталог результатов:

```text
HERMES_IMAGE_ID='sha256:eff6ae1832649f11d229d89a10be93a68a7c89b6ad91e8d2dc548cf96217df21'
RESULTS_DIR="$(mktemp -d)"
python3 tools/compatibility/install_published.py \
  --image "$HERMES_IMAGE_ID" \
  --results-dir "$RESULTS_DIR" \
  --timeout 180 \
  --target hermes
```

Сценарий Codex сохраняет прежнюю пустую рабочую копию. Сценарий Hermes создаёт
отдельный проект с исходной фикстурой `evals/compatibility/edit-agents/fixture/AGENTS.md`
и локальным Git-корнем без коммита. Установка APM выполняется с сетью `bridge`,
а затем штатные команды `hermes skills trust /workspace` и
`hermes skills list --source local` запускаются с сетью `none`, read-only rootfs,
непривилегированным UID:GID и отдельным временным `HERMES_HOME`. Ни авторизация,
ни профиль пользователя, ни модельные команды не передаются.

Для цели Hermes проверяется общая APM-проекция `.agents/skills`, путь которой
определён реализацией APM для Agent Skills. Проверка требует совпадения списка
файлов и SHA-256 из `apm.lock.yaml`, поэтому одного `SKILL.md` недостаточно.
На текущем опубликованном пакете `2.6.12` проверка фиксирует блокер: его метаданные
целей содержат `claude` и `codex`, но не Hermes, поэтому APM не создаёт проекцию.
Даже нулевые коды APM не меняют этот результат: отсутствие ожидаемой проекции
или lock-хэшей считается общей ошибкой установки. Стенд сохраняет диагностический
вывод и не исправляет это продуктовым маршрутом.
В обоих сценариях сохраняются stdout, stderr, коды команд APM, версия APM,
сведения из lock-файла и результаты очистки контейнеров. При ошибке частичные
результаты остаются на месте.

Проверку локального кандидата выполняйте отдельно от опубликованной `2.6.12`.
Кандидат собирается только во временном marketplace по шагам
«Синхронизировать состав пакета» из `.github/workflows/release.yml`. Исходный
`apm.yml` передаётся в `tools/sync-marketplace-manifest.py`, поэтому `target` не
исправляется вручную, а версия получает отдельное SemVer-значение:

```text
WORK_DIR="$(mktemp -d)"
CANDIDATE_VERSION='2.6.12-hermes-local.20260928'
git clone --branch master https://github.com/mekras/apm-marketplace.git "$WORK_DIR/marketplace"
candidate_dir="$WORK_DIR/ai-agent-supervisor-candidate"
package_dir="$WORK_DIR/marketplace/packages/ai-agent-supervisor"
mkdir -p "$candidate_dir"
cp -a .apm "$candidate_dir/.apm"
cp README.md CHANGELOG.md LICENSE "$candidate_dir/"
cp "$package_dir/apm.yml" "$candidate_dir/apm.yml"
python3 tools/sync-marketplace-manifest.py \
  --source apm.yml --package "$candidate_dir/apm.yml" --version "$CANDIDATE_VERSION"
mv "$package_dir" "$WORK_DIR/previous-package"
mv "$candidate_dir" "$package_dir"
MARKETPLACE_DIR="$WORK_DIR/marketplace" RELEASE_VERSION="$CANDIDATE_VERSION" python3 - <<'PY'
import os
import re
from pathlib import Path

path = Path(os.environ["MARKETPLACE_DIR"]) / "apm.yml"
text = path.read_text(encoding="utf-8")
text, count = re.subn(
    r"(source: ./packages/ai-agent-supervisor\n\s+version: )\"[^\"]+\"",
    rf'\g<1>"{os.environ["RELEASE_VERSION"]}"',
    text,
    count=1,
)
if count != 1:
    raise SystemExit("Не найдена версия пакета в реестре")
path.write_text(text, encoding="utf-8")
PY
(cd "$WORK_DIR/marketplace" && apm marketplace check && \
  apm pack --marketplace=claude,codex && \
  apm pack --marketplace=claude,codex --check-clean --dry-run)
git -C "$WORK_DIR/marketplace" add -A
git -C "$WORK_DIR/marketplace" -c user.name='Hermes compatibility candidate' \
  -c user.email='hermes-compatibility@example.invalid' \
  commit -m 'Подготовлен локальный кандидат коллекции'
```

Затем в новом проекте создайте `.git` без коммита, установите кандидат через
`apm marketplace add "$WORK_DIR/marketplace" --name local-candidate --ref master`
и `apm install ai-agent-supervisor@local-candidate --target hermes`. В отдельном
`HERMES_HOME` выполните с теми же параметрами read-only rootfs, UID:GID и сети
`none`, что указаны выше, `hermes skills trust /workspace` и
`hermes skills list --source local`. Успешный результат должен одновременно
содержать проекцию `.agents/skills`, совпадение всех lock-хэшей и запись
`ai-agents-md-maintenance` с источником `local`. В проверенном кандидате
установились 14 навыков, совпали 202 файла и обнаружение прошло. Это не меняет
результат опубликованной `2.6.12`, которая остаётся неуспешной из-за отсутствия
цели Hermes.
