#!/usr/bin/env python3
"""Проверить, что выпуск ждёт общую матрицу переносимости."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PORTABILITY = ROOT / ".github" / "workflows" / "portability.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
CHECKS = ROOT / ".github" / "workflows" / "portability-checks.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def jobs(text: str) -> str:
    marker = "jobs:\n"
    assert marker in text
    return text.split(marker, 1)[1]


def main() -> int:
    checks = read(CHECKS)
    portability = read(PORTABILITY)
    release = read(RELEASE)

    assert "workflow_call:" in checks
    assert "windows-latest" in checks
    assert "macos-latest" in checks
    assert "ubuntu-latest" in checks
    assert "deterministic-tests:" in checks
    assert jobs(portability) == jobs(checks)
    assert "verify-portability:" in release
    assert "needs: verify-portability" in release
    assert release.index("needs: verify-portability") < release.index("name: Проверить и опубликовать")
    print("Выпуск ожидает общую матрицу переносимости.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
