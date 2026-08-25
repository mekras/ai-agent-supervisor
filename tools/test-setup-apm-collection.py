#!/usr/bin/env python3
"""Проверки создания манифеста APM без внешнего YAML-пакета."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / ".apm/skills/ai-setup-apm/scripts/setup-apm-collection"


def run(project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SETUP), str(project), *extra],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="навык с пробелом ") as temporary:
        project = Path(temporary)
        shutil.copytree(
            ROOT / ".apm" / "skills" / "ai-setup-apm",
            project / ".apm" / "skills" / "ai-setup-apm",
        )
        created = run(
            project,
            "--name",
            "example-package",
            "--description",
            "Example collection",
            "--target",
            "codex",
            "--target",
            "claude",
        )
        assert created.returncode == 0, created.stderr
        manifest = (project / "apm.yml").read_text(encoding="utf-8")
        assert 'name: "example-package"' in manifest
        assert '  - "codex"' in manifest
        assert '  - "claude"' in manifest
        assert 'tests: "python tools/run-collection-checks.py"' in manifest
        assert 'evals: "python tools/run-skill-evals.py"' in manifest
        assert (project / ".apm" / "skills").is_dir()
        assert (project / "tools" / "run-collection-checks.py").is_file()
        assert (project / "tools" / "validate-skill-descriptions.py").is_file()
        assert (project / "tools" / "validate-python-artifacts.py").is_file()
        assert (project / "tools" / "validate-python-syntax.py").is_file()
        assert (project / "tools" / "run-apm-safe.py").is_file()
        assert (project / "tools" / "run-skill-script-contract-tests.py").is_file()
        checks = subprocess.run(
            [sys.executable, str(project / "tools" / "run-collection-checks.py")],
            cwd=project,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert checks.returncode == 0, checks.stdout + checks.stderr

        cache = project / ".apm" / "skills" / "example" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "check.cpython-313.pyc").write_bytes(b"bytecode")
        rejected = subprocess.run(
            [sys.executable, str(project / "tools" / "run-collection-checks.py")],
            cwd=project,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert rejected.returncode == 1
        assert "скомпилированные Python-артефакты" in rejected.stderr

        repeated = run(project)
        assert repeated.returncode == 2
        assert "уже существует" in repeated.stderr
        assert (project / "apm.yml").read_text(encoding="utf-8") == manifest

    help_result = subprocess.run(
        [sys.executable, str(SETUP), "--help"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert help_result.returncode == 0
    assert "Create apm.yml" in help_result.stdout
    print("Создание apm.yml и оснастки проверок без внешнего YAML-пакета проверено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
