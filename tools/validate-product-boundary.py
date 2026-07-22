#!/usr/bin/env python3
"""Проверить публикуемые файлы на известные внутренние сведения проекта."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TEXT_SUFFIXES = {".json", ".md", ".py", ".sh", ".txt", ".yaml", ".yml"}
FORBIDDEN_PATTERNS = (
    (
        "внутренний корпус",
        re.compile(r"knowledge/|\bcorpus\b|\bкорпус\w*", re.IGNORECASE),
    ),
    (
        "внутренняя прослеживаемость сценариев",
        re.compile(
            r'"(?:source_basis|required_corpus_claims|corpus_claims|'
            r'claim_id|statement_path)"'
        ),
    ),
    (
        "внутренний идентификатор источника",
        re.compile(r"\b[A-Z][A-Z0-9]{3,7}-\d{3}\b"),
    ),
    (
        "историческое имя проекта или пакета",
        re.compile(r"\bai-agent-supervisor\b|\bai-dev-team\b|\bmekras/"),
    ),
    (
        "локальный абсолютный путь",
        re.compile(r"(?:^|[\s'\"])(?:/home/|/Users/)[^\s'\"]+"),
    ),
    (
        "конкретный внутренний пример тарифа",
        re.compile(r"\bChatGPT\s+Pro(?:\s+\d+x)?\b", re.IGNORECASE),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверить границу публикуемой коллекции навыков.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".apm/skills")],
        help="Файлы или каталоги продукта. По умолчанию .apm/skills.",
    )
    return parser.parse_args()


def iter_text_files(paths: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            files.add(path)
        elif path.is_dir():
            files.update(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix in TEXT_SUFFIXES
            )
    return sorted(files)


def find_leaks(paths: list[Path]) -> list[str]:
    leaks: list[str] = []
    for path in iter_text_files(paths):
        content = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                leaks.append(f"{path}:{line}: {label}")
    return leaks


def main() -> int:
    args = parse_args()
    missing = [str(path) for path in args.paths if not path.exists()]
    if missing:
        print(f"Пути продукта не найдены: {', '.join(missing)}", file=sys.stderr)
        return 1

    leaks = find_leaks(args.paths)
    if leaks:
        print("\n".join(leaks), file=sys.stderr)
        return 1

    print("Известные внутренние сведения в публикуемых файлах не найдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
