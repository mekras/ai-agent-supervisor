# Извлечённые утверждения: `AZPF`

## Основание

- Источник учёта: `knowledge/inventory/AZPF.md`
- Первичный источник: `knowledge/primary/AZPF/source.md`
- Индекс первичных страниц: `knowledge/primary/AZPF/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/AZPF/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-10`

## Назначение

Документ фиксирует проверяемые утверждения о `evaluation flow` в Azure Machine
Learning prompt flow и о связанных ограничениях жизненного цикла продукта.

## Ограничения

- Утверждения извлечены из краткого нормализованного пересказа, а не из полного
  текста страницы.
- Источник относится к продуктовой линии `Prompt flow`, для которой в документе
  уже объявлена дата вывода из эксплуатации.

## Утверждения

### AZPF-001

- Статус: `ready_for_review`
- Утверждение: `Prompt flow` в Microsoft Foundry и Azure Machine Learning будет
  выведен из эксплуатации `20 апреля 2027 года`, а новые разработки
  рекомендуется переносить на `Microsoft Agent Framework`.
- Фрагмент источника: предупреждение в начале страницы перечисляет дату
  retirement и маршрут миграции.
- Область применения: оценка уместности использования Prompt flow в новых
  проектах.
- Опора в артефактах:
  - `knowledge/normalized/AZPF/pages/evaluation-flow/index.md`
  - `knowledge/primary/AZPF/pages/evaluation-flow/index.html`
- Куда может перейти: ограничения на выбор платформы для evaluation-потоков.

### AZPF-002

- Статус: `ready_for_review`
- Утверждение: evaluation flow является специальным типом prompt flow, который
  получает входы и выходы тестируемого запуска и вычисляет оценки или метрики
  по его результатам.
- Фрагмент источника: раздел `Understand evaluation flows` определяет evaluation
  flow через отличие от стандартного flow и связь с tested run.
- Область применения: модель устройства отдельного evaluation-потока.
- Опора в артефактах:
  - `knowledge/normalized/AZPF/pages/evaluation-flow/index.md`
  - `knowledge/primary/AZPF/pages/evaluation-flow/index.html`
- Куда может перейти: сравнение разных реализаций evaluation pipeline.

### AZPF-003

- Статус: `ready_for_review`
- Утверждение: входы evaluation flow могут включать выходы проверяемого
  процесса, ground truth и дополнительный контекст, а по умолчанию используется
  тот же набор данных, что и у тестируемого запуска.
- Фрагмент источника: раздел `Inputs` описывает mapping tested outputs,
  labels и контекстных полей, а также возможность смены набора данных.
- Область применения: проектирование входного контракта оценки.
- Опора в артефактах:
  - `knowledge/normalized/AZPF/pages/evaluation-flow/index.md`
  - `knowledge/primary/AZPF/pages/evaluation-flow/index.html`
- Куда может перейти: проектирование интерфейса входных данных для evaluation.

### AZPF-004

- Статус: `ready_for_review`
- Утверждение: evaluation flow может выдавать построчные оценки для каждого
  примера и агрегировать их через reduce-узел `Aggregation` в общую метрику по
  всему набору.
- Фрагмент источника: разделы `Outputs and metrics` и `Aggregation and metrics
  logging` различают instance-level scores и overall assessment.
- Область применения: разделение локальных и итоговых результатов оценки.
- Опора в артефактах:
  - `knowledge/normalized/AZPF/pages/evaluation-flow/index.md`
  - `knowledge/primary/AZPF/pages/evaluation-flow/index.html`
- Куда может перейти: правила публикации per-row и aggregated metrics.

### AZPF-005

- Статус: `ready_for_review`
- Утверждение: итоговые metrics в evaluation flow должны быть числовыми и
  обычно записываются через `promptflow_sdk.log_metric()`.
- Фрагмент источника: пример reduce-узла показывает запись accuracy через
  `log_metric()`, а текст отдельно запрещает string metrics.
- Область применения: контракт типов для агрегированных метрик.
- Опора в артефактах:
  - `knowledge/normalized/AZPF/pages/evaluation-flow/index.md`
  - `knowledge/primary/AZPF/pages/evaluation-flow/index.html`
- Куда может перейти: требования к хранению и публикации итоговых показателей.

### AZPF-006

- Статус: `ready_for_review`
- Утверждение: evaluation flow можно начинать либо с шаблона, либо с clone
  built-in flow, а построчная оценка может считаться в Python-узле или через
  LLM-узел.
- Фрагмент источника: раздел `Develop an evaluation flow` описывает оба старта,
  а раздел `Calculate scores for each data point` допускает Python node и LLM
  node.
- Область применения: способы авторинга evaluation-потока.
- Опора в артефактах:
  - `knowledge/normalized/AZPF/pages/evaluation-flow/index.md`
  - `knowledge/primary/AZPF/pages/evaluation-flow/index.html`
- Куда может перейти: сравнение ручного и модельного способа расчёта оценок.
