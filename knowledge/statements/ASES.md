# Извлечённые утверждения: `ASES`

## Основание

- Источник учёта: `knowledge/inventory/ASES.md`
- Первичный источник: `knowledge/primary/ASES/source.md`
- Индекс первичных страниц: `knowledge/primary/ASES/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/ASES/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-10`

## Назначение

Документ фиксирует проверяемые утверждения из `Autonomous Systems Evaluation
Standard`, которые относятся к построению и приёмке evaluation-пакетов.

## Ограничения

- Утверждения извлечены из краткого нормализованного пересказа, а не из полного
  текста страницы.
- При спорных формулировках нужно сверяться с локальным HTML-снимком в
  `knowledge/primary/ASES`.

## Утверждения

### ASES-001

- Статус: `ready_for_review`
- Утверждение: все оценки для набора `Autonomous Systems` должны быть построены
  на `Inspect`.
- Фрагмент источника: раздел `Inspect` в обязательных требованиях прямо называет
  `Inspect` обязательной основой для evaluation.
- Область применения: выбор фреймворка для подготовки оценки.
- Опора в артефактах:
  - `knowledge/normalized/ASES/pages/standard/index.md`
  - `knowledge/primary/ASES/pages/standard/index.html`
- Куда может перейти: правила проектирования evaluation-пакетов и обзоры
  внешних evaluation-фреймворков.

### ASES-002

- Статус: `ready_for_review`
- Утверждение: репозиторий оценки должен соответствовать шаблону
  `as-evaluation-standard` и включать обязательные файлы `README.md`,
  `CONTRIBUTING.md` и `METADATA.json`.
- Фрагмент источника: раздел `Code and Repository Structure` связывает подачу
  оценки с cookiecutter-шаблоном и перечисляет обязательные артефакты.
- Область применения: структура репозитория и требования к комплектности.
- Опора в артефактах:
  - `knowledge/normalized/ASES/pages/standard/index.md`
  - `knowledge/primary/ASES/pages/standard/index.html`
- Куда может перейти: checked list для приёмки evaluation-репозитория.

### ASES-003

- Статус: `ready_for_review`
- Утверждение: scoring должен быть полностью автоматическим и не требовать
  ручной проверки.
- Фрагмент источника: раздел `Scoring` в обязательных требованиях запрещает
  manual grading steps.
- Область применения: требования к воспроизводимости и автоматизации оценки.
- Опора в артефактах:
  - `knowledge/normalized/ASES/pages/standard/index.md`
  - `knowledge/primary/ASES/pages/standard/index.html`
- Куда может перейти: правила выбора оценивателей и критериев приёмки.

### ASES-004

- Статус: `ready_for_review`
- Утверждение: quality assurance требует evidence в виде `Inspect`-журнала
  хотя бы одного успешного прогона, а также ручной проверки журналов на
  ошибки модели, инструментов и окружения.
- Фрагмент источника: раздел `Quality Assurance` требует QA log files и
  дополнительно просит просмотреть журналы на model API errors и tool issues.
- Область применения: подтверждение, что evaluation действительно исполнима.
- Опора в артефактах:
  - `knowledge/normalized/ASES/pages/standard/index.md`
  - `knowledge/primary/ASES/pages/standard/index.html`
- Куда может перейти: правила доказательства работоспособности evaluation.

### ASES-005

- Статус: `ready_for_review`
- Утверждение: каждая оценка должна включать собственные тесты, как минимум
  unit tests для custom tools или scorers и проверки получения внешних
  ресурсов, если задача зависит от них.
- Фрагмент источника: раздел `Custom Tests` перечисляет минимальный состав
  обязательных тестов.
- Область применения: тестовое покрытие evaluation-пакетов.
- Опора в артефактах:
  - `knowledge/normalized/ASES/pages/standard/index.md`
  - `knowledge/primary/ASES/pages/standard/index.html`
- Куда может перейти: проверка полноты тестов перед публикацией оценки.

### ASES-006

- Статус: `ready_for_review`
- Утверждение: evaluation не должна побуждать агента к небезопасным,
  незаконным или неэтичным действиям в реальном мире; для опасных возможностей
  рекомендуются симуляции, мокирование или подзадачи.
- Фрагмент источника: раздел `Ethical and Safety Guidelines` задаёт это
  ограничение как обязательное.
- Область применения: безопасность постановки задач для evaluation.
- Опора в артефактах:
  - `knowledge/normalized/ASES/pages/standard/index.md`
  - `knowledge/primary/ASES/pages/standard/index.html`
- Куда может перейти: ограничения на дизайн сценариев для агентных проверок.
