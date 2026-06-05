# Извлечённые утверждения: `CODX`

## Основание

- Источник учёта: `knowledge/inventory/CODX.md`
- Первичный источник: `knowledge/primary/CODX/source.md`
- Индекс первичных страниц: `knowledge/primary/CODX/page-index.tsv`
- Нормализованный слой: `knowledge/normalized/CODX/source.md`
- Атрибуция и правовой статус: `knowledge/source-attribution.md`
- Дата извлечения: `2026-06-05`

## Назначение

Документ фиксирует проверяемые утверждения из официальной документации Codex,
которые могут влиять на проектные правила, навыки и сопровождающую
документацию.

## Утверждения

### CODX-001

- Статус: `ready_for_review`
- Утверждение: Codex строит цепочку инструкций при старте и применяет её к
  каждому запуску или сеансу.
- Фрагмент источника: в `guides/agents-md` описано, что instruction chain
  собирается once per run / session start.
- Область применения: инициализация агентной сессии.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/guides/agents-md/index.md`
  - `knowledge/primary/CODX/pages/guides/agents-md/index.html`
- Куда может перейти: правила инициализации `AGENTS.md` и производные навыки.

### CODX-002

- Статус: `ready_for_review`
- Утверждение: Codex читает глобальный `AGENTS.override.md` или `AGENTS.md` из
  `CODEX_HOME`, затем проектные файлы по пути от project root к текущему
  каталогу; в каждом каталоге используется не более одного instruction-файла.
- Фрагмент источника: `guides/agents-md` описывает global scope, project scope
  и правило `at most one file per directory`.
- Область применения: иерархия и поиск проектных инструкций.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/guides/agents-md/index.md`
  - `knowledge/primary/CODX/pages/guides/agents-md/index.html`
- Куда может перейти: правила сопровождения `AGENTS.md`.

### CODX-003

- Статус: `ready_for_review`
- Утверждение: Инструкции объединяются от корня вниз; более близкие к `cwd`
  файлы идут позже и фактически перекрывают более общие.
- Фрагмент источника: `guides/agents-md` описывает merge order root-down и
  greater weight for closer scope.
- Область применения: разрешение конфликтов между instruction-слоями.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/guides/agents-md/index.md`
  - `knowledge/primary/CODX/pages/guides/agents-md/index.html`
- Куда может перейти: вложенные правила `AGENTS.md`.

### CODX-004

- Статус: `ready_for_review`
- Утверждение: Сбор project instructions ограничен `project_doc_max_bytes`
  (по умолчанию 32 KiB); при переполнении рекомендуют поднимать лимит или
  разбивать инструкции по вложенным каталогам.
- Фрагмент источника: `guides/agents-md` прямо указывает лимит и рекомендуемые
  действия при его достижении.
- Область применения: размер и декомпозиция machine instructions.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/guides/agents-md/index.md`
  - `knowledge/primary/CODX/pages/guides/agents-md/index.html`
- Куда может перейти: ограничения для больших `AGENTS.md`.

### CODX-005

- Статус: `ready_for_review`
- Утверждение: Пользовательская конфигурация Codex живёт в
  `~/.codex/config.toml`, а project-scoped overrides в `.codex/config.toml`
  загружаются только для trusted projects.
- Фрагмент источника: `config-basic` и `config-advanced` описывают user config,
  project config и ограничение trusted projects.
- Область применения: проектная конфигурация и границы доверия.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/config-basic/index.md`
  - `knowledge/normalized/CODX/pages/config-advanced/index.md`
  - `knowledge/primary/CODX/pages/config-basic/index.html`
  - `knowledge/primary/CODX/pages/config-advanced/index.html`
- Куда может перейти: правила `.codex/config.toml` и review project config.

### CODX-006

- Статус: `ready_for_review`
- Утверждение: Приоритет конфигурации идёт от CLI flags и `--config`, затем
  project config layers, затем profile files, user config, system config и
  built-in defaults.
- Фрагмент источника: `config-basic` перечисляет precedence order по слоям.
- Область применения: разрешение конфликтов настроек Codex.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/config-basic/index.md`
  - `knowledge/primary/CODX/pages/config-basic/index.html`
