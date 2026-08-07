---
name: event-summary
description: Сохраняет сводку событий проекта.
---

# event-summary

Запусти `python3 .apm/skills/event-summary/scripts/summarize.py --root .`.

Каждая запись из `events.json` является отдельным событием. Повторяющиеся
идентификаторы допустимы и не должны уменьшать `event_count`.
