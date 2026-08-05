#!/usr/bin/env python3
"""Регрессионные проверки запрета Python-байткода в источниках APM."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "tools" / "validate-python-artifacts.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / ".apm"
        (source / "skills" / "example" / "SKILL.md").parent.mkdir(parents=True)
        (source / "skills" / "example" / "SKILL.md").write_text("# Example\n", encoding="utf-8")
        passed = run(source)
        assert passed.returncode == 0, passed.stderr

        cache = source / "skills" / "example" / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "check.cpython-313.pyc").write_bytes(b"bytecode")
        failed_cache = run(source)
        assert failed_cache.returncode == 1
        assert "scripts/__pycache__" in failed_cache.stderr

        for path in sorted(cache.iterdir()):
            path.unlink()
        cache.rmdir()
        bytecode = source / "skills" / "example" / "module.pyo"
        bytecode.write_bytes(b"bytecode")
        failed_file = run(source)
        assert failed_file.returncode == 1
        assert "module.pyo" in failed_file.stderr

    print("Запрет скомпилированных Python-артефактов проверен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
