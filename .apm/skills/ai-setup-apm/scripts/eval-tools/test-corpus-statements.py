#!/usr/bin/env python3
"""Regression checks for portable corpus statement parsing."""

from __future__ import annotations

from corpus_statements import (
    collect_claim_ids,
    extract_claim_block,
    PORTABLE_STATEMENT_PATH_RE,
)


YAML_STATEMENTS = """statements:
  - id: EVAR-026
    text: Первый текст утверждения.
    excerpt: Первый фрагмент.
  - id: EVAR-027
    text: Второй текст утверждения.
    excerpt: Второй фрагмент.
"""


def main() -> int:
    assert collect_claim_ids(YAML_STATEMENTS) == {"EVAR-026", "EVAR-027"}
    first = extract_claim_block(YAML_STATEMENTS, "EVAR-026")
    assert first.startswith("- id: EVAR-026")
    assert "Первый текст утверждения." in first
    assert "EVAR-027" not in first
    assert extract_claim_block(YAML_STATEMENTS, "EVAR-999") == ""

    assert PORTABLE_STATEMENT_PATH_RE.fullmatch(
        "knowledge/data/example/pages/overview/statements.yml",
    )
    assert PORTABLE_STATEMENT_PATH_RE.fullmatch(
        "knowledge/data/example/items/overview/statements.yml",
    )
    assert PORTABLE_STATEMENT_PATH_RE.fullmatch(
        "knowledge/data/example/sections/part-1/overview/statements.yml",
    )
    assert not PORTABLE_STATEMENT_PATH_RE.fullmatch(
        "knowledge/data/example/statements.yml",
    )
    assert not PORTABLE_STATEMENT_PATH_RE.fullmatch(
        "knowledge/data/example/pages/../outside/statements.yml",
    )

    print("Проверки разбора утверждений корпуса пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
