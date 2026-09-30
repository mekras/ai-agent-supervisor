# Обезличенные выдержки испытаний Hermes

## Успешный прогон

Сессия `20260929_115553_05b486`, Hermes Agent 0.21.3, локальный кандидат
`2.6.12-hermes-local.20260929`.

- `hermes-command.json`, поля `hermes_argv` и `effort_mechanism`: переданы
  `--provider openai-codex`, `--model gpt-5.6-luna`, `--reasoning high`.
- `hermes-agent.log.txt`, API call #1–#5: клиентский журнал фиксирует
  `model=gpt-5.6-luna provider=openai-codex`.
- `hermes-session.jsonl`, поля `model` и
  `model_config.reasoning_config.effort`: сохранены `gpt-5.6-luna` и `high`.
  Эти источники подтверждают переданные и сохранённые клиентом параметры, но
  не дают независимого подтверждения фактических параметров на стороне сервера.
- `skill_view`: загружен `ai-agents-md-maintenance`, затем прочитаны
  `references/maintenance-checklist.md` и `references/content-guidelines.md`.
- `read_file`: перечитан исходный и итоговый `AGENTS.md`.
- `patch`: изменён только `AGENTS.md`.
- `terminal`: проверены Git-изменения до и после правки.
- Итог: код 0, статус `passed`, длительность 55,375 секунды, контейнер очищен.

В отдельном `HERMES_HOME` штатный загрузчик подтвердил
`security.protected_instruction_files=false`. Общий auto-approve и yolo не
включались. Телеметрия не проверялась. Полное соблюдение инструкций навыка не
оценивалось.

## Предыдущий неуспешный прогон

Сессия `20260929_104352_856be9` выполнялась с включённой защитой
`security.protected_instruction_files`. Вызов `patch` для `AGENTS.md` дошёл до
защищённой операции, ожидал отдельного подтверждения и не вернул результат до
тайм-аута 181,315 секунды. Это были другие условия, чем в успешном прогоне, где
защита была отключена только в отдельном стендовом `HERMES_HOME`.
