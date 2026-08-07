---
name: policy-export
description: Создаёт машинное состояние политики проекта.
---

# policy-export

Запусти `python3 .apm/skills/policy-export/scripts/export.py --root .` для
режима `standard` или добавь `--mode strict`. Других режимов публичный интерфейс
не поддерживает. Выбранное значение должно попасть в `.policy/state.json`.
