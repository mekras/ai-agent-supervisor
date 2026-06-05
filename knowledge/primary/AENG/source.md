# Источник: `AENG`

## Статус

Источник принят в корпус знаний как внешний публичный веб-материал
с ограничением на хранение полного HTML в Git.

## Происхождение

- Сайт: `https://www.anthropic.com/engineering`
- Дата получения: `2026-06-05`
- Способ получения: HTTP GET с локальным сохранением raw HTML и заголовков
  ответа
- Страницы источника:
  - `https://www.anthropic.com/engineering/building-effective-agents`
  - `https://www.anthropic.com/engineering/multi-agent-research-system`
  - `https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents`

## Что сохранено

В состав источника включены следующие артефакты:

- passport: `knowledge/primary/AENG/source.md`
- индекс: `knowledge/primary/AENG/page-index.tsv`
- страница:
  `knowledge/primary/AENG/pages/building-effective-agents/index.html`
- заголовки ответа:
  `knowledge/primary/AENG/pages/building-effective-agents/response-headers.txt`
- страница:
  `knowledge/primary/AENG/pages/multi-agent-research-system/index.html`
- заголовки ответа:
  `knowledge/primary/AENG/pages/multi-agent-research-system/response-headers.txt`
- страница:
  `knowledge/primary/AENG/pages/effective-context-engineering-for-ai-agents/index.html`
- заголовки ответа:
  `knowledge/primary/AENG/pages/effective-context-engineering-for-ai-agents/response-headers.txt`

Снимки хранятся локально с исключением `pages/` из Git через
`knowledge/primary/AENG/.gitignore`.

## Ограничения

- Источник ограничен тремя указанными страницами раздела engineering.
- Снимки отражают состояние страниц на момент получения.
- Полный текст страниц не должен использоваться как единственная опора без
  проверки условий использования.
- Нормализованные представления и извлечённые утверждения должны строиться из
  сохранённых артефактов этого источника, а не из живых страниц.

## Условия использования

- На уровне сохранённых HTML-снимков явная открытая лицензия на переиспользование
  полного текста не зафиксирована.
- Уровень уверенности: средний.
- Хранение полного HTML-артефакта в Git публичного проекта не допускается без
  отдельного подтверждения условий.
- Для внутренних задач допустимо извлечение проверяемых утверждений на основе
  сохранённых снимков.
- Атрибуция и правовой статус: `knowledge/source-attribution.md`.

## Очистка перед сохранением

В заголовках ответа удалены значения `set-cookie` и служебная строка прокси
`HTTP/1.1 200 Connection established`.

## Назначение в проекте

Материалы источника могут использоваться как первичные для изучения:

- практик построения эффективных AI-агентов;
- архитектуры и координации multi-agent систем;
- подходов к context engineering для агентных сценариев.
