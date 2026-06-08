# Извлечённые утверждения: `APMP`

## Основание

- Источник учёта: `knowledge/inventory/APMP.md`
- Первичный источник: `knowledge/primary/APMP/source.md`
- Индекс первичных страниц: `knowledge/primary/APMP/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/APMP/source.md`
- Нормализованные страницы: локальные неотслеживаемые артефакты в
  `knowledge/normalized/APMP/pages/**/index.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-08`

## Назначение

Документ фиксирует проверяемые утверждения из producer-документации APM,
которые относятся к сопровождению и выпуску этого репозитория как пакета
навыков.

## Утверждения

### APMP-001

- Статус: `ready_for_review`
- Утверждение: producer-процесс APM оформлен как последовательность шагов:
  author primitives, compile, preview and validate, pack a bundle, publish to a
  marketplace.
- Фрагмент источника: обзорная страница `producer/` задаёт «producer ladder»
  из пяти шагов и связывает каждый шаг с отдельной страницей.
- Область применения: выпуск и сопровождение пакета через APM.
- Опора в артефактах:
  - `knowledge/normalized/APMP/pages/overview/index.md`
  - `knowledge/primary/APMP/pages/overview/index.html`
- Куда может перейти: `README.md` для сопровождающего процесса пакета.

### APMP-002

- Статус: `ready_for_review`
- Утверждение: `apm compile` нужен только для инструкционных примитивов и
  особенно важен для не-Copilot harnesses; skills, prompts, agents, hooks и
  commands не компилируются этой командой и доставляются через `apm install`.
- Фрагмент источника: страница `compile/` отделяет instructions от остальных
  primitive types и прямо говорит, что без compile инструкции могут лежать на
  диске, но не попадать в root context file у `claude`, `codex`, `cursor`,
  `gemini`, `opencode` и `windsurf`.
- Область применения: выбор release-проверок и понимание текущей skills-only
  модели пакета.
- Опора в артефактах:
  - `knowledge/normalized/APMP/pages/compile/index.md`
  - `knowledge/primary/APMP/pages/compile/index.html`
- Куда может перейти: `README.md`, `docs/architecture.md`.

### APMP-003

- Статус: `ready_for_review`
- Утверждение: рекомендуемый producer verify loop перед упаковкой состоит из
  `apm compile --dry-run`, `apm view`, `apm audit`, затем `apm pack`, а
  `apm compile --validate` выступает как более строгая структурная проверка.
- Фрагмент источника: страница `preview-and-validate/` описывает read-only loop
  producer-проверок и отдельно выделяет `--validate` как быстрый строгий
  сигнал синтаксической и структурной корректности.
- Область применения: локальная проверка пакета перед выпуском и регрессией
  producer-артефактов.
- Опора в артефактах:
  - `knowledge/normalized/APMP/pages/preview-and-validate/index.md`
  - `knowledge/primary/APMP/pages/preview-and-validate/index.html`
- Куда может перейти: `README.md`.

### APMP-004

- Статус: `ready_for_review`
- Утверждение: APM различает переносимые primitives (`skills`, `prompts`,
  `instructions`, `agents`) и target-specific primitives (`hooks`,
  `commands`); hooks и commands не должны рассматриваться как основной
  кросс-харнесный путь доставки.
- Фрагмент источника: страницы `author-primitives/` и
  `author-primitives/hooks-and-commands/` описывают матрицу primitive types и
  прямо называют hooks и commands opt-in surface для ограниченного набора
  harnesses.
- Область применения: архитектурные решения о том, как расширять пакет в
  будущем.
- Опора в артефактах:
  - `knowledge/normalized/APMP/pages/author-primitives/index.md`
  - `knowledge/normalized/APMP/pages/author-primitives/hooks-and-commands/index.md`
  - `knowledge/primary/APMP/pages/author-primitives/index.html`
  - `knowledge/primary/APMP/pages/author-primitives/hooks-and-commands/index.html`
- Куда может перейти: `docs/architecture.md`, `README.md`.

### APMP-005

- Статус: `ready_for_review`
- Утверждение: APM переписывает относительные Markdown-ссылки в instructions,
  prompts, agents и commands при установке, а ссылки внутри skill bundle обычно
  продолжают работать без переписывания, потому что каталог навыка
  копируется целиком.
- Фрагмент источника: страница `package-relative-links/` разделяет общий
  rewrite contract и special case для skills.
- Область применения: организация ссылок между `SKILL.md`, `references/`,
  `assets/` и другими файлами пакета.
- Опора в артефактах:
  - `knowledge/normalized/APMP/pages/package-relative-links/index.md`
  - `knowledge/primary/APMP/pages/package-relative-links/index.html`
- Куда может перейти: `docs/architecture.md`, правила структуры навыков.
