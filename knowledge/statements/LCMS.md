# Извлечённые утверждения: `LCMS`

## Основание

- Источник учёта: `knowledge/inventory/LCMS.md`
- Первичный источник: `knowledge/primary/LCMS/source.md`
- Индекс первичных страниц: `knowledge/primary/LCMS/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/LCMS/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-05`

## Назначение

Документ фиксирует проверяемые утверждения из статьи LangChain о границах
применения multi-agent систем и сопутствующей инженерной инфраструктуре.

## Утверждения

### LCMS-001

- Статус: `ready_for_review`
- Утверждение: Для agentic систем context engineering является критической
  инженерной задачей, потому что эффективность модели определяется не только
  prompt, но и тем, какой контекст и в каком порядке попадает в LLM.
- Фрагмент источника: статья несколько раз называет context engineering
  центральной проблемой и связывает её с полным контролем над оркестрацией.
- Область применения: проектирование контекстных слоёв и orchestration.
- Опора в артефактах:
  - `knowledge/normalized/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.md`
  - `knowledge/primary/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.html`
- Куда может перейти: правила работы с контекстом и framework selection.

### LCMS-002

- Статус: `ready_for_review`
- Утверждение: Multi-agent системы, которые в основном читают и исследуют,
  обычно проще и безопаснее распараллеливать, чем системы, где несколько
  агентов одновременно пишут и изменяют общий результат.
- Фрагмент источника: статья противопоставляет read-heavy и write-heavy
  multi-agent patterns и связывает write-path с конфликтующими решениями.
- Область применения: границы параллелизации и распределения ответственности.
- Опора в артефактах:
  - `knowledge/normalized/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.md`
  - `knowledge/primary/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.html`
- Куда может перейти: правила выбора задач для подагентов.

### LCMS-003

- Статус: `ready_for_review`
- Утверждение: Даже read-heavy subagents требуют подробных task descriptions;
  без них агенты дублируют работу, теряют границы задачи или уходят в
  нерелевантные ветки поиска.
- Фрагмент источника: в статье разобран пример, где короткие инструкции lead
  agent приводили к дублированию исследований и неверному разделению труда.
- Область применения: постановка задач и границы делегирования.
- Опора в артефактах:
  - `knowledge/normalized/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.md`
  - `knowledge/primary/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.html`
- Куда может перейти: шаблоны для prompts и contracts подагентов.

### LCMS-004

- Статус: `ready_for_review`
- Утверждение: Durable execution, observability и evals образуют обязательный
  инженерный слой для production-agent систем, потому что агенты stateful,
  недетерминированы и накапливают ошибки по ходу длинных цепочек действий.
- Фрагмент источника: отдельные разделы статьи посвящены durable execution,
  observability и evaluation как общим требованиям к agent infrastructure.
- Область применения: требования к платформе и эксплуатационной надёжности.
- Опора в артефактах:
  - `knowledge/normalized/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.md`
  - `knowledge/primary/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.html`
- Куда может перейти: чек-листы production readiness.

### LCMS-005

- Статус: `ready_for_review`
- Утверждение: Multi-agent архитектура оправдана для ценных задач с хорошей
  параллелизацией и ограниченным требованием к общему контексту; универсальной
  схемы для всех агентных задач нет.
- Фрагмент источника: вывод статьи связывает пригодность multi-agent режима с
  ценностью задачи, parallelization и отсутствием one-size-fits-all решения.
- Область применения: архитектурный выбор и экономическая оценка.
- Опора в артефактах:
  - `knowledge/normalized/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.md`
  - `knowledge/primary/LCMS/pages/how-and-when-to-build-multi-agent-systems/index.html`
- Куда может перейти: критерии принятия multi-agent решений.
