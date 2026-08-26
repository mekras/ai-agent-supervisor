#!/usr/bin/env python3
"""Повторно проверить извлечённые единицы корпуса и закрыть source_check."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VALIDATOR = PROJECT_ROOT / ".agents/skills/kc-inventory/scripts/validate-corpus-layout.py"
PENDING_STAGE = "workflow_stage: statements_extracted"
CHECKED_STAGE = "workflow_stage: source_checked"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверить извлечённые единицы корпуса и закрыть очередь source_check."
    )
    parser.add_argument("corpus", type=Path, help="Корень корпуса с corpus.yml.")
    parser.add_argument(
        "--validator",
        type=Path,
        default=DEFAULT_VALIDATOR,
        help="Путь к validate-corpus-layout.py.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Только показать число готовых единиц."
    )
    return parser.parse_args()


def validate(corpus: Path, validator: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(corpus),
            "--strict-statements",
            "--strict-concepts",
            "--operational",
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Проверка корпуса не пройдена, очередь source_check не изменена.")


def pending_items(corpus: Path) -> list[Path]:
    items: list[Path] = []
    for item_path in sorted(corpus.glob("data/*/pages/**/item.yml")):
        content = item_path.read_text(encoding="utf-8")
        if PENDING_STAGE not in content:
            continue
        if content.count(PENDING_STAGE) != 1:
            raise RuntimeError(f"Некорректная стадия в {item_path}.")
        if not (item_path.parent / "statements.yml").is_file():
            raise RuntimeError(f"Нет утверждений для {item_path}.")
        items.append(item_path)
    return items


def replace_stage(item_path: Path) -> None:
    content = item_path.read_text(encoding="utf-8")
    updated = content.replace(PENDING_STAGE, CHECKED_STAGE)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=item_path.parent, delete=False
    ) as stream:
        stream.write(updated)
        temporary_path = Path(stream.name)
    temporary_path.replace(item_path)


def main() -> int:
    args = parse_args()
    corpus = args.corpus.resolve()
    validator = args.validator.resolve()
    try:
        corpus.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise RuntimeError("Корпус должен находиться внутри корня проекта.") from exc
    if not (corpus / "corpus.yml").is_file():
        raise RuntimeError(f"Не найден договор корпуса: {corpus / 'corpus.yml'}.")
    if not validator.is_file():
        raise RuntimeError(f"Не найден валидатор: {validator}.")

    validate(corpus, validator)
    items = pending_items(corpus)
    if args.dry_run:
        print(f"К проверке готовы единиц: {len(items)}.")
        return 0

    originals = {item_path: item_path.read_text(encoding="utf-8") for item_path in items}
    try:
        for item_path in items:
            replace_stage(item_path)
        validate(corpus, validator)
    except Exception:
        for item_path, content in originals.items():
            item_path.write_text(content, encoding="utf-8")
        raise
    print(f"Повторно проверено единиц: {len(items)}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        raise SystemExit(2)