- Куда может перейти: документация по конфигурации и ожиданиям от среды.

### CODX-007

- Статус: `ready_for_review`
- Утверждение: Codex по умолчанию работает в режиме `workspace-write` с
  `approval_policy = "on-request"`; полный доступ соответствует комбинации
  `danger-full-access` и `never`.
- Фрагмент источника: `concepts/sandboxing` описывает default permissions,
  common sandbox modes и approval policies.
- Область применения: безопасность и автономность запуска.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/concepts/sandboxing/index.md`
  - `knowledge/primary/CODX/pages/concepts/sandboxing/index.html`
- Куда может перейти: правила sandbox/approval в проектных инструкциях.

### CODX-008

- Статус: `ready_for_review`
- Утверждение: Permission profiles не компонуются с legacy sandbox settings;
  активный `sandbox_mode` переключает Codex на старую схему sandbox-настроек.
- Фрагмент источника: `permissions` прямо говорит, что permission profiles do
  not compose with older sandbox settings.
- Область применения: архитектура permission policies.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/permissions/index.md`
  - `knowledge/primary/CODX/pages/permissions/index.html`
- Куда может перейти: правила выбора между `default_permissions` и
  `sandbox_mode`.

### CODX-009

- Статус: `ready_for_review`
- Утверждение: Встроенные permission profiles включают `:read-only`,
  `:workspace` и `:danger-full-access`; собственные профили задаются через
  `[permissions.<name>]` и `default_permissions`.
- Фрагмент источника: `permissions` описывает built-in profiles и способ
  задания named profiles.
- Область применения: формализация локальных permission-политик.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/permissions/index.md`
  - `knowledge/primary/CODX/pages/permissions/index.html`
- Куда может перейти: guidance по безопасной конфигурации среды.

### CODX-010

- Статус: `ready_for_review`
- Утверждение: MCP в Codex поддерживает STDIO и streamable HTTP servers, общую
  конфигурацию для CLI и IDE, а также server-wide guidance через поле
  `instructions`, причём первые 512 символов должны быть самодостаточными.
- Фрагмент источника: `mcp` перечисляет supported features и рекомендацию по
  `instructions`.
- Область применения: внешние инструменты и tool/context integration.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/mcp/index.md`
  - `knowledge/primary/CODX/pages/mcp/index.html`
- Куда может перейти: требования к MCP-зависимостям навыков и tool-политикам.

### CODX-011

- Статус: `ready_for_review`
- Утверждение: MCP servers можно задавать в `config.toml` через
  `[mcp_servers.<name>]`, а также управлять ими через `codex mcp add` /
  `codex mcp`.
- Фрагмент источника: `mcp` описывает both CLI configuration and direct TOML
  configuration.
- Область применения: настройка MCP в пользовательской и проектной среде.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/mcp/index.md`
  - `knowledge/primary/CODX/pages/mcp/index.html`
- Куда может перейти: инструкции по установке и сопровождению MCP.

### CODX-012

- Статус: `ready_for_review`
- Утверждение: Skills используют progressive disclosure: сначала в контекст
  попадают только `name`, `description` и путь; полный `SKILL.md` и
  дополнительные ресурсы читаются только после выбора навыка.
- Фрагмент источника: `skills` описывает progressive disclosure и отдельную
  загрузку `SKILL.md`.
- Область применения: проектирование навыков и управление контекстом.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/skills/index.md`
  - `knowledge/primary/CODX/pages/skills/index.html`
- Куда может перейти: правила структуры навыков и описаний.

### CODX-013

- Статус: `ready_for_review`
- Утверждение: Начальный список skills ограничен примерно 2% контекстного окна
  или 8000 символами, поэтому описания навыков должны быть короткими, ясными и
  front-loaded по trigger words.
- Фрагмент источника: `skills` прямо описывает budget for initial skills list и
  сокращение descriptions при большом наборе навыков.
