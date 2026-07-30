#!/usr/bin/env python3
"""Проверки обновления существующего манифеста APM."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / ".apm" / "skills" / "ai-setup-apm" / "scripts" / "setup-apm-collection"


def run_setup(project: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SETUP),
            str(project),
            "--test-command",
            "python3 tools/check.py",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def assert_duplicate_keys_are_rejected(project: Path) -> None:
    (project / "apm.yml").write_text(
        """name: duplicate-keys
scripts: {}
scripts: {}
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SETUP), str(project), "--test-command", "python3 tools/check.py"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode != 0
    assert "duplicate key 'scripts'" in result.stderr


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        tools = project / "tools"
        tools.mkdir()
        (tools / "run-skill-evals.py").write_text("", encoding="utf-8")
        (project / "apm.yml").write_text(
            """name: existing-package
version: 1.2.3
description: Existing package
author: Example author
license: MIT
target: codex
includes: {skills: .apm/skills}
scripts: {tests: old-command, custom: keep-me}
dependencies: {apm: [example/package]}
devDependencies: {apm: [example/development]}
""",
            encoding="utf-8",
        )

        run_setup(project)
        first_run = (project / "apm.yml").read_text(encoding="utf-8")
        run_setup(project)
        second_run = (project / "apm.yml").read_text(encoding="utf-8")

        assert second_run == first_run
        assert second_run.count("scripts:") == 1
        assert second_run.count("includes:") == 1

        manifest = yaml.safe_load(second_run)
        assert manifest["name"] == "existing-package"
        assert manifest["version"] == "1.2.3"
        assert manifest["author"] == "Example author"
        assert manifest["license"] == "MIT"
        assert manifest["target"] == "codex"
        assert manifest["includes"] == {"skills": ".apm/skills"}
        assert manifest["scripts"] == {
            "tests": "python3 tools/check.py",
            "evals": 'python3 tools/run-skill-evals.py "${APM_EVAL_PATH:-.apm/skills}"',
            "custom": "keep-me",
        }
        assert manifest["dependencies"] == {
            "apm": ["example/package"],
            "mcp": [],
        }
        assert manifest["devDependencies"] == {"apm": ["example/development"]}
        assert_duplicate_keys_are_rejected(project)

    print("Повторное обновление apm.yml прошло без дублированных ключей.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
