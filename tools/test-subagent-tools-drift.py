#!/usr/bin/env python3
"""Проверяет манифест и контроль дрейфа средств подагентов."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".apm/skills/ai-setup-subagents/scripts"
CHECKER = SCRIPTS / "check-subagent-tools-drift.py"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CHECKER), *arguments], text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for profile, installer in (("portable", "install-subagent-tools"), ("codex", "install-codex-tools"), ("claude", "install-claude-tools")):
            project = root / profile
            installed = subprocess.run(
                [str(SCRIPTS / installer), str(project)], text=True, encoding="utf-8",
                errors="replace", capture_output=True, check=False,
            )
            assert installed.returncode == 0, installed.stderr
            checked = run("--profile", profile, "--project-root", str(project))
            assert checked.returncode == 0, checked.stderr

        changed = root / "claude/tools/run-execution-class"
        changed.write_bytes(changed.read_bytes() + b"\n")
        checked = run("--profile", "claude", "--project-root", str(root / "claude"))
        assert checked.returncode == 1
        assert "расхождение: tools/run-execution-class" in checked.stderr

    print("Проверка дрейфа средств подагентов пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
