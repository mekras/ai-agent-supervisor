# Извлечённые утверждения: `VSCD`

## Основание

- Источник учёта: `knowledge/inventory/VSCD.md`
- Первичный источник: `knowledge/primary/VSCD/source.md`
- Индекс первичных страниц: `knowledge/primary/VSCD/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/VSCD/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-03`

## Назначение

Фиксация наблюдений по механике custom instructions в VS Code.

## Утверждения

### VSCD-001

- Статус: `ready_for_review`
- Утверждение: VS Code поддерживает как глобальные, так и файловые
  инструкции для чат-ассистента, включая scoped-подход по шаблонам.
- Фрагмент источника: разделы про Always-on instructions и
  File-based instructions.
- Область применения: политика конфигурации ассистента в проекте.
- Опора в артефактах:
  - `knowledge/normalized/VSCD/pages/custom-instructions/index.md`
  - `knowledge/primary/VSCD/pages/custom-instructions/index.html`
- Куда может перейти: шаблон распределения инструкций по уровням.

### VSCD-002

- Статус: `ready_for_review`
- Утверждение: `AGENTS.md`, `.github/copilot-instructions.md`,
  `.instructions.md` и `CLAUDE.md` рассматриваются как легитимные точки
  хранения правил.
- Фрагмент источника: перечислены типы поддерживаемых файловых инструкций.
- Область применения: выбор формата для внутренних и общих правил.
- Опора в артефактах:
  - `knowledge/normalized/VSCD/pages/custom-instructions/index.md`
  - `knowledge/primary/VSCD/pages/custom-instructions/index.html`
- Куда может перейти: проверка совместимости инструментов с правилами.

### VSCD-003

- Статус: `ready_for_review`
- Утверждение: если инструкций несколько, их контент может
  комбинироваться без строгой гарантии порядка.
- Фрагмент источника: раздел об условиях слияния нескольких instruction-файлов.
- Область применения: риск конфликтов при дублирующих правилах.
- Опора в артефактах:
  - `knowledge/normalized/VSCD/pages/custom-instructions/index.md`
  - `knowledge/primary/VSCD/pages/custom-instructions/index.html`
- Куда может перейти: методика управления конфликтами правил.

### VSCD-004

- Статус: `ready_for_review`
- Утверждение: inline suggestions в редакторе не обрабатываются через
  custom instructions чата.
- Фрагмент источника: заметка о том, что custom instructions не применяются
  к предложениям inline.
- Область применения: ожидания от поведения автодополнений.
- Опора в артефактах:
  - `knowledge/normalized/VSCD/pages/custom-instructions/index.md`
  - `knowledge/primary/VSCD/pages/custom-instructions/index.html`
- Куда может перейти: разделение правил для chat и редактора.

### VSCD-005

- Статус: `ready_for_review`
- Утверждение: scoped подход через паттерны файлов повышает точность
  применения инструкций для частей репозитория.
- Фрагмент источника: раздел про file-based instructions и match по
  описанию/файлу.
- Область применения: модульная маршрутизация правил.
- Опора в артефактах:
  - `knowledge/normalized/VSCD/pages/custom-instructions/index.md`
  - `knowledge/primary/VSCD/pages/custom-instructions/index.html`
- Куда может перейти: архитектура многоуровневых инструкций в репозитории.
