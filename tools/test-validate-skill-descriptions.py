#!/usr/bin/env python3
"""Check description validation at the CLI boundary (REQ-0014)."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "tools/validate-skill-descriptions.py"


def main() -> int:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for key in ("APM_SKILL_DESCRIPTION_MAX_CHARS", "APM_SKILL_DESCRIPTION_TOTAL_MAX_CHARS"):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="skill-description-test-") as temp:
        root = Path(temp)
        # More than the former per-skill and collection budgets, within the format limit.
        for i in range(12):
            skill = root / f"skill-{i}"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: sample\ndescription: " + "x" * 200 + "\n---\n", encoding="utf-8")

        def run(*args: str, expected: int, extra_env: dict[str, str] | None = None) -> str:
            result = subprocess.run([sys.executable, str(VALIDATOR), str(root), *args], env=env | (extra_env or {}), capture_output=True, text=True)
            assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
            return result.stdout + result.stderr

        run(expected=0)
        run("--max-description-chars", "180", expected=1)
        run("--max-total-chars", "2200", expected=1)
        run(expected=1, extra_env={"APM_SKILL_DESCRIPTION_MAX_CHARS": "180"})
        run("--max-total-chars", "0", expected=1)
        first = root / "skill-0/SKILL.md"
        first.write_text("---\nname: sample\ndescription: " + "x" * 1025 + "\n---\n", encoding="utf-8")
        assert "spec limit" in run(expected=1)
        first.write_text("---\nname: sample\n---\n", encoding="utf-8")
        assert "missing non-empty description" in run(expected=1)
    print("Description CLI checks: 7 passed. Content quality was not evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
