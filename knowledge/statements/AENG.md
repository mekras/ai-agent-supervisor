# Извлечённые утверждения: `AENG`

## Основание

- Источник учёта: `knowledge/inventory/AENG.md`
- Первичный источник: `knowledge/primary/AENG/source.md`
- Индекс первичных страниц: `knowledge/primary/AENG/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/AENG/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-05`

## Назначение

Документ фиксирует проверяемые утверждения из материалов Anthropic Engineering
о проектировании агентов, multi-agent систем и context engineering.

## Утверждения

### AENG-001

- Статус: `ready_for_review`
- Утверждение: Anthropic различает workflow-системы с заранее заданными
  кодовыми траекториями и agents, где модель сама направляет процесс и выбор
  инструментов.
- Фрагмент источника: в `building-effective-agents` вводится архитектурное
  разделение между workflows и agents.
- Область применения: терминология и выбор архитектурного режима.
- Опора в артефактах:
  - `knowledge/normalized/AENG/pages/building-effective-agents/index.md`
  - `knowledge/primary/AENG/pages/building-effective-agents/index.html`
- Куда может перейти: словарь терминов и проектные правила выбора паттерна.

### AENG-002

- Статус: `ready_for_review`
- Утверждение: При построении LLM-приложений рекомендуется начинать с самого
  простого решения и добавлять агентную сложность только при подтверждённом
  выигрыше по качеству результата.
- Фрагмент источника: `building-effective-agents` несколько раз повторяет
  принцип simplest solution first и добавления сложности по необходимости.
- Область применения: критерии внедрения multi-step и agentic логики.
- Опора в артефактах:
  - `knowledge/normalized/AENG/pages/building-effective-agents/index.md`
  - `knowledge/primary/AENG/pages/building-effective-agents/index.html`
- Куда может перейти: архитектурные эвристики и review новых решений.

### AENG-003

- Статус: `ready_for_review`
- Утверждение: Multi-agent research systems особенно сильны на breadth-first
  запросах с несколькими независимыми направлениями поиска, но резко повышают
  token cost и потому не универсальны.
- Фрагмент источника: `multi-agent-research-system` связывает пригодность
  multi-agent режима с breadth-first query patterns, token budget и стоимостью.
- Область применения: отбор задач для multi-agent оркестрации.
- Опора в артефактах:
  - `knowledge/normalized/AENG/pages/multi-agent-research-system/index.md`
  - `knowledge/primary/AENG/pages/multi-agent-research-system/index.html`
- Куда может перейти: правила выбора между single-agent и multi-agent.

### AENG-004

- Статус: `ready_for_review`
- Утверждение: Для качественного делегирования lead agent должен задавать
  subagents цель, формат результата, допустимые инструменты, источники и
  границы задачи; короткие общие инструкции приводят к дублированию и пропускам.
- Фрагмент источника: `multi-agent-research-system` описывает ошибки ранних
  версий и требования к task description для subagents.
- Область применения: контракт между оркестратором и подагентами.
- Опора в артефактах:
  - `knowledge/normalized/AENG/pages/multi-agent-research-system/index.md`
  - `knowledge/primary/AENG/pages/multi-agent-research-system/index.html`
- Куда может перейти: требования к маршрутизации и prompt/tool contracts.

### AENG-005

- Статус: `ready_for_review`
- Утверждение: Context engineering трактуется как управление полным набором
  токенов, доступных модели на каждом шаге, а не только как написание prompt;
  целевой принцип — минимальный набор high-signal tokens.
- Фрагмент источника: `effective-context-engineering-for-ai-agents` вводит
  определение context engineering и принцип smallest set of high-signal tokens.
- Область применения: управление контекстом в агентах и навыках.
- Опора в артефактах:
  - `knowledge/normalized/AENG/pages/effective-context-engineering-for-ai-agents/index.md`
  - `knowledge/primary/AENG/pages/effective-context-engineering-for-ai-agents/index.html`
- Куда может перейти: правила написания инструкций, навыков и tool guidance.

### AENG-006

- Статус: `ready_for_review`
- Утверждение: Для long-horizon задач полезны compaction, structured
  note-taking и sub-agent architectures как механизмы сохранения связности при
  ограниченном context window.
- Фрагмент источника: `effective-context-engineering-for-ai-agents` выделяет
  эти три техники как основные способы борьбы с context pollution.
- Область применения: дизайн долгоживущих агентных сессий.
- Опора в артефактах:
  - `knowledge/normalized/AENG/pages/effective-context-engineering-for-ai-agents/index.md`
  - `knowledge/primary/AENG/pages/effective-context-engineering-for-ai-agents/index.html`
- Куда может перейти: паттерны memory, compaction и делегирования.
