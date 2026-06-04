# Извлечённые утверждения: `CODX`

## Основание

- Источник учёта: `knowledge/inventory/CODX.md`
- Первичный источник: `knowledge/primary/CODX/source.md`
- Индекс первичных страниц: `knowledge/primary/CODX/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/CODX/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-03`

## Назначение

Документ фиксирует проверки содержимого страницы `agents-md` перед
влиянием на каркас.

## Утверждения

### CODX-001

- Статус: `ready_for_review`
- Утверждение: Codex строит цепочку инструкций при старте и
  применяет их к каждому сеансу.
- Фрагмент источника: в разделе описания объясняется порядок
  формирование guidance-сцепочки при старте.
- Область применения: процессы инициализации.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/agents-md/index.md`
  - `knowledge/primary/CODX/pages/agents-md/index.html`
- Куда может перейти: проектирование цепочки AGENTS-приоритетов.

### CODX-002

- Статус: `ready_for_review`
- Утверждение: глобальный уровень `~/.codex` имеет приоритет над
  локальными до тех пор, пока не будет найден более специфичный override.
- Фрагмент источника: указана очередь чтения в глобальном скоупе и правило
  "первый непустой файл".
- Область применения: глобальные соглашения между проектами.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/agents-md/index.md`
  - `knowledge/primary/CODX/pages/agents-md/index.html`
- Куда может перейти: определение глобальных базовых инструкций.

### CODX-003

- Статус: `ready_for_review`
- Утверждение: проектный уровень просматривает все каталоги от корня
  до текущего и для каждого пытается применить до одного файла
  (`AGENTS.override.md`, затем `AGENTS.md`, затем fallback).
- Фрагмент источника: описание процесса Discovery по пути от root до cwd.
- Область применения: локальные правила в многоуровневых репозиториях.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/agents-md/index.md`
  - `knowledge/primary/CODX/pages/agents-md/index.html`
- Куда может перейти: иерархия AGENTS в проектах.

### CODX-004

- Статус: `ready_for_review`
- Утверждение: порядок объединения — от корня вниз, более глубокие файлы
  идут позже и имеют больший вес.
- Фрагмент источника: описан порядок конкатенации с пустыми строками и
  правило override для closer scope.
- Область применения: маршрутизация конфликтов между файлами инструкций.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/agents-md/index.md`
  - `knowledge/primary/CODX/pages/agents-md/index.html`
- Куда может перейти: политика конфликтов в `AGENTS.md`.

### CODX-005

- Статус: `ready_for_review`
- Утверждение: Codex прекращает добавление файлов инструкций по лимиту
  размера контекста (`project_doc_max_bytes`, по умолчанию 32 KiB).
- Фрагмент источника: источник прямо указывает на лимит и возможный
  срез при сборе инструкций.
- Область применения: контроль размера цепочки инструкций.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/agents-md/index.md`
  - `knowledge/primary/CODX/pages/agents-md/index.html`
- Куда может перейти: практики разбиения инструкций по nested каталогам.

### CODX-006

- Статус: `ready_for_review`
- Утверждение: для повышения надёжности рекомендуют увеличивать лимит
  или делить соглашения на вложенные файлы при переполнении.
- Фрагмент источника: указание "Raise the limit or split instructions
  across nested directories when you hit the cap."
- Область применения: устойчивость конфигурации для длинных правил.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/agents-md/index.md`
  - `knowledge/primary/CODX/pages/agents-md/index.html`
- Куда может перейти: структура вложенных AGENTS для больших репозиториев.
