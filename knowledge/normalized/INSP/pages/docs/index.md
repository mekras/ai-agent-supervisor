# Inspect Documentation Home (нормализованное представление)

## URL

- `https://inspect.aisi.org.uk/`

## Ключевые тезисы

- `Inspect` описан как фреймворк для frontier AI evaluations, разработанный
  `UK AI Security Institute` и `Meridian Labs`.
- Источник заявляет широкую область применения: coding, agentic tasks,
  reasoning, knowledge, behavior и multimodal evaluations.
- Базовые строительные блоки включают datasets, agents, tools и scorers;
  отдельно упомянуты более `200` готовых evaluation-наборов.
- В состав экосистемы входят `Inspect View`, расширение для `VS Code`,
  встроенная поддержка вызова инструментов и запуск внешних агентов, включая
  `Claude Code`, `Codex CLI` и `Gemini CLI`.
- Инструмент поддерживает sandboxing для недоверенного кода через Docker,
  Kubernetes, Modal, Proxmox и другие системы через extension API.
- Для запуска нужен пакет `inspect-ai`, при желании расширение `VS Code`, а
  также доступ к модели через пакет провайдера и ключ API в окружении.
- Базовая модель задачи у `Inspect`: `Task = Dataset + Solver + Scorer`.

## Ограничения нормализации

- Нормализация основана на локальном HTML-снимке из `knowledge/primary/INSP`.
- Полный текст страницы не переносится в Git из-за неустановленного
  лицензионного статуса.
- Примеры `SimpleQA`, команды установки отдельных провайдеров и справочные
  ссылки сокращены до общего обзора возможностей.