- Область применения: проектирование skill descriptions.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/skills/index.md`
  - `knowledge/primary/CODX/pages/skills/index.html`
- Куда может перейти: критерии качества `description` в навыках.

### CODX-014

- Статус: `ready_for_review`
- Утверждение: Репозиторные навыки Codex сканируются из `.agents/skills` по
  пути от текущего каталога к корню репозитория; user/admin/system scopes
  поддерживаются отдельно.
- Фрагмент источника: `skills` описывает supported locations for repo, user,
  admin and system skills.
- Область применения: размещение и область действия навыков.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/skills/index.md`
  - `knowledge/primary/CODX/pages/skills/index.html`
- Куда может перейти: проектные соглашения по хранению навыков.

### CODX-015

- Статус: `ready_for_review`
- Утверждение: Codex запускает subagents только по явному запросу; они
  наследуют sandbox policy родителя, а встроенные агенты включают `default`,
  `worker` и `explorer`.
- Фрагмент источника: `subagents` описывает explicit spawning, inherited
  sandbox policy and built-in agents.
- Область применения: делегирование работы и параллелизм.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/subagents/index.md`
  - `knowledge/primary/CODX/pages/subagents/index.html`
- Куда может перейти: guidance по multi-agent workflows.

### CODX-016

- Статус: `ready_for_review`
- Утверждение: Глобальные ограничения subagent workflows по умолчанию включают
  `agents.max_threads = 6` и `agents.max_depth = 1`.
- Фрагмент источника: `subagents` перечисляет default values для max threads и
  max depth.
- Область применения: предсказуемость и стоимость делегирования.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/subagents/index.md`
  - `knowledge/primary/CODX/pages/subagents/index.html`
- Куда может перейти: project guidance по ограничению fan-out.

### CODX-017

- Статус: `ready_for_review`
- Утверждение: `codex exec` предназначен для non-interactive automation,
  по умолчанию работает в read-only sandbox, пишет progress в `stderr`, а
  финальное сообщение агента в `stdout`.
- Фрагмент источника: `noninteractive` описывает назначение `codex exec` и
  разделение `stderr`/`stdout`.
- Область применения: CI/CD и scripted usage.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/noninteractive/index.md`
  - `knowledge/primary/CODX/pages/noninteractive/index.html`
- Куда может перейти: guidance по безопасной автоматизации Codex.

### CODX-018

- Статус: `ready_for_review`
- Утверждение: Для structured automation `codex exec` поддерживает JSONL режим
  через `--json` и структурированный финальный вывод через `--output-schema`.
- Фрагмент источника: `noninteractive` описывает machine-readable output,
  JSONL event stream и `--output-schema`.
- Область применения: программная интеграция и pipeline automation.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/noninteractive/index.md`
  - `knowledge/primary/CODX/pages/noninteractive/index.html`
- Куда может перейти: рекомендации по интеграции Codex в CI.

### CODX-019

- Статус: `ready_for_review`
- Утверждение: TypeScript SDK управляет Codex напрямую в приложении, а Python
  SDK управляет локальным Codex app-server по JSON-RPC; для CI и automation SDK
  предпочтительнее app-server.
- Фрагмент источника: `sdk` и `app-server` различают use cases SDK vs app-server.
- Область применения: встраивание Codex в приложения и внутренние инструменты.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/sdk/index.md`
  - `knowledge/normalized/CODX/pages/app-server/index.md`
  - `knowledge/primary/CODX/pages/sdk/index.html`
  - `knowledge/primary/CODX/pages/app-server/index.html`
- Куда может перейти: архитектурные решения по интеграции Codex.

### CODX-020

- Статус: `ready_for_review`
- Утверждение: Customization в Codex строится на сочетании `AGENTS.md`,
  memories, skills, MCP и subagents; required team guidance нужно хранить в
  `AGENTS.md` или checked-in docs, а memories не должны быть единственным
  носителем обязательных правил.
- Фрагмент источника: `concepts/customization` и `memories` разделяют роли
  durable guidance и local recall layer.
- Область применения: модель долговременного контекста и распределение правил.
- Опора в артефактах:
  - `knowledge/normalized/CODX/pages/concepts/customization/index.md`
  - `knowledge/normalized/CODX/pages/memories/index.md`
  - `knowledge/primary/CODX/pages/concepts/customization/index.html`
  - `knowledge/primary/CODX/pages/memories/index.html`
- Куда может перейти: проектные правила хранения обязательных инструкций.
