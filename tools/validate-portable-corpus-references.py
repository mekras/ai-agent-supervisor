#!/usr/bin/env python3
"""Reject historical corpus layers and references in published skill materials."""

from __future__ import annotations

import re
import sys
from pathlib import Path


HISTORICAL_REFERENCE = re.compile(
    r"historical-statements\.md|knowledge/(?:inventory|primary|normalized|statements|reports)/"
)
TEXT_SUFFIXES = {".md", ".json", ".yml", ".yaml", ".py", ".sh"}


def main() -> int:
    roots = [Path(".apm/skills"), Path("knowledge")]
    errors: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if path.name == Path(__file__).name:
                continue
            content = path.read_text(encoding="utf-8")
            for match in HISTORICAL_REFERENCE.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                errors.append(f"{path}:{line}: historical corpus reference: {match.group()}")

    for path in Path("knowledge/data").rglob("historical-statements.md"):
        errors.append(f"{path}: historical statement archive must not exist")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Исторических слоёв и ссылок корпуса не найдено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
