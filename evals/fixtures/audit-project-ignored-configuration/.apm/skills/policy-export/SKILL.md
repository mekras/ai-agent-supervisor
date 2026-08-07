---
name: policy-export
description: Создаёт машинное состояние политики проекта.
---

# policy-export

Запусти `python3 .apm/skills/policy-export/scripts/export.py --root .`.

Без `policy.json` используется режим `standard`. Если файл существует, поле
`mode` из него должно попасть в `.policy/state.json`.
