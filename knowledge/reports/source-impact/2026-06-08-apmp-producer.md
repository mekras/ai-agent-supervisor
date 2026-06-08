# Отчёт о влиянии источника: `APMP`

## Источники и дата проверки

- Источник учёта:
  - `knowledge/inventory/APMP.md`
- Первичный слой:
  - `knowledge/primary/APMP/source.md`
  - `knowledge/primary/APMP/page-index.tsv`
- Нормализованный слой:
  - `knowledge/normalized/APMP/source.md`
- Извлечённые утверждения:
  - `knowledge/statements/APMP.md`
- Дата проверки: `2026-06-08`

## Границы аудита

Проверялось влияние producer-документации APM на:

- `README.md` как точку входа для сопровождающего пакета;
- `docs/architecture.md` как краткое описание архитектурной роли APM;
- `knowledge/sources-manifest.yml` как контракт фактической структуры корпуса.

Аудит не переписывал навыки или `AGENTS.md`: новый источник даёт guidance по
producer-процессу APM, а не по прикладным правилам работы агентов в этом
репозитории.

## Существенные сведения источника

- `APMP-001` — producer-процесс APM задаётся как лестница из author, compile,
  preview, pack и publish.
- `APMP-002` — `apm compile` относится только к instructions и не нужен как
  обязательный шаг для skills-only пакета.
- `APMP-003` — перед выпуском APM рекомендует verify loop из `compile
  --dry-run`, `view`, `audit` и `pack`, при этом `--validate` служит жёсткой
  структурной проверкой.
- `APMP-004` — hooks и commands являются target-specific surfaces и не должны
  подменять переносимые primitives без явной причины.
- `APMP-005` — package-relative links работают по предсказуемому контракту, а
  внутри bundle навыка ссылки обычно сохраняют работоспособность без rewrite.

## Расхождения и решения

### Severity: Medium — README описывал только потребительский путь через APM

Документ: `README.md`

Источник: `APMP`

Класс: неполное покрытие producer-процесса

Факт источника: producer-документация APM задаёт проверяемый release loop для
сопровождающего пакета, но в `README.md` были только команды потребителя:
install, update и outdated.

Вывод: в `README.md` нужен короткий раздел для сопровождающего пакета с
разделением между текущим skills-only состоянием и будущим сценарием, где в
пакет добавятся instructions.

Что сделать: обновить `README.md`.

### Severity: Medium — архитектура не различала переносимые и target-specific primitives

Документ: `docs/architecture.md`

Источник: `APMP`

Класс: неполная архитектурная оговорка

Факт источника: producer-документация APM явно разделяет skills/prompts/
instructions/agents и hooks/commands.

Вывод: в архитектуре нужно зафиксировать текущий выбор в пользу skills и
предупреждение против неосознанного ухода в target-specific primitives.

Что сделать: обновить `docs/architecture.md`.

### Severity: Medium — манифест корпуса ссылался на несуществующий путь реестра

Документ: `knowledge/sources-manifest.yml`

Источник: проверка корпуса после обновления

Класс: устаревший контракт корпуса

Факт: фактический учёт источников ведётся через `knowledge/inventory/*.md`,
`knowledge/primary/<SOURCE>/page-index.tsv`, `knowledge/normalized/<SOURCE>/source.md`
и `knowledge/statements/<SOURCE>.md`, но манифест указывал на несуществующий
`knowledge/primary/web/knowledge-sources/index.yml`.

Вывод: манифест нужно привести к фактической структуре корпуса, иначе корпус
сам себе противоречит.

Что сделать: обновить `knowledge/sources-manifest.yml`.

## Изменения по итогам аудита

- Добавить producer-раздел в `README.md`.
- Уточнить роль APM primitives и compile-loop в `docs/architecture.md`.
- Исправить контракт структуры корпуса в `knowledge/sources-manifest.yml`.

## Ограничения проверки

- Полные HTML-снимки страниц `APMP` не публикуются в Git и используются только
  как локальная первичная опора.
- Новый источник не требует автоматического изменения навыков проекта без
  отдельной задачи на их APM-упаковку или расширение набора primitives.
