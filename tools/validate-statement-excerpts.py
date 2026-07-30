#!/usr/bin/env python3
"""Проверить, что цитаты утверждений непрерывно присутствуют в артефактах."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def load_statements(path: Path) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"не удалось прочитать YAML: {exc}") from exc
    if isinstance(data, list):
        statements = data
    elif isinstance(data, dict):
        statements = data.get("statements", [])
    else:
        raise ValueError("ожидался список утверждений или ключ statements")
    if not isinstance(statements, list):
        raise ValueError("ключ statements должен содержать список")
    return [item for item in statements if isinstance(item, dict)]


def validate(corpus: Path) -> list[str]:
    errors: list[str] = []
    checked = 0
    for statements_path in sorted(corpus.glob("data/**/statements.yml")):
        try:
            statements = load_statements(statements_path)
        except ValueError as exc:
            errors.append(f"{statements_path}: {exc}")
            continue
        for index, statement in enumerate(statements, start=1):
            excerpt = statement.get("excerpt")
            artifact = statement.get("artifact")
            identifier = statement.get("id", f"запись № {index}")
            label = f"{statements_path}: {identifier}"
            if not isinstance(excerpt, str) or not excerpt.strip():
                errors.append(f"{label}: отсутствует непустая цитата")
                continue
            if not isinstance(artifact, str) or not artifact:
                errors.append(f"{label}: отсутствует путь к артефакту")
                continue
            artifact_relative = Path(artifact)
            if artifact_relative.is_absolute() or ".." in artifact_relative.parts:
                errors.append(f"{label}: путь к артефакту выходит за пределы единицы")
                continue
            artifact_path = statements_path.parent / artifact_relative
            try:
                artifact_text = artifact_path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"{label}: не удалось прочитать {artifact}: {exc}")
                continue
            checked += 1
            if normalize_whitespace(excerpt) not in normalize_whitespace(artifact_text):
                errors.append(
                    f"{label}: цитата не найдена непрерывно в {artifact}"
                )
    if not errors:
        print(f"Цитаты утверждений проверены: {checked}.")
    return errors


def main() -> int:
    corpus = Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "knowledge"
    errors = validate(corpus)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
