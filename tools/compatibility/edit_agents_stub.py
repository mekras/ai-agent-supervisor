#!/usr/bin/env python3
"""Тестовая заглушка механики; не является модельным прогоном."""

from pathlib import Path
import sys


TASK = sys.stdin.read()
PATH = Path("/workspace/AGENTS.md")
OLD = "В итоговом ответе перечисляй изменённые файлы."
NEW = "В итоговом ответе кратко описывай результат и выполненные проверки."

if not TASK.strip():
    raise SystemExit("Задача не передана через stdin")

text = PATH.read_text(encoding="utf-8")
if OLD not in text:
    raise SystemExit("Исходное требование не найдено")
PATH.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
