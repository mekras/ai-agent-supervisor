#!/usr/bin/env python3
"""Пересобрать индексы корпуса с путями, относительными к корню корпуса.

Установленный контроллер ``kc-pipeline`` записывает пути относительно корня
репозитория, а установленный валидатор ``kc-inventory`` требует относительные
к каталогу корпуса. Этот проектный мост устраняет только разницу представления
производного индекса; карточки источников и зависимости APM он не изменяет.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = PROJECT_ROOT / "knowledge"
OPERATIONS = CORPUS_ROOT / "operations.yml"
CONTROLLER = PROJECT_ROOT / ".agents/skills/kc-pipeline/scripts/run-corpus-operations.py"
ITEM_INDEX = CORPUS_ROOT / "index/items.yml"
REPOSITORY_PREFIX = "path: knowledge/"
CORPUS_PREFIX = "path: "


def normalize_item_index_paths() -> int:
    content = ITEM_INDEX.read_text(encoding="utf-8")
    normalized = content.replace(REPOSITORY_PREFIX, CORPUS_PREFIX)
    if normalized == content:
        return 0
    ITEM_INDEX.write_text(normalized, encoding="utf-8")
    return content.count(REPOSITORY_PREFIX)


def main() -> int:
    if not CONTROLLER.is_file():
        print(f"Не найден установленный контроллер: {CONTROLLER}", file=sys.stderr)
        return 2

    result = subprocess.run(
        [sys.executable, str(CONTROLLER), "knowledge", "--operations", "knowledge/operations.yml", "--rebuild-indexes"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode:
        return result.returncode
    corrected = normalize_item_index_paths()
    print(f"Индексы корпуса пересобраны; скорректировано путей: {corrected}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
