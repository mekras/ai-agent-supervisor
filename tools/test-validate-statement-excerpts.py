#!/usr/bin/env python3
"""Регрессионные проверки непрерывности цитат утверждений."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "validate_statement_excerpts",
    ROOT / "tools" / "validate-statement-excerpts.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_fixture(root: Path, excerpt: str, artifact: str) -> None:
    page = root / "data" / "source" / "pages" / "page"
    page.mkdir(parents=True)
    (page / "statements.yml").write_text(
        f"""statements:
  - id: TEST-001
    excerpt: |-
{excerpt}
    artifact: normalized.local.md
""",
        encoding="utf-8",
    )
    (page / "normalized.local.md").write_text(artifact, encoding="utf-8")


def indented(value: str) -> str:
    return "\n".join(f"      {line}" for line in value.splitlines())


def test_line_wrapping_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        corpus = Path(temporary)
        write_fixture(
            corpus,
            indented("The quote spans\nsource line wrapping."),
            "The quote spans source\nline wrapping.\n",
        )
        assert MODULE.validate(corpus) == []


def test_skipped_source_text_fails() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        corpus = Path(temporary)
        write_fixture(
            corpus,
            indented("First sentence.\nThird sentence."),
            "First sentence.\nSecond sentence.\nThird sentence.\n",
        )
        errors = MODULE.validate(corpus)
        assert len(errors) == 1
        assert "не найдена непрерывно" in errors[0]


def main() -> int:
    test_line_wrapping_is_ignored()
    test_skipped_source_text_fails()
    print("Проверки непрерывности цитат утверждений пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
