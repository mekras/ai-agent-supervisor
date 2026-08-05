#!/usr/bin/env python3
"""Проверки валидатора переносимости навыков."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / ".apm/skills/ai-setup-apm/scripts/eval-tools/validate-skill-portability.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_skill(root: Path, frontmatter: str, procedure: str, script: str) -> None:
    skill = root / "навык с пробелом"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: example\n{frontmatter}---\n\n# Example\n\n"
        f"## Переносимость\n\n{procedure}\n",
        encoding="utf-8",
    )
    (scripts / "check.py").write_text(script, encoding="utf-8")
    fixture = skill / "evals" / "script-fixtures" / "empty"
    fixture.mkdir(parents=True)
    (skill / "evals" / "script-contract-tests.json").write_text(
        """{
  "version": 1,
  "cases": [
    {
      "id": "check",
      "script": "scripts/check.py",
      "fixture": "evals/script-fixtures/empty",
      "command": ["{python}", "{script}"],
      "expect": {"stdout_contains": ["ok"]}
    }
  ]
}
""",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="переносимость ") as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта. Если Python недоступен, проверка помечается как невыполненная.",
            "#!/usr/bin/env python3\nimport json\nprint(json.dumps({'ok': True}))\n",
        )
        passed = run(root)
        assert passed.returncode == 0, passed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "",
            "Скрипт обязателен.",
            "#!/usr/bin/env python3\nimport yaml\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "нет поля compatibility" in failed.stderr
        assert "не описан базовый маршрут P0" in failed.stderr
        assert "сторонние импорты запрещены: yaml" in failed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает, если Python отсутствует.",
            "#!/usr/bin/env python3\n# pip install unsafe\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "скрытая установка" in failed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        skill = root / "навык с пробелом"
        scripts = skill / "scripts"
        scripts.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            """---
name: example
compatibility: P0 не требует Python. P1 требует Python 3.
---

# Example

## Переносимость

P0 работает без скрипта. Если Python недоступен, проверка помечается как невыполненная.
""",
            encoding="utf-8",
        )
        (scripts / "check.py").write_text("print('ok')\n", encoding="utf-8")
        failed = run(root)
        assert failed.returncode == 1
        assert "script-contract-tests.json" in failed.stderr

    print("Валидатор переносимости навыков проверен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
