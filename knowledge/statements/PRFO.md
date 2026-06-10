# Извлечённые утверждения: `PRFO`

## Основание

- Источник учёта: `knowledge/inventory/PRFO.md`
- Первичный источник: `knowledge/primary/PRFO/source.md`
- Индекс первичных страниц: `knowledge/primary/PRFO/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/PRFO/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-10`

## Назначение

Документ фиксирует проверяемые утверждения о `promptfoo` как инструменте для
evaluation и red teaming LLM-приложений.

## Ограничения

- Утверждения извлечены из краткого нормализованного пересказа вводной страницы.
- Вводная страница сочетает продуктовые обещания и рабочий процесс, поэтому
  проектные решения нельзя выводить из неё без дополнительной проверки.

## Утверждения

### PRFO-001

- Статус: `ready_for_review`
- Утверждение: `promptfoo` представлен как open-source CLI и библиотека для
  evaluation и red teaming приложений на LLM.
- Фрагмент источника: вступительный абзац страницы задаёт именно это
  позиционирование.
- Область применения: классификация инструмента и его заявленных задач.
- Опора в артефактах:
  - `knowledge/normalized/PRFO/pages/intro/index.md`
  - `knowledge/primary/PRFO/pages/intro/index.html`
- Куда может перейти: обзор инструментов для проверки LLM-приложений.

### PRFO-002

- Статус: `ready_for_review`
- Утверждение: `promptfoo` заявляет поддержку benchmark-проверок prompts,
  моделей и `RAG`, автоматизированного red teaming, кеширования, concurrency и
  live reload.
- Фрагмент источника: вводный список возможностей перечисляет эти свойства как
  ключевые.
- Область применения: сравнение практических возможностей evaluation-инструмента.
- Опора в артефактах:
  - `knowledge/normalized/PRFO/pages/intro/index.md`
  - `knowledge/primary/PRFO/pages/intro/index.html`
- Куда может перейти: матрица сравнения evaluation- и red-team-инструментов.

### PRFO-003

- Статус: `ready_for_review`
- Утверждение: `promptfoo` можно использовать как CLI, библиотеку и интеграцию
  в `CI/CD`, а также подключать разные LLM-провайдеры и пользовательские API.
- Фрагмент источника: вводный блок с перечислением возможностей и провайдеров
  прямо описывает эти режимы использования.
- Область применения: интеграция инструмента в процесс разработки и проверки.
- Опора в артефактах:
  - `knowledge/normalized/PRFO/pages/intro/index.md`
  - `knowledge/primary/PRFO/pages/intro/index.html`
- Куда может перейти: выбор места запуска evaluation в инженерном процессе.

### PRFO-004

- Статус: `ready_for_review`
- Утверждение: основная философия `promptfoo` сформулирована как
  test-driven LLM development вместо trial-and-error.
- Фрагмент источника: эта формулировка вынесена как явный `goal` страницы.
- Область применения: методологические ориентиры для построения evaluation.
- Опора в артефактах:
  - `knowledge/normalized/PRFO/pages/intro/index.md`
  - `knowledge/primary/PRFO/pages/intro/index.html`
- Куда может перейти: сравнение подходов к работе с prompts и тестами.

### PRFO-005

- Статус: `ready_for_review`
- Утверждение: рабочий цикл `promptfoo` состоит из пяти шагов: определить test
  cases, настроить evaluation, выполнить прогон, проанализировать результаты и
  пополнять examples через feedback loop.
- Фрагмент источника: раздел `Workflow and philosophy` перечисляет эти шаги по
  порядку.
- Область применения: схема непрерывного улучшения LLM-приложения.
- Опора в артефактах:
  - `knowledge/normalized/PRFO/pages/intro/index.md`
  - `knowledge/primary/PRFO/pages/intro/index.html`
- Куда может перейти: описание evaluation-цикла в проектной документации.

### PRFO-006

- Статус: `ready_for_review`
- Утверждение: `promptfoo` заявляет локальный режим работы, в котором evals
  выполняются на машине пользователя и напрямую обращаются к LLM.
- Фрагмент источника: блок `Why choose promptfoo?` описывает private/local
  режим без внешнего сервиса-посредника.
- Область применения: требования к приватности и локальному запуску.
- Опора в артефактах:
  - `knowledge/normalized/PRFO/pages/intro/index.md`
  - `knowledge/primary/PRFO/pages/intro/index.html`
- Куда может перейти: сравнение локальных и облачных способов запуска evals.
