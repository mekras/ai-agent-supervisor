# Источник: `LSME`

## Статус

Источник принят в корпус знаний как внешний публичный веб-материал
с ограничением на хранение полного HTML в Git.

## Происхождение

- Платформа: `https://docs.langchain.com`
- Раздел: `LangSmith`
- Дата пакетного получения: `2026-06-10T07:41:37Z`
- Способ получения: HTTP GET с локальным сохранением raw HTML и заголовков
  ответа.
- Страницы источника:
  - `https://docs.langchain.com/langsmith/evaluation`
  - `https://docs.langchain.com/langsmith/evaluation-approaches`
  - `https://docs.langchain.com/langsmith/trajectory-evals`
- Получено 3 страницы с HTTP-статусом `200`.

## Что сохранено

В состав источника включены следующие артефакты:

- passport: `knowledge/primary/LSME/source.md`
- индекс: `knowledge/primary/LSME/page-index.tsv`
- страницы:
  - `knowledge/primary/LSME/pages/evaluation/index.html`
  - `knowledge/primary/LSME/pages/evaluation-approaches/index.html`
  - `knowledge/primary/LSME/pages/trajectory-evals/index.html`
- заголовки ответа:
  - `knowledge/primary/LSME/pages/evaluation/response-headers.txt`
  - `knowledge/primary/LSME/pages/evaluation-approaches/response-headers.txt`
  - `knowledge/primary/LSME/pages/trajectory-evals/response-headers.txt`

Снимки хранятся локально с исключением `pages/` из Git через
`knowledge/primary/LSME/.gitignore`.

## Ограничения

- Источник ограничен тремя указанными страницами документации LangSmith.
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
`HTTP/1.1 200 Connection established`, если они присутствовали.

## Назначение в проекте

Материал может использоваться как первичный для изучения подходов к оценке
LangSmith, включая общую оценку, подходы к evaluation и trajectory evals.
