# Извлечённые утверждения: `INSP`

## Основание

- Источник учёта: `knowledge/inventory/INSP.md`
- Первичный источник: `knowledge/primary/INSP/source.md`
- Индекс первичных страниц: `knowledge/primary/INSP/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/INSP/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-10`

## Назначение

Документ фиксирует проверяемые утверждения о `Inspect` как framework для
frontier AI evaluations и агентных проверок.

## Ограничения

- Утверждения извлечены из краткого нормализованного пересказа главной страницы
  документации.
- Главная страница даёт обзор, а не полный технический контракт каждой функции.

## Утверждения

### INSP-001

- Статус: `ready_for_review`
- Утверждение: `Inspect` позиционируется как framework for frontier AI
  evaluations, разработанный `UK AI Security Institute` и `Meridian Labs`.
- Фрагмент источника: вступительный блок страницы определяет происхождение и
  назначение `Inspect`.
- Область применения: идентификация инструмента и его заявленной роли.
- Опора в артефактах:
  - `knowledge/normalized/INSP/pages/docs/index.md`
  - `knowledge/primary/INSP/pages/docs/index.html`
- Куда может перейти: обзор инструментов для evaluation и многоагентных задач.

### INSP-002

- Статус: `ready_for_review`
- Утверждение: `Inspect` заявляет composable building blocks `datasets`,
  `agents`, `tools` и `scorers`, а также более `200` готовых evaluation-наборов.
- Фрагмент источника: список core features перечисляет эти primitives и число
  pre-built evaluations.
- Область применения: оценка широты встроенной экосистемы инструмента.
- Опора в артефактах:
  - `knowledge/normalized/INSP/pages/docs/index.md`
  - `knowledge/primary/INSP/pages/docs/index.html`
- Куда может перейти: сравнение evaluation-фреймворков по готовности к повторному
  использованию.

### INSP-003

- Статус: `ready_for_review`
- Утверждение: в экосистему `Inspect` входят `Inspect View`, расширение для
  `VS Code` и встроенная поддержка вызова пользовательских и `MCP`-инструментов.
- Фрагмент источника: список core features называет web-based Inspect View,
  VS Code extension и flexible support for tool calling.
- Область применения: наблюдаемость и удобство разработки evaluation.
- Опора в артефактах:
  - `knowledge/normalized/INSP/pages/docs/index.md`
  - `knowledge/primary/INSP/pages/docs/index.html`
- Куда может перейти: требования к инструментам разработки и просмотра прогонов.

### INSP-004

- Статус: `ready_for_review`
- Утверждение: `Inspect` поддерживает agent evaluations, multi-agent primitives
  и запуск внешних агентов, включая `Claude Code`, `Codex CLI` и `Gemini CLI`.
- Фрагмент источника: список core features прямо перечисляет внешние agent CLIs.
- Область применения: оценка применимости фреймворка к внешним агентам.
- Опора в артефактах:
  - `knowledge/normalized/INSP/pages/docs/index.md`
  - `knowledge/primary/INSP/pages/docs/index.html`
- Куда может перейти: проектирование экспериментов для внешних агентных систем.

### INSP-005

- Статус: `ready_for_review`
- Утверждение: `Inspect` включает sandboxing system для запуска недоверенного
  кода через Docker, Kubernetes, Modal, Proxmox и другие системы через
  extension API.
- Фрагмент источника: список core features выделяет sandboxing как отдельную
  возможность фреймворка.
- Область применения: контроль риска при запуске агентного кода.
- Опора в артефактах:
  - `knowledge/normalized/INSP/pages/docs/index.md`
  - `knowledge/primary/INSP/pages/docs/index.html`
- Куда может перейти: требования к изоляции среды в evaluation-инфраструктуре.

### INSP-006

- Статус: `ready_for_review`
- Утверждение: базовая модель задачи в `Inspect` описана как связка
  `Dataset + Solver + Scorer`.
- Фрагмент источника: раздел `Hello, Inspect` раскладывает `Task` на эти три
  составные части.
- Область применения: концептуальная модель построения evaluation-задач.
- Опора в артефактах:
  - `knowledge/normalized/INSP/pages/docs/index.md`
  - `knowledge/primary/INSP/pages/docs/index.html`
- Куда может перейти: сравнение task-моделей между разными evaluation-средами.
