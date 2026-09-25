#!/usr/bin/env python3
"""Эвристически проверить результат сценария правки AGENTS.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def normalized(text: str) -> str:
    """Свести регистр, ё и Markdown-разрывы к удобному для поиска виду."""

    text = text.casefold().replace("ё", "е")
    text = re.sub(r"[`*_~]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_old_requirement(text: str) -> bool:
    """Найти старое положительное требование с допустимыми формами слов."""

    pattern = re.compile(
        r"(?:в итоговом ответе\s+)?"
        r"(?:перечисл\w*|указ\w*|назов\w*)\s+"
        r"(?:все\s+)?изменен\w*\s+файл\w*"
    )
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 18) : match.start()]
        if not re.search(r"\bне\s*$", prefix):
            return True
    return False


def check_conditions(content: str) -> list[tuple[str, bool]]:
    text = normalized(content)
    return [
        ("Старое требование удалено", not has_old_requirement(text)),
        (
            "Новое требование содержит краткое описание результата",
            bool(
                re.search(r"кратк\w*\s+(?:опис\w*|излож\w*)\s+результат", text)
                or re.search(r"кратк\w*\s+описани\w*\s+результат", text)
            ),
        ),
        (
            "Новое требование содержит выполненные проверки",
            bool(re.search(r"(?:выполнен|пройден|проведен)\w*\s+провер\w*", text)),
        ),
        (
            "Сохранено правило русского языка",
            bool(re.search(r"отвеч\w*\s+(?:по-?русски|на русском)", text)),
        ),
        (
            "Сохранено ограничение archive/",
            bool(re.search(r"не\s+измен\w*\s+файл\w*\s+в\s+archive/", text)),
        ),
        (
            "Сохранено ограничение commit и push",
            bool(
                re.search(
                    r"не\s+выполн\w*\s+commit\s+и\s+push\s+"
                    r"без\s+явн\w*\s+разрешен\w*\s+пользовател",
                    text,
                )
            ),
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Эвристически проверить итоговую правку AGENTS.md."
    )
    parser.add_argument("project", type=Path, help="Путь к рабочему проекту после задачи")
    args = parser.parse_args()

    agents_path = args.project / "AGENTS.md"
    print("Проверка текста эвристическая и не заменяет полную смысловую оценку.")
    if not agents_path.is_file():
        print("[FAIL] AGENTS.md существует")
        print(f"Файл не найден: {agents_path}", file=sys.stderr)
        return 1

    content = agents_path.read_text(encoding="utf-8")
    results = [("AGENTS.md существует", True), *check_conditions(content)]
    for label, passed in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {label}")
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
