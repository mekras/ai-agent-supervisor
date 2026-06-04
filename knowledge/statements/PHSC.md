# Извлечённые утверждения: `PHSC`

## Основание

- Источник учёта: `knowledge/inventory/PHSC.md`
- Первичный источник: `knowledge/primary/PHSC/source.md`
- Индекс первичных страниц: `knowledge/primary/PHSC/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/PHSC/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-03`

## Назначение

Фиксация наблюдений по практическим рекомендациям AGENTS.md.

## Утверждения

### PHSC-001

- Статус: `ready_for_review`
- Утверждение: AGENTS.md выступает как первичный вход в проект для
  кодового ассистента и оказывает решающее влияние на его контекст.
- Фрагмент источника: тезис о "single highest-leverage configuration point".
- Область применения: стартовая инициализация новых задач.
- Опора в артефактах:
  - `knowledge/normalized/PHSC/pages/writing-good-agents/index.md`
  - `knowledge/primary/PHSC/pages/writing-good-agents/index.html`
- Куда может перейти: минимальный обязательный onboarding-файл.

### PHSC-002

- Статус: `ready_for_review`
- Утверждение: авто-сгенерированный файл может снижать успех задач и
  увеличивать стоимость inference по сравнению с отсутствием таких файла.
- Фрагмент источника: разделы с цифрами снижения успеха и роста стоимости.
- Область применения: выбор между ручной и LLM-генерацией правил.
- Опора в артефактах:
  - `knowledge/normalized/PHSC/pages/writing-good-agents/index.md`
  - `knowledge/primary/PHSC/pages/writing-good-agents/index.html`
- Куда может перейти: оценка рисков автогенерации AGENTS.md.

### PHSC-003

- Статус: `ready_for_review`
- Утверждение: полезные файлы включают WHAT/WHY/HOW и минимум конкретной
  операционной информации (стек, процессы сборки, тестирования).
- Фрагмент источника: разделы What to Include и структура рекомендаций.
- Область применения: шаблоны содержания AGENTS.md.
- Опора в артефактах:
  - `knowledge/normalized/PHSC/pages/writing-good-agents/index.md`
  - `knowledge/primary/PHSC/pages/writing-good-agents/index.html`
- Куда может перейти: стандартные секции шаблона AGENTS.

### PHSC-004

- Статус: `ready_for_review`
- Утверждение: подробный обзор дерева репозитория и избыточные обзоры не
  дают выигрыш навигации и могут перегружать инструкцию.
- Фрагмент источника: результат экспериментов о том, что обзоры не
  ускоряют поиск релевантных файлов.
- Область применения: борьба с лишним объёмом инструкций.
- Опора в артефактах:
  - `knowledge/normalized/PHSC/pages/writing-good-agents/index.md`
  - `knowledge/primary/PHSC/pages/writing-good-agents/index.html`
- Куда может перейти: приоритизация содержимого AGENTS.md.

### PHSC-005

- Статус: `ready_for_review`
- Утверждение: упоминание инструментов в AGENTS.md резко повышает
  вероятность их использования моделью.
- Фрагмент источника: оценка, что указанные инструменты используются
  в десятки раз чаще.
- Область применения: оптимизация перечня ключевых команд.
- Опора в артефактах:
  - `knowledge/normalized/PHSC/pages/writing-good-agents/index.md`
  - `knowledge/primary/PHSC/pages/writing-good-agents/index.html`
- Куда может перейти: стратегия упоминания инструментов в правилах.
