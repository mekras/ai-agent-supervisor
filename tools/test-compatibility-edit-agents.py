#!/usr/bin/env python3
"""Проверить эвристический оракул сценария правки AGENTS.md."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "evals/compatibility/edit-agents/check.py"
FIXTURE = ROOT / "evals/compatibility/edit-agents/fixture/AGENTS.md"


def run_check(content: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="compatibility-edit-agents-") as directory:
        project = Path(directory)
        (project / "AGENTS.md").write_text(content, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECK), str(project)],
            cwd=ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


def assert_result(content: str, expected_code: int, *needles: str) -> None:
    result = run_check(content)
    assert result.returncode == expected_code, result.stdout + result.stderr
    output = result.stdout + result.stderr
    for needle in needles:
        assert needle in output, f"Не найдено {needle!r} в выводе:\n{output}"


original = FIXTURE.read_text(encoding="utf-8")
correct = original.replace(
    "В итоговом ответе перечисляй изменённые файлы.",
    "В итоговом ответе кратко описывай результат и выполненные проверки.",
)
assert_result(correct, 0, "[PASS] Старое требование удалено")
assert_result(original, 1, "[FAIL] Старое требование удалено")
assert_result(
    correct.replace("Не изменяй файлы в archive/.\n", ""),
    1,
    "[FAIL] Сохранено ограничение archive/",
)
assert_result(
    correct.replace(" и выполненные проверки", ""),
    1,
    "[FAIL] Новое требование содержит выполненные проверки",
)
markdown_variant = """# Правила проекта

## Общение
- Отвечай по-русски.

## Отчёт о работе
- В итоговом ответе кратко
  описывай результат и выполненные проверки.

## Ограничения
- Не изменяй файлы в archive/.
- Не выполняй `commit` и `push` без явного разрешения пользователя.
"""
assert_result(markdown_variant, 0, "[PASS] Новое требование содержит выполненные проверки")

print("Проверки сценария правки AGENTS.md пройдены.")
