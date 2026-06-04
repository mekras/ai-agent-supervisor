# Извлечённые утверждения: `GHAB`

## Основание

- Источник учёта: `knowledge/inventory/GHAB.md`
- Первичный источник: `knowledge/primary/GHAB/source.md`
- Индекс первичных страниц: `knowledge/primary/GHAB/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/GHAB/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-03`

## Назначение

Документ фиксирует первые наблюдения по материалу `GHAB` до их
переноса в проектные правила.

## Утверждения

### GHAB-001

- Статус: `ready_for_review`
- Утверждение: в `agents.md` для Copilot рекомендуется описывать
  специализированные роли агентов, а не один общий ассистент.
- Фрагмент источника: описаны команды "docs-agent", "test-agent",
  "security-agent".
- Область применения: структура декомпозиции контекста.
- Опора в артефактах:
  - `knowledge/normalized/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.md`
  - `knowledge/primary/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.html`
- Куда может перейти: шаблоны разбиения по ролям.

### GHAB-002

- Статус: `ready_for_review`
- Утверждение: успешные файлы содержат конкретную персонажность,
  точный стек, границы и конкретные команды, а не абстрактные формулировки.
- Фрагмент источника: раздел "What works in practice" с разбором
  рабочих паттернов.
- Область применения: качество описания `SKILL.md` и `AGENTS.md`.
- Опора в артефактах:
  - `knowledge/normalized/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.md`
  - `knowledge/primary/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.html`
- Куда может перейти: критерии пригодности файлов инструкций.

### GHAB-003

- Статус: `ready_for_review`
- Утверждение: в статье зафиксирован порог между "нерабочими" и
  "рабочими" agents.md: успешные файлы являются специалистами по задаче.
- Фрагмент источника: формулировка о чёткой специализации в
  "divide between ones that fail and ones that work".
- Область применения: отбор подхода к проектированию AGENTS/Skills.
- Опора в артефактах:
  - `knowledge/normalized/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.md`
  - `knowledge/primary/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.html`
- Куда может перейти: минимальные требования к `agents.md`.

### GHAB-004

- Статус: `ready_for_review`
- Утверждение: командам советуют включать в `agents.md` исполняемые
  команды с флагами и опциями, а не только названия инструментов.
- Фрагмент источника: "Include flags and options, not just tool names".
- Область применения: практический onboarding для агентов.
- Опора в артефактах:
  - `knowledge/normalized/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.md`
  - `knowledge/primary/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.html`
- Куда может перейти: контрольная матрица действий для задач.

### GHAB-005

- Статус: `ready_for_review`
- Утверждение: кодовые примеры в `agents.md` приравниваются к сильным
  сигналам для модели по сравнению с теоретическими описаниями.
- Фрагмент источника: "Code examples over explanations".
- Область применения: контент для шаблонов инструкций.
- Опора в артефактах:
  - `knowledge/normalized/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.md`
  - `knowledge/primary/GHAB/pages/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/index.html`
- Куда может перейти: структура чек-листов для AGENTS.md.
